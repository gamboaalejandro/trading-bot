"""
Binance USDT-M Futures REST client (/fapi), native implementation.

Spec: docs/research/PLAN.md §4.4 and §7.4.

- HMAC SHA256 signed requests (query string signed, sent as query string).
- One-way position mode and ISOLATED margin only (idempotent setters).
- Leverage capped by policy: 1x altcoins, 2x nominal BTC/ETH (<= 1.5x effective
  is enforced by sizing); never above the user's hard ceiling of 3x.
- Catastrophe stops are STOP_MARKET reduceOnly with workingType=MARK_PRICE sent
  to ``POST /fapi/v1/algoOrder``. Since 2025-12-09 ``/fapi/v1/order`` rejects
  conditional orders with error -4120, which is mapped to ``AlgoOrderRequiredError``.
- Base URL defaults to the futures testnet; override with the
  ``BINANCE_FUTURES_BASE_URL`` environment variable. Mutating requests against
  production require ``LIVE_TRADING_CONFIRM=I_UNDERSTAND``.

[VERIFICAR] Algo order parameter names follow
https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Algo-Order
and must be checked against the testnet before live use.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

import pandas as pd
import requests

logger = logging.getLogger(__name__)

PRODUCTION_BASE_URL = "https://fapi.binance.com"
TESTNET_BASE_URL = "https://testnet.binancefuture.com"
BASE_URL_ENV = "BINANCE_FUTURES_BASE_URL"
LIVE_CONFIRM_ENV = "LIVE_TRADING_CONFIRM"
LIVE_CONFIRM_VALUE = "I_UNDERSTAND"

# Error codes
ERR_NO_NEED_TO_CHANGE_MARGIN_TYPE = -4046
ERR_NO_NEED_TO_CHANGE_POSITION_SIDE = -4059
ERR_ALGO_ORDER_REQUIRED = -4120

# Risk policy (PLAN §7.4 and user decision: hard ceiling 3x, isolated margin)
HARD_MAX_LEVERAGE = 3
MAJORS = frozenset({"BTCUSDT", "ETHUSDT"})
MAJORS_MAX_LEVERAGE = 2
ALTS_MAX_LEVERAGE = 1

PLAIN_ORDER_TYPES = frozenset({"MARKET", "LIMIT"})
CONDITIONAL_ORDER_TYPES = frozenset({
    "STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET",
})
_CLIENT_ID_RE = re.compile(r"^[.A-Z:/a-z0-9_-]{1,36}$")

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]


class BinanceFuturesError(Exception):
    """Error returned by the futures API (or transport failure)."""

    def __init__(self, status: Optional[int], code: Optional[int], msg: str, endpoint: str = ""):
        self.status = status
        self.code = code
        self.msg = msg
        self.endpoint = endpoint
        super().__init__(f"{endpoint} -> HTTP {status} code={code} msg={msg}")


class AlgoOrderRequiredError(BinanceFuturesError):
    """-4120: conditional order types must go through the Algo Order API."""


class ReadOnlyViolation(RuntimeError):
    """A mutating request was attempted on a read-only client."""


class LiveTradingNotConfirmed(RuntimeError):
    """A mutating request against production without LIVE_TRADING_CONFIRM."""


def resolve_base_url(base_url: Optional[str] = None) -> str:
    """Explicit value, else ``$BINANCE_FUTURES_BASE_URL``, else the testnet."""
    url = base_url or os.getenv(BASE_URL_ENV, "").strip() or TESTNET_BASE_URL
    return url.rstrip("/")


def is_production(base_url: str) -> bool:
    return urlparse(base_url).hostname == urlparse(PRODUCTION_BASE_URL).hostname


def policy_max_leverage(symbol: str) -> int:
    """Max nominal leverage allowed by the risk policy for ``symbol``."""
    return MAJORS_MAX_LEVERAGE if symbol.upper() in MAJORS else ALTS_MAX_LEVERAGE


def fmt_decimal(value: Any) -> str:
    """Format a number for the API without exponent or float noise."""
    d = Decimal(str(value))
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _validate_client_id(client_id: str, name: str) -> None:
    if not client_id or not _CLIENT_ID_RE.match(client_id):
        raise ValueError(f"{name} must match {_CLIENT_ID_RE.pattern} (deterministic, idempotent id)")


class BinanceFuturesClient:
    """Native client for Binance USDT-M futures (/fapi)."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: Optional[str] = None,
        recv_window: int = 5000,
        timeout: float = 10.0,
        read_only: bool = False,
        session: Optional[requests.Session] = None,
    ):
        """
        Args:
            api_key: API key (may be empty for public endpoints only)
            api_secret: API secret (may be empty for public endpoints only)
            base_url: REST base URL; ``None`` -> ``resolve_base_url()`` (testnet by default)
            recv_window: recvWindow for signed requests (ms)
            timeout: HTTP timeout in seconds
            read_only: if True, any non-GET request raises ``ReadOnlyViolation``
            session: optional ``requests.Session`` (tests)
        """
        self.api_key = api_key or ""
        self._secret = (api_secret or "").encode("utf-8")
        self.base_url = resolve_base_url(base_url)
        self.recv_window = int(recv_window)
        self.timeout = timeout
        self.read_only = read_only
        self.session = session or requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self._time_offset = 0
        self.last_used_weight: Optional[int] = None
        logger.info("Futures client initialized: %s (%s%s)", self.base_url,
                    "PRODUCTION" if is_production(self.base_url) else "TESTNET/CUSTOM",
                    ", read-only" if read_only else "")

    def __repr__(self) -> str:
        return f"BinanceFuturesClient(base_url={self.base_url!r}, read_only={self.read_only})"

    @classmethod
    def from_env(cls, environment: str = "futures_testnet", **kwargs) -> "BinanceFuturesClient":
        """Build a client with credentials from environment variables (core.secrets)."""
        from core.secrets import get_credentials

        creds = get_credentials(environment)  # type: ignore[arg-type]
        if environment == "live" and "base_url" not in kwargs and not os.getenv(BASE_URL_ENV):
            kwargs["base_url"] = PRODUCTION_BASE_URL
        return cls(creds.api_key, creds.api_secret, **kwargs)

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    def sign(self, query_string: str) -> str:
        """HMAC SHA256 hex digest of ``query_string`` with the API secret."""
        return hmac.new(self._secret, query_string.encode("utf-8"), hashlib.sha256).hexdigest()

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None,
                 signed: bool = False, api_key: bool = False) -> Any:
        method = method.upper()
        if method != "GET":
            if self.read_only:
                raise ReadOnlyViolation(f"{method} {path} blocked: client is read-only")
            # The user stream listenKey does not trade, so it is exempt from the live confirmation
            if (is_production(self.base_url) and path != "/fapi/v1/listenKey"
                    and os.getenv(LIVE_CONFIRM_ENV) != LIVE_CONFIRM_VALUE):
                raise LiveTradingNotConfirmed(
                    f"{method} {path} against production requires {LIVE_CONFIRM_ENV}={LIVE_CONFIRM_VALUE}")

        items = [(k, v) for k, v in (params or {}).items() if v is not None]
        items = [(k, ("true" if v else "false") if isinstance(v, bool) else v) for k, v in items]
        if signed or api_key:
            if not self.api_key:
                raise BinanceFuturesError(None, None, "API key required", path)
        if signed:
            if not self._secret:
                raise BinanceFuturesError(None, None, "API secret required", path)
            items.append(("recvWindow", self.recv_window))
            items.append(("timestamp", self._timestamp()))
            query = urlencode(items)
            query = f"{query}&signature={self.sign(query)}"
        else:
            query = urlencode(items)

        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        try:
            resp = self.session.request(method, url, timeout=self.timeout)
        except requests.RequestException as e:
            # Never include the URL: it carries the signature
            raise BinanceFuturesError(None, None, f"transport error: {type(e).__name__}", path) from None

        weight = resp.headers.get("X-MBX-USED-WEIGHT-1M") or resp.headers.get("X-MBX-USED-WEIGHT")
        if weight is not None:
            try:
                self.last_used_weight = int(weight)
            except ValueError:
                pass

        try:
            payload = resp.json()
        except ValueError:
            payload = None

        if resp.status_code >= 400:
            code = payload.get("code") if isinstance(payload, dict) else None
            msg = payload.get("msg", "") if isinstance(payload, dict) else (resp.text or "")[:200]
            exc_cls = AlgoOrderRequiredError if code == ERR_ALGO_ORDER_REQUIRED else BinanceFuturesError
            raise exc_cls(resp.status_code, code, msg, path)
        if payload is None:
            raise BinanceFuturesError(resp.status_code, None, "invalid JSON response", path)
        return payload

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------
    def ping(self) -> dict:
        """GET /fapi/v1/ping"""
        return self._request("GET", "/fapi/v1/ping")

    def server_time(self) -> int:
        """GET /fapi/v1/time -> serverTime (ms)."""
        return int(self._request("GET", "/fapi/v1/time")["serverTime"])

    def sync_time(self) -> int:
        """Align local timestamps with the server clock. Returns the offset (ms)."""
        local = int(time.time() * 1000)
        self._time_offset = self.server_time() - local
        return self._time_offset

    def exchange_info(self) -> dict:
        """GET /fapi/v1/exchangeInfo (symbol filters: LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    @staticmethod
    def _klines_frame(rows: list) -> pd.DataFrame:
        df = pd.DataFrame(rows, columns=KLINE_COLUMNS[: len(rows[0])] if rows else KLINE_COLUMNS)
        if df.empty:
            return df.set_index(pd.DatetimeIndex([], tz="UTC", name="open_time"))
        for c in ("open", "high", "low", "close", "volume", "quote_volume",
                  "taker_buy_volume", "taker_buy_quote_volume"):
            if c in df:
                df[c] = df[c].astype(float)
        df["open_time"] = df["open_time"].astype("int64")
        df["close_time"] = df["close_time"].astype("int64")
        df = df.drop(columns=["ignore"], errors="ignore")
        df.index = pd.to_datetime(df["open_time"], unit="ms", utc=True).rename("open_time")
        return df.drop(columns=["open_time"])

    def _get_klines(self, path: str, symbol: str, interval: str, limit: int,
                    start_ms: Optional[int], end_ms: Optional[int], closed_only: bool) -> pd.DataFrame:
        rows = self._request("GET", path, {
            "symbol": symbol, "interval": interval, "limit": int(limit),
            "startTime": start_ms, "endTime": end_ms,
        })
        df = self._klines_frame(rows)
        if closed_only and not df.empty:
            now = self.server_time()
            df = df[df["close_time"] < now]
        return df

    def klines(self, symbol: str, interval: str, limit: int = 1500, closed_only: bool = True,
               start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> pd.DataFrame:
        """GET /fapi/v1/klines. ``closed_only`` drops rows with closeTime >= serverTime."""
        return self._get_klines("/fapi/v1/klines", symbol, interval, limit, start_ms, end_ms, closed_only)

    def mark_price_klines(self, symbol: str, interval: str, limit: int = 1500, closed_only: bool = True,
                          start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> pd.DataFrame:
        """GET /fapi/v1/markPriceKlines (volume columns are meaningless and zero)."""
        return self._get_klines("/fapi/v1/markPriceKlines", symbol, interval, limit,
                                start_ms, end_ms, closed_only)

    def funding_rate(self, symbol: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None,
                     limit: int = 1000) -> pd.DataFrame:
        """
        GET /fapi/v1/fundingRate. Settled funding history as a DataFrame indexed by
        fundingTime (UTC) with ``funding_rate`` as a FRACTION (0.0001 = 0.01 %) and
        ``mark_price``. With ``start_ms`` the full range is paginated.
        """
        records: List[dict] = []
        cursor = start_ms
        while True:
            batch = self._request("GET", "/fapi/v1/fundingRate", {
                "symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": int(limit),
            })
            records.extend(batch)
            if start_ms is None or len(batch) < limit:
                break
            last = int(batch[-1]["fundingTime"])
            if cursor is not None and last < cursor:
                break
            cursor = last + 1
        if not records:
            return pd.DataFrame(columns=["funding_rate", "mark_price"],
                                index=pd.DatetimeIndex([], tz="UTC", name="funding_time"))
        df = pd.DataFrame(records)
        out = pd.DataFrame({
            "funding_time_ms": df["fundingTime"].astype("int64"),
            "funding_rate": df["fundingRate"].astype(float),
            "mark_price": pd.to_numeric(df.get("markPrice"), errors="coerce") if "markPrice" in df else float("nan"),
        })
        out.index = pd.to_datetime(out["funding_time_ms"], unit="ms", utc=True).rename("funding_time")
        out = out[~out.index.duplicated(keep="first")].sort_index()
        return out

    def funding_info(self) -> List[dict]:
        """GET /fapi/v1/fundingInfo (symbols with non-default interval / caps)."""
        return self._request("GET", "/fapi/v1/fundingInfo")

    def premium_index(self, symbol: Optional[str] = None) -> Any:
        """GET /fapi/v1/premiumIndex (mark price, index price, next funding)."""
        return self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})

    # ------------------------------------------------------------------
    # Account (signed)
    # ------------------------------------------------------------------
    def commission_rate(self, symbol: str) -> dict:
        """GET /fapi/v1/commissionRate -> makerCommissionRate / takerCommissionRate."""
        return self._request("GET", "/fapi/v1/commissionRate", {"symbol": symbol}, signed=True)

    def leverage_bracket(self, symbol: str) -> List[dict]:
        """GET /fapi/v1/leverageBracket -> list of brackets (maintMarginRatio, notionalCap...)."""
        data = self._request("GET", "/fapi/v1/leverageBracket", {"symbol": symbol}, signed=True)
        if isinstance(data, dict):
            data = [data]
        for entry in data:
            if entry.get("symbol") == symbol:
                return list(entry.get("brackets", []))
        return []

    def position_risk(self, symbol: Optional[str] = None) -> List[dict]:
        """GET /fapi/v2/positionRisk"""
        return self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)

    def account(self) -> dict:
        """GET /fapi/v2/account"""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def balance(self) -> List[dict]:
        """GET /fapi/v2/balance"""
        return self._request("GET", "/fapi/v2/balance", signed=True)

    def get_position_mode(self) -> bool:
        """GET /fapi/v1/positionSide/dual -> True if hedge mode."""
        return bool(self._request("GET", "/fapi/v1/positionSide/dual", signed=True)["dualSidePosition"])

    def set_one_way_mode(self) -> None:
        """POST /fapi/v1/positionSide/dual dualSidePosition=false (idempotent)."""
        try:
            self._request("POST", "/fapi/v1/positionSide/dual", {"dualSidePosition": False}, signed=True)
        except BinanceFuturesError as e:
            if e.code != ERR_NO_NEED_TO_CHANGE_POSITION_SIDE:
                raise
            logger.debug("Position mode already one-way")

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> None:
        """POST /fapi/v1/marginType. Idempotent: ignores -4046 'No need to change margin type'."""
        if margin_type.upper() != "ISOLATED":
            raise ValueError("Risk policy (PLAN §7.4): only ISOLATED margin is allowed")
        try:
            self._request("POST", "/fapi/v1/marginType",
                          {"symbol": symbol, "marginType": "ISOLATED"}, signed=True)
        except BinanceFuturesError as e:
            if e.code != ERR_NO_NEED_TO_CHANGE_MARGIN_TYPE:
                raise
            logger.debug("%s margin type already ISOLATED", symbol)

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """POST /fapi/v1/leverage, bounded by ``policy_max_leverage`` (<= 3x hard ceiling)."""
        if isinstance(leverage, bool) or int(leverage) != leverage or leverage < 1:
            raise ValueError("leverage must be a positive integer")
        cap = min(policy_max_leverage(symbol), HARD_MAX_LEVERAGE)
        if leverage > cap:
            raise ValueError(f"leverage {leverage}x exceeds policy cap {cap}x for {symbol}")
        return self._request("POST", "/fapi/v1/leverage",
                             {"symbol": symbol, "leverage": int(leverage)}, signed=True)

    # ------------------------------------------------------------------
    # Orders (signed)
    # ------------------------------------------------------------------
    def new_order(self, symbol: str, side: str, type_: str, quantity: float, client_order_id: str,
                  reduce_only: bool = False, price: Optional[float] = None,
                  tif: Optional[str] = None) -> dict:
        """
        POST /fapi/v1/order for MARKET / LIMIT orders with a deterministic
        ``newClientOrderId``. Conditional types are rejected locally: use
        ``new_stop_market_algo`` (the exchange answers -4120 otherwise).
        """
        side = side.upper()
        type_ = type_.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if type_ in CONDITIONAL_ORDER_TYPES:
            raise ValueError(f"{type_} must be sent via new_stop_market_algo (/fapi/v1/algoOrder, -4120)")
        if type_ not in PLAIN_ORDER_TYPES:
            raise ValueError(f"unsupported order type {type_}")
        if quantity is None or float(quantity) <= 0:
            raise ValueError("quantity must be > 0")
        _validate_client_id(client_order_id, "client_order_id")
        params: Dict[str, Any] = {
            "symbol": symbol, "side": side, "type": type_,
            "quantity": fmt_decimal(quantity),
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        if reduce_only:
            params["reduceOnly"] = True
        if type_ == "LIMIT":
            if price is None or float(price) <= 0:
                raise ValueError("price is required for LIMIT orders")
            params["price"] = fmt_decimal(price)
            params["timeInForce"] = (tif or "GTC").upper()
        elif price is not None or tif is not None:
            raise ValueError("price/tif are only valid for LIMIT orders")
        logger.info("Futures order %s %s %s qty=%s id=%s reduceOnly=%s",
                    symbol, side, type_, params["quantity"], client_order_id, reduce_only)
        return self._request("POST", "/fapi/v1/order", params, signed=True)

    def query_order(self, symbol: str, client_order_id: Optional[str] = None,
                    order_id: Optional[int] = None) -> dict:
        """GET /fapi/v1/order by orderId or origClientOrderId (idempotent retries)."""
        if not client_order_id and order_id is None:
            raise ValueError("client_order_id or order_id is required")
        return self._request("GET", "/fapi/v1/order", {
            "symbol": symbol, "orderId": order_id, "origClientOrderId": client_order_id}, signed=True)

    def cancel_order(self, symbol: str, client_order_id: Optional[str] = None,
                     order_id: Optional[int] = None) -> dict:
        """DELETE /fapi/v1/order"""
        if not client_order_id and order_id is None:
            raise ValueError("client_order_id or order_id is required")
        return self._request("DELETE", "/fapi/v1/order", {
            "symbol": symbol, "orderId": order_id, "origClientOrderId": client_order_id}, signed=True)

    def open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """GET /fapi/v1/openOrders"""
        return self._request("GET", "/fapi/v1/openOrders", {"symbol": symbol}, signed=True)

    def new_stop_market_algo(self, symbol: str, side: str, quantity: float, trigger_price: float,
                             client_algo_id: str, reduce_only: bool = True,
                             working_type: str = "MARK_PRICE") -> dict:
        """
        Catastrophe stop: POST /fapi/v1/algoOrder with algoType=CONDITIONAL,
        type=STOP_MARKET, reduceOnly=true and workingType=MARK_PRICE.
        [VERIFICAR parameter names against the official New-Algo-Order docs.]
        """
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if not reduce_only:
            raise ValueError("Risk policy (PLAN §7.4): catastrophe stops must be reduceOnly")
        working_type = working_type.upper()
        if working_type not in ("MARK_PRICE", "CONTRACT_PRICE"):
            raise ValueError("working_type must be MARK_PRICE or CONTRACT_PRICE")
        if quantity is None or float(quantity) <= 0:
            raise ValueError("quantity must be > 0")
        if trigger_price is None or float(trigger_price) <= 0:
            raise ValueError("trigger_price must be > 0")
        _validate_client_id(client_algo_id, "client_algo_id")
        params = {
            "algoType": "CONDITIONAL",
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "quantity": fmt_decimal(quantity),
            "triggerPrice": fmt_decimal(trigger_price),
            "workingType": working_type,
            "reduceOnly": True,
            "priceProtect": True,
            "clientAlgoId": client_algo_id,
        }
        logger.info("Futures algo stop %s %s qty=%s trigger=%s id=%s",
                    symbol, side, params["quantity"], params["triggerPrice"], client_algo_id)
        return self._request("POST", "/fapi/v1/algoOrder", params, signed=True)

    def cancel_algo_order(self, symbol: str, algo_id: Optional[int] = None,
                          client_algo_id: Optional[str] = None) -> dict:
        """DELETE /fapi/v1/algoOrder by algoId or clientAlgoId."""
        if algo_id is None and not client_algo_id:
            raise ValueError("algo_id or client_algo_id is required")
        return self._request("DELETE", "/fapi/v1/algoOrder", {
            "symbol": symbol, "algoId": algo_id, "clientAlgoId": client_algo_id}, signed=True)

    def open_algo_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """GET /fapi/v1/openAlgoOrders"""
        data = self._request("GET", "/fapi/v1/openAlgoOrders", {"symbol": symbol}, signed=True)
        if isinstance(data, dict):
            data = data.get("orders", data.get("rows", []))
        return list(data)

    # ------------------------------------------------------------------
    # User data stream (API key only, not signed)
    # ------------------------------------------------------------------
    def start_user_stream(self) -> str:
        """POST /fapi/v1/listenKey -> listenKey (valid 60 min)."""
        return self._request("POST", "/fapi/v1/listenKey", api_key=True)["listenKey"]

    def keepalive_user_stream(self, listen_key: str) -> None:
        """PUT /fapi/v1/listenKey (call every ~30 min). ``listen_key`` kept for symmetry."""
        self._request("PUT", "/fapi/v1/listenKey", api_key=True)

    def close_user_stream(self, listen_key: str) -> None:
        """DELETE /fapi/v1/listenKey"""
        self._request("DELETE", "/fapi/v1/listenKey", api_key=True)

    def close(self) -> None:
        self.session.close()
