"""
Ex-ante regime labels (PLAN.md §3.2) and alignment helpers. Every label is causal.

- ``trend_btc``: ``up`` if ``C_BTC > SMA200_BTC`` at the close of ``t``, else ``down``.
- ``vol_tercile``: ``low`` / ``mid`` / ``high`` from the expanding percentile
  (>= 365 days of history) of BTC's daily ``ATR%``, cut at 33 and 67
  (``pctl <= 33`` -> low, ``33 < pctl <= 67`` -> mid, ``> 67`` -> high).
- ``cell = trend_btc x vol_tercile`` (6 cells at most), e.g. ``up_low``.

The cell computed with the CLOSED daily bar ``t`` applies to the returns of
``t+1``: :func:`ex_ante_cells` returns, for each daily row, the cell that was
known at the previous close, i.e. the label to attach to the return indexed at
that row (``r_t = C_t / C_{t-1} - 1``). Labels are NaN (None) while undefined.

Live trading computes these labels with exactly this code (PLAN §3.4).
"""
from __future__ import annotations

import pandas as pd

from apps.research.features.funding import asof_bar_close
from apps.research.features.trend import sma
from apps.research.features.volatility import (
    PCTL_MIN_DAYS,
    FeatureError,
    atr_pct,
    expanding_pctl,
    require_columns,
)

__all__ = [
    "TREND_LABELS",
    "VOL_LABELS",
    "CELLS",
    "VOL_CUTS",
    "trend_btc",
    "vol_tercile",
    "regime_cells",
    "ex_ante_cells",
    "daily_asof",
    "fng_features",
]

TREND_LABELS = ("up", "down")
VOL_LABELS = ("low", "mid", "high")
VOL_CUTS = (33.0, 67.0)
CELLS = tuple(f"{t}_{v}" for t in TREND_LABELS for v in VOL_LABELS)
DAY = pd.Timedelta(days=1)


def trend_btc(btc_1d: pd.DataFrame, n: int = 200) -> pd.Series:
    """``up`` if ``C > SMA_n`` else ``down``; None while SMA_n is undefined or C is missing."""
    require_columns(btc_1d, ("close",))
    c = btc_1d["close"]
    s = sma(c, n)
    lab = pd.Series(None, index=btc_1d.index, dtype=object)
    ok = c.notna() & s.notna()
    lab[ok & (c > s)] = "up"
    lab[ok & ~(c > s)] = "down"
    return lab.rename("trend_btc")


def _tercile(pctl: pd.Series, cuts=VOL_CUTS) -> pd.Series:
    lo, hi = cuts
    lab = pd.Series(None, index=pctl.index, dtype=object)
    ok = pctl.notna()
    lab[ok & (pctl <= lo)] = "low"
    lab[ok & (pctl > lo) & (pctl <= hi)] = "mid"
    lab[ok & (pctl > hi)] = "high"
    return lab


def vol_tercile(btc_1d: pd.DataFrame, min_days: int = PCTL_MIN_DAYS) -> pd.Series:
    """Tercile label of the expanding percentile of BTC's daily ``ATR%``."""
    return _tercile(expanding_pctl(atr_pct(btc_1d), min_periods=min_days)).rename("vol_tercile")


def regime_cells(btc_1d: pd.DataFrame, min_days: int = PCTL_MIN_DAYS) -> pd.DataFrame:
    """
    Regime at the close of each daily bar ``t``: columns ``trend_btc``,
    ``atr_pct_pctl``, ``vol_tercile`` and ``cell`` (None while undefined).
    """
    if btc_1d.attrs.get("tf") not in (None, "1d"):
        raise FeatureError("regime cells are defined on the daily BTC bars")
    tr = trend_btc(btc_1d)
    pctl = expanding_pctl(atr_pct(btc_1d), min_periods=min_days).rename("atr_pct_pctl")
    vt = _tercile(pctl).rename("vol_tercile")
    cell = pd.Series(None, index=btc_1d.index, dtype=object)
    ok = tr.notna() & vt.notna()
    cell[ok] = tr[ok] + "_" + vt[ok]
    return pd.DataFrame({"trend_btc": tr, "atr_pct_pctl": pctl, "vol_tercile": vt, "cell": cell})


def ex_ante_cells(btc_1d: pd.DataFrame, min_days: int = PCTL_MIN_DAYS) -> pd.Series:
    """Cell to attach to the daily return indexed at each row: the cell of the previous close."""
    cells = regime_cells(btc_1d, min_days)["cell"]
    return cells.shift(1).rename("cell")


def daily_asof(daily_values: pd.Series | pd.DataFrame, intraday_index: pd.DatetimeIndex,
               intraday_delta: pd.Timedelta | str) -> pd.Series | pd.DataFrame:
    """
    Attach daily values (indexed by daily bar open time, known at its close) to
    intraday bars: each intraday bar gets the last daily bar CLOSED at or before
    the intraday bar's close (``merge_asof`` backward). A daily value is never
    used for more than one day after its close.
    """
    delta = pd.Timedelta(intraday_delta)
    return asof_bar_close(daily_values, intraday_index, delta,
                          value_times=daily_values.index + DAY, tolerance=DAY)


def fng_features(fng: pd.Series, min_days: int = PCTL_MIN_DAYS) -> pd.DataFrame:
    """
    ``fng`` and its expanding percentile ``fng_pctl`` (>= ``min_days``). Only
    available when the user supplies the alternative.me CSV (``load_fng`` raises
    otherwise). The value dated ``d`` is treated as known at the close of day ``d``.
    Diagnostic / paper use only (multiplier <= 1).
    """
    return pd.DataFrame({"fng": fng, "fng_pctl": expanding_pctl(fng.rename("fng"), min_days)})
