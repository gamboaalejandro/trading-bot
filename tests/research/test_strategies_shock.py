"""Tests for apps.research.strategies.shock (PLAN §2.9, §6.2 R12).

Small hand-built deterministic fixtures; the integration test reads the real
local data in the debug window (2020-09 .. 2021-12) and is skipped without it.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.event_bt import run_event_bt
from apps.research.features.volatility import atr
from apps.research.strategies._intraday import StrategyError
from apps.research.strategies.base import EventStrategy
from apps.research.strategies.shock import (
    SHOCK_CONFIGS,
    TAIL_EVENTS,
    Shock,
    long_signal,
    make_shock,
    shock_features,
    shock_zscore,
    tail_event_report,
)

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)
H1 = SHOCK_CONFIGS["H1"]
N1H = 900
SHOCK_BAR = 850


def wiggle_1h(n=N1H, start="2024-06-01", price=100.0, seed=0):
    """Deterministic small zig-zag 1h path (no shock) with a constant 1-unit range."""
    rng = np.random.default_rng(seed)
    close = price * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    open_ = np.r_[price, close[:-1]]
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1e6}, index=idx)


def btc_daily(end="2024-08-01", n=300, up=True):
    idx = pd.date_range(end=end, periods=n, freq="1D", tz="UTC")
    c = 100.0 * np.exp(np.arange(n) * (0.003 if up else -0.003))
    d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6}, index=idx)
    d["quote_volume"] = d["volume"] * d["close"]
    return d


def to_daily(df):
    d = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    d["quote_volume"] = d["volume"] * d["close"]
    return d


def shock(df, i, drop=0.06):
    df = df.copy()
    c = df["close"].iloc[i - 1] * (1 - drop)
    df.iloc[i, :4] = [df["close"].iloc[i - 1], df["close"].iloc[i - 1] + 0.5, c - 0.5, c]
    # The next bar opens where the shock closed (no gap).
    df.iloc[i + 1:, :4] = df.iloc[i + 1:, :4] * (c / df["close"].iloc[i])
    return df


# --------------------------------------------------------------------------- configs
def test_configs_h1_to_h3_are_time_exits_of_4_12_24_hours():
    assert {k: v["hold_bars"] for k, v in SHOCK_CONFIGS.items()} == {"H1": 4, "H2": 12, "H3": 24}
    for c in SHOCK_CONFIGS.values():
        assert c["z_entry"] == -3.0 and c["btc_sigma_mult"] == -2.0 and c["sigma_window"] == 720
        assert c["stop_atr"] == 2.0 and c["risk"] == 0.0025 and c["btc_sma_n"] == 200
    s = make_shock("H2")
    assert isinstance(s, EventStrategy) and s.name == "SHOCK-H2"
    with pytest.raises(StrategyError):
        Shock("H4")
    with pytest.raises(StrategyError):
        Shock("H1", risk=0.01)          # above the 0.5 % per-trade cap
    assert TAIL_EVENTS == ("2021-05-19", "2022-11-09", "2025-10-10")


# --------------------------------------------------------------------------- z-score
def test_z_uses_a_rolling_window_of_the_previous_bars():
    rng = np.random.default_rng(1)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 60))),
                      index=pd.date_range("2024-01-01", periods=60, freq="1h", tz="UTC"))
    z = shock_zscore(close, window=10, min_frac=1.0)
    r = close.pct_change()
    for i in (11, 30, 59):
        sigma = r.iloc[i - 10:i].std(ddof=1)
        assert z["sigma"].iloc[i] == pytest.approx(sigma)
        assert z["z"].iloc[i] == pytest.approx(r.iloc[i] / sigma)
    assert z["z"].iloc[:11].isna().all()
    # Rolling, not expanding: old returns leave the window.
    close2 = close.copy()
    close2.iloc[:5] = close2.iloc[:5] * np.array([1.5, 0.7, 1.4, 0.6, 1.3])
    z2 = shock_zscore(close2, window=10, min_frac=1.0)
    assert z2["z"].iloc[30] == pytest.approx(z["z"].iloc[30])


def test_shock_bar_is_not_in_its_own_scale_and_truncation_invariance():
    df = shock(wiggle_1h(), SHOCK_BAR)
    z = shock_zscore(df["close"])
    base = shock_zscore(wiggle_1h()["close"])
    assert z["sigma"].iloc[SHOCK_BAR] == pytest.approx(base["sigma"].iloc[SHOCK_BAR])
    assert z["z"].iloc[SHOCK_BAR] < -10
    btc = wiggle_1h(seed=5)
    d = btc_daily()
    full = shock_features(df, H1, btc, d)
    for k in (SHOCK_BAR, SHOCK_BAR + 1, SHOCK_BAR + 7):
        t = df.index[k - 1]
        d_tr = d[d.index + pd.Timedelta(days=1) <= t + pd.Timedelta(hours=1)]
        part = shock_features(df.iloc[:k], H1, btc.iloc[:k], d_tr)
        pd.testing.assert_series_equal(part.iloc[-1], full.iloc[k - 1], check_names=False)


# --------------------------------------------------------------------------- signal
def sig_row(**kw):
    base = dict(z=-3.5, btc_r=-0.001, btc_sigma=0.005, btc_d_close=110.0, btc_d_sma=100.0)
    base.update(kw)
    return pd.Series(base)


def test_long_signal_rules_and_btc_systemic_filter():
    assert long_signal(sig_row(), H1)
    assert long_signal(sig_row(z=-3.0), H1)                        # z <= -3 inclusive
    assert not long_signal(sig_row(z=-2.9), H1)
    assert not long_signal(sig_row(btc_r=-0.0101), H1)             # BTC fell > 2 sigma: systemic
    assert long_signal(sig_row(btc_r=-0.0099), H1)
    assert not long_signal(sig_row(btc_r=-0.01), H1)               # strict ">" -2 sigma
    assert not long_signal(sig_row(btc_d_close=99.0), H1)          # BTC below its SMA200
    assert not long_signal(sig_row(btc_r=np.nan), H1)
    assert not long_signal(sig_row(z=np.nan), H1)


# --------------------------------------------------------------------------- engine
def _run(strat, sol, btc, bd, market="spot", **kw):
    panel = {"SOLUSDT": sol, "BTCUSDT": btc}
    daily = {"SOLUSDT": to_daily(sol), "BTCUSDT": bd}
    return run_event_bt(strat, panel, market, ZERO, None, daily=daily, fixed_slip_bps=0.0,
                        start=sol.index[800], **kw)


@pytest.mark.parametrize("config,hold", [("H1", 4), ("H2", 12), ("H3", 24)])
def test_entry_next_open_stop_risk_and_time_exit(config, hold):
    sol = shock(wiggle_1h(), SHOCK_BAR)
    btc, bd = wiggle_1h(seed=5), btc_daily()
    strat = Shock(config)
    res = _run(strat, sol, btc, bd)
    rt = res.meta["round_trips"]
    assert len(rt) == 1
    tr = rt.iloc[0]
    assert tr["symbol"] == "SOLUSDT" and tr["side"] == 1
    assert tr["entry_time"] == sol.index[SHOCK_BAR + 1]
    assert tr["entry_price"] == pytest.approx(sol["open"].iloc[SHOCK_BAR + 1])
    assert tr["exit_reason"].endswith("time_exit")
    assert tr["exit_time"] == sol.index[SHOCK_BAR + 1 + hold]
    a = atr(sol).iloc[SHOCK_BAR]
    assert tr["qty"] == pytest.approx(0.0025 * 10_000.0 / (2.0 * a))
    trades = res.trades
    assert len(trades) == 2


def test_no_entry_when_btc_falls_with_the_coin_or_is_below_sma200():
    sol = shock(wiggle_1h(), SHOCK_BAR)
    btc = shock(wiggle_1h(seed=5), SHOCK_BAR, drop=0.05)
    res = _run(Shock("H1"), sol, btc, btc_daily())
    assert len(res.meta["round_trips"]) == 0
    res = _run(Shock("H1"), sol, wiggle_1h(seed=5), btc_daily(up=False))
    assert len(res.meta["round_trips"]) == 0


def test_stop_two_atr_below_and_prepared_equals_lazy():
    sol = shock(wiggle_1h(), SHOCK_BAR)
    # Keep falling after the entry: the 2 ATR stop fires before the time exit.
    sol.iloc[SHOCK_BAR + 2, :4] = [sol["open"].iloc[SHOCK_BAR + 2], sol["open"].iloc[SHOCK_BAR + 2],
                                   sol["open"].iloc[SHOCK_BAR + 2] - 20, sol["open"].iloc[SHOCK_BAR + 2] - 19]
    sol.iloc[SHOCK_BAR + 3:, :4] = sol.iloc[SHOCK_BAR + 3:, :4] - 19
    btc, bd = wiggle_1h(seed=5), btc_daily()
    panel = {"SOLUSDT": sol, "BTCUSDT": btc}
    daily = {"SOLUSDT": to_daily(sol), "BTCUSDT": bd}
    prepared = Shock("H3").prepare(panel, daily)
    res_p = _run(prepared, sol, btc, bd)
    res_l = _run(Shock("H3"), sol, btc, bd)
    pd.testing.assert_frame_equal(res_p.meta["round_trips"], res_l.meta["round_trips"])
    tr = res_p.meta["round_trips"].iloc[0]
    stop = sol["close"].iloc[SHOCK_BAR] - 2.0 * atr(sol).iloc[SHOCK_BAR]
    assert tr["exit_reason"] == "stop" and tr["exit_price"] == pytest.approx(stop)
    assert tr["exit_time"] == sol.index[SHOCK_BAR + 2]


def test_shock_needs_btc_data():
    sol = shock(wiggle_1h(), SHOCK_BAR)
    with pytest.raises(StrategyError):
        Shock("H1").prepare({"SOLUSDT": sol}, {"SOLUSDT": to_daily(sol)})


# --------------------------------------------------------------------------- tail report
def test_tail_event_report_selects_trades_exposed_on_the_day():
    ts = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    rt = pd.DataFrame({
        "symbol": ["A", "B", "C"],
        "entry_time": [ts("2022-11-08 22:00"), ts("2022-11-09 10:00"), ts("2022-11-12")],
        "exit_time": [ts("2022-11-09 02:00"), ts("2022-11-09 12:00"), ts("2022-11-12 04:00")],
        "pnl": [-30.0, 10.0, 5.0],
        "r_multiple": [-1.2, 0.4, 0.2],
        "exit_reason": ["stop_gap", "SHOCK-H1_time_exit", "x"],
    })
    rep = tail_event_report(rt, nav=10_000.0)
    assert list(rep.index) == list(TAIL_EVENTS)
    row = rep.loc["2022-11-09"]
    assert row["n_trades"] == 2 and row["pnl"] == pytest.approx(-20.0) and row["n_stops"] == 1
    assert row["worst_r"] == pytest.approx(-1.2) and row["pnl_pct"] == pytest.approx(-0.002)
    assert rep.loc["2021-05-19", "n_trades"] == 0 and rep.loc["2021-05-19", "pnl"] == 0.0


@pytest.mark.skipif(not (Path("/home/user/harness/data") / "futures" / "SOLUSDT_1h.csv").exists(),
                    reason="local data not available")
def test_real_futures_debug_window_signals_are_causal():
    from apps.research.data.loader import load_ohlcv

    syms = ["BTCUSDT", "SOLUSDT"]
    h1 = {s: load_ohlcv(s, "futures", "1h", "2020-10-01", "2021-12-31") for s in syms}
    d1 = {s: load_ohlcv(s, "futures", "1d", "2020-10-01", "2021-12-31") for s in syms}
    d1["BTCUSDT"] = load_ohlcv("BTCUSDT", "futures", "1d", "2020-09-01", "2021-12-31")
    strat = Shock("H2").prepare(h1, d1)
    f = strat.features("SOLUSDT")
    sig = f.apply(lambda r: long_signal(r, strat.params), axis=1)
    assert sig.any()
    for t in sig[sig].index[:3]:
        k = h1["SOLUSDT"].index.get_loc(t) + 1
        d_tr = {s: d[d.index + pd.Timedelta(days=1) <= t + pd.Timedelta(hours=1)] for s, d in d1.items()}
        part = shock_features(h1["SOLUSDT"].iloc[:k], strat.params, h1["BTCUSDT"].loc[:t], d_tr["BTCUSDT"])
        assert long_signal(part.iloc[-1], strat.params)
