"""
Trend and chart features (PLAN.md §2.0, §3.1, groups "Chart" and "Tendencia").

See :mod:`apps.research.features.volatility` for the shared conventions (index =
bar open time, value at ``t`` known at the close of ``t``, NaN never filled).

- ``sma``/``ema`` (standard), ``sma_ratio_n = C / SMA_n - 1`` for n in {50, 100, 200}.
- ``sma50_gt_sma200`` (1.0 / 0.0, NaN while undefined) and
  ``slope_sma50 = SMA50_t / SMA50_{t-20} - 1`` (20-day slope).
- ``adx`` (Wilder, n=14).
- ``er`` (Kaufman efficiency ratio, n=30):
  ``|C_t - C_{t-n}| / sum_{k=t-n+1..t} |C_k - C_{k-1}|``.
- Donchian channels on CLOSES, excluding the current bar:
  ``UP_n(t) = max(C_{t-n..t-1})``, ``DN_n(t) = min(C_{t-n..t-1})``,
  ``MID_n = (UP_n + DN_n) / 2`` and ``donchian_pos_n = (C - DN_n) / (UP_n - DN_n)``.
- ``dist_52w_high = C / max(H over the last 365 bars incl. t) - 1``.
- ``dd_365 = C / max(C over the last 365 bars incl. t) - 1`` (<= 0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from apps.research.features.volatility import (
    ATR_N,
    check_window,
    require_columns,
    rolling_full,
    true_range,
    wilder_smooth,
)

__all__ = [
    "SMA_RATIO_WINDOWS",
    "sma",
    "ema",
    "sma_ratio",
    "sma50_gt_sma200",
    "slope_sma",
    "slope_sma50",
    "directional_movement",
    "adx",
    "er",
    "donchian",
    "donchian_pos",
    "dist_52w_high",
    "dd_365",
    "trend_features",
]

SMA_RATIO_WINDOWS = (50, 100, 200)


def sma(x: pd.Series, n: int, min_frac: float = 2 / 3) -> pd.Series:
    """
    Simple moving average of the valid values among the last ``n`` bars incl.
    ``t``. Needs ``n`` bars of history and ``ceil(min_frac * n)`` valid values
    in the window (:func:`~apps.research.features.volatility.window_ok`).
    """
    return rolling_full(x, check_window(n), "mean", min_frac).rename(f"sma{n}")


def ema(x: pd.Series, n: int) -> pd.Series:
    """
    Standard EMA with ``alpha = 2 / (n + 1)`` (recursive, ``adjust=False``).

    NaN inputs are skipped (output NaN, state kept) and the first ``n - 1``
    valid values are treated as warm-up (NaN).
    """
    n = check_window(n)
    out = x.ewm(span=n, adjust=False, ignore_na=True, min_periods=n).mean()
    return out.where(x.notna()).rename(f"ema{n}")


def sma_ratio(close: pd.Series, n: int) -> pd.Series:
    """``C / SMA_n - 1``."""
    return (close / sma(close, n) - 1.0).rename(f"sma_ratio_{n}")


def sma50_gt_sma200(close: pd.Series) -> pd.Series:
    """1.0 if ``SMA50 > SMA200``, 0.0 otherwise, NaN while either is undefined."""
    s50, s200 = sma(close, 50), sma(close, 200)
    out = (s50 > s200).astype(float).where(s50.notna() & s200.notna())
    return out.rename("sma50_gt_sma200")


def slope_sma(close: pd.Series, n: int, lag: int) -> pd.Series:
    """Relative slope of ``SMA_n`` over ``lag`` bars: ``SMA_n(t) / SMA_n(t - lag) - 1``."""
    lag = check_window(lag, "lag")
    s = sma(close, n)
    return (s / s.shift(lag) - 1.0).rename(f"slope_sma{n}")


def slope_sma50(close: pd.Series) -> pd.Series:
    """20-day slope of SMA50."""
    return slope_sma(close, 50, 20)


def directional_movement(df: pd.DataFrame) -> pd.DataFrame:
    """Wilder's ``+DM`` / ``-DM`` per bar (NaN when the previous bar is missing)."""
    require_columns(df, ("high", "low"))
    up = df["high"] - df["high"].shift(1)
    down = df["low"].shift(1) - df["low"]
    valid = up.notna() & down.notna()
    plus = np.where((up > down) & (up > 0), up, 0.0)
    minus = np.where((down > up) & (down > 0), down, 0.0)
    return pd.DataFrame(
        {"plus_dm": pd.Series(plus, index=df.index).where(valid),
         "minus_dm": pd.Series(minus, index=df.index).where(valid)},
        index=df.index,
    )


def adx(df: pd.DataFrame, n: int = ATR_N, return_di: bool = False) -> pd.Series | pd.DataFrame:
    """
    Wilder's ADX: smooth ``TR``, ``+DM`` and ``-DM`` with Wilder's average,
    ``+DI = 100 * sm(+DM) / sm(TR)``, ``-DI`` likewise,
    ``DX = 100 * |+DI - -DI| / (+DI + -DI)`` and ``ADX = Wilder average of DX``.

    The first valid ADX needs ``2n`` bars (n for the DIs, n for the ADX seed).
    With ``return_di=True`` a frame ``plus_di, minus_di, dx, adx`` is returned.
    """
    n = check_window(n)
    dm = directional_movement(df)
    tr = true_range(df).where(dm["plus_dm"].notna())   # same valid bars for the 3 sums
    s_tr = wilder_smooth(tr, n)
    s_tr = s_tr.where(s_tr > 0)
    plus_di = 100.0 * wilder_smooth(dm["plus_dm"], n) / s_tr
    minus_di = 100.0 * wilder_smooth(dm["minus_dm"], n) / s_tr
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.where(di_sum > 0)
    # A flat market (both DIs 0) has no directional movement: DX = 0.
    dx = dx.mask(di_sum.eq(0) & plus_di.notna(), 0.0)
    out = wilder_smooth(dx, n).rename(f"adx{n}")
    if return_di:
        return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "dx": dx, "adx": out})
    return out


def er(close: pd.Series, n: int = 30) -> pd.Series:
    """Kaufman efficiency ratio over ``n`` bars, in [0, 1]; NaN if the path length is 0."""
    n = check_window(n)
    net = (close - close.shift(n)).abs()
    path = close.diff().abs().rolling(n, min_periods=n).sum()
    return (net / path.where(path > 0)).rename(f"er{n}")


def donchian(close: pd.Series, n: int) -> pd.DataFrame:
    """
    Donchian channel on closes over the ``n`` bars BEFORE ``t``:
    ``up = max(C_{t-n..t-1})``, ``dn = min(C_{t-n..t-1})``, ``mid = (up + dn) / 2``.

    Needs ``n`` bars of history and 2/3 of the closes in the window valid.
    """
    n = check_window(n)
    prev = close.shift(1)
    up = rolling_full(prev, n, "max")
    dn = rolling_full(prev, n, "min")
    return pd.DataFrame({"up": up, "dn": dn, "mid": (up + dn) / 2.0}, index=close.index)


def donchian_pos(close: pd.Series, n: int) -> pd.Series:
    """
    ``(C - DN_n) / (UP_n - DN_n)``. Above 1 is a breakout above the channel,
    below 0 a breakdown; NaN when the channel has zero width.
    """
    ch = donchian(close, n)
    width = ch["up"] - ch["dn"]
    return ((close - ch["dn"]) / width.where(width > 0)).rename(f"donchian_pos_{n}")


def dist_52w_high(df_1d: pd.DataFrame, n: int = 365) -> pd.Series:
    """``C / max(H over the last n bars incl. t) - 1`` (diagnostic, not traded)."""
    require_columns(df_1d, ("high", "close"))
    hi = rolling_full(df_1d["high"], check_window(n), "max")
    return (df_1d["close"] / hi - 1.0).rename("dist_52w_high")


def dd_365(close: pd.Series, n: int = 365) -> pd.Series:
    """Drawdown of the close from its maximum over the last ``n`` bars incl. ``t`` (<= 0)."""
    peak = rolling_full(close, check_window(n), "max")
    return (close / peak - 1.0).rename("dd_365")


def trend_features(df_1d: pd.DataFrame, donchian_windows=(20, 55)) -> pd.DataFrame:
    """Daily trend and chart features of §3.1 for one symbol."""
    require_columns(df_1d, ("open", "high", "low", "close"))
    c = df_1d["close"]
    cols: dict[str, pd.Series] = {f"sma_ratio_{n}": sma_ratio(c, n) for n in SMA_RATIO_WINDOWS}
    cols["sma50_gt_sma200"] = sma50_gt_sma200(c)
    cols["slope_sma50"] = slope_sma50(c)
    cols["adx14"] = adx(df_1d, 14)
    cols["er30"] = er(c, 30)
    for n in donchian_windows:
        cols[f"donchian_pos_{n}"] = donchian_pos(c, n)
    cols["dist_52w_high"] = dist_52w_high(df_1d)
    cols["dd_365"] = dd_365(c)
    return pd.DataFrame(cols, index=df_1d.index)
