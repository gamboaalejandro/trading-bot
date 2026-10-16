"""
BRK4H: 4h breakout with a daily regime filter (PLAN.md §2.6, informes 01-C3 / 03-C2).

Event strategy for :func:`apps.research.engine.event_bt.run_event_bt` (4h bars).
At the close of 4h bar ``t``:

- **Regime** (last CLOSED 1d bar, ``merge_asof`` backward on ``t + 4h``):
  long allowed if ``C_1d > SMA100_1d`` and ``ADX14_1d >= 20``; short (perps
  only) if ``C_1d < SMA100_1d``, ``ADX14_1d >= 20`` and BTC ``C_1d < SMA200_1d``.
- **Entry**: long if ``C_4h > max(H_{t-n..t-1})``; short if
  ``C_4h < min(L_{t-n..t-1})`` (``n`` in 4h bars, the bar ``t`` excluded).
- **Initial stop**: ``C_t - 2.5 * ATR14_4h`` (``+`` for shorts), placed with the
  entry. ``C_t`` stands for the entry price: the fill is at ``open[t+1]`` and
  the engine rejects the entry if that open is already beyond the stop.
- **Chandelier trailing**: ``max(H since entry) - 3 * ATR14_4h`` (shorts:
  ``min(L since entry) + 3 * ATR14_4h``), only in the trade's favour (the
  strategy only sends tighter stops and the engine never loosens one).
- **Extra exits**: ``C_4h < MID_n`` (shorts: ``C_4h > MID_n``) or the daily
  regime inverts (longs: ``C_1d < SMA100_1d``; shorts: ``C_1d > SMA100_1d``).
  ``MID_n`` follows the common definition of §2.0: the Donchian mid-point on
  CLOSES of the ``n`` bars before ``t``.
- **Funding filter** (perp data, also used for spot longs when available): no
  long if ``APR(F_bar_3d) > 50 %`` or ``fund_pct > 95``; no short if
  ``APR < -30 %``. A filter input that is not known (NaN, e.g. warm-up of the
  365-day percentile, or no funding data) does not block.
- **B5 volume filter** (03-C2): ``rvol = V / median(V, 20) >= 1.5`` and
  ``close_loc = (C - L) / (H - L) >= 0.7`` (shorts: ``close_loc <= 0.3``).
- **Sizing**: risk-based in the engine, ``qty = R * NAV / |entry - stop|`` with
  ``R`` = 0.5 % on BTC/ETH and 0.25 % on altcoins, then the §2.0 caps and the
  leverage cap (<= 1x altcoins, <= 1.5x BTC/ETH; ``config/risk_limits.yml``).

Configurations (fixed before seeing results, PLAN §2.6): ``B1`` n=20 with all
filters, ``B2`` n=55, ``B3`` B1 without ADX, ``B4`` B1 without the funding
filter, ``B5`` B1 plus the volume / close-location filter.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional

import pandas as pd

from apps.research.features.candles import close_loc, rvol
from apps.research.features.regime import daily_asof
from apps.research.features.trend import adx, donchian, sma
from apps.research.features.volatility import ATR_N, atr, check_window, rolling_full
from apps.research.strategies._intraday import (
    BTC,
    FeatureCache,
    StrategyError,
    btc_daily_trend,
    intraday_funding,
)
from apps.research.strategies.base import Context, OrderIntent

__all__ = [
    "BRK4H_CONFIGS",
    "Breakout4H",
    "breakout_features",
    "long_regime",
    "short_regime",
    "entry_side",
    "make_breakout4h",
]

TF = pd.Timedelta(hours=4)

_BASE = {
    "n": 20,
    "sma_n": 100,
    "adx_n": ATR_N,
    "adx_min": 20.0,
    "btc_sma_n": 200,
    "atr_n": ATR_N,
    "stop_atr": 2.5,
    "trail_atr": 3.0,
    "use_adx": True,
    "use_funding": True,
    "apr_long_max": 0.50,
    "fund_pct_max": 95.0,
    "apr_short_min": -0.30,
    "use_volume": False,
    "rvol_n": 20,
    "rvol_min": 1.5,
    "close_loc_min": 0.7,
}

BRK4H_CONFIGS: dict[str, dict] = {
    "B1": dict(_BASE),
    "B2": {**_BASE, "n": 55},
    "B3": {**_BASE, "use_adx": False},
    "B4": {**_BASE, "use_funding": False},
    "B5": {**_BASE, "use_volume": True},
}


def _free_params(p: Mapping) -> int:
    """Active numeric thresholds of a configuration (``p_k`` of the adaptability score)."""
    k = 5                                   # n, sma_n, btc_sma_n, stop_atr, trail_atr
    k += 1 if p["use_adx"] else 0           # adx_min
    k += 3 if p["use_funding"] else 0       # apr_long_max, fund_pct_max, apr_short_min
    k += 2 if p["use_volume"] else 0        # rvol_min, close_loc_min
    return k


def breakout_features(df: pd.DataFrame, daily: pd.DataFrame, params: Mapping, tf=TF,
                      funding: Optional[pd.Series] = None, btc_daily: Optional[pd.DataFrame] = None,
                      symbol: Optional[str] = None) -> pd.DataFrame:
    """
    Causal BRK4H features per 4h bar (index = bar open time, values known at its close).

    Columns: ``close, high, low, hh`` (max H of the ``n`` previous bars), ``ll``,
    ``mid`` (Donchian mid on closes, ``n`` previous bars), ``atr``, ``rvol``,
    ``close_loc``, ``d_close, d_sma, d_adx`` (last closed daily bar),
    ``btc_d_close, btc_d_sma`` and ``apr_3d, fund_pct``.
    """
    n = check_window(params["n"])
    idx = df.index
    h, l, c = (df[k].astype(float) for k in ("high", "low", "close"))
    out = pd.DataFrame(index=idx)
    out["close"], out["high"], out["low"] = c, h, l
    out["hh"] = rolling_full(h.shift(1), n, "max")
    out["ll"] = rolling_full(l.shift(1), n, "min")
    out["mid"] = donchian(c, n)["mid"]
    out["atr"] = atr(df, params["atr_n"])
    out["rvol"] = rvol(df, params["rvol_n"])
    out["close_loc"] = close_loc(df)
    dc = daily["close"].astype(float)
    dfeat = pd.DataFrame({"d_close": dc, "d_sma": sma(dc, params["sma_n"]),
                          "d_adx": adx(daily, params["adx_n"])}, index=daily.index)
    out[["d_close", "d_sma", "d_adx"]] = daily_asof(dfeat, idx, tf).to_numpy()
    btc = btc_daily_trend(btc_daily, idx, tf, params["btc_sma_n"])
    out["btc_d_close"], out["btc_d_sma"] = btc.iloc[:, 0].to_numpy(), btc.iloc[:, 1].to_numpy()
    fund = intraday_funding(funding, daily.index, idx, tf, symbol)
    out["apr_3d"], out["fund_pct"] = fund["apr_3d"].to_numpy(), fund["fund_pct"].to_numpy()
    return out


def _gt(a, b) -> bool:
    return bool(pd.notna(a) and pd.notna(b) and a > b)


def _lt(a, b) -> bool:
    return bool(pd.notna(a) and pd.notna(b) and a < b)


def long_regime(row: Mapping, p: Mapping) -> bool:
    """Daily long regime: ``C_1d > SMA100_1d`` and (B3 excepted) ``ADX14_1d >= 20``."""
    if not _gt(row["d_close"], row["d_sma"]):
        return False
    return not p["use_adx"] or bool(pd.notna(row["d_adx"]) and row["d_adx"] >= p["adx_min"])


def short_regime(row: Mapping, p: Mapping, market: str) -> bool:
    """Daily short regime (perps only): ``C_1d < SMA100_1d``, ADX >= 20 and BTC ``C < SMA200``."""
    if market != "futures" or not _lt(row["d_close"], row["d_sma"]):
        return False
    if p["use_adx"] and not (pd.notna(row["d_adx"]) and row["d_adx"] >= p["adx_min"]):
        return False
    return _lt(row["btc_d_close"], row["btc_d_sma"])


def _funding_ok(row: Mapping, p: Mapping, side: int) -> bool:
    if not p["use_funding"]:
        return True
    a, pct = row["apr_3d"], row["fund_pct"]
    if side == 1:
        return not (_gt(a, p["apr_long_max"]) or _gt(pct, p["fund_pct_max"]))
    return not _lt(a, p["apr_short_min"])


def _volume_ok(row: Mapping, p: Mapping, side: int) -> bool:
    if not p["use_volume"]:
        return True
    if not (pd.notna(row["rvol"]) and row["rvol"] >= p["rvol_min"]) or pd.isna(row["close_loc"]):
        return False
    loc = row["close_loc"]
    return loc >= p["close_loc_min"] if side == 1 else loc <= 1.0 - p["close_loc_min"]


def entry_side(row: Mapping, p: Mapping, market: str) -> int:
    """+1 long entry, -1 short entry, 0 nothing, at the close of the bar described by ``row``."""
    if not (pd.notna(row["atr"]) and row["atr"] > 0):
        return 0
    if _gt(row["close"], row["hh"]) and long_regime(row, p) and _funding_ok(row, p, 1) \
            and _volume_ok(row, p, 1):
        return 1
    if _lt(row["close"], row["ll"]) and short_regime(row, p, market) and _funding_ok(row, p, -1) \
            and _volume_ok(row, p, -1):
        return -1
    return 0


class Breakout4H:
    """BRK4H event strategy (see the module docstring); ``config`` is ``B1``..``B5``."""

    def __init__(self, config: str = "B1", btc_symbol: str = BTC, **overrides):
        if config not in BRK4H_CONFIGS:
            raise StrategyError(f"unknown BRK4H config {config!r}; expected one of {list(BRK4H_CONFIGS)}")
        unknown = set(overrides) - set(_BASE)
        if unknown:
            raise StrategyError(f"unknown BRK4H parameters {sorted(unknown)}")
        self.params = {**BRK4H_CONFIGS[config], **overrides, "config": config}
        p = self.params
        if not (p["stop_atr"] > 0 and p["trail_atr"] > 0):
            raise StrategyError("stop_atr and trail_atr must be > 0")
        self.name = f"BRK4H-{config}"
        self.n_free_params = _free_params(p)
        self.tf = TF
        self._cache = FeatureCache(self._compute, btc_symbol)

    def _compute(self, symbol, df, daily, funding, btc_intraday, btc_daily) -> pd.DataFrame:
        return breakout_features(df, daily, self.params, self.tf, funding, btc_daily, symbol)

    def prepare(self, panel: Mapping[str, pd.DataFrame], daily: Mapping[str, pd.DataFrame],
                funding: Optional[Mapping[str, pd.Series]] = None,
                btc_daily: Optional[pd.DataFrame] = None) -> "Breakout4H":
        """Precompute the causal features on the backtest data (fast path; same values as lazy)."""
        self._cache.prepare(panel, daily, funding, btc_daily=btc_daily)
        return self

    def features(self, symbol: str) -> pd.DataFrame:
        return self._cache.frames[symbol]

    def on_bar(self, t, bars: dict[str, pd.Series], ctx: Context) -> list[OrderIntent]:
        p = self.params
        intents: list[OrderIntent] = []
        for s in bars:
            row = self._cache.row(s, t, ctx)
            if row is None or pd.isna(row["close"]):
                continue
            pos = ctx.position(s)
            if pos is None:
                side = entry_side(row, p, ctx.market)
                if side == 0:
                    continue
                stop = row["close"] - side * p["stop_atr"] * row["atr"]
                if not (math.isfinite(stop) and stop > 0):
                    continue
                intents.append(OrderIntent(s, "BUY" if side == 1 else "SELL", stop_price=float(stop),
                                           tag=f"{self.name}_{'long' if side == 1 else 'short'}"))
                continue
            intents.extend(self._manage(s, row, pos, ctx))
        return intents

    def _manage(self, s: str, row: pd.Series, pos, ctx: Context) -> list[OrderIntent]:
        p = self.params
        close_side = "SELL" if pos.side == 1 else "BUY"
        if pos.side == 1:
            exit_mid = _lt(row["close"], row["mid"])
            exit_regime = _lt(row["d_close"], row["d_sma"])
        else:
            exit_mid = _gt(row["close"], row["mid"])
            exit_regime = _gt(row["d_close"], row["d_sma"])
        if exit_mid or exit_regime:
            return [OrderIntent(s, close_side, reduce_only=True,
                                tag=f"{self.name}_exit_{'mid' if exit_mid else 'regime'}")]
        if not (pd.notna(row["atr"]) and row["atr"] > 0):
            return []
        since = ctx.history(s).loc[pos.entry_time:]
        if pos.side == 1:
            new_stop = float(since["high"].max()) - p["trail_atr"] * row["atr"]
            tighter = pos.stop is None or new_stop > pos.stop
        else:
            new_stop = float(since["low"].min()) + p["trail_atr"] * row["atr"]
            tighter = pos.stop is None or new_stop < pos.stop
        if tighter and math.isfinite(new_stop) and new_stop > 0:
            return [OrderIntent(s, close_side, reduce_only=True, stop_price=new_stop,
                                tag=f"{self.name}_trail")]
        return []


def make_breakout4h(config: str, **overrides) -> Breakout4H:
    """Factory used by the experiment runner (``B1``..``B5``)."""
    return Breakout4H(config, **overrides)
