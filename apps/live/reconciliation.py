"""
Reconciliation of the local state against the exchange (PLAN.md §6.2 L02, §7.4, §7.5, §7.7).

The exchange is the source of truth. ``Reconciler.run_once`` compares, per
venue (spot / USDT-M futures), the positions and protective stops recorded in
the local :class:`LiveState` with what the exchange reports and:

- **position without a stop** -> places the catastrophe stop (price from the
  local state, else from ``stop_price_fn``; if neither is known it alerts);
- **orphan stop** (no position, wrong side or a duplicate) -> cancels it;
- **stop quantity != position quantity** -> replaces the stop;
- **divergence** between local and exchange quantities -> alerts and adopts the
  exchange quantity. A local position that vanished while it had a stop is
  reported as ``closed_externally`` (stopped out) so the executor can lock the
  symbol until its signal resets.

It runs at start-up and every 5 minutes (``run_forever``) and after every
daily execution of :mod:`apps.live.portfolio_executor`.

The module also holds the exchange layer shared with the executor:

- :class:`SymbolFilters` (LOT_SIZE / MARKET_LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL
  or NOTIONAL) and the rounding rules (quantities always DOWN to the step);
- the :class:`Venue` protocol and its implementations: :class:`SpotVenue`
  (``core.binance_client.BinanceClient``), :class:`FuturesVenue`
  (``core.binance_futures_client.BinanceFuturesClient``) and :class:`PaperVenue`
  (``TRADING_MODE=dry_run``: reads market data from a real venue, simulates
  every write, never calls a mutating endpoint).

Spot catastrophe stops are ``STOP_LOSS`` SELL orders moved with
``cancelReplace`` (STOP_ON_FAILURE); futures stops are STOP_MARKET reduceOnly
MARK_PRICE algo orders (``POST /fapi/v1/algoOrder``). [VERIFICAR] response
field names of ``/fapi/v1/openAlgoOrders`` (``algoId``, ``clientAlgoId``,
``triggerPrice``, ``quantity``) against the testnet before live use.
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, runtime_checkable

import pandas as pd

logger = logging.getLogger(__name__)

__all__ = [
    "ReconciliationError",
    "StopPlacementError",
    "SymbolFilters",
    "parse_symbol_filters",
    "ExchangePosition",
    "StopOrder",
    "OrderResult",
    "Venue",
    "SpotVenue",
    "FuturesVenue",
    "PaperVenue",
    "klines_frame",
    "LocalPosition",
    "LiveState",
    "ReconciliationAction",
    "ReconciliationReport",
    "Reconciler",
    "RECONCILE_INTERVAL_SECONDS",
]

RECONCILE_INTERVAL_SECONDS = 300
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]
SPOT_STOP_TYPES = ("STOP_LOSS", "STOP_LOSS_LIMIT")
SPOT_ORDER_NOT_FOUND = -2013
FUTURES_ORDER_NOT_FOUND = -2013
_EPS = 1e-12


class ReconciliationError(RuntimeError):
    """Inconsistent exchange data (missing filters, unparsable answers...)."""


class StopPlacementError(RuntimeError):
    """A protective stop could not be placed (the position may be unprotected)."""


# ---------------------------------------------------------------------------
# Symbol filters and rounding
# ---------------------------------------------------------------------------

def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class SymbolFilters:
    """Exchange trading rules of one symbol (all values as Decimal)."""

    symbol: str
    step_size: Decimal
    min_qty: Decimal
    max_qty: Optional[Decimal]
    tick_size: Decimal
    min_notional: Decimal

    def round_qty(self, qty: float) -> float:
        """Round ``|qty|`` DOWN to a multiple of the step (sign preserved)."""
        q = _dec(abs(qty))
        if self.step_size > 0:
            q = (q / self.step_size).to_integral_value(rounding=ROUND_DOWN) * self.step_size
        if self.max_qty is not None and self.max_qty > 0 and q > self.max_qty:
            q = (self.max_qty / self.step_size).to_integral_value(rounding=ROUND_DOWN) * self.step_size \
                if self.step_size > 0 else self.max_qty
        out = float(q)
        return -out if qty < 0 else out

    def round_price(self, price: float, direction: str = "down") -> float:
        """Round a price to the tick (``down`` for long stops, ``up`` for short stops)."""
        p = _dec(price)
        if self.tick_size > 0:
            rounding = ROUND_FLOOR if direction == "down" else ROUND_CEILING
            p = (p / self.tick_size).to_integral_value(rounding=rounding) * self.tick_size
        return float(p)

    def check(self, qty: float, price: float) -> Optional[str]:
        """``None`` if an order of ``qty`` at ``price`` passes the filters, else the reason."""
        q = abs(qty)
        if q <= 0:
            return "zero_qty"
        if q + _EPS < float(self.min_qty):
            return "below_min_qty"
        if q * price + _EPS < float(self.min_notional):
            return "below_min_notional"
        return None

    def is_dust(self, qty: float, price: float) -> bool:
        """Position too small to be traded or protected by a stop."""
        return self.check(self.round_qty(qty), price) is not None


def parse_symbol_filters(symbol_info: Mapping[str, Any], market: str) -> SymbolFilters:
    """
    Build :class:`SymbolFilters` from one ``exchangeInfo`` symbol entry.

    Quantity step: ``MARKET_LOT_SIZE`` when it defines a positive step (market
    orders), else ``LOT_SIZE``. Minimum notional: spot ``NOTIONAL.minNotional``
    or legacy ``MIN_NOTIONAL.minNotional``; futures ``MIN_NOTIONAL.notional``.
    Missing filters raise :class:`ReconciliationError` (fail closed).
    """
    symbol = symbol_info.get("symbol", "?")
    filters = {f.get("filterType"): f for f in symbol_info.get("filters", [])}
    lot = filters.get("LOT_SIZE")
    mlot = filters.get("MARKET_LOT_SIZE")
    pf = filters.get("PRICE_FILTER")
    if lot is None or pf is None:
        raise ReconciliationError(f"{symbol}: LOT_SIZE/PRICE_FILTER missing in exchangeInfo")
    src = mlot if (mlot is not None and _dec(mlot.get("stepSize", "0")) > 0) else lot
    step = _dec(src.get("stepSize", "0"))
    min_qty = max(_dec(lot.get("minQty", "0")), _dec(src.get("minQty", "0")))
    max_qty = _dec(src["maxQty"]) if src.get("maxQty") not in (None, "") else None
    if market == "futures":
        mn = filters.get("MIN_NOTIONAL", {})
        min_notional = mn.get("notional", mn.get("minNotional"))
    else:
        mn = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        min_notional = mn.get("minNotional")
    if min_notional is None:
        raise ReconciliationError(f"{symbol}: MIN_NOTIONAL/NOTIONAL filter missing in exchangeInfo")
    if step <= 0:
        raise ReconciliationError(f"{symbol}: stepSize must be > 0")
    return SymbolFilters(symbol=symbol, step_size=step, min_qty=min_qty, max_qty=max_qty,
                         tick_size=_dec(pf.get("tickSize", "0")), min_notional=_dec(min_notional))


def klines_frame(rows: list, server_time_ms: Optional[int] = None) -> pd.DataFrame:
    """
    Kline rows -> loader-format frame (index = bar OPEN time UTC; columns
    open/high/low/close/volume/quote_volume/close_time).

    With ``server_time_ms`` every row with ``closeTime >= serverTime`` (the
    candle still forming) is dropped. Bars with ``volume == 0`` get NaN prices
    (same rule as the research loader, never forward-filled).
    """
    cols = ["open", "high", "low", "close", "volume", "quote_volume"]
    if not rows:
        return pd.DataFrame(columns=cols + ["close_time"],
                            index=pd.DatetimeIndex([], tz="UTC", name="open_time"))
    df = pd.DataFrame([list(r)[:12] for r in rows], columns=KLINE_COLUMNS[: min(12, len(rows[0]))])
    for c in cols:
        df[c] = df[c].astype(float)
    df["open_time"] = df["open_time"].astype("int64")
    df["close_time"] = df["close_time"].astype("int64")
    if server_time_ms is not None:
        df = df[df["close_time"] < int(server_time_ms)]
    df = df.drop_duplicates("open_time").sort_values("open_time")
    idx = pd.to_datetime(df["open_time"], unit="ms", utc=True).rename("open_time")
    out = pd.DataFrame({c: df[c].to_numpy() for c in cols + ["close_time"]}, index=idx)
    zero = out["volume"] == 0
    if zero.any():
        out.loc[zero, ["open", "high", "low", "close"]] = float("nan")
    return out


# ---------------------------------------------------------------------------
# Exchange views
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExchangePosition:
    symbol: str
    market: str
    qty: float                      # signed, negative = short
    entry_price: float = float("nan")
    leverage: float = 1.0


@dataclass(frozen=True)
class StopOrder:
    symbol: str
    market: str
    side: str                       # closing side (SELL protects a long)
    qty: float
    stop_price: float
    order_id: str
    client_id: str = ""


@dataclass(frozen=True)
class OrderResult:
    symbol: str
    side: str
    client_id: str
    status: str
    executed_qty: float
    avg_price: float
    order_id: str = ""
    reduce_only: bool = False


@runtime_checkable
class Venue(Protocol):
    """What the executor and the reconciler need from one market."""

    market: str
    mutating: bool

    def server_time_ms(self) -> int: ...
    def closed_klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame: ...
    def filters(self, symbol: str) -> SymbolFilters: ...
    def mark_prices(self, symbols: Iterable[str]) -> dict[str, float]: ...
    def equity(self, marks: Mapping[str, float]) -> float: ...
    def free_quote(self) -> float: ...
    def positions(self, marks: Optional[Mapping[str, float]] = None) -> dict[str, ExchangePosition]: ...
    def open_stops(self) -> list[StopOrder]: ...
    def find_order(self, symbol: str, client_id: str) -> Optional[OrderResult]: ...
    def market_order(self, symbol: str, side: str, qty: float, client_id: str,
                     reduce_only: bool = False) -> OrderResult: ...
    def find_stop(self, symbol: str, client_id: str) -> Optional[StopOrder]: ...
    def place_stop(self, symbol: str, side: str, qty: float, stop_price: float,
                   client_id: str) -> StopOrder: ...
    def cancel_stop(self, stop: StopOrder) -> None: ...
    def replace_stop(self, old: StopOrder, qty: float, stop_price: float, client_id: str) -> StopOrder: ...
    def prepare_symbol(self, symbol: str, leverage: int) -> None: ...
    def maint_margin_rate(self, symbol: str) -> float: ...
    def funding_history(self, symbol: str) -> pd.Series: ...


def _f(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _http_error_code(exc: Exception) -> Optional[int]:
    resp = getattr(exc, "response", None)
    if resp is None:
        return getattr(exc, "code", None)
    try:
        return resp.json().get("code")
    except Exception:
        return None


def _base_asset(symbol: str, quote: str) -> str:
    return symbol[: -len(quote)] if symbol.endswith(quote) else symbol


class SpotVenue:
    """Spot market through :class:`core.binance_client.BinanceClient`."""

    market = "spot"
    mutating = True

    def __init__(self, client: Any, symbols: Iterable[str], quote: str = "USDT"):
        self.client = client
        self.symbols = tuple(symbols)
        self.quote = quote
        self._filters: dict[str, SymbolFilters] = {}

    # -- market data -----------------------------------------------------
    def server_time_ms(self) -> int:
        return int(self.client.get_server_time())

    def closed_klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
        rows = self.client.get_klines(symbol, interval=interval, limit=min(int(limit), 1000))
        return klines_frame(rows, self.server_time_ms())

    def filters(self, symbol: str) -> SymbolFilters:
        if symbol not in self._filters:
            info = self.client.get_exchange_info(symbol)
            entries = [s for s in info.get("symbols", []) if s.get("symbol") == symbol]
            if not entries:
                raise ReconciliationError(f"{symbol}: not in spot exchangeInfo")
            self._filters[symbol] = parse_symbol_filters(entries[0], "spot")
        return self._filters[symbol]

    def mark_prices(self, symbols: Iterable[str]) -> dict[str, float]:
        return {s: _f(self.client.get_ticker_24hr(s).get("lastPrice")) for s in symbols}

    # -- account ---------------------------------------------------------
    def _balances(self) -> dict[str, float]:
        acct = self.client.get_account()
        return {b["asset"]: _f(b.get("free"), 0.0) + _f(b.get("locked"), 0.0)
                for b in acct.get("balances", [])}

    def equity(self, marks: Mapping[str, float]) -> float:
        """USDT plus the bot universe's base assets valued at ``marks`` (other assets ignored)."""
        bal = self._balances()
        total = bal.get(self.quote, 0.0)
        for s in self.symbols:
            q = bal.get(_base_asset(s, self.quote), 0.0)
            if q:
                px = marks.get(s)
                if px is None or not math.isfinite(px):
                    raise ReconciliationError(f"{s}: no price to value a balance of {q}")
                total += q * px
        return float(total)

    def free_quote(self) -> float:
        acct = self.client.get_account()
        for b in acct.get("balances", []):
            if b.get("asset") == self.quote:
                return _f(b.get("free"), 0.0)
        return 0.0

    def positions(self, marks: Optional[Mapping[str, float]] = None) -> dict[str, ExchangePosition]:
        bal = self._balances()
        out = {}
        for s in self.symbols:
            q = bal.get(_base_asset(s, self.quote), 0.0)
            if q > 0:
                out[s] = ExchangePosition(s, "spot", q)
        return out

    def open_stops(self) -> list[StopOrder]:
        out = []
        for o in self.client.get_open_orders() or []:
            if o.get("symbol") not in self.symbols or str(o.get("type", "")) not in SPOT_STOP_TYPES:
                continue
            out.append(StopOrder(o["symbol"], "spot", str(o.get("side", "")).upper(),
                                 _f(o.get("origQty"), 0.0) - _f(o.get("executedQty"), 0.0),
                                 _f(o.get("stopPrice")), str(o.get("orderId")), str(o.get("clientOrderId", ""))))
        return out

    # -- orders ----------------------------------------------------------
    @staticmethod
    def _result(symbol: str, side: str, client_id: str, o: Mapping[str, Any]) -> OrderResult:
        qty = _f(o.get("executedQty"), 0.0)
        quote = _f(o.get("cummulativeQuoteQty"), 0.0)
        avg = quote / qty if qty > 0 and quote > 0 else _f(o.get("price"))
        return OrderResult(symbol, side, client_id, str(o.get("status", "")), qty, avg,
                           str(o.get("orderId", "")))

    def find_order(self, symbol: str, client_id: str) -> Optional[OrderResult]:
        try:
            o = self.client.get_order(symbol, orig_client_order_id=client_id)
        except Exception as exc:
            if _http_error_code(exc) == SPOT_ORDER_NOT_FOUND:
                return None
            raise
        return self._result(symbol, str(o.get("side", "")).upper(), client_id, o)

    def market_order(self, symbol: str, side: str, qty: float, client_id: str,
                     reduce_only: bool = False) -> OrderResult:
        o = self.client.create_order(symbol, side, "MARKET", qty, new_client_order_id=client_id)
        return self._result(symbol, side, client_id, o)

    def find_stop(self, symbol: str, client_id: str) -> Optional[StopOrder]:
        for st in self.open_stops():
            if st.symbol == symbol and st.client_id == client_id:
                return st
        return None

    def place_stop(self, symbol: str, side: str, qty: float, stop_price: float, client_id: str) -> StopOrder:
        o = self.client.create_order(symbol, side, "STOP_LOSS", qty, stop_price=stop_price,
                                     new_client_order_id=client_id)
        return StopOrder(symbol, "spot", side, qty, stop_price, str(o.get("orderId")), client_id)

    def cancel_stop(self, stop: StopOrder) -> None:
        self.client.cancel_order(stop.symbol, int(stop.order_id))

    def replace_stop(self, old: StopOrder, qty: float, stop_price: float, client_id: str) -> StopOrder:
        """cancelReplace STOP_ON_FAILURE; if the cancel leg succeeded but the new
        stop failed the position is unprotected: place a fresh stop."""
        from core.binance_client import CancelReplaceError

        try:
            res = self.client.cancel_replace_order(
                old.symbol, int(old.order_id), old.side, "STOP_LOSS", qty,
                stop_price=stop_price, new_client_order_id=client_id)
        except CancelReplaceError as exc:
            if exc.cancel_succeeded:
                return self.place_stop(old.symbol, old.side, qty, stop_price, client_id)
            raise StopPlacementError(f"{old.symbol}: cancelReplace failed: {exc}") from exc
        new = res.get("newOrderResponse") or {}
        return StopOrder(old.symbol, "spot", old.side, qty, stop_price, str(new.get("orderId")), client_id)

    def prepare_symbol(self, symbol: str, leverage: int) -> None:
        if leverage != 1:
            raise ReconciliationError("spot positions cannot be leveraged")

    def maint_margin_rate(self, symbol: str) -> float:
        return 0.0

    def funding_history(self, symbol: str) -> pd.Series:
        raise ReconciliationError("spot has no funding")


class FuturesVenue:
    """USDT-M perps through :class:`core.binance_futures_client.BinanceFuturesClient`."""

    market = "futures"
    mutating = True

    def __init__(self, client: Any, symbols: Iterable[str]):
        self.client = client
        self.symbols = tuple(symbols)
        self._filters: dict[str, SymbolFilters] = {}
        self._prepared: set[str] = set()
        self._one_way = False

    def server_time_ms(self) -> int:
        return int(self.client.server_time())

    def closed_klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
        df = self.client.klines(symbol, interval, limit=min(int(limit), 1500), closed_only=True)
        if df.empty:
            return klines_frame([])
        out = df[["open", "high", "low", "close", "volume", "quote_volume", "close_time"]].copy()
        zero = out["volume"] == 0
        if zero.any():
            out.loc[zero, ["open", "high", "low", "close"]] = float("nan")
        return out

    def filters(self, symbol: str) -> SymbolFilters:
        if not self._filters:
            info = self.client.exchange_info()
            for entry in info.get("symbols", []):
                if entry.get("symbol") in self.symbols:
                    self._filters[entry["symbol"]] = parse_symbol_filters(entry, "futures")
        if symbol not in self._filters:
            raise ReconciliationError(f"{symbol}: not in futures exchangeInfo")
        return self._filters[symbol]

    def mark_prices(self, symbols: Iterable[str]) -> dict[str, float]:
        data = self.client.premium_index()
        rows = data if isinstance(data, list) else [data]
        marks = {r.get("symbol"): _f(r.get("markPrice")) for r in rows}
        return {s: marks.get(s, float("nan")) for s in symbols}

    def equity(self, marks: Mapping[str, float]) -> float:
        acct = self.client.account()
        return _f(acct.get("totalMarginBalance"), 0.0)

    def free_quote(self) -> float:
        acct = self.client.account()
        return _f(acct.get("availableBalance"), 0.0)

    def positions(self, marks: Optional[Mapping[str, float]] = None) -> dict[str, ExchangePosition]:
        out = {}
        for p in self.client.position_risk() or []:
            s = p.get("symbol")
            q = _f(p.get("positionAmt"), 0.0)
            if s in self.symbols and q != 0:
                out[s] = ExchangePosition(s, "futures", q, _f(p.get("entryPrice")), _f(p.get("leverage"), 1.0))
        return out

    def open_stops(self) -> list[StopOrder]:
        out = []
        for o in self.client.open_algo_orders() or []:
            if o.get("symbol") not in self.symbols:
                continue
            otype = str(o.get("orderType", o.get("type", ""))).upper()
            if otype and otype != "STOP_MARKET":
                continue
            out.append(StopOrder(o["symbol"], "futures", str(o.get("side", "")).upper(),
                                 _f(o.get("quantity", o.get("origQty")), 0.0),
                                 _f(o.get("triggerPrice", o.get("stopPrice"))),
                                 str(o.get("algoId", o.get("orderId", ""))),
                                 str(o.get("clientAlgoId", o.get("clientOrderId", "")))))
        return out

    def find_order(self, symbol: str, client_id: str) -> Optional[OrderResult]:
        from core.binance_futures_client import BinanceFuturesError

        try:
            o = self.client.query_order(symbol, client_order_id=client_id)
        except BinanceFuturesError as exc:
            if exc.code == FUTURES_ORDER_NOT_FOUND or exc.status == 404:
                return None
            raise
        return self._result(symbol, str(o.get("side", "")).upper(), client_id, o)

    @staticmethod
    def _result(symbol: str, side: str, client_id: str, o: Mapping[str, Any]) -> OrderResult:
        return OrderResult(symbol, side, client_id, str(o.get("status", "")),
                           _f(o.get("executedQty"), 0.0), _f(o.get("avgPrice")),
                           str(o.get("orderId", "")), bool(o.get("reduceOnly", False)))

    def market_order(self, symbol: str, side: str, qty: float, client_id: str,
                     reduce_only: bool = False) -> OrderResult:
        o = self.client.new_order(symbol, side, "MARKET", qty, client_id, reduce_only=reduce_only)
        return self._result(symbol, side, client_id, o)

    def find_stop(self, symbol: str, client_id: str) -> Optional[StopOrder]:
        for st in self.open_stops():
            if st.symbol == symbol and st.client_id == client_id:
                return st
        return None

    def place_stop(self, symbol: str, side: str, qty: float, stop_price: float, client_id: str) -> StopOrder:
        o = self.client.new_stop_market_algo(symbol, side, qty, stop_price, client_id,
                                             reduce_only=True, working_type="MARK_PRICE")
        return StopOrder(symbol, "futures", side, qty, stop_price, str(o.get("algoId", "")), client_id)

    def cancel_stop(self, stop: StopOrder) -> None:
        algo_id = int(stop.order_id) if str(stop.order_id).isdigit() else None
        self.client.cancel_algo_order(stop.symbol, algo_id=algo_id,
                                      client_algo_id=None if algo_id is not None else stop.client_id)

    def replace_stop(self, old: StopOrder, qty: float, stop_price: float, client_id: str) -> StopOrder:
        """New reduceOnly stop first (never unprotected), then cancel the old one."""
        new = self.place_stop(old.symbol, old.side, qty, stop_price, client_id)
        try:
            self.cancel_stop(old)
        except Exception as exc:  # duplicate reduceOnly stop: harmless, reconciler cancels it
            logger.warning("%s: could not cancel replaced stop %s: %s", old.symbol, old.order_id, exc)
        return new

    def prepare_symbol(self, symbol: str, leverage: int) -> None:
        """One-way mode, ISOLATED margin and leverage (PLAN §4.4 steps 1-2)."""
        if symbol in self._prepared:
            return
        if not self._one_way:
            self.client.set_one_way_mode()
            self._one_way = True
        self.client.set_margin_type(symbol, "ISOLATED")
        self.client.set_leverage(symbol, int(leverage))
        self._prepared.add(symbol)

    def maint_margin_rate(self, symbol: str) -> float:
        brackets = self.client.leverage_bracket(symbol)
        if not brackets:
            raise ReconciliationError(f"{symbol}: no leverage bracket")
        first = min(brackets, key=lambda b: _f(b.get("notionalFloor"), 0.0))
        return _f(first.get("maintMarginRatio"))

    def funding_history(self, symbol: str) -> pd.Series:
        df = self.client.funding_rate(symbol, limit=1000)
        return df["funding_rate"].astype(float)


class PaperVenue:
    """
    Simulated venue for ``TRADING_MODE=dry_run`` (and the market not covered by
    ``spot_demo`` / ``futures_testnet``).

    Market data (server time, closed klines, filters, funding) comes from
    ``data`` (a real venue used read-only, or a test double). Orders fill at
    the last mark set with :meth:`set_marks` and pay ``fee_rate``; stops are
    kept in the book and triggered by :meth:`process_bar`. Nothing is ever sent
    to an exchange. ``book`` is a plain dict persisted in :class:`LiveState`.
    """

    mutating = False

    def __init__(self, market: str, data: Any, book: dict, fee_rate: float, symbols: Iterable[str] = ()):
        self.market = market
        self.data = data
        self.book = book
        self.fee_rate = float(fee_rate)
        self.symbols = tuple(symbols)
        book.setdefault("cash", 0.0)
        book.setdefault("positions", {})
        book.setdefault("entry", {})
        book.setdefault("orders", {})
        book.setdefault("stops", {})
        self.marks: dict[str, float] = {}

    # -- market data (read-only delegation) ------------------------------
    def server_time_ms(self) -> int:
        return int(self.data.server_time_ms())

    def closed_klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
        return self.data.closed_klines(symbol, interval, limit)

    def filters(self, symbol: str) -> SymbolFilters:
        return self.data.filters(symbol)

    def funding_history(self, symbol: str) -> pd.Series:
        return self.data.funding_history(symbol)

    def set_marks(self, marks: Mapping[str, float]) -> None:
        self.marks.update({k: float(v) for k, v in marks.items() if v is not None and math.isfinite(v)})

    def mark_prices(self, symbols: Iterable[str]) -> dict[str, float]:
        return {s: self.marks.get(s, float("nan")) for s in symbols}

    # -- account ---------------------------------------------------------
    def _qty(self, symbol: str) -> float:
        return float(self.book["positions"].get(symbol, 0.0))

    def equity(self, marks: Mapping[str, float]) -> float:
        total = float(self.book["cash"])
        for s, q in self.book["positions"].items():
            px = marks.get(s, self.marks.get(s))
            if px is None or not math.isfinite(px):
                raise ReconciliationError(f"{s}: no price to value the paper position")
            if self.market == "spot":
                total += q * px
            else:
                total += q * (px - float(self.book["entry"].get(s, px)))
        return total

    def free_quote(self) -> float:
        if self.market == "spot":
            return float(self.book["cash"])
        return self.equity(self.marks)

    def positions(self, marks: Optional[Mapping[str, float]] = None) -> dict[str, ExchangePosition]:
        return {s: ExchangePosition(s, self.market, float(q), float(self.book["entry"].get(s, float("nan"))))
                for s, q in self.book["positions"].items() if q != 0}

    def open_stops(self) -> list[StopOrder]:
        return [StopOrder(**d) for d in self.book["stops"].values()]

    # -- orders ----------------------------------------------------------
    def _apply_fill(self, symbol: str, signed_qty: float, price: float) -> None:
        q0 = self._qty(symbol)
        q1 = q0 + signed_qty
        fee = abs(signed_qty) * price * self.fee_rate
        if self.market == "spot":
            self.book["cash"] = float(self.book["cash"]) - signed_qty * price - fee
        else:
            entry = float(self.book["entry"].get(symbol, price))
            closed = 0.0
            if q0 != 0 and (q1 == 0 or math.copysign(1, q1) != math.copysign(1, q0) or abs(q1) < abs(q0)):
                closed = min(abs(signed_qty), abs(q0)) * math.copysign(1, q0)
                self.book["cash"] = float(self.book["cash"]) + closed * (price - entry)
            if q1 != 0 and (q0 == 0 or math.copysign(1, q1) != math.copysign(1, q0)):
                self.book["entry"][symbol] = price
            elif q1 != 0 and abs(q1) > abs(q0):
                self.book["entry"][symbol] = (abs(q0) * entry + abs(signed_qty) * price) / abs(q1)
            self.book["cash"] = float(self.book["cash"]) - fee
        if abs(q1) < 1e-15:
            self.book["positions"].pop(symbol, None)
            self.book["entry"].pop(symbol, None)
        else:
            self.book["positions"][symbol] = q1
            if self.market == "spot":
                self.book["entry"].setdefault(symbol, price)

    def find_order(self, symbol: str, client_id: str) -> Optional[OrderResult]:
        d = self.book["orders"].get(client_id)
        return OrderResult(**d) if d is not None else None

    def market_order(self, symbol: str, side: str, qty: float, client_id: str,
                     reduce_only: bool = False) -> OrderResult:
        if client_id in self.book["orders"]:
            return OrderResult(**self.book["orders"][client_id])
        px = self.marks.get(symbol)
        if px is None or not math.isfinite(px):
            raise ReconciliationError(f"{symbol}: no mark price for a paper fill")
        signed = qty if side == "BUY" else -qty
        q0 = self._qty(symbol)
        if reduce_only and (q0 == 0 or math.copysign(1, signed) == math.copysign(1, q0)):
            raise ReconciliationError(f"{symbol}: reduce-only order would increase the position")
        if reduce_only:
            signed = math.copysign(min(abs(signed), abs(q0)), signed)
        if self.market == "spot" and signed < 0 and abs(signed) > q0 + 1e-12:
            raise ReconciliationError(f"{symbol}: paper spot sell above the held balance")
        self._apply_fill(symbol, signed, px)
        res = OrderResult(symbol, side, client_id, "FILLED", abs(signed), px, f"paper-{client_id}", reduce_only)
        self.book["orders"][client_id] = asdict(res)
        return res

    def find_stop(self, symbol: str, client_id: str) -> Optional[StopOrder]:
        d = self.book["stops"].get(client_id)
        return StopOrder(**d) if d is not None else None

    def place_stop(self, symbol: str, side: str, qty: float, stop_price: float, client_id: str) -> StopOrder:
        st = StopOrder(symbol, self.market, side, float(qty), float(stop_price), f"paper-{client_id}", client_id)
        self.book["stops"][client_id] = asdict(st)
        return st

    def cancel_stop(self, stop: StopOrder) -> None:
        self.book["stops"].pop(stop.client_id, None)

    def replace_stop(self, old: StopOrder, qty: float, stop_price: float, client_id: str) -> StopOrder:
        self.cancel_stop(old)
        return self.place_stop(old.symbol, old.side, qty, stop_price, client_id)

    def prepare_symbol(self, symbol: str, leverage: int) -> None:
        if self.market == "spot" and leverage != 1:
            raise ReconciliationError("spot positions cannot be leveraged")

    def maint_margin_rate(self, symbol: str) -> float:
        return 0.01 if self.market == "futures" else 0.0

    def process_bar(self, symbol: str, bar: Mapping[str, float]) -> Optional[OrderResult]:
        """Trigger the paper stops of ``symbol`` on one closed bar (gap-aware fill)."""
        q = self._qty(symbol)
        for cid, d in list(self.book["stops"].items()):
            if d["symbol"] != symbol:
                continue
            if q == 0:
                del self.book["stops"][cid]
                continue
            o, h, low = _f(bar.get("open")), _f(bar.get("high")), _f(bar.get("low"))
            stop = float(d["stop_price"])
            if q > 0 and math.isfinite(low) and low <= stop:
                px = min(stop, o) if math.isfinite(o) else stop
            elif q < 0 and math.isfinite(h) and h >= stop:
                px = max(stop, o) if math.isfinite(o) else stop
            else:
                continue
            self._apply_fill(symbol, -q, px)
            del self.book["stops"][cid]
            res = OrderResult(symbol, "SELL" if q > 0 else "BUY", cid, "FILLED", abs(q), px, d["order_id"], True)
            logger.warning("PAPER stop %s %s filled at %s", symbol, cid, px)
            return res
        return None


# ---------------------------------------------------------------------------
# Local state
# ---------------------------------------------------------------------------

@dataclass
class LocalPosition:
    """What the bot believes it holds on one venue."""

    symbol: str
    market: str
    qty: float
    stop_price: Optional[float] = None
    stop_client_id: Optional[str] = None
    stop_order_id: Optional[str] = None


@dataclass
class LiveState:
    """
    Persistent state of the live bot (JSON, atomic writes).

    ``positions[market][symbol]`` are :class:`LocalPosition` dicts; ``locks``
    maps a stopped-out symbol to the side it was stopped on (the symbol stays
    flat until its signal resets); ``blocked`` holds the per-symbol kill-switch
    set when a stop could not be placed (manual release); ``paper`` holds the
    :class:`PaperVenue` books.
    """

    positions: dict = field(default_factory=lambda: {"spot": {}, "futures": {}})
    locks: dict = field(default_factory=dict)
    blocked: dict = field(default_factory=dict)
    paper: dict = field(default_factory=dict)
    last_run_day: Optional[str] = None
    last_bar: dict = field(default_factory=dict)
    path: Optional[Path] = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path | str | None) -> "LiveState":
        if path is None:
            return cls()
        path = Path(path)
        if not path.exists():
            return cls(path=path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            st = cls(**raw)
        except (ValueError, TypeError) as exc:
            # A corrupt state must not silently drop positions or locks.
            raise ReconciliationError(f"corrupt live state {path}: {exc}") from exc
        st.path = path
        st.positions.setdefault("spot", {})
        st.positions.setdefault("futures", {})
        return st

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if k != "path"}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, market: str, symbol: str) -> Optional[LocalPosition]:
        d = self.positions.get(market, {}).get(symbol)
        return LocalPosition(**d) if d is not None else None

    def put(self, pos: LocalPosition) -> None:
        if pos.qty == 0:
            self.positions.setdefault(pos.market, {}).pop(pos.symbol, None)
        else:
            self.positions.setdefault(pos.market, {})[pos.symbol] = asdict(pos)

    def drop(self, market: str, symbol: str) -> None:
        self.positions.setdefault(market, {}).pop(symbol, None)


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReconciliationAction:
    kind: str          # place_stop | cancel_stop | replace_stop | divergence | closed_externally | alert
    market: str
    symbol: str
    detail: str = ""
    executed: bool = False


@dataclass
class ReconciliationReport:
    ts: str
    actions: list = field(default_factory=list)

    def of_kind(self, kind: str) -> list[ReconciliationAction]:
        return [a for a in self.actions if a.kind == kind]

    @property
    def ok(self) -> bool:
        return not any(a.kind in ("divergence", "alert", "closed_externally") for a in self.actions)


def closing_side(qty: float) -> str:
    """Side of the order that closes a position of signed ``qty``."""
    return "SELL" if qty > 0 else "BUY"


StopPriceFn = Callable[[str, str, int], Optional[float]]


class Reconciler:
    """
    Compare :class:`LiveState` with the venues and fix what can be fixed.

    ``act=False`` only reports the actions (audit). ``stop_price_fn(market,
    symbol, side)`` gives a catastrophe stop price when the local state has
    none. ``alert`` receives every divergence / failure message.
    """

    def __init__(self, venues: Mapping[str, Venue], state: LiveState, *,
                 stop_price_fn: Optional[StopPriceFn] = None,
                 alert: Optional[Callable[[str], None]] = None,
                 act: bool = True, qty_rel_tol: float = 0.01):
        self.venues = dict(venues)
        self.state = state
        self.stop_price_fn = stop_price_fn
        self.alert_fn = alert
        self.act = act
        self.qty_rel_tol = qty_rel_tol

    def _alert(self, msg: str) -> None:
        logger.warning("RECONCILIATION: %s", msg)
        if self.alert_fn is not None:
            try:
                self.alert_fn(msg)
            except Exception:  # alerting must never break reconciliation
                logger.exception("reconciliation alert callback failed")

    def _same_qty(self, a: float, b: float, filters: Optional[SymbolFilters]) -> bool:
        step = float(filters.step_size) if filters is not None else 0.0
        return abs(a - b) <= max(step * 1.0001, self.qty_rel_tol * max(abs(a), abs(b)), _EPS)

    def run_once(self, now: Optional[datetime] = None,
                 marks: Optional[Mapping[str, Mapping[str, float]]] = None) -> ReconciliationReport:
        now = now or datetime.now(timezone.utc)
        report = ReconciliationReport(ts=now.isoformat())
        for market, venue in self.venues.items():
            try:
                self._reconcile_venue(market, venue, now, report,
                                      (marks or {}).get(market))
            except Exception as exc:
                report.actions.append(ReconciliationAction("alert", market, "*", f"reconciliation failed: {exc}"))
                self._alert(f"{market}: reconciliation failed: {exc}")
        if self.act:
            self.state.save()
        return report

    def _reconcile_venue(self, market: str, venue: Venue, now: datetime, report: ReconciliationReport,
                         marks: Optional[Mapping[str, float]]) -> None:
        ex_pos = venue.positions(marks)
        stops = venue.open_stops()
        local = self.state.positions.setdefault(market, {})
        symbols = sorted(set(local) | set(ex_pos) | {s.symbol for s in stops})
        need_marks = [s for s in symbols if s in ex_pos and (marks is None or s not in marks)]
        if need_marks:
            marks = {**(marks or {}), **venue.mark_prices(need_marks)}
        marks = marks or {}

        for sym in symbols:
            try:
                filters = venue.filters(sym)
            except Exception:
                filters = None
            ex = ex_pos.get(sym)
            ex_qty = ex.qty if ex is not None else 0.0
            px = marks.get(sym, float("nan"))
            if ex_qty and filters is not None and math.isfinite(px) and filters.is_dust(ex_qty, px):
                ex_qty = 0.0   # dust: cannot be traded or protected
            loc = self.state.get(market, sym)
            loc_qty = loc.qty if loc is not None else 0.0

            # 1. Quantities.
            if not self._same_qty(ex_qty, loc_qty, filters):
                if loc_qty != 0 and ex_qty == 0:
                    kind = "closed_externally"
                    detail = f"local {loc_qty} but no position on the exchange (stop filled or manual close)"
                else:
                    kind = "divergence"
                    detail = f"local qty {loc_qty} != exchange qty {ex_qty}"
                report.actions.append(ReconciliationAction(kind, market, sym, detail, executed=self.act))
                self._alert(f"{market} {sym}: {detail}")
                if self.act:
                    if ex_qty == 0:
                        if kind == "closed_externally" and loc is not None and loc.stop_price is not None:
                            self.state.locks[sym] = 1 if loc_qty > 0 else -1
                        self.state.drop(market, sym)
                        loc = None
                    else:
                        same_side = loc is not None and loc_qty * ex_qty > 0
                        loc = LocalPosition(sym, market, ex_qty,
                                            loc.stop_price if same_side else None,
                                            loc.stop_client_id if same_side else None,
                                            loc.stop_order_id if same_side else None)
                        self.state.put(loc)

            # 2. Stops.
            sym_stops = [s for s in stops if s.symbol == sym]
            if ex_qty == 0:
                for st in sym_stops:
                    self._cancel(venue, st, "orphan stop (no position)", report)
                continue
            side = closing_side(ex_qty)
            good = [s for s in sym_stops if s.side == side]
            for st in sym_stops:
                if st.side != side:
                    self._cancel(venue, st, "orphan stop (wrong side)", report)
            keep: Optional[StopOrder] = None
            if good:
                preferred = [s for s in good if loc is not None and loc.stop_client_id
                             and s.client_id == loc.stop_client_id]
                keep = preferred[0] if preferred else min(good, key=lambda s: abs(s.qty - abs(ex_qty)))
                for st in good:
                    if st is not keep:
                        self._cancel(venue, st, "duplicate stop", report)
            if keep is not None:
                stop_price: Optional[float] = keep.stop_price
            elif loc is not None and loc.stop_price is not None:
                stop_price = loc.stop_price
            else:
                stop_price = None
            if stop_price is None and self.stop_price_fn is not None:
                stop_price = self.stop_price_fn(market, sym, 1 if ex_qty > 0 else -1)
            cid = f"{now:%Y%m%d%H%M}-REC-{sym}"[:36]

            if keep is None:
                if stop_price is None or not math.isfinite(stop_price) or stop_price <= 0:
                    msg = "position WITHOUT stop and no stop price known"
                    report.actions.append(ReconciliationAction("alert", market, sym, msg))
                    self._alert(f"{market} {sym}: {msg}")
                    continue
                if filters is not None:
                    stop_price = filters.round_price(stop_price, "down" if ex_qty > 0 else "up")
                qty = filters.round_qty(abs(ex_qty)) if filters is not None else abs(ex_qty)
                detail = f"position {ex_qty} without stop: {side} {qty} @ {stop_price}"
                executed = False
                if self.act:
                    try:
                        st = venue.find_stop(sym, cid) or venue.place_stop(sym, side, qty, stop_price, cid)
                        executed = True
                        self._record_stop(market, sym, ex_qty, st)
                    except Exception as exc:
                        detail += f" FAILED: {exc}"
                        self._alert(f"{market} {sym}: could not place the missing stop: {exc}")
                report.actions.append(ReconciliationAction("place_stop", market, sym, detail, executed))
                if executed:
                    self._alert(f"{market} {sym}: {detail}")
            elif not self._same_qty(keep.qty, abs(ex_qty), filters):
                qty = filters.round_qty(abs(ex_qty)) if filters is not None else abs(ex_qty)
                detail = f"stop qty {keep.qty} != position {ex_qty}: replace with {qty} @ {keep.stop_price}"
                executed = False
                if self.act:
                    try:
                        st = venue.replace_stop(keep, qty, keep.stop_price, cid)
                        executed = True
                        self._record_stop(market, sym, ex_qty, st)
                    except Exception as exc:
                        detail += f" FAILED: {exc}"
                        self._alert(f"{market} {sym}: could not replace the stop: {exc}")
                report.actions.append(ReconciliationAction("replace_stop", market, sym, detail, executed))
            elif self.act:
                self._record_stop(market, sym, ex_qty, keep)

    def _record_stop(self, market: str, sym: str, qty: float, st: StopOrder) -> None:
        self.state.put(LocalPosition(sym, market, qty, st.stop_price, st.client_id, st.order_id))

    def _cancel(self, venue: Venue, st: StopOrder, why: str, report: ReconciliationReport) -> None:
        executed = False
        detail = f"{why}: {st.side} {st.qty} @ {st.stop_price} id={st.order_id}"
        if self.act:
            try:
                venue.cancel_stop(st)
                executed = True
            except Exception as exc:
                detail += f" FAILED: {exc}"
                self._alert(f"{st.market} {st.symbol}: could not cancel stop {st.order_id}: {exc}")
        report.actions.append(ReconciliationAction("cancel_stop", st.market, st.symbol, detail, executed))

    def run_forever(self, interval: float = RECONCILE_INTERVAL_SECONDS,
                    should_stop: Callable[[], bool] = lambda: False,
                    sleep: Callable[[float], None] = time.sleep) -> None:
        """Reconcile every ``interval`` seconds (PLAN §7.7) until ``should_stop()``."""
        while not should_stop():
            self.run_once()
            sleep(interval)
