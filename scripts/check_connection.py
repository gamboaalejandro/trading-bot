#!/usr/bin/env python
"""
Read-only connection check for Binance Spot Demo and USDT-M Futures Testnet.

Only GET endpoints are called: ping, time, exchangeInfo, account and balance.
No order is ever sent and secrets are never printed (only whether each
variable is set). Credentials come from environment variables (core.secrets).

Usage:
    python scripts/check_connection.py              # spot demo + futures testnet
    python scripts/check_connection.py --only futures
    python scripts/check_connection.py --spot-base-url https://testnet.binance.vision

Base URLs:
    spot:    --spot-base-url, else $BINANCE_SPOT_BASE_URL, else $BINANCE_TESTNET_URL,
             else https://demo-api.binance.com  [VERIFICAR: matches demo.binance.com keys]
    futures: --futures-base-url, else $BINANCE_FUTURES_BASE_URL,
             else https://testnet.binancefuture.com

Exit code 0 when every executed check passed, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.binance_futures_client import BinanceFuturesClient, resolve_base_url  # noqa: E402
from core.secrets import ENV_VARS, MissingSecretError, get_credentials, redact  # noqa: E402

SPOT_DEMO_BASE_URL = "https://demo-api.binance.com"

# The only endpoints this script may call (all GET)
SPOT_READ_ENDPOINTS = ("/api/v3/ping", "/api/v3/time", "/api/v3/exchangeInfo", "/api/v3/account")
FUTURES_READ_ENDPOINTS = ("/fapi/v1/ping", "/fapi/v1/time", "/fapi/v1/exchangeInfo",
                          "/fapi/v2/account", "/fapi/v2/balance")

_SIG_RE = re.compile(r"signature=[0-9a-fA-F]+")


def resolve_spot_base_url(explicit: Optional[str] = None) -> str:
    return (explicit or os.getenv("BINANCE_SPOT_BASE_URL", "").strip()
            or os.getenv("BINANCE_TESTNET_URL", "").strip() or SPOT_DEMO_BASE_URL).rstrip("/")


class SpotReadOnlyClient:
    """Minimal spot client exposing GET endpoints only."""

    def __init__(self, api_key: str, api_secret: str, base_url: str, timeout: float = 10.0,
                 session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self._key = api_key or ""
        self._secret = (api_secret or "").encode("utf-8")
        self.timeout = timeout
        self.session = session or requests.Session()
        if self._key:
            self.session.headers.update({"X-MBX-APIKEY": self._key})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Any:
        if path not in SPOT_READ_ENDPOINTS:
            raise ValueError(f"{path} is not a whitelisted read-only endpoint")
        items = list((params or {}).items())
        if signed:
            items += [("recvWindow", 5000), ("timestamp", int(time.time() * 1000))]
            q = urlencode(items)
            q += "&signature=" + hmac.new(self._secret, q.encode(), hashlib.sha256).hexdigest()
        else:
            q = urlencode(items)
        try:
            resp = self.session.get(f"{self.base_url}{path}" + (f"?{q}" if q else ""), timeout=self.timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"{path}: transport error {type(e).__name__}") from None
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        if resp.status_code >= 400:
            code = payload.get("code") if isinstance(payload, dict) else None
            msg = payload.get("msg") if isinstance(payload, dict) else (resp.text or "")[:200]
            raise RuntimeError(f"{path}: HTTP {resp.status_code} code={code} msg={msg}")
        return payload

    def ping(self) -> Any:
        return self._get("/api/v3/ping")

    def server_time(self) -> int:
        return int(self._get("/api/v3/time")["serverTime"])

    def exchange_info(self) -> dict:
        return self._get("/api/v3/exchangeInfo", {"symbol": "BTCUSDT"})

    def account(self) -> dict:
        return self._get("/api/v3/account", {"omitZeroBalances": "true"}, signed=True)


class Reporter:
    """Collects check results; every message is redacted before printing."""

    def __init__(self, secrets: Tuple[str, ...] = (), out: Callable[[str], None] = print):
        self.secrets = tuple(s for s in secrets if s)
        self.out = out
        self.results: List[Tuple[str, bool]] = []

    def say(self, text: str) -> None:
        self.out(_SIG_RE.sub("signature=<redacted>", redact(text, *self.secrets)))

    def run(self, name: str, fn: Callable[[], str]) -> bool:
        try:
            detail = fn()
            ok = True
        except Exception as e:  # noqa: BLE001 - report any failure, never crash
            detail = f"{type(e).__name__}: {e}"
            ok = False
        self.results.append((name, ok))
        self.say(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")
        return ok


def _skew(server_ms: int) -> str:
    skew = server_ms - int(time.time() * 1000)
    warn = "  (WARNING: > 1000 ms, sync your clock)" if abs(skew) > 1000 else ""
    return f"serverTime={server_ms} skew={skew} ms{warn}"


def _env_status(environment: str) -> str:
    key_var, secret_vars = ENV_VARS[environment]
    key_set = bool(os.getenv(key_var, "").strip())
    secret_set = any(os.getenv(v, "").strip() for v in secret_vars)
    return (f"{key_var}={'set' if key_set else 'MISSING'}, "
            f"{secret_vars[0]}={'set' if secret_set else 'MISSING'}")


def check_spot(base_url: str, rep: Reporter, session: Optional[requests.Session] = None) -> None:
    rep.say(f"\n== Spot demo ({base_url}) ==")
    rep.say(f"  credentials: {_env_status('spot_demo')}")
    try:
        creds = get_credentials("spot_demo")
        key, secret = creds.api_key, creds.api_secret
        rep.secrets += (key, secret)
    except MissingSecretError:
        key = secret = ""
    client = SpotReadOnlyClient(key, secret, base_url, session=session)
    rep.run("spot.ping", lambda: (client.ping(), "reachable")[1])
    rep.run("spot.time", lambda: _skew(client.server_time()))

    def _info() -> str:
        info = client.exchange_info()
        sym = (info.get("symbols") or [{}])[0]
        return f"BTCUSDT status={sym.get('status')} filters={len(sym.get('filters', []))}"
    rep.run("spot.exchangeInfo", _info)

    if not key:
        rep.say("  [SKIP] account/balance: spot demo credentials not set")
        return

    def _account() -> str:
        acc = client.account()
        bals = [b for b in acc.get("balances", []) if float(b.get("free", 0)) + float(b.get("locked", 0)) > 0]
        usdt = next((b for b in bals if b.get("asset") == "USDT"), None)
        usdt_txt = f"USDT free={usdt['free']}" if usdt else "USDT=0"
        return (f"canTrade={acc.get('canTrade')} canWithdraw={acc.get('canWithdraw')} "
                f"assets_with_balance={len(bals)} {usdt_txt}")
    rep.run("spot.account/balance", _account)


def check_futures(base_url: str, rep: Reporter, session: Optional[requests.Session] = None) -> None:
    rep.say(f"\n== Futures testnet ({base_url}) ==")
    rep.say(f"  credentials: {_env_status('futures_testnet')}")
    try:
        creds = get_credentials("futures_testnet")
        key, secret = creds.api_key, creds.api_secret
        rep.secrets += (key, secret)
    except MissingSecretError:
        key = secret = ""
    client = BinanceFuturesClient(key, secret, base_url=base_url, read_only=True, session=session)
    rep.run("futures.ping", lambda: (client.ping(), "reachable")[1])
    rep.run("futures.time", lambda: _skew(client.server_time()))

    def _info() -> str:
        info = client.exchange_info()
        syms = info.get("symbols", [])
        btc = next((s for s in syms if s.get("symbol") == "BTCUSDT"), {})
        mn = next((f.get("notional") for f in btc.get("filters", []) if f.get("filterType") == "MIN_NOTIONAL"), None)
        return f"symbols={len(syms)} BTCUSDT status={btc.get('status')} minNotional={mn}"
    rep.run("futures.exchangeInfo", _info)

    if not key:
        rep.say("  [SKIP] account/balance: futures testnet credentials not set")
        return

    def _account() -> str:
        acc = client.account()
        open_pos = [p for p in acc.get("positions", []) if float(p.get("positionAmt", 0) or 0) != 0]
        return (f"canTrade={acc.get('canTrade')} totalWalletBalance={acc.get('totalWalletBalance')} "
                f"open_positions={len(open_pos)}")
    rep.run("futures.account", _account)

    def _balance() -> str:
        bals = client.balance()
        usdt = next((b for b in bals if b.get("asset") == "USDT"), None)
        return f"USDT balance={usdt.get('balance')} available={usdt.get('availableBalance')}" if usdt else "USDT=0"
    rep.run("futures.balance", _balance)


def main(argv: Optional[List[str]] = None, session: Optional[requests.Session] = None,
         out: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(description="Read-only Binance connection check (never trades).")
    ap.add_argument("--only", choices=["spot", "futures"], default=None)
    ap.add_argument("--spot-base-url", default=None)
    ap.add_argument("--futures-base-url", default=None)
    args = ap.parse_args(argv)

    rep = Reporter(out=out)
    rep.say("Binance read-only connection check (no orders are sent; secrets are never printed)")
    if args.only in (None, "spot"):
        check_spot(resolve_spot_base_url(args.spot_base_url), rep, session=session)
    if args.only in (None, "futures"):
        check_futures(resolve_base_url(args.futures_base_url), rep, session=session)

    failed = [n for n, ok in rep.results if not ok]
    rep.say(f"\nSummary: {len(rep.results) - len(failed)}/{len(rep.results)} checks OK"
            + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 0 if not failed and rep.results else 1


if __name__ == "__main__":
    sys.exit(main())
