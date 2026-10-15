"""
Funding and basis features (PLAN.md §2.0, §3.1, §5.2). Every feature is causal.

- ``f_bar_3d``: mean of the last 9 funding settlements on the 8h grid
  (00/08/16 UTC), i.e. three days. The settlements are put on a regular 8h grid
  first, so a missing settlement makes the mean NaN instead of silently
  stretching the window. Off-grid prints of the source (periods with 4h
  funding, e.g. a few in SOL) are ignored by default: APR assumes 8h intervals
  and the cost of those periods is covered by the x0.5 / x2 funding stress.
- ``apr(F) = F * 3 * 365`` (fraction).
- Daily alignment: the value for the daily bar ``t`` is the one known at its
  close (00:00 UTC of ``t+1``), i.e. built from settlements with timestamp
  ``<= close of t``.
- ``fund_pct``: rolling percentile (0-100) of the daily ``f_bar_3d`` over 365
  days with at least 180 valid days.
- ``basis = C_perp / C_spot - 1`` on the common bars (no fill).

BNBUSDT funding is excluded (anomalous source, PLAN §5.2.2): any series tagged
with that symbol raises :class:`FeatureError`. The local funding is NOT
verified against ``/fapi/v1/fundingRate`` (reports must say so).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from apps.research.data.loader import FUNDING_EXCLUDED, load_funding
from apps.research.features.volatility import FeatureError, check_window, rolling_pctl

__all__ = [
    "SETTLEMENT_STEP",
    "F_BAR_N",
    "FUND_PCT_WINDOW",
    "FUND_PCT_MIN",
    "apr",
    "settlement_grid",
    "f_bar_3d",
    "asof_bar_close",
    "to_daily",
    "fund_pct",
    "funding_features",
    "load_funding_features",
    "basis",
]

SETTLEMENT_STEP = pd.Timedelta(hours=8)
F_BAR_N = 9
FUND_PCT_WINDOW = 365
FUND_PCT_MIN = 180
DAY = pd.Timedelta(days=1)


def _check_not_excluded(funding: pd.Series) -> None:
    symbol = funding.attrs.get("symbol") if hasattr(funding, "attrs") else None
    if symbol in FUNDING_EXCLUDED:
        raise FeatureError(f"{symbol} funding is excluded (anomalous source data, PLAN §5.2.2)")


def apr(f: pd.Series | float) -> pd.Series | float:
    """Annualised funding ``F * 3 * 365`` (fraction) for 8h settlements."""
    return f * 3 * 365


def settlement_grid(funding: pd.Series) -> pd.Series:
    """
    Funding on the regular 8h settlement grid (00/08/16 UTC). Off-grid prints are
    dropped and missing settlements become NaN (never filled).
    """
    if not isinstance(funding.index, pd.DatetimeIndex):
        raise FeatureError("funding must be indexed by settlement time")
    _check_not_excluded(funding)
    s = funding.sort_index()
    epoch = pd.Timestamp(0, tz=s.index.tz)
    on_grid = ((s.index - epoch) % SETTLEMENT_STEP) == pd.Timedelta(0)
    s = s[on_grid]
    if s.empty:
        raise FeatureError("no funding settlements on the 8h grid")
    grid = pd.date_range(s.index[0], s.index[-1], freq=SETTLEMENT_STEP, name=s.index.name)
    out = s.reindex(grid).astype(float)
    out.index.freq = None
    out.attrs = dict(funding.attrs)
    return out


def f_bar_3d(funding: pd.Series, n: int = F_BAR_N) -> pd.Series:
    """Mean of the last ``n`` (9) settlements, indexed by settlement time; NaN if any is missing."""
    n = check_window(n)
    grid = settlement_grid(funding)
    out = grid.rolling(n, min_periods=n).mean().rename("f_bar_3d")
    out.attrs = dict(funding.attrs)
    return out


def asof_bar_close(values: pd.Series | pd.DataFrame, bar_index: pd.DatetimeIndex,
                   bar_delta: pd.Timedelta, value_times: pd.DatetimeIndex | None = None,
                   tolerance: pd.Timedelta | None = None) -> pd.Series | pd.DataFrame:
    """
    For every bar (open time in ``bar_index``, closing at ``open + bar_delta``),
    take the last row of ``values`` whose availability time is ``<= `` that close.

    ``value_times`` gives the availability time of each row (defaults to the
    index of ``values``). Rows older than ``tolerance`` relative to the bar close
    are not used (NaN): stale values are never carried forward indefinitely.
    """
    if not isinstance(bar_index, pd.DatetimeIndex):
        raise FeatureError("bar_index must be a DatetimeIndex")
    avail = values.index if value_times is None else pd.DatetimeIndex(value_times)
    if len(avail) != len(values):
        raise FeatureError("value_times must have one entry per row of values")
    frame = values.to_frame() if isinstance(values, pd.Series) else values
    right = frame.copy()
    right.index = avail
    right = right.sort_index()
    right.index.name = "_avail"
    right = right.reset_index()
    right["_avail"] = right["_avail"].astype("datetime64[ns, UTC]")
    left = pd.DataFrame({"_close": (bar_index + bar_delta).astype("datetime64[ns, UTC]")})
    merged = pd.merge_asof(left, right, left_on="_close", right_on="_avail",
                           direction="backward", allow_exact_matches=True, tolerance=tolerance)
    out = merged[frame.columns]
    out.index = bar_index
    if isinstance(values, pd.Series):
        res = out.iloc[:, 0].rename(values.name)
        res.attrs = dict(values.attrs)
        return res
    return out


def to_daily(settlement_values: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    """
    Value known at the close of each daily bar (the 00:00 UTC settlement of
    ``t+1`` is included). At most one settlement (8h) of staleness is accepted.
    """
    return asof_bar_close(settlement_values, daily_index, DAY, tolerance=SETTLEMENT_STEP)


def fund_pct(f_bar_daily: pd.Series, window: int = FUND_PCT_WINDOW,
             min_periods: int = FUND_PCT_MIN) -> pd.Series:
    """Rolling percentile (0-100) of the daily ``f_bar_3d`` (365 days, >= 180 valid)."""
    return rolling_pctl(f_bar_daily, window, min_periods).rename("fund_pct")


def funding_features(funding: pd.Series, daily_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Daily funding features ``f_bar_3d, apr_3d, fund_pct, f_last`` for one perp,
    indexed like ``daily_index`` (daily bar open times; values known at the close).
    """
    fb = f_bar_3d(funding)
    grid = settlement_grid(funding)
    fb_d = to_daily(fb, daily_index)
    out = pd.DataFrame(
        {
            "f_bar_3d": fb_d,
            "apr_3d": apr(fb_d),
            "fund_pct": fund_pct(fb_d),
            "f_last": to_daily(grid.rename("f_last"), daily_index),
        },
        index=daily_index,
    )
    out.attrs = {"funding_verified": False, "symbol": funding.attrs.get("symbol")}
    return out


def load_funding_features(symbol: str, daily_index: pd.DatetimeIndex,
                          root: str | os.PathLike | None = None) -> pd.DataFrame:
    """Load the local funding of ``symbol`` (BNBUSDT raises) and build :func:`funding_features`."""
    return funding_features(load_funding(symbol, root=root), daily_index)


def basis(perp: pd.DataFrame | pd.Series, spot: pd.DataFrame | pd.Series) -> pd.Series:
    """
    ``C_perp / C_spot - 1`` on bars present in both (same timeframe, same open
    times). Bars missing in either market are NaN; nothing is filled.
    """
    c_perp = perp["close"] if isinstance(perp, pd.DataFrame) else perp
    c_spot = spot["close"] if isinstance(spot, pd.DataFrame) else spot
    tf_perp, tf_spot = perp.attrs.get("tf"), spot.attrs.get("tf")
    if tf_perp and tf_spot and tf_perp != tf_spot:
        raise FeatureError(f"basis needs the same timeframe (perp {tf_perp}, spot {tf_spot})")
    idx = c_perp.index.union(c_spot.index)
    b = c_perp.reindex(idx) / c_spot.reindex(idx) - 1.0
    return b.replace([np.inf, -np.inf], np.nan).rename("basis")
