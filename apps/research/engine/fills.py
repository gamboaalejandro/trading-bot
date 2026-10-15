"""
Fill rules for the research backtests (PLAN.md §2.0, §1.4, report 07 §2.2-2.3).

- Signals are computed on the CLOSE of bar ``t`` and filled at ``open[t + delay]``
  (``delay_bars = 1`` in the base case, 2 in the "+1 bar" stress test), plus
  slippage. A bar's index label is its OPEN time (UTC), as in the data loader.
- Protective stops are evaluated on every bar after the entry:

  * ``gap_aware`` (base case): long fill = ``min(stop, open)``, short fill =
    ``max(stop, open)``; a gap through the stop fills at the open.
  * ``worst_bar`` (mandatory stress test): long fill = bar ``low``, short fill =
    bar ``high``.

  In both modes the stop pays twice the normal slippage (report 07 §2.2).
- Catastrophe stop (§2.0): ``stop(t) = max(stop(t-1), C_t - 3*ATR14(t))`` for
  longs, mirrored for shorts; it only moves in the trade's favour.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from apps.research.engine.costs import slipped_price

__all__ = [
    "FillError",
    "StopFill",
    "STOP_SLIP_MULT",
    "next_open_fill",
    "held_weights",
    "stop_fill",
    "ratchet_stop",
]

StopMode = Literal["gap_aware", "worst_bar"]

# Stops are market orders fired into a moving market: they pay double slippage.
STOP_SLIP_MULT = 2.0


class FillError(ValueError):
    """Raised when a fill cannot be produced from real data (no imputation)."""


@dataclass(frozen=True)
class StopFill:
    """Result of a stop check on one bar."""

    triggered: bool
    price: Optional[float] = None
    gapped: bool = False  # True if the bar opened beyond the stop level


def next_open_fill(
    bars: pd.DataFrame,
    t,
    side: int,
    slip_bps: float = 0.0,
    delay_bars: int = 1,
) -> tuple[pd.Timestamp, float]:
    """
    Fill of a market order decided at the close of bar ``t``.

    Returns ``(fill_time, price)`` where ``fill_time`` is the open time of the bar
    ``delay_bars`` after ``t`` and ``price`` its open moved by ``slip_bps``
    against the order (``side`` = +1 buy, -1 sell). Raises ``FillError`` if that
    bar does not exist or its open is missing (never falls back to a close).
    """
    if delay_bars < 1:
        raise FillError(f"delay_bars must be >= 1 (no same-bar fills), got {delay_bars}")
    if t not in bars.index:
        raise FillError(f"signal bar {t} not in data")
    pos = bars.index.get_loc(t)
    if not isinstance(pos, int):
        raise FillError(f"signal bar {t} is not unique in data")
    fill_pos = pos + delay_bars
    if fill_pos >= len(bars):
        raise FillError(f"no bar {delay_bars} after {t} to fill at")
    fill_time = bars.index[fill_pos]
    open_price = float(bars["open"].iloc[fill_pos])
    if not math.isfinite(open_price):
        raise FillError(f"missing open at {fill_time}")
    return fill_time, slipped_price(open_price, side, slip_bps)


def held_weights(target: pd.DataFrame | pd.Series, delay_bars: int = 1):
    """
    Weights actually held during each bar given targets decided at each bar's close.

    The target set at the close of ``t`` is in force from ``open[t + delay_bars]``,
    so the held weight of bar ``s`` is ``target[s - delay_bars]``; the first
    ``delay_bars`` bars are flat (0).
    """
    if delay_bars < 1:
        raise FillError(f"delay_bars must be >= 1 (no same-bar fills), got {delay_bars}")
    return target.shift(delay_bars).fillna(0.0)


def stop_fill(
    open_: float,
    high: float,
    low: float,
    stop: float,
    side: int,
    mode: StopMode = "gap_aware",
    slip_bps: float = 0.0,
) -> StopFill:
    """
    Check a protective stop on one bar of a position with direction ``side``.

    A long (+1) stop triggers when ``low <= stop``; a short (-1) stop when
    ``high >= stop``. The exit price follows ``mode`` (see module docstring) and
    then pays ``STOP_SLIP_MULT * slip_bps`` against the position.
    """
    if side not in (1, -1):
        raise FillError(f"side must be +1 (long) or -1 (short), got {side!r}")
    if mode not in ("gap_aware", "worst_bar"):
        raise FillError(f"unknown stop mode {mode!r}")
    for name, value in (("open", open_), ("high", high), ("low", low), ("stop", stop)):
        if value is None or not math.isfinite(value) or value <= 0:
            raise FillError(f"{name} must be finite and > 0, got {value!r}")

    if side == 1:
        if low > stop:
            return StopFill(False)
        gapped = open_ <= stop
        raw = min(stop, open_) if mode == "gap_aware" else low
        # Exiting a long is a sell.
        return StopFill(True, slipped_price(raw, -1, STOP_SLIP_MULT * slip_bps), gapped)

    if high < stop:
        return StopFill(False)
    gapped = open_ >= stop
    raw = max(stop, open_) if mode == "gap_aware" else high
    # Exiting a short is a buy.
    return StopFill(True, slipped_price(raw, 1, STOP_SLIP_MULT * slip_bps), gapped)


def ratchet_stop(prev_stop: Optional[float], close: float, atr: float, side: int, mult: float = 3.0) -> float:
    """
    One daily update of the catastrophe stop, computed after the close of ``t``.

    Long: ``max(prev_stop, close - mult*atr)``; short: ``min(prev_stop, close + mult*atr)``.
    ``prev_stop=None`` starts a new stop at the entry bar.
    """
    if side not in (1, -1):
        raise FillError(f"side must be +1 (long) or -1 (short), got {side!r}")
    if not (math.isfinite(close) and math.isfinite(atr)) or atr < 0:
        raise FillError(f"close/atr must be finite (atr >= 0), got {close!r}, {atr!r}")
    candidate = close - side * mult * atr
    if prev_stop is None or not math.isfinite(prev_stop):
        return candidate
    return max(prev_stop, candidate) if side == 1 else min(prev_stop, candidate)
