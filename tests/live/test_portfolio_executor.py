"""Tests for apps/live/portfolio_executor.py (PLAN.md §6.2 L04, §4.3, §4.4, §7). No network.

Market data are small deterministic hand-built fixtures (tests/live/exchange_mock.py).
"""
import json
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit

import numpy as np
import pandas as pd
import pytest
import responses

from apps.live.kill_switch import KillSwitch, KillSwitchLevel, load_risk_limits
from apps.live.portfolio_executor import (
    ExecutorConfig,
    ExecutorError,
    PortfolioExecutor,
    build_executor,
    client_order_id,
    decide_targets,
    decision_bar,
    make_engine,
    next_run_time,
    research_kill_state,
)
from apps.live.reconciliation import FuturesVenue, LiveState, LocalPosition, PaperVenue, SpotVenue
from apps.research.engine.fills import ratchet_stop
from apps.research.engine.portfolio_bt import daily_inputs
from apps.research.portfolio.sizing import annualized_vol, discretize, stress_cov, target_weights
from core.binance_client import BinanceClient
from core.binance_futures_client import BinanceFuturesClient

from .exchange_mock import NOW, MockExchange, fixture_data, trend_rows

SYMS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DAY = pd.Timestamp("2026-10-14", tz="UTC")


@pytest.fixture
def limits():
    return load_risk_limits()


def make_cfg(tmp_path=None, **kw):
    base = dict(spot_symbols=SYMS, state_path=None, journal_path=None, kill_switch_state_path=None,
                stop_retry_delays=(0.0, 0.0))
    if tmp_path is not None:
        base.update(state_path=tmp_path / "state.json", journal_path=tmp_path / "journal.jsonl")
    base.update(kw)
    return ExecutorConfig(**base)


def make_executor(cfg, venues, limits, mode="spot_demo", state=None, ks=None, alerts=None):
    return PortfolioExecutor(cfg, venues, mode=mode, limits=limits, state=state or LiveState.load(cfg.state_path),
                             kill_switch=ks or KillSwitch(limits), alert=(alerts.append if alerts is not None else None),
                             sleep=lambda s: None)


# --- helpers ---------------------------------------------------------------------

def test_client_order_id_is_deterministic_and_valid():
    cid = client_order_id(pd.Timestamp("2026-10-15", tz="UTC"), "T3", "BTCUSDT", 1)
    assert cid == "20261015-T3-BTCUSDT-1"
    assert client_order_id("2026-10-15", "T3", "BTCUSDT", 1) == cid
    with pytest.raises(ExecutorError):
        client_order_id("2026-10-15", "T3", "X" * 40, 1)


def test_decision_bar_and_schedule():
    assert decision_bar(NOW) == DAY
    assert decision_bar(datetime(2026, 10, 15, 23, 59, tzinfo=timezone.utc)) == DAY
    assert next_run_time(datetime(2026, 10, 14, 23, 0, tzinfo=timezone.utc)) == NOW
    assert next_run_time(NOW) == NOW + timedelta(days=1)
    with pytest.raises(ExecutorError):
        decision_bar(datetime(2026, 10, 15, 0, 5))


def test_make_engine_shares_research_configs():
    strat, sizing = make_engine("T3")
    assert strat.name == "TREND-MIX-T3" and sizing.sigma_target == 0.15 and sizing.band == 0.20
    with pytest.raises(ExecutorError):
        make_engine("X9")
    with pytest.raises(ExecutorError):
        ExecutorConfig(engine="S1")          # short leg needs futures routing


# --- same code as research ----------------------------------------------------------

def _panel(data):
    return {s: data.closed_klines(s)[["open", "high", "low", "close", "volume", "quote_volume"]] for s in SYMS}


def test_decide_targets_matches_research_layer_d():
    data = fixture_data()
    panel = _panel(data)
    strat, sizing = make_engine("T3")
    td = decide_targets(strat, panel, sizing, pd.Series(0.0, index=list(SYMS)), None, day=DAY)
    # Recompute with the research functions directly.
    E = strat.signal(panel, None).loc[DAY].fillna(0.0)
    e_q = discretize(E, sizing.step)
    rets = pd.DataFrame({s: daily_inputs(panel[s])["logret"] for s in SYMS})
    sigma = annualized_vol(rets.loc[:DAY], None, window=90)
    w = target_weights(e_q, sigma, stress_cov(rets.loc[:DAY], DAY), sizing)
    pd.testing.assert_series_equal(td.w_layer_d, w, check_names=False)
    pd.testing.assert_series_equal(td.w_final, w, check_names=False)     # held 0: band opens everything
    assert td.w_final["BTCUSDT"] > 0 and td.w_final["SOLUSDT"] == 0
    assert td.w_final[td.w_final > 0].sum() <= 1.0 + 1e-12


def test_decide_targets_band_lock_and_frozen():
    data = fixture_data()
    panel = _panel(data)
    strat, sizing = make_engine("T3")
    base = decide_targets(strat, panel, sizing, pd.Series(0.0, index=list(SYMS)), None, day=DAY).w_final
    held = base * 0.9                        # within the 20% band: keep held
    td = decide_targets(strat, panel, sizing, held, None, day=DAY)
    assert td.w_final["BTCUSDT"] == pytest.approx(held["BTCUSDT"])
    locks = {"BTCUSDT": 1}
    td = decide_targets(strat, panel, sizing, pd.Series(0.0, index=list(SYMS)), None, day=DAY, locks=locks)
    assert td.w_final["BTCUSDT"] == 0 and locks == {"BTCUSDT": 1}
    panel2 = dict(panel)
    panel2["ETHUSDT"] = panel["ETHUSDT"].drop(index=DAY)
    td = decide_targets(strat, panel2, sizing, pd.Series({"BTCUSDT": 0.0, "ETHUSDT": 0.1, "SOLUSDT": 0.0}),
                        None, day=DAY)
    assert td.frozen == ["ETHUSDT"] and td.w_final["ETHUSDT"] == pytest.approx(0.1)


# --- dry run, end to end -----------------------------------------------------------

def test_dry_run_end_to_end(tmp_path, limits):
    data = fixture_data()
    cfg = make_cfg(tmp_path)
    state = LiveState.load(cfg.state_path)
    paper = PaperVenue("spot", data, state.paper.setdefault("spot", {"cash": 1_000.0}), 0.001, SYMS)
    ex = make_executor(cfg, {"spot": paper}, limits, mode="dry_run", state=state)
    report = ex.run(NOW)
    assert report.status == "ok" and report.mode == "dry_run" and report.nav == pytest.approx(1_000.0)

    # Only reads reached the market-data source: it has no write method at all.
    assert all(c.split(":")[0] in ("server_time_ms", "closed_klines", "filters") for c in data.calls)

    btc = [o for o in report.orders if o.symbol == "BTCUSDT"][0]
    assert btc.status == "filled" and btc.client_id == "20261015-T3-BTCUSDT-1" and btc.side == "BUY"
    # Rounded DOWN to the LOT_SIZE step (0.00001).
    target_qty = report.weights["BTCUSDT"] * 1_000.0 / btc.ref_price
    assert btc.qty == pytest.approx(math.floor(target_qty / 1e-5) * 1e-5)
    assert btc.qty <= target_qty
    # ETH order below minNotional (10000): skipped and journaled.
    eth = [o for o in report.orders if o.symbol == "ETHUSDT"][0]
    assert eth.status == "skipped" and eth.detail == "below_min_notional"
    assert "SOLUSDT" not in {o.symbol for o in report.orders}

    # Stop placed right after the fill: C - 3*ATR14 of the decision bar, rounded down to the tick.
    panel = _panel(data)
    atr = daily_inputs(panel["BTCUSDT"])["atr"].loc[DAY]
    expected = math.floor(ratchet_stop(None, panel["BTCUSDT"]["close"].loc[DAY], atr, 1) / 0.01) * 0.01
    (stop,) = paper.open_stops()
    assert stop.client_id == "20261015-T3-BTCUSDT-2" and stop.side == "SELL"
    assert stop.qty == pytest.approx(btc.qty) and stop.stop_price == pytest.approx(expected)

    # State and journal persisted.
    saved = json.loads((tmp_path / "state.json").read_text())
    assert saved["last_run_day"] == "2026-10-15"
    assert saved["positions"]["spot"]["BTCUSDT"]["stop_price"] == pytest.approx(expected)
    events = [json.loads(line)["event"] for line in (tmp_path / "journal.jsonl").read_text().splitlines()]
    for ev in ("run_start", "input_bar", "kill_switch", "decision", "order", "order_skipped", "stop", "run_end"):
        assert ev in events

    # Same day again: no-op.
    assert ex.run(NOW + timedelta(hours=1)).status == "skipped"

    # Next day (new process, same files): no duplicate entry, stop ratcheted only upwards.
    data2 = fixture_data(now=NOW + timedelta(days=1), extra_days=1)
    state2 = LiveState.load(cfg.state_path)
    paper2 = PaperVenue("spot", data2, state2.paper["spot"], 0.001, SYMS)
    ex2 = make_executor(cfg, {"spot": paper2}, limits, mode="dry_run", state=state2)
    rep2 = ex2.run(NOW + timedelta(days=1))
    assert rep2.status == "ok"
    assert not [o for o in rep2.orders if o.symbol == "BTCUSDT" and o.status == "filled"]
    (stop2,) = paper2.open_stops()
    assert stop2.stop_price >= stop.stop_price and stop2.qty == pytest.approx(btc.qty)


def test_dry_run_refuses_mutating_venues(limits):
    ex = MockExchange("spot", fixture_data(), cash=1_000.0, symbols=SYMS)
    with pytest.raises(ExecutorError):
        make_executor(make_cfg(), {"spot": ex}, limits, mode="dry_run")


def test_paper_stop_triggers_and_locks_symbol(tmp_path, limits):
    cfg = make_cfg(tmp_path)
    state = LiveState.load(cfg.state_path)
    paper = PaperVenue("spot", fixture_data(), state.paper.setdefault("spot", {"cash": 1_000.0}), 0.001, SYMS)
    make_executor(cfg, {"spot": paper}, limits, mode="dry_run", state=state).run(NOW)
    (stop,) = paper.open_stops()
    # Next day crashes through the stop.
    data2 = fixture_data(now=NOW + timedelta(days=1), extra_days=1)
    bar = data2.rows["BTCUSDT"][-2]
    bar[3] = f"{stop.stop_price * 0.9:.2f}"
    state2 = LiveState.load(cfg.state_path)
    paper2 = PaperVenue("spot", data2, state2.paper["spot"], 0.001, SYMS)
    rep = make_executor(cfg, {"spot": paper2}, limits, mode="dry_run", state=state2).run(NOW + timedelta(days=1))
    assert paper2.positions() == {} and paper2.open_stops() == []
    assert state2.locks == {"BTCUSDT": 1}
    assert not [o for o in rep.orders if o.symbol == "BTCUSDT"]     # no buy-back of the same move


# --- exchange mock (spot_demo-like) --------------------------------------------------

def test_stop_placed_immediately_after_each_fill(limits):
    data = fixture_data()
    for s in ("ETHUSDT",):
        data._filters[s] = data._filters["BTCUSDT"].__class__(s, data._filters[s].step_size, data._filters[s].min_qty,
                                                             None, data._filters[s].tick_size,
                                                             data._filters["BTCUSDT"].min_notional)
    ex = MockExchange("spot", data, cash=10_000.0, symbols=SYMS)
    rep = make_executor(make_cfg(), {"spot": ex}, limits).run(NOW)
    writes = ex.writes()
    kinds = [w[0] for w in writes]
    assert kinds == ["market_order", "place_stop", "market_order", "place_stop"]
    for i in (0, 2):
        assert writes[i][1] == writes[i + 1][1]        # stop on the symbol just filled
        assert writes[i + 1][3] == pytest.approx(writes[i][3])
    assert [w[4] for w in writes if w[0] == "market_order"] == ["20261015-T3-BTCUSDT-1", "20261015-T3-ETHUSDT-1"]
    assert {o.status for o in rep.orders} == {"filled"}


def test_stop_failure_closes_position_and_blocks_symbol(limits):
    data = fixture_data()
    ex = MockExchange("spot", data, cash=1_000.0, symbols=SYMS, fail_stops=99)
    alerts = []
    state = LiveState()
    rep = make_executor(make_cfg(), {"spot": ex}, limits, state=state, alerts=alerts).run(NOW)
    orders = [w for w in ex.writes() if w[0] == "market_order"]
    assert orders[0][2] == "BUY" and orders[1][2] == "SELL"
    assert orders[1][4] == "20261015-T3-BTCUSDT-3" and orders[1][3] == pytest.approx(orders[0][3])
    assert len([w for w in ex.writes() if w[0] == "place_stop"]) == 3      # 1 attempt + 2 retries
    assert ex.positions() == {}
    assert "BTCUSDT" in state.blocked
    assert any("WITHOUT stop" in a for a in alerts)
    assert [o.reason for o in rep.orders if o.symbol == "BTCUSDT"] == ["increase", "emergency_close"]
    # Blocked symbol: no new entry the next day.
    data2 = fixture_data(now=NOW + timedelta(days=1), extra_days=1)
    ex2 = MockExchange("spot", data2, cash=ex.book["cash"], symbols=SYMS)
    rep2 = make_executor(make_cfg(), {"spot": ex2}, limits, state=state).run(NOW + timedelta(days=1))
    assert rep2.weights["BTCUSDT"] == 0 and not [w for w in ex2.writes() if w[1] == "BTCUSDT"]


def test_existing_order_id_is_adopted_not_resent(limits):
    data = fixture_data()
    ex = MockExchange("spot", data, cash=1_000.0, symbols=SYMS)
    first = make_executor(make_cfg(), {"spot": ex}, limits, state=LiveState()).run(NOW)
    sent = [w for w in ex.writes() if w[0] == "market_order"]
    assert len(sent) == 1
    # Simulate a crash after the order: the exchange keeps the order, the local view says "flat".
    executor = make_executor(make_cfg(), {"spot": ex}, limits, state=LiveState())
    executor._day = DAY
    executor._panel = _panel(data)
    executor._report = first
    ks = executor.kill_switch.update(1_000.0, NOW)
    touched = set()
    executor._trade("spot", "BTCUSDT", 0.0, sent[0][3], first.orders[0].ref_price, ks, first, touched, 1)
    assert first.orders[-1].status == "existing"
    assert len([w for w in ex.writes() if w[0] == "market_order"]) == 1


def test_kill_switch_block_entries_sends_no_buy(limits):
    ex = MockExchange("spot", fixture_data(), cash=1_000.0, symbols=SYMS)
    ks = KillSwitch(limits)
    ks.update(1_000.0, NOW - timedelta(minutes=4))
    ks.update(975.0, NOW - timedelta(minutes=1))              # -2.5 % today
    assert ks.level == KillSwitchLevel.BLOCK_ENTRIES
    rep = make_executor(make_cfg(), {"spot": ex}, limits, ks=ks).run(NOW)
    assert rep.kill_level == "BLOCK_ENTRIES"
    assert [w for w in ex.writes() if w[0] == "market_order"] == []
    assert all(w == 0 for w in rep.weights.values())


def test_kill_switch_flatten_closes_short_keeps_spot(limits):
    data = fixture_data()
    spot = MockExchange("spot", data, cash=500.0, symbols=SYMS)
    spot.book["positions"]["BTCUSDT"] = 0.001
    fut = MockExchange("futures", data, cash=500.0, fee_rate=0.0005, symbols=SYMS)
    fut.set_marks({"SOLUSDT": 100.0})
    fut.market_order("SOLUSDT", "SELL", 1.0, "seed")                # existing short
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.001))
    state.put(LocalPosition("SOLUSDT", "futures", -1.0))
    spot.calls.clear()
    fut.calls.clear()
    ks = KillSwitch(limits)
    ks.update(1_100.0, NOW - timedelta(minutes=4))
    ks.update(1_000.0, NOW - timedelta(minutes=1))            # -9 %: FLATTEN
    cfg = make_cfg(shorts_on_futures=True)
    rep = make_executor(cfg, {"spot": spot, "futures": fut}, limits, state=state, ks=ks).run(NOW)
    assert rep.kill_level == "FLATTEN"
    assert [w for w in spot.writes() if w[0] == "market_order"] == []     # spot 1x long is kept
    closes = [w for w in fut.writes() if w[0] == "market_order"]
    assert len(closes) == 1 and closes[0][1:3] == ("SOLUSDT", "BUY") and closes[0][5] is True
    assert fut.positions() == {}
    assert rep.weights["BTCUSDT"] > 0


# --- modes ---------------------------------------------------------------------------

def test_trading_mode_defaults_to_dry_run_with_paper_venues(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    cfg = make_cfg(tmp_path)
    ex = build_executor(cfg, environ={}, spot_client=BinanceClient("", "", demo_mode=False))
    assert ex.mode == "dry_run"
    assert isinstance(ex.venues["spot"], PaperVenue) and not ex.venues["spot"].mutating
    assert ex.state.paper["spot"]["cash"] == cfg.paper_equity_spot


def test_live_requires_confirmation(tmp_path):
    with pytest.raises(ExecutorError):
        build_executor(make_cfg(tmp_path), environ={"TRADING_MODE": "live"})
    with pytest.raises(ExecutorError):
        build_executor(make_cfg(tmp_path), environ={"TRADING_MODE": "yolo"})


def test_spot_demo_requires_demo_client(tmp_path):
    with pytest.raises(ExecutorError):
        build_executor(make_cfg(tmp_path), environ={"TRADING_MODE": "spot_demo"},
                       spot_client=BinanceClient("k", "s", demo_mode=False))


# --- real clients with mocked HTTP -----------------------------------------------------

SBASE = "https://spot.test"
FBASE = "https://futures.test"


def _q(call):
    return dict(parse_qsl(urlsplit(call.request.url).query, keep_blank_values=True))


@responses.activate
def test_spot_venue_closed_klines_and_order_ids(monkeypatch):
    monkeypatch.setenv("BINANCE_TESTNET_URL", SBASE)
    client = BinanceClient("k" * 16, "s" * 16, demo_mode=True)
    venue = SpotVenue(client, ("BTCUSDT",))
    rows = trend_rows(20_000.0, 0.003, n=5)
    responses.get(f"{SBASE}/api/v3/klines", json=rows)
    responses.get(f"{SBASE}/api/v3/time", json={"serverTime": int(NOW.timestamp() * 1000)})
    df = venue.closed_klines("BTCUSDT")
    assert len(df) == 4 and df.index[-1] == DAY               # the open 2026-10-15 bar is dropped
    assert len(client.get_klines("BTCUSDT", "1d", closed_only=True)) == 4
    assert len(client.get_klines("BTCUSDT", "1d")) == 5
    responses.post(f"{SBASE}/api/v3/order", json={"orderId": 1, "status": "FILLED", "executedQty": "0.001",
                                                 "cummulativeQuoteQty": "100"})
    res = venue.market_order("BTCUSDT", "BUY", 0.001, "20261015-T3-BTCUSDT-1")
    assert res.executed_qty == 0.001 and res.avg_price == pytest.approx(100_000.0)
    venue.place_stop("BTCUSDT", "SELL", 0.001, 90_000.0, "20261015-T3-BTCUSDT-2")
    p1, p2 = _q(responses.calls[-2]), _q(responses.calls[-1])
    assert p1["newClientOrderId"] == "20261015-T3-BTCUSDT-1" and p1["type"] == "MARKET"
    assert p2["type"] == "STOP_LOSS" and p2["stopPrice"] == "90000.0" and p2["side"] == "SELL"
    responses.get(f"{SBASE}/api/v3/order", status=400, json={"code": -2013, "msg": "Order does not exist."})
    assert venue.find_order("BTCUSDT", "nope") is None


FUT_INFO = {"symbols": [{"symbol": "BTCUSDT", "filters": [
    {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
    {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "120"},
    {"filterType": "MIN_NOTIONAL", "notional": "100"}]}]}


@responses.activate
def test_futures_entry_stop_failure_closes_with_reduce_only(limits):
    """L04 via core.binance_futures_client: one-way/isolated/1x, MARKET entry, algo stop
    rejected 3 times -> reduceOnly MARKET close with the emergency client id."""
    client = BinanceFuturesClient("k" * 16, "s" * 16, base_url=FBASE)
    venue = FuturesVenue(client, ("BTCUSDT",))
    rows = trend_rows(20_000.0, 0.003, n=600)
    pos = {"amt": 0.0}

    def order_cb(request):
        p = dict(parse_qsl(urlsplit(request.url).query))
        q = float(p["quantity"])
        pos["amt"] += q if p["side"] == "BUY" else -q
        body = {"orderId": 1, "status": "FILLED", "executedQty": p["quantity"], "avgPrice": "118000",
                "reduceOnly": p.get("reduceOnly") == "true"}
        return 200, {}, json.dumps(body)

    def position_cb(request):
        return 200, {}, json.dumps([{"symbol": "BTCUSDT", "positionAmt": str(pos["amt"]),
                                     "entryPrice": "118000", "leverage": "1"}])

    responses.get(f"{FBASE}/fapi/v1/time", json={"serverTime": int(NOW.timestamp() * 1000)})
    responses.get(f"{FBASE}/fapi/v1/klines", json=rows)
    responses.get(f"{FBASE}/fapi/v1/exchangeInfo", json=FUT_INFO)
    responses.get(f"{FBASE}/fapi/v2/account", json={"totalMarginBalance": "1000", "availableBalance": "1000"})
    responses.add_callback(responses.GET, f"{FBASE}/fapi/v2/positionRisk", callback=position_cb)
    responses.get(f"{FBASE}/fapi/v1/openAlgoOrders", json=[])
    responses.get(f"{FBASE}/fapi/v1/leverageBracket",
                  json=[{"symbol": "BTCUSDT", "brackets": [{"notionalFloor": 0, "maintMarginRatio": 0.004}]}])
    responses.get(f"{FBASE}/fapi/v1/order", status=400, json={"code": -2013, "msg": "Order does not exist."})
    responses.post(f"{FBASE}/fapi/v1/positionSide/dual", json={"code": 200})
    responses.post(f"{FBASE}/fapi/v1/marginType", json={"code": 200})
    responses.post(f"{FBASE}/fapi/v1/leverage", json={"leverage": 1})
    responses.add_callback(responses.POST, f"{FBASE}/fapi/v1/order", callback=order_cb)
    responses.post(f"{FBASE}/fapi/v1/algoOrder", status=400, json={"code": -1111, "msg": "Precision"})

    cfg = make_cfg(spot_symbols=(), futures_symbols=("BTCUSDT",))
    alerts = []
    state = LiveState()
    rep = make_executor(cfg, {"futures": venue}, limits, mode="futures_testnet", state=state,
                        alerts=alerts).run(NOW)
    posts = [(urlsplit(c.request.url).path, _q(c)) for c in responses.calls if c.request.method == "POST"]
    paths = [p for p, _ in posts]
    assert paths[:3] == ["/fapi/v1/positionSide/dual", "/fapi/v1/marginType", "/fapi/v1/leverage"]
    assert posts[1][1]["marginType"] == "ISOLATED" and posts[2][1]["leverage"] == "1"
    assert paths[3] == "/fapi/v1/order" and paths[4:7] == ["/fapi/v1/algoOrder"] * 3
    entry, close = posts[3][1], posts[7][1]
    assert entry["side"] == "BUY" and entry["newClientOrderId"] == "20261015-T3-BTCUSDT-1"
    assert float(entry["quantity"]) * 1000 == pytest.approx(round(float(entry["quantity"]) * 1000))  # step 0.001
    algo = posts[4][1]
    assert algo["reduceOnly"] == "true" and algo["workingType"] == "MARK_PRICE" and algo["side"] == "SELL"
    assert close["side"] == "SELL" and close["reduceOnly"] == "true" and close["type"] == "MARKET"
    assert close["newClientOrderId"] == "20261015-T3-BTCUSDT-3" and close["quantity"] == entry["quantity"]
    assert pos["amt"] == pytest.approx(0.0)
    assert "BTCUSDT" in state.blocked and any("WITHOUT stop" in a for a in alerts)
    assert rep.status == "ok"


def test_spot_reductions_adjust_the_stop_before_selling(limits):
    data = fixture_data()
    ex = MockExchange("spot", data, cash=200.0, symbols=SYMS)
    ex.set_marks({"BTCUSDT": 118_907.71, "SOLUSDT": 63.0})
    ex.book["positions"].update({"BTCUSDT": 0.006, "SOLUSDT": 2.0})      # BTC ~70 % of NAV; SOL trends down
    btc_stop = PaperVenue.place_stop(ex, "BTCUSDT", "SELL", 0.006, 100_000.0, "old-btc")
    sol_stop = PaperVenue.place_stop(ex, "SOLUSDT", "SELL", 2.0, 50.0, "old-sol")
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.006, 100_000.0, "old-btc", btc_stop.order_id))
    state.put(LocalPosition("SOLUSDT", "spot", 2.0, 50.0, "old-sol", sol_stop.order_id))
    rep = make_executor(make_cfg(), {"spot": ex}, limits, state=state).run(NOW)
    w = ex.writes()
    sol = [x for x in w if x[1] == "SOLUSDT"]
    assert [x[0] for x in sol] == ["cancel_stop", "market_order"]          # stop released, then full exit
    assert sol[1][2:4] == ("SELL", 2.0)
    btc = [x for x in w if x[1] == "BTCUSDT"]
    assert [x[0] for x in btc] == ["replace_stop", "market_order"]         # stop shrunk BEFORE the sell
    remaining = btc[0][2]
    assert btc[1][2] == "SELL" and btc[1][3] + remaining == pytest.approx(0.006)
    assert remaining * 118_907.71 / rep.nav == pytest.approx(rep.weights["BTCUSDT"], abs=1e-4)
    (st,) = ex.open_stops()
    assert st.symbol == "BTCUSDT" and st.qty == pytest.approx(remaining) and st.stop_price >= 100_000.0
    assert ex.positions()["BTCUSDT"].qty == pytest.approx(remaining)


def test_short_engine_reads_funding_from_futures(limits):
    data = fixture_data()
    idx = pd.date_range("2025-06-01", "2026-10-14 16:00", freq="8h", tz="UTC")
    data.funding = {s: pd.Series(1e-4, index=idx, name="funding_rate") for s in SYMS}
    spot = MockExchange("spot", data, cash=1_000.0, symbols=SYMS)
    fut = MockExchange("futures", data, cash=0.0, fee_rate=0.0005, symbols=SYMS)
    cfg = make_cfg(engine="S1", shorts_on_futures=True)
    rep = make_executor(cfg, {"spot": spot, "futures": fut}, limits).run(NOW)
    assert rep.status == "ok"
    assert {f"funding:{s}" for s in SYMS} <= set(data.calls)
    assert rep.weights["SOLUSDT"] <= 0 and rep.weights["BTCUSDT"] > 0     # BTC > SMA200: short gate off
    assert not [x for x in fut.writes() if x[0] == "market_order"]


# --- kill-switch levels share the research apply_kill_switch ------------------------

def _decision(limits, start, end):
    ks = KillSwitch(limits)
    ks.update(start, NOW - timedelta(minutes=4))
    return ks, ks.update(end, NOW - timedelta(minutes=1))


def test_decide_targets_flatten_follows_signal_exit_and_reductions(limits):
    data = fixture_data()
    panel = _panel(data)
    strat, sizing = make_engine("T3")
    flat = pd.Series(0.0, index=list(SYMS))
    base = decide_targets(strat, panel, sizing, flat, None, day=DAY).w_final
    assert base["BTCUSDT"] > 0 and base["SOLUSDT"] == 0
    held = pd.Series({"BTCUSDT": base["BTCUSDT"] * 2.0, "ETHUSDT": 0.0, "SOLUSDT": 0.15})
    ks, dec = _decision(limits, 1_100.0, 1_000.0)                        # -9 %: FLATTEN
    assert ks.level == KillSwitchLevel.FLATTEN and dec.risk_multiplier == 0.0
    st = research_kill_state(dec, limits)
    assert st.level == "flatten_leveraged" and st.risk_mult == 1.0     # drawdown 9 % < 10 %: full risk
    _, dec_dd = _decision(limits, 1_000.0, 880.0)                        # -12 %: FLATTEN + half risk
    assert research_kill_state(dec_dd, limits).risk_mult == pytest.approx(0.5)
    td = decide_targets(strat, panel, sizing, held, dec, day=DAY)
    assert td.w_final["SOLUSDT"] == 0.0                                  # signal exit: the long is sold
    assert td.w_final["BTCUSDT"] == pytest.approx(base["BTCUSDT"])      # cut toward the strategy target
    # Never increases: a held long below the target stays at most at its held size.
    small = pd.Series({"BTCUSDT": base["BTCUSDT"] * 0.5, "ETHUSDT": 0.0, "SOLUSDT": 0.0})
    td = decide_targets(strat, panel, sizing, small, dec, day=DAY)
    assert 0 < td.w_final["BTCUSDT"] <= small["BTCUSDT"] + 1e-12
    # Shorts and leveraged longs are closed.
    held = pd.Series({"BTCUSDT": base["BTCUSDT"], "ETHUSDT": -0.1, "SOLUSDT": 0.0})
    td = decide_targets(strat, panel, sizing, held, dec, day=DAY, leverage={"BTCUSDT": 1.5})
    assert td.w_final["ETHUSDT"] == 0.0 and td.w_final["BTCUSDT"] == 0.0


def test_decide_targets_halt_closes_everything(limits):
    data = fixture_data()
    panel = _panel(data)
    strat, sizing = make_engine("T3")
    base = decide_targets(strat, panel, sizing, pd.Series(0.0, index=list(SYMS)), None, day=DAY).w_final
    held = pd.Series({"BTCUSDT": base["BTCUSDT"], "ETHUSDT": -0.05, "SOLUSDT": 0.1})
    ks, dec = _decision(limits, 1_000.0, 790.0)                          # drawdown 21 %: HALT
    assert ks.level == KillSwitchLevel.HALT
    td = decide_targets(strat, panel, sizing, held, dec, day=DAY)
    assert (td.w_final == 0.0).all()


def test_kill_switch_flatten_sells_spot_long_on_signal_exit(limits):
    data = fixture_data()
    spot = MockExchange("spot", data, cash=944.0, symbols=SYMS)       # NAV ~ 1000: stays at FLATTEN
    spot.book["positions"]["SOLUSDT"] = 1.0                         # strategy target for SOL is 0
    state = LiveState()
    state.put(LocalPosition("SOLUSDT", "spot", 1.0))
    spot.calls.clear()
    ks = KillSwitch(limits)
    ks.update(1_100.0, NOW - timedelta(minutes=4))
    ks.update(1_000.0, NOW - timedelta(minutes=1))                    # -9 %: FLATTEN
    rep = make_executor(make_cfg(), {"spot": spot}, limits, state=state, ks=ks).run(NOW)
    assert rep.kill_level == "FLATTEN"
    orders = [w for w in spot.writes() if w[0] == "market_order"]
    assert len(orders) == 1 and orders[0][1:3] == ("SOLUSDT", "SELL")
    assert rep.weights["SOLUSDT"] == 0.0
    assert spot.positions().get("SOLUSDT", 0.0) == 0.0


def test_kill_switch_halt_closes_all_positions(limits):
    data = fixture_data()
    spot = MockExchange("spot", data, cash=300.0, symbols=SYMS)
    spot.book["positions"]["BTCUSDT"] = 0.001
    fut = MockExchange("futures", data, cash=400.0, fee_rate=0.0005, symbols=SYMS)
    fut.set_marks({"SOLUSDT": 100.0})
    fut.market_order("SOLUSDT", "SELL", 1.0, "seed")                # existing short
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.001))
    state.put(LocalPosition("SOLUSDT", "futures", -1.0))
    spot.calls.clear()
    fut.calls.clear()
    ks = KillSwitch(limits)
    ks.update(1_000.0, NOW - timedelta(minutes=4))
    ks.update(790.0, NOW - timedelta(minutes=1))                      # drawdown 21 %: HALT
    assert ks.level == KillSwitchLevel.HALT
    cfg = make_cfg(shorts_on_futures=True)
    rep = make_executor(cfg, {"spot": spot, "futures": fut}, limits, state=state, ks=ks).run(NOW)
    assert rep.kill_level == "HALT"
    assert all(w == 0 for w in rep.weights.values())
    sells = [w for w in spot.writes() if w[0] == "market_order"]
    assert len(sells) == 1 and sells[0][1:3] == ("BTCUSDT", "SELL")
    buys = [w for w in fut.writes() if w[0] == "market_order"]
    assert len(buys) == 1 and buys[0][1:3] == ("SOLUSDT", "BUY") and buys[0][5] is True
    assert fut.positions() == {}
    assert spot.positions().get("BTCUSDT", 0.0) == 0.0


def test_parse_symbols_restricts_universe():
    from apps.live.portfolio_executor import ExecutorError, parse_symbols

    assert parse_symbols("btcusdt, ETH/USDT,BTCUSDT") == ("BTCUSDT", "ETHUSDT")
    with pytest.raises(ExecutorError):
        parse_symbols("PEPEUSDT")
    with pytest.raises(ExecutorError):
        parse_symbols(" , ")
