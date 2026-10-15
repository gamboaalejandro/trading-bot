"""
Risk-reducing overlays on top of a TREND signal (PLAN.md §2.4, §2.5).

Overlays wrap a :class:`~apps.research.strategies.base.TargetWeightStrategy`
and can only REDUCE exposure:

- REGIME (R1-R3): BTC regime multiplier ``m_t in (0, 1]`` on the LONG weights
  of every coin (BTC and altcoins).

  ======  ==================================================================
  R1      ``m = 1`` if ``C_BTC > SMA200`` else ``0.5``
  R2      ``m = 1`` if ``C > SMA200`` and ``SMA50 > SMA200``; ``0.5`` if only
          one holds; ``0.25`` if none
  R3      R2 x (``0.5`` if the expanding (>= 365 d) percentile of
          ``ATR%_BTC`` is > 80, else ``1``)
  ======  ==================================================================

- FVETO (F1-F3): per-symbol funding crowding, using the funding known at the
  close of ``t`` (settlements with timestamp <= close, via
  :func:`apps.research.features.funding.funding_features`).

  ======  ==================================================================
  F1      ``fund_pct >= 95`` or ``APR(F_bar_3d) > 50 %``: no new long entries
          (``E_q`` cannot rise); open positions are kept
  F2      same trigger: ``w_i <- 0.5 w_i``
  F3      ``fund_pct >= 90``: ``w_i <- 0.5 w_i``
  ======  ==================================================================

  BNBUSDT is excluded (anomalous funding, PLAN §5.2.2): it is never modified
  and its funding is never read.

Why weights and not ``E``: layer D scales the whole portfolio to ``sigma_p*``,
so multiplying the signal of every symbol by ``m`` would be undone by the vol
target. Multipliers are therefore exposed through ``weight_multiplier`` (see
:class:`~apps.research.strategies.base.WeightOverlayStrategy`) and applied by
:func:`apps.research.engine.portfolio_bt.run_portfolio_bt` after
``target_weights`` and before the kill-switch and the no-trade band (the band
cannot undo a reduction). F1 changes the signal itself (an entry rule).

Conventions [OPINION, fixed a priori, documented]:

- Multipliers act on long exposure only (the base signal ``E > 0`` at ``t``);
  short or flat rows get ``1``.
- Undefined inputs never reduce: ``m = 1`` while BTC's SMA200/SMA50 are
  undefined, the ATR factor is ``1`` while its percentile is undefined, and a
  funding trigger with NaN inputs (e.g. before the perp existed, spot
  2017-2019) does not fire. The overlay is then identical to its base.
- A non-BNB symbol without a funding series raises (no imputation). In spot
  backtests the perp funding must be passed explicitly (``funding=``), since
  the spot engine gives strategies no funding.
- Overlays compose: ``RegimeOverlay(FundingVeto(T3, "F2"), "R1")`` multiplies
  both factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.data.loader import FUNDING_EXCLUDED
from apps.research.features.funding import funding_features
from apps.research.features.trend import sma
from apps.research.features.volatility import PCTL_MIN_DAYS, atr_pct_pctl
from apps.research.portfolio.sizing import discretize
from apps.research.strategies.base import Context, TargetWeightStrategy, weight_multiplier_of
from apps.research.strategies.trend import BTC_SYMBOL, StrategyError

__all__ = [
    "REGIME_CONFIGS",
    "FVETO_CONFIGS",
    "FVetoRule",
    "regime_multiplier",
    "funding_trigger",
    "block_increases",
    "RegimeOverlay",
    "FundingVeto",
]

RegimeRule = Literal["R1", "R2", "R3"]
REGIME_CONFIGS: tuple[str, ...] = ("R1", "R2", "R3")
ATR_PCTL_HIGH = 80.0


@dataclass(frozen=True)
class FVetoRule:
    """One FVETO configuration (PLAN §2.5)."""

    config_id: str
    pct_threshold: float                 # fund_pct >= threshold fires
    apr_threshold: Optional[float]       # APR(F_bar_3d) > threshold fires (None = unused)
    action: Literal["block", "halve"]


FVETO_CONFIGS: dict[str, FVetoRule] = {
    "F1": FVetoRule("F1", 95.0, 0.50, "block"),
    "F2": FVetoRule("F2", 95.0, 0.50, "halve"),
    "F3": FVetoRule("F3", 90.0, None, "halve"),
}


# --------------------------------------------------------------------------- REGIME
def regime_multiplier(btc_1d: pd.DataFrame, rule: RegimeRule = "R1",
                      pctl_min_days: int = PCTL_MIN_DAYS) -> pd.Series:
    """
    BTC regime multiplier ``m_t in (0, 1]`` known at the close of ``t`` (R1-R3).
    Undefined inputs give ``m = 1`` (never reduce on missing information).
    """
    if rule not in REGIME_CONFIGS:
        raise StrategyError(f"unknown REGIME config {rule!r} (expected {list(REGIME_CONFIGS)})")
    if "close" not in btc_1d.columns:
        raise StrategyError("BTC frame lacks a close column")
    c = btc_1d["close"].astype(float)
    s200 = sma(c, 200)
    above = (c > s200).astype(float).where(c.notna() & s200.notna())
    if rule == "R1":
        m = pd.Series(np.where(above == 0.0, 0.5, 1.0), index=c.index)
    else:
        s50 = sma(c, 50)
        golden = (s50 > s200).astype(float).where(s50.notna() & s200.notna())
        n_ok = above + golden                                  # NaN if either is undefined
        m = n_ok.map({2.0: 1.0, 1.0: 0.5, 0.0: 0.25}).fillna(1.0)
        if rule == "R3":
            pctl = atr_pct_pctl(btc_1d, min_days=pctl_min_days)
            m = m * pd.Series(np.where(pctl > ATR_PCTL_HIGH, 0.5, 1.0), index=c.index)
    return m.astype(float).rename(f"m_{rule}")


def _btc(panel: Mapping[str, pd.DataFrame], btc: Optional[pd.DataFrame], symbol: str) -> pd.DataFrame:
    if btc is not None:
        return btc
    if symbol in panel:
        return panel[symbol]
    raise StrategyError(f"REGIME needs {symbol} daily bars (panel or btc=)")


def _compose(own: pd.DataFrame, base: TargetWeightStrategy, panel, ctx) -> pd.DataFrame:
    inner = weight_multiplier_of(base, panel, ctx)
    if inner is None:
        return own
    inner = inner.reindex(index=own.index, columns=own.columns).fillna(1.0)
    return own * inner


def _long_rows(E: pd.DataFrame) -> pd.DataFrame:
    return E.fillna(0.0) > 0


@dataclass
class RegimeOverlay:
    """REGIME overlay (R1-R3) on the long weights of ``base`` (PLAN §2.4)."""

    base: TargetWeightStrategy
    rule: RegimeRule = "R1"
    btc: Optional[pd.DataFrame] = None
    btc_symbol: str = BTC_SYMBOL
    name: str = ""
    params: dict = field(default_factory=dict)
    n_free_params: int = 0

    def __post_init__(self) -> None:
        if self.rule not in REGIME_CONFIGS:
            raise StrategyError(f"unknown REGIME config {self.rule!r}")
        self.name = self.name or f"{self.base.name}+REGIME-{self.rule}"
        self.params = {"base": dict(getattr(self.base, "params", {}) or {}), "regime": self.rule,
                       **self.params}
        own = {"R1": 1, "R2": 2, "R3": 3}[self.rule]
        self.n_free_params = self.n_free_params or getattr(self.base, "n_free_params", 0) + own

    def signal(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        return self.base.signal(panel, ctx)

    def multiplier(self, panel: Mapping[str, pd.DataFrame]) -> pd.Series:
        return regime_multiplier(_btc(panel, self.btc, self.btc_symbol), self.rule)

    def weight_multiplier(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        E = self.base.signal(panel, ctx)
        m = self.multiplier(panel).reindex(E.index).fillna(1.0)
        own = pd.DataFrame({s: m for s in E.columns}, index=E.index).where(_long_rows(E), 1.0)
        return _compose(own, self.base, panel, ctx)


# --------------------------------------------------------------------------- FVETO
def funding_trigger(feats: pd.DataFrame, rule: FVetoRule) -> pd.Series:
    """
    Crowding trigger per daily bar from :func:`funding_features` columns
    ``fund_pct`` and ``apr_3d``. NaN inputs do not fire.
    """
    fired = (feats["fund_pct"] >= rule.pct_threshold).fillna(False)
    if rule.apr_threshold is not None:
        fired = fired | (feats["apr_3d"] > rule.apr_threshold).fillna(False)
    return fired.astype(bool).rename(f"trigger_{rule.config_id}")


def block_increases(E_q: pd.Series, blocked: pd.Series) -> pd.Series:
    """
    F1 entry rule on a discretised signal: while ``blocked``, the long exposure
    cannot rise above the previous effective value (positions are kept, exits
    and reductions pass through). NaN rows stay NaN (flat for the engine).
    """
    e = E_q.to_numpy(dtype=float)
    b = blocked.reindex(E_q.index).fillna(False).to_numpy(dtype=bool)
    out = np.full(len(e), np.nan)
    prev = 0.0
    for i, v in enumerate(e):
        if not np.isfinite(v):
            prev = 0.0
            continue
        cur = min(v, max(prev, 0.0)) if (b[i] and v > 0) else v
        out[i] = cur
        prev = cur
    return pd.Series(out, index=E_q.index, name=E_q.name)


@dataclass
class FundingVeto:
    """
    FVETO overlay (F1-F3) on ``base`` (PLAN §2.5). ``funding`` maps symbol ->
    settlement series (fraction); it defaults to ``ctx.funding`` (futures).
    """

    base: TargetWeightStrategy
    rule: str = "F2"
    funding: Optional[Mapping[str, pd.Series]] = None
    step: float = 0.25
    name: str = ""
    params: dict = field(default_factory=dict)
    n_free_params: int = 0

    def __post_init__(self) -> None:
        if self.rule not in FVETO_CONFIGS:
            raise StrategyError(f"unknown FVETO config {self.rule!r} (expected {sorted(FVETO_CONFIGS)})")
        self.cfg = FVETO_CONFIGS[self.rule]
        self.name = self.name or f"{self.base.name}+FVETO-{self.rule}"
        self.params = {"base": dict(getattr(self.base, "params", {}) or {}), "fveto": self.rule,
                       **self.params}
        own = 2 if self.cfg.apr_threshold is not None else 1
        self.n_free_params = self.n_free_params or getattr(self.base, "n_free_params", 0) + own

    def _funding(self, ctx: Optional[Context]) -> Mapping[str, pd.Series]:
        if self.funding is not None:
            return self.funding
        return ctx.funding if ctx is not None else {}

    def triggers(self, panel: Mapping[str, pd.DataFrame], ctx: Optional[Context] = None,
                 index: Optional[pd.DatetimeIndex] = None) -> pd.DataFrame:
        """Boolean trigger per symbol and date (BNBUSDT always False, funding not read)."""
        funding = self._funding(ctx)
        cols = {}
        for s, df in panel.items():
            if s in FUNDING_EXCLUDED:
                cols[s] = pd.Series(False, index=df.index)
                continue
            f = funding.get(s)
            if f is None:
                raise StrategyError(f"{s}: no funding for FVETO (no imputation)")
            f = f.copy()
            f.attrs = {**f.attrs, "symbol": f.attrs.get("symbol", s)}
            cols[s] = funding_trigger(funding_features(f, df.index), self.cfg)
        out = pd.DataFrame(cols, index=index)
        return out.fillna(False).astype(bool)

    def signal(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        E = self.base.signal(panel, ctx)
        if self.cfg.action != "block":
            return E
        E_q = discretize(E, self.step)
        trig = self.triggers(panel, ctx, E.index)
        out = {s: block_increases(E_q[s], trig[s]) if s in trig.columns else E_q[s] for s in E.columns}
        return pd.DataFrame(out, index=E.index)

    def weight_multiplier(self, panel: dict[str, pd.DataFrame], ctx: Optional[Context] = None) -> pd.DataFrame:
        E = self.signal(panel, ctx)
        own = pd.DataFrame(1.0, index=E.index, columns=E.columns)
        if self.cfg.action == "halve":
            trig = self.triggers(panel, ctx, E.index).reindex(columns=E.columns, fill_value=False)
            own = own.mask(trig & _long_rows(E), 0.5)
        return _compose(own, self.base, panel, ctx)
