"""Tests for apps.research.engine.portfolio_bt (PLAN §6.2 R06).

Unit tests use small hand-built OHLC fixtures (allowed for formula checks);
the integration test reads the real local data and is skipped without it.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.portfolio_bt import (
    BTError,
    daily_inputs,
    resolve_slip,
    run_portfolio_bt,
    wilder_atr,
)
from apps.research.portfolio.risk import RiskConfig
from apps.research.portfolio.sizing import SizingConfig

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)
N = 40
START = 20  # first decision bar (index)


def make_bars(close, open_=None, high=None, low=None, start="2024-01-01", freq="1D", volume=1e9):
    close = np.asarray(close, dtype=float)
    open_ = np.r_[close[0], close[:-1]] if open_ is None else np.asarray(open_, dtype=float)
    high = np.maximum(open_, close) + 1.0 if high is None else np.asarray(high, dtype=float)
    low = np.minimum(open_, close) - 1.0 if low is None else np.asarray(low, dtype=float)
    idx = pd.date_range(start, periods=len(close), freq=freq, tz="UTC")
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": volume}, index=idx)
    df["quote_volume"] = df["volume"] * df["close"]
    return df


def trend_bars(n=N, base=100.0):
    """close_i = base + i, open_i = close_{i-1}: true range is 3 on every bar, so ATR14 = 3."""
    close = base + np.arange(n, dtype=float)
    return make_bars(close, open_=close - 1.0)


class Fixed:
    """Target-weight strategy returning a precomputed signal frame."""

    name = "fixed"
    params: dict = {}
    n_free_params = 0

    def __init__(self, signal: dict[str, list] | pd.DataFrame):
        self._signal = signal

    def signal(self, panel, ctx):
        if isinstance(self._signal, pd.DataFrame):
            return self._signal
        idx = next(iter(panel.values())).index
        return pd.DataFrame({s: v for s, v in self._signal.items()}, index=idx)


def ones(n=N, start=START, stop=None, value=1.0):
    e = np.zeros(n)
    e[start:stop] = value
    return e


def flat_funding(idx, rate=1e-4):
    times = pd.date_range(idx[0], idx[-1] + pd.Timedelta(hours=16), freq="8h", tz="UTC")
    return pd.Series(rate, index=times, name="funding_rate")


def run(panel, signal, market="spot", cost=ZERO, sizing=None, risk=None, **kw):
    kw.setdefault("catastrophe_atr_mult", None)
    kw.setdefault("fixed_slip_bps", 0.0)
    first = next(iter(panel.values())).index
    return run_portfolio_bt(Fixed(signal), panel, market, cost, sizing, risk,
                            start=kw.pop("start", first[START]), end=kw.pop("end", None), **kw)


# --------------------------------------------------------------------------- inputs
def test_wilder_atr_hand_computed():
    df = trend_bars()
    atr = wilder_atr(df)
    assert atr.iloc[:13].isna().all()
    assert atr.iloc[13:].to_numpy() == pytest.approx(3.0)
    # One wide bar moves ATR by (TR - ATR)/14.
    df2 = df.copy()
    df2.iloc[20, df2.columns.get_loc("high")] += 14.0
    assert wilder_atr(df2).iloc[20] == pytest.approx(3.0 + 14.0 / 14)


def test_daily_inputs_are_causal():
    df = trend_bars(60)
    full = daily_inputs(df)
    cut = daily_inputs(df.iloc[:45])
    pd.testing.assert_frame_equal(full.iloc[:45], cut)


# --------------------------------------------------------------------------- B&H
def test_e1_spot_equals_buy_and_hold_minus_costs():
    df = make_bars(100.0 * np.exp(0.03 * np.sin(np.arange(N) * 0.9) + 0.004 * np.arange(N)))
    cost = CostModel()  # spot 0.10 % per side
    slip = 5.0
    res = run({"BTCUSDT": df}, {"BTCUSDT": np.ones(N)}, cost=cost, fixed_slip_bps=slip)

    entry = df["open"].iloc[START + 1] * (1 + slip / 1e4)
    qty = 10_000.0 / (entry * (1 + cost.spot_fee))
    expected = pd.Series(qty * df["close"].iloc[START + 1:].to_numpy(), index=df.index[START + 1:])
    assert res.equity.iloc[0] == pytest.approx(10_000.0)          # decision bar: still cash
    np.testing.assert_allclose(res.equity.iloc[1:].to_numpy(), expected.to_numpy(), rtol=1e-12)
    assert len(res.trades) == 1                                    # bought once, never rebalanced
    tot = res.cost_totals()
    assert tot["commission"] == pytest.approx(qty * entry * cost.spot_fee)
    assert tot["slippage"] == pytest.approx(qty * (entry - df["open"].iloc[START + 1]))
    assert tot["funding"] == 0.0
    # Without costs the equity is exactly the price path.
    free = run({"BTCUSDT": df}, {"BTCUSDT": np.ones(N)})
    bh = 10_000.0 * df["close"].iloc[START + 1:] / df["open"].iloc[START + 1]
    np.testing.assert_allclose(free.equity.iloc[1:].to_numpy(), bh.to_numpy(), rtol=1e-12)
    np.testing.assert_allclose(free.weights.iloc[1:]["BTCUSDT"].to_numpy(), 1.0, rtol=1e-12)


# --------------------------------------------------------------------------- accounting
def test_accounting_equity_is_pnl_minus_costs():
    a = make_bars(100.0 * np.exp(0.02 * np.sin(np.arange(N) * 0.7) + 0.002 * np.arange(N)))
    b = make_bars(50.0 * np.exp(0.04 * np.cos(np.arange(N) * 0.5)))
    sig = {"BTCUSDT": np.r_[np.zeros(START), [0.3, 0.3, 0.2, 0.2, 0.0, 0.0, 0.3] * 3][:N],
           "SOLUSDT": np.r_[np.zeros(START), [-0.2, -0.2, -0.1, 0.0, 0.2, 0.2, 0.2] * 3][:N]}
    panel = {"BTCUSDT": a, "SOLUSDT": b}
    fund = {s: flat_funding(a.index, 2e-4) for s in panel}
    res = run(panel, sig, market="futures", cost=CostModel(), fixed_slip_bps=3.0, funding=fund)

    tr = res.trades
    tot = res.cost_totals()
    final_qty = tr.groupby("symbol")["qty"].sum()
    mtm = sum(final_qty.get(s, 0.0) * panel[s]["close"].iloc[-1] for s in panel)
    price_pnl = -(tr["qty"] * tr["ref_price"]).sum() + mtm
    expected = 10_000.0 + price_pnl - tot["commission"] - tot["slippage"] + tot["funding"]
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-12)
    assert tot["commission"] == pytest.approx(tr["commission"].sum())
    assert tot["slippage"] == pytest.approx(tr["slippage"].sum())
    assert tot["funding"] < 0  # net long most of the time with positive funding
    np.testing.assert_allclose(tr["commission"], (tr["qty"] * tr["price"]).abs() * 0.0005, rtol=1e-12)
    # Daily returns chain back to the equity curve.
    assert (1 + res.returns).prod() * 10_000.0 == pytest.approx(res.equity.iloc[-1])


def test_delay_bars_shift_fills_by_one_more_bar():
    df = trend_bars()
    sig = {"BTCUSDT": ones(stop=30)}
    base = run({"BTCUSDT": df}, sig)
    late = run({"BTCUSDT": df}, sig, delay_bars=2)
    w1, w2 = base.weights["BTCUSDT"], late.weights["BTCUSDT"]
    assert w1.ne(0).idxmax() == df.index[START + 1]
    assert w2.ne(0).idxmax() == df.index[START + 2]
    assert base.trades["time"].tolist() == [df.index[START + 1], df.index[31]]
    assert late.trades["time"].tolist() == [df.index[START + 2], df.index[32]]
    with pytest.raises(BTError):
        run({"BTCUSDT": df}, sig, delay_bars=0)


def test_signal_at_t_does_not_change_the_past():
    df = trend_bars()
    e = ones()
    res1 = run({"BTCUSDT": df}, {"BTCUSDT": e})
    e2 = e.copy()
    e2[30:] = 0.0
    res2 = run({"BTCUSDT": df}, {"BTCUSDT": e2})
    pd.testing.assert_series_equal(res1.equity.loc[: df.index[30]], res2.equity.loc[: df.index[30]])


# --------------------------------------------------------------------------- funding
def test_funding_only_in_perps_and_uses_tau_minus_position():
    df = make_bars(np.full(N, 100.0), high=np.full(N, 100.0), low=np.full(N, 100.0))
    sig = {"BTCUSDT": ones(stop=26)}           # held during bars 21..26, exit at open[27]
    fund = {"BTCUSDT": flat_funding(df.index, 1e-4)}
    spot = run({"BTCUSDT": df}, sig, funding=fund)
    assert spot.cost_totals()["funding"] == 0.0

    perp = run({"BTCUSDT": df}, sig, market="futures", funding=fund)
    # 100 units * 100 = 10k notional; 6 bars * (08h, 16h) + 00h of bars 22..27 = 18
    # settlements; the 00h settlement of the entry bar 21 is paid by the flat
    # position held before the rebalance.
    assert perp.cost_totals()["funding"] == pytest.approx(-18 * 10_000.0 * 1e-4)
    by_day = perp.costs["funding"].groupby(level=0).sum()
    assert by_day.loc[df.index[START + 1]] == pytest.approx(-2.0)
    assert by_day.loc[df.index[27]] == pytest.approx(-1.0)        # 00h with the tau- long
    assert perp.equity.iloc[-1] == pytest.approx(10_000.0 - 18.0)

    short = run({"BTCUSDT": df}, {"BTCUSDT": ones(stop=26, value=-0.5)}, market="futures", funding=fund)
    assert short.cost_totals()["funding"] == pytest.approx(+18 * 5_000.0 * 1e-4)  # shorts receive


def test_funding_missing_raises_and_bnb_never_traded_as_perp():
    df = trend_bars()
    sig = {"BTCUSDT": ones(), "BNBUSDT": ones()}
    with pytest.raises(BTError, match="funding"):
        run({"BTCUSDT": df, "BNBUSDT": df}, sig, market="futures")
    fund = {"BTCUSDT": flat_funding(df.index)}
    res = run({"BTCUSDT": df, "BNBUSDT": df}, {"BTCUSDT": ones(value=0.5), "BNBUSDT": ones(value=0.5)},
              market="futures", funding=fund)
    assert (res.weights["BNBUSDT"] == 0).all()
    assert (res.weights["BTCUSDT"].iloc[1:] > 0).all()
    holed = fund["BTCUSDT"].copy()
    holed.iloc[70] = np.nan
    with pytest.raises(BTError, match="missing funding"):
        run({"BTCUSDT": df}, {"BTCUSDT": ones()}, market="futures", funding={"BTCUSDT": holed})


# --------------------------------------------------------------------------- stops
@pytest.mark.parametrize("mode,gap", [("gap_aware", False), ("worst_bar", False), ("gap_aware", True)])
def test_catastrophe_stop_3atr(mode, gap):
    df = trend_bars()
    # Stop placed at entry: C20 - 3*ATR = 120 - 9 = 111, ratcheted +1 per close: 115 after C24.
    crash = 25
    o = 110.0 if gap else 124.0
    df.iloc[crash, :4] = [o, o + 1.0, 100.0, 105.0]
    slip = 4.0
    res = run({"BTCUSDT": df}, {"BTCUSDT": np.ones(N)}, catastrophe_atr_mult=3.0, stop_fill=mode,
              fixed_slip_bps=slip)
    exit_ = res.trades.iloc[1]
    assert exit_["time"] == df.index[crash] and exit_["qty"] < 0
    raw = {"gap_aware": 110.0 if gap else 115.0, "worst_bar": 100.0}[mode]
    assert exit_["ref_price"] == pytest.approx(raw)
    assert exit_["price"] == pytest.approx(raw * (1 - 2 * slip / 1e4))   # stops pay double slippage
    assert exit_["reason"] == ("stop_gap" if gap else "stop")
    # Locked: the signal stays at 1, so the engine does not buy the same move back.
    assert (res.weights["BTCUSDT"].loc[df.index[crash]:] == 0).all()
    assert res.meta["counters"]["stops"] == 1


def test_stop_lock_released_when_signal_resets():
    df = trend_bars()
    df.iloc[25, :4] = [124.0, 125.0, 100.0, 105.0]
    e = np.ones(N)
    e[28] = 0.0
    res = run({"BTCUSDT": df}, {"BTCUSDT": e}, catastrophe_atr_mult=3.0)
    times = res.trades["time"].tolist()
    assert times == [df.index[21], df.index[25], df.index[30]]


# --------------------------------------------------------------------------- risk layer
def test_kill_switch_halt_closes_and_stays_flat():
    close = 100.0 + np.arange(N, dtype=float)
    df = make_bars(close)
    df.iloc[25, :4] = [124.0, 124.0, 70.0, 75.0]       # -40 %: drawdown above 20 %
    df.iloc[26:, :4] = df.iloc[26:, :4] - 50.0
    res = run({"BTCUSDT": df}, {"BTCUSDT": np.ones(N)}, risk=RiskConfig())
    ks = res.meta["kill_switch"]
    assert ks.loc[df.index[25], "level"] == "halted"
    assert res.trades.iloc[-1]["time"] == df.index[26]                  # closed at the next open
    assert (res.weights["BTCUSDT"].loc[df.index[26]:] == 0).all()


def test_sizing_mode_respects_layer_d_caps():
    n = 160
    i = np.arange(n)
    panel = {
        "BTCUSDT": make_bars(100 * np.exp(0.03 * np.sin(i * 0.7) + 0.002 * i)),
        "ETHUSDT": make_bars(50 * np.exp(0.04 * np.sin(i * 0.5 + 1) + 0.002 * i)),
        "SOLUSDT": make_bars(20 * np.exp(0.06 * np.cos(i * 0.3) + 0.003 * i)),
    }
    sig = {s: np.r_[np.zeros(100), np.ones(n - 100)] for s in panel}
    res = run_portfolio_bt(Fixed(sig), panel, "spot", CostModel(), SizingConfig(), RiskConfig(),
                           start=panel["BTCUSDT"].index[95], fixed_slip_bps=2.0, catastrophe_atr_mult=None)
    w = res.weights
    assert (w > 0).any().all()
    tol = 0.03  # drift between rebalances inside the no-trade band
    assert (w["BTCUSDT"] <= 0.35 + tol).all() and (w["SOLUSDT"] <= 0.20 + tol).all()
    assert (w.sum(axis=1) <= 1.0 + tol).all()
    first_fill = res.trades.groupby("symbol")["time"].min()
    assert (first_fill == panel["BTCUSDT"].index[101]).all()


def test_input_validation():
    df = trend_bars()
    with pytest.raises(BTError, match="spot"):
        run({"BTCUSDT": df}, {"BTCUSDT": -np.ones(N)})
    with pytest.raises(BTError, match=r"\[-1, 1\]"):
        run({"BTCUSDT": df}, {"BTCUSDT": 2 * np.ones(N)})
    with pytest.raises(BTError, match="leverage"):
        run({"BTCUSDT": df}, {"BTCUSDT": np.ones(N)}, market="futures",
            funding={"BTCUSDT": flat_funding(df.index)}, risk=RiskConfig(), leverage={"BTCUSDT": 2.0})
    nan_df = df.copy()
    nan_df.iloc[30, :4] = np.nan
    with pytest.raises(BTError, match="missing"):
        run({"BTCUSDT": nan_df}, {"BTCUSDT": np.ones(N)})


# --------------------------------------------------------------------------- real data
DATA = Path("/home/user/harness/data")


@pytest.mark.skipif(not (DATA / "spot" / "BTCUSDT_1d.csv").exists(), reason="local data not available")
def test_real_btc_spot_e1_equals_buy_and_hold_minus_costs():
    from apps.research.data.loader import load_ohlcv

    # Debug window (PLAN §5.3): free to use for code checks.
    df = load_ohlcv("BTCUSDT", "spot", "1d", "2020-06-01", "2021-12-31")
    cost = CostModel()
    t0 = pd.Timestamp("2020-10-01", tz="UTC")
    res = run_portfolio_bt(Fixed({"BTCUSDT": np.ones(len(df))}), {"BTCUSDT": df}, "spot", cost, None, None,
                           start=t0, catastrophe_atr_mult=None)
    fill_day = df.index[df.index.get_loc(t0) + 1]
    slip = resolve_slip("BTCUSDT", fill_day, daily_inputs(df).loc[t0].to_dict(), cost, None)
    assert 2.0 <= slip < 10.0                                   # tier A, widened by ATR ratio
    entry = df.loc[fill_day, "open"] * (1 + slip / 1e4)
    qty = 10_000.0 / (entry * (1 + cost.spot_fee))
    assert res.equity.iloc[-1] == pytest.approx(qty * df["close"].iloc[-1], rel=1e-12)
    assert len(res.trades) == 1
    assert res.meta["data"]["BTCUSDT"]["sha256"]
    assert math.isfinite(res.returns.std())
