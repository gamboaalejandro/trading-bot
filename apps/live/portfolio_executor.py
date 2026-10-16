"""
Daily live portfolio executor (PLAN.md §4.3, §2.0, §3.4, §7; task L04).

Runs once a day at 00:05 UTC and shares the research code without
duplicating logic: the exposure signal comes from
``apps.research.strategies`` (TREND T1-T5, SHORT S1/S2), portfolio
construction from ``apps.research.portfolio.sizing`` (layer D), the per-bar
inputs (ATR14, 30-day volume tier) from ``apps.research.engine.portfolio_bt``
and the catastrophe stop from ``apps.research.engine.fills.ratchet_stop``.

One run:

1. Download 1d klines by REST and drop every row with ``closeTime >= serverTime``
   (only closed bars). The decision bar ``d`` is the bar that opened at
   00:00 UTC of the previous day; a symbol whose bar ``d`` is missing is
   frozen (its target is its held weight) and an alert is raised.
2. Paper venues trigger their stops on the new bars; then the
   :class:`~apps.live.reconciliation.Reconciler` aligns the local state with
   the exchange (stopped-out symbols are locked until their signal resets).
3. NAV -> live kill-switch (``apps.live.kill_switch``, user thresholds of
   ``config/risk_limits.yml``). ``signal`` -> discretise -> ``target_weights``
   -> weight overlays -> liquidation check (perps) -> kill-switch -> no-trade
   band -> §7.3 exposure check (:func:`decide_targets`).
4. Deltas against the REAL positions, quantities rounded DOWN to LOT_SIZE /
   MARKET_LOT_SIZE and stop prices to PRICE_FILTER. Deltas below MIN_NOTIONAL /
   NOTIONAL (or minQty) are skipped and logged. Reductions are sent first.
5. Orders carry a deterministic ``newClientOrderId``
   ``{YYYYMMDD}-{engine}-{symbol}-{seq}``; before sending, the order is looked
   up by that id, so a re-run after a crash never duplicates it.
6. The catastrophe stop (``max(stop, C - 3 ATR14)``, long; mirrored for
   shorts) is placed or moved IMMEDIATELY after each fill (spot: STOP_LOSS +
   cancelReplace; futures: STOP_MARKET reduceOnly MARK_PRICE algo order). If it
   cannot be placed after the retries, the position is closed at market, an
   alert is raised and the symbol is blocked (per-symbol kill-switch, manual
   release). Untouched positions get their daily stop ratchet.
7. Every input and decision is appended to a JSONL journal.

Execution modes (``TRADING_MODE``, :func:`core.config.resolve_trading_mode`):
``dry_run`` (default: everything simulated by
:class:`~apps.live.reconciliation.PaperVenue` on real market data),
``spot_demo`` (spot on the demo exchange, futures simulated),
``futures_testnet`` (futures on the testnet, spot simulated) and ``live``
(requires ``LIVE_TRADING_CONFIRM=I_UNDERSTAND`` and a user-confirmed
``config/risk_limits.yml``).

Routing (PLAN §1.1.3): longs of coins with a spot pair go to spot; shorts
(SHORT engine, ``shorts_on_futures``) and coins without a spot pair go to
isolated one-way perps at 1x.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from apps.live.kill_switch import (
    DEFAULT_RISK_LIMITS_PATH,
    KillSwitch,
    KillSwitchDecision,
    KillSwitchLevel,
    RiskLimits,
    assert_can_start,
    check_target_weights,
)
from apps.live.reconciliation import (
    LiveState,
    LocalPosition,
    OrderResult,
    PaperVenue,
    Reconciler,
    ReconciliationError,
    StopOrder,
    StopPlacementError,
    SymbolFilters,
    Venue,
    closing_side,
)
from apps.research.engine.costs import CostModel
from apps.research.engine.fills import ratchet_stop
from apps.research.engine.liquidation import worst_wick
from apps.research.engine.portfolio_bt import daily_inputs, resolve_slip
from apps.research.portfolio.risk import (
    KillSwitchState,
    RiskConfig,
    apply_kill_switch,
    check_liquidation,
    load_risk_config,
)
from apps.research.portfolio.sizing import (
    SizingConfig,
    annualized_vol,
    apply_band,
    coin_vol_cap,
    discretize,
    stress_cov,
    target_weights,
)
from apps.research.strategies.base import Context, weight_multiplier_of
from apps.research.strategies.trend import (
    SHORT_CONFIGS,
    TREND_CONFIGS,
    make_short,
    make_trend,
    sizing_config,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ExecutorError",
    "ExecutorConfig",
    "SPOT_UNIVERSE",
    "RUN_HOUR_UTC",
    "RUN_MINUTE_UTC",
    "client_order_id",
    "decision_bar",
    "next_run_time",
    "make_engine",
    "TargetDecision",
    "decide_targets",
    "PlannedOrder",
    "RunReport",
    "PortfolioExecutor",
    "build_venues",
    "build_executor",
]

#: Spot universe of PLAN §5.1 (top ~10 liquid coins, user decision).
SPOT_UNIVERSE = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                 "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT")
RUN_HOUR_UTC = 0
RUN_MINUTE_UTC = 5
ONE_DAY = pd.Timedelta(days=1)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIR = REPO_ROOT / "data" / "live"

# Deterministic order id sequence numbers, one meaning each (idempotent re-runs).
SEQ_ORDER = 1          # rebalance order (or the closing leg of a flip)
SEQ_STOP = 2           # catastrophe stop placed / moved after the fill or the daily ratchet
SEQ_EMERGENCY = 3      # market close after a failed stop
SEQ_FLATTEN = 4        # kill-switch close (leveraged / short positions)
SEQ_RESTOP = 5         # stop restored after a failed spot sell
SEQ_OPEN_FLIP = 6      # opening leg of a sign flip

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,36}$")
_EPS = 1e-12


class ExecutorError(RuntimeError):
    """The daily run cannot proceed (bad data, bad configuration, unsafe mode)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def client_order_id(day: date | datetime | pd.Timestamp | str, engine: str, symbol: str, seq: int) -> str:
    """``{YYYYMMDD}-{engine}-{symbol}-{seq}``: deterministic and idempotent (PLAN §4.3.5)."""
    if isinstance(day, str):
        day_s = day.replace("-", "")[:8]
    else:
        day_s = f"{day:%Y%m%d}"
    cid = f"{day_s}-{engine}-{symbol}-{int(seq)}"
    if not _CLIENT_ID_RE.match(cid):
        raise ExecutorError(f"client order id {cid!r} is not valid (<= 36 chars of [A-Za-z0-9_-])")
    return cid


def decision_bar(now: datetime) -> pd.Timestamp:
    """Label (open time) of the last daily bar closed at ``now``: 00:00 UTC of the previous day."""
    if now.tzinfo is None:
        raise ExecutorError("timestamps must be timezone-aware (UTC)")
    today = pd.Timestamp(now.astimezone(timezone.utc)).floor("D")
    return today - ONE_DAY


def next_run_time(now: datetime, hour: int = RUN_HOUR_UTC, minute: int = RUN_MINUTE_UTC) -> datetime:
    """Next daily run (00:05 UTC by default) strictly after ``now``."""
    now = now.astimezone(timezone.utc)
    run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return run if run > now else run + timedelta(days=1)


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float, np.floating)) and not isinstance(x, bool) and math.isfinite(x)


def make_engine(engine: str):
    """(strategy, SizingConfig) of a preregistered configuration: T1-T5 or S1/S2 (PLAN §2.2-§2.3)."""
    if engine in TREND_CONFIGS:
        return make_trend(engine), sizing_config(engine)
    if engine in SHORT_CONFIGS:
        return make_short(engine), sizing_config(engine)
    raise ExecutorError(f"unknown engine {engine!r} (expected {sorted(TREND_CONFIGS) + sorted(SHORT_CONFIGS)})")


def research_kill_state(
    decision: Optional[KillSwitchDecision],
    limits: Optional[RiskLimits] = None,
    risk: Optional[RiskConfig] = None,
) -> Optional[KillSwitchState]:
    """
    Map the live kill-switch decision onto the research ``KillSwitchState``.

    The research ``risk_mult`` only depends on the drawdown (half risk), while
    the live ``risk_multiplier`` is 0 from FLATTEN up (no new exposure at all).
    Using 0 there would turn every reduction into a full exit, so at FLATTEN /
    HALT the drawdown multiplier is recomputed from the user thresholds
    (``limits``, else ``risk``, else the ``RiskConfig`` defaults that mirror
    ``config/risk_limits.yml``). ``apply_kill_switch`` then forbids increases
    (FLATTEN) or closes everything (HALT) by itself.
    """
    if decision is None:
        return None
    lvl = KillSwitchLevel(decision.level)
    level = {
        KillSwitchLevel.NORMAL: "normal",
        KillSwitchLevel.BLOCK_ENTRIES: "block_entries",
        KillSwitchLevel.FLATTEN: "flatten_leveraged",
        KillSwitchLevel.HALT: "halted",
    }[lvl]
    mult = float(decision.risk_multiplier)
    if lvl >= KillSwitchLevel.FLATTEN:
        if limits is not None:
            dd_half, half_mult = limits.kill_switch.drawdown_half_risk, limits.kill_switch.reduced_risk_multiplier
        else:
            rc = risk or RiskConfig()
            dd_half, half_mult = rc.dd_half_risk, rc.half_risk_mult
        mult = float(half_mult) if float(decision.drawdown) >= dd_half - 1e-12 else 1.0
    return KillSwitchState(level, mult, float(decision.daily_return), float(decision.drawdown))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutorConfig:
    """Static configuration of the daily executor."""

    engine: str = "T3"                              # primary preregistered configuration
    spot_symbols: tuple = SPOT_UNIVERSE
    futures_symbols: tuple = ()                     # perps WITHOUT a spot pair (traded on futures)
    shorts_on_futures: bool = False                 # route negative weights to perps (SHORT engine)
    kline_limit: int = 1000
    atr_mult: float = 3.0                           # catastrophe stop C -/+ 3 ATR14
    futures_leverage: int = 1                       # isolated leverage (<= 1x alts, PLAN §7.4)
    stop_retry_delays: tuple = (1.0, 3.0)
    spot_buy_buffer: float = 0.995                  # keep some quote balance for fees
    paper_equity_spot: float = 1_000.0
    paper_equity_futures: float = 0.0
    spot_fee: float = 0.0010
    futures_fee: float = 0.0005
    run_hour: int = RUN_HOUR_UTC
    run_minute: int = RUN_MINUTE_UTC
    state_path: Optional[Path] = DEFAULT_STATE_DIR / "executor_state.json"
    journal_path: Optional[Path] = DEFAULT_STATE_DIR / "executor_journal.jsonl"
    kill_switch_state_path: Optional[Path] = DEFAULT_STATE_DIR / "kill_switch_state.json"
    risk_limits_path: Path = DEFAULT_RISK_LIMITS_PATH

    def __post_init__(self) -> None:
        overlap = set(self.spot_symbols) & set(self.futures_symbols)
        if overlap:
            raise ExecutorError(f"symbols routed to both markets: {sorted(overlap)}")
        if self.engine in SHORT_CONFIGS and not self.shorts_on_futures:
            raise ExecutorError(f"engine {self.engine} has a short leg: set shorts_on_futures=True")
        if self.futures_leverage != 1:
            # Only 1x is wired: L > 1 needs the per-symbol <=1.5x effective cap and the
            # liquidation check against leverageBracket for every long too.
            raise ExecutorError("futures_leverage must be 1 (PLAN §1.4, §7.4)")

    @property
    def symbols(self) -> tuple:
        return tuple(self.spot_symbols) + tuple(self.futures_symbols)

    @property
    def needs_futures(self) -> bool:
        return bool(self.futures_symbols) or self.shorts_on_futures


# ---------------------------------------------------------------------------
# Target weights (same research code as the backtest)
# ---------------------------------------------------------------------------

@dataclass
class TargetDecision:
    day: pd.Timestamp
    E: pd.Series
    E_q: pd.Series
    sigma: pd.Series
    w_layer_d: pd.Series
    w_final: pd.Series
    w_held: pd.Series
    frozen: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)


def decide_targets(
    strategy: Any,
    panel: Mapping[str, pd.DataFrame],
    sizing: SizingConfig,
    w_held: pd.Series,
    kill: Optional[KillSwitchDecision],
    *,
    day: pd.Timestamp,
    ctx: Optional[Context] = None,
    locks: Optional[dict] = None,
    blocked: Optional[Mapping[str, str]] = None,
    cost: Optional[CostModel] = None,
    limits: Optional[RiskLimits] = None,
    risk: Optional[RiskConfig] = None,
    perp_symbols: Sequence[str] = (),
    leverage: Optional[Mapping[str, float]] = None,
    mmr: Optional[Mapping[str, float]] = None,
    atr_mult: float = 3.0,
) -> TargetDecision:
    """
    Target weights decided at the close of bar ``day`` (step 7 of
    ``apps.research.engine.portfolio_bt.run_portfolio_bt``, live version).

    ``w_held`` are the current weights (signed fraction of NAV). ``locks``
    (symbol -> side stopped out) is updated in place: a lock clears when the
    discretised signal leaves that side. ``perp_symbols`` are checked for the
    liquidation distance before a short (or a leveraged long) is opened or
    increased. Kill-switch:

    the live decision is mapped onto the research ``KillSwitchState`` and
    ``apply_kill_switch`` + ``apply_band`` run exactly as in the backtest at
    every level:

    - NORMAL: risk multiplier only (half risk in drawdown);
    - BLOCK_ENTRIES: only reductions toward the strategy target;
    - FLATTEN: additionally shorts and leveraged positions go to 0; 1x longs
      can still be reduced or exited toward the strategy target, never increased;
    - HALT (drawdown stop): every position goes to 0 (full stop, PLAN §7.6).

    A symbol without bar ``day`` is frozen at its held weight. A per-symbol
    block (failed stop) only allows reductions. If the final vector still
    breaks a §7.3 limit only reductions are kept.
    """
    cost = cost or CostModel()
    locks = locks if locks is not None else {}
    blocked = blocked or {}
    symbols = list(panel)
    if not symbols:
        raise ExecutorError("empty panel")
    dates = panel[symbols[0]].index
    for s in symbols[1:]:
        dates = dates.union(panel[s].index)
    if day not in dates:
        raise ExecutorError(f"decision bar {day} not in the panel")
    gi = int(dates.get_loc(day))
    inputs = {s: daily_inputs(panel[s]).reindex(dates) for s in symbols}
    closes = pd.Series({s: panel[s]["close"].reindex(dates).iloc[gi] for s in symbols}, dtype=float)
    rets = pd.DataFrame({s: inputs[s]["logret"] for s in symbols})
    held = w_held.reindex(symbols).astype(float).fillna(0.0)
    lev = pd.Series({s: float((leverage or {}).get(s, 1.0)) for s in symbols})
    notes: dict[str, str] = {}

    ctx = ctx or Context(market="spot")
    ctx.frames = dict(panel)
    E_all = strategy.signal(dict(panel), ctx)
    E = E_all.reindex(index=dates, columns=symbols).astype(float).iloc[gi]
    e = E.fillna(0.0).copy()
    frozen = [s for s in symbols if not _finite(closes[s])]
    for s in frozen:
        notes[s] = "frozen: no closed bar for the decision day"

    e_sign = np.sign(discretize(e, sizing.step))
    for s in symbols:
        lock = int(locks.get(s, 0))
        if lock != 0:
            if e_sign[s] != lock:
                locks.pop(s, None)
                notes.setdefault(s, "lock released (signal reset)")
            else:
                e[s] = 0.0
                notes.setdefault(s, "locked after a stop-out")
        if e[s] != 0 and resolve_slip(s, day, inputs[s].iloc[gi].to_dict(), cost, None) is None:
            e[s] = 0.0
            notes.setdefault(s, "untradable (30d volume tier < C or not enough history)")

    e_q = discretize(e, sizing.step)
    sigma = annualized_vol(rets.iloc[: gi + 1], None, window=sizing.vol_window)
    no_vol = (e_q != 0) & ~np.isfinite(sigma)
    for s in e_q.index[no_vol.to_numpy()]:
        notes.setdefault(s, "no sigma_90")
    e_q[no_vol] = 0.0
    cov = stress_cov(rets.iloc[: gi + 1], day, lam=sizing.ewma_lambda, rho_floor=sizing.rho_floor,
                     vol_window=sizing.vol_window)
    w_new = target_weights(e_q, sigma, cov, sizing)
    w_layer_d = w_new.copy()

    # Risk-reducing weight overlays (REGIME / FVETO): never increase exposure.
    overlay_cap = None
    wm = weight_multiplier_of(strategy, dict(panel), ctx)
    if wm is not None:
        m = wm.reindex(index=dates, columns=symbols).astype(float).fillna(1.0).iloc[gi].clip(0.0, 1.0)
        if (m < 1.0).any():
            w_new = w_new * m
            overlay_cap = w_new.abs().where(m < 1.0, np.inf)

    # Liquidation distance before opening / increasing a perp position.
    for s in perp_symbols:
        if s not in symbols:
            continue
        wn, wh = w_new[s], held[s]
        if wn == 0 or (np.sign(wn) == np.sign(wh) and abs(wn) <= abs(wh)):
            continue
        side = 1 if wn > 0 else -1
        if side == 1 and lev[s] <= 1.0:
            continue   # isolated long at <= 1x cannot be liquidated
        c, a = closes[s], inputs[s]["atr"].iloc[gi]
        ww = worst_wick(panel[s], side).reindex(dates).iloc[gi]
        ok = _finite(c) and _finite(a) and a > 0 and check_liquidation(
            s, c, c - side * atr_mult * a, lev[s], side, ww, risk,
            mmr=float((mmr or {}).get(s, 0.01)))
        if not ok:
            notes[s] = "liquidation check failed"
            w_new[s] = wh if np.sign(wh) == side else 0.0

    # Same kill-switch + band sequence as the backtest (portfolio_bt step 7) at every level.
    state = research_kill_state(kill, limits, risk)
    w_ks = apply_kill_switch(w_new, held, state, lev).reindex(symbols) if state is not None else w_new
    max_abs = coin_vol_cap(e_q, sigma, sizing)
    if state is not None and (state.risk_mult < 1 or state.entries_blocked):
        max_abs = np.minimum(max_abs, w_ks.abs())
    if overlay_cap is not None:
        max_abs = np.minimum(max_abs, overlay_cap.reindex(symbols))
    w_final = apply_band(w_ks, held, sizing.band, cfg=sizing, max_abs=max_abs).reindex(symbols)

    for s in frozen:
        w_final[s] = held[s]
    for s in blocked:
        if s in symbols:
            h = held[s]
            w_final[s] = 0.0 if h == 0 or np.sign(w_final[s]) != np.sign(h) else \
                np.sign(h) * min(abs(w_final[s]), abs(h))
            notes[s] = f"blocked: {blocked[s]}"

    if limits is not None:
        violations = check_target_weights(limits, w_final.to_dict())
        if violations:
            notes["*"] = "exposure limits breached, only reductions kept: " + "; ".join(violations)
            w_final = apply_kill_switch(w_final, held, KillSwitchState("block_entries")).reindex(symbols)

    return TargetDecision(day=day, E=E, E_q=e_q, sigma=sigma, w_layer_d=w_layer_d,
                          w_final=(w_final + 0.0).rename("weight"), w_held=held, frozen=frozen, notes=notes)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

@dataclass
class PlannedOrder:
    market: str
    symbol: str
    side: str
    qty: float
    client_id: str
    reduce_only: bool
    ref_price: float
    reason: str
    status: str = "planned"          # planned | filled | existing | skipped | blocked | failed
    detail: str = ""
    executed_qty: float = 0.0
    avg_price: float = float("nan")


@dataclass
class RunReport:
    day: str
    mode: str
    status: str = "ok"               # ok | skipped | aborted
    nav: float = float("nan")
    kill_level: str = ""
    weights: dict = field(default_factory=dict)
    orders: list = field(default_factory=list)
    stops: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    def orders_with(self, status: str) -> list[PlannedOrder]:
        return [o for o in self.orders if o.status == status]


class PortfolioExecutor:
    """
    Daily target-weight executor. ``venues`` maps ``"spot"`` / ``"futures"`` to
    a :class:`~apps.live.reconciliation.Venue` (real or paper, see
    :func:`build_venues`).
    """

    def __init__(self, cfg: ExecutorConfig, venues: Mapping[str, Venue], *, mode: str,
                 limits: RiskLimits, kill_switch: Optional[KillSwitch] = None,
                 state: Optional[LiveState] = None, risk: Optional[RiskConfig] = None,
                 alert: Optional[Callable[[str], None]] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 strategy: Any = None, sizing: Optional[SizingConfig] = None,
                 cost: Optional[CostModel] = None):
        self.cfg = cfg
        self.venues = dict(venues)
        self.mode = mode
        self.limits = limits
        self.alert_fn = alert
        self.sleep = sleep
        self.state = state if state is not None else LiveState.load(cfg.state_path)
        self.kill_switch = kill_switch if kill_switch is not None else KillSwitch(
            limits, state_path=cfg.kill_switch_state_path, alert=alert)
        self.risk = risk if risk is not None else load_risk_config(cfg.risk_limits_path)
        if strategy is None:
            strategy, default_sizing = make_engine(cfg.engine)
            sizing = sizing or default_sizing
        self.strategy = strategy
        self.sizing = sizing or sizing_config(cfg.engine)
        self.cost = cost or CostModel()
        if "spot" not in self.venues and cfg.spot_symbols:
            raise ExecutorError("spot symbols configured without a spot venue")
        if cfg.needs_futures and "futures" not in self.venues:
            raise ExecutorError("futures routing configured without a futures venue")
        if mode == "dry_run" and any(getattr(v, "mutating", True) for v in self.venues.values()):
            raise ExecutorError("dry_run requires paper venues only")
        self._report: Optional[RunReport] = None
        self._panel: dict[str, pd.DataFrame] = {}
        self._day: Optional[pd.Timestamp] = None

    # -- logging ---------------------------------------------------------
    def _alert(self, msg: str) -> None:
        logger.warning("EXECUTOR ALERT: %s", msg)
        if self._report is not None:
            self._report.alerts.append(msg)
        self._journal("alert", message=msg)
        if self.alert_fn is not None:
            try:
                self.alert_fn(msg)
            except Exception:  # alerting must never break execution
                logger.exception("alert callback failed")

    def _journal(self, event: str, **data: Any) -> None:
        path = self.cfg.journal_path
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "mode": self.mode,
               "engine": self.cfg.engine, "day": str(self._day.date()) if self._day is not None else None,
               **data}
        logger.info("journal %s %s", event, {k: v for k, v in data.items() if k not in ("panel",)})
        if path is None:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=_json_default, sort_keys=True) + "\n")

    # -- routing ---------------------------------------------------------
    def _venue_of(self, symbol: str, weight_sign: int) -> Optional[str]:
        if symbol in self.cfg.futures_symbols:
            return "futures"
        if weight_sign < 0:
            return "futures" if self.cfg.shorts_on_futures else None
        return "spot"

    def _data_venue(self, symbol: str) -> Venue:
        return self.venues["futures" if symbol in self.cfg.futures_symbols else "spot"]

    # -- run -------------------------------------------------------------
    def run(self, now: Optional[datetime] = None, force: bool = False) -> RunReport:
        now = now or datetime.now(timezone.utc)
        day = decision_bar(now)
        run_day = (day + ONE_DAY).date().isoformat()
        self._day = day
        report = RunReport(day=run_day, mode=self.mode)
        self._report = report
        if self.state.last_run_day == run_day and not force:
            report.status = "skipped"
            report.notes["*"] = f"already ran for {run_day}"
            self._journal("run_skipped", reason=report.notes["*"])
            return report
        self._journal("run_start", now=now.isoformat(), decision_bar=str(day))
        try:
            self._run(now, day, report)
        except Exception as exc:
            report.status = "aborted"
            self._alert(f"daily run aborted: {type(exc).__name__}: {exc}")
            self.state.save()
            raise
        self.state.last_run_day = run_day
        self.state.save()
        self._journal("run_end", status=report.status, nav=report.nav, kill_level=report.kill_level,
                      orders=[asdict(o) for o in report.orders], stops=report.stops, alerts=report.alerts)
        return report

    def _load_panel(self, day: pd.Timestamp) -> dict[str, pd.DataFrame]:
        panel = {}
        for s in self.cfg.symbols:
            df = self._data_venue(s).closed_klines(s, "1d", self.cfg.kline_limit)
            if df.empty:
                raise ExecutorError(f"{s}: no closed daily klines")
            df = df[df.index <= day]
            if day not in df.index:
                self._alert(f"{s}: closed bar {day.date()} missing (last {df.index[-1] if len(df) else None})")
            panel[s] = df[["open", "high", "low", "close", "volume", "quote_volume"]].copy()
            last = df.iloc[-1]
            self._journal("input_bar", symbol=s, bar=str(df.index[-1]),
                          ohlcv={k: float(last[k]) for k in ("open", "high", "low", "close", "volume")},
                          n_bars=len(df))
        return panel

    def _context(self) -> Context:
        ctx = Context(market="futures" if self.cfg.shorts_on_futures else "spot")
        if self.cfg.shorts_on_futures and getattr(self.strategy, "short_signal", None) is not None:
            # SHORT leg: funding veto needs the settlements of every shorted perp (no imputation).
            fut = self.venues["futures"]
            ctx.funding = {s: fut.funding_history(s) for s in self.cfg.symbols if s != "BNBUSDT"}
        return ctx

    def _closes(self, day: pd.Timestamp) -> dict[str, float]:
        out = {}
        for s, df in self._panel.items():
            c = df["close"].get(day, float("nan"))
            if not _finite(c):
                c = df["close"].dropna().iloc[-1] if df["close"].notna().any() else float("nan")
            out[s] = float(c)
        return out

    def _atr(self, symbol: str, day: pd.Timestamp) -> float:
        inp = daily_inputs(self._panel[symbol])
        return float(inp["atr"].get(day, float("nan")))

    def _stop_price(self, market: str, symbol: str, side: int, prev: Optional[float] = None) -> Optional[float]:
        """Catastrophe stop at the close of the decision bar (ratchet when ``prev`` is given)."""
        day = self._day
        c = self._panel[symbol]["close"].get(day, float("nan")) if symbol in self._panel else float("nan")
        a = self._atr(symbol, day) if symbol in self._panel else float("nan")
        if not (_finite(c) and _finite(a)):
            return prev
        px = ratchet_stop(prev, float(c), float(a), side, self.cfg.atr_mult)
        return px if px > 0 else prev

    def _run(self, now: datetime, day: pd.Timestamp, report: RunReport) -> None:
        cfg = self.cfg
        self._panel = self._load_panel(day)
        closes = self._closes(day)

        # Paper venues: marks and stops triggered by the new closed bars.
        for market, venue in self.venues.items():
            if isinstance(venue, PaperVenue):
                for s in cfg.symbols:
                    df = self._panel[s]
                    last = self.state.last_bar.get(f"{market}:{s}")
                    new = df[df.index > pd.Timestamp(last)] if last else df.iloc[0:0]
                    for t, bar in new.iterrows():
                        res = venue.process_bar(s, bar.to_dict())
                        if res is not None:
                            self._journal("paper_stop_filled", market=market, symbol=s, bar=str(t),
                                          result=asdict(res))
                    self.state.last_bar[f"{market}:{s}"] = str(df.index[-1])
                venue.set_marks(closes)

        # Reconcile before deciding (stopped-out symbols get locked).
        marks = {m: closes for m in self.venues}
        rec = Reconciler(self.venues, self.state, alert=self._alert,
                         stop_price_fn=lambda m, s, side: self._stop_price(m, s, side))
        rep = rec.run_once(now, marks=marks)
        self._journal("reconciliation", phase="pre", actions=[asdict(a) for a in rep.actions])

        # NAV, positions and kill-switch.
        positions = {m: v.positions(closes) for m, v in self.venues.items()}
        nav = float(sum(v.equity(closes) for v in self.venues.values()))
        report.nav = nav
        if not _finite(nav) or nav <= 0:
            raise ExecutorError(f"invalid NAV {nav}")
        decision = self.kill_switch.update(nav, now)
        report.kill_level = KillSwitchLevel(decision.level).name
        self._journal("kill_switch", nav=nav, decision=asdict(decision))

        held_qty = {s: sum(positions[m][s].qty for m in positions if s in positions[m]) for s in cfg.symbols}
        w_held = pd.Series({s: held_qty[s] * closes[s] / nav if held_qty[s] else 0.0 for s in cfg.symbols})
        perp = [s for s in cfg.symbols if s in cfg.futures_symbols or cfg.shorts_on_futures]
        mmr = {}
        if "futures" in self.venues:
            for s in perp:
                try:
                    mmr[s] = self.venues["futures"].maint_margin_rate(s)
                except Exception as exc:
                    self._alert(f"{s}: leverage bracket unavailable ({exc}); default MMR 1%")
        lev = {s: float(cfg.futures_leverage) if s in perp else 1.0 for s in cfg.symbols}
        td = decide_targets(
            self.strategy, self._panel, self.sizing, w_held, decision, day=day, ctx=self._context(),
            locks=self.state.locks, blocked=self.state.blocked, cost=self.cost, limits=self.limits,
            risk=self.risk, perp_symbols=perp, leverage=lev, mmr=mmr, atr_mult=cfg.atr_mult)
        report.weights = {s: float(w) for s, w in td.w_final.items()}
        report.notes.update(td.notes)
        for s in td.frozen:
            self._alert(f"{s}: frozen at its held weight (missing closed bar {day.date()})")
        self._journal("decision", E={k: _nan_none(v) for k, v in td.E.items()},
                      E_q=td.E_q.to_dict(), sigma={k: _nan_none(v) for k, v in td.sigma.items()},
                      w_layer_d=td.w_layer_d.to_dict(), w_held=td.w_held.to_dict(),
                      w_final=td.w_final.to_dict(), notes=td.notes, locks=dict(self.state.locks))

        # Per-venue target quantities.
        plan: list[tuple[str, str, float, float]] = []   # (market, symbol, held, target)
        for s in cfg.symbols:
            w = float(td.w_final[s])
            px = closes[s]
            if not _finite(px) or px <= 0:
                continue
            target_by_market = {m: 0.0 for m in self.venues}
            dest = self._venue_of(s, int(np.sign(w)))
            if w != 0 and dest is None:
                report.notes[s] = f"weight {w:.4f} has no venue (shorts disabled): kept flat"
            elif w != 0:
                target_by_market[dest] = w * nav / px
            for m in self.venues:
                h = positions[m][s].qty if s in positions[m] else 0.0
                if s in td.frozen and h != 0:
                    target_by_market[m] = h
                if m == "spot" and s not in cfg.spot_symbols and h == 0:
                    continue
                if h != 0 or target_by_market[m] != 0:
                    plan.append((m, s, h, target_by_market[m]))

        touched: set[tuple[str, str]] = set()
        # Reductions (and kill-switch closes) first, then increases.
        reductions = [p for p in plan if abs(p[3]) < abs(p[2]) or np.sign(p[3]) != np.sign(p[2])]
        increases = [p for p in plan if p not in reductions]
        for m, s, h, t in reductions:
            self._rebalance(m, s, h, t, closes[s], decision, report, touched)
        for m, s, h, t in increases:
            self._rebalance(m, s, h, t, closes[s], decision, report, touched)

        # Daily ratchet of the stops of positions not traded today.
        for m, venue in self.venues.items():
            for s, pos in venue.positions(closes).items():
                if (m, s) not in touched:
                    self._ratchet_stop(m, s, pos.qty, report)

        rep = rec.run_once(now, marks=marks)
        self._journal("reconciliation", phase="post", actions=[asdict(a) for a in rep.actions])

    # -- orders ----------------------------------------------------------
    def _stops_of(self, market: str, symbol: str) -> list[StopOrder]:
        return [st for st in self.venues[market].open_stops() if st.symbol == symbol]

    def _current_stop(self, market: str, symbol: str, side: str) -> Optional[StopOrder]:
        stops = [st for st in self._stops_of(market, symbol) if st.side == side]
        loc = self.state.get(market, symbol)
        if loc is not None and loc.stop_client_id:
            for st in stops:
                if st.client_id == loc.stop_client_id:
                    return st
        return stops[0] if stops else None

    def _rebalance(self, market: str, symbol: str, held: float, target: float, price: float,
                   decision: KillSwitchDecision, report: RunReport, touched: set) -> None:
        if held != 0 and target != 0 and np.sign(held) != np.sign(target):
            # Flip: close first, then open (two orders, two ids).
            self._trade(market, symbol, held, 0.0, price, decision, report, touched, SEQ_ORDER)
            left = self.venues[market].positions({symbol: price}).get(symbol)
            if left is None or left.qty == 0:
                self._trade(market, symbol, 0.0, target, price, decision, report, touched, SEQ_OPEN_FLIP)
            return
        self._trade(market, symbol, held, target, price, decision, report, touched, SEQ_ORDER)

    def _trade(self, market: str, symbol: str, held: float, target: float, price: float,
               decision: KillSwitchDecision, report: RunReport, touched: set, seq: int) -> None:
        venue = self.venues[market]
        filters = venue.filters(symbol)
        if target != 0 and abs(target) < abs(held) and np.sign(target) == np.sign(held) \
                and filters.check(filters.round_qty(abs(target)), price) is not None:
            target = 0.0     # the remainder could not be traded nor protected: exit fully
        delta = target - held
        full_exit = target == 0
        side = "BUY" if delta > 0 else "SELL"
        reduce_only = bool(abs(target) < abs(held) and (target == 0 or np.sign(target) == np.sign(held)))
        if full_exit:
            qty = filters.round_qty(abs(held))
        elif reduce_only:
            # Keep a step-rounded remainder (the stop is sized on it before a spot sell).
            qty = filters.round_qty(abs(held) - filters.round_qty(abs(target)))
        else:
            qty = filters.round_qty(abs(delta))
        cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, seq)
        order = PlannedOrder(market, symbol, side, qty, cid, reduce_only, price,
                             "close" if full_exit else ("reduce" if reduce_only else "increase"))
        report.orders.append(order)

        if decision.level >= KillSwitchLevel.FLATTEN and reduce_only and full_exit:
            order.reason = "kill_switch_close"
            order.client_id = cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_FLATTEN)
        reason = filters.check(qty, price)
        if reason is not None:
            order.status, order.detail = "skipped", reason
            self._journal("order_skipped", order=asdict(order),
                          min_notional=str(filters.min_notional), min_qty=str(filters.min_qty))
            return
        if not reduce_only and not self.kill_switch.allows_order(False):
            order.status, order.detail = "blocked", f"kill-switch {KillSwitchLevel(decision.level).name}"
            self._journal("order_blocked", order=asdict(order))
            return
        if not reduce_only and symbol in self.state.blocked:
            order.status, order.detail = "blocked", f"symbol blocked: {self.state.blocked[symbol]}"
            self._journal("order_blocked", order=asdict(order))
            return
        if not reduce_only and market == "spot":
            budget = venue.free_quote() * self.cfg.spot_buy_buffer
            if qty * price > budget:
                qty = filters.round_qty(budget / price)
                order.qty = qty
                order.detail = "scaled to the free quote balance"
                reason = filters.check(qty, price)
                if reason is not None:
                    order.status, order.detail = "skipped", f"{reason} after scaling to the free balance"
                    self._journal("order_skipped", order=asdict(order))
                    return
        if market == "futures" and not reduce_only:
            venue.prepare_symbol(symbol, self.cfg.futures_leverage)

        touched.add((market, symbol))
        pos_side = 1 if (held > 0 or (held == 0 and delta > 0)) else -1
        close_side = closing_side(pos_side)
        old_stop = self._current_stop(market, symbol, close_side) if held != 0 else None
        remaining = filters.round_qty(abs(target))

        # Spot: the stop locks the base balance, so it is shrunk (or cancelled) BEFORE a sell.
        if market == "spot" and side == "SELL" and old_stop is not None:
            try:
                if remaining > 0 and filters.check(remaining, price) is None:
                    px = self._stop_price(market, symbol, pos_side, old_stop.stop_price) or old_stop.stop_price
                    px = filters.round_price(px, "down")
                    st = venue.replace_stop(old_stop, remaining, px,
                                            client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_STOP))
                    self._record(market, symbol, held, st)
                else:
                    venue.cancel_stop(old_stop)
            except Exception as exc:
                order.status, order.detail = "failed", f"could not adjust the stop before selling: {exc}"
                self._alert(f"{symbol}: sell not sent, stop adjustment failed ({exc}); position still protected")
                return

        # Send (or adopt) the order: idempotent by client id.
        try:
            res = venue.find_order(symbol, cid)
            if res is not None:
                order.status = "existing"
            else:
                res = venue.market_order(symbol, side, qty, cid, reduce_only=reduce_only and market == "futures")
                order.status = "filled"
        except Exception as exc:
            res = None
            order.status, order.detail = "failed", str(exc)
        if res is not None:
            order.executed_qty, order.avg_price = res.executed_qty, res.avg_price
        self._journal("order", order=asdict(order))
        if res is None or res.executed_qty <= 0:
            self._alert(f"{market} {symbol}: order {cid} not filled ({order.detail or (res.status if res else '')})")
            if market == "spot" and side == "SELL" and old_stop is not None:
                self._restore_stop(market, symbol, report)
            return

        # Protect the resulting position IMMEDIATELY (before any other order).
        self._protect_after_fill(market, symbol, held, price, report)

    def _record(self, market: str, symbol: str, qty: float, st: Optional[StopOrder]) -> None:
        if qty == 0:
            self.state.drop(market, symbol)
            return
        self.state.put(LocalPosition(symbol, market, qty, st.stop_price if st else None,
                                     st.client_id if st else None, st.order_id if st else None))
        self.state.save()

    def _protect_after_fill(self, market: str, symbol: str, held_before: float, price: float,
                            report: RunReport) -> None:
        venue = self.venues[market]
        filters = venue.filters(symbol)
        pos = venue.positions({symbol: price}).get(symbol)
        qty = pos.qty if pos is not None else 0.0
        if qty == 0 or filters.is_dust(qty, price):
            for st in self._stops_of(market, symbol):
                try:
                    venue.cancel_stop(st)
                except Exception as exc:
                    self._alert(f"{market} {symbol}: could not cancel leftover stop {st.order_id}: {exc}")
            self._record(market, symbol, 0.0, None)
            return
        side = 1 if qty > 0 else -1
        cside = closing_side(qty)
        same_side = held_before != 0 and np.sign(held_before) == side
        old = self._current_stop(market, symbol, cside)
        prev = old.stop_price if (old is not None and same_side) else None
        if prev is None and same_side:
            loc = self.state.get(market, symbol)
            prev = loc.stop_price if loc is not None else None
        px = self._stop_price(market, symbol, side, prev)
        if px is None:
            self._emergency_close(market, symbol, qty, price, "no stop price (missing ATR)", report)
            return
        px = filters.round_price(px, "down" if side == 1 else "up")
        stop_qty = filters.round_qty(abs(qty))
        if old is not None and math.isclose(old.qty, stop_qty, rel_tol=1e-9) \
                and math.isclose(old.stop_price, px, rel_tol=1e-12):
            self._record(market, symbol, qty, old)
            report.stops.append({"market": market, "symbol": symbol, "action": "kept", "stop": old.stop_price})
            return
        cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_STOP)
        try:
            st = self._place_with_retries(venue, symbol, cside, stop_qty, px, cid, old)
        except StopPlacementError as exc:
            self._emergency_close(market, symbol, qty, price, str(exc), report)
            return
        self._record(market, symbol, qty, st)
        report.stops.append({"market": market, "symbol": symbol, "action": "placed" if old is None else "moved",
                             "stop": st.stop_price, "qty": st.qty, "client_id": st.client_id})
        self._journal("stop", market=market, symbol=symbol, stop=asdict(st))

    def _place_with_retries(self, venue: Venue, symbol: str, side: str, qty: float, price: float,
                            cid: str, old: Optional[StopOrder]) -> StopOrder:
        last: Optional[Exception] = None
        delays = (0.0,) + tuple(self.cfg.stop_retry_delays)
        for attempt, delay in enumerate(delays):
            if delay:
                self.sleep(delay)
            try:
                if attempt > 0:
                    found = venue.find_stop(symbol, cid)
                    if found is not None:
                        return found
                if old is not None:
                    still = [st for st in venue.open_stops() if st.order_id == old.order_id]
                    if still:
                        return venue.replace_stop(old, qty, price, cid)
                return venue.place_stop(symbol, side, qty, price, cid)
            except Exception as exc:
                last = exc
                logger.error("%s: stop attempt %d/%d failed: %s", symbol, attempt + 1, len(delays), exc)
        raise StopPlacementError(f"{symbol}: stop not placed after {len(delays)} attempts: {last}")

    def _emergency_close(self, market: str, symbol: str, qty: float, price: float, why: str,
                         report: RunReport) -> None:
        """PLAN §4.4.6: stop failed -> close at market, alert, block the symbol."""
        venue = self.venues[market]
        filters = venue.filters(symbol)
        self._alert(f"{market} {symbol}: position WITHOUT stop ({why}): closing at market")
        for st in self._stops_of(market, symbol):
            try:
                venue.cancel_stop(st)
            except Exception as exc:
                logger.warning("%s: could not cancel stop %s before the emergency close: %s",
                               symbol, st.order_id, exc)
        cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_EMERGENCY)
        close_qty = filters.round_qty(abs(qty))
        order = PlannedOrder(market, symbol, closing_side(qty), close_qty, cid, True, price, "emergency_close")
        report.orders.append(order)
        try:
            res = venue.find_order(symbol, cid) or venue.market_order(
                symbol, closing_side(qty), close_qty, cid, reduce_only=market == "futures")
            order.status, order.executed_qty, order.avg_price = "filled", res.executed_qty, res.avg_price
        except Exception as exc:
            order.status, order.detail = "failed", str(exc)
            self._alert(f"{market} {symbol}: EMERGENCY CLOSE FAILED ({exc}): manual action required")
        self._journal("order", order=asdict(order))
        self.state.blocked[symbol] = f"{self._day.date()}: stop failure ({why})"
        pos = venue.positions({symbol: price}).get(symbol)
        self._record(market, symbol, pos.qty if pos is not None else 0.0, None)

    def _restore_stop(self, market: str, symbol: str, report: RunReport) -> None:
        venue = self.venues[market]
        filters = venue.filters(symbol)
        price = self._closes(self._day).get(symbol, float("nan"))
        pos = venue.positions({symbol: price}).get(symbol)
        if pos is None or pos.qty == 0:
            return
        loc = self.state.get(market, symbol)
        px = (loc.stop_price if loc is not None else None) or self._stop_price(market, symbol, 1 if pos.qty > 0 else -1)
        cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_RESTOP)
        try:
            st = self._place_with_retries(venue, symbol, closing_side(pos.qty), filters.round_qty(abs(pos.qty)),
                                          filters.round_price(px, "down" if pos.qty > 0 else "up"), cid, None)
            self._record(market, symbol, pos.qty, st)
        except StopPlacementError as exc:
            self._emergency_close(market, symbol, pos.qty, price, str(exc), report)

    def _ratchet_stop(self, market: str, symbol: str, qty: float, report: RunReport) -> None:
        venue = self.venues[market]
        filters = venue.filters(symbol)
        price = self._closes(self._day).get(symbol, float("nan"))
        if qty == 0 or (_finite(price) and filters.is_dust(qty, price)):
            return
        side = 1 if qty > 0 else -1
        old = self._current_stop(market, symbol, closing_side(qty))
        if old is None:
            return   # the reconciler alerts / places missing stops
        px = self._stop_price(market, symbol, side, old.stop_price)
        if px is None:
            return
        px = filters.round_price(px, "down" if side == 1 else "up")
        if abs(px - old.stop_price) < float(filters.tick_size) * 0.5 or (px - old.stop_price) * side <= 0:
            self._record(market, symbol, qty, old)
            return
        cid = client_order_id(self._day + ONE_DAY, self.cfg.engine, symbol, SEQ_STOP)
        try:
            st = self._place_with_retries(venue, symbol, old.side, old.qty, px, cid, old)
        except StopPlacementError as exc:
            self._alert(f"{market} {symbol}: daily stop ratchet failed ({exc}); previous stop kept")
            return
        self._record(market, symbol, qty, st)
        report.stops.append({"market": market, "symbol": symbol, "action": "ratchet",
                             "stop": st.stop_price, "previous": old.stop_price})
        self._journal("stop", market=market, symbol=symbol, stop=asdict(st), previous=old.stop_price)

    # -- scheduling ------------------------------------------------------
    def run_forever(self, should_stop: Callable[[], bool] = lambda: False,
                    reconcile_every: float = 300.0) -> None:
        """Daily run at 00:05 UTC; reconciliation every ``reconcile_every`` seconds in between."""
        rec = Reconciler(self.venues, self.state, alert=self._alert)
        real = any(getattr(v, "mutating", False) for v in self.venues.values())
        while not should_stop():
            now = datetime.now(timezone.utc)
            run_at = now.replace(hour=self.cfg.run_hour, minute=self.cfg.run_minute, second=0, microsecond=0)
            if now >= run_at and self.state.last_run_day != now.date().isoformat():
                try:
                    self.run(now)
                except Exception:
                    logger.exception("daily run failed")
            elif real:
                try:
                    rec.run_once()
                except Exception:
                    logger.exception("reconciliation failed")
            due = next_run_time(datetime.now(timezone.utc), self.cfg.run_hour, self.cfg.run_minute)
            self.sleep(max(1.0, min(reconcile_every, (due - datetime.now(timezone.utc)).total_seconds())))


def _nan_none(x: Any) -> Any:
    return None if isinstance(x, float) and not math.isfinite(x) else x


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# Wiring from the environment
# ---------------------------------------------------------------------------

def build_venues(cfg: ExecutorConfig, mode: str, state: LiveState,
                 spot_client: Any = None, futures_client: Any = None) -> dict[str, Venue]:
    """
    Venues for ``mode``. Real venues only for the market the mode allows
    (``spot_demo`` -> spot, ``futures_testnet`` -> futures, ``live`` -> both);
    the rest are :class:`PaperVenue` reading public market data. Clients are
    built from environment variables (``core.secrets``) unless injected.
    """
    from apps.live.reconciliation import FuturesVenue, SpotVenue

    real_spot = mode in ("spot_demo", "live")
    real_fut = mode in ("futures_testnet", "live")
    venues: dict[str, Venue] = {}

    if spot_client is None:
        from core.binance_client import BinanceClient

        if real_spot:
            from core.secrets import get_credentials

            creds = get_credentials("spot_demo" if mode == "spot_demo" else "live")
            spot_client = BinanceClient(creds.api_key, creds.api_secret, demo_mode=mode != "live")
        else:
            spot_client = BinanceClient("", "", demo_mode=False)   # public market data only
    if real_spot and mode != "live" and not getattr(spot_client, "demo_mode", False):
        raise ExecutorError("spot_demo requires a demo-mode spot client")
    spot = SpotVenue(spot_client, cfg.spot_symbols)
    venues["spot"] = spot if real_spot else PaperVenue(
        "spot", spot, state.paper.setdefault("spot", {"cash": cfg.paper_equity_spot}), cfg.spot_fee,
        cfg.spot_symbols)

    if cfg.needs_futures:
        from core.binance_futures_client import PRODUCTION_BASE_URL, BinanceFuturesClient, is_production

        fut_symbols = tuple(cfg.futures_symbols) + (tuple(cfg.spot_symbols) if cfg.shorts_on_futures else ())
        if futures_client is None:
            if real_fut:
                futures_client = BinanceFuturesClient.from_env("futures_testnet" if mode != "live" else "live")
            else:
                futures_client = BinanceFuturesClient("", "", base_url=PRODUCTION_BASE_URL, read_only=True)
        if real_fut and mode != "live" and is_production(futures_client.base_url):
            raise ExecutorError("futures_testnet must not point at the production futures API")
        fut = FuturesVenue(futures_client, fut_symbols)
        venues["futures"] = fut if real_fut else PaperVenue(
            "futures", fut, state.paper.setdefault("futures", {"cash": cfg.paper_equity_futures}),
            cfg.futures_fee, fut_symbols)
    return venues


def build_executor(cfg: Optional[ExecutorConfig] = None, mode: Optional[str] = None,
                   environ: Optional[Mapping[str, str]] = None, **kwargs: Any) -> PortfolioExecutor:
    """
    Executor from ``TRADING_MODE`` (``dry_run`` by default). ``live`` needs
    ``LIVE_TRADING_CONFIRM=I_UNDERSTAND`` and a user-confirmed risk limits file.
    """
    from core.config import TradingModeError, resolve_trading_mode

    env = os.environ if environ is None else environ
    cfg = cfg or ExecutorConfig()
    try:
        em = resolve_trading_mode(mode if mode is not None else env.get("TRADING_MODE"),
                                  live_confirm=env.get("LIVE_TRADING_CONFIRM"), timeframe="1d")
    except TradingModeError as exc:
        raise ExecutorError(str(exc)) from exc
    limits = assert_can_start(em.mode, cfg.risk_limits_path)
    if limits is None:
        raise ExecutorError(f"no valid risk limits at {cfg.risk_limits_path}: refusing to run")
    state = LiveState.load(cfg.state_path)
    venues = build_venues(cfg, em.mode, state, kwargs.pop("spot_client", None), kwargs.pop("futures_client", None))
    return PortfolioExecutor(cfg, venues, mode=em.mode, limits=limits, state=state, **kwargs)


def parse_symbols(value: str) -> tuple:
    """Parse --symbols into a tuple, keeping only symbols of the researched spot universe."""
    symbols = tuple(dict.fromkeys(s.strip().upper().replace("/", "") for s in value.split(",") if s.strip()))
    unknown = [s for s in symbols if s not in SPOT_UNIVERSE]
    if not symbols or unknown:
        raise ExecutorError(f"--symbols must be a non-empty subset of {SPOT_UNIVERSE}; unknown: {unknown}")
    return symbols


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Daily live portfolio executor (PLAN §4.3)")
    parser.add_argument("--once", action="store_true", help="run the daily step once and exit")
    parser.add_argument("--force", action="store_true", help="run even if today's run already completed")
    parser.add_argument("--engine", default="T3", help="preregistered configuration (T1-T5, S1/S2)")
    parser.add_argument("--symbols", default=None,
                        help="comma-separated subset of the spot universe, e.g. BTCUSDT,ETHUSDT "
                             "(small accounts: each order must clear MIN_NOTIONAL)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    spot_symbols = parse_symbols(args.symbols) if args.symbols else SPOT_UNIVERSE
    cfg = ExecutorConfig(engine=args.engine, spot_symbols=spot_symbols,
                         shorts_on_futures=args.engine in SHORT_CONFIGS)
    executor = build_executor(cfg)
    logger.info("Portfolio executor mode=%s engine=%s", executor.mode, cfg.engine)
    if args.once:
        report = executor.run(force=args.force)
        logger.info("run %s status=%s nav=%.2f orders=%d", report.day, report.status, report.nav,
                    len(report.orders))
        return 0 if report.status != "aborted" else 1
    executor.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
