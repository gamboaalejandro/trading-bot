"""
Event-driven backtest engine for intraday strategies with stops (4h / 1h; PLAN.md §2.6, §2.9, §4.2).

Timeline of one intraday bar ``t`` (labels are bar OPEN times, UTC):

1. ``open[t]``: funding settlements at exactly ``t`` are paid with the
   position held before any fill (``tau-``). Then the intents decided at the
   close of ``t - delay_bars`` are executed in this order: stop/take-profit
   updates, exits, entries. Market fills use ``open[t]`` plus slippage.
2. During ``t``: the remaining settlements of the bar are paid with the new
   position; resting stops and take-profits are checked against the bar's
   range. **If both the stop and the take-profit are inside the bar, the stop
   wins** (the intrabar path is unknown; PLAN §1.4). Stops fill gap-aware or at
   the bar's worst price (``fills.stop_fill``) and pay double slippage;
   take-profits fill exactly at their level (never better), with the taker fee.
3. ``close[t]``: mark to market. On the last bar of a UTC day the simulated
   kill-switch is updated with the NAV (daily close-to-close, PLAN §7.6).
   Then ``strategy.on_bar(t, bars, ctx)`` returns new intents.

Rules enforced by the engine, whatever the strategy asks:

- Stops only move in the trade's favour (trailing never loosens).
- An entry needs a protective stop; entries whose fill already sits beyond the
  stop are rejected; there is no pyramiding (a second entry in the same
  direction is ignored) and no averaging down.
- Risk sizing: ``qty = R * NAV / |entry - stop|`` with ``R`` = 0.5 % of NAV
  on BTC/ETH and 0.25 % on altcoins (``config/risk_limits.yml``), times the
  kill-switch risk multiplier; then the per-coin caps of §2.0 (0.35 / 0.20 of
  NAV, never more than the leverage cap), gross long <= 1, gross short <= 0.5,
  long altcoins <= 0.6, and the cash available in spot.
- Futures: isolated margin; shorts and leveraged positions must pass the
  liquidation-distance check with the worst historical wick of the CLOSED
  daily bars. BNBUSDT is never traded as a perp.

Daily context: every intraday bar sees the last 1d bar whose close is at or
before the intraday bar's close (``merge_asof`` backward on availability
times, :func:`merge_daily_asof`). The 4h bar 20:00-24:00 sees the day that
closes at 24:00; the 16:00-20:00 bar still sees the previous day.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.config import git_sha
from apps.research.engine.costs import CostModel, slipped_price
from apps.research.engine.fills import STOP_SLIP_MULT
from apps.research.engine.fills import stop_fill as check_stop
from apps.research.engine.liquidation import worst_wick
from apps.research.engine.portfolio_bt import (
    FUNDING_EXCLUDED,
    BTError,
    BTResult,
    _Book,
    _finite,
    _settlements,
    _ts,
    _validate_panel,
    daily_inputs,
    provenance,
    resolve_slip,
    stop_trigger_price,
)
from apps.research.portfolio.risk import KillSwitch, RiskConfig, check_liquidation
from apps.research.portfolio.sizing import SizingConfig
from apps.research.strategies.base import Context, EventStrategy, OrderIntent, Position

__all__ = [
    "DEFAULT_RISK_MAJOR",
    "DEFAULT_RISK_ALT",
    "merge_daily_asof",
    "infer_tf",
    "run_event_bt",
]

Market = Literal["spot", "futures"]
StopMode = Literal["gap_aware", "worst_bar"]

DEFAULT_RISK_MAJOR = 0.005   # 0.5 % NAV per trade on BTC/ETH (PLAN §7.3)
DEFAULT_RISK_ALT = 0.0025    # 0.25 % NAV per trade on altcoins / tactical engines
ONE_DAY = pd.Timedelta(days=1)
ROUND_TRIP_COLUMNS = ["symbol", "side", "entry_time", "entry_price", "exit_time", "exit_price",
                      "qty", "pnl", "r_multiple", "exit_reason", "tag"]


def infer_tf(index: pd.DatetimeIndex) -> pd.Timedelta:
    """Bar length of a regular intraday index (smallest positive step)."""
    if len(index) < 2:
        raise BTError("cannot infer the timeframe from fewer than 2 bars")
    step = pd.Series(index).diff().dropna().min()
    if step <= pd.Timedelta(0):
        raise BTError("index must be strictly increasing")
    return pd.Timedelta(step)


def merge_daily_asof(intraday: pd.DataFrame, daily: pd.DataFrame, tf, prefix: str = "d_") -> pd.DataFrame:
    """
    Attach to each intraday bar the last CLOSED daily bar (``merge_asof`` backward).

    An intraday bar labelled ``t`` closes at ``t + tf``; a daily bar labelled
    ``D`` closes at ``D + 1 day``. The daily bar is joined when
    ``D + 1 day <= t + tf``. Daily columns get ``prefix`` and ``{prefix}date``
    holds the daily bar's label. The intraday index and columns are preserved.
    """
    tf = pd.Timedelta(tf)
    left = pd.DataFrame({"_avail": (intraday.index + tf).astype("datetime64[ns, UTC]")})
    right = daily.add_prefix(prefix)
    right[f"{prefix}date"] = daily.index
    right["_avail"] = (daily.index + ONE_DAY).astype("datetime64[ns, UTC]")
    right = right.reset_index(drop=True).sort_values("_avail")
    merged = pd.merge_asof(left, right, on="_avail", direction="backward", allow_exact_matches=True)
    merged.index = intraday.index
    merged = merged.drop(columns="_avail")
    return pd.concat([intraday, merged], axis=1)


@dataclass
class _Pos:
    side: int
    qty: float
    entry_price: float
    entry_time: pd.Timestamp
    stop: float
    tp: Optional[float]
    init_risk: float
    tag: str
    bars_held: int = 0

    def view(self, symbol: str) -> Position:
        return Position(symbol, self.side, self.qty, self.entry_price, self.entry_time,
                        self.stop, self.tp, self.bars_held)


def run_event_bt(
    strategy: EventStrategy,
    panel: Mapping[str, pd.DataFrame],
    market: Market,
    cost: CostModel,
    risk: Optional[RiskConfig],
    start=None,
    end=None,
    stop_fill: StopMode = "gap_aware",
    delay_bars: int = 1,
    *,
    daily: Mapping[str, pd.DataFrame],
    tf=None,
    funding: Optional[Mapping[str, pd.Series]] = None,
    sizing: Optional[SizingConfig] = None,
    ctx: Optional[Context] = None,
    initial_equity: float = 10_000.0,
    leverage: Optional[Mapping[str, float]] = None,
    risk_per_trade: Optional[Mapping[str, float]] = None,
    fixed_slip_bps: Optional[float] = None,
    trial_id: Optional[str] = None,
) -> BTResult:
    """
    Run an event-driven backtest (see the module docstring).

    ``panel``: intraday OHLCV per symbol (4h or 1h, loader format). ``daily``:
    1d OHLCV per symbol, used for the closed-day context, slippage tiers and
    the worst historical wick. ``funding`` is required in futures for every
    traded symbol. ``risk=None`` disables the kill-switch and liquidation check
    (leverage then defaults to the 1x cap). ``sizing`` provides the per-coin and
    gross caps (defaults to ``SizingConfig()``).

    ``equity`` and ``weights`` are per intraday bar; ``returns`` are daily
    (NAV at each UTC day close), as for the portfolio engine.
    """
    if market not in ("spot", "futures"):
        raise BTError(f"unknown market {market!r}")
    if stop_fill not in ("gap_aware", "worst_bar"):
        raise BTError(f"unknown stop_fill {stop_fill!r}")
    if not isinstance(delay_bars, int) or delay_bars < 1:
        raise BTError(f"delay_bars must be an int >= 1 (no same-bar fills), got {delay_bars!r}")
    _validate_panel(panel)
    symbols = list(panel)
    missing_daily = [s for s in symbols if s not in daily]
    if missing_daily:
        raise BTError(f"no daily bars for {missing_daily}")
    _validate_panel({s: daily[s] for s in symbols})
    sizing = sizing or SizingConfig()
    funding = dict(funding or {})
    tradable = [s for s in symbols if not (market == "futures" and s in FUNDING_EXCLUDED)]
    if market == "futures":
        missing_f = [s for s in tradable if s not in funding]
        if missing_f:
            raise BTError(f"futures backtest without funding for {missing_f} (no imputation)")
    lev = {s: float((leverage or {}).get(s, 1.0)) for s in symbols}
    for s, L in lev.items():
        if market == "spot" and L != 1.0:
            raise BTError("spot positions cannot be leveraged")
        if risk is not None and L > risk.max_leverage(s) + 1e-12:
            raise BTError(f"{s}: leverage {L} above the cap {risk.max_leverage(s)}")
    majors = risk.majors if risk is not None else sizing.majors
    rpt = {s: float((risk_per_trade or {}).get(s, DEFAULT_RISK_MAJOR if s in majors else DEFAULT_RISK_ALT))
           for s in symbols}

    times = panel[symbols[0]].index
    for s in symbols[1:]:
        times = times.union(panel[s].index)
    tf = pd.Timedelta(tf) if tf is not None else infer_tf(times)

    # Closed-day context per intraday bar: OHLCV, slippage inputs and worst wicks.
    frames, ctx_in = {}, {}
    for s in symbols:
        d = daily[s]
        extra = daily_inputs(d)
        extra["wick_long"] = worst_wick(d, 1)
        extra["wick_short"] = worst_wick(d, -1)
        frames[s] = merge_daily_asof(panel[s], d, tf).reindex(times)
        ctx_in[s] = merge_daily_asof(panel[s][[]], extra, tf, prefix="").reindex(times)
    O = pd.DataFrame({s: frames[s]["open"] for s in symbols}).astype(float).to_numpy()
    H = pd.DataFrame({s: frames[s]["high"] for s in symbols}).astype(float).to_numpy()
    Lw = pd.DataFrame({s: frames[s]["low"] for s in symbols}).astype(float).to_numpy()
    C = pd.DataFrame({s: frames[s]["close"] for s in symbols}).astype(float).to_numpy()
    col = {s: i for i, s in enumerate(symbols)}

    t0, t1 = _ts(start, times[0]), _ts(end, times[-1])
    sim = np.flatnonzero((times >= t0) & (times <= t1))
    if len(sim) < 2:
        raise BTError(f"need at least 2 bars in [{t0}, {t1}]")

    ctx = ctx or Context(market=market)
    ctx.frames = {s: frames[s].loc[panel[s].index] for s in symbols}
    ctx.daily = dict(daily)
    ctx.funding = funding if market == "futures" else {}
    pos_end = {s: ctx.frames[s].index for s in symbols}

    book = _Book(symbols, market, cost, initial_equity)
    ks = KillSwitch(risk) if risk is not None else None
    state = None
    positions: dict[str, _Pos] = {}
    queue: dict[int, list[OrderIntent]] = {}
    round_trips: list[tuple] = []
    counters = {"entries": 0, "stops": 0, "take_profits": 0, "exits": 0, "ignored_entries": 0,
                "rejected_gap": 0, "rejected_liq": 0, "rejected_size": 0, "blocked_entries": 0,
                "missed_entries": 0, "stop_loosen_ignored": 0, "stop_and_tp_same_bar": 0,
                "untradable": 0, "kill_switch_exits": 0}
    eq_vals, w_rows, ks_rows = [], [], []
    fmult = cost.funding_mult

    def inp(s: str, gi: int) -> dict:
        return ctx_in[s].iloc[gi].to_dict()

    def close_pos(s: str, t, day, ref: float, slip: float, reason: str, qty: Optional[float] = None) -> None:
        p = positions[s]
        q = p.qty if qty is None else min(qty, p.qty)
        price = book.fill(t, day, s, -p.side * q, ref, slip, reason)
        pnl = p.side * q * (price - p.entry_price)
        round_trips.append((s, p.side, p.entry_time, p.entry_price, t, price, q, pnl,
                            pnl / (q * p.init_risk) if p.init_risk > 0 else math.nan, reason, p.tag))
        p.qty -= q
        if p.qty <= 1e-15 or book.qty[s] == 0:
            del positions[s]

    def _enter(it: OrderIntent, s: str, side: int, t, day, gi: int) -> None:
        px = opens[s]
        if not _finite(px):
            counters["missed_entries"] += 1
            return
        row = inp(s, gi)
        slip = resolve_slip(s, t, row, cost, fixed_slip_bps)
        if slip is None:
            counters["untradable"] += 1
            return
        fill_est = slipped_price(px, side, slip)
        stop = float(it.stop_price)
        if (side == 1 and fill_est <= stop) or (side == -1 and fill_est >= stop):
            counters["rejected_gap"] += 1        # the open is already beyond the stop
            return
        if market == "futures" and risk is not None and (side == -1 or lev[s] > 1.0):
            wick = row.get("wick_long" if side == 1 else "wick_short")
            if not check_liquidation(s, fill_est, stop, lev[s], side, wick, risk):
                counters["rejected_liq"] += 1
                return
        nav_open = book.nav(opens, t)
        if it.qty is not None:
            qty = it.qty
        elif it.target_weight is not None:
            qty = it.target_weight * nav_open / fill_est
        else:
            mult = state.risk_mult if state is not None else 1.0
            qty = rpt[s] * mult * nav_open / abs(fill_est - stop)
        long_now = sum(q * opens[x] for x, q in book.qty.items() if q > 0)
        short_now = -sum(q * opens[x] for x, q in book.qty.items() if q < 0)
        alt_long_now = sum(q * opens[x] for x, q in book.qty.items() if q > 0 and not sizing.is_major(x))
        lev_cap = risk.max_leverage(s) if risk is not None else 1.0
        caps = [qty * fill_est, nav_open * min(sizing.coin_cap(s), lev_cap)]
        if side == 1:
            caps.append(sizing.gross_long_cap * nav_open - long_now)
            if not sizing.is_major(s):
                caps.append(sizing.alt_long_cap * nav_open - alt_long_now)
        else:
            caps.append(sizing.gross_short_cap * nav_open - short_now)
        if market == "spot":
            caps.append(book.cash / (1.0 + cost.fee_rate("spot")))
        notional = min(caps)
        if not notional > 1e-6 * nav_open:
            counters["rejected_size"] += 1
            return
        price = book.fill(t, day, s, side * notional / fill_est, px, slip, it.tag or "entry")
        positions[s] = _Pos(side, notional / fill_est, price, t, stop, it.take_profit,
                            abs(price - stop), it.tag)
        counters["entries"] += 1

    for k, gi in enumerate(sim):
        t = times[gi]
        day = t.floor("D")
        opens = {s: O[gi, col[s]] for s in symbols}

        # 1. Settlement at the open with the position before any fill (tau-).
        bar_settle = {s: _settlements(funding[s], t, t + tf) for s in tradable} if market == "futures" else {}
        pre_qty = dict(book.qty)
        for s, rows in bar_settle.items():
            for tau, rate in rows:
                if tau == t:
                    book.fund(day, s, pre_qty[s], opens[s], rate, fmult, tau)

        # 2. Execute the intents due at this open: updates, exits, then entries.
        due = queue.pop(k, [])
        order = sorted(due, key=lambda it: 0 if it.is_order_update else (1 if it.is_exit else 2))
        for it in order:
            s = it.symbol
            p = positions.get(s)
            if it.is_order_update:
                if p is None or it.direction != -p.side:
                    continue
                if it.stop_price is not None:
                    better = it.stop_price > p.stop if p.side == 1 else it.stop_price < p.stop
                    if better:
                        p.stop = it.stop_price
                    elif it.stop_price != p.stop:
                        counters["stop_loosen_ignored"] += 1
                if it.take_profit is not None:
                    p.tp = it.take_profit
                continue
            if it.is_exit:
                if p is None or it.direction != -p.side:
                    continue
                px = opens[s]
                if not _finite(px):
                    raise BTError(f"{s}: missing bar {t} with an open position (no imputation)")
                slip = resolve_slip(s, t, inp(s, gi), cost, fixed_slip_bps, exit_only=True)
                close_pos(s, t, day, px, slip, it.tag or "exit", it.qty)
                counters["exits"] += 1
                continue
            # Entry.
            side = it.direction
            if p is not None:
                if p.side == side:
                    counters["ignored_entries"] += 1     # no pyramiding / averaging down
                    continue
                px = opens[s]
                if not _finite(px):
                    raise BTError(f"{s}: missing bar {t} with an open position (no imputation)")
                close_pos(s, t, day, px, resolve_slip(s, t, inp(s, gi), cost, fixed_slip_bps, exit_only=True),
                          "reverse")
            _enter(it, s, side, t, day, gi)

        # 3. Settlements inside the bar with the post-fill position.
        for s, rows in bar_settle.items():
            if (pre_qty[s] != 0 or book.qty[s] != 0) and not rows and tf >= pd.Timedelta(hours=8):
                raise BTError(f"{s}: no funding settlement in bar {t} with an open position")
            for tau, rate in rows:
                if tau != t:
                    book.fund(day, s, book.qty[s], opens[s], rate, fmult, tau)

        # 4. Resting stops and take-profits (the stop wins when both are hit).
        for s in list(positions):
            p = positions[s]
            o, h, l = O[gi, col[s]], H[gi, col[s]], Lw[gi, col[s]]
            if not (_finite(o) and _finite(h) and _finite(l)):
                raise BTError(f"{s}: missing bar {t} with an open position (no imputation)")
            slip = resolve_slip(s, t, inp(s, gi), cost, fixed_slip_bps, exit_only=True)
            sf = check_stop(o, h, l, p.stop, p.side, stop_fill, slip)
            tp_hit = p.tp is not None and (h >= p.tp if p.side == 1 else l <= p.tp)
            if sf.triggered:
                if tp_hit:
                    counters["stop_and_tp_same_bar"] += 1
                raw = stop_trigger_price(o, h, l, p.stop, p.side, stop_fill)
                close_pos(s, t, day, raw, STOP_SLIP_MULT * slip, "stop_gap" if sf.gapped else "stop")
                counters["stops"] += 1
            elif tp_hit:
                close_pos(s, t, day, p.tp, 0.0, "take_profit")
                counters["take_profits"] += 1

        # 5. Mark to market.
        closes = {s: C[gi, col[s]] for s in symbols}
        nav = book.nav(closes, t)
        eq_vals.append(nav)
        w_rows.append({s: book.qty[s] * closes[s] / nav if book.qty[s] != 0 else 0.0 for s in symbols})
        for p in positions.values():
            p.bars_held += 1

        # 6. Kill-switch on the daily close.
        if ks is not None and (t + tf).floor("D") == t + tf:
            state = ks.update(nav)
            ks_rows.append((t + tf, state.level, state.risk_mult, state.daily_return, state.drawdown))
        if k + delay_bars >= len(sim):
            continue
        forced: list[OrderIntent] = []
        if state is not None and state.flatten_leveraged:
            for s, p in positions.items():
                if state.halted or p.side == -1 or lev[s] > 1.0:
                    forced.append(OrderIntent(s, "SELL" if p.side == 1 else "BUY", reduce_only=True,
                                              tag="kill_switch"))
            counters["kill_switch_exits"] += len(forced)

        # 7. Strategy decision at the close of t.
        intents: list[OrderIntent] = []
        if state is None or not state.halted:
            ctx.t = t
            ctx.nav = nav
            ctx.kill_switch = state
            ctx.positions = {s: p.view(s) for s, p in positions.items()}
            ctx._pos = {s: int(pos_end[s].searchsorted(t, side="right")) for s in symbols}
            bars = {s: frames[s].iloc[gi] for s in symbols if _finite(C[gi, col[s]])}
            out = strategy.on_bar(t, bars, ctx) or []
            for it in out:
                if not isinstance(it, OrderIntent):
                    raise BTError(f"on_bar must return OrderIntent objects, got {type(it).__name__}")
                if it.symbol not in col:
                    raise BTError(f"intent for unknown symbol {it.symbol!r}")
                if it.is_entry:
                    if market == "spot" and it.side == "SELL":
                        raise BTError("short entries are not executable in spot")
                    if it.stop_price is None:
                        raise BTError(f"{it.symbol}: entry without a protective stop (PLAN §7.4)")
                    if it.symbol not in tradable:
                        counters["untradable"] += 1
                        continue
                    if state is not None and state.entries_blocked:
                        counters["blocked_entries"] += 1
                        continue
                intents.append(it)
        if forced or intents:
            queue.setdefault(k + delay_bars, []).extend(forced + intents)

    # ----------------------------------------------------------------- results
    idx = times[sim]
    equity = pd.Series(eq_vals, index=idx, name="equity")
    weights = pd.DataFrame(w_rows, index=idx, columns=symbols)
    trades, costs = book.frames()
    close_day = (idx + tf - pd.Timedelta(1, "ns")).floor("D")
    daily_nav = equity.groupby(close_day).last()
    returns = daily_nav.pct_change()
    returns.iloc[0] = daily_nav.iloc[0] / initial_equity - 1.0
    meta = {
        "engine": "event_bt",
        "strategy": getattr(strategy, "name", type(strategy).__name__),
        "params": dict(getattr(strategy, "params", {}) or {}),
        "n_free_params": getattr(strategy, "n_free_params", None),
        "market": market,
        "tf": str(tf),
        "start": str(idx[0]), "end": str(idx[-1]),
        "initial_equity": initial_equity,
        "cost": asdict(cost),
        "sizing": asdict(sizing),
        "risk": asdict(risk) if risk is not None else None,
        "risk_per_trade": rpt,
        "stop_fill": stop_fill,
        "delay_bars": delay_bars,
        "fixed_slip_bps": fixed_slip_bps,
        "leverage": lev,
        "funding_verified": False if market == "futures" else None,
        "git_sha": git_sha(),
        "trial_id": trial_id,
        "counters": counters,
        "round_trips": pd.DataFrame(round_trips, columns=ROUND_TRIP_COLUMNS),
        "equity_daily": daily_nav,
        "kill_switch": pd.DataFrame(ks_rows, columns=["date", "level", "risk_mult", "daily_return",
                                                      "drawdown"]).set_index("date"),
        **provenance(panel, funding if market == "futures" else None),
    }
    return BTResult(equity, returns.rename("returns"), weights, trades, costs, meta)

