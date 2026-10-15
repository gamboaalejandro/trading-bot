"""
Shared helpers of the intraday strategies (BRK4H, SHOCK, PULLBACK; PLAN.md §2.6, §2.8, §2.9).

Intraday strategies compute their indicators with ONE causal feature function
per strategy, used in two ways:

- **prepared** (backtests): :meth:`prepare` evaluates the feature function once
  on the full local data. Every feature is a causal rolling / expanding /
  recursive statistic, so the row at ``t`` only depends on data available at
  the close of ``t``; the tests check it by truncation.
- **lazy** (live trading, or when nothing was prepared): ``on_bar`` evaluates
  the same function on the truncated views of :class:`~apps.research.strategies.base.Context`
  (``history``, ``daily_history``, ``funding_history``) and keeps the last row.

Daily values are attached to an intraday bar ``t`` only when the daily bar is
CLOSED at the intraday close ``t + tf`` (``merge_asof`` backward,
:func:`apps.research.features.regime.daily_asof`).
"""
from __future__ import annotations

from typing import Callable, Mapping, Optional

import pandas as pd

from apps.research.data.loader import FUNDING_EXCLUDED
from apps.research.features.funding import SETTLEMENT_STEP, apr, asof_bar_close, f_bar_3d, fund_pct, to_daily
from apps.research.features.regime import daily_asof
from apps.research.features.trend import sma
from apps.research.strategies.base import Context

__all__ = [
    "StrategyError",
    "BTC",
    "OHLCV",
    "btc_daily_trend",
    "intraday_funding",
    "FeatureCache",
]

BTC = "BTCUSDT"
OHLCV = ["open", "high", "low", "close", "volume"]


class StrategyError(ValueError):
    """Invalid strategy configuration or missing inputs."""


def ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """The raw OHLCV columns of a bar frame (drops the ``d_*`` daily context of the engine)."""
    cols = [c for c in OHLCV if c in df.columns]
    return df[cols]


def btc_daily_trend(btc_daily: Optional[pd.DataFrame], index: pd.DatetimeIndex, tf,
                    n: int = 200) -> pd.DataFrame:
    """
    ``btc_d_close`` and ``btc_d_sma{n}`` of the last BTC daily bar closed at each
    intraday close (NaN without BTC data).
    """
    cols = ["btc_d_close", f"btc_d_sma{n}"]
    if btc_daily is None or len(btc_daily) == 0:
        return pd.DataFrame(float("nan"), index=index, columns=cols)
    c = btc_daily["close"].astype(float)
    feat = pd.DataFrame({cols[0]: c, cols[1]: sma(c, n)}, index=btc_daily.index)
    return daily_asof(feat, index, tf)


def intraday_funding(funding: Optional[pd.Series], daily_index: pd.DatetimeIndex,
                     index: pd.DatetimeIndex, tf, symbol: Optional[str] = None) -> pd.DataFrame:
    """
    Funding features known at each intraday close ``t + tf``:

    - ``apr_3d``: ``APR(F_bar_3d)`` of the last 9 settlements with ``tau <= t + tf``
      (at most one 8h settlement of staleness);
    - ``fund_pct``: rolling 365-day percentile of the daily ``F_bar_3d`` (>= 180
      days), taken from the last daily bar closed by ``t + tf``.

    All NaN without funding data or for BNBUSDT (excluded, PLAN §5.2.2).
    """
    out = pd.DataFrame(float("nan"), index=index, columns=["apr_3d", "fund_pct"])
    if funding is None or len(funding) == 0 or symbol in FUNDING_EXCLUDED \
            or funding.attrs.get("symbol") in FUNDING_EXCLUDED:
        return out
    fb = f_bar_3d(funding)
    out["apr_3d"] = apr(asof_bar_close(fb, index, pd.Timedelta(tf), tolerance=SETTLEMENT_STEP)).to_numpy()
    if len(daily_index):
        pct_d = fund_pct(to_daily(fb, daily_index))
        out["fund_pct"] = daily_asof(pct_d, index, tf).to_numpy()
    return out


class FeatureCache:
    """
    Prepared features per symbol, with the lazy fallback on the context views.

    ``compute(symbol, intraday, daily, funding, btc_intraday, btc_daily)``
    returns a feature frame indexed like ``intraday``.
    """

    def __init__(self, compute: Callable[..., pd.DataFrame], btc_symbol: str = BTC):
        self._compute = compute
        self.btc_symbol = btc_symbol
        self.frames: dict[str, pd.DataFrame] = {}

    def prepare(self, panel: Mapping[str, pd.DataFrame], daily: Mapping[str, pd.DataFrame],
                funding: Optional[Mapping[str, pd.Series]] = None,
                btc_intraday: Optional[pd.DataFrame] = None,
                btc_daily: Optional[pd.DataFrame] = None) -> None:
        funding = funding or {}
        btc_i = btc_intraday if btc_intraday is not None else panel.get(self.btc_symbol)
        btc_d = btc_daily if btc_daily is not None else daily.get(self.btc_symbol)
        self.frames = {}
        for s, df in panel.items():
            if s not in daily:
                raise StrategyError(f"{s}: no daily bars to prepare the features")
            self.frames[s] = self._compute(s, ohlcv(df), daily[s], funding.get(s),
                                           None if btc_i is None else ohlcv(btc_i), btc_d)

    def row(self, symbol: str, t, ctx: Context) -> Optional[pd.Series]:
        """Features of ``symbol`` at ``t``: prepared row, else computed on the truncated context."""
        f = self.frames.get(symbol)
        if f is not None and t in f.index:
            return f.loc[t]
        hist = ctx.history(symbol)
        if len(hist) == 0 or hist.index[-1] != t:
            return None
        daily = ctx.daily_history(symbol) if symbol in ctx.daily else None
        if daily is None:
            raise StrategyError(f"{symbol}: no daily bars in the context")
        fund = ctx.funding_history(symbol) if symbol in ctx.funding else None
        btc_i = ohlcv(ctx.history(self.btc_symbol)) if self.btc_symbol in ctx.frames else None
        btc_d = ctx.daily_history(self.btc_symbol) if self.btc_symbol in ctx.daily else None
        feat = self._compute(symbol, ohlcv(hist), daily, fund, btc_i, btc_d)
        return feat.iloc[-1]
