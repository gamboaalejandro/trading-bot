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
whose :meth:`Context.history`, :meth:`Context.daily_history` and
:meth:`Context.funding_history` (and the ``daily`` / ``funding`` mapping views)
are truncated at what is available at the close of the current bar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Mapping, Optional, Protocol, runtime_checkable

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
ONE_DAY = pd.Timedelta(days=1)


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


class _AvailableView(Mapping):
    """
    Read-only mapping whose values are truncated to the rows available at ``cutoff``.

    A row labelled ``x`` is available when ``x + lag <= cutoff`` (``lag`` is 1 day
    for daily bars, labelled by their open, and 0 for funding settlements).
    ``cutoff=None`` returns the full objects (vectorized engines, no clock).
    """

    __slots__ = ("_src", "_cutoff", "_lag")

    def __init__(self, src: Mapping, cutoff: Optional[pd.Timestamp], lag: pd.Timedelta):
        self._src = src
        self._cutoff = cutoff
        self._lag = lag

    def __getitem__(self, key):
        obj = self._src[key]
        if self._cutoff is None or obj is None:
            return obj
        end = int(obj.index.searchsorted(self._cutoff - self._lag, side="right"))
        return obj.iloc[:end]

    def __iter__(self) -> Iterator:
        return iter(self._src)

    def __len__(self) -> int:
        return len(self._src)

    def __repr__(self) -> str:
        return f"_AvailableView(keys={list(self._src)}, cutoff={self._cutoff})"


@dataclass
class Context:
    """
    Information available to a strategy at the close of bar ``t``.

    ``history(symbol)`` returns the symbol's frame truncated at ``t`` (inclusive),
    so a strategy cannot look ahead. ``daily_history(symbol)`` returns the 1d
    bars closed by ``t + tf`` (``D + 1 day <= t + tf``) and
    ``funding_history(symbol)`` the settlements with ``tau <= t + tf`` (perps
    only, never BNBUSDT). The ``daily`` and ``funding`` attributes are
    read-only mapping views with the same truncation; assigning to them sets
    the full source data (kept private). With ``t=None`` (vectorized engines,
    no clock) nothing is truncated.
    """

    market: Literal["spot", "futures"]
    t: Optional[pd.Timestamp] = None
    nav: float = float("nan")
    positions: Mapping[str, Position] = field(default_factory=dict)
    kill_switch: Any = None
    params: dict = field(default_factory=dict)
    frames: Mapping[str, pd.DataFrame] = field(default_factory=dict, repr=False)
    tf: Optional[pd.Timedelta] = None
    _pos: dict = field(default_factory=dict, repr=False)
    _daily: Mapping[str, pd.DataFrame] = field(default_factory=dict, repr=False)
    _funding: Mapping[str, pd.Series] = field(default_factory=dict, repr=False)

    def _cutoff(self) -> Optional[pd.Timestamp]:
        """Close time of bar ``t`` (``t + tf``); ``t`` itself when ``tf`` is unknown."""
        if self.t is None:
            return None
        return self.t + (pd.Timedelta(self.tf) if self.tf is not None else pd.Timedelta(0))

    @property
    def daily(self) -> Mapping[str, pd.DataFrame]:
        """Closed 1d bars per symbol, truncated at ``D + 1 day <= t + tf``."""
        return _AvailableView(self._daily, self._cutoff(), ONE_DAY)

    @daily.setter
    def daily(self, value: Mapping[str, pd.DataFrame]) -> None:
        self._daily = dict(value or {})

    @property
    def funding(self) -> Mapping[str, pd.Series]:
        """Funding settlements per symbol, truncated at ``tau <= t + tf``."""
        return _AvailableView(self._funding, self._cutoff(), pd.Timedelta(0))

    @funding.setter
    def funding(self, value: Mapping[str, pd.Series]) -> None:
        self._funding = dict(value or {})

    def daily_history(self, symbol: str, n: Optional[int] = None) -> pd.DataFrame:
        """1d bars of ``symbol`` closed by ``t + tf`` (the last ``n`` if given)."""
        out = self.daily[symbol]
        return out if n is None else out.iloc[-n:]

    def funding_history(self, symbol: str) -> pd.Series:
        """Funding settlements of ``symbol`` with ``tau <= t + tf``."""
        return self.funding[symbol]

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
