"""
Daily trend family TREND (PLAN.md §2.2) and the conditioned short leg SHORT (§2.3).

All signals follow :class:`~apps.research.strategies.base.TargetWeightStrategy`:
the row labelled ``t`` (bar OPEN time, as in the loader) is computed with data
up to the CLOSE of ``t`` and is filled by the engine at ``open[t + 1]``.
Truncating the input at ``t`` never changes the value at ``t`` (tested).

TREND-DON
    Donchian sub-models on CLOSES (:func:`apps.research.features.trend.donchian`,
    ``UP_n(t) = max(C_{t-n..t-1})``) with ``n in {5, 10, 20, 30, 60, 90, 150, 250, 360}``.
    Flat and ``C_t > UP_n(t)`` -> ``pos_n = 1`` with ``S_n = MID_n(t)``; every
    day ``S_n(t) = max(S_n(t-1), MID_n(t))``; ``C_t < S_n(t)`` -> ``pos_n = 0``.
    ``E_t = mean_n(pos_n)``.
TREND-TSM
    ``E_t = mean_k 1{C_t > SMA_{n_k}(t)}`` with ``n in {10, 20, 40, 50, 100, 200}``.
TREND-MIX
    ``E_t = 0.5 E_DON + 0.5 E_TSM``.

Conventions [OPINION, fixed a priori, documented]:

- Warm-up: ``E`` is NaN ("no opinion", flat for the engine) until every
  sub-model of the signal is defined (e.g. 360 prior closes for DON). The
  sub-model state machines run from the first defined channel, so the value at
  ``t`` only depends on data ``<= t``.
- A missing close (hole in the data) never triggers an entry or an exit: the
  state is kept and ``E`` repeats the previous value (no price is imputed; the
  engine raises if it has to mark an open position without a price).
- A missing ``MID_n(t)`` keeps the trailing level ``S_n(t-1)``.
- After an exit the sub-model cannot re-enter on the same bar.
- The signals are returned raw (``k/9``, ``k/6``...). Layer D discretises them
  to quarters (``E_q = round(4E)/4``) with :class:`~apps.research.portfolio.sizing.SizingConfig`.

SHORT (perps only, §2.3)
    Mirror Donchian sub-models with ``n in {20, 30, 60, 90, 150, 250, 360}``:
    entry if ``C_t < DN_n`` with ``S_n = MID_n``, trailing
    ``S_n(t) = min(S_n(t-1), MID_n(t))``, exit if ``C_t > S_n``.
    ``E_s = mean`` discretised to quarters and the combined signal is
    ``E = E_q,long(T3) - k * E_s,q``, so that layer D builds
    ``w = (E_q,long - k E_s,q) / sigma_90`` with the same ``Sigma_s`` and the
    gross short cap of 0.5.

    - The short leg is active only while BTC closes below its SMA200
      (``C_1d < SMA200_1d`` at the close of ``t``). Short sub-models can only
      enter while the gate is on and are reset to flat when it is off (or
      undefined).
    - Funding veto: no new short sub-model entry while
      ``APR(F_bar_3d) < -25 %`` (shorts would pay more than 25 % a year) or
      while that APR is unknown (conservative); open shorts are kept.
    - BNBUSDT never gets a short (its funding is excluded, PLAN §5.2.2).
    - ``E`` takes values on a 1/16 grid: run it with
      :func:`sizing_config` (``step = 1/16``), otherwise quarter rounding would
      distort ``k * E_s,q``.

Configurations (fixed before seeing results): T1-T5 (:data:`TREND_CONFIGS`),
S1 (``k = 0.5``) and S2 (``k = 0.25``) on top of T3 (:data:`SHORT_CONFIGS`).
``n_free_params`` counts the a-priori choices of each signal (window sets, mix
weight, ``k``, veto threshold); it feeds the adaptability penalty of §3.3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from apps.research.data.loader import FUNDING_EXCLUDED
from apps.research.features.funding import funding_features
from apps.research.features.trend import donchian, sma
from apps.research.portfolio.sizing import SizingConfig, discretize
from apps.research.strategies.base import Context

__all__ = [
    "StrategyError",
    "DON_WINDOWS",
    "TSM_WINDOWS",
    "SHORT_WINDOWS",
    "SHORT_FUNDING_VETO_APR",
    "SHORT_SIZING_STEP",
    "BTC_SYMBOL",
    "TrendConfig",
    "TREND_CONFIGS",
    "SHORT_CONFIGS",
    "donchian_trail",
    "donchian_long_state",
    "donchian_short_state",
    "don_signal",
    "tsm_signal",
    "mix_signal",
    "btc_below_sma",
    "TrendStrategy",
    "TrendWithShort",
    "make_trend",
    "make_short",
    "sizing_config",
]

DON_WINDOWS: tuple[int, ...] = (5, 10, 20, 30, 60, 90, 150, 250, 360)
TSM_WINDOWS: tuple[int, ...] = (10, 20, 40, 50, 100, 200)
SHORT_WINDOWS: tuple[int, ...] = (20, 30, 60, 90, 150, 250, 360)
SHORT_FUNDING_VETO_APR = -0.25
SHORT_SIZING_STEP = 1 / 16
BTC_SYMBOL = "BTCUSDT"
SIGNAL_STEP = 0.25

SignalKind = Literal["DON", "TSM", "MIX"]


class StrategyError(ValueError):
    """Invalid strategy inputs (missing BTC frame, missing funding...)."""


# --------------------------------------------------------------------------- state machines
def donchian_trail(close: pd.Series, n: int, side: int = 1,
                   allowed: Optional[pd.Series] = None,
                   active: Optional[pd.Series] = None) -> pd.DataFrame:
    """
    State of one Donchian sub-model: ``pos`` (1 = in the trade, 0 = flat, NaN =
    channel not yet defined) and the trailing exit level ``stop`` (``S_n``, NaN
    when flat). ``side=+1``: long breakout above ``UP_n``; ``side=-1``: short
    breakdown below ``DN_n``. ``allowed`` (bool per bar) gates new entries;
    ``active`` (bool per bar) forces the sub-model flat when False.
    """
    if side not in (1, -1):
        raise StrategyError(f"side must be +1 or -1, got {side!r}")
    ch = donchian(close, n)
    c = close.to_numpy(dtype=float)
    trigger = (ch["up"] if side > 0 else ch["dn"]).to_numpy(dtype=float)
    mid = ch["mid"].to_numpy(dtype=float)
    ok_entry = np.ones(len(c), dtype=bool) if allowed is None else \
        allowed.reindex(close.index).fillna(False).to_numpy(dtype=bool)
    on = np.ones(len(c), dtype=bool) if active is None else \
        active.reindex(close.index).fillna(False).to_numpy(dtype=bool)

    out = np.full(len(c), np.nan)
    stops = np.full(len(c), np.nan)
    pos, stop, started = 0, math.nan, False
    for i in range(len(c)):
        if not started:
            if not math.isfinite(trigger[i]):
                continue
            started = True
        if not on[i]:
            pos, stop = 0, math.nan
            out[i] = 0.0
            continue
        ci = c[i]
        if not math.isfinite(ci):
            out[i], stops[i] = pos, stop
            continue
        if pos:
            if math.isfinite(mid[i]):
                stop = max(stop, mid[i]) if side > 0 else min(stop, mid[i])
            if (side > 0 and ci < stop) or (side < 0 and ci > stop):
                pos, stop = 0, math.nan
        elif ok_entry[i] and math.isfinite(trigger[i]) and math.isfinite(mid[i]) and (
                (side > 0 and ci > trigger[i]) or (side < 0 and ci < trigger[i])):
            pos, stop = 1, mid[i]
        out[i] = pos
        stops[i] = stop
    return pd.DataFrame({"pos": out, "stop": stops}, index=close.index)


def _donchian_state(close: pd.Series, n: int, side: int,
                    allowed: Optional[pd.Series] = None,
                    active: Optional[pd.Series] = None) -> pd.Series:
    return donchian_trail(close, n, side, allowed, active)["pos"].rename(f"pos_{n}")


def donchian_long_state(close: pd.Series, n: int) -> pd.Series:
    """Long Donchian sub-model ``pos_n`` (TREND-DON)."""
    return _donchian_state(close, n, +1)


def donchian_short_state(close: pd.Series, n: int, allowed: Optional[pd.Series] = None,
                         active: Optional[pd.Series] = None) -> pd.Series:
    """Mirror (short) Donchian sub-model; 1 means short (SHORT, §2.3)."""
    return _donchian_state(close, n, -1, allowed, active)


def _hold_over_holes(E: pd.Series, close: pd.Series) -> pd.Series:
    """Rows without a close repeat the previous value (no entry/exit without a price)."""
    missing = close.isna()
    if not missing.any():
        return E
    held = E.mask(missing).ffill()
    return E.where(~missing, held)


def don_signal(close: pd.Series, windows: Sequence[int] = DON_WINDOWS) -> pd.Series:
    """TREND-DON ``E_t = mean_n(pos_n)``; NaN until every sub-model is defined."""
    states = pd.concat([donchian_long_state(close, n) for n in windows], axis=1)
    E = states.mean(axis=1, skipna=False)
    return _hold_over_holes(E, close).rename("E_don")


def tsm_signal(close: pd.Series, windows: Sequence[int] = TSM_WINDOWS) -> pd.Series:
    """TREND-TSM ``E_t = mean_k 1{C_t > SMA_{n_k}(t)}``; NaN until every SMA is defined."""
    cols = []
    for n in windows:
        s = sma(close, n)
        cols.append((close > s).astype(float).where(s.notna() & close.notna()))
    E = pd.concat(cols, axis=1).mean(axis=1, skipna=False)
    return _hold_over_holes(E, close).rename("E_tsm")


def mix_signal(close: pd.Series, don_windows: Sequence[int] = DON_WINDOWS,
               tsm_windows: Sequence[int] = TSM_WINDOWS, w_don: float = 0.5) -> pd.Series:
    """TREND-MIX ``E_t = 0.5 E_DON + 0.5 E_TSM`` (NaN if either is undefined)."""
    E = w_don * don_signal(close, don_windows) + (1.0 - w_don) * tsm_signal(close, tsm_windows)
    return E.rename("E_mix")


def btc_below_sma(btc_1d: pd.DataFrame, n: int = 200) -> pd.Series:
    """
    Short-leg gate: 1.0 if BTC ``C_1d < SMA_n`` at the close of ``t``, 0.0 if
    not, NaN while undefined (no close or SMA).
    """
    if "close" not in btc_1d.columns:
        raise StrategyError("BTC frame lacks a close column")
    c = btc_1d["close"].astype(float)
    s = sma(c, n)
    return (c < s).astype(float).where(c.notna() & s.notna()).rename("btc_below_sma")


# --------------------------------------------------------------------------- configs
@dataclass(frozen=True)
class TrendConfig:
    """One preregistered TREND configuration (PLAN §2.2)."""

    config_id: str
    signal: SignalKind
    sigma_target: float = 0.15
    band: float = 0.20


TREND_CONFIGS: dict[str, TrendConfig] = {
    "T1": TrendConfig("T1", "DON", 0.15, 0.20),
    "T2": TrendConfig("T2", "TSM", 0.15, 0.20),
    "T3": TrendConfig("T3", "MIX", 0.15, 0.20),   # primary preregistered configuration
    "T4": TrendConfig("T4", "MIX", 0.20, 0.20),
    "T5": TrendConfig("T5", "MIX", 0.15, 0.10),
}

#: SHORT configurations: ``k`` of the short leg on top of T3 (PLAN §2.3).
SHORT_CONFIGS: dict[str, float] = {"S1": 0.5, "S2": 0.25}

_N_FREE = {"DON": 1, "TSM": 1, "MIX": 3}   # window set(s) and the mix weight


def _symbol_frames(panel: Mapping[str, pd.DataFrame]) -> dict[str, pd.Series]:
    if not panel:
        raise StrategyError("empty panel")
    out = {}
    for sym, df in panel.items():
        if "close" not in df.columns:
            raise StrategyError(f"{sym}: frame lacks a close column")
        if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_monotonic_increasing:
            raise StrategyError(f"{sym}: index must be a sorted DatetimeIndex")
        out[sym] = df["close"].astype(float)
    return out


def _all_dates(panel: Mapping[str, pd.DataFrame]) -> pd.DatetimeIndex:
    dates = None
    for df in panel.values():
        dates = df.index if dates is None else dates.union(df.index)
    return dates


@dataclass
class TrendStrategy:
    """TREND-DON / TSM / MIX long-only exposure signal (PLAN §2.2)."""

    kind: SignalKind = "MIX"
    config_id: str = ""
    don_windows: tuple = DON_WINDOWS
    tsm_windows: tuple = TSM_WINDOWS
    name: str = ""
    params: dict = field(default_factory=dict)
    n_free_params: int = 0

    def __post_init__(self) -> None:
        if self.kind not in ("DON", "TSM", "MIX"):
            raise StrategyError(f"unknown TREND signal {self.kind!r}")
        self.name = self.name or f"TREND-{self.kind}" + (f"-{self.config_id}" if self.config_id else "")
        self.params = {"signal": self.kind, "don_windows": list(self.don_windows),
                       "tsm_windows": list(self.tsm_windows), **self.params}
        self.n_free_params = self.n_free_params or _N_FREE[self.kind]

    def symbol_signal(self, close: pd.Series) -> pd.Series:
        if self.kind == "DON":
            return don_signal(close, self.don_windows)
        if self.kind == "TSM":
            return tsm_signal(close, self.tsm_windows)
        return mix_signal(close, self.don_windows, self.tsm_windows)

    def signal(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        closes = _symbol_frames(panel)
        out = pd.DataFrame({s: self.symbol_signal(c) for s, c in closes.items()},
                           index=_all_dates(panel))
        return out.clip(lower=0.0, upper=1.0)


@dataclass
class TrendWithShort:
    """
    TREND long leg plus the conditioned short leg in perps (PLAN §2.3).

    ``E = discretize(E_long) - k * discretize(E_s)`` (values on a 1/16 grid).
    ``funding`` (settlements per symbol, fraction) defaults to ``ctx.funding``;
    every shorted symbol needs it (no imputation). ``btc`` defaults to
    ``panel[btc_symbol]``.
    """

    long: TrendStrategy
    k: float = 0.5
    config_id: str = ""
    windows: tuple = SHORT_WINDOWS
    veto_apr: float = SHORT_FUNDING_VETO_APR
    btc_sma: int = 200
    btc_symbol: str = BTC_SYMBOL
    btc: Optional[pd.DataFrame] = None
    funding: Optional[Mapping[str, pd.Series]] = None
    name: str = ""
    params: dict = field(default_factory=dict)
    n_free_params: int = 0

    def __post_init__(self) -> None:
        if not 0 < self.k <= 1:
            raise StrategyError(f"k must be in (0, 1], got {self.k!r}")
        if not math.isclose(self.k / SIGNAL_STEP, round(self.k / SIGNAL_STEP)):
            # k * E_s,q must stay on the 1/16 grid used by sizing_config().
            raise StrategyError(f"k must be a multiple of {SIGNAL_STEP}, got {self.k!r}")
        self.name = self.name or f"SHORT-{self.config_id or self.k}+{self.long.name}"
        self.params = {"long": dict(self.long.params), "k": self.k, "short_windows": list(self.windows),
                       "veto_apr": self.veto_apr, "btc_gate": f"C<SMA{self.btc_sma}", **self.params}
        self.n_free_params = self.n_free_params or self.long.n_free_params + 3

    # -- inputs
    def _btc_frame(self, panel: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        if self.btc is not None:
            return self.btc
        if self.btc_symbol in panel:
            return panel[self.btc_symbol]
        raise StrategyError(f"the short leg needs {self.btc_symbol} daily bars (panel or btc=)")

    def _funding(self, ctx: Optional[Context]) -> Mapping[str, pd.Series]:
        if self.funding is not None:
            return self.funding
        if ctx is not None:
            return ctx.funding
        return {}

    def short_apr(self, symbol: str, index: pd.DatetimeIndex,
                  funding: Mapping[str, pd.Series]) -> pd.Series:
        """``APR(F_bar_3d)`` known at the close of each daily bar of ``symbol``."""
        if symbol not in funding or funding[symbol] is None:
            raise StrategyError(f"{symbol}: no funding for the short-leg veto (no imputation)")
        f = funding[symbol].copy()
        f.attrs = {**f.attrs, "symbol": f.attrs.get("symbol", symbol)}
        return funding_features(f, index)["apr_3d"]

    def short_signal(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        """Quarter-discretised short exposure ``E_s,q`` in [0, 1] (1 = fully short)."""
        closes = _symbol_frames(panel)
        dates = _all_dates(panel)
        gate = btc_below_sma(self._btc_frame(panel), self.btc_sma) == 1.0
        funding = self._funding(ctx)
        out = {}
        for s, c in closes.items():
            if s in FUNDING_EXCLUDED:
                out[s] = pd.Series(0.0, index=c.index)
                continue
            active = gate.reindex(c.index).fillna(False).astype(bool)
            apr_ = self.short_apr(s, c.index, funding)
            allowed = active & (apr_ >= self.veto_apr).fillna(False)
            states = pd.concat([donchian_short_state(c, n, allowed, active) for n in self.windows], axis=1)
            Es = _hold_over_holes(states.mean(axis=1, skipna=False), c)
            out[s] = Es
        E_s = pd.DataFrame(out, index=dates)
        return discretize(E_s, SIGNAL_STEP)

    def signal(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        long_q = discretize(self.long.signal(panel, ctx), SIGNAL_STEP)
        short_q = self.short_signal(panel, ctx).reindex_like(long_q)
        # Long and short legs net per coin (one-way mode). NaN in a leg = no opinion (0)
        # unless both are NaN.
        both_nan = long_q.isna() & short_q.isna()
        E = long_q.fillna(0.0) - self.k * short_q.fillna(0.0)
        return E.mask(both_nan).clip(lower=-1.0, upper=1.0)


# --------------------------------------------------------------------------- factories
def make_trend(config_id: str = "T3") -> TrendStrategy:
    """Signal of a preregistered TREND configuration (T1-T5)."""
    if config_id not in TREND_CONFIGS:
        raise StrategyError(f"unknown TREND config {config_id!r} (expected {sorted(TREND_CONFIGS)})")
    cfg = TREND_CONFIGS[config_id]
    return TrendStrategy(kind=cfg.signal, config_id=config_id,
                         params={"config": config_id, "sigma_target": cfg.sigma_target, "band": cfg.band})


def make_short(config_id: str = "S1", btc: Optional[pd.DataFrame] = None,
               funding: Optional[Mapping[str, pd.Series]] = None) -> TrendWithShort:
    """SHORT S1 (k = 0.5) / S2 (k = 0.25) on top of T3."""
    if config_id not in SHORT_CONFIGS:
        raise StrategyError(f"unknown SHORT config {config_id!r} (expected {sorted(SHORT_CONFIGS)})")
    return TrendWithShort(long=make_trend("T3"), k=SHORT_CONFIGS[config_id], config_id=config_id,
                          btc=btc, funding=funding, params={"config": config_id})


def sizing_config(config_id: str = "T3", **overrides) -> SizingConfig:
    """
    Layer-D configuration of a TREND (T1-T5) or SHORT (S1/S2, on top of T3) config.

    SHORT configs use ``step = 1/16`` because their signal is already
    discretised (``E_q,long - k E_s,q``).
    """
    if config_id in SHORT_CONFIGS:
        base = TREND_CONFIGS["T3"]
        kw = {"sigma_target": base.sigma_target, "band": base.band, "step": SHORT_SIZING_STEP}
    elif config_id in TREND_CONFIGS:
        base = TREND_CONFIGS[config_id]
        kw = {"sigma_target": base.sigma_target, "band": base.band}
    else:
        raise StrategyError(f"unknown config {config_id!r}")
    kw.update(overrides)
    return SizingConfig(**kw)
