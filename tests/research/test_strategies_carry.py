"""Tests for apps.research.strategies.carry (PLAN §2.7, §6.2 R11).

Small hand-built 4h fixtures check the rules; the integration test reads the
real local data (debug window) and is skipped without it.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.liquidation import liq_price
from apps.research.strategies.carry import (
    CARRY_CONFIGS,
    CARRY_UNIVERSE,
    CarryConfig,
    CarryError,
    carry_inputs,
    carry_leverage,
    load_carry_data,
    make_carry,
    run_carry_bt,
)

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)
START = "2024-01-01"
N_BARS = 6 * 20  # 20 days of 4h bars
F_HIGH = 0.0003  # APR 32.85 % >= K1 theta_in (25 %)


def bars(n=N_BARS, price=100.0, start=START):
    idx = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    p = np.full(n, float(price))
    df = pd.DataFrame({"open": p, "high": p, "low": p, "close": p, "volume": 1e6}, index=idx)
    df["quote_volume"] = df["volume"] * df["close"]
    return df


def funding(rate=F_HIGH, n_days=20, start=START, symbol="SOLUSDT"):
    idx = pd.date_range(start, periods=3 * n_days, freq="8h", tz="UTC")
    f = pd.Series(float(rate), index=idx, name="funding_rate")
    f.attrs["symbol"] = symbol
    return f


def market(symbol="SOLUSDT", rate=F_HIGH, spot_price=100.0, perp_price=100.0):
    return bars(price=spot_price), bars(price=perp_price), funding(rate, symbol=symbol)


def run1(spot, perp, fund, symbol="SOLUSDT", config="K1", cost=ZERO, **kw):
    kw.setdefault("fixed_slip_bps", 0.0)
    return run_carry_bt(make_carry(config), {symbol: spot}, {symbol: perp}, {symbol: fund}, cost, **kw)


def first_entry_time(fund):
    """First settlement whose 9-settlement mean is known: the 9th settlement."""
    return fund.index[8]


# --------------------------------------------------------------------------- configs
def test_configs_k1_k3_match_the_plan():
    assert (CARRY_CONFIGS["K1"].theta_in, CARRY_CONFIGS["K1"].theta_out) == (0.25, 0.08)
    assert (CARRY_CONFIGS["K2"].theta_in, CARRY_CONFIGS["K2"].theta_out) == (0.20, 0.05)
    assert (CARRY_CONFIGS["K3"].theta_in, CARRY_CONFIGS["K3"].theta_out) == (0.35, 0.10)
    for c in CARRY_CONFIGS.values():
        assert (c.max_symbol, c.max_symbols, c.max_total, c.basis_exit) == (0.20, 5, 0.70, -0.002)
    assert make_carry("K2").n_free_params == 2
    with pytest.raises(CarryError):
        CarryConfig("bad", theta_in=0.05, theta_out=0.08)
    with pytest.raises(CarryError):
        CarryConfig("bad", theta_in=0.25, theta_out=0.08, short_leverage=2.0)


def test_short_survives_a_100pct_squeeze():
    lev = carry_leverage(CARRY_CONFIGS["K1"])
    assert lev <= 1.0
    assert liq_price(100.0, lev, -1) >= 200.0 - 1e-9
    assert liq_price(100.0, 1.0, -1) < 200.0          # plain 1x would not survive it


# --------------------------------------------------------------------------- BNB
def test_bnb_is_excluded_everywhere():
    spot, perp, fund = market(symbol="BNBUSDT")
    with pytest.raises(CarryError):
        run1(spot, perp, fund, symbol="BNBUSDT")
    with pytest.raises(CarryError):
        carry_inputs(spot, perp, fund)
    with pytest.raises(CarryError):
        load_carry_data(["BNBUSDT"])
    assert "BNBUSDT" not in CARRY_UNIVERSE and len(CARRY_UNIVERSE) == 9


# --------------------------------------------------------------------------- alignment
def test_inputs_are_on_the_settlement_grid_and_use_the_bar_closing_there():
    spot, perp, fund = market()
    perp["close"] = 100.0 + np.arange(len(perp)) * 0.01
    inp = carry_inputs(spot, perp, fund)
    assert set(inp.index.hour) == {0, 8, 16}
    assert inp.index[0] == spot.index[0] + pd.Timedelta(hours=8)    # first 4h bar closing at 08:00
    tau = inp.index[5]
    label = tau - pd.Timedelta(hours=4)
    assert inp.at[tau, "perp_close"] == perp.at[label, "close"]
    assert inp.at[tau, "basis"] == pytest.approx(perp.at[label, "close"] / 100.0 - 1.0)
    # F_bar_3d needs 9 settlements: NaN before the 9th one, F_HIGH from it on.
    assert inp.loc[inp.index < fund.index[8], "f_bar_3d"].isna().all()
    assert inp.at[fund.index[8], "apr_3d"] == pytest.approx(F_HIGH * 3 * 365)
    assert inp.at[tau, "f_last"] == F_HIGH


def test_inputs_are_causal():
    spot, perp, fund = market()
    perp["close"] = 100.0 + np.sin(np.arange(len(perp)))
    full = carry_inputs(spot, perp, fund)
    cut = full.index[20]
    trunc = carry_inputs(spot[spot.index < cut], perp[perp.index < cut], fund[fund.index <= cut])
    pd.testing.assert_frame_equal(trunc.loc[:cut], full.loc[:cut])


def test_entry_fills_at_the_open_after_the_settlement_and_skips_its_funding():
    spot, perp, fund = market()
    res = run1(spot, perp, fund)
    tau = first_entry_time(fund)
    trades = res.trades
    assert set(trades["time"].iloc[:2]) == {tau}
    assert list(trades["leg"].iloc[:2]) == ["spot", "perp"]
    q = trades["qty"].iloc[0]
    assert trades["qty"].iloc[1] == pytest.approx(-q)                  # same quantity, opposite sides
    fl = res.costs["funding"]
    paid = fl[fl != 0]
    # The settlement that triggered the entry is not collected; the next one is.
    assert paid.index.get_level_values("date")[0] == tau + pd.Timedelta(hours=8)
    assert paid.iloc[0] == pytest.approx(q * 100.0 * F_HIGH)            # short receives when F > 0
    assert (paid > 0).all()
    # Number of settlements collected while open (until the end of the data).
    n_settle = int(((fund.index > tau) & (fund.index < spot.index[-1] + pd.Timedelta(hours=4))).sum())
    assert len(paid) == n_settle
    assert res.meta["pnl_breakdown"]["funding"] == pytest.approx(n_settle * q * 100.0 * F_HIGH)
    assert res.meta["paper_only"] and res.meta["pnl_verified"] is False
    assert "unverified" in res.meta["warning"]


def test_decisions_only_at_settlement_closes():
    spot, perp, fund = market()
    res = run1(spot, perp, fund)
    for t in res.trades["time"]:
        assert t.hour in (0, 8, 16)


# --------------------------------------------------------------------------- costs
def test_four_cost_legs_per_cycle():
    spot, perp, fund = market()
    fund.iloc[30:] = -0.0001                     # forces an APR exit
    cost = CostModel()                           # 0.10 % spot, 0.05 % perp taker
    res = run1(spot, perp, fund, cost=cost, fixed_slip_bps=10.0)
    cyc = res.meta["cycles"]
    assert len(cyc) == 1
    c = cyc.iloc[0]
    legs = res.trades
    assert len(legs) == 4 and sorted(legs["leg"]) == ["perp", "perp", "spot", "spot"]
    # Commission: 2 spot legs at 0.10 % + 2 perp legs at 0.05 % on the slipped fills.
    exp_comm = c.qty * (0.001 * (c.spot_entry + c.spot_exit) + 0.0005 * (c.perp_entry + c.perp_exit))
    assert c.commission == pytest.approx(exp_comm)
    assert legs["commission"].sum() == pytest.approx(exp_comm)
    # Slippage: 10 bp on each of the 4 legs (all prices are 100).
    assert c.slippage == pytest.approx(c.qty * 4 * 100.0 * 10 / 1e4)
    # About 0.30 % of the notional + 4 x 10 bp per cycle.
    assert (c.commission + c.slippage) / (c.qty * 100.0) == pytest.approx(0.003 + 0.004, rel=1e-2)
    # Buys pay up, sells receive less.
    assert c.spot_entry > 100.0 and c.perp_entry < 100.0
    assert c.spot_exit < 100.0 and c.perp_exit > 100.0
    # cost_mult doubles commission and slippage.
    res2 = run1(spot, perp, fund, cost=cost.stressed(2.0), fixed_slip_bps=10.0)
    c2 = res2.meta["cycles"].iloc[0]
    assert (c2.commission + c2.slippage) / c2.qty == pytest.approx(2 * (c.commission + c.slippage) / c.qty, rel=1e-2)


def test_funding_mult_scales_funding():
    spot, perp, fund = market()
    base = run1(spot, perp, fund).meta["pnl_breakdown"]["funding"]
    stressed = run1(spot, perp, fund, cost=CostModel(0, 0, 0, funding_mult=0.5)).meta["pnl_breakdown"]["funding"]
    assert stressed == pytest.approx(0.5 * base, rel=1e-6)


def test_apr_exit_and_hysteresis():
    spot, perp, fund = market()
    fund.iloc[30:] = -0.0001
    res = run1(spot, perp, fund)
    strat = make_carry("K1")
    inp = carry_inputs(spot, perp, fund)
    exit_tau = inp.index[strat.exit_now(inp) & (inp.index > first_entry_time(fund))][0]
    cyc = res.meta["cycles"].iloc[0]
    assert cyc.exit_time == exit_tau and cyc.exit_reason == "signal_exit"
    assert inp.at[exit_tau, "apr_3d"] < 0.08
    # No re-entry: F_last <= 0 and APR below theta_in afterwards.
    assert len(res.meta["cycles"]) == 1 and res.meta["open_cycles"] == []


# --------------------------------------------------------------------------- basis drift
def test_basis_drift_is_booked_and_equity_reconciles():
    spot, perp, fund = market()
    perp.loc[perp.index >= "2024-01-06", ["open", "high", "low", "close"]] = 100.15  # basis +0.15 %
    spot.loc[spot.index >= "2024-01-10", ["open", "high", "low", "close"]] = 99.70   # basis widens, > -0.2 %
    res = run1(spot, perp, fund, cost=CostModel(), fixed_slip_bps=2.0)
    q = res.trades["qty"].iloc[0]
    bd = res.meta["pnl_breakdown"]
    # Entry at basis 0 (both 100); open at the end with spot 99.70, perp 100.15.
    assert bd["basis_pnl"] == pytest.approx(q * ((99.70 - 100.0) - (100.15 - 100.0)))
    assert bd["basis_pnl"] < 0
    final = res.equity.iloc[-1] - 10_000.0
    assert final == pytest.approx(bd["net"], rel=1e-9, abs=1e-9)


def test_negative_basis_exits_and_blocks_entries():
    spot, perp, fund = market()
    spot.loc[spot.index >= "2024-01-08", ["open", "high", "low", "close"]] = 100.5  # basis -0.5 %
    res = run1(spot, perp, fund)
    cyc = res.meta["cycles"]
    assert len(cyc) == 1 and cyc.iloc[0].exit_reason == "signal_exit"
    assert cyc.iloc[0].exit_time == pd.Timestamp("2024-01-08 08:00", tz="UTC")
    assert res.meta["open_cycles"] == []      # never re-entered while basis < -0.2 %
    assert cyc.iloc[0].basis_pnl == pytest.approx(cyc.iloc[0].qty * 0.5)


# --------------------------------------------------------------------------- sizing / liquidation
def test_sizing_caps_per_symbol_count_and_total():
    syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"]
    spot = {s: bars() for s in syms}
    perp = {s: bars() for s in syms}
    fund = {s: funding(F_HIGH + 1e-5 * i, symbol=s) for i, s in enumerate(syms)}
    res = run_carry_bt(make_carry("K1"), spot, perp, fund, ZERO, fixed_slip_bps=0.0)
    # 3 cycles at 20 % + a 4th with the remaining 10 %: the 70 % total binds first.
    assert res.meta["counters"]["entries"] == 4
    assert res.meta["counters"]["skipped_capacity"] > 0
    # Candidates are ranked by APR: the two lowest (BTC, ETH) are left out.
    assert sorted(res.meta["open_cycles"]) == sorted(syms[2:])
    # With 10 % per symbol the 5-symbol limit binds instead.
    res10 = run_carry_bt(make_carry("K1", max_symbol=0.10), spot, perp, fund, ZERO, fixed_slip_bps=0.0)
    assert res10.meta["counters"]["entries"] == 5 and "BTCUSDT" not in res10.meta["open_cycles"]
    entries = res.trades[res.trades["leg"] == "spot"]
    lev = carry_leverage(CARRY_CONFIGS["K1"])
    capital = entries["qty"] * 100.0 * (1 + 1 / lev)
    assert (capital <= 0.20 * 10_000 + 1e-6).all()
    assert capital.sum() <= 0.70 * 10_000 + 1e-6


def test_squeeze_liquidates_the_short_and_closes_the_spot():
    spot, perp, fund = market()
    jump = perp.index >= "2024-01-10"
    perp.loc[jump, ["open", "low", "close"]] = 150.0
    perp.loc[jump, "high"] = 250.0            # +150 % wick: beyond the liquidation price
    spot.loc[spot.index >= "2024-01-10", ["open", "high", "low", "close"]] = 150.0
    res = run1(spot, perp, fund)
    assert res.meta["counters"]["liquidations"] >= 1
    cyc = res.meta["cycles"].iloc[0]
    assert cyc.exit_reason == "liquidation"
    # The perp leg is booked at the bankruptcy price (whole isolated margin lost).
    assert cyc.perp_exit == pytest.approx(cyc.perp_entry * (1 + 1 / cyc.leverage))
    assert cyc.perp_exit > liq_price(cyc.perp_entry, cyc.leverage, -1)


def test_liquidation_loses_the_whole_isolated_margin():
    spot, perp, fund = market()
    fund.loc[fund.index >= "2024-01-10"] = 0.0   # no re-entry after the squeeze: one cycle only
    jump = perp.index >= "2024-01-10"
    perp.loc[jump, ["open", "low", "close"]] = 150.0
    perp.loc[jump, "high"] = 250.0
    spot.loc[spot.index >= "2024-01-10", ["open", "high", "low", "close"]] = 150.0
    res = run1(spot, perp, fund)
    assert len(res.meta["cycles"]) == 1 and res.meta["open_cycles"] == []
    cyc = res.meta["cycles"].iloc[0]
    assert cyc.exit_reason == "liquidation"
    margin = cyc.qty * cyc.perp_entry / cyc.leverage
    liq = liq_price(cyc.perp_entry, cyc.leverage, -1)
    assert cyc.liquidation_loss == pytest.approx(margin)
    # Net cash of the perp leg (zero fees/slippage otherwise): exactly -margin.
    tr = res.trades[(res.trades["leg"] == "perp")]
    exit_row = tr[tr["reason"] == "liquidation"].iloc[0]
    perp_cash = -cyc.qty * (exit_row["price"] - cyc.perp_entry)
    assert perp_cash == pytest.approx(-margin)
    assert margin > cyc.qty * (liq - cyc.perp_entry)          # more than the old liq-price booking
    # The clearance fee (bankruptcy - liq) is booked as commission in trades, ledger and cycle.
    fee = cyc.qty * (exit_row["price"] - liq)
    assert exit_row["commission"] == pytest.approx(fee) and fee > 0
    assert cyc.commission == pytest.approx(fee)
    assert res.costs["commission"].sum() == pytest.approx(fee)
    # Equity: spot leg gain + funding - margin, and the breakdown reconciles.
    spot_pnl = cyc.qty * (cyc.spot_exit - cyc.spot_entry)
    final = res.equity.iloc[-1] - 10_000.0
    assert final == pytest.approx(spot_pnl + cyc.funding - margin)
    assert final == pytest.approx(res.meta["pnl_breakdown"]["net"])
    assert cyc.net == pytest.approx(final)


def test_signal_exit_has_no_liquidation_loss():
    spot, perp, fund = market()
    spot.loc[spot.index >= "2024-01-08", ["open", "high", "low", "close"]] = 100.5
    cyc = run1(spot, perp, fund).meta["cycles"]
    assert (cyc["liquidation_loss"] == 0.0).all()


def test_missing_price_with_open_cycle_raises():
    spot, perp, fund = market()
    spot.iloc[60, :4] = np.nan
    with pytest.raises(CarryError):
        run1(spot, perp, fund)


# --------------------------------------------------------------------------- real data
DATA = Path("/home/user/harness/data")


@pytest.mark.skipif(not (DATA / "funding" / "BTCUSDT.csv").exists(), reason="local data not available")
def test_integration_debug_window():
    sp, pp, fd = load_carry_data(["BTCUSDT", "ETHUSDT"], "2020-10-01", "2021-03-31 20:00", root=DATA)
    res = run_carry_bt(make_carry("K2"), sp, pp, fd, CostModel())
    assert res.meta["pnl_verified"] is False and res.meta["funding_verified"] is False
    assert np.isfinite(res.equity).all()
    bd = res.meta["pnl_breakdown"]
    assert res.equity.iloc[-1] - 10_000.0 == pytest.approx(bd["net"], abs=1e-6)
    assert res.meta["data"]["spot/BTCUSDT"]["source_commit"]
