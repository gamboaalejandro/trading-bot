"""
Strategy protocols shared by the backtest engines and the live executor (PLAN.md §4.2, §4.3).

Two kinds of strategies exist:

- :class:`TargetWeightStrategy` (daily families: TREND and its overlays). It
  returns an exposure signal ``E`` in ``[-1, 1]`` per symbol and bar. The row
  labelled ``t`` (the bar's OPEN time, as in the data loader) is computed with
  data up to and including the CLOSE of bar ``t`` and is filled by the engine at
  ``open[t + delay_bars]``. Portfolio construction (layer D) and the kill-switch
  are applied by the engine, not by the strategy.
- :class:`EventStrategy` (intraday families with stops: BRK4H, SHOCK, ...). It is
  called once per closed bar and returns :class:`OrderIntent` objects that the
  engine executes at the next bar's open.

Strategies never see future data: the engine hands them a :class:`Context`
whose :meth:`Context.history` is truncated at the current bar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional, Protocol, runtime_checkable

import pandas as pd

__all__ = [
    "Context",
    "Position",
    "OrderIntent",
    "OrderIntentError",
    "TargetWeightStrategy",
    "EventStrategy",
]

Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]


class OrderIntentError(ValueError):
    """An order intent is internally inconsistent."""


@dataclass(frozen=True)
class OrderIntent:
    """
    What a strategy wants done at the next bar's open (PLAN §4.2).

    Interpretation by :mod:`apps.research.engine.event_bt`:

    - **Entry** (``reduce_only=False``): BUY opens a long, SELL a short. Size is
      ``qty`` (units) if given, else ``target_weight`` (fraction of NAV), else
      risk-based (``R * NAV / |entry - stop|``). ``stop_price`` is mandatory: the
      protective stop goes on the exchange with the entry (§7.4).
    - **Exit** (``reduce_only=True`` and no ``stop_price``/``take_profit``):
      market close of ``qty`` units (``None`` = the whole position).
    - **Stop / take-profit update** (``reduce_only=True`` with ``stop_price``
      and/or ``take_profit``): moves the resting orders. The engine only moves a
      stop in the trade's favour (trailing never loosens).

    ``side`` of a reduce-only intent is the closing side (SELL closes a long).
    """

    symbol: str
    side: Side
    qty: Optional[float] = None
    target_weight: Optional[float] = None
    order_type: OrderType = "MARKET"
    stop_price: Optional[float] = None
    reduce_only: bool = False
    tag: str = ""
    take_profit: Optional[float] = None

    def __post_init__(self) -> None:
        if self.side not in ("BUY", "SELL"):
            raise OrderIntentError(f"side must be BUY or SELL, got {self.side!r}")
        if self.order_type not in ("MARKET", "LIMIT"):
            raise OrderIntentError(f"order_type must be MARKET or LIMIT, got {self.order_type!r}")
        if self.qty is not None and (not math.isfinite(self.qty) or self.qty <= 0):
            raise OrderIntentError(f"qty must be finite and > 0, got {self.qty!r}")
        if self.target_weight is not None and (
            not math.isfinite(self.target_weight) or not 0 < self.target_weight <= 1
        ):
            raise OrderIntentError(f"target_weight must be in (0, 1], got {self.target_weight!r}")
        if self.qty is not None and self.target_weight is not None:
            raise OrderIntentError("give qty or target_weight, not both")
        for name in ("stop_price", "take_profit"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise OrderIntentError(f"{name} must be finite and > 0, got {value!r}")

    @property
    def direction(self) -> int:
        """+1 for BUY, -1 for SELL."""
        return 1 if self.side == "BUY" else -1

    @property
    def is_entry(self) -> bool:
        return not self.reduce_only

    @property
    def is_order_update(self) -> bool:
        return self.reduce_only and (self.stop_price is not None or self.take_profit is not None)

    @property
    def is_exit(self) -> bool:
        return self.reduce_only and not self.is_order_update


@dataclass(frozen=True)
class Position:
    """Read-only view of an open position handed to strategies."""

    symbol: str
    side: int                     # +1 long, -1 short
    qty: float                    # absolute units
    entry_price: float
    entry_time: pd.Timestamp
    stop: Optional[float] = None
    take_profit: Optional[float] = None
    bars_held: int = 0


@dataclass
class Context:
    """
    Information available to a strategy at the close of bar ``t``.

    ``history(symbol)`` returns the symbol's frame truncated at ``t`` (inclusive),
    so a strategy cannot look ahead. ``daily`` holds closed 1d bars (event
    engine) and ``funding`` the settlement series (perps only, never BNBUSDT).
    """

    market: Literal["spot", "futures"]
    t: Optional[pd.Timestamp] = None
    nav: float = float("nan")
    positions: Mapping[str, Position] = field(default_factory=dict)
    funding: Mapping[str, pd.Series] = field(default_factory=dict)
    daily: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    kill_switch: Any = None
    params: dict = field(default_factory=dict)
    frames: Mapping[str, pd.DataFrame] = field(default_factory=dict, repr=False)
    _pos: dict = field(default_factory=dict, repr=False)

    def history(self, symbol: str, n: Optional[int] = None) -> pd.DataFrame:
        """Bars of ``symbol`` up to and including ``t`` (the last ``n`` if given)."""
        df = self.frames[symbol]
        if self.t is None:
            out = df
        else:
            end = self._pos.get(symbol)
            if end is None:
                end = int(df.index.searchsorted(self.t, side="right"))
            out = df.iloc[:end]
        return out if n is None else out.iloc[-n:]

    def position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)


@runtime_checkable
class TargetWeightStrategy(Protocol):
    """Daily exposure signal (PLAN §4.2)."""

    name: str
    params: dict
    n_free_params: int

    def signal(self, panel: dict[str, pd.DataFrame], ctx: Context) -> pd.DataFrame:
        """E per symbol (columns) and date (index = bar label, known at its close), in [-1, 1],
        using only data <= t. NaN means "no opinion" and is treated as flat."""
        ...


@runtime_checkable
class EventStrategy(Protocol):
    """Bar-by-bar strategy with stops (PLAN §4.2)."""

    name: str
    params: dict
    n_free_params: int

    def on_bar(self, t, bars: dict[str, pd.Series], ctx: Context) -> list[OrderIntent]:
        """Intents decided at the close of bar ``t``; executed at the next bar's open."""
        ...
