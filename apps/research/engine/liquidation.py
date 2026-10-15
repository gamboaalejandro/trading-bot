"""
Isolated-margin liquidation checks (PLAN.md §1.3, §2.3, §4.2, §7.4; report 04 §2.6).

Isolated margin with ``cumB = 0`` and wallet balance ``Q*EP/L`` gives:

- long:  ``LP = EP * (1 - 1/L) / (1 - MMR)``
- short: ``LP = EP * (1 + 1/L) / (1 + MMR)``

This ignores the bracket's maintenance amount and tier changes [VERIFICAR with
``GET /fapi/v1/leverageBracket``]; the default MMR of 1 % is deliberately
higher than BTC's lowest tier (~0.4 %), which makes it conservative. There is
no mark price in the local data, so wicks are measured on last price
(conservative, declared in every report).

Entry rule: ``dist_liq >= max(3 * dist_stop, worst_wick)`` where ``worst_wick``
is the largest adverse intrabar move ever observed for the symbol up to the
decision bar (expanding and causal).
"""
from __future__ import annotations

import math

import pandas as pd

__all__ = [
    "LiquidationError",
    "DEFAULT_MMR",
    "liq_price",
    "liq_distance",
    "worst_wick",
    "liq_ok",
    "max_safe_leverage",
]

DEFAULT_MMR = 0.01
STOP_DISTANCE_MULT = 3.0


class LiquidationError(ValueError):
    """Invalid inputs for a liquidation computation."""


def _check_side(side: int) -> None:
    if side not in (1, -1):
        raise LiquidationError(f"side must be +1 (long) or -1 (short), got {side!r}")


def liq_price(entry: float, lev: float, side: int, mmr: float = DEFAULT_MMR) -> float:
    """Isolated liquidation price. Long: EP*(1-1/L)/(1-MMR); short: EP*(1+1/L)/(1+MMR)."""
    _check_side(side)
    if not math.isfinite(entry) or entry <= 0:
        raise LiquidationError(f"entry must be finite and > 0, got {entry!r}")
    if not math.isfinite(lev) or lev <= 0:
        raise LiquidationError(f"lev must be finite and > 0, got {lev!r}")
    if not math.isfinite(mmr) or not 0 <= mmr < 1:
        raise LiquidationError(f"mmr must be in [0, 1), got {mmr!r}")
    if side == 1:
        return max(entry * (1.0 - 1.0 / lev) / (1.0 - mmr), 0.0)
    return entry * (1.0 + 1.0 / lev) / (1.0 + mmr)


def liq_distance(entry: float, lev: float, side: int, mmr: float = DEFAULT_MMR) -> float:
    """Adverse move (fraction of entry) that liquidates the position."""
    return abs(liq_price(entry, lev, side, mmr) - entry) / entry


def worst_wick(df_1d: pd.DataFrame, side: int) -> pd.Series:
    """
    Worst adverse intrabar move seen so far, as a positive fraction (expanding, causal).

    For longs the adverse move of bar ``t`` is the larger of ``1 - low/open`` and
    ``1 - low/close[t-1]``; for shorts ``high/open - 1`` and ``high/close[t-1] - 1``.
    The value at ``t`` uses only bars up to and including ``t`` (known at the
    close of ``t``). Bars with missing prices (e.g. ``volume == 0`` filtered to
    NaN) are skipped, never filled.
    """
    _check_side(side)
    missing = {"open", "high", "low", "close"} - set(df_1d.columns)
    if missing:
        raise LiquidationError(f"df_1d lacks columns {sorted(missing)}")
    prev_close = df_1d["close"].shift(1)
    if side == 1:
        from_open = 1.0 - df_1d["low"] / df_1d["open"]
        from_prev = 1.0 - df_1d["low"] / prev_close
    else:
        from_open = df_1d["high"] / df_1d["open"] - 1.0
        from_prev = df_1d["high"] / prev_close - 1.0
    bar_move = pd.concat([from_open, from_prev], axis=1).max(axis=1, skipna=True).clip(lower=0.0)
    out = bar_move.expanding(min_periods=1).max()
    out.name = "worst_wick_long" if side == 1 else "worst_wick_short"
    return out


def liq_ok(entry, stop, lev, side, worst_wick_t, mmr=DEFAULT_MMR) -> bool:
    """
    True if ``dist_liq >= max(3 * dist_stop, worst_wick_t)``.

    ``stop`` must be on the protective side of ``entry``. A missing worst wick
    (not enough history) returns False: without evidence the trade is refused.
    """
    _check_side(side)
    if not math.isfinite(stop) or stop <= 0:
        raise LiquidationError(f"stop must be finite and > 0, got {stop!r}")
    if (side == 1 and stop >= entry) or (side == -1 and stop <= entry):
        raise LiquidationError(f"stop {stop} is not protective for side {side} at entry {entry}")
    if worst_wick_t is None or not math.isfinite(worst_wick_t):
        return False
    dist_stop = abs(entry - stop) / entry
    required = max(STOP_DISTANCE_MULT * dist_stop, float(worst_wick_t))
    return liq_distance(entry, lev, side, mmr) >= required


def max_safe_leverage(entry, stop, side, worst_wick_t, mmr=DEFAULT_MMR, lev_cap: float = 1.0) -> float:
    """
    Highest leverage in ``(0, lev_cap]`` that passes ``liq_ok`` (0.0 if none does).

    Uses the closed form of the isolated liquidation distance, solved for L.
    """
    _check_side(side)
    if worst_wick_t is None or not math.isfinite(worst_wick_t):
        return 0.0
    dist_stop = abs(entry - stop) / entry
    required = max(STOP_DISTANCE_MULT * dist_stop, float(worst_wick_t))
    if side == 1:
        if required >= 1.0:
            return 0.0  # a long can never be more than 100 % away from liquidation
        # 1 - (1 - 1/L)/(1 - m) >= d  <=>  1/L >= 1 - (1 - d)(1 - m)
        inv = 1.0 - (1.0 - required) * (1.0 - mmr)
    else:
        # (1 + 1/L)/(1 + m) - 1 >= d  <=>  1/L >= (1 + d)(1 + m) - 1
        inv = (1.0 + required) * (1.0 + mmr) - 1.0
    if inv <= 0:
        return float(lev_cap)
    lev = min(1.0 / inv, float(lev_cap))
    # Step just inside the boundary if floating point rounding put us outside it.
    if not liq_ok(entry, stop, lev, side, worst_wick_t, mmr):
        lev *= 1.0 - 1e-9
    return lev if liq_ok(entry, stop, lev, side, worst_wick_t, mmr) else 0.0
