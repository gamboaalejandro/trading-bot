"""F02: the legacy backtester never falls back to synthetic data."""
import pytest
import requests
import responses

from apps.analytics import backtester as bt_mod
from apps.analytics.backtester import BacktestDataError, Backtester

URL = Backtester.BASE_URL


def _make():
    with pytest.warns(DeprecationWarning):
        return Backtester("SOL/USDT", timeframe="1h", limit=3)


def test_mock_generator_removed():
    assert not hasattr(Backtester, "_generate_mock_data")
    assert "DEPRECATED" in (bt_mod.__doc__ or "")


@pytest.mark.parametrize("status", [451, 403, 500])
@responses.activate
def test_http_errors_raise(status):
    responses.add(responses.GET, URL, status=status, json={"msg": "blocked"})
    bt = _make()
    with pytest.raises(BacktestDataError):
        bt.fetch_data()
    assert bt.df.empty


@responses.activate
def test_network_error_raises():
    responses.add(responses.GET, URL, body=requests.exceptions.ConnectionError("down"))
    with pytest.raises(BacktestDataError):
        _make().fetch_data()


@responses.activate
def test_empty_answer_raises():
    responses.add(responses.GET, URL, json=[])
    with pytest.raises(BacktestDataError):
        _make().fetch_data()


@responses.activate
def test_malformed_payload_raises():
    responses.add(responses.GET, URL, json=[[1, "x"]])
    with pytest.raises(BacktestDataError):
        _make().fetch_data()


@responses.activate
def test_run_without_data_raises_instead_of_simulating():
    responses.add(responses.GET, URL, status=451)
    bt = _make()
    with pytest.raises(BacktestDataError):
        bt.run_momentum()
    with pytest.raises(BacktestDataError):
        bt.run_mean_reversion()


@responses.activate
def test_valid_payload_is_parsed():
    row = lambda t, c: [t, str(c), str(c + 1), str(c - 1), str(c), "10", t + 1, "0", 1, "0", "0", "0"]
    responses.add(responses.GET, URL, json=[row(0, 10.0), row(3_600_000, 11.0), row(7_200_000, 12.0)])
    df = _make().fetch_data()
    assert list(df["close"]) == [10.0, 11.0, 12.0]
    q = responses.calls[0].request.url
    assert "symbol=SOLUSDT" in q and "interval=1h" in q
