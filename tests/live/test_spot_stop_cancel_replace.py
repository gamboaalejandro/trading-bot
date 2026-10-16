"""F03: spot stop moved with POST /api/v3/order/cancelReplace (STOP_ON_FAILURE).

All HTTP is mocked with ``responses``; a tiny simulated exchange tracks the
open stop orders so the time a position spends without an exchange stop can
be measured.
"""
import asyncio
import time
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest
import requests
import responses

import apps.executor.multi_symbol_engine as engine_mod
from apps.executor.testnet_connector import TestnetConnector as SpotConnector
from core.binance_client import BinanceClient, CancelReplaceError

BASE = "https://spot.test"
CR_URL = f"{BASE}/api/v3/order/cancelReplace"
ORDER_URL = f"{BASE}/api/v3/order"
OPEN_ORDERS_URL = f"{BASE}/api/v3/openOrders"
ACCOUNT_URL = f"{BASE}/api/v3/account"
EXCHANGE_INFO_URL = f"{BASE}/api/v3/exchangeInfo"
EXCHANGE_INFO = {"symbols": [{"symbol": "SOLUSDT", "filters": [
    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
    {"filterType": "LOT_SIZE", "stepSize": "0.001"},
]}]}


def _query(request) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}


def _json(status, body):
    import json
    return status, {}, json.dumps(body)


def _cr_failure(cancel_ok: bool, new_ok: bool = False):
    """Binance error bodies for cancelReplace (-2021 partial, -2022 failed)."""
    if cancel_ok:
        return {"code": -2021, "msg": "Order cancel-replace partially failed.", "data": {
            "cancelResult": "SUCCESS", "newOrderResult": "FAILURE",
            "cancelResponse": {"orderId": 11, "status": "CANCELED"},
            "newOrderResponse": {"code": -2010, "msg": "Stop price would trigger immediately."}}}
    return {"code": -2022, "msg": "Order cancel-replace failed.", "data": {
        "cancelResult": "FAILURE", "newOrderResult": "NOT_ATTEMPTED",
        "cancelResponse": {"code": -2011, "msg": "Unknown order sent."} if new_ok else
                          {"code": -1003, "msg": "Too many requests."},
        "newOrderResponse": None}}


class SimExchange:
    """Spot exchange holding stop orders; records naked (no stop) intervals."""

    def __init__(self, rsps, script_cr=(), script_order=()):
        self.stops = {11: 100.0}
        self.next_id = 12
        self.script_cr = list(script_cr)        # per call: 'ok' | 'cancel_fail' | 'partial' | 'unknown' | 'unknown_done'
        self.script_order = list(script_order)  # per call: 'ok' | 'fail'
        self.cr_calls = []
        self.order_calls = []
        self.delete_calls = 0
        self.naked_since = None
        self.max_naked = 0.0
        # Closed orders queryable with GET /api/v3/order, and the SOL wallet
        self.history = {}           # orderId -> order body (status, executedQty...)
        self.held_free = 0.0
        self.held_locked = 2.0      # the 2.0 SOL position, locked by stop 11
        self.open_orders_failures = 0
        self.order_queries = []
        rsps.add(responses.GET, EXCHANGE_INFO_URL, json=EXCHANGE_INFO)
        rsps.add_callback(responses.POST, CR_URL, callback=self._cancel_replace)
        rsps.add_callback(responses.POST, ORDER_URL, callback=self._new_order)
        rsps.add_callback(responses.DELETE, ORDER_URL, callback=self._delete)
        rsps.add_callback(responses.GET, ORDER_URL, callback=self._query_order)
        rsps.add_callback(responses.GET, OPEN_ORDERS_URL, callback=self._open_orders)
        rsps.add_callback(responses.GET, ACCOUNT_URL, callback=self._account)

    def stop_filled(self, oid=11, price=99.5, qty=2.0):
        """The stop triggered between two monitor ticks and sold the position."""
        del self.stops[oid]
        self.history[oid] = {
            "orderId": oid, "status": "FILLED", "type": "STOP_LOSS", "side": "SELL",
            "stopPrice": "100.00", "executedQty": f"{qty}", "cummulativeQuoteQty": f"{qty * price}",
        }
        self.held_free, self.held_locked = 0.0, 0.0

    def stop_expired(self, oid=11):
        """The stop vanished unfilled (e.g. expired): the coins are free again."""
        del self.stops[oid]
        self.history[oid] = {
            "orderId": oid, "status": "EXPIRED", "type": "STOP_LOSS", "side": "SELL",
            "stopPrice": "100.00", "executedQty": "0", "cummulativeQuoteQty": "0",
        }
        self.held_free, self.held_locked = self.held_locked, 0.0

    def _mark(self):
        now = time.monotonic()
        if not self.stops and self.naked_since is None:
            self.naked_since = now
        elif self.stops and self.naked_since is not None:
            self.max_naked = max(self.max_naked, now - self.naked_since)
            self.naked_since = None

    def _add_stop(self, price):
        oid = self.next_id
        self.next_id += 1
        self.stops[oid] = price
        return oid

    def _cancel_replace(self, request):
        q = _query(request)
        self.cr_calls.append(q)
        action = self.script_cr.pop(0) if self.script_cr else "ok"
        old = int(q["cancelOrderId"])
        if action == "cancel_fail":
            return _json(400, _cr_failure(cancel_ok=False))
        if action == "unknown":  # nothing applied, answer lost
            return _json(503, {"code": -1007, "msg": "Timeout waiting for response from backend server."})
        if old not in self.stops:
            return _json(400, _cr_failure(cancel_ok=False, new_ok=True))
        if action == "partial":
            del self.stops[old]
            self._mark()
            return _json(400, _cr_failure(cancel_ok=True))
        del self.stops[old]
        new_id = self._add_stop(float(q["stopPrice"]))
        self._mark()
        if action == "unknown_done":
            return _json(503, {"code": -1007, "msg": "Timeout; execution status unknown."})
        return _json(200, {
            "cancelResult": "SUCCESS", "newOrderResult": "SUCCESS",
            "cancelResponse": {"orderId": old, "status": "CANCELED"},
            "newOrderResponse": {"orderId": new_id, "type": "STOP_LOSS", "stopPrice": q["stopPrice"]},
        })

    def _new_order(self, request):
        q = _query(request)
        self.order_calls.append(q)
        action = self.script_order.pop(0) if self.script_order else "ok"
        if action == "fail":
            return _json(400, {"code": -2010, "msg": "Account has insufficient balance."})
        oid = self._add_stop(float(q["stopPrice"]))
        self._mark()
        return _json(200, {"orderId": oid, "status": "NEW", "type": q["type"]})

    def _delete(self, request):
        self.delete_calls += 1
        return _json(200, {})

    def _query_order(self, request):
        oid = int(_query(request)["orderId"])
        self.order_queries.append(oid)
        if oid in self.stops:
            return _json(200, {"orderId": oid, "status": "NEW", "type": "STOP_LOSS",
                               "stopPrice": f"{self.stops[oid]:.2f}", "executedQty": "0"})
        if oid in self.history:
            return _json(200, self.history[oid])
        return _json(400, {"code": -2013, "msg": "Order does not exist."})

    def _account(self, request):
        return _json(200, {"balances": [
            {"asset": "SOL", "free": f"{self.held_free}", "locked": f"{self.held_locked}"},
            {"asset": "USDT", "free": "1000", "locked": "0"},
        ]})

    def _open_orders(self, request):
        if self.open_orders_failures > 0:
            self.open_orders_failures -= 1
            return _json(503, {"code": -1001, "msg": "Internal error; unable to process your request."})
        return _json(200, [
            {"orderId": oid, "side": "SELL", "type": "STOP_LOSS", "stopPrice": f"{p:.2f}"}
            for oid, p in self.stops.items()
        ])


# ---------------------------------------------------------------- client


@pytest.fixture
def client():
    c = BinanceClient("key", "secret")
    c.base_url = BASE
    return c


@responses.activate
def test_client_sends_cancel_replace_with_stop_on_failure(client):
    responses.add(responses.POST, CR_URL, json={
        "cancelResult": "SUCCESS", "newOrderResult": "SUCCESS",
        "cancelResponse": {"orderId": 11}, "newOrderResponse": {"orderId": 12},
    })
    result = client.cancel_replace_order("SOLUSDT", 11, "sell", "STOP_LOSS", 1.5, stop_price=101.5)
    assert result["newOrderResponse"]["orderId"] == 12
    q = _query(responses.calls[0].request)
    assert q["cancelReplaceMode"] == "STOP_ON_FAILURE"
    assert q["cancelOrderId"] == "11"
    assert q["type"] == "STOP_LOSS" and q["side"] == "SELL"
    assert q["stopPrice"] == "101.5" and q["quantity"] == "1.5"
    assert "signature" in q and "timestamp" in q
    assert responses.calls[0].request.headers["X-MBX-APIKEY"] == "key"


@responses.activate
def test_client_cancel_failure_means_old_order_intact(client):
    responses.add(responses.POST, CR_URL, status=400, json=_cr_failure(cancel_ok=False))
    with pytest.raises(CancelReplaceError) as exc:
        client.cancel_replace_order("SOLUSDT", 11, "SELL", "STOP_LOSS", 1.0, stop_price=101.0)
    err = exc.value
    assert err.code == -2022
    assert err.cancel_result == "FAILURE" and err.new_order_result == "NOT_ATTEMPTED"
    assert not err.cancel_succeeded and not err.outcome_unknown


@responses.activate
def test_client_partial_failure_flags_unprotected(client):
    responses.add(responses.POST, CR_URL, status=400, json=_cr_failure(cancel_ok=True))
    with pytest.raises(CancelReplaceError) as exc:
        client.cancel_replace_order("SOLUSDT", 11, "SELL", "STOP_LOSS", 1.0, stop_price=101.0)
    assert exc.value.code == -2021
    assert exc.value.cancel_succeeded


@responses.activate
def test_client_unknown_order_code_exposed(client):
    responses.add(responses.POST, CR_URL, status=400, json=_cr_failure(cancel_ok=False, new_ok=True))
    with pytest.raises(CancelReplaceError) as exc:
        client.cancel_replace_order("SOLUSDT", 11, "SELL", "STOP_LOSS", 1.0, stop_price=101.0)
    assert exc.value.cancel_error_code == -2011


@responses.activate
def test_client_5xx_and_network_errors_are_unknown_outcome(client):
    responses.add(responses.POST, CR_URL, status=503, json={"code": -1007, "msg": "timeout"})
    responses.add(responses.POST, CR_URL, body=requests.exceptions.ConnectionError("reset"))
    for _ in range(2):
        with pytest.raises(CancelReplaceError) as exc:
            client.cancel_replace_order("SOLUSDT", 11, "SELL", "STOP_LOSS", 1.0, stop_price=101.0)
        assert exc.value.outcome_unknown
        assert not exc.value.cancel_succeeded


@responses.activate
def test_client_get_order_queries_by_id(client):
    responses.add(responses.GET, ORDER_URL, json={"orderId": 11, "status": "FILLED"})
    assert client.get_order("SOLUSDT", 11)["status"] == "FILLED"
    q = _query(responses.calls[0].request)
    assert q["symbol"] == "SOLUSDT" and q["orderId"] == "11"
    assert "signature" in q


@responses.activate
def test_client_requires_stop_price(client):
    with pytest.raises(ValueError):
        client.cancel_replace_order("SOLUSDT", 11, "SELL", "STOP_LOSS", 1.0)
    assert len(responses.calls) == 0


# ---------------------------------------------------------------- engine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_mod, "STATE_FILE", str(tmp_path / "positions.json"))
    monkeypatch.setattr(
        "apps.ingestion.sentiment.SentimentAnalyzer.get_sentiment_multiplier", lambda self: 1.0
    )
    eng = engine_mod.MultiSymbolEngine(symbols=["SOL/USDT"], dry_run=False)
    connector = SpotConnector(use_testnet=True)
    connector.client.base_url = BASE
    connector._initialized = True
    eng.connector = connector
    eng.stop_retry_delays = (0.01, 0.01, 0.01)
    closes = np.linspace(90, 100, 300)
    eng.latest_candles["SOL/USDT"] = pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.5, "close": closes, "volume": 1.0}
    )
    eng.open_positions["SOL/USDT"] = {
        "side": "buy", "entry_price": 100.0, "quantity": 2.0, "stop_loss": 103.0,
        "take_profit": 130.0, "order_id": 1, "timestamp": "2026-10-15T00:00:00",
        "stop_order_id": 11,
    }
    yield eng
    # An open ZMQ socket makes Context.term() block at interpreter exit
    eng.zmq_socket.close(linger=0)
    eng.zmq_context.term()


def _move(engine):
    asyncio.run(engine._move_exchange_stop("SOL/USDT"))
    return engine.open_positions["SOL/USDT"]


@responses.activate
def test_move_uses_cancel_replace_and_never_naked(engine):
    ex = SimExchange(responses)
    position = _move(engine)
    assert len(ex.cr_calls) == 1
    assert ex.cr_calls[0]["cancelReplaceMode"] == "STOP_ON_FAILURE"
    assert ex.cr_calls[0]["stopPrice"] == "103.0"
    assert position["stop_order_id"] == 12
    assert ex.stops == {12: 103.0}
    assert ex.delete_calls == 0  # never a bare cancel
    assert ex.max_naked == 0.0 and ex.naked_since is None
    assert engine.alerts == []


@responses.activate
def test_cancel_failure_keeps_old_stop_and_retries(engine):
    ex = SimExchange(responses, script_cr=["cancel_fail", "cancel_fail", "ok"])
    position = _move(engine)
    assert len(ex.cr_calls) == 3
    assert position["stop_order_id"] == 12
    assert ex.stops == {12: 103.0}
    assert ex.max_naked == 0.0
    assert engine.alerts == []


@responses.activate
def test_persistent_cancel_failure_alerts_and_keeps_old_stop(engine):
    ex = SimExchange(responses, script_cr=["cancel_fail"] * 10)
    position = _move(engine)
    assert len(ex.cr_calls) == 1 + len(engine.stop_retry_delays)
    assert position["stop_order_id"] == 11  # previous stop still protects
    assert ex.stops == {11: 100.0}
    assert len(engine.alerts) == 1
    assert "could not move exchange stop" in engine.alerts[0]["message"]


@responses.activate
def test_partial_failure_rearms_within_bound_with_default_delays(engine):
    engine.stop_retry_delays = engine_mod.STOP_RETRY_DELAYS
    assert sum(engine_mod.STOP_RETRY_DELAYS) < engine_mod.MAX_UNPROTECTED_SECONDS
    ex = SimExchange(responses, script_cr=["partial"], script_order=["fail", "ok"])
    position = _move(engine)
    assert position["stop_order_id"] in ex.stops
    assert list(ex.stops.values()) == [103.0]
    assert len(ex.order_calls) == 2
    assert ex.order_calls[-1]["type"] == "STOP_LOSS"
    assert ex.naked_since is None
    assert 0.0 < ex.max_naked < engine_mod.MAX_UNPROTECTED_SECONDS
    assert any("unprotected" in a["message"] for a in engine.alerts)


def _assert_closed_by_exchange_stop(engine, ex, expected_pnl):
    assert "SOL/USDT" not in engine.open_positions
    assert ex.order_calls == []          # no stop re-placed for coins no longer held
    assert ex.stops == {}
    assert engine.daily_realized_pnl == pytest.approx(expected_pnl)
    with open(engine_mod.STATE_FILE) as f:
        assert "SOL/USDT" not in f.read()


@responses.activate
def test_unknown_order_filled_stop_closes_position(engine):
    # A >3% wick between two monitor ticks: stop 11 triggered and FILLED
    ex = SimExchange(responses)
    ex.stop_filled(price=99.5)
    asyncio.run(engine._move_exchange_stop("SOL/USDT"))
    assert ex.cr_calls and ex.order_queries == [11]
    _assert_closed_by_exchange_stop(engine, ex, (99.5 - 100.0) * 2.0)


@responses.activate
def test_unknown_order_without_balance_closes_position(engine):
    # Order history unavailable (-2013) but the coins are gone: closed by the stop
    ex = SimExchange(responses)
    ex.stops = {}
    ex.held_free = ex.held_locked = 0.0
    asyncio.run(engine._move_exchange_stop("SOL/USDT"))
    _assert_closed_by_exchange_stop(engine, ex, (103.0 - 100.0) * 2.0)


@responses.activate
def test_unknown_order_expired_with_coins_places_fresh_stop(engine):
    ex = SimExchange(responses)
    ex.stop_expired()  # vanished unfilled, quantity still held
    position = _move(engine)
    assert ex.order_queries == [11]
    assert position["stop_order_id"] in ex.stops
    assert list(ex.stops.values()) == [103.0]
    assert any("unprotected" in a["message"] for a in engine.alerts)


@responses.activate
def test_unknown_order_unverifiable_is_not_replaced_until_verified(engine):
    ex = SimExchange(responses)
    ex.stops = {}  # gone, no order history (-2013), coins still held
    ex.held_free, ex.held_locked = 2.0, 0.0
    position = _move(engine)
    assert ex.order_calls == []
    assert position["stop_order_id"] is None
    assert position["unverified_stop_id"] == 11
    assert any("fate is unknown" in a["message"] for a in engine.alerts)

    # The monitor re-checks instead of blindly re-placing; now the order is visible
    ex.history[11] = {"orderId": 11, "status": "CANCELED", "executedQty": "0"}
    asyncio.run(engine._rearm_stop_if_due("SOL/USDT"))
    assert position["stop_order_id"] in ex.stops
    assert "unverified_stop_id" not in position
    assert list(ex.stops.values()) == [103.0]


@responses.activate
def test_unknown_outcome_with_filled_stop_closes_position(engine):
    ex = SimExchange(responses, script_cr=["unknown"])
    ex.stop_filled(price=99.0)
    asyncio.run(engine._move_exchange_stop("SOL/USDT"))
    assert len(ex.cr_calls) == 1
    _assert_closed_by_exchange_stop(engine, ex, (99.0 - 100.0) * 2.0)


@responses.activate
def test_open_orders_failure_on_unknown_outcome_retries(engine):
    # Listing failed is not 'no stop': retry the move, never place a duplicate
    ex = SimExchange(responses, script_cr=["unknown", "ok"])
    ex.open_orders_failures = 1
    position = _move(engine)
    assert len(ex.cr_calls) == 2
    assert ex.order_calls == [] and ex.order_queries == []
    assert position["stop_order_id"] == 12
    assert ex.stops == {12: 103.0}
    assert engine.alerts == []


@responses.activate
def test_open_orders_failure_on_unknown_order_waits_then_closes(engine):
    ex = SimExchange(responses)
    ex.stop_filled()
    ex.open_orders_failures = 1
    position = _move(engine)
    assert ex.order_calls == []
    assert position["stop_order_id"] is None and position["unverified_stop_id"] == 11
    # Next monitor check: listing works, the FILLED stop closes the position
    asyncio.run(engine._rearm_stop_if_due("SOL/USDT"))
    _assert_closed_by_exchange_stop(engine, ex, (99.5 - 100.0) * 2.0)


@responses.activate
def test_place_stop_skips_attempt_when_listing_fails(engine):
    ex = SimExchange(responses, script_order=["fail", "ok"])
    ex.stops = {}
    ex.open_orders_failures = 1
    order_id = asyncio.run(engine._place_exchange_stop("SOL/USDT", 2.0, 103.0))
    # attempt 1 fails, attempt 2 cannot verify -> skipped, attempt 3 places
    assert len(ex.order_calls) == 2
    assert order_id in ex.stops and len(ex.stops) == 1


@responses.activate
def test_unknown_outcome_reconciles_with_open_orders(engine):
    ex = SimExchange(responses, script_cr=["unknown_done"])
    position = _move(engine)
    # The replace went through: adopt it, no duplicate stop, no extra call
    assert len(ex.cr_calls) == 1
    assert ex.order_calls == []
    assert position["stop_order_id"] == 12
    assert ex.stops == {12: 103.0}


@responses.activate
def test_unknown_outcome_not_applied_is_retried(engine):
    ex = SimExchange(responses, script_cr=["unknown", "ok"])
    position = _move(engine)
    assert len(ex.cr_calls) == 2
    assert position["stop_order_id"] == 12
    assert ex.stops == {12: 103.0}


@responses.activate
def test_unprotected_position_is_rearmed_by_monitor(engine):
    ex = SimExchange(responses, script_cr=["partial"], script_order=["fail"] * 4)
    position = _move(engine)
    assert position["stop_order_id"] is None
    assert ex.stops == {}
    assert any("WITHOUT exchange stop" in a["message"] for a in engine.alerts)

    # The exchange recovers: the monitor's re-arm places the stop
    asyncio.run(engine._rearm_stop_if_due("SOL/USDT"))
    assert position["stop_order_id"] in ex.stops
    assert ex.naked_since is None
    # Throttled: no second attempt inside the interval
    calls = len(ex.order_calls)
    position["stop_order_id"] = None
    asyncio.run(engine._rearm_stop_if_due("SOL/USDT"))
    assert len(ex.order_calls) == calls


@responses.activate
def test_dry_run_never_touches_exchange(engine):
    engine.dry_run = True
    _move(engine)
    assert len(responses.calls) == 0
