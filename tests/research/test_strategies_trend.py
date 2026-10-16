"""Tests for apps.research.strategies.trend (PLAN §2.2, §2.3, §6.2 R08).

Unit tests use small hand-built close series (allowed for formula checks).
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.portfolio.sizing import discretize
from apps.research.strategies.base import TargetWeightStrategy
from apps.research.strategies.trend import (
    DON_WINDOWS,
    SHORT_SIZING_STEP,
    TREND_CONFIGS,
    TSM_WINDOWS,
    StrategyError,
    TrendStrategy,
    TrendWithShort,
    btc_below_sma,
    don_signal,
    donchian_trail,
    make_short,
    make_trend,
    mix_signal,
    sizing_config,
    tsm_signal,
)

NAN = np.nan
# Hand-made path (n = 3): no breakout at t3 (C = UP = 10); breakout at t4 (C=14 > UP=10,
# S = MID = 10); S ratchets to 12 (t5), 12 (t6), 13 (t7); at t8 MID falls to 12.5 but S
# stays at 13; at t9 C = 12.9 < S = 13 -> exit (it would have held with S = MID = 12.5).
HAND = [10, 10, 10, 10, 14, 12, 12, 13, 13, 12.9]
HAND_POS = [NAN, NAN, NAN, 0, 1, 1, 1, 1, 1, 0]
HAND_STOP = [NAN, NAN, NAN, NAN, 10, 12, 12, 13, 13, NAN]


def series(values, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="1D", tz="UTC")
    return pd.Series(np.asarray(values, dtype=float), index=idx, name="close")


def frame(close):
    c = close if isinstance(close, pd.Series) else series(close)
    o = c.shift(1).fillna(c)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99,
                         "close": c, "volume": 1e6}, index=c.index)


def funding_for(idx, rate=1e-4, overrides=None):
    """8h settlements covering the daily index (starting 3 days before it)."""
    times = pd.date_range(idx[0] - pd.Timedelta(days=3), idx[-1] + pd.Timedelta(days=1),
                          freq="8h", tz="UTC")
    f = pd.Series(rate, index=times, name="funding_rate")
    for t, v in (overrides or {}).items():
        f[f.index >= pd.Timestamp(t, tz="UTC")] = v
    return f


def assert_series(actual, expected):
    np.testing.assert_allclose(np.asarray(actual, dtype=float), np.asarray(expected, dtype=float),
                               equal_nan=True)


# --------------------------------------------------------------------------- DON
def test_donchian_long_entry_trailing_and_exit_by_hand():
    st = donchian_trail(series(HAND), 3, side=1)
    assert_series(st["pos"], HAND_POS)
    assert_series(st["stop"], HAND_STOP)
    in_pos = st["pos"] == 1
    assert (st["stop"][in_pos].diff().dropna() >= 0).all()      # trailing only in favour


def test_donchian_short_mirror_by_hand():
    st = donchian_trail(series([30 - x for x in HAND]), 3, side=-1)
    assert_series(st["pos"], HAND_POS)
    assert_series(st["stop"], [NAN, NAN, NAN, NAN, 20, 18, 18, 17, 17, NAN])


def test_don_signal_is_mean_of_submodels_and_waits_for_warmup():
    c = series(HAND + [14, 15])
    e = don_signal(c, windows=(3, 5))
    p3 = donchian_trail(c, 3)["pos"]
    p5 = donchian_trail(c, 5)["pos"]
    assert e.iloc[:5].isna().all()                  # 5-window not defined before t5
    assert_series(e.iloc[5:], ((p3 + p5) / 2).iloc[5:])
    assert e.dropna().between(0, 1).all()


def test_don_no_reentry_on_exit_bar_and_hole_keeps_state():
    c = series(HAND)
    c.iloc[6] = np.nan                              # missing close inside the trade
    e = don_signal(c, windows=(3,))
    assert e.iloc[6] == 1.0                         # state kept, no exit without a price
    st = donchian_trail(c, 3)
    assert st["stop"].iloc[6] == st["stop"].iloc[5]


# --------------------------------------------------------------------------- TSM / MIX
def test_tsm_signal_by_hand():
    # windows (2, 3): SMA2 = mean(C_{t-1}, C_t), SMA3 = mean(C_{t-2..t}).
    c = series([10, 12, 11, 9, 13])
    e = tsm_signal(c, windows=(2, 3))
    # t2: C=11 vs SMA2=11.5 (no), SMA3=11 (no, not strictly) -> 0
    # t3: C=9 vs 10 (no), 10.67 (no) -> 0
    # t4: C=13 vs 11 (yes), 11 (yes) -> 1
    assert_series(e, [NAN, NAN, 0.0, 0.0, 1.0])
    c2 = series([10, 12, 13, 12.4])
    # t3: SMA2 = 12.7 (no), SMA3 = 12.47 (no) ; t2: 12.5 yes, 11.67 yes
    assert_series(tsm_signal(c2, windows=(2, 3)), [NAN, NAN, 1.0, 0.0])
    c3 = series([10, 14, 12, 12.5])
    # t3: SMA2 = 12.25 (yes), SMA3 = 12.83 (no) -> 0.5
    assert tsm_signal(c3, windows=(2, 3)).iloc[3] == 0.5


def test_mix_is_half_don_half_tsm():
    c = series(HAND + [14, 15, 16])
    don = don_signal(c, (3, 5))
    tsm = tsm_signal(c, (2, 3))
    mix = mix_signal(c, (3, 5), (2, 3))
    assert_series(mix, 0.5 * don + 0.5 * tsm)


def test_default_windows_and_configs():
    assert DON_WINDOWS == (5, 10, 20, 30, 60, 90, 150, 250, 360)
    assert TSM_WINDOWS == (10, 20, 40, 50, 100, 200)
    kinds = {k: (v.signal, v.sigma_target, v.band) for k, v in TREND_CONFIGS.items()}
    assert kinds == {"T1": ("DON", 0.15, 0.20), "T2": ("TSM", 0.15, 0.20), "T3": ("MIX", 0.15, 0.20),
                     "T4": ("MIX", 0.20, 0.20), "T5": ("MIX", 0.15, 0.10)}
    assert make_trend("T1").kind == "DON" and make_trend("T2").kind == "TSM"
    assert sizing_config("T4").sigma_target == 0.20 and sizing_config("T5").band == 0.10
    assert sizing_config("T3").step == 0.25
    assert sizing_config("S1").step == SHORT_SIZING_STEP
    assert isinstance(make_trend("T3"), TargetWeightStrategy)
    with pytest.raises(StrategyError):
        make_trend("T9")
    with pytest.raises(StrategyError):
        make_short("S3")


def test_trend_strategy_panel_signal():
    panel = {"AAAUSDT": frame(HAND + [14, 15]), "BBBUSDT": frame([30 - x for x in HAND] + [14, 15])}
    strat = TrendStrategy(kind="DON", don_windows=(3,))
    E = strat.signal(panel, None)
    assert list(E.columns) == ["AAAUSDT", "BBBUSDT"]
    assert_series(E["AAAUSDT"].iloc[:10], HAND_POS)
    assert E.stack().dropna().between(0, 1).all()


# --------------------------------------------------------------------------- SHORT
def short_setup(btc_close, funding_overrides=None, k=0.5):
    sym = frame([30 - x for x in HAND])
    btc = frame(btc_close)
    panel = {"BTCUSDT": btc, "AAAUSDT": sym}
    funding = {s: funding_for(sym.index, overrides=funding_overrides) for s in panel}
    strat = TrendWithShort(long=TrendStrategy(kind="DON", don_windows=(3,)), k=k, windows=(3,),
                           btc_sma=3, funding=funding)
    return strat, panel


BTC_DOWN = [100 - i for i in range(10)]     # C < SMA3 from t2 on: short gate active


def test_short_leg_mirror_with_btc_gate():
    strat, panel = short_setup(BTC_DOWN)
    assert_series(strat.short_signal(panel)["AAAUSDT"], HAND_POS)
    E = strat.signal(panel)["AAAUSDT"]
    # Long DON(3) never enters on this falling path: E = 0 - 0.5 * E_s.
    assert_series(E, [NAN, NAN, NAN, 0, -0.5, -0.5, -0.5, -0.5, -0.5, 0])


def test_short_gate_off_when_btc_above_sma():
    strat, panel = short_setup([100 + i for i in range(10)])
    assert (strat.short_signal(panel)["AAAUSDT"].dropna() == 0).all()
    # Gate switching off while short closes the leg.
    btc = BTC_DOWN[:6] + [200, 210, 220, 230]
    strat, panel = short_setup(btc)
    es = strat.short_signal(panel)["AAAUSDT"]
    assert es.iloc[4] == 1 and es.iloc[5] == 1 and (es.iloc[6:] == 0).all()


def test_short_funding_veto_blocks_new_shorts_only():
    # Huge negative funding from the 00:00 settlement that closes t4: the entry at t4 is vetoed.
    strat, panel = short_setup(BTC_DOWN, {"2024-01-06": -0.01})
    assert (strat.short_signal(panel)["AAAUSDT"].dropna() == 0).all()
    # Veto starting after the entry (close of t5): the open short is kept until its exit.
    strat, panel = short_setup(BTC_DOWN, {"2024-01-07": -0.01})
    assert_series(strat.short_signal(panel)["AAAUSDT"], HAND_POS)


def test_short_veto_when_apr_unknown_and_missing_funding_raises():
    strat, panel = short_setup(BTC_DOWN)
    strat.funding = {s: f[f.index >= pd.Timestamp("2024-01-05", tz="UTC")] for s, f in strat.funding.items()}
    # 9 settlements are needed for F_bar_3d: the APR at t4 is unknown -> no entry.
    assert strat.short_signal(panel)["AAAUSDT"].iloc[4] == 0
    strat.funding = {"BTCUSDT": strat.funding["BTCUSDT"]}
    with pytest.raises(StrategyError):
        strat.short_signal(panel)


def test_short_excludes_bnb_and_needs_btc():
    strat, panel = short_setup(BTC_DOWN)
    panel["BNBUSDT"] = panel.pop("AAAUSDT")      # BNB funding is never read
    assert (strat.short_signal(panel)["BNBUSDT"] == 0).all()
    strat2 = TrendWithShort(long=make_trend("T3"), k=0.5, funding={})
    with pytest.raises(StrategyError):
        strat2.short_signal({"AAAUSDT": frame(HAND)})
    with pytest.raises(StrategyError):
        TrendWithShort(long=make_trend("T3"), k=0.3)


@pytest.mark.parametrize("k", [0.5, 0.25])
def test_combined_signal_on_sixteenth_grid(k):
    strat, panel = short_setup(BTC_DOWN, k=k)
    strat.long = TrendStrategy(kind="MIX", don_windows=(3,), tsm_windows=(2, 3))
    E = strat.signal(panel)
    vals = E.stack().dropna()
    assert vals.between(-0.5, 1).all()
    pd.testing.assert_frame_equal(discretize(E, SHORT_SIZING_STEP), E)
    assert make_short("S1").k == 0.5 and make_short("S2").k == 0.25


# --------------------------------------------------------------------------- causality
def smooth_path(n, seed_phase=0.0, drift=0.0005):
    i = np.arange(n, dtype=float)
    r = 0.03 * np.sin(i / 9 + seed_phase) + 0.02 * np.sin(i / 37 + 2 * seed_phase) + drift
    return 100 * np.exp(np.cumsum(r * 0.5))


@pytest.fixture(scope="module")
def causal_panel():
    n = 700
    panel = {"BTCUSDT": frame(series(smooth_path(n, 0.0))),
             "ETHUSDT": frame(series(smooth_path(n, 1.3, -0.001))),
             "BNBUSDT": frame(series(smooth_path(n, 2.1)))}
    idx = panel["BTCUSDT"].index
    times = pd.date_range(idx[0] - pd.Timedelta(days=3), idx[-1] + pd.Timedelta(days=1), freq="8h", tz="UTC")
    k = np.arange(len(times), dtype=float)
    funding = {s: pd.Series(1e-4 + 6e-4 * np.sin(k / 40 + j), index=times, name="funding_rate")
               for j, s in enumerate(["BTCUSDT", "ETHUSDT"])}
    return panel, funding


def truncated(panel, funding, t):
    p = {s: df.loc[:t] for s, df in panel.items()}
    f = {s: x.loc[: t + pd.Timedelta(days=1)] for s, x in funding.items()}
    return p, f


TRUNC_DATES = [400, 455, 520, 610, 699]


@pytest.mark.parametrize("build", [
    lambda f: make_trend("T1"),
    lambda f: make_trend("T2"),
    lambda f: make_trend("T3"),
    lambda f: make_short("S1", funding=f),
    lambda f: make_short("S2", funding=f),
], ids=["T1", "T2", "T3", "S1", "S2"])
def test_signal_invariant_to_truncation(causal_panel, build):
    panel, funding = causal_panel
    full = build(funding).signal(panel, None)
    assert full.iloc[400:].notna().all().all()
    assert (full.iloc[400:].abs().sum() > 0).any()            # non-trivial signal
    for i in TRUNC_DATES:
        t = full.index[i]
        p, f = truncated(panel, funding, t)
        part = build(f).signal(p, None)
        pd.testing.assert_series_equal(part.loc[t], full.loc[t], check_names=False)


def test_btc_below_sma_gate():
    g = btc_below_sma(frame([10, 9, 8, 9, 12]), 3)
    assert_series(g, [NAN, NAN, 1.0, 0.0, 0.0])   # t3: C=9 vs SMA3=8.67 -> not below


# --------------------------------------------------------------------------- real data
DATA_ROOT = Path(os.environ.get("RESEARCH_DATA_ROOT", "/home/user/harness/data"))


@pytest.mark.skipif(not (DATA_ROOT / "futures" / "BTCUSDT_1d.csv").is_file(), reason="harness data not present")
def test_real_data_signals_causal_on_debug_period():
    """Signals only (no metrics) on the free debug period, up to 2021-12 (PLAN §5.3)."""
    from apps.research.data.loader import load_funding, load_ohlcv

    panel = {s: load_ohlcv(s, "futures", "1d", end="2021-12-31", root=DATA_ROOT) for s in ("BTCUSDT", "ETHUSDT")}
    funding = {s: load_funding(s, root=DATA_ROOT) for s in panel}
    full = make_short("S1", funding=funding).signal(panel, None)
    assert full.iloc[-60:].notna().all().all()
    for t in full.index[-90::30]:
        p = {s: df.loc[:t] for s, df in panel.items()}
        f = {s: x.loc[: t + pd.Timedelta(days=1)] for s, x in funding.items()}
        pd.testing.assert_series_equal(make_short("S1", funding=f).signal(p, None).loc[t], full.loc[t],
                                       check_names=False)
