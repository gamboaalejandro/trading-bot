"""Tests for apps/live/reconciliation.py (PLAN.md §6.2 L02, §7.7). No network."""
from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import pytest
import responses

from apps.live.reconciliation import (
    ExchangePosition,
    FuturesVenue,
    LiveState,
    LocalPosition,
    Reconciler,
    ReconciliationError,
    SpotVenue,
    StopOrder,
    klines_frame,
    parse_symbol_filters,
)
from core.binance_futures_client import BinanceFuturesClient

from .exchange_mock import NOW, MockExchange, fixture_data

SYMS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


@pytest.fixture
def exchange():
    ex = MockExchange("spot", fixture_data(), cash=1_000.0, symbols=SYMS)
    ex.set_marks({"BTCUSDT": 100_000.0, "ETHUSDT": 4_000.0, "SOLUSDT": 150.0})
    return ex


def _hold(ex: MockExchange, symbol: str, qty: float) -> None:
    ex.book["positions"][symbol] = qty


def test_position_without_stop_places_it_with_local_price(exchange):
    _hold(exchange, "BTCUSDT", 0.003)
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.003, stop_price=90_000.123))
    rep = Reconciler({"spot": exchange}, state).run_once(NOW)
    placed = rep.of_kind("place_stop")
    assert len(placed) == 1 and placed[0].executed
    stops = exchange.open_stops()
    assert len(stops) == 1
    st = stops[0]
    assert st.side == "SELL" and st.qty == pytest.approx(0.003) and st.stop_price == pytest.approx(90_000.12)
    assert st.client_id == "202610150005-REC-BTCUSDT"
    assert state.get("spot", "BTCUSDT").stop_client_id == st.client_id


def test_position_without_stop_uses_stop_price_fn_or_alerts(exchange):
    _hold(exchange, "BTCUSDT", 0.003)
    alerts = []
    rep = Reconciler({"spot": exchange}, LiveState(), alert=alerts.append,
                     stop_price_fn=lambda m, s, side: 95_000.0).run_once(NOW)
    assert exchange.open_stops()[0].stop_price == pytest.approx(95_000.0)
    assert rep.of_kind("divergence")          # the local state did not know the position
    # Without any stop price: alert, nothing placed.
    ex2 = MockExchange("spot", fixture_data(), cash=0.0, symbols=SYMS)
    ex2.set_marks({"SOLUSDT": 150.0})
    _hold(ex2, "SOLUSDT", 2.0)
    alerts.clear()
    rep2 = Reconciler({"spot": ex2}, LiveState(), alert=alerts.append).run_once(NOW)
    assert not ex2.open_stops()
    assert any("WITHOUT stop" in a.detail for a in rep2.of_kind("alert"))
    assert any("WITHOUT stop" in a for a in alerts)


def test_orphan_stop_is_cancelled(exchange):
    st = exchange.place_stop("ETHUSDT", "SELL", 0.5, 3_000.0, "old-stop")
    state = LiveState()
    rep = Reconciler({"spot": exchange}, state).run_once(NOW)
    assert [a.kind for a in rep.actions] == ["cancel_stop"]
    assert ("cancel_stop", "ETHUSDT", st.order_id) in exchange.calls
    assert exchange.open_stops() == []


def test_wrong_side_and_duplicate_stops_are_cancelled(exchange):
    _hold(exchange, "BTCUSDT", 0.003)
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.003, 90_000.0, "keep-me"))
    exchange.place_stop("BTCUSDT", "SELL", 0.003, 90_000.0, "keep-me")
    exchange.place_stop("BTCUSDT", "SELL", 0.003, 80_000.0, "dupe")
    exchange.place_stop("BTCUSDT", "BUY", 0.003, 120_000.0, "wrong-side")
    rep = Reconciler({"spot": exchange}, state).run_once(NOW)
    cancelled = {a.detail.split(":")[0] for a in rep.of_kind("cancel_stop")}
    assert cancelled == {"orphan stop (wrong side)", "duplicate stop"}
    assert [s.client_id for s in exchange.open_stops()] == ["keep-me"]
    assert rep.ok


def test_divergence_alerts_and_adopts_exchange_qty(exchange):
    _hold(exchange, "BTCUSDT", 0.005)
    exchange.place_stop("BTCUSDT", "SELL", 0.003, 90_000.0, "s1")
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.003, 90_000.0, "s1"))
    alerts = []
    rep = Reconciler({"spot": exchange}, state, alert=alerts.append).run_once(NOW)
    assert rep.of_kind("divergence") and not rep.ok
    assert any("0.003" in a and "0.005" in a for a in alerts)
    assert state.get("spot", "BTCUSDT").qty == pytest.approx(0.005)
    # The stop no longer covers the position: replaced with the full quantity.
    assert rep.of_kind("replace_stop")
    (st,) = exchange.open_stops()
    assert st.qty == pytest.approx(0.005) and st.stop_price == pytest.approx(90_000.0)


def test_closed_externally_locks_symbol(exchange):
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.003, 90_000.0, "s1"))
    rep = Reconciler({"spot": exchange}, state).run_once(NOW)
    assert rep.of_kind("closed_externally")
    assert state.locks == {"BTCUSDT": 1}
    assert state.get("spot", "BTCUSDT") is None


def test_dust_balance_is_ignored(exchange):
    _hold(exchange, "SOLUSDT", 0.01)        # 1.5 USDT < minNotional 5
    rep = Reconciler({"spot": exchange}, LiveState()).run_once(NOW)
    assert rep.actions == [] and exchange.writes() == []


def test_audit_mode_does_not_act(exchange):
    _hold(exchange, "BTCUSDT", 0.003)
    exchange.place_stop("ETHUSDT", "SELL", 0.5, 3_000.0, "orphan")
    exchange.calls.clear()
    state = LiveState()
    state.put(LocalPosition("BTCUSDT", "spot", 0.003, 90_000.0))
    rep = Reconciler({"spot": exchange}, state, act=False).run_once(NOW)
    assert {a.kind for a in rep.actions} == {"place_stop", "cancel_stop"}
    assert not any(a.executed for a in rep.actions)
    assert exchange.writes() == []


def test_failed_listing_alerts_instead_of_crashing(exchange):
    def boom(marks=None):
        raise RuntimeError("timeout")
    exchange.positions = boom
    alerts = []
    rep = Reconciler({"spot": exchange}, LiveState(), alert=alerts.append).run_once(NOW)
    assert rep.of_kind("alert") and "timeout" in alerts[0]


def test_state_roundtrip_and_corruption(tmp_path):
    p = tmp_path / "state.json"
    st = LiveState.load(p)
    st.put(LocalPosition("BTCUSDT", "spot", 0.1, 1.0, "c", "o"))
    st.locks["SOLUSDT"] = 1
    st.save()
    again = LiveState.load(p)
    assert again.get("spot", "BTCUSDT").stop_client_id == "c" and again.locks == {"SOLUSDT": 1}
    p.write_text("{not json")
    with pytest.raises(ReconciliationError):
        LiveState.load(p)


# --- filters -----------------------------------------------------------------

def test_parse_filters_spot_and_futures():
    spot = {"symbol": "BTCUSDT", "filters": [
        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
        {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "9000"},
        {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.00000000", "minQty": "0", "maxQty": "100"},
        {"filterType": "NOTIONAL", "minNotional": "5.00"}]}
    f = parse_symbol_filters(spot, "spot")
    assert f.step_size == Decimal("0.00001") and f.min_notional == Decimal("5.00")
    assert f.round_qty(0.0029999) == pytest.approx(0.00299)        # always DOWN
    assert f.round_qty(-0.0029999) == pytest.approx(-0.00299)
    assert f.round_price(90_000.129, "down") == pytest.approx(90_000.12)
    assert f.round_price(90_000.121, "up") == pytest.approx(90_000.13)
    assert f.check(0.00004, 100_000) == "below_min_notional"
    assert f.check(0.000001, 100_000) == "below_min_qty"
    assert f.check(0.001, 100_000) is None
    fut = {"symbol": "SOLUSDT", "filters": [
        {"filterType": "PRICE_FILTER", "tickSize": "0.0100"},
        {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "1000000"},
        {"filterType": "MARKET_LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "5000"},
        {"filterType": "MIN_NOTIONAL", "notional": "5"}]}
    g = parse_symbol_filters(fut, "futures")
    assert g.round_qty(7.9) == 7.0 and g.min_notional == Decimal("5") and g.max_qty == Decimal("5000")
    with pytest.raises(ReconciliationError):
        parse_symbol_filters({"symbol": "X", "filters": [fut["filters"][0], fut["filters"][1]]}, "futures")


def test_klines_frame_drops_unclosed_rows_and_masks_zero_volume():
    rows = [
        [0, "1", "2", "0.5", "1.5", "10", 86_399_999, "15", 1, "0", "0", "0"],
        [86_400_000, "1.5", "2", "1", "1.8", "0", 172_799_999, "0", 0, "0", "0", "0"],
        [172_800_000, "1.8", "2", "1", "1.9", "5", 259_199_999, "9", 1, "0", "0", "0"],
    ]
    df = klines_frame(rows, server_time_ms=259_199_999)      # third bar still open (closeTime >= now)
    assert len(df) == 2
    assert df["close"].isna().iloc[1] and df["close"].iloc[0] == 1.5
    assert str(df.index[0]) == "1970-01-01 00:00:00+00:00"


# --- real adapters with mocked HTTP --------------------------------------------

FBASE = "https://futures.test"


def _q(call) -> dict:
    return dict(parse_qsl(urlsplit(call.request.url).query, keep_blank_values=True))


FUT_INFO = {"symbols": [{"symbol": "SOLUSDT", "filters": [
    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
    {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "1000000"},
    {"filterType": "MARKET_LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "5000"},
    {"filterType": "MIN_NOTIONAL", "notional": "5"}]}]}


@responses.activate
def test_futures_reconciliation_places_algo_stop_and_cancels_orphan():
    client = BinanceFuturesClient("k" * 16, "s" * 16, base_url=FBASE)
    venue = FuturesVenue(client, ("SOLUSDT", "ADAUSDT"))
    responses.get(f"{FBASE}/fapi/v1/exchangeInfo", json=FUT_INFO)
    responses.get(f"{FBASE}/fapi/v2/positionRisk", json=[
        {"symbol": "SOLUSDT", "positionAmt": "-10", "entryPrice": "150", "leverage": "1"},
        {"symbol": "ADAUSDT", "positionAmt": "0", "entryPrice": "0", "leverage": "1"},
    ])
    responses.get(f"{FBASE}/fapi/v1/openAlgoOrders", json=[
        {"algoId": 77, "clientAlgoId": "orphan", "symbol": "ADAUSDT", "side": "SELL",
         "orderType": "STOP_MARKET", "quantity": "100", "triggerPrice": "0.3"},
    ])
    responses.post(f"{FBASE}/fapi/v1/algoOrder", json={"algoId": 99, "clientAlgoId": "x"})
    responses.delete(f"{FBASE}/fapi/v1/algoOrder", json={"algoId": 77})
    state = LiveState()
    state.put(LocalPosition("SOLUSDT", "futures", -10.0, stop_price=180.004))
    rep = Reconciler({"futures": venue}, state).run_once(NOW, marks={"futures": {"SOLUSDT": 150.0}})
    assert {a.kind for a in rep.actions} == {"place_stop", "cancel_stop"}
    post = [c for c in responses.calls if c.request.method == "POST"][0]
    p = _q(post)
    assert p["side"] == "BUY" and p["type"] == "STOP_MARKET" and p["reduceOnly"] == "true"
    assert p["workingType"] == "MARK_PRICE" and p["triggerPrice"] == "180.01"   # short stop rounded UP
    assert p["quantity"] == "10" and p["clientAlgoId"] == "202610150005-REC-SOLUSDT"
    delete = [c for c in responses.calls if c.request.method == "DELETE"][0]
    assert _q(delete)["algoId"] == "77"


class _SpotClientStub:
    """Minimal BinanceClient stand-in for SpotVenue unit tests."""

    def __init__(self, balances, orders):
        self.balances = balances
        self.orders = orders

    def get_account(self):
        return {"balances": [{"asset": a, "free": str(f), "locked": str(l)} for a, (f, l) in self.balances.items()]}

    def get_open_orders(self, symbol=None):
        return self.orders


def test_spot_venue_positions_and_stops_parsing():
    stub = _SpotClientStub({"USDT": (100, 0), "BTC": (0.001, 0.002), "XYZ": (5, 0)}, [
        {"symbol": "BTCUSDT", "type": "STOP_LOSS", "side": "SELL", "origQty": "0.002",
         "executedQty": "0", "stopPrice": "90000", "orderId": 5, "clientOrderId": "c5"},
        {"symbol": "BTCUSDT", "type": "LIMIT", "side": "SELL", "origQty": "1", "executedQty": "0",
         "orderId": 6, "clientOrderId": "c6"},
    ])
    v = SpotVenue(stub, ("BTCUSDT", "ETHUSDT"))
    pos = v.positions()
    assert list(pos) == ["BTCUSDT"] and isinstance(pos["BTCUSDT"], ExchangePosition)
    assert pos["BTCUSDT"].qty == pytest.approx(0.003) and pos["BTCUSDT"].market == "spot"
    assert v.equity({"BTCUSDT": 100_000.0}) == pytest.approx(400.0)
    (st,) = v.open_stops()
    assert (st.order_id, st.client_id, st.qty, st.stop_price) == ("5", "c5", 0.002, 90_000.0)
