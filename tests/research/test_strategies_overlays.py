"""Tests for apps.research.strategies.overlays (PLAN §2.4, §2.5, §6.2 R09).

Unit tests use small hand-built series (allowed for formula checks).
"""
import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.portfolio_bt import BTError, run_portfolio_bt
from apps.research.features.funding import funding_features
from apps.research.portfolio.sizing import SizingConfig, discretize
from apps.research.strategies.base import WeightOverlayStrategy
from apps.research.strategies.overlays import (
    FVETO_CONFIGS,
    FundingVeto,
    RegimeOverlay,
    block_increases,
    funding_trigger,
    regime_multiplier,
)
from apps.research.strategies.trend import StrategyError, make_short, make_trend

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)


def series(values, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="1D", tz="UTC")
    return pd.Series(np.asarray(values, dtype=float), index=idx, name="close")


def frame(close):
    c = close if isinstance(close, pd.Series) else series(close)
    o = c.shift(1).fillna(c)
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99,
                       "close": c, "volume": 1e9}, index=c.index)
    df["quote_volume"] = df["volume"] * df["close"]
    return df


class Fixed:
    """Target-weight strategy returning a precomputed signal."""

    name = "fixed"
    params: dict = {}
    n_free_params = 0

    def __init__(self, signal: dict):
        self._signal = signal

    def signal(self, panel, ctx=None):
        idx = next(iter(panel.values())).index
        return pd.DataFrame(self._signal, index=idx)


def funding_for(idx, rate=1e-4, spikes=None):
    times = pd.date_range(idx[0] - pd.Timedelta(days=3), idx[-1] + pd.Timedelta(days=1),
                          freq="8h", tz="UTC")
    f = pd.Series(rate, index=times, name="funding_rate")
    for t, v in (spikes or {}).items():
        f[pd.Timestamp(t, tz="UTC")] = v
    return f


# --------------------------------------------------------------------------- REGIME
def btc_rise_then_crash():
    """230 rising closes, then 30 closes at 50."""
    return frame(np.r_[100.0 + np.arange(230), np.full(30, 50.0)])


def hand_conditions(c: np.ndarray, i: int):
    s200 = c[i - 199:i + 1].mean()
    s50 = c[i - 49:i + 1].mean()
    return c[i] > s200, s50 > s200


def test_regime_rules_by_hand():
    btc = btc_rise_then_crash()
    c = btc["close"].to_numpy()
    m1, m2 = regime_multiplier(btc, "R1"), regime_multiplier(btc, "R2")
    # Undefined SMA200 (first 199 bars): never reduce.
    assert (m1.iloc[:199] == 1).all() and (m2.iloc[:199] == 1).all()
    # Before the crash: C > SMA200 and SMA50 > SMA200.
    assert hand_conditions(c, 229) == (True, True)
    assert m1.iloc[229] == 1.0 and m2.iloc[229] == 1.0
    # First crash day: C < SMA200, SMA50 still > SMA200.
    assert hand_conditions(c, 230) == (False, True)
    assert m1.iloc[230] == 0.5 and m2.iloc[230] == 0.5
    # Last day: neither condition.
    assert hand_conditions(c, 259) == (False, False)
    assert m1.iloc[259] == 0.5 and m2.iloc[259] == 0.25


def test_regime_r3_halves_on_high_atr_percentile():
    btc = btc_rise_then_crash()
    m2 = regime_multiplier(btc, "R2")
    m3 = regime_multiplier(btc, "R3", pctl_min_days=30)
    # The crash bar has the largest ATR% so far: percentile 100 > 80 -> x0.5.
    assert m3.iloc[230] == 0.5 * m2.iloc[230] == 0.25
    ratio = (m3 / m2).dropna()
    assert set(np.round(ratio.unique(), 12)) <= {0.5, 1.0}
    # With the default 365-day minimum the percentile is undefined: R3 == R2.
    pd.testing.assert_series_equal(regime_multiplier(btc, "R3"), m2, check_names=False)
    for rule in ("R1", "R2", "R3"):
        m = regime_multiplier(btc, rule, pctl_min_days=30)
        assert ((m > 0) & (m <= 1)).all()
    with pytest.raises(StrategyError):
        regime_multiplier(btc, "R4")


def test_regime_overlay_only_scales_long_weights():
    btc = btc_rise_then_crash()
    n = len(btc)
    sig = {"BTCUSDT": np.ones(n), "AAAUSDT": np.r_[np.zeros(n - 10), np.full(10, -0.5)]}
    panel = {"BTCUSDT": btc, "AAAUSDT": frame(np.linspace(10, 5, n))}
    ov = RegimeOverlay(Fixed(sig), "R1")
    assert isinstance(ov, WeightOverlayStrategy)
    pd.testing.assert_frame_equal(ov.signal(panel), Fixed(sig).signal(panel))
    m = ov.weight_multiplier(panel)
    assert (m["BTCUSDT"].iloc[230:] == 0.5).all() and (m["BTCUSDT"].iloc[:230] == 1).all()
    assert (m["AAAUSDT"] == 1).all()                 # flat / short rows untouched
    with pytest.raises(StrategyError):
        RegimeOverlay(Fixed(sig), "R1").weight_multiplier({"AAAUSDT": panel["AAAUSDT"]})


# --------------------------------------------------------------------------- FVETO
E_PATH = [0, 0.25, 0.5, 0.5, 0.75, 1, 0.5, 0.75, 1, 1]
# A 1% settlement at 2024-01-05 00:00 enters F_bar_3d for the closes of 01-05, 01-06 and
# 01-07 (rows 3, 4, 5): APR > 50 % there. fund_pct is undefined (< 180 days).
SPIKE = {"2024-01-05 00:00": 0.01}
TRIGGER_ROWS = [3, 4, 5]


def fveto_setup(rule, funding_spikes=SPIKE, bnb_too=False):
    panel = {"AAAUSDT": frame(np.linspace(10, 12, len(E_PATH)))}
    sig = {"AAAUSDT": E_PATH}
    funding = {"AAAUSDT": funding_for(panel["AAAUSDT"].index, spikes=funding_spikes)}
    if bnb_too:
        panel["BNBUSDT"] = frame(np.linspace(10, 12, len(E_PATH)))
        sig["BNBUSDT"] = E_PATH
        funding["BNBUSDT"] = funding_for(panel["BNBUSDT"].index, rate=0.01)
    return FundingVeto(Fixed(sig), rule, funding=funding), panel


def test_funding_trigger_rows_by_hand():
    ov, panel = fveto_setup("F1")
    trig = ov.triggers(panel)["AAAUSDT"]
    assert list(np.flatnonzero(trig.to_numpy())) == TRIGGER_ROWS


def test_block_increases_by_hand():
    E = series(E_PATH)
    blocked = pd.Series(False, index=E.index)
    blocked.iloc[TRIGGER_ROWS] = True
    out = block_increases(E, blocked)
    assert out.tolist() == [0, 0.25, 0.5, 0.5, 0.5, 0.5, 0.5, 0.75, 1, 1]
    # Reductions pass through while blocked; NaN stays NaN and resets the state.
    E2 = series([0.5, 0.25, np.nan, 0.75])
    out2 = block_increases(E2, pd.Series([False, True, True, True], index=E2.index))
    assert out2.iloc[0] == 0.5 and out2.iloc[1] == 0.25
    assert np.isnan(out2.iloc[2]) and out2.iloc[3] == 0.0
    # Blocked from the start: never enters.
    assert block_increases(E2, pd.Series(True, index=E2.index)).iloc[:2].tolist() == [0.0, 0.0]


def test_f1_blocks_new_long_entries_but_keeps_positions():
    ov, panel = fveto_setup("F1")
    E = ov.signal(panel)["AAAUSDT"]
    assert E.tolist() == [0, 0.25, 0.5, 0.5, 0.5, 0.5, 0.5, 0.75, 1, 1]
    assert (ov.weight_multiplier(panel) == 1).all().all()


def test_f2_halves_weights_and_f3_needs_percentile():
    ov, panel = fveto_setup("F2")
    pd.testing.assert_frame_equal(ov.signal(panel), Fixed({"AAAUSDT": E_PATH}).signal(panel))
    m = ov.weight_multiplier(panel)["AAAUSDT"]
    expected = np.ones(len(E_PATH))
    expected[TRIGGER_ROWS] = 0.5
    np.testing.assert_allclose(m, expected)
    ov3, panel3 = fveto_setup("F3")                 # fund_pct undefined: never fires
    assert (ov3.weight_multiplier(panel3) == 1).all().all()


def test_fveto_excludes_bnb():
    for rule in FVETO_CONFIGS:
        ov, panel = fveto_setup(rule, bnb_too=True)
        assert not ov.triggers(panel)["BNBUSDT"].any()
        assert ov.signal(panel)["BNBUSDT"].tolist() == E_PATH
        assert (ov.weight_multiplier(panel)["BNBUSDT"] == 1).all()
        del ov.funding["BNBUSDT"]                   # BNB funding is never required
        ov.signal(panel)
        ov.weight_multiplier(panel)
        del ov.funding["AAAUSDT"]
        with pytest.raises(StrategyError):
            ov.weight_multiplier(panel)


def test_fveto_unknown_rule():
    with pytest.raises(StrategyError):
        FundingVeto(Fixed({"A": [1]}), "F4")


# --------------------------------------------------------------------------- never increase
@pytest.fixture(scope="module")
def long_fixture():
    n = 700
    i = np.arange(n, dtype=float)

    def path(phase, drift):
        r = 0.03 * np.sin(i / 9 + phase) + 0.02 * np.sin(i / 37 + 2 * phase) + drift
        return 100 * np.exp(np.cumsum(r * 0.5))

    panel = {"BTCUSDT": frame(series(path(0.0, 0.0005))), "ETHUSDT": frame(series(path(1.3, -0.001))),
             "BNBUSDT": frame(series(path(2.1, 0.0)))}
    idx = panel["BTCUSDT"].index
    times = pd.date_range(idx[0] - pd.Timedelta(days=3), idx[-1] + pd.Timedelta(days=1), freq="8h", tz="UTC")
    k = np.arange(len(times), dtype=float)
    funding = {s: pd.Series(1e-4 + 6e-4 * np.sin(k / 40 + j), index=times, name="funding_rate")
               for j, s in enumerate(["BTCUSDT", "ETHUSDT"])}
    return panel, funding


def overlays_for(funding):
    base = make_trend("T3")
    out = {f"R{j}": RegimeOverlay(base, f"R{j}") for j in (1, 2, 3)}
    out.update({f: FundingVeto(base, f, funding=funding) for f in FVETO_CONFIGS})
    out["R2+F2"] = RegimeOverlay(FundingVeto(base, "F2", funding=funding), "R2")
    return base, out


def test_overlays_never_increase_exposure(long_fixture):
    panel, funding = long_fixture
    base, ovs = overlays_for(funding)
    E_base = discretize(base.signal(panel), 0.25)
    for name, ov in ovs.items():
        E = discretize(ov.signal(panel), 0.25)
        assert (E.fillna(0) <= E_base.fillna(0) + 1e-12).all().all(), name
        m = ov.weight_multiplier(panel)
        assert ((m > 0) & (m <= 1)).all().all(), name
        assert (m["BNBUSDT"] == 1).all() or name.startswith("R"), name
    # The trigger is the documented rule on the causal funding features.
    ov = ovs["F3"]
    feats = funding_features(funding["ETHUSDT"].copy(), panel["ETHUSDT"].index)
    pd.testing.assert_series_equal(ov.triggers(panel)["ETHUSDT"], funding_trigger(feats, FVETO_CONFIGS["F3"]),
                                   check_names=False)
    assert ov.triggers(panel)["ETHUSDT"].any()
    m_r2f2 = ovs["R2+F2"].weight_multiplier(panel)
    expected = ovs["R2"].weight_multiplier(panel) * ovs["F2"].weight_multiplier(panel)
    pd.testing.assert_frame_equal(m_r2f2, expected)


@pytest.mark.parametrize("name", ["R1", "R2", "R3", "F1", "F2", "F3"])
def test_overlay_invariant_to_truncation(long_fixture, name):
    panel, funding = long_fixture
    _, ovs = overlays_for(funding)
    full_e, full_m = ovs[name].signal(panel), ovs[name].weight_multiplier(panel)
    for i in (420, 515, 640, 699):
        t = full_e.index[i]
        p = {s: df.loc[:t] for s, df in panel.items()}
        f = {s: x.loc[: t + pd.Timedelta(days=1)] for s, x in funding.items()}
        _, part = overlays_for(f)
        pd.testing.assert_series_equal(part[name].signal(p).loc[t], full_e.loc[t], check_names=False)
        pd.testing.assert_series_equal(part[name].weight_multiplier(p).loc[t], full_m.loc[t],
                                       check_names=False)


def test_regime_overlay_on_short_strategy_leaves_shorts(long_fixture):
    panel, funding = long_fixture
    ov = RegimeOverlay(make_short("S1", funding=funding), "R1")
    E = ov.signal(panel)
    m = ov.weight_multiplier(panel)
    assert (E < 0).any().any()
    assert (m[E.fillna(0) <= 0] .fillna(1) == 1).all().all()


# --------------------------------------------------------------------------- engine hook
class Scaled(Fixed):
    def __init__(self, signal, mult):
        super().__init__(signal)
        self._mult = mult

    def weight_multiplier(self, panel, ctx=None):
        idx = next(iter(panel.values())).index
        return pd.DataFrame({s: np.full(len(idx), self._mult) for s in self._signal}, index=idx)


def run(strategy, panel, sizing=None):
    first = next(iter(panel.values())).index
    return run_portfolio_bt(strategy, panel, "spot", ZERO, sizing, None, start=first[100],
                            catastrophe_atr_mult=None, fixed_slip_bps=0.0)


def test_engine_applies_weight_multiplier(long_fixture):
    panel, _ = long_fixture
    panel = {s: panel[s] for s in ("BTCUSDT", "ETHUSDT")}
    n = len(panel["BTCUSDT"])
    sig = {s: np.r_[np.zeros(120), np.full(n - 120, 0.5)] for s in panel}
    # sizing=None: the signal is the weight.
    base, half = run(Fixed(sig), panel), run(Scaled(sig, 0.5), panel)
    first_fill = 21          # decided at the close of bar 120, filled at the open of 121
    assert base.weights.iloc[first_fill - 1].sum() == 0
    gross_b, gross_h = base.weights.iloc[first_fill].sum(), half.weights.iloc[first_fill].sum()
    assert gross_b == pytest.approx(1.0, rel=0.05)
    assert gross_h == pytest.approx(0.5 * gross_b, rel=0.05)
    # Layer D: the vol target does not undo the overlay.
    sz = SizingConfig()
    base_d, half_d = run(Fixed(sig), panel, sz), run(Scaled(sig, 0.5), panel, sz)
    gb, gh = base_d.weights.iloc[25:].abs().sum(axis=1), half_d.weights.iloc[25:].abs().sum(axis=1)
    assert gb.mean() > 0.1
    assert (gh <= 0.5 * gb * 1.25 + 1e-9).all()
    with pytest.raises(BTError):
        run(Scaled(sig, 1.5), panel)
