"""
Transaction cost model for the research harness (PLAN.md §5.4, report 07 §2.2).

Three cost components are modelled explicitly:

- Commission: a fixed rate per side on the traded notional. Spot 0.10 % (VIP0),
  futures 0.05 % taker / 0.02 % maker. The base case uses taker on every leg.
- Slippage: a base number of basis points chosen by the 30-day median USDT
  volume tier (A > 500M -> 2 bp, B 50M-500M -> 5 bp, C 5M-50M -> 15 bp,
  < 5M -> excluded from the universe), multiplied by
  ``max(1, ATR% / median_90d(ATR%))`` so that it widens in volatile periods.
- Funding (perps only): at every settlement ``tau`` the position held just
  BEFORE ``tau`` pays ``side * notional * F(tau)``; longs pay when F > 0.

``cost_mult`` scales commission and slippage (cost x2 stress test) and
``funding_mult`` scales funding (x0.5 / x2 stress tests). Missing inputs are
never imputed: a NaN where a value is required raises ``CostError``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

__all__ = [
    "CostError",
    "CostModel",
    "TIER_THRESHOLDS",
    "liquidity_tier",
    "slippage_bps",
    "commission",
    "slipped_price",
    "funding_cashflow",
]

# Lower bounds (USDT per day, 30-day median quote volume) of each tier.
TIER_THRESHOLDS: dict[str, float] = {"A": 500e6, "B": 50e6, "C": 5e6}


class CostError(ValueError):
    """Raised when a cost cannot be computed without imputing data."""


def _default_slip() -> dict[str, float]:
    return {"A": 2.0, "B": 5.0, "C": 15.0}


@dataclass(frozen=True)
class CostModel:
    """Commission, slippage and funding parameters (fractions, bps for slippage)."""

    spot_fee: float = 0.0010
    fut_taker: float = 0.0005
    fut_maker: float = 0.0002
    slip_bps: dict = field(default_factory=_default_slip)
    cost_mult: float = 1.0
    funding_mult: float = 1.0

    def __post_init__(self) -> None:
        for name in ("spot_fee", "fut_taker", "fut_maker", "cost_mult", "funding_mult"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise CostError(f"{name} must be a finite non-negative number, got {value!r}")
        missing = set(TIER_THRESHOLDS) - set(self.slip_bps)
        if missing:
            raise CostError(f"slip_bps is missing tiers {sorted(missing)}")

    def fee_rate(self, market: Literal["spot", "futures"], maker: bool = False) -> float:
        """Commission rate per side, already multiplied by ``cost_mult``."""
        if market == "spot":
            base = self.spot_fee
        elif market == "futures":
            base = self.fut_maker if maker else self.fut_taker
        else:
            raise CostError(f"unknown market {market!r}")
        return base * self.cost_mult

    def stressed(self, cost_mult: float = 2.0, funding_mult: Optional[float] = None) -> "CostModel":
        """Copy of the model with stressed multipliers (robustness runs, not new trials)."""
        return CostModel(
            spot_fee=self.spot_fee,
            fut_taker=self.fut_taker,
            fut_maker=self.fut_maker,
            slip_bps=dict(self.slip_bps),
            cost_mult=cost_mult,
            funding_mult=self.funding_mult if funding_mult is None else funding_mult,
        )


def liquidity_tier(quote_vol_30d: float) -> Optional[str]:
    """Liquidity tier from the 30-day median USDT volume; ``None`` means excluded (< 5M)."""
    if quote_vol_30d is None or not math.isfinite(quote_vol_30d):
        raise CostError(f"quote_vol_30d must be finite, got {quote_vol_30d!r}")
    if quote_vol_30d > TIER_THRESHOLDS["A"]:
        return "A"
    if quote_vol_30d >= TIER_THRESHOLDS["B"]:
        return "B"
    if quote_vol_30d >= TIER_THRESHOLDS["C"]:
        return "C"
    return None


def slippage_bps(symbol, t, quote_vol_30d, atr_pct, atr_pct_med90, cm: CostModel) -> float:
    """
    Slippage in basis points for one fill of ``symbol`` at time ``t``.

    ``base_bps[tier(quote_vol_30d)] * max(1, atr_pct / atr_pct_med90) * cm.cost_mult``.
    Raises ``CostError`` if the symbol falls below the tradable tier or any input
    is missing (``symbol`` and ``t`` are used only in error messages).
    """
    tier = liquidity_tier(quote_vol_30d)
    if tier is None:
        raise CostError(
            f"{symbol} at {t}: 30d quote volume {quote_vol_30d:,.0f} USDT < 5M, excluded from universe"
        )
    for name, value in (("atr_pct", atr_pct), ("atr_pct_med90", atr_pct_med90)):
        if value is None or not math.isfinite(value) or value <= 0:
            raise CostError(f"{symbol} at {t}: {name} must be finite and > 0, got {value!r}")
    vol_mult = max(1.0, atr_pct / atr_pct_med90)
    return float(cm.slip_bps[tier]) * vol_mult * cm.cost_mult


def commission(notional: float, market: Literal["spot", "futures"], cm: CostModel, maker: bool = False) -> float:
    """Commission paid (positive number, USDT) on a traded notional of either sign."""
    if not math.isfinite(notional):
        raise CostError(f"notional must be finite, got {notional!r}")
    return abs(notional) * cm.fee_rate(market, maker=maker)


def slipped_price(price: float, side: int, slip_bps: float) -> float:
    """Execution price after slippage: buys (side=+1) pay up, sells (side=-1) receive less."""
    if side not in (1, -1):
        raise CostError(f"side must be +1 (buy) or -1 (sell), got {side!r}")
    if not math.isfinite(price) or price <= 0:
        raise CostError(f"price must be finite and > 0, got {price!r}")
    if not math.isfinite(slip_bps) or slip_bps < 0:
        raise CostError(f"slip_bps must be finite and >= 0, got {slip_bps!r}")
    return price * (1.0 + side * slip_bps / 1e4)


def funding_cashflow(
    position_notional: pd.Series,
    funding: pd.Series,
    side: pd.Series,
    mult: float = 1.0,
) -> pd.Series:
    """
    Funding cash flow at each settlement: ``-side(tau-) * notional(tau-) * F(tau) * mult``.

    ``position_notional`` (absolute USDT notional) and ``side`` (+1 long, -1 short,
    0 flat) are step series indexed by the time each position state STARTS. The
    position at ``tau-`` is the last state with timestamp strictly before ``tau``,
    i.e. the one in force just BEFORE a rebalance executed at the same instant as
    the settlement (00:00 UTC). ``funding`` is in fraction (0.0001 = 0.01 %),
    indexed by settlement time.

    Returns a Series indexed like ``funding``: negative values are payments.
    Raises ``CostError`` if a settlement with an open position has no funding rate.
    """
    if not position_notional.index.equals(side.index):
        raise CostError("position_notional and side must share the same index")
    if not math.isfinite(mult) or mult < 0:
        raise CostError(f"mult must be finite and >= 0, got {mult!r}")
    for name, s in (("position_notional", position_notional), ("side", side), ("funding", funding)):
        if not s.index.is_monotonic_increasing:
            raise CostError(f"{name} index must be sorted ascending")
    if len(side) and not np.isin(side.fillna(0).to_numpy(), (-1, 0, 1)).all():
        raise CostError("side values must be in {-1, 0, +1}")

    pos_idx = position_notional.index
    # Index of the last position state strictly before each settlement.
    loc = pos_idx.searchsorted(funding.index, side="left") - 1
    has_prior = loc >= 0
    safe_loc = np.where(has_prior, loc, 0)

    notional = np.abs(position_notional.to_numpy(dtype=float))[safe_loc] if len(pos_idx) else np.zeros(len(loc))
    sgn = side.fillna(0).to_numpy(dtype=float)[safe_loc] if len(pos_idx) else np.zeros(len(loc))
    bad_notional = has_prior & (sgn != 0) & ~np.isfinite(notional)
    if bad_notional.any():
        first = funding.index[np.argmax(bad_notional)]
        raise CostError(f"missing position notional before settlement {first}")
    exposure = np.where(has_prior & (sgn != 0), sgn * np.where(np.isfinite(notional), notional, 0.0), 0.0)

    rates = funding.to_numpy(dtype=float)
    open_and_missing = (exposure != 0) & ~np.isfinite(rates)
    if open_and_missing.any():
        first = funding.index[np.argmax(open_and_missing)]
        raise CostError(f"missing funding rate at {first} while a position is open")

    flows = -exposure * np.where(np.isfinite(rates), rates, 0.0) * mult
    return pd.Series(flows + 0.0, index=funding.index, name="funding")
