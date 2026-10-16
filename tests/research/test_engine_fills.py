"""Tests for apps.research.engine.fills (PLAN §6.2 R02)."""
import pandas as pd
import pytest

from apps.research.engine.fills import (
    STOP_SLIP_MULT,
    FillError,
    held_weights,
    next_open_fill,
    ratchet_stop,
    stop_fill,
)


@pytest.fixture
def bars():
    idx = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 104.0, 98.0, 101.0],
            "high": [105.0, 106.0, 99.0, 103.0],
            "low": [99.0, 101.0, 90.0, 97.0],
            "close": [104.0, 102.0, 95.0, 100.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        },
        index=idx,
    )


# --------------------------------------------------------------------------- open t+1
def test_fill_at_next_open_not_signal_close(bars):
    t = bars.index[0]
    fill_time, price = next_open_fill(bars, t, side=+1)
    assert fill_time == bars.index[1]
    assert price == 104.0          # open[t+1], not close[t] (also 104 by construction)
    _, price2 = next_open_fill(bars, bars.index[1], side=+1)
    assert price2 == 98.0 != bars["close"].iloc[1]


def test_fill_slippage_and_delay(bars):
    _, buy = next_open_fill(bars, bars.index[0], side=+1, slip_bps=10)
    _, sell = next_open_fill(bars, bars.index[0], side=-1, slip_bps=10)
    assert buy == pytest.approx(104.0 * 1.001)
    assert sell == pytest.approx(104.0 * 0.999)
    t2, p2 = next_open_fill(bars, bars.index[0], side=+1, delay_bars=2)
    assert t2 == bars.index[2] and p2 == 98.0


def test_fill_errors(bars):
    with pytest.raises(FillError):
        next_open_fill(bars, bars.index[-1], side=+1)        # no t+1 bar
    with pytest.raises(FillError):
        next_open_fill(bars, bars.index[0], side=+1, delay_bars=0)
    nan_bars = bars.copy()
    nan_bars.loc[nan_bars.index[1], "open"] = float("nan")
    with pytest.raises(FillError, match="missing open"):
        next_open_fill(nan_bars, bars.index[0], side=+1)


def test_held_weights_shift_by_delay():
    idx = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")
    target = pd.DataFrame({"BTCUSDT": [1.0, 0.5, 0.0, 0.25]}, index=idx)
    held = held_weights(target)
    assert held["BTCUSDT"].tolist() == [0.0, 1.0, 0.5, 0.0]
    held2 = held_weights(target, delay_bars=2)
    assert held2["BTCUSDT"].tolist() == [0.0, 0.0, 1.0, 0.5]


# --------------------------------------------------------------------------- stops
def test_long_stop_not_triggered():
    assert not stop_fill(100, 105, 96, 95, side=+1).triggered


def test_long_stop_intrabar_gap_aware_vs_worst_bar():
    gap = stop_fill(100, 105, 90, 95, side=+1, mode="gap_aware")
    worst = stop_fill(100, 105, 90, 95, side=+1, mode="worst_bar")
    assert gap.triggered and not gap.gapped
    assert gap.price == pytest.approx(95.0)
    assert worst.price == pytest.approx(90.0)
    assert worst.price < gap.price


def test_long_stop_gap_through_fills_at_open():
    res = stop_fill(92, 94, 88, 95, side=+1, mode="gap_aware")
    assert res.triggered and res.gapped
    assert res.price == pytest.approx(92.0)            # min(stop, open)
    assert stop_fill(92, 94, 88, 95, side=+1, mode="worst_bar").price == pytest.approx(88.0)


def test_short_stop_gap_aware_vs_worst_bar():
    gap = stop_fill(108, 112, 104, 105, side=-1, mode="gap_aware")
    assert gap.triggered and gap.gapped and gap.price == pytest.approx(108.0)  # max(stop, open)
    intrabar = stop_fill(100, 112, 98, 105, side=-1, mode="gap_aware")
    assert intrabar.price == pytest.approx(105.0)
    worst = stop_fill(100, 112, 98, 105, side=-1, mode="worst_bar")
    assert worst.price == pytest.approx(112.0)
    assert not stop_fill(100, 104, 98, 105, side=-1).triggered


def test_stop_pays_double_slippage():
    res = stop_fill(100, 105, 90, 95, side=+1, slip_bps=10)
    assert res.price == pytest.approx(95.0 * (1 - STOP_SLIP_MULT * 10 / 1e4))
    res_s = stop_fill(100, 112, 98, 105, side=-1, slip_bps=10)
    assert res_s.price == pytest.approx(105.0 * (1 + STOP_SLIP_MULT * 10 / 1e4))


def test_stop_invalid_inputs():
    with pytest.raises(FillError):
        stop_fill(100, 105, 90, 95, side=0)
    with pytest.raises(FillError):
        stop_fill(100, 105, 90, 95, side=1, mode="close")
    with pytest.raises(FillError):
        stop_fill(float("nan"), 105, 90, 95, side=1)


# --------------------------------------------------------------------------- catastrophe stop
def test_ratchet_stop_only_moves_in_favour():
    s0 = ratchet_stop(None, close=100, atr=5, side=+1)
    assert s0 == 85.0
    s1 = ratchet_stop(s0, close=110, atr=5, side=+1)
    assert s1 == 95.0
    s2 = ratchet_stop(s1, close=97, atr=5, side=+1)   # price falls: stop stays
    assert s2 == 95.0
    sh = ratchet_stop(None, close=100, atr=5, side=-1)
    assert sh == 115.0
    assert ratchet_stop(sh, close=105, atr=5, side=-1) == 115.0
    assert ratchet_stop(sh, close=90, atr=5, side=-1) == 105.0
