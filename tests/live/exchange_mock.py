"""
In-memory exchange double for the live executor / reconciliation tests (no network).

Market data comes from small deterministic, hand-built OHLCV fixtures (unit
tests only: never used for backtest results).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from apps.live.reconciliation import OrderResult, PaperVenue, StopOrder, SymbolFilters, klines_frame

NOW = datetime(2026, 10, 15, 0, 5, tzinfo=timezone.utc)
DAY_MS = 86_400_000


def make_filters(symbol: str, step="0.00001", tick="0.01", min_notional="5", min_qty=None) -> SymbolFilters:
    return SymbolFilters(symbol=symbol, step_size=Decimal(step), min_qty=Decimal(min_qty or step),
                         max_qty=Decimal("9000"), tick_size=Decimal(tick), min_notional=Decimal(min_notional))


def trend_rows(start_price: float, drift: float, n: int = 600, end: str = "2026-10-15",
               volume: float = 1e5, wiggle: float = 0.02) -> list[list]:
    """Kline rows (Binance layout) for ``n`` daily bars, the last one opening at ``end``.

    Deterministic: ``close_i = p0 * exp(drift * i + wiggle * sin(i / 7))``.
    """
    end_ts = pd.Timestamp(end, tz="UTC")
    rows = []
    prev = start_price
    for i in range(n):
        t = end_ts - pd.Timedelta(days=n - 1 - i)
        close = start_price * math.exp(drift * i + wiggle * math.sin(i / 7.0))
        op = prev
        hi = max(op, close) * 1.01
        lo = min(op, close) * 0.99
        ms = int(t.value // 1_000_000)
        rows.append([ms, f"{op:.2f}", f"{hi:.2f}", f"{lo:.2f}", f"{close:.2f}", f"{volume}",
                     ms + DAY_MS - 1, f"{volume * close}", 1000, "0", "0", "0"])
        prev = close
    return rows


class StaticData:
    """Read-only market data source (what PaperVenue delegates to)."""

    def __init__(self, rows: dict, filters: dict, now: datetime = NOW, funding: dict | None = None):
        self.rows = rows
        self._filters = filters
        self.now = now
        self.funding = funding or {}
        self.calls: list[str] = []

    def server_time_ms(self) -> int:
        self.calls.append("server_time_ms")
        return int(self.now.timestamp() * 1000)

    def closed_klines(self, symbol: str, interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
        self.calls.append(f"closed_klines:{symbol}")
        return klines_frame(self.rows[symbol][-limit:], self.server_time_ms())

    def filters(self, symbol: str) -> SymbolFilters:
        self.calls.append(f"filters:{symbol}")
        return self._filters[symbol]

    def funding_history(self, symbol: str) -> pd.Series:
        self.calls.append(f"funding:{symbol}")
        return self.funding[symbol]


class MockExchange(PaperVenue):
    """A 'real' (mutating) venue held in memory, recording every call.

    ``fail_stops`` makes the next N stop placements/replacements raise.
    """

    mutating = True

    def __init__(self, market: str, data: StaticData, cash: float, fee_rate: float = 0.001,
                 symbols=(), fail_stops: int = 0, fail_orders: int = 0):
        super().__init__(market, data, {"cash": cash}, fee_rate, symbols)
        self.calls: list[tuple] = []
        self.fail_stops = fail_stops
        self.fail_orders = fail_orders

    def positions(self, marks=None):
        self.calls.append(("positions",))
        return super().positions(marks)

    def mark_prices(self, symbols):
        return {s: self.marks.get(s, float("nan")) for s in symbols}

    def market_order(self, symbol, side, qty, client_id, reduce_only=False) -> OrderResult:
        self.calls.append(("market_order", symbol, side, qty, client_id, reduce_only))
        if self.fail_orders > 0:
            self.fail_orders -= 1
            raise RuntimeError("order rejected")
        return super().market_order(symbol, side, qty, client_id, reduce_only)

    def find_order(self, symbol, client_id):
        self.calls.append(("find_order", symbol, client_id))
        return super().find_order(symbol, client_id)

    def place_stop(self, symbol, side, qty, stop_price, client_id) -> StopOrder:
        self.calls.append(("place_stop", symbol, side, qty, stop_price, client_id))
        if self.fail_stops > 0:
            self.fail_stops -= 1
            raise RuntimeError("stop rejected")
        return super().place_stop(symbol, side, qty, stop_price, client_id)

    def replace_stop(self, old, qty, stop_price, client_id) -> StopOrder:
        self.calls.append(("replace_stop", old.symbol, qty, stop_price, client_id))
        if self.fail_stops > 0:
            self.fail_stops -= 1
            raise RuntimeError("stop rejected")
        PaperVenue.cancel_stop(self, old)
        return PaperVenue.place_stop(self, old.symbol, old.side, qty, stop_price, client_id)

    def cancel_stop(self, stop) -> None:
        self.calls.append(("cancel_stop", stop.symbol, stop.order_id))
        super().cancel_stop(stop)

    def prepare_symbol(self, symbol, leverage) -> None:
        self.calls.append(("prepare_symbol", symbol, leverage))

    def writes(self) -> list[tuple]:
        return [c for c in self.calls if c[0] in ("market_order", "place_stop", "replace_stop", "cancel_stop")]


def fixture_data(now: datetime = NOW, extra_days: int = 0) -> StaticData:
    """BTC and ETH trend up, SOL trends down. The bar opening on ``now``'s day is still open.

    ``extra_days`` extends the same deterministic series (same first bar) by N days.
    """
    end = (pd.Timestamp("2026-10-15", tz="UTC") + pd.Timedelta(days=extra_days)).strftime("%Y-%m-%d")
    n = 600 + extra_days
    rows = {
        "BTCUSDT": trend_rows(20_000.0, 0.003, n=n, end=end, volume=1e5),
        "ETHUSDT": trend_rows(1_500.0, 0.002, n=n, end=end, volume=1e6),
        "SOLUSDT": trend_rows(200.0, -0.002, n=n, end=end, volume=1e7),
    }
    filters = {
        "BTCUSDT": make_filters("BTCUSDT", "0.00001", "0.01", "5"),
        "ETHUSDT": make_filters("ETHUSDT", "0.0001", "0.01", "10000"),   # forces a minNotional skip
        "SOLUSDT": make_filters("SOLUSDT", "0.001", "0.01", "5"),
    }
    return StaticData(rows, filters, now)
