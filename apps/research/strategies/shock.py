"""
SHOCK: reversal after an idiosyncratic 1h shock (PLAN.md §2.9; paper only).

Event strategy for :func:`apps.research.engine.event_bt.run_event_bt` (1h bars).
At the close of 1h bar ``t``:

- ``r_t = C_t / C_{t-1} - 1`` and ``z_t = r_t / sigma_1h(t)`` where
  ``sigma_1h(t)`` is the standard deviation of the 1h returns of the 720 bars
  BEFORE ``t`` (rolling window ``t-720..t-1``; at least 2/3 of them valid). The
  shock bar is left out of its own scale so a single crash cannot dampen its
  own z-score.
- **Long signal**: ``z_t <= -3`` and
  - the shock is idiosyncratic: BTC's 1h return of the same bar
    ``r_BTC,t > -2 * sigma_1h,BTC(t)`` (same window definition), and
  - BTC's last CLOSED daily bar is above its SMA200.
  BTCUSDT itself can never qualify (its own z <= -3 fails the BTC test).
- **Entry** at ``open[t+1]`` (engine), stop ``entry - 2 * ATR14_1h`` (``C_t``
  stands for the entry; the engine rejects the entry if the open is already
  below the stop). Risk 0.25 % of NAV: ``qty = 0.0025 * NAV * risk_mult /
  (2 * ATR14_1h)``, then the engine caps.
- **Time exit** after ``hold_bars`` 1h bars: ``H1`` = 4h, ``H2`` = 12h,
  ``H3`` = 24h (the market exit fills at the open of bar ``entry + hold``).

Long only, spot or perp. :func:`tail_event_report` gives the conditional loss
of the trades exposed on the tail days 2021-05-19, 2022-11-09 and 2025-10-10,
which reports must show separately.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.features.volatility import ATR_N, atr, check_window
from apps.research.strategies._intraday import BTC, FeatureCache, StrategyError, btc_daily_trend
from apps.research.strategies.base import Context, OrderIntent

__all__ = [
    "SHOCK_CONFIGS",
    "TAIL_EVENTS",
    "Shock",
    "shock_zscore",
    "shock_features",
    "long_signal",
    "make_shock",
    "tail_event_report",
]

TF = pd.Timedelta(hours=1)
TAIL_EVENTS = ("2021-05-19", "2022-11-09", "2025-10-10")

_BASE = {
    "sigma_window": 720,
    "sigma_min_frac": 2 / 3,
    "z_entry": -3.0,
    "btc_sigma_mult": -2.0,
    "btc_sma_n": 200,
    "atr_n": ATR_N,
    "stop_atr": 2.0,
    "risk": 0.0025,
    "hold_bars": 4,
}

SHOCK_CONFIGS: dict[str, dict] = {
    "H1": {**_BASE, "hold_bars": 4},
    "H2": {**_BASE, "hold_bars": 12},
    "H3": {**_BASE, "hold_bars": 24},
}


def shock_zscore(close: pd.Series, window: int = 720, min_frac: float = 2 / 3) -> pd.DataFrame:
    """
    ``r``, ``sigma`` and ``z = r / sigma`` per bar; ``sigma`` is the std (ddof=1)
    of the returns of the ``window`` bars before ``t``. NaN where undefined.
    """
    window = check_window(window, "window")
    r = close.astype(float).pct_change(fill_method=None)
    min_obs = max(2, math.ceil(min_frac * window))
    sigma = r.shift(1).rolling(window, min_periods=min_obs).std(ddof=1)
    sigma = sigma.where(sigma > 0)
    return pd.DataFrame({"r": r, "sigma": sigma, "z": r / sigma}, index=close.index)


def shock_features(df: pd.DataFrame, params: Mapping, btc_intraday: Optional[pd.DataFrame],
                   btc_daily: Optional[pd.DataFrame], tf=TF) -> pd.DataFrame:
    """
    Causal SHOCK features per 1h bar: ``close, r, sigma, z, atr`` of the symbol,
    ``btc_r, btc_sigma`` of the same bar and ``btc_d_close, btc_d_sma`` of the
    last BTC daily bar closed at ``t + 1h``.
    """
    idx = df.index
    zs = shock_zscore(df["close"], params["sigma_window"], params["sigma_min_frac"])
    out = pd.DataFrame(index=idx)
    out["close"] = df["close"].astype(float)
    out[["r", "sigma", "z"]] = zs.to_numpy()
    out["atr"] = atr(df, params["atr_n"])
    if btc_intraday is not None and len(btc_intraday):
        bz = shock_zscore(btc_intraday["close"], params["sigma_window"], params["sigma_min_frac"])
        bz = bz.reindex(idx)
        out["btc_r"], out["btc_sigma"] = bz["r"].to_numpy(), bz["sigma"].to_numpy()
    else:
        out["btc_r"] = out["btc_sigma"] = np.nan
    btc = btc_daily_trend(btc_daily, idx, tf, params["btc_sma_n"])
    out["btc_d_close"], out["btc_d_sma"] = btc.iloc[:, 0].to_numpy(), btc.iloc[:, 1].to_numpy()
    return out


def long_signal(row: Mapping, p: Mapping) -> bool:
    """True when the bar is an idiosyncratic downside shock in a BTC up-trend (§2.9)."""
    z, br, bs = row["z"], row["btc_r"], row["btc_sigma"]
    if not (pd.notna(z) and z <= p["z_entry"]):
        return False
    if not (pd.notna(br) and pd.notna(bs) and br > p["btc_sigma_mult"] * bs):
        return False
    bc, bsma = row["btc_d_close"], row["btc_d_sma"]
    return bool(pd.notna(bc) and pd.notna(bsma) and bc > bsma)


class Shock:
    """SHOCK event strategy (see the module docstring); ``config`` is ``H1``..``H3``."""

    def __init__(self, config: str = "H1", btc_symbol: str = BTC, **overrides):
        if config not in SHOCK_CONFIGS:
            raise StrategyError(f"unknown SHOCK config {config!r}; expected one of {list(SHOCK_CONFIGS)}")
        unknown = set(overrides) - set(_BASE)
        if unknown:
            raise StrategyError(f"unknown SHOCK parameters {sorted(unknown)}")
        self.params = {**SHOCK_CONFIGS[config], **overrides, "config": config}
        p = self.params
        if not (isinstance(p["hold_bars"], int) and p["hold_bars"] >= 1):
            raise StrategyError("hold_bars must be an int >= 1")
        if not (0 < p["risk"] <= 0.005 and p["stop_atr"] > 0):
            raise StrategyError("risk must be in (0, 0.5 %] and stop_atr > 0 (PLAN §7.3)")
        self.name = f"SHOCK-{config}"
        # sigma_window, z_entry, btc_sigma_mult, btc_sma_n, stop_atr, hold_bars
        self.n_free_params = 6
        self.tf = TF
        self._cache = FeatureCache(self._compute, btc_symbol)

    def _compute(self, symbol, df, daily, funding, btc_intraday, btc_daily) -> pd.DataFrame:
        if btc_intraday is None or btc_daily is None:
            raise StrategyError(f"SHOCK needs {self._cache.btc_symbol} 1h and 1d bars (systemic filter)")
        return shock_features(df, self.params, btc_intraday, btc_daily, self.tf)

    def prepare(self, panel: Mapping[str, pd.DataFrame], daily: Mapping[str, pd.DataFrame],
                btc_intraday: Optional[pd.DataFrame] = None,
                btc_daily: Optional[pd.DataFrame] = None) -> "Shock":
        """Precompute the causal features (fast path for backtests; same values as lazy)."""
        self._cache.prepare(panel, daily, None, btc_intraday=btc_intraday, btc_daily=btc_daily)
        return self

    def features(self, symbol: str) -> pd.DataFrame:
        return self._cache.frames[symbol]

    def on_bar(self, t, bars: dict[str, pd.Series], ctx: Context) -> list[OrderIntent]:
        p = self.params
        intents: list[OrderIntent] = []
        for s in bars:
            pos = ctx.position(s)
            if pos is not None:
                if pos.side == 1 and pos.bars_held >= p["hold_bars"]:
                    intents.append(OrderIntent(s, "SELL", reduce_only=True, tag=f"{self.name}_time_exit"))
                continue
            row = self._cache.row(s, t, ctx)
            if row is None or not long_signal(row, p):
                continue
            a, c = row["atr"], row["close"]
            if not (pd.notna(a) and a > 0 and pd.notna(c)):
                continue
            stop = c - p["stop_atr"] * a
            if not stop > 0:
                continue
            mult = getattr(ctx.kill_switch, "risk_mult", 1.0) if ctx.kill_switch is not None else 1.0
            if not (math.isfinite(ctx.nav) and ctx.nav > 0):
                continue
            qty = p["risk"] * mult * ctx.nav / (c - stop)
            if not (math.isfinite(qty) and qty > 0):
                continue
            intents.append(OrderIntent(s, "BUY", qty=float(qty), stop_price=float(stop),
                                       tag=f"{self.name}_long"))
        return intents


def make_shock(config: str, **overrides) -> Shock:
    """Factory used by the experiment runner (``H1``..``H3``)."""
    return Shock(config, **overrides)


def tail_event_report(round_trips: pd.DataFrame, events: Iterable[str] = TAIL_EVENTS,
                      nav: Optional[float] = None) -> pd.DataFrame:
    """
    Conditional loss on the tail days (PLAN §2.9, §5.4): for each UTC day, the
    round trips exposed during it (``entry_time < day end`` and
    ``exit_time >= day start``) with their count, P&L, worst R multiple and
    stop exits. ``pnl_pct`` is relative to ``nav`` when given.
    """
    rows = []
    rt = round_trips
    for ev in events:
        d0 = pd.Timestamp(ev, tz="UTC")
        d1 = d0 + pd.Timedelta(days=1)
        if len(rt):
            m = (rt["entry_time"] < d1) & (rt["exit_time"] >= d0)
            sel = rt[m]
        else:
            sel = rt
        pnl = float(sel["pnl"].sum()) if len(sel) else 0.0
        rows.append({
            "event": ev,
            "n_trades": int(len(sel)),
            "pnl": pnl,
            "pnl_pct": pnl / nav if nav else np.nan,
            "worst_r": float(sel["r_multiple"].min()) if len(sel) else np.nan,
            "n_stops": int(sel["exit_reason"].astype(str).str.startswith("stop").sum()) if len(sel) else 0,
        })
    return pd.DataFrame(rows).set_index("event")
