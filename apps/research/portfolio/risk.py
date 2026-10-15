"""
Simulated risk controls for the research backtests (PLAN.md §7.3-7.6, §1.4).

Thresholds come from ``config/risk_limits.yml`` (fixed by the user, never
optimised). Current user values:

- daily loss <= -2 %: no new entries (positions may only shrink);
- daily loss <= -5 %: close positions with leverage > 1 and every short, block
  all entries, alert;
- drawdown from peak >= 10 %: risk multiplier 0.5;
- drawdown from peak >= 20 %: close everything and stop (latched; a human
  must review before restarting).

In a daily backtest the state computed from the equity at the close of ``t``
applies to the targets decided at that close (filled at ``open[t+1]``).
Per-position leverage is capped at 1x on altcoins and 1.5x on BTC/ETH (isolated
margin; the user's absolute ceiling is 3x) and every leveraged entry must pass
the liquidation-distance check of ``apps.research.engine.liquidation``.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
import yaml

from apps.research.engine.liquidation import DEFAULT_MMR, liq_ok

logger = logging.getLogger(__name__)

__all__ = [
    "RiskConfig",
    "RiskConfigError",
    "RISK_LIMITS_PATH",
    "load_risk_config",
    "KillSwitchState",
    "KillSwitch",
    "simulate_kill_switch",
    "apply_kill_switch",
    "check_liquidation",
]

RISK_LIMITS_PATH = Path(__file__).resolve().parents[3] / "config" / "risk_limits.yml"

Level = Literal["normal", "block_entries", "flatten_leveraged", "halted"]

# Thresholds are inclusive; the tolerance keeps e.g. 99/110 counting as a 10 % drawdown.
_EPS = 1e-12


class RiskConfigError(ValueError):
    """Missing or inconsistent risk limits."""


@dataclass(frozen=True)
class RiskConfig:
    """User risk limits (fractions). Defaults mirror ``config/risk_limits.yml``."""

    daily_block_entries: float = -0.02
    daily_flatten_leveraged: float = -0.05
    dd_half_risk: float = 0.10
    dd_halt: float = 0.20
    half_risk_mult: float = 0.5
    max_lev_alt: float = 1.0
    max_lev_major: float = 1.5
    hard_max_leverage: float = 3.0
    majors: tuple = field(default=("BTCUSDT", "ETHUSDT"))

    def __post_init__(self) -> None:
        if not self.daily_flatten_leveraged < self.daily_block_entries < 0:
            raise RiskConfigError("daily thresholds must satisfy flatten < block_entries < 0")
        if not 0 < self.dd_half_risk < self.dd_halt < 1:
            raise RiskConfigError("drawdown thresholds must satisfy 0 < half_risk < halt < 1")
        if not 0 < self.half_risk_mult <= 1:
            raise RiskConfigError("half_risk_mult must be in (0, 1]")
        if not 0 < self.max_lev_alt <= self.hard_max_leverage:
            raise RiskConfigError("max_lev_alt must be in (0, hard_max_leverage]")
        if not 0 < self.max_lev_major <= self.hard_max_leverage:
            raise RiskConfigError("max_lev_major must be in (0, hard_max_leverage]")

    def max_leverage(self, symbol: str) -> float:
        """Effective leverage cap per position for ``symbol``."""
        return self.max_lev_major if symbol in self.majors else self.max_lev_alt


def load_risk_config(path: Path | str = RISK_LIMITS_PATH) -> RiskConfig:
    """Read ``config/risk_limits.yml``. Fails loudly: there are no silent defaults."""
    path = Path(path)
    if not path.exists():
        raise RiskConfigError(f"risk limits file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        daily = raw["daily_loss"]
        dd = raw["drawdown"]
        lev = raw["leverage"]
        values = dict(
            daily_block_entries=float(daily["block_entries"]),
            daily_flatten_leveraged=float(daily["flatten_leveraged"]),
            dd_half_risk=float(dd["half_risk"]),
            dd_halt=float(dd["halt"]),
            half_risk_mult=float(dd.get("half_risk_mult", 0.5)),
            max_lev_alt=float(lev["max_alt"]),
            max_lev_major=float(lev["max_major"]),
            hard_max_leverage=float(lev["hard_max"]),
        )
        if "majors" in lev:
            values["majors"] = tuple(lev["majors"])
        if str(lev.get("margin_type", "ISOLATED")).upper() != "ISOLATED":
            raise RiskConfigError("only ISOLATED margin is allowed")
    except (KeyError, TypeError) as exc:
        raise RiskConfigError(f"incomplete risk limits in {path}: {exc}") from exc
    return RiskConfig(**values)


@dataclass(frozen=True)
class KillSwitchState:
    """Kill-switch state known at the close of one bar."""

    level: Level = "normal"
    risk_mult: float = 1.0
    daily_return: float = 0.0
    drawdown: float = 0.0

    @property
    def halted(self) -> bool:
        return self.level == "halted"

    @property
    def entries_blocked(self) -> bool:
        return self.level != "normal"

    @property
    def flatten_leveraged(self) -> bool:
        return self.level in ("flatten_leveraged", "halted")


class KillSwitch:
    """
    Stateful simulator fed with the NAV at each daily close.

    The drawdown is measured from the running NAV peak; the daily return is
    close-to-close. The halt is latched: once triggered it never clears inside
    a backtest.
    """

    def __init__(self, cfg: Optional[RiskConfig] = None):
        self.cfg = cfg or RiskConfig()
        self.peak: Optional[float] = None
        self.prev_nav: Optional[float] = None
        self.halted = False

    def update(self, nav: float) -> KillSwitchState:
        if nav is None or not math.isfinite(nav):
            raise RiskConfigError(f"NAV must be finite, got {nav!r}")
        cfg = self.cfg
        daily = 0.0 if self.prev_nav in (None, 0) else nav / self.prev_nav - 1.0
        self.peak = nav if self.peak is None else max(self.peak, nav)
        dd = 0.0 if self.peak <= 0 else 1.0 - nav / self.peak
        self.prev_nav = nav

        if self.halted or dd >= cfg.dd_halt - _EPS or nav <= 0:
            if not self.halted:
                logger.warning("Kill-switch HALT: drawdown %.2f%% >= %.2f%%", dd * 100, cfg.dd_halt * 100)
            self.halted = True
            return KillSwitchState("halted", 0.0, daily, dd)

        risk_mult = cfg.half_risk_mult if dd >= cfg.dd_half_risk - _EPS else 1.0
        if daily <= cfg.daily_flatten_leveraged + _EPS:
            logger.warning("Kill-switch: daily loss %.2f%%, flattening leveraged/short positions", daily * 100)
            level: Level = "flatten_leveraged"
        elif daily <= cfg.daily_block_entries + _EPS:
            level = "block_entries"
        else:
            level = "normal"
        return KillSwitchState(level, risk_mult, daily, dd)


def simulate_kill_switch(equity: pd.Series, cfg: Optional[RiskConfig] = None) -> pd.DataFrame:
    """
    Kill-switch state for every date of an equity curve (state known at that close).

    Columns: ``daily_return``, ``drawdown``, ``level``, ``risk_mult``,
    ``entries_blocked``, ``flatten_leveraged``, ``halted``.
    """
    ks = KillSwitch(cfg)
    rows = []
    for nav in equity.to_numpy(dtype=float):
        st = ks.update(nav)
        rows.append((st.daily_return, st.drawdown, st.level, st.risk_mult,
                     st.entries_blocked, st.flatten_leveraged, st.halted))
    return pd.DataFrame(rows, index=equity.index, columns=[
        "daily_return", "drawdown", "level", "risk_mult",
        "entries_blocked", "flatten_leveraged", "halted",
    ])


def apply_kill_switch(
    w_target: pd.Series,
    w_held: pd.Series,
    state: KillSwitchState,
    leverage: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Constrain target weights with the kill-switch state.

    - halted: everything goes to 0;
    - the target is multiplied by ``state.risk_mult`` (half risk in drawdown);
    - entries blocked: no new positions, no sign flips and no increases, only
      reductions toward 0 (never below the held size in the same direction);
    - flatten_leveraged: additionally closes shorts and positions whose
      ``leverage`` (per symbol, effective) is above 1.
    """
    idx = w_target.index.union(w_held.index)
    target = w_target.reindex(idx).astype(float).fillna(0.0)
    held = w_held.reindex(idx).astype(float).fillna(0.0)
    if state.halted:
        return pd.Series(0.0, index=idx, name=w_target.name)

    out = target * state.risk_mult
    if state.entries_blocked:
        same_dir = np.sign(out) == np.sign(held)
        shrunk = np.sign(held) * np.minimum(out.abs(), held.abs())
        out = shrunk.where(same_dir & (held != 0), 0.0)
    if state.flatten_leveraged:
        lev = (leverage.reindex(idx).astype(float).fillna(1.0)
               if leverage is not None else pd.Series(1.0, index=idx))
        out = out.where((out >= 0) & (lev <= 1.0), 0.0)
    out = out + 0.0
    out.name = w_target.name
    return out


def check_liquidation(
    symbol: str,
    entry: float,
    stop: float,
    lev: float,
    side: int,
    worst_wick_t: float,
    cfg: Optional[RiskConfig] = None,
    mmr: float = DEFAULT_MMR,
) -> bool:
    """
    Pre-trade futures check: leverage within the per-symbol cap and the
    liquidation distance ``>= max(3 * dist_stop, worst historical wick)``.
    """
    cfg = cfg or RiskConfig()
    if lev > cfg.max_leverage(symbol) + 1e-12:
        logger.info("%s: leverage %.2f above cap %.2f", symbol, lev, cfg.max_leverage(symbol))
        return False
    return liq_ok(entry, stop, lev, side, worst_wick_t, mmr)

