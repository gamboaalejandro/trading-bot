"""
Live kill-switch (PLAN.md §7.6) driven by the user's config/risk_limits.yml.

Levels, evaluated on every equity update:

- NORMAL           : everything allowed.
- BLOCK_ENTRIES    : daily loss <= ``daily_loss_block_entries`` (default file: -2 %).
                     Only reduce-only orders until the next UTC day.
- FLATTEN          : daily loss <= ``daily_loss_flatten`` (-5 %). Close every
                     position with leverage > 1 and every short, block all
                     new orders except reduce-only ones, alert.
                     Lasts until the next UTC day.
- HALT             : drawdown from the high-water mark >= ``drawdown_halt`` (20 %).
                     Same actions as FLATTEN, but sticky: only a manual
                     ``reset_halt`` (human review) clears it.

Daily P&L is measured against the equity at 00:00 UTC (explicit snapshot from
the caller, else the last equity persisted before the day change). Updates
older than the last accepted one are rejected (``StaleObservationError``).

Independently, drawdown >= ``drawdown_half_risk`` (10 %) halves the risk
multiplier applied to target weights.

Thresholds are never optimised and there are no hidden defaults: every key of
the YAML file is mandatory. Without a valid, user-confirmed file the bot does
not start in ``live`` mode (see ``assert_can_start``).
"""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

logger = logging.getLogger(__name__)

DEFAULT_RISK_LIMITS_PATH = Path(__file__).resolve().parents[2] / "config" / "risk_limits.yml"

TRADING_MODES = ("dry_run", "spot_demo", "futures_testnet", "live")

# Non-negotiable ceilings from PLAN.md §7. The user's file may be stricter,
# never looser.
PLAN_MAX_GROSS_LONG = 1.0
PLAN_MAX_GROSS_SHORT = 0.5
PLAN_MAX_WEIGHT_MAJOR = 0.35
PLAN_MAX_WEIGHT_ALT = 0.20
PLAN_MAX_ALTS_TOTAL = 0.60
PLAN_MAX_BETA_BTC = 1.0
PLAN_MAX_RISK_PER_TRADE = 0.005
PLAN_MAX_LEVERAGE_MAJOR = 1.5
PLAN_MAX_LEVERAGE_ALT = 1.0
USER_MAX_ACCOUNT_LEVERAGE = 3.0

_EPS = 1e-12


class RiskLimitsError(Exception):
    """Missing, incomplete or invalid risk limits configuration."""


class StaleObservationError(ValueError):
    """Equity observation older than the last one registered (out-of-order
    event, replayed message, clock skew). It is rejected so it can never
    roll the daily bookkeeping back and clear an active lock."""


class KillSwitchLevel(IntEnum):
    NORMAL = 0
    BLOCK_ENTRIES = 1
    FLATTEN = 2
    HALT = 3


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KillSwitchLimits:
    daily_loss_block_entries: float
    daily_loss_flatten: float
    drawdown_half_risk: float
    drawdown_halt: float
    reduced_risk_multiplier: float


@dataclass(frozen=True)
class ExposureLimits:
    max_gross_long: float
    max_gross_short: float
    max_weight_major: float
    max_weight_alt: float
    max_alts_total: float
    max_beta_btc: float
    max_risk_per_trade_major: float
    max_risk_per_trade_alt: float


@dataclass(frozen=True)
class LeverageLimits:
    margin_type: str
    position_mode: str
    max_leverage_major: float
    max_leverage_alt: float
    account_max_leverage: float
    majors: tuple[str, ...]


@dataclass(frozen=True)
class RiskLimits:
    version: int
    user_confirmed: bool
    confirmed_on: str
    kill_switch: KillSwitchLimits
    exposure: ExposureLimits
    leverage: LeverageLimits
    max_capital_usdt: float
    source: str = ""

    def is_major(self, symbol: str) -> bool:
        return normalize_symbol(symbol) in self.leverage.majors

    def max_leverage(self, symbol: str) -> float:
        lev = self.leverage
        return lev.max_leverage_major if self.is_major(symbol) else lev.max_leverage_alt

    def max_weight(self, symbol: str) -> float:
        exp = self.exposure
        return exp.max_weight_major if self.is_major(symbol) else exp.max_weight_alt

    def max_risk_per_trade(self, symbol: str) -> float:
        exp = self.exposure
        return exp.max_risk_per_trade_major if self.is_major(symbol) else exp.max_risk_per_trade_alt


def normalize_symbol(symbol: str) -> str:
    """'BTC/USDT' -> 'BTCUSDT'."""
    return symbol.replace("/", "").replace("-", "").upper()


def _section(raw: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name not in raw:
        raise RiskLimitsError(f"missing section '{name}'")
    sec = raw[name]
    if not isinstance(sec, Mapping):
        raise RiskLimitsError(f"section '{name}' must be a mapping")
    return sec


def _num(sec: Mapping[str, Any], key: str, where: str) -> float:
    if key not in sec:
        raise RiskLimitsError(f"missing key '{where}.{key}'")
    val = sec[key]
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise RiskLimitsError(f"'{where}.{key}' must be a number, got {val!r}")
    val = float(val)
    if not math.isfinite(val):
        raise RiskLimitsError(f"'{where}.{key}' must be finite")
    return val


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise RiskLimitsError(msg)


def parse_risk_limits(raw: Any, source: str = "") -> RiskLimits:
    """Validate a parsed YAML mapping and build ``RiskLimits``. No defaults."""
    if not isinstance(raw, Mapping):
        raise RiskLimitsError("risk limits file must contain a mapping")
    for key in ("version", "user_confirmed", "confirmed_on"):
        if key not in raw:
            raise RiskLimitsError(f"missing key '{key}'")
    _check(raw["version"] == 1, f"unsupported version {raw['version']!r}")
    _check(isinstance(raw["user_confirmed"], bool), "'user_confirmed' must be true/false")

    ks_raw = _section(raw, "kill_switch")
    ks = KillSwitchLimits(
        daily_loss_block_entries=_num(ks_raw, "daily_loss_block_entries", "kill_switch"),
        daily_loss_flatten=_num(ks_raw, "daily_loss_flatten", "kill_switch"),
        drawdown_half_risk=_num(ks_raw, "drawdown_half_risk", "kill_switch"),
        drawdown_halt=_num(ks_raw, "drawdown_halt", "kill_switch"),
        reduced_risk_multiplier=_num(ks_raw, "reduced_risk_multiplier", "kill_switch"),
    )
    _check(-1.0 < ks.daily_loss_flatten < ks.daily_loss_block_entries < 0.0,
           "kill_switch requires -1 < daily_loss_flatten < daily_loss_block_entries < 0")
    _check(0.0 < ks.drawdown_half_risk < ks.drawdown_halt < 1.0,
           "kill_switch requires 0 < drawdown_half_risk < drawdown_halt < 1")
    _check(0.0 < ks.reduced_risk_multiplier < 1.0,
           "kill_switch.reduced_risk_multiplier must be in (0, 1)")

    ex_raw = _section(raw, "exposure")
    ex = ExposureLimits(**{
        k: _num(ex_raw, k, "exposure") for k in ExposureLimits.__dataclass_fields__
    })
    caps = {
        "max_gross_long": PLAN_MAX_GROSS_LONG,
        "max_gross_short": PLAN_MAX_GROSS_SHORT,
        "max_weight_major": PLAN_MAX_WEIGHT_MAJOR,
        "max_weight_alt": PLAN_MAX_WEIGHT_ALT,
        "max_alts_total": PLAN_MAX_ALTS_TOTAL,
        "max_beta_btc": PLAN_MAX_BETA_BTC,
        "max_risk_per_trade_major": PLAN_MAX_RISK_PER_TRADE,
        "max_risk_per_trade_alt": PLAN_MAX_RISK_PER_TRADE,
    }
    for key, cap in caps.items():
        val = getattr(ex, key)
        # max_gross_short may be 0 (no shorts); the rest must be positive.
        lo_ok = val >= 0.0 if key == "max_gross_short" else val > 0.0
        _check(lo_ok and val <= cap + _EPS,
               f"exposure.{key}={val} outside (0, {cap}] (PLAN §7 ceiling)")

    lv_raw = _section(raw, "leverage")
    for key in ("margin_type", "position_mode", "majors"):
        if key not in lv_raw:
            raise RiskLimitsError(f"missing key 'leverage.{key}'")
    majors = lv_raw["majors"]
    _check(isinstance(majors, list) and all(isinstance(s, str) for s in majors),
           "leverage.majors must be a list of symbols")
    lv = LeverageLimits(
        margin_type=str(lv_raw["margin_type"]).upper(),
        position_mode=str(lv_raw["position_mode"]).upper(),
        max_leverage_major=_num(lv_raw, "max_leverage_major", "leverage"),
        max_leverage_alt=_num(lv_raw, "max_leverage_alt", "leverage"),
        account_max_leverage=_num(lv_raw, "account_max_leverage", "leverage"),
        majors=tuple(normalize_symbol(s) for s in majors),
    )
    _check(lv.margin_type == "ISOLATED", "leverage.margin_type must be ISOLATED")
    _check(lv.position_mode == "ONE_WAY", "leverage.position_mode must be ONE_WAY")
    _check(0.0 < lv.account_max_leverage <= USER_MAX_ACCOUNT_LEVERAGE + _EPS,
           f"leverage.account_max_leverage must be in (0, {USER_MAX_ACCOUNT_LEVERAGE}]")
    _check(0.0 < lv.max_leverage_major <= min(PLAN_MAX_LEVERAGE_MAJOR, lv.account_max_leverage) + _EPS,
           f"leverage.max_leverage_major must be in (0, {PLAN_MAX_LEVERAGE_MAJOR}]")
    _check(0.0 < lv.max_leverage_alt <= min(PLAN_MAX_LEVERAGE_ALT, lv.account_max_leverage) + _EPS,
           f"leverage.max_leverage_alt must be in (0, {PLAN_MAX_LEVERAGE_ALT}]")

    cap_raw = _section(raw, "capital")
    max_capital = _num(cap_raw, "max_capital_usdt", "capital")
    _check(max_capital > 0.0, "capital.max_capital_usdt must be > 0")

    return RiskLimits(
        version=1,
        user_confirmed=raw["user_confirmed"],
        confirmed_on=str(raw["confirmed_on"]),
        kill_switch=ks,
        exposure=ex,
        leverage=lv,
        max_capital_usdt=max_capital,
        source=source,
    )


def load_risk_limits(path: Path | str = DEFAULT_RISK_LIMITS_PATH) -> RiskLimits:
    """Read and validate the user's risk limits. Raises ``RiskLimitsError``."""
    path = Path(path)
    if not path.is_file():
        raise RiskLimitsError(f"risk limits file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RiskLimitsError(f"invalid YAML in {path}: {exc}") from exc
    return parse_risk_limits(raw, source=str(path))


def resolve_trading_mode(mode: str | None = None) -> str:
    """Return the trading mode (``TRADING_MODE`` env var, ``dry_run`` by default)."""
    mode = (mode if mode is not None else os.environ.get("TRADING_MODE", "dry_run")).strip().lower()
    if mode not in TRADING_MODES:
        raise RiskLimitsError(f"unknown TRADING_MODE {mode!r}; expected one of {TRADING_MODES}")
    return mode


def assert_can_start(mode: str | None = None,
                     path: Path | str = DEFAULT_RISK_LIMITS_PATH) -> RiskLimits | None:
    """Startup guard.

    In ``live`` mode a valid file with ``user_confirmed: true`` is mandatory;
    any problem raises ``RiskLimitsError`` and the bot must not start.
    In the other modes the limits are loaded when valid; otherwise a warning is
    logged and ``None`` is returned.
    """
    mode = resolve_trading_mode(mode)
    if mode == "live":
        limits = load_risk_limits(path)
        if not limits.user_confirmed:
            raise RiskLimitsError("live mode requires user_confirmed: true in the risk limits file")
        return limits
    try:
        return load_risk_limits(path)
    except RiskLimitsError as exc:
        logger.warning("Risk limits unavailable in %s mode: %s", mode, exc)
        return None


# ---------------------------------------------------------------------------
# Runtime kill-switch
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PositionView:
    """Minimal view of an open position. ``qty`` is signed (negative = short)."""
    symbol: str
    qty: float
    leverage: float = 1.0
    market: str = "spot"

    @property
    def is_short(self) -> bool:
        return self.qty < 0

    @property
    def is_leveraged(self) -> bool:
        return self.leverage > 1.0 + _EPS


@dataclass(frozen=True)
class KillSwitchDecision:
    level: KillSwitchLevel
    allow_entries: bool
    allow_any_new_orders: bool
    close_leveraged_and_shorts: bool
    risk_multiplier: float
    daily_return: float
    drawdown: float
    reasons: tuple[str, ...] = ()


@dataclass
class KillSwitchState:
    day: str | None = None          # ISO date (UTC) of the current trading day
    last_ts: str | None = None      # ISO timestamp (UTC) of the last accepted update
    day_start_equity: float | None = None
    peak_equity: float | None = None
    daily_level: int = int(KillSwitchLevel.NORMAL)
    halted: bool = False
    halt_reason: str = ""
    last_equity: float | None = None


def _valid_equity(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _utc_day(now: datetime) -> date:
    if now.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware (UTC)")
    return now.astimezone(timezone.utc).date()


class KillSwitch:
    """Stateful kill-switch. Feed it the account equity with ``update``.

    Daily locks are sticky until the next UTC day even if equity recovers;
    the HALT level is sticky until ``reset_halt``. When ``state_path`` is given
    the state is persisted as JSON so a restart cannot clear a lock.
    """

    def __init__(self, limits: RiskLimits, state_path: Path | str | None = None,
                 alert: Callable[[str], None] | None = None):
        self.limits = limits
        self.state_path = Path(state_path) if state_path is not None else None
        self.alert = alert
        self.state = self._load_state()

    # -- persistence -------------------------------------------------------
    def _load_state(self) -> KillSwitchState:
        if self.state_path is None or not self.state_path.exists():
            return KillSwitchState()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return KillSwitchState(**data)
        except (ValueError, TypeError) as exc:
            # A corrupt state file must not silently unlock trading.
            raise RiskLimitsError(f"corrupt kill-switch state {self.state_path}: {exc}") from exc

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def _notify(self, msg: str) -> None:
        logger.warning("KILL-SWITCH: %s", msg)
        if self.alert is not None:
            try:
                self.alert(msg)
            except Exception:  # alerting must never break risk control
                logger.exception("kill-switch alert callback failed")

    # -- core ----------------------------------------------------------------
    def update(self, equity: float, now: datetime | None = None,
               day_start_equity: float | None = None) -> KillSwitchDecision:
        """Register the current equity (USDT) and return the active decision.

        Daily P&L is measured against the equity at 00:00 UTC. When an update
        opens a new UTC day, the reference is ``day_start_equity`` if the caller
        provides an explicit midnight snapshot; otherwise the last persisted
        equity (the closest known value to midnight) is used, so losses made
        between the last update of the previous day and this one (restart,
        downtime, sparse loop) still count against the new day's limits.
        ``day_start_equity`` is ignored when the update does not open a new day.

        Observations older than the last accepted one raise
        ``StaleObservationError`` and leave the state untouched.
        """
        if not _valid_equity(equity):
            raise ValueError(f"invalid equity {equity!r}")
        if day_start_equity is not None and not _valid_equity(day_start_equity):
            raise ValueError(f"invalid day_start_equity {day_start_equity!r}")
        now = now or datetime.now(timezone.utc)
        today = _utc_day(now)
        now_utc = now.astimezone(timezone.utc)
        st = self.state
        ks = self.limits.kill_switch

        if st.last_ts is not None and now_utc < datetime.fromisoformat(st.last_ts):
            raise StaleObservationError(
                f"observation at {now_utc.isoformat()} is older than the last one ({st.last_ts})")
        stored_day = date.fromisoformat(st.day) if st.day is not None else None
        if stored_day is not None and today < stored_day:
            raise StaleObservationError(
                f"observation day {today.isoformat()} is before the current day {st.day}")

        prev_level = self.level
        day = today.isoformat()
        if stored_day is None or today > stored_day:
            # New UTC day: reference is the equity at (or closest before) 00:00 UTC.
            if day_start_equity is not None:
                reference = float(day_start_equity)
            elif st.last_equity is not None:
                reference = float(st.last_equity)
            else:
                reference = float(equity)   # very first observation ever
            st.day = day
            st.day_start_equity = reference
            st.daily_level = int(KillSwitchLevel.NORMAL)
        st.last_ts = now_utc.isoformat()
        st.peak_equity = max(st.peak_equity or 0.0, float(equity))
        st.last_equity = float(equity)

        daily_ret = self.daily_return
        dd = self.drawdown

        if daily_ret <= ks.daily_loss_flatten + _EPS:
            st.daily_level = max(st.daily_level, int(KillSwitchLevel.FLATTEN))
        elif daily_ret <= ks.daily_loss_block_entries + _EPS:
            st.daily_level = max(st.daily_level, int(KillSwitchLevel.BLOCK_ENTRIES))

        if dd >= ks.drawdown_halt - _EPS and not st.halted:
            st.halted = True
            st.halt_reason = f"drawdown {dd:.2%} >= {ks.drawdown_halt:.2%} on {day}"

        new_level = self.level
        if new_level > prev_level:
            self._notify(f"level {prev_level.name} -> {new_level.name} "
                         f"(daily {daily_ret:.2%}, drawdown {dd:.2%})")
        self._save_state()
        return self.decision()

    @property
    def daily_return(self) -> float:
        st = self.state
        if not st.day_start_equity or st.last_equity is None:
            return 0.0
        return st.last_equity / st.day_start_equity - 1.0

    @property
    def drawdown(self) -> float:
        st = self.state
        if not st.peak_equity or st.last_equity is None:
            return 0.0
        return 1.0 - st.last_equity / st.peak_equity

    @property
    def level(self) -> KillSwitchLevel:
        if self.state.halted:
            return KillSwitchLevel.HALT
        return KillSwitchLevel(self.state.daily_level)

    @property
    def risk_multiplier(self) -> float:
        lvl = self.level
        if lvl >= KillSwitchLevel.FLATTEN:
            return 0.0
        if self.drawdown >= self.limits.kill_switch.drawdown_half_risk - _EPS:
            return self.limits.kill_switch.reduced_risk_multiplier
        return 1.0

    def decision(self) -> KillSwitchDecision:
        lvl = self.level
        ks = self.limits.kill_switch
        reasons: list[str] = []
        if self.state.halted:
            reasons.append(f"HALT: {self.state.halt_reason}; manual review required")
        if self.state.daily_level >= KillSwitchLevel.FLATTEN:
            reasons.append(f"daily loss <= {ks.daily_loss_flatten:.2%}")
        elif self.state.daily_level >= KillSwitchLevel.BLOCK_ENTRIES:
            reasons.append(f"daily loss <= {ks.daily_loss_block_entries:.2%}")
        mult = self.risk_multiplier
        if 0.0 < mult < 1.0:
            reasons.append(f"drawdown >= {ks.drawdown_half_risk:.2%}: risk x{mult}")
        return KillSwitchDecision(
            level=lvl,
            allow_entries=lvl == KillSwitchLevel.NORMAL,
            allow_any_new_orders=lvl < KillSwitchLevel.FLATTEN,
            close_leveraged_and_shorts=lvl >= KillSwitchLevel.FLATTEN,
            risk_multiplier=mult,
            daily_return=self.daily_return,
            drawdown=self.drawdown,
            reasons=tuple(reasons),
        )

    def allows_order(self, reduce_only: bool) -> bool:
        """Entries need NORMAL; reduce-only orders (exits, stops) are always allowed."""
        return bool(reduce_only) or self.level == KillSwitchLevel.NORMAL

    def filter_orders(self, intents: Iterable[Any]) -> tuple[list[Any], list[Any]]:
        """Split order intents (objects with a ``reduce_only`` attribute) into
        (allowed, blocked) according to the current level."""
        allowed, blocked = [], []
        for intent in intents:
            (allowed if self.allows_order(getattr(intent, "reduce_only", False)) else blocked).append(intent)
        if blocked:
            logger.warning("KILL-SWITCH %s blocked %d order(s)", self.level.name, len(blocked))
        return allowed, blocked

    def positions_to_close(self, positions: Iterable[PositionView]) -> list[PositionView]:
        """Positions that must be closed now: L > 1 and shorts when level >= FLATTEN."""
        if self.level < KillSwitchLevel.FLATTEN:
            return []
        return [p for p in positions if p.qty != 0 and (p.is_leveraged or p.is_short)]

    def scale_weights(self, weights: Mapping[str, float]) -> dict[str, float]:
        """Apply the risk multiplier to target weights (never increases exposure)."""
        mult = self.risk_multiplier
        return {s: float(w) * mult for s, w in weights.items()}

    def reset_halt(self, operator: str, reason: str) -> None:
        """Manual human release of HALT. The high-water mark is reset to the
        last equity so the drawdown trigger does not fire again immediately."""
        if not operator or not reason:
            raise ValueError("reset_halt requires an operator and a reason")
        if not self.state.halted:
            return
        self._notify(f"HALT released by {operator}: {reason}")
        self.state.halted = False
        self.state.halt_reason = ""
        self.state.peak_equity = self.state.last_equity
        self._save_state()


# ---------------------------------------------------------------------------
# Exposure / leverage checks (§7.3, §7.4)
# ---------------------------------------------------------------------------

def check_leverage(limits: RiskLimits, symbol: str, leverage: float) -> None:
    """Raise ``RiskLimitsError`` if ``leverage`` exceeds the symbol's cap."""
    cap = limits.max_leverage(symbol)
    if not (leverage > 0 and leverage <= cap + _EPS):
        raise RiskLimitsError(f"{normalize_symbol(symbol)}: leverage {leverage} exceeds cap {cap}")


def check_target_weights(limits: RiskLimits, weights: Mapping[str, float],
                         betas: Mapping[str, float] | None = None) -> list[str]:
    """Return the list of §7.3 exposure violations (empty when compliant).

    ``weights`` are signed fractions of NAV; ``betas`` (to BTC) default to 1.
    """
    ex = limits.exposure
    out: list[str] = []
    gross_long = sum(w for w in weights.values() if w > 0)
    gross_short = -sum(w for w in weights.values() if w < 0)
    alts = sum(abs(w) for s, w in weights.items() if not limits.is_major(s))
    for s, w in weights.items():
        cap = limits.max_weight(s)
        if abs(w) > cap + _EPS:
            out.append(f"{normalize_symbol(s)}: |w|={abs(w):.4f} > {cap}")
    if gross_long > ex.max_gross_long + _EPS:
        out.append(f"gross long {gross_long:.4f} > {ex.max_gross_long}")
    if gross_short > ex.max_gross_short + _EPS:
        out.append(f"gross short {gross_short:.4f} > {ex.max_gross_short}")
    if alts > ex.max_alts_total + _EPS:
        out.append(f"altcoins total {alts:.4f} > {ex.max_alts_total}")
    betas = betas or {}
    beta = sum(w * betas.get(s, 1.0) for s, w in weights.items())
    if beta > ex.max_beta_btc + _EPS:
        out.append(f"aggregate beta to BTC {beta:.4f} > {ex.max_beta_btc}")
    return out
