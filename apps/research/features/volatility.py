"""
Volatility features (PLAN.md §2.0, §3.1). Every feature is causal.

Conventions shared by ``apps.research.features``:

- Inputs are frames as returned by :func:`apps.research.data.loader.load_ohlcv`:
  indexed by bar OPEN time (UTC) on a regular grid, columns
  ``open, high, low, close, volume``. Missing bars are NaN rows.
- The value of a feature at row ``t`` uses only bars ``<= t``, i.e. it is
  known at the CLOSE of bar ``t`` (a signal at that close is filled at
  ``open[t+1]``). Truncating the input at ``t`` never changes the value at
  ``t`` (tested in ``tests/research/test_features.py``).
- Missing values are never filled. Rolling statistics need a minimum number of
  valid observations; recursive (Wilder / EWMA) statistics skip NaN inputs,
  keep their state and output NaN on that bar.

Features here:

- ``true_range``, ``atr`` (Wilder, n=14) and ``atr_pct = ATR14 / C``.
- ``log_returns`` and ``sigma_n``: std of the last ``n`` daily log returns,
  annualised with sqrt(365) (``sigma_30``, ``sigma_90``).
- ``expanding_pctl``: expanding percentile (0-100) with a minimum history;
  ``atr_pct_pctl`` uses it with >= 365 days.
- ``ewma_corr`` (lambda = 0.97, zero-mean RiskMetrics) at a date, and
  ``ewma_corr_to``: its time series against one reference column.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from apps.research.portfolio.sizing import ANNUALIZATION
from apps.research.portfolio.sizing import ewma_corr as _ewma_corr_matrix

__all__ = [
    "FeatureError",
    "ANNUALIZATION",
    "ATR_N",
    "require_columns",
    "check_window",
    "window_ok",
    "rolling_full",
    "wilder_smooth",
    "true_range",
    "atr",
    "atr_pct",
    "log_returns",
    "sigma_n",
    "sigma_30",
    "sigma_90",
    "expanding_pctl",
    "rolling_pctl",
    "atr_pct_pctl",
    "ewma_corr",
    "ewma_corr_to",
    "volatility_features",
]

ATR_N = 14
PCTL_MIN_DAYS = 365


class FeatureError(ValueError):
    """Invalid feature inputs (missing columns, bad window...)."""


def require_columns(df: pd.DataFrame, cols) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise FeatureError(f"input frame lacks columns {missing}")


def check_window(n: int, name: str = "n") -> int:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
        raise FeatureError(f"{name} must be a positive integer, got {n!r}")
    return int(n)


def window_ok(x: pd.Series, n: int, min_frac: float = 2 / 3) -> pd.Series:
    """
    True where a rolling window of ``n`` rows ending at ``t`` is usable: the
    series has at least ``n`` rows of history since its first valid value and
    the window holds at least ``ceil(min_frac * n)`` valid values.

    A single missing bar therefore does not blank a long window (e.g. SMA200)
    for ``n`` bars, while the start of the history still needs a full window.
    """
    n = check_window(n)
    if not 0 < min_frac <= 1:
        raise FeatureError(f"min_frac must be in (0, 1], got {min_frac!r}")
    valid = x.notna()
    history = (valid.cumsum() > 0).cumsum()
    count = valid.astype(float).rolling(n, min_periods=1).sum()
    return (history >= n) & (count >= math.ceil(min_frac * n))


def rolling_full(x: pd.Series, n: int, how: str, min_frac: float = 2 / 3) -> pd.Series:
    """Rolling ``mean`` / ``max`` / ``min`` over ``n`` rows, NaN unless :func:`window_ok`."""
    roll = x.rolling(n, min_periods=1)
    if how not in ("mean", "max", "min"):
        raise FeatureError(f"unsupported rolling statistic {how!r}")
    return getattr(roll, how)().where(window_ok(x, n, min_frac))


def wilder_smooth(x: pd.Series, n: int) -> pd.Series:
    """
    Wilder's running average: seed = mean of the first ``n`` valid values, then
    ``S_t = S_{t-1} + (x_t - S_{t-1}) / n``.

    NaN inputs are skipped (the state is kept and the output is NaN on that bar);
    the output is NaN until ``n`` valid values have been seen.
    """
    n = check_window(n)
    values = x.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)
    state = math.nan
    seed_sum = 0.0
    seen = 0
    for i, v in enumerate(values):
        if not math.isfinite(v):
            continue
        if seen < n:
            seed_sum += v
            seen += 1
            if seen == n:
                state = seed_sum / n
                out[i] = state
            continue
        state += (v - state) / n
        out[i] = state
    return pd.Series(out, index=x.index, name=x.name)


def true_range(df: pd.DataFrame) -> pd.Series:
    """
    ``TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)``.

    When ``C_{t-1}`` is missing (first bar, or the bar after a hole) only
    ``H_t - L_t`` is used: the previous close is never forward-filled.
    """
    require_columns(df, ("high", "low", "close"))
    prev_close = df["close"].shift(1)
    parts = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    tr = parts.max(axis=1, skipna=True).where(df["high"].notna() & df["low"].notna())
    return tr.rename("tr")


def atr(df: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    """Wilder's Average True Range (ATR14 by default) in price units."""
    return wilder_smooth(true_range(df), n).rename(f"atr{n}")


def atr_pct(df: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    """``ATR% = ATR_n / C`` (fraction)."""
    require_columns(df, ("close",))
    return (atr(df, n) / df["close"]).rename("atr_pct")


def log_returns(close: pd.Series) -> pd.Series:
    """``log(C_t / C_{t-1})``; NaN when either close is missing."""
    return np.log(close / close.shift(1)).rename("log_ret")


def sigma_n(close: pd.Series, n: int, min_frac: float = 2 / 3,
            periods_per_year: int = ANNUALIZATION) -> pd.Series:
    """
    ``sigma_n(t)``: std (ddof=1) of the daily log returns of the last ``n`` bars
    up to ``t``, times ``sqrt(periods_per_year)``.

    NaN with fewer than ``max(2, ceil(min_frac * n))`` valid returns in the window
    (same rule as :func:`apps.research.portfolio.sizing.annualized_vol`).
    """
    n = check_window(n)
    if not 0 < min_frac <= 1:
        raise FeatureError(f"min_frac must be in (0, 1], got {min_frac!r}")
    min_obs = max(2, math.ceil(min_frac * n))
    r = log_returns(close)
    vol = r.rolling(n, min_periods=min_obs).std(ddof=1) * math.sqrt(periods_per_year)
    return vol.rename(f"sigma_{n}")


def sigma_30(close: pd.Series) -> pd.Series:
    return sigma_n(close, 30)


def sigma_90(close: pd.Series) -> pd.Series:
    return sigma_n(close, 90)


def expanding_pctl(x: pd.Series, min_periods: int = PCTL_MIN_DAYS) -> pd.Series:
    """
    Expanding percentile (0-100) of ``x_t`` among all valid values up to ``t``
    (share of values ``<= x_t``). NaN with fewer than ``min_periods`` valid values.
    """
    min_periods = check_window(min_periods, "min_periods")
    pct = x.expanding(min_periods=min_periods).rank(pct=True, method="max") * 100.0
    return pct.where(x.notna()).rename(f"{x.name}_pctl" if x.name else "pctl")


def rolling_pctl(x: pd.Series, window: int, min_periods: int) -> pd.Series:
    """
    Rolling percentile (0-100) of ``x_t`` among the valid values of the last
    ``window`` rows (share of values ``<= x_t``). NaN with fewer than
    ``min_periods`` valid values in the window.
    """
    window = check_window(window, "window")
    min_periods = check_window(min_periods, "min_periods")
    if min_periods > window:
        raise FeatureError("min_periods cannot exceed window")
    pct = x.rolling(window, min_periods=min_periods).rank(pct=True, method="max") * 100.0
    return pct.where(x.notna()).rename(f"{x.name}_pctl" if x.name else "pctl")


def atr_pct_pctl(df_1d: pd.DataFrame, n: int = ATR_N, min_days: int = PCTL_MIN_DAYS) -> pd.Series:
    """Expanding percentile (0-100, >= ``min_days`` of history) of the daily ``ATR%``."""
    return expanding_pctl(atr_pct(df_1d, n), min_periods=min_days).rename("atr_pct_pctl")


def ewma_corr(returns: pd.DataFrame, t=None, lam: float = 0.97) -> np.ndarray:
    """
    Zero-mean EWMA correlation matrix with data up to ``t`` (rows/cols follow
    ``returns.columns``). Same implementation as the sizing layer, so backtest,
    live and diagnostics share one formula.
    """
    if not 0 < lam < 1:
        raise FeatureError(f"lam must be in (0, 1), got {lam!r}")
    return _ewma_corr_matrix(returns, t, lam=lam)


def ewma_corr_to(returns: pd.DataFrame, ref: str, lam: float = 0.97) -> pd.DataFrame:
    """
    Time series of the zero-mean EWMA correlation of every column with ``ref``.

    Recursive form of :func:`ewma_corr`: on each date the sums decay by ``lam``
    and only jointly observed returns are added, so the value at ``t`` equals
    ``ewma_corr(returns, t)[i, ref]``. NaN until the pair has a joint observation.
    """
    if not 0 < lam < 1:
        raise FeatureError(f"lam must be in (0, 1), got {lam!r}")
    if ref not in returns.columns:
        raise FeatureError(f"reference column {ref!r} not in returns")
    x = returns.to_numpy(dtype=float)
    y_ref = returns[ref].to_numpy(dtype=float)
    k = x.shape[1]
    s_xy = np.zeros(k)
    s_xx = np.zeros(k)   # sum w * x_i^2 over dates where ref is observed
    s_yy = np.zeros(k)   # sum w * ref^2 over dates where x_i is observed
    out = np.full(x.shape, np.nan)
    for i in range(x.shape[0]):
        s_xy *= lam
        s_xx *= lam
        s_yy *= lam
        row = x[i]
        r = y_ref[i]
        if math.isfinite(r):
            ok = np.isfinite(row)
            s_xy[ok] += row[ok] * r
            s_xx[ok] += row[ok] ** 2
            s_yy[ok] += r * r
        denom = np.sqrt(s_xx * s_yy)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i] = np.where(denom > 0, s_xy / denom, np.nan)
    return pd.DataFrame(np.clip(out, -1.0, 1.0), index=returns.index, columns=returns.columns)


def volatility_features(df_1d: pd.DataFrame) -> pd.DataFrame:
    """Daily volatility features of §3.1 for one symbol."""
    require_columns(df_1d, ("high", "low", "close"))
    a = atr(df_1d)
    ap = (a / df_1d["close"]).rename("atr_pct")
    return pd.DataFrame(
        {
            "atr14": a,
            "atr_pct": ap,
            "atr_pct_pctl": expanding_pctl(ap, PCTL_MIN_DAYS),
            "sigma_30": sigma_30(df_1d["close"]),
            "sigma_90": sigma_90(df_1d["close"]),
        },
        index=df_1d.index,
    )
