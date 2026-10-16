"""Tests for scripts/check_connection.py and scripts/fetch_official_audit_data.py (mocked HTTP)."""
import json
from pathlib import Path

import pandas as pd
import pytest
import responses

from scripts import check_connection as cc
from scripts import fetch_official_audit_data as fa

SPOT = "https://spot.test"
FUT = "https://fut.test"
SPOT_KEY, SPOT_SECRET = "spotKEY" * 4, "spotSECRET" * 4
FUT_KEY, FUT_SECRET = "futKEY" * 4, "futSECRET" * 4


def _register_read_endpoints():
    responses.get(f"{SPOT}/api/v3/ping", json={})
    responses.get(f"{SPOT}/api/v3/time", json={"serverTime": 1_700_000_000_000})
    responses.get(f"{SPOT}/api/v3/exchangeInfo",
                  json={"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "filters": [{}, {}]}]})
    responses.get(f"{SPOT}/api/v3/account", json={
        "canTrade": True, "canWithdraw": False,
        "balances": [{"asset": "USDT", "free": "1000", "locked": "0"}]})
    responses.get(f"{FUT}/fapi/v1/ping", json={})
    responses.get(f"{FUT}/fapi/v1/time", json={"serverTime": 1_700_000_000_000})
    responses.get(f"{FUT}/fapi/v1/exchangeInfo", json={"symbols": [{"symbol": "BTCUSDT", "status": "TRADING",
                  "filters": [{"filterType": "MIN_NOTIONAL", "notional": "100"}]}]})
    responses.get(f"{FUT}/fapi/v2/account", json={"canTrade": True, "totalWalletBalance": "5000",
                                                  "positions": []})
    responses.get(f"{FUT}/fapi/v2/balance", json=[{"asset": "USDT", "balance": "5000",
                                                   "availableBalance": "5000"}])


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("BINANCE_TESTNET_API_KEY", SPOT_KEY)
    monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", SPOT_SECRET)
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", FUT_KEY)
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", FUT_SECRET)


@responses.activate
def test_check_connection_read_only_and_no_secrets(creds):
    _register_read_endpoints()
    lines = []
    rc = cc.main(["--spot-base-url", SPOT, "--futures-base-url", FUT], out=lines.append)
    text = "\n".join(lines)
    assert rc == 0, text
    # only GET requests on whitelisted read endpoints
    assert responses.calls, "no request was made"
    for call in responses.calls:
        assert call.request.method == "GET"
        path = call.request.path_url.split("?")[0]
        assert path in cc.SPOT_READ_ENDPOINTS + cc.FUTURES_READ_ENDPOINTS
    # secrets never printed
    for s in (SPOT_KEY, SPOT_SECRET, FUT_KEY, FUT_SECRET):
        assert s not in text
    assert "signature=" not in text
    assert "9/9 checks OK" in text


@responses.activate
def test_check_connection_reports_errors_without_leaking(creds):
    _register_read_endpoints()
    responses.replace(responses.GET, f"{FUT}/fapi/v2/account", status=401,
                      json={"code": -2015, "msg": f"Invalid API-key {FUT_KEY}"})
    lines = []
    rc = cc.main(["--only", "futures", "--futures-base-url", FUT], out=lines.append)
    text = "\n".join(lines)
    assert rc == 1
    assert "FAIL] futures.account" in text and "-2015" in text
    assert FUT_KEY not in text and FUT_SECRET not in text


@responses.activate
def test_check_connection_without_credentials_skips_signed(monkeypatch):
    for v in ("BINANCE_FUTURES_TESTNET_API_KEY", "BINANCE_FUTURES_TESTNET_API_SECRET"):
        monkeypatch.delenv(v, raising=False)
    _register_read_endpoints()
    lines = []
    rc = cc.main(["--only", "futures", "--futures-base-url", FUT], out=lines.append)
    assert rc == 0
    assert "SKIP" in "\n".join(lines)
    assert all("/fapi/v2/" not in c.request.url for c in responses.calls)


def test_spot_client_refuses_non_whitelisted_endpoint():
    c = cc.SpotReadOnlyClient("", "", SPOT)
    with pytest.raises(ValueError):
        c._get("/api/v3/order")
    assert not hasattr(c, "post") and not hasattr(c, "create_order")


def test_check_connection_source_has_no_mutating_calls():
    src = Path(cc.__file__).read_text()
    for forbidden in (".post(", ".delete(", ".put(", "new_order", "set_leverage", "set_margin_type",
                      "algoOrder", "start_user_stream"):
        assert forbidden not in src


# ----------------------------------------------------------------------------
# fetch_official_audit_data
# ----------------------------------------------------------------------------
def test_compare_funding_handles_jitter_and_mismatch(tmp_path):
    h8 = 28_800_000
    local = pd.DataFrame({"timestamp": [0, h8, 2 * h8], "funding_rate": [1e-4, 2e-4, 1e-4]})
    local.to_csv(tmp_path / "BTCUSDT.csv", index=False)
    official = pd.DataFrame({"timestamp": [3, h8 + 5, 2 * h8 + 1, 2 * h8 + 4 * 3_600_000],
                             "funding_rate": [1e-4, 2e-4, 0.5e-4, 1e-4]})
    rep = fa.compare_funding(official, tmp_path / "BTCUSDT.csv")
    assert rep["n_matched"] == 3
    assert rep["share_exact"] == pytest.approx(2 / 3)
    assert rep["max_abs_diff"] == pytest.approx(0.5e-4)
    assert fa.compare_funding(official, tmp_path / "missing.csv")["status"] == "local_missing"


def test_compare_closes(tmp_path):
    local = pd.DataFrame({"timestamp": [0, 1, 2], "open": 1, "high": 1, "low": 1, "close": [10.0, 11.0, 12.0],
                          "volume": 1})
    local.to_csv(tmp_path / "X_1d.csv", index=False)
    off = pd.DataFrame({"timestamp": [1, 2, 3], "close": [11.0, 12.12, 13.0]})
    rep = fa.compare_closes(off, tmp_path / "X_1d.csv")
    assert rep["n_matched"] == 2 and rep["share_exact"] == 0.5
    assert rep["max_rel_diff"] == pytest.approx(0.01)


def test_paginate_klines_stops_and_dedups():
    pages = {0: [[0], [1], [2]], 3: [[2], [3]]}
    rows = fa.paginate_klines(lambda s, lim: [list(r) for r in pages.get(s, [])], 0, 10, 3)
    assert [r[0] for r in rows] == [0, 1, 2, 3]


@responses.activate
def test_fetch_audit_end_to_end(tmp_path, monkeypatch):
    day = 86_400_000
    now = 3 * day + 1000
    responses.get(f"{FUT}/fapi/v1/time", json={"serverTime": now})
    responses.get(f"{FUT}/fapi/v1/exchangeInfo", json={"symbols": []})
    responses.get(f"{FUT}/fapi/v1/fundingInfo", json=[{"symbol": "SOLUSDT", "fundingIntervalHours": 4}])
    responses.get(f"{FUT}/fapi/v1/fundingRate", json=[
        {"symbol": "BTCUSDT", "fundingTime": 0, "fundingRate": "0.0001", "markPrice": "1"}])
    k = [[i * day, "1", "2", "0.5", "1.5", "10", (i + 1) * day - 1, "0", 0, "0", "0", "0"] for i in range(4)]
    responses.get(f"{FUT}/fapi/v1/markPriceKlines", json=k)
    responses.get(f"{FUT}/fapi/v1/klines", json=k)
    responses.get(f"{SPOT}/api/v3/exchangeInfo", json={"symbols": []})
    responses.get(f"{SPOT}/api/v3/klines", json=k)
    local = tmp_path / "local"
    (local / "funding").mkdir(parents=True)
    pd.DataFrame({"timestamp": [0], "funding_rate": [1e-4]}).to_csv(local / "funding" / "BTCUSDT.csv", index=False)
    out = tmp_path / "audit"
    rc = fa.main(["--out", str(out), "--futures-symbols", "BTCUSDT", "--spot-symbols", "BTCUSDT",
                  "--futures-base-url", FUT, "--spot-base-url", SPOT, "--futures-start", "1970-01-01",
                  "--spot-start", "1970-01-01", "--pause", "0", "--local-data", str(local)])
    assert rc == 0
    assert all(c.request.method == "GET" for c in responses.calls)
    manifest = json.loads((out / "manifest.json").read_text())
    assert "funding/BTCUSDT.csv" in manifest["files"]
    assert len(manifest["files"]["funding/BTCUSDT.csv"]["sha256"]) == 64
    fk = pd.read_csv(out / "futures_klines_1d" / "BTCUSDT.csv")
    assert len(fk) == 3  # the still-open 4th daily candle is dropped
    report = json.loads((out / "audit_report.json").read_text())
    assert report["funding"]["BTCUSDT"]["share_exact"] == 1.0
