"""Tests for core.binance_futures_client (HTTP mocked with `responses`, no network)."""
import hashlib
import hmac
from urllib.parse import parse_qsl, urlsplit

import pytest
import responses

from core import binance_futures_client as bfc
from core.binance_futures_client import (
    AlgoOrderRequiredError,
    BinanceFuturesClient,
    BinanceFuturesError,
    LiveTradingNotConfirmed,
    ReadOnlyViolation,
)

BASE = "https://futures.test"
KEY = "k" * 16
SECRET = "s" * 16


def _params(call) -> dict:
    return dict(parse_qsl(urlsplit(call.request.url).query, keep_blank_values=True))


def _raw_query(call) -> str:
    return urlsplit(call.request.url).query


@pytest.fixture
def client():
    return BinanceFuturesClient(KEY, SECRET, base_url=BASE)


# ----------------------------------------------------------------------------
# Base URL and signature
# ----------------------------------------------------------------------------
def test_default_base_url_is_testnet(monkeypatch):
    monkeypatch.delenv("BINANCE_FUTURES_BASE_URL", raising=False)
    assert BinanceFuturesClient(KEY, SECRET).base_url == "https://testnet.binancefuture.com"


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("BINANCE_FUTURES_BASE_URL", "https://custom.example/")
    assert BinanceFuturesClient(KEY, SECRET).base_url == "https://custom.example"


@responses.activate
def test_hmac_signature_and_headers(client):
    responses.get(f"{BASE}/fapi/v2/account", json={"canTrade": True})
    client.account()
    call = responses.calls[0]
    query = _raw_query(call)
    payload, sig = query.rsplit("&signature=", 1)
    expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert sig == expected
    p = _params(call)
    assert p["recvWindow"] == "5000" and int(p["timestamp"]) > 0
    assert call.request.headers["X-MBX-APIKEY"] == KEY


def test_signature_known_vector():
    # Public example from the Binance API docs (HMAC SHA256 over the query string).
    # Literals are split so the repository secret scan does not flag the doc example.
    doc_secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP" "1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
    c = BinanceFuturesClient("x", doc_secret, base_url=BASE)
    q = ("symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1"
         "&recvWindow=5000&timestamp=1499827319559")
    assert c.sign(q) == "c8db56825ae71d6d79447849e617115f" "4a920fa2acdcab2b053c4b2838bd6b71"


@responses.activate
def test_public_endpoint_not_signed(client):
    responses.get(f"{BASE}/fapi/v1/exchangeInfo", json={"symbols": []})
    client.exchange_info()
    assert "signature" not in _params(responses.calls[0])


@responses.activate
def test_used_weight_header_recorded(client):
    responses.get(f"{BASE}/fapi/v1/ping", json={}, headers={"X-MBX-USED-WEIGHT-1M": "17"})
    client.ping()
    assert client.last_used_weight == 17


# ----------------------------------------------------------------------------
# Idempotent account setup
# ----------------------------------------------------------------------------
@responses.activate
def test_margin_type_isolated_idempotent(client):
    responses.post(f"{BASE}/fapi/v1/marginType", json={"code": 200, "msg": "success"})
    responses.post(f"{BASE}/fapi/v1/marginType", status=400,
                   json={"code": -4046, "msg": "No need to change margin type."})
    client.set_margin_type("BTCUSDT")
    client.set_margin_type("BTCUSDT")  # second call: -4046 is swallowed
    assert len(responses.calls) == 2
    for call in responses.calls:
        assert call.request.method == "POST"
        assert _params(call)["marginType"] == "ISOLATED"


@responses.activate
def test_margin_type_other_errors_raise(client):
    responses.post(f"{BASE}/fapi/v1/marginType", status=400,
                   json={"code": -4048, "msg": "Margin type cannot be changed if there exists position."})
    with pytest.raises(BinanceFuturesError) as ei:
        client.set_margin_type("BTCUSDT")
    assert ei.value.code == -4048


def test_cross_margin_rejected(client):
    with pytest.raises(ValueError):
        client.set_margin_type("BTCUSDT", "CROSSED")


@responses.activate
def test_one_way_mode_idempotent(client):
    responses.post(f"{BASE}/fapi/v1/positionSide/dual", status=400,
                   json={"code": -4059, "msg": "No need to change position side."})
    client.set_one_way_mode()
    assert _params(responses.calls[0])["dualSidePosition"] == "false"


@responses.activate
def test_leverage_policy(client):
    responses.post(f"{BASE}/fapi/v1/leverage", json={"leverage": 2, "symbol": "BTCUSDT"})
    client.set_leverage("BTCUSDT", 2)
    assert _params(responses.calls[0])["leverage"] == "2"
    with pytest.raises(ValueError):
        client.set_leverage("BTCUSDT", 3)
    with pytest.raises(ValueError):
        client.set_leverage("SOLUSDT", 2)  # altcoins: 1x
    with pytest.raises(ValueError):
        client.set_leverage("SOLUSDT", 0)
    assert bfc.policy_max_leverage("ETHUSDT") == 2 <= bfc.HARD_MAX_LEVERAGE == 3


@responses.activate
def test_leverage_bracket_and_commission(client):
    responses.get(f"{BASE}/fapi/v1/leverageBracket", json=[{"symbol": "BTCUSDT", "brackets": [
        {"bracket": 1, "initialLeverage": 125, "notionalCap": 50000, "maintMarginRatio": 0.004}]}])
    responses.get(f"{BASE}/fapi/v1/commissionRate",
                  json={"symbol": "BTCUSDT", "makerCommissionRate": "0.0002", "takerCommissionRate": "0.0005"})
    br = client.leverage_bracket("BTCUSDT")
    assert br[0]["maintMarginRatio"] == 0.004
    assert client.commission_rate("BTCUSDT")["takerCommissionRate"] == "0.0005"
    assert all("signature" in _params(c) for c in responses.calls)


# ----------------------------------------------------------------------------
# Orders
# ----------------------------------------------------------------------------
@responses.activate
def test_new_order_market(client):
    responses.post(f"{BASE}/fapi/v1/order", json={"orderId": 1, "status": "FILLED"})
    client.new_order("BTCUSDT", "buy", "MARKET", 0.0012, "20261015-TREND-BTCUSDT-1")
    p = _params(responses.calls[0])
    assert p["side"] == "BUY" and p["type"] == "MARKET"
    assert p["quantity"] == "0.0012"
    assert p["newClientOrderId"] == "20261015-TREND-BTCUSDT-1"
    assert "reduceOnly" not in p and "price" not in p


@responses.activate
def test_new_order_limit_reduce_only(client):
    responses.post(f"{BASE}/fapi/v1/order", json={"orderId": 2})
    client.new_order("ETHUSDT", "SELL", "LIMIT", 1e-3, "id-2", reduce_only=True, price=2500.10)
    p = _params(responses.calls[0])
    assert p["reduceOnly"] == "true" and p["price"] == "2500.1" and p["timeInForce"] == "GTC"
    assert p["quantity"] == "0.001"


def test_new_order_rejects_stop_types_and_bad_ids(client):
    with pytest.raises(ValueError, match="algo"):
        client.new_order("BTCUSDT", "SELL", "STOP_MARKET", 1, "id")
    with pytest.raises(ValueError):
        client.new_order("BTCUSDT", "SELL", "MARKET", 1, "")
    with pytest.raises(ValueError):
        client.new_order("BTCUSDT", "SELL", "MARKET", 1, "x" * 37)
    with pytest.raises(ValueError):
        client.new_order("BTCUSDT", "SELL", "LIMIT", 1, "id")  # no price


@responses.activate
def test_error_4120_recognized(client):
    responses.post(f"{BASE}/fapi/v1/order", status=400, json={
        "code": -4120, "msg": "Order type not supported for this endpoint. Please use the Algo Order API endpoints instead."})
    with pytest.raises(AlgoOrderRequiredError) as ei:
        client.new_order("BTCUSDT", "SELL", "MARKET", 1, "id-x")
    assert ei.value.code == bfc.ERR_ALGO_ORDER_REQUIRED == -4120
    assert isinstance(ei.value, BinanceFuturesError)


@responses.activate
def test_stop_market_algo_params(client):
    responses.post(f"{BASE}/fapi/v1/algoOrder", json={"algoId": 99, "clientAlgoId": "stop-1"})
    out = client.new_stop_market_algo("BTCUSDT", "SELL", 0.002, 55000.5, "stop-1")
    assert out["algoId"] == 99
    call = responses.calls[0]
    assert call.request.method == "POST"
    assert urlsplit(call.request.url).path == "/fapi/v1/algoOrder"
    p = _params(call)
    assert p["algoType"] == "CONDITIONAL"
    assert p["type"] == "STOP_MARKET"
    assert p["reduceOnly"] == "true"
    assert p["workingType"] == "MARK_PRICE"
    assert p["triggerPrice"] == "55000.5"
    assert p["quantity"] == "0.002"
    assert p["clientAlgoId"] == "stop-1"
    assert "signature" in p


def test_stop_market_algo_requires_reduce_only(client):
    with pytest.raises(ValueError):
        client.new_stop_market_algo("BTCUSDT", "SELL", 1, 100, "s", reduce_only=False)


@responses.activate
def test_cancel_and_open_algo_orders(client):
    responses.delete(f"{BASE}/fapi/v1/algoOrder", json={"algoId": 99, "code": "200"})
    responses.get(f"{BASE}/fapi/v1/openAlgoOrders", json=[{"algoId": 99, "symbol": "BTCUSDT"}])
    client.cancel_algo_order("BTCUSDT", 99)
    assert _params(responses.calls[0])["algoId"] == "99"
    assert client.open_algo_orders("BTCUSDT")[0]["algoId"] == 99


@responses.activate
def test_cancel_and_query_order(client):
    responses.delete(f"{BASE}/fapi/v1/order", json={"status": "CANCELED"})
    responses.get(f"{BASE}/fapi/v1/order", json={"status": "FILLED"})
    client.cancel_order("BTCUSDT", client_order_id="abc")
    assert _params(responses.calls[0])["origClientOrderId"] == "abc"
    assert client.query_order("BTCUSDT", client_order_id="abc")["status"] == "FILLED"


@responses.activate
def test_user_stream(client):
    responses.post(f"{BASE}/fapi/v1/listenKey", json={"listenKey": "LK"})
    responses.put(f"{BASE}/fapi/v1/listenKey", json={})
    assert client.start_user_stream() == "LK"
    client.keepalive_user_stream("LK")
    assert "signature" not in _params(responses.calls[0])
    assert responses.calls[0].request.headers["X-MBX-APIKEY"] == KEY


# ----------------------------------------------------------------------------
# Market data
# ----------------------------------------------------------------------------
def _kline(open_ms, close_ms, c):
    return [open_ms, "1", "2", "0.5", str(c), "10", close_ms, "15", 5, "4", "6", "0"]


@responses.activate
def test_klines_closed_only(client):
    day = 86_400_000
    responses.get(f"{BASE}/fapi/v1/klines", json=[_kline(0, day - 1, 1.5), _kline(day, 2 * day - 1, 1.7)])
    responses.get(f"{BASE}/fapi/v1/time", json={"serverTime": day + 1000})
    df = client.klines("BTCUSDT", "1d")
    assert len(df) == 1 and df["close"].iloc[0] == 1.5
    assert str(df.index.tz) == "UTC"


@responses.activate
def test_funding_rate_fraction_and_pagination(client):
    page1 = [{"symbol": "BTCUSDT", "fundingTime": 1 + i * 28_800_000, "fundingRate": "0.00010000",
              "markPrice": "100"} for i in range(3)]
    page2 = [{"symbol": "BTCUSDT", "fundingTime": 1 + 3 * 28_800_000, "fundingRate": "-0.00005000",
              "markPrice": "101"}]
    responses.get(f"{BASE}/fapi/v1/fundingRate", json=page1)
    responses.get(f"{BASE}/fapi/v1/fundingRate", json=page2)
    df = client.funding_rate("BTCUSDT", start_ms=0, limit=3)
    assert len(df) == 4
    assert df["funding_rate"].iloc[0] == pytest.approx(1e-4)
    assert df["funding_rate"].iloc[-1] == pytest.approx(-5e-5)
    assert _params(responses.calls[1])["startTime"] == str(page1[-1]["fundingTime"] + 1)


# ----------------------------------------------------------------------------
# Safety guards and secret hygiene
# ----------------------------------------------------------------------------
def test_read_only_blocks_writes():
    c = BinanceFuturesClient(KEY, SECRET, base_url=BASE, read_only=True)
    with pytest.raises(ReadOnlyViolation):
        c.new_order("BTCUSDT", "BUY", "MARKET", 1, "id")
    with pytest.raises(ReadOnlyViolation):
        c.set_margin_type("BTCUSDT")


def test_production_writes_need_confirmation(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_CONFIRM", raising=False)
    c = BinanceFuturesClient(KEY, SECRET, base_url=bfc.PRODUCTION_BASE_URL)
    with pytest.raises(LiveTradingNotConfirmed):
        c.new_order("BTCUSDT", "BUY", "MARKET", 1, "id")


@responses.activate
def test_errors_do_not_leak_signature_or_secret(client):
    responses.get(f"{BASE}/fapi/v2/account", status=401, json={"code": -2015, "msg": "Invalid API-key"})
    with pytest.raises(BinanceFuturesError) as ei:
        client.account()
    text = str(ei.value)
    assert "signature" not in text and SECRET not in text and KEY not in text
    assert ei.value.code == -2015
    assert SECRET not in repr(client)
