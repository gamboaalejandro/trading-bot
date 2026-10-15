"""
Candle features (PLAN.md §3.1, group "Velas"). Every feature is causal.

See :mod:`apps.research.features.volatility` for the shared conventions (index =
bar open time, value at ``t`` known at the close of ``t``, NaN never filled).

- ``body_atr = (C - O) / ATR14``
- ``upper_wick_atr = (H - max(O, C)) / ATR14``
- ``lower_wick_atr = (min(O, C) - L) / ATR14``
- ``range_atr = (H - L) / ATR14``
- ``close_loc = (C - L) / (H - L)`` (NaN on a zero-range bar)
- ``rvol = V / median(V, 20)`` (median of the last 20 bars including ``t``)
- ``gap = O_t / C_{t-1} - 1``

Candle patterns are NOT used as triggers (PLAN §2.12); these features are
diagnostics, the BRK4H-B5 filter and inputs for the worst-wick / shock checks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from apps.research.features.volatility import ATR_N, check_window, atr, require_columns

__all__ = [
    "RVOL_N",
    "body_atr",
    "upper_wick_atr",
    "lower_wick_atr",
    "range_atr",
    "close_loc",
    "rvol",
    "gap",
    "candle_features",
]

RVOL_N = 20
_OHLC = ("open", "high", "low", "close")


def _atr(df: pd.DataFrame, atr_series: pd.Series | None, n: int) -> pd.Series:
    return atr(df, n) if atr_series is None else atr_series


def body_atr(df: pd.DataFrame, n: int = ATR_N, atr_series: pd.Series | None = None) -> pd.Series:
    """Signed candle body in ATR units: ``(C - O) / ATR_n``."""
    require_columns(df, _OHLC)
    return ((df["close"] - df["open"]) / _atr(df, atr_series, n)).rename("body_atr")


def upper_wick_atr(df: pd.DataFrame, n: int = ATR_N, atr_series: pd.Series | None = None) -> pd.Series:
    """Upper wick in ATR units: ``(H - max(O, C)) / ATR_n``."""
    require_columns(df, _OHLC)
    top = np.maximum(df["open"], df["close"])
    return ((df["high"] - top) / _atr(df, atr_series, n)).rename("upper_wick_atr")


def lower_wick_atr(df: pd.DataFrame, n: int = ATR_N, atr_series: pd.Series | None = None) -> pd.Series:
    """Lower wick in ATR units: ``(min(O, C) - L) / ATR_n``."""
    require_columns(df, _OHLC)
    bottom = np.minimum(df["open"], df["close"])
    return ((bottom - df["low"]) / _atr(df, atr_series, n)).rename("lower_wick_atr")


def range_atr(df: pd.DataFrame, n: int = ATR_N, atr_series: pd.Series | None = None) -> pd.Series:
    """Bar range in ATR units: ``(H - L) / ATR_n`` (shock detection)."""
    require_columns(df, _OHLC)
    return ((df["high"] - df["low"]) / _atr(df, atr_series, n)).rename("range_atr")


def close_loc(df: pd.DataFrame) -> pd.Series:
    """Close location in the bar range, ``(C - L) / (H - L)`` in [0, 1]; NaN if ``H == L``."""
    require_columns(df, ("high", "low", "close"))
    rng = df["high"] - df["low"]
    loc = (df["close"] - df["low"]) / rng.where(rng > 0)
    return loc.rename("close_loc")


def rvol(df: pd.DataFrame, n: int = RVOL_N) -> pd.Series:
    """
    Relative volume ``V_t / median(V_{t-n+1..t})``.

    Needs ``n`` valid volumes in the window (missing bars make it NaN); a zero
    median gives NaN.
    """
    require_columns(df, ("volume",))
    n = check_window(n)
    med = df["volume"].rolling(n, min_periods=n).median()
    return (df["volume"] / med.where(med > 0)).rename("rvol")


def gap(df: pd.DataFrame) -> pd.Series:
    """Opening gap ``O_t / C_{t-1} - 1`` (NaN if the previous bar is missing)."""
    require_columns(df, ("open", "close"))
    return (df["open"] / df["close"].shift(1) - 1.0).rename("gap")


def candle_features(df: pd.DataFrame, n_atr: int = ATR_N, n_rvol: int = RVOL_N) -> pd.DataFrame:
    """All the candle features of §3.1 for one symbol and timeframe."""
    require_columns(df, (*_OHLC, "volume"))
    a = atr(df, n_atr)
    return pd.DataFrame(
        {
            "body_atr": body_atr(df, atr_series=a),
            "upper_wick_atr": upper_wick_atr(df, atr_series=a),
            "lower_wick_atr": lower_wick_atr(df, atr_series=a),
            "range_atr": range_atr(df, atr_series=a),
            "close_loc": close_loc(df),
            "rvol": rvol(df, n_rvol),
            "gap": gap(df),
        },
        index=df.index,
    )
