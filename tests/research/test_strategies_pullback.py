"""Tests for apps.research.strategies.pullback (PLAN §2.8, §6.2 R12).

Small hand-built deterministic fixtures; the integration test reads the real
local data in the debug window (2020-09 .. 2021-12) and is skipped without it.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.strategies._intraday import StrategyError
from apps.research.strategies.pullback import (
    PULLBACK_CONFIGS,
    Pullback,
    increase_events,
    make_pullback,
    pullback_report,
    pullback_schedule,
    rsi,
    trigger_series,
)

DAYS = pd.date_range("2024-01-01", periods=30, freq="1D", tz="UTC")
DEC = 20                                    # decision day index
T = DAYS[DEC]
WIN0 = T + pd.Timedelta(days=1)             # first 1h bar of the window


def daily(close=100.0):
    """Flat daily bars with a constant 2-unit range: ATR14 = 2 exactly."""
    c = np.full(len(DAYS), close)
    d = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1e6}, index=DAYS)
    d["quote_volume"] = d["volume"] * d["close"]
    return d


def hourly(price=100.0):
    idx = pd.date_range(DAYS[0], DAYS[-1] + pd.Timedelta(hours=23), freq="1h", tz="UTC")
    p = np.full(len(idx), price)
    h = pd.DataFrame({"open": p, "high": p + 0.2, "low": p - 0.2, "close": p, "volume": 1e3}, index=idx)
    h["open"] = h["open"] + np.arange(len(idx)) * 1e-6      # distinct opens to identify the fill bar
    return h


def set_close(h, t, c):
    h.loc[t, "close"] = c
    h.loc[t, "low"] = min(h.loc[t, "low"], c)


def e_frame(values=None):
    e = pd.Series(0.0, index=DAYS)
    e.iloc[DEC:] = 0.5
    if values:
        for i, v in values.items():
            e.iloc[i] = v
    return pd.DataFrame({"SOLUSDT": e})


# --------------------------------------------------------------------------- configs / RSI
def test_configs_p1_to_p3():
    assert {k: v["rule"] for k, v in PULLBACK_CONFIGS.items()} == {"P1": "P1", "P2": "P2", "P3": "P3"}
    for c in PULLBACK_CONFIGS.values():
        assert c["rsi_n"] == 2 and c["rsi_max"] == 10 and c["atr_mult"] == 0.5 and c["max_wait"] == 24
    p = make_pullback("P2")
    assert p.name == "PULLBACK-P2" and p.n_free_params >= 1
    with pytest.raises(StrategyError):
        Pullback("P4")


def test_rsi2_matches_a_hand_computation():
    c = pd.Series([10.0, 11.0, 10.0, 12.0, 11.0, 11.0])
    r = rsi(c, 2)
    # diffs: +1, -1, +2, -1, 0 ; seeds (n=2): gain (1+0)/2=.5, loss (0+1)/2=.5
    g, l = 0.5, 0.5
    assert np.isnan(r.iloc[0]) and np.isnan(r.iloc[1])
    assert r.iloc[2] == pytest.approx(100 - 100 / (1 + g / l))
    g, l = g + (2 - g) / 2, l + (0 - l) / 2
    assert r.iloc[3] == pytest.approx(100 - 100 / (1 + g / l))
    g, l = g + (0 - g) / 2, l + (1 - l) / 2
    assert r.iloc[4] == pytest.approx(100 - 100 / (1 + g / l))
    assert rsi(pd.Series([1.0, 2.0, 3.0, 4.0]), 2).iloc[-1] == 100.0
    assert rsi(pd.Series([1.0, 1.0, 1.0, 1.0]), 2).iloc[-1] == 50.0


# --------------------------------------------------------------------------- events
def test_only_increases_are_deferred_and_nan_is_flat():
    e = pd.DataFrame({"A": [0.0, 0.25, 0.25, 0.5, 0.0, np.nan, 0.75]},
                     index=pd.date_range("2024-01-01", periods=7, freq="1D", tz="UTC"))
    ev = increase_events(e)
    assert list(ev["decision"].dt.day) == [2, 4, 7]
    assert list(ev["e_prev"]) == [0.0, 0.25, 0.0] and list(ev["e_new"]) == [0.25, 0.5, 0.75]


# --------------------------------------------------------------------------- schedule
def test_timeout_buys_at_the_open_of_bar_25():
    h = hourly()
    ev = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P3"])
    assert len(ev) == 1
    r = ev.iloc[0]
    assert r["status"] == "timeout" and r["decision"] == T
    assert r["base_time"] == WIN0 and r["base_price"] == 100.0
    assert r["fill_time"] == WIN0 + pd.Timedelta(hours=24) and r["wait_bars"] == 24
    assert r["fill_price"] == pytest.approx(h.loc[WIN0 + pd.Timedelta(hours=24), "open"])
    assert r["size"] == pytest.approx(0.5)


def test_p1_rsi_trigger_fills_at_the_next_bar_open():
    h = hourly()
    tj = WIN0 + pd.Timedelta(hours=5)
    set_close(h, tj, 99.5)                  # RSI2 -> 0 (< 10) but above C_1d - 0.5 ATR = 99
    ev = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P1"])
    r = ev.iloc[0]
    assert r["status"] == "triggered" and r["trigger"] == "P1" and r["trigger_time"] == tj
    assert r["fill_time"] == tj + pd.Timedelta(hours=1) and r["wait_bars"] == 6
    assert r["fill_price"] == pytest.approx(h.loc[tj + pd.Timedelta(hours=1), "open"])
    # P2 alone does not fire on that bar: 99.5 > 99.
    ev2 = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P2"])
    assert ev2.iloc[0]["status"] == "timeout"


def test_p2_atr_trigger_and_p3_either():
    h = hourly()
    d = daily()
    d.loc[T, "close"] = 110.0               # decision close 110, ATR14 = 2 -> level 109; 1h at 100
    for cfg in ("P2", "P3"):
        ev = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": d}, PULLBACK_CONFIGS[cfg])
        r = ev.iloc[0]
        assert r["status"] == "triggered" and r["trigger"] == "P2" and r["trigger_time"] == WIN0
        assert r["fill_time"] == WIN0 + pd.Timedelta(hours=1)
    ev1 = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": d}, PULLBACK_CONFIGS["P1"])
    assert ev1.iloc[0]["status"] == "timeout"


def test_the_window_has_24_bars_and_ignores_triggers_before_or_after_it():
    h = hourly()
    set_close(h, WIN0 - pd.Timedelta(hours=1), 90.0)     # before the decision is known
    set_close(h, WIN0 + pd.Timedelta(hours=24), 90.0)    # bar 25: outside the window
    ev = pullback_schedule(e_frame(), {"SOLUSDT": h}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P3"])
    assert ev.iloc[0]["status"] == "timeout"
    h2 = hourly()
    set_close(h2, WIN0 + pd.Timedelta(hours=23), 90.0)   # last bar of the window
    ev = pullback_schedule(e_frame(), {"SOLUSDT": h2}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P3"])
    r = ev.iloc[0]
    assert r["status"] == "triggered" and r["fill_time"] == WIN0 + pd.Timedelta(hours=24)


def test_trigger_does_not_use_later_bars():
    h = hourly()
    tj = WIN0 + pd.Timedelta(hours=3)
    set_close(h, tj, 99.5)
    params = PULLBACK_CONFIGS["P3"]
    full = trigger_series(h.loc[WIN0:WIN0 + pd.Timedelta(hours=23)], 100.0, 2.0, params, rsi(h["close"], 2))
    trunc = h.loc[:tj]
    part = trigger_series(trunc.loc[WIN0:], 100.0, 2.0, params, rsi(trunc["close"], 2))
    pd.testing.assert_series_equal(full.loc[:tj], part)
    assert part.loc[tj] and not part.loc[:tj].iloc[:-1].any()


def test_missing_intraday_data_falls_back_to_the_baseline():
    ev = pullback_schedule(e_frame(), {}, {"SOLUSDT": daily()}, PULLBACK_CONFIGS["P3"])
    r = ev.iloc[0]
    assert r["status"] == "no_intraday" and r["fill_time"] == r["base_time"] and r["fill_price"] == 100.0


def test_report_incremental_return_per_unit_of_turnover():
    ev = pd.DataFrame({
        "size": [0.5, 0.25, 0.25],
        "base_price": [100.0, 100.0, 50.0],
        "fill_price": [98.0, 101.0, 50.0],
        "status": ["triggered", "triggered", "timeout"],
        "wait_bars": [3, 10, 24],
    })
    rep = pullback_report(ev, fee=0.001)
    expected = (0.5 * 0.02 + 0.25 * -0.01 + 0.0) * 1.001 / 1.0
    assert rep["incremental_per_turnover"] == pytest.approx(expected)
    assert rep["n_events"] == 3 and rep["triggered"] == pytest.approx(2 / 3)
    assert rep["timeout"] == pytest.approx(1 / 3) and rep["mean_wait_h"] == pytest.approx(37 / 3)
    assert np.isnan(pullback_report(ev.iloc[:0])["incremental_per_turnover"])


def test_size_frame_overrides_the_e_increase():
    w = pd.DataFrame({"SOLUSDT": 0.0}, index=DAYS)
    w.iloc[DEC:] = 0.12
    ev = Pullback("P3").schedule(e_frame(), {"SOLUSDT": hourly()}, {"SOLUSDT": daily()}, size=w)
    assert ev.iloc[0]["size"] == pytest.approx(0.12)


@pytest.mark.skipif(not (Path("/home/user/harness/data") / "futures" / "ETHUSDT_1h.csv").exists(),
                    reason="local data not available")
def test_real_futures_debug_window_schedule():
    from apps.research.data.loader import load_ohlcv

    h1 = load_ohlcv("ETHUSDT", "futures", "1h", "2021-01-01", "2021-12-31")
    d1 = load_ohlcv("ETHUSDT", "futures", "1d", "2020-12-01", "2021-12-31")
    # Exposure steps chosen by hand (no strategy result is evaluated here).
    e = pd.Series(0.0, index=d1.index)
    e.loc["2021-03-01":] = 0.5
    e.loc["2021-06-01":] = 0.0
    e.loc["2021-09-01":] = 1.0
    ev = pullback_schedule(pd.DataFrame({"ETHUSDT": e}), {"ETHUSDT": h1}, {"ETHUSDT": d1},
                           PULLBACK_CONFIGS["P3"])
    assert len(ev) == 2
    assert (ev["fill_time"] > ev["base_time"]).all() and (ev["wait_bars"] <= 24).all()
    for r in ev.itertuples():
        assert r.fill_price == pytest.approx(h1.loc[r.fill_time, "open"])
