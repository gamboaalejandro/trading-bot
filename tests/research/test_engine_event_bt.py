"""Tests for apps.research.engine.event_bt (PLAN §6.2 R07).

Small hand-built 4h fixtures; the integration test reads the real local data
(debug window) and is skipped without it.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.event_bt import merge_daily_asof, run_event_bt
from apps.research.engine.portfolio_bt import BTError
from apps.research.portfolio.risk import RiskConfig
from apps.research.strategies.base import OrderIntent, OrderIntentError

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)
NB = 6 * 12  # 12 days of 4h bars


def bars_4h(n=NB, price=100.0, start="2024-01-01"):
    idx = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    p = np.full(n, price)
    return pd.DataFrame({"open": p, "high": p + 1.0, "low": p - 1.0, "close": p, "volume": 1e6}, index=idx)


def to_daily(df):
    d = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    d["quote_volume"] = d["volume"] * d["close"]
    return d


def set_bar(df, i, o, h, l, c):
    df.iloc[i, :4] = [o, h, l, c]


class Script:
    """Event strategy that emits pre-scripted intents and records what it sees."""

    name = "script"
    params: dict = {}
    n_free_params = 0

    def __init__(self, plan: dict):
        self.plan = plan
        self.seen = []

    def on_bar(self, t, bars, ctx):
        self.seen.append((t, {s: b.copy() for s, b in bars.items()}, dict(ctx.positions),
                          {s: len(ctx.history(s)) for s in bars}))
        return list(self.plan.get(t, []))


def run(df, plan, market="spot", cost=ZERO, risk=None, symbol="SOLUSDT", **kw):
    strat = Script({df.index[i]: v for i, v in plan.items()})
    kw.setdefault("fixed_slip_bps", 0.0)
    res = run_event_bt(strat, {symbol: df}, market, cost, risk, daily={symbol: to_daily(df)}, **kw)
    return res, strat


# --------------------------------------------------------------------------- daily merge
def test_merge_asof_uses_only_the_closed_daily_bar():
    df = bars_4h(18)
    daily = to_daily(df)
    daily["close"] = [1.0, 2.0, 3.0]
    m = merge_daily_asof(df, daily, "4h")
    d0, d1 = daily.index[0], daily.index[1]
    # Bars 00:00-16:00 of day 0 close before 24:00: no closed day yet.
    assert m["d_close"].iloc[:5].isna().all()
    # The 20:00 bar closes at 24:00, exactly when day 0 closes.
    assert m["d_date"].iloc[5] == d0 and m["d_close"].iloc[5] == 1.0
    assert (m["d_date"].iloc[6:11] == d0).all()
    assert m["d_date"].iloc[11] == d1 and m["d_close"].iloc[11] == 2.0
    pd.testing.assert_frame_equal(m[df.columns], df)
    # 1h bars: only the 23:00 bar of a day sees that day.
    h1 = pd.DataFrame({"close": 1.0}, index=pd.date_range("2024-01-02", periods=24, freq="1h", tz="UTC"))
    m1 = merge_daily_asof(h1, daily, "1h")
    assert (m1["d_date"].iloc[:23] == d0).all() and m1["d_date"].iloc[23] == d1


def test_strategy_bars_carry_the_closed_daily_context():
    df = bars_4h()
    res, strat = run(df, {})
    for t, bars, _, n_hist in strat.seen:
        b = bars["SOLUSDT"]
        expected = (t + pd.Timedelta(hours=4)).floor("D") - pd.Timedelta(days=1)
        if expected < df.index[0]:
            assert pd.isna(b["d_date"])
        else:
            assert b["d_date"] == expected
        assert n_hist["SOLUSDT"] == df.index.get_loc(t) + 1    # history truncated at t


# --------------------------------------------------------------------------- stops / TP
def test_stop_wins_when_stop_and_take_profit_hit_in_same_bar():
    df = bars_4h()
    set_bar(df, 12, 100.0, 120.0, 80.0, 100.0)      # both 90 (stop) and 110 (TP) inside the bar
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=90.0, take_profit=110.0)]})
    rt = res.meta["round_trips"]
    assert len(rt) == 1
    assert rt["exit_reason"].iloc[0] == "stop" and rt["exit_price"].iloc[0] == pytest.approx(90.0)
    assert rt["exit_time"].iloc[0] == df.index[12]
    assert res.meta["counters"]["stop_and_tp_same_bar"] == 1


def test_take_profit_alone_fills_at_its_level():
    df = bars_4h()
    set_bar(df, 12, 100.0, 120.0, 99.0, 115.0)
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=90.0, take_profit=110.0)]})
    rt = res.meta["round_trips"].iloc[0]
    assert rt["exit_reason"] == "take_profit" and rt["exit_price"] == pytest.approx(110.0)
    assert rt["pnl"] == pytest.approx(rt["qty"] * 10.0)


@pytest.mark.parametrize("mode,expected", [("gap_aware", 85.0), ("worst_bar", 80.0)])
def test_stop_gap_aware_and_worst_bar(mode, expected):
    df = bars_4h()
    set_bar(df, 12, 85.0, 86.0, 80.0, 84.0)          # opens through the 90 stop
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=90.0)]},
                 stop_fill=mode, fixed_slip_bps=5.0)
    rt = res.meta["round_trips"].iloc[0]
    assert rt["exit_price"] == pytest.approx(expected * (1 - 2 * 5.0 / 1e4))


def test_trailing_stop_only_moves_in_favour():
    df = bars_4h()
    sell = lambda stop: OrderIntent("SOLUSDT", "SELL", reduce_only=True, stop_price=stop, tag="trail")  # noqa: E731
    plan = {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=90.0)],
            12: [sell(95.0)],     # tighter: applied
            14: [sell(92.0)],     # looser: ignored
            16: [sell(97.0)]}
    set_bar(df, 20, 100.0, 100.5, 96.0, 99.0)        # touches 96: stops at 97, not at 92/95
    res, strat = run(df, plan)
    stops = {t: pos["SOLUSDT"].stop for t, _, pos, _ in strat.seen if "SOLUSDT" in pos}
    assert stops[df.index[12]] == 90.0
    assert stops[df.index[13]] == 95.0
    assert stops[df.index[15]] == 95.0              # 92 was refused
    assert stops[df.index[17]] == 97.0
    assert res.meta["counters"]["stop_loosen_ignored"] == 1
    rt = res.meta["round_trips"].iloc[0]
    assert rt["exit_time"] == df.index[20] and rt["exit_price"] == pytest.approx(97.0)


def test_short_trailing_only_down_and_futures_short_pays_negative_funding():
    df = bars_4h()
    funding = pd.Series(-1e-4, index=pd.date_range(df.index[0], df.index[-1], freq="8h", tz="UTC"))
    plan = {10: [OrderIntent("SOLUSDT", "SELL", target_weight=0.1, stop_price=110.0)],
            12: [OrderIntent("SOLUSDT", "BUY", reduce_only=True, stop_price=115.0)],   # looser for a short
            14: [OrderIntent("SOLUSDT", "BUY", reduce_only=True)]}                     # market exit at 15
    res, strat = run(df, plan, market="futures", funding={"SOLUSDT": funding}, risk=RiskConfig())
    assert res.meta["counters"]["stop_loosen_ignored"] == 1
    rt = res.meta["round_trips"].iloc[0]
    assert rt["side"] == -1 and rt["exit_time"] == df.index[15]
    # Filled at open[11], closed at open[15]: the settlement at open[11] belongs to the
    # flat position (tau-), the one at open[15] (if any) to the short. With F < 0 shorts pay.
    held = [t for t in funding.index if df.index[11] < t <= df.index[15]]
    assert len(held) == 2
    assert res.cost_totals()["funding"] == pytest.approx(-len(held) * rt["qty"] * 100.0 * 1e-4)


# --------------------------------------------------------------------------- sizing
def test_risk_based_sizing_and_caps():
    df = bars_4h()
    # Alt: R = 0.25 % of NAV / (100 - 90) = 2.5 units.
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", stop_price=90.0)]})
    assert res.trades["qty"].iloc[0] == pytest.approx(0.0025 * 10_000 / 10.0)
    # Major: R = 0.5 % -> 5 units.
    res, _ = run(df, {10: [OrderIntent("BTCUSDT", "BUY", stop_price=90.0)]}, symbol="BTCUSDT")
    assert res.trades["qty"].iloc[0] == pytest.approx(0.005 * 10_000 / 10.0)
    # A very tight stop is capped at 35 % of NAV for BTC (per-coin cap of PLAN §2.0).
    res, _ = run(df, {10: [OrderIntent("BTCUSDT", "BUY", stop_price=99.9)]}, symbol="BTCUSDT")
    assert res.trades["qty"].iloc[0] * 100.0 == pytest.approx(3_500.0)
    # ... and at 20 % for an altcoin.
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", stop_price=99.9)]})
    assert res.trades["qty"].iloc[0] * 100.0 == pytest.approx(2_000.0)


def test_entry_rules():
    df = bars_4h()
    set_bar(df, 11, 89.0, 92.0, 88.0, 91.0)          # opens below the stop: entry rejected
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", stop_price=90.0)]})
    assert res.trades.empty and res.meta["counters"]["rejected_gap"] == 1
    # No pyramiding: a second entry in the same direction is ignored.
    df = bars_4h()
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", stop_price=90.0)],
                      12: [OrderIntent("SOLUSDT", "BUY", stop_price=95.0)]})
    assert len(res.trades) == 1 and res.meta["counters"]["ignored_entries"] == 1
    with pytest.raises(BTError, match="stop"):
        run(df, {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1)]})
    with pytest.raises(BTError, match="spot"):
        run(df, {10: [OrderIntent("SOLUSDT", "SELL", target_weight=0.1, stop_price=110.0)]})
    with pytest.raises(OrderIntentError):
        OrderIntent("SOLUSDT", "BUY", qty=1.0, target_weight=0.1)


def test_fill_at_next_open_and_accounting():
    df = bars_4h()
    set_bar(df, 11, 101.0, 102.0, 100.0, 101.5)
    set_bar(df, 30, 104.0, 105.0, 103.0, 104.0)
    df.iloc[31:, :4] = df.iloc[31:, :4] + 4.0
    cost = CostModel()
    res, _ = run(df, {10: [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=90.0)],
                      29: [OrderIntent("SOLUSDT", "SELL", reduce_only=True)]}, cost=cost, fixed_slip_bps=10.0)
    tr = res.trades
    assert tr["time"].tolist() == [df.index[11], df.index[30]]
    assert tr["ref_price"].tolist() == [101.0, 104.0]                    # open[t+1], not close[t]
    assert tr["price"].iloc[0] == pytest.approx(101.0 * 1.001)
    tot = res.cost_totals()
    pnl = -(tr["qty"] * tr["ref_price"]).sum()
    assert res.equity.iloc[-1] == pytest.approx(10_000 + pnl - tot["commission"] - tot["slippage"])
    assert (1 + res.returns).prod() * 10_000 == pytest.approx(res.equity.iloc[-1])


def test_kill_switch_blocks_entries_after_daily_loss():
    df = bars_4h()
    # Big long loses > 2 % of NAV on day 2 (bars 12-17) via a risk-sized position with a far stop.
    plan = {6: [OrderIntent("SOLUSDT", "BUY", qty=19.0, stop_price=50.0)]}
    df.iloc[12:, :4] = df.iloc[12:, :4] - 15.0       # -15 % on a 19 % position: about -2.9 % NAV
    plan[20] = [OrderIntent("SOLUSDT", "SELL", reduce_only=True)]
    plan[22] = [OrderIntent("SOLUSDT", "BUY", target_weight=0.1, stop_price=50.0)]   # day 3: blocked
    res, _ = run(df, plan, risk=RiskConfig())
    levels = res.meta["kill_switch"]["level"]
    assert levels.iloc[1] == "normal" and levels.iloc[2] == "block_entries"   # day 2 close
    assert res.meta["counters"]["blocked_entries"] == 1
    assert len(res.meta["round_trips"]) == 1


# --------------------------------------------------------------------------- real data
DATA = Path("/home/user/harness/data")


@pytest.mark.skipif(not (DATA / "futures" / "BTCUSDT_4h.csv").exists(), reason="local data not available")
def test_real_btc_futures_4h_runs_with_costs_and_funding():
    from apps.research.data.loader import load_funding, load_ohlcv

    # Debug window only (PLAN §5.3).
    h4 = load_ohlcv("BTCUSDT", "futures", "4h", "2020-09-01", "2021-03-31")
    d1 = load_ohlcv("BTCUSDT", "futures", "1d", "2020-09-01", "2021-03-31")
    entries = {h4.index[i]: [OrderIntent("BTCUSDT", "BUY", target_weight=0.2,
                                         stop_price=float(h4["close"].iloc[i]) * 0.9)]
               for i in range(400, 1000, 60)}
    exits = {h4.index[i + 30]: [OrderIntent("BTCUSDT", "SELL", reduce_only=True)] for i in range(400, 1000, 60)}
    plan = {**entries, **exits}
    res = run_event_bt(Script(plan), {"BTCUSDT": h4}, "futures", CostModel(), RiskConfig(),
                       start=h4.index[300], daily={"BTCUSDT": d1}, funding={"BTCUSDT": load_funding("BTCUSDT")})
    tot = res.cost_totals()
    assert tot["commission"] > 0 and tot["slippage"] > 0 and tot["funding"] != 0
    assert res.meta["counters"]["entries"] >= 5
    assert res.meta["funding_verified"] is False
    tr = res.trades
    final_qty = tr["qty"].sum()
    mtm = final_qty * h4["close"].iloc[-1]
    expected = 10_000 - (tr["qty"] * tr["ref_price"]).sum() + mtm - tot["commission"] - tot["slippage"] \
        + tot["funding"]
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-12)
