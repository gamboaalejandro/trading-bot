"""F01 (websocket part): kline events are only usable when k.x is true."""
from core.binance_websocket import BinanceWebSocket


def _event(closed):
    return {"e": "kline", "s": "BTCUSDT", "k": {"t": 0, "T": 59_999, "c": "100.0", "v": "1", "x": closed}}


def test_forming_candle_is_ignored():
    assert BinanceWebSocket.closed_kline(_event(False)) is None


def test_closed_candle_is_returned():
    kline = BinanceWebSocket.closed_kline(_event(True))
    assert kline is not None and kline["c"] == "100.0"


def test_combined_stream_wrapper():
    wrapped = {"stream": "btcusdt@kline_1d", "data": _event(True)}
    assert BinanceWebSocket.closed_kline(wrapped)["T"] == 59_999
    assert BinanceWebSocket.closed_kline({"stream": "x", "data": _event(False)}) is None


def test_non_kline_and_malformed_events():
    assert BinanceWebSocket.closed_kline({"e": "24hrTicker", "c": "1"}) is None
    assert BinanceWebSocket.closed_kline({"e": "kline", "k": {"c": "1"}}) is None  # no x
    assert BinanceWebSocket.closed_kline({"e": "kline", "k": {"x": "true"}}) is None  # not a bool
    assert BinanceWebSocket.closed_kline(None) is None
