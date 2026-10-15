"""
Daily multi-symbol target-weight backtest engine (PLAN.md §2.0, §4.2, §5.2, §5.4, §7).

Timeline of one daily bar ``d`` (labels are bar OPEN times, UTC):

1. ``open[d]`` (00:00 UTC): the funding settlement at 00:00 is paid with the
   position held just BEFORE the rebalance (``tau-``); then the targets decided
   at the close of ``d - delay_bars`` are filled at ``open[d]`` plus slippage
   and commission (sells first; in spot buys never spend more than the cash).
2. During ``d``: the other settlements of the bar (08:00, 16:00 UTC; any extra
   settlement in the funding file) are paid with the post-rebalance position,
   and the catastrophe stop is checked with ``fills.stop_fill`` (gap-aware or
   worst price of the bar). A position is assumed open for every settlement of
   the bar in which its stop fires (the stop time inside the bar is unknown).
3. ``close[d]``: mark to market, ratchet the catastrophe stop
   (``max(stop, C - 3*ATR14)`` for longs, once a day after the close), update
   the simulated kill-switch with the NAV, and compute the next targets:
   ``strategy.signal`` row ``d`` -> discretise -> layer D (``target_weights``)
   -> liquidation check (futures) -> kill-switch -> no-trade band.

Funding notional at a settlement is ``|qty| * open[d]`` (the 1d data has no
intrabar price; at 00:00 it is exact). Funding is applied only to perps, every
row of the funding series is a settlement, and a missing rate while a position
is open raises (no imputation). BNBUSDT has no perp P&L (PLAN §5.2.2).

After a catastrophe stop the symbol is locked until its signal returns to 0
(or flips sign): the engine never buys back the same move the next morning.

With ``sizing=None`` the signal is used directly as the weight (no
discretisation, vol target or band) and orders are sent only when the target
changes: ``E = 1`` on one spot symbol is buy & hold minus costs.

Any missing price for a symbol with an open position raises :class:`BTError`.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.config import git_sha
from apps.research.engine.costs import (
    TIER_THRESHOLDS,
    CostModel,
    commission,
    slipped_price,
    slippage_bps,
)
from apps.research.engine.fills import STOP_SLIP_MULT, ratchet_stop
from apps.research.engine.fills import stop_fill as check_stop
from apps.research.engine.liquidation import worst_wick
from apps.research.portfolio.risk import KillSwitch, RiskConfig, apply_kill_switch, check_liquidation
from apps.research.portfolio.sizing import (
    SizingConfig,
    annualized_vol,
    apply_band,
    coin_vol_cap,
    discretize,
    stress_cov,
    target_weights,
)
from apps.research.strategies.base import Context, TargetWeightStrategy

__all__ = [
    "BTError",
    "BTResult",
    "FUNDING_EXCLUDED",
    "wilder_atr",
    "daily_inputs",
    "run_portfolio_bt",
    "resolve_slip",
    "stop_trigger_price",
]

Market = Literal["spot", "futures"]
StopMode = Literal["gap_aware", "worst_bar"]

#: Symbols whose perp P&L is never simulated (anomalous funding, PLAN §5.2.2).
FUNDING_EXCLUDED = frozenset({"BNBUSDT"})
ONE_DAY = pd.Timedelta(days=1)
_TOL = 1e-12
TRADE_COLUMNS = ["time", "symbol", "qty", "ref_price", "price", "notional",
                 "commission", "slippage", "reason"]
COST_COLUMNS = ["commission", "slippage", "funding"]


class BTError(RuntimeError):
    """The backtest cannot continue without imputing data or breaking a rule."""


@dataclass
class BTResult:
    """
    Backtest output (PLAN §4.2).

    - ``equity``: NAV at each bar close (USDT).
    - ``returns``: daily simple returns of the NAV (from day closes).
    - ``weights``: signed notional / NAV per symbol at each bar close.
    - ``trades``: one row per fill (``qty`` signed: + buy, - sell; ``price``
      includes slippage, ``ref_price`` does not; ``reason``).
    - ``costs``: MultiIndex (date, symbol) with ``commission`` and ``slippage``
      (positive costs, USDT) and ``funding`` (cash flow, negative = paid).
    - ``meta``: configuration, data provenance, git sha, trial id and counters.
    """

    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    costs: pd.DataFrame
    meta: dict = field(default_factory=dict)

    def cost_totals(self) -> pd.Series:
        """Total commission, slippage and funding over the run."""
        if self.costs.empty:
            return pd.Series(0.0, index=COST_COLUMNS)
        return self.costs[COST_COLUMNS].sum()


# --------------------------------------------------------------------------- inputs
def wilder_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """
    Wilder's ATR: seeded with the mean of the first ``n`` true ranges, then
    ``ATR_t = (ATR_{t-1} * (n - 1) + TR_t) / n``. Causal. A bar with missing
    prices gets NaN and the recursion resumes from the last valid value.
    """
    h, l, c = (df[k].astype(float) for k in ("high", "low", "close"))
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1, skipna=True)
    tr = tr.where(h.notna() & l.notna())
    trv = tr.to_numpy(dtype=float)
    out = np.full(len(trv), np.nan)
    seed: list[float] = []
    atr = math.nan
    for i, x in enumerate(trv):
        if not math.isfinite(x):
            continue
        if math.isnan(atr):
            seed.append(x)
            if len(seed) == n:
                atr = sum(seed) / n
                out[i] = atr
            continue
        atr = (atr * (n - 1) + x) / n
        out[i] = atr
    return pd.Series(out, index=df.index, name=f"atr{n}")


def daily_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Causal per-bar inputs used by the engines: log return, Wilder ATR14,
    ``atr_pct``, its rolling 90-bar median (``atr_pct_med90``) and the 30-bar
    median quote volume (``qv30``, NaN until 30 valid bars exist).
    """
    close = df["close"].astype(float)
    qv = df["quote_volume"] if "quote_volume" in df else df["volume"] * close
    atr = wilder_atr(df, 14)
    atr_pct = atr / close
    return pd.DataFrame({
        "logret": np.log(close / close.shift(1)),
        "atr": atr,
        "atr_pct": atr_pct,
        "atr_pct_med90": atr_pct.rolling(90, min_periods=1).median(),
        "qv30": qv.astype(float).rolling(30, min_periods=30).median(),
    }, index=df.index)


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float, np.floating)) and math.isfinite(x)


def resolve_slip(symbol, t, row: Mapping, cost: CostModel, fixed_slip_bps: Optional[float],
                 exit_only: bool = False) -> Optional[float]:
    """
    Slippage (bps) for a fill of ``symbol`` decided with the inputs ``row``.

    Returns ``None`` when the symbol is not tradable (30d volume < 5M or not
    enough history) for a new/increased position. Exits of untradable symbols
    use the worst tradable tier (C), widened by the ATR ratio when known.
    """
    if fixed_slip_bps is not None:
        return float(fixed_slip_bps) * cost.cost_mult
    qv, ap, med = row.get("qv30"), row.get("atr_pct"), row.get("atr_pct_med90")
    if _finite(qv) and qv >= TIER_THRESHOLDS["C"] and _finite(ap) and _finite(med) and ap > 0 and med > 0:
        return slippage_bps(symbol, t, qv, ap, med, cost)
    if not exit_only:
        return None
    mult = max(1.0, ap / med) if (_finite(ap) and _finite(med) and med > 0) else 1.0
    return float(cost.slip_bps["C"]) * mult * cost.cost_mult


def provenance(panel: Mapping[str, pd.DataFrame], funding: Optional[Mapping[str, pd.Series]]) -> dict:
    """Data provenance (hashes and source commits from the loader's ``attrs``)."""
    keys = ("relpath", "sha256", "source_commit", "proxy", "verified")
    data = {s: {k: df.attrs[k] for k in keys if k in df.attrs} for s, df in panel.items()}
    fund = {s: {k: f.attrs[k] for k in keys if k in f.attrs} for s, f in (funding or {}).items()}
    return {"data": data, "funding_data": fund}


def _validate_panel(panel: Mapping[str, pd.DataFrame]) -> None:
    if not panel:
        raise BTError("empty panel")
    for sym, df in panel.items():
        missing = {"open", "high", "low", "close"} - set(df.columns)
        if missing:
            raise BTError(f"{sym}: missing columns {sorted(missing)}")
        if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_monotonic_increasing:
            raise BTError(f"{sym}: index must be a sorted DatetimeIndex")
        if df.index.has_duplicates:
            raise BTError(f"{sym}: duplicated bars")


def _validate_signal(E, symbols: list[str], market: str) -> pd.DataFrame:
    if not isinstance(E, pd.DataFrame):
        raise BTError(f"strategy.signal must return a DataFrame, got {type(E).__name__}")
    extra = set(E.columns) - set(symbols)
    if extra:
        raise BTError(f"signal has symbols not in the panel: {sorted(extra)}")
    vals = E.to_numpy(dtype=float)
    finite = vals[np.isfinite(vals)]
    if np.isinf(vals).any() or (finite.size and (finite.min() < -1 - _TOL or finite.max() > 1 + _TOL)):
        raise BTError("signal values must be in [-1, 1] (or NaN)")
    if market == "spot" and finite.size and finite.min() < -_TOL:
        raise BTError("short signals are not executable in spot")
    return E


# --------------------------------------------------------------------------- engine
class _Book:
    """Cash, positions and the cost/trade ledgers shared by the two engines."""

    def __init__(self, symbols: list[str], market: str, cost: CostModel, initial: float):
        self.symbols = symbols
        self.market = market
        self.cost = cost
        self.cash = float(initial)
        self.qty = dict.fromkeys(symbols, 0.0)
        self.trades: list[tuple] = []
        self.costs: dict[tuple, list[float]] = {}

    def _cost_row(self, day, sym) -> list[float]:
        return self.costs.setdefault((day, sym), [0.0, 0.0, 0.0])

    def fill(self, time, day, sym: str, delta: float, ref_price: float, slip_bps: float, reason: str,
             raw_price: Optional[float] = None) -> float:
        """Execute ``delta`` units at ``ref_price`` (+ slippage). Returns the fill price.

        ``raw_price`` overrides the slipped price (stops: already slipped).
        """
        if delta == 0:
            return ref_price
        side = 1 if delta > 0 else -1
        price = raw_price if raw_price is not None else slipped_price(ref_price, side, slip_bps)
        fee = commission(delta * price, self.market, self.cost)
        slip_cost = abs(delta) * abs(price - ref_price)
        self.cash -= delta * price + fee
        self.qty[sym] += delta
        if abs(self.qty[sym]) < 1e-15:
            self.qty[sym] = 0.0
        row = self._cost_row(day, sym)
        row[0] += fee
        row[1] += slip_cost
        self.trades.append((time, sym, delta, ref_price, price, delta * price, fee, slip_cost, reason))
        return price

    def fund(self, day, sym: str, qty: float, price: float, rate: float, mult: float, when) -> None:
        """Funding at one settlement: ``-qty * price * F * mult`` (longs pay when F > 0)."""
        if qty == 0:
            return
        if not (_finite(rate) and _finite(price)):
            raise BTError(f"{sym}: missing funding rate or price at settlement {when} with an open position")
        flow = -qty * price * rate * mult
        self.cash += flow
        self._cost_row(day, sym)[2] += flow

    def nav(self, prices: Mapping[str, float], when) -> float:
        total = self.cash
        for sym, q in self.qty.items():
            if q != 0:
                p = prices.get(sym, math.nan)
                if not _finite(p):
                    raise BTError(f"{sym}: missing price at {when} with an open position (no imputation)")
                total += q * p
        return total

    def frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        trades = pd.DataFrame(self.trades, columns=TRADE_COLUMNS)
        if self.costs:
            idx = pd.MultiIndex.from_tuples(list(self.costs), names=["date", "symbol"])
            costs = pd.DataFrame(list(self.costs.values()), index=idx, columns=COST_COLUMNS).sort_index()
        else:
            costs = pd.DataFrame(columns=COST_COLUMNS,
                                 index=pd.MultiIndex.from_tuples([], names=["date", "symbol"]))
        return trades, costs


def _ts(value, default) -> pd.Timestamp:
    if value is None:
        return default
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts


def _settlements(funding: Optional[pd.Series], start, end) -> list[tuple[pd.Timestamp, float]]:
    if funding is None or funding.empty:
        return []
    lo = funding.index.searchsorted(start, side="left")
    hi = funding.index.searchsorted(end, side="left")
    return list(zip(funding.index[lo:hi], funding.to_numpy(dtype=float)[lo:hi]))


def stop_trigger_price(open_: float, high: float, low: float, stop: float, side: int, mode: str) -> float:
    """Raw stop exit price before slippage (same rule as ``fills.stop_fill``)."""
    if mode == "gap_aware":
        return min(stop, open_) if side == 1 else max(stop, open_)
    return low if side == 1 else high


def _rebalance_fill(book: "_Book", d, s: str, delta: float, px: float, slip: float, stop: dict,
                    C: pd.DataFrame, ATR: pd.DataFrame, gi: int, atr_mult: Optional[float]) -> None:
    """Fill a rebalance order at the open and (re)place the catastrophe stop on a new position."""
    before = book.qty[s]
    book.fill(d, d, s, delta, px, slip, "rebalance")
    after = book.qty[s]
    if after == 0:
        stop[s] = math.nan
    elif before == 0 or np.sign(before) != np.sign(after):
        stop[s] = math.nan
        if atr_mult is not None:
            pc = C.iloc[gi - 1][s] if gi > 0 else math.nan
            pa = ATR.iloc[gi - 1][s] if gi > 0 else math.nan
            if not (_finite(pc) and _finite(pa)):
                raise BTError(f"{s}: no ATR14 before {d} to place the catastrophe stop")
            stop[s] = ratchet_stop(None, pc, pa, 1 if after > 0 else -1, atr_mult)


def run_portfolio_bt(
    strategy: TargetWeightStrategy,
    panel: Mapping[str, pd.DataFrame],
    market: Market,
    cost: CostModel,
    sizing: Optional[SizingConfig],
    risk: Optional[RiskConfig],
    start=None,
    end=None,
    stop_fill: StopMode = "gap_aware",
    delay_bars: int = 1,
    *,
    funding: Optional[Mapping[str, pd.Series]] = None,
    ctx: Optional[Context] = None,
    initial_equity: float = 10_000.0,
    catastrophe_atr_mult: Optional[float] = 3.0,
    leverage: Optional[Mapping[str, float]] = None,
    fixed_slip_bps: Optional[float] = None,
    trial_id: Optional[str] = None,
) -> BTResult:
    """
    Run a daily target-weight backtest (see the module docstring for the timeline).

    ``panel``: 1d OHLCV per symbol (loader format). ``funding``: settlement
    series per perp (required in futures for every symbol except BNBUSDT, which
    is never traded as a perp). ``sizing=None`` uses the signal as weights;
    ``risk=None`` disables the simulated kill-switch and liquidation check.
    ``catastrophe_atr_mult=None`` disables the catastrophe stop (benchmarks only).
    ``fixed_slip_bps`` replaces the volume-tier slippage (still scaled by
    ``cost.cost_mult``). ``leverage`` is the isolated-margin leverage per perp
    (default 1x; capped by ``risk``).
    """
    if market not in ("spot", "futures"):
        raise BTError(f"unknown market {market!r}")
    if stop_fill not in ("gap_aware", "worst_bar"):
        raise BTError(f"unknown stop_fill {stop_fill!r}")
    if not isinstance(delay_bars, int) or delay_bars < 1:
        raise BTError(f"delay_bars must be an int >= 1 (no same-bar fills), got {delay_bars!r}")
    if not _finite(initial_equity) or initial_equity <= 0:
        raise BTError("initial_equity must be > 0")
    _validate_panel(panel)
    symbols = list(panel)
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
        if risk is not None and L > risk.max_leverage(s) + _TOL:
            raise BTError(f"{s}: leverage {L} above the cap {risk.max_leverage(s)}")
    lev_series = pd.Series(lev)

    dates = panel[symbols[0]].index
    for s in symbols[1:]:
        dates = dates.union(panel[s].index)
    frames = {s: panel[s].reindex(dates) for s in symbols}
    inputs = {s: daily_inputs(panel[s]).reindex(dates) for s in symbols}
    O = pd.DataFrame({s: frames[s]["open"] for s in symbols}).astype(float)
    H = pd.DataFrame({s: frames[s]["high"] for s in symbols}).astype(float)
    Lo = pd.DataFrame({s: frames[s]["low"] for s in symbols}).astype(float)
    C = pd.DataFrame({s: frames[s]["close"] for s in symbols}).astype(float)
    ATR = pd.DataFrame({s: inputs[s]["atr"] for s in symbols})
    rets = pd.DataFrame({s: inputs[s]["logret"] for s in symbols})
    wick = {}
    if market == "futures" and risk is not None:
        wick = {side: pd.DataFrame({s: worst_wick(panel[s], side).reindex(dates) for s in symbols})
                for side in (1, -1)}

    t0 = _ts(start, dates[0])
    t1 = _ts(end, dates[-1])
    sim = np.flatnonzero((dates >= t0) & (dates <= t1))
    if len(sim) < 2:
        raise BTError(f"need at least 2 bars in [{t0}, {t1}]")

    ctx = ctx or Context(market=market)
    ctx.frames = dict(panel)
    ctx.funding = funding if market == "futures" else {}
    E = _validate_signal(strategy.signal(dict(panel), ctx), symbols, market)
    E = E.reindex(index=dates, columns=symbols).astype(float)

    book = _Book(symbols, market, cost, initial_equity)
    ks = KillSwitch(risk) if risk is not None else None
    stop = dict.fromkeys(symbols, math.nan)
    lock = dict.fromkeys(symbols, 0)          # side of the stopped-out position, 0 = unlocked
    last_raw = dict.fromkeys(symbols, 0.0)    # sizing=None: last target sent
    queue: dict[int, dict[str, float]] = {}
    carry: dict[str, float] = {}
    counters = {"stops": 0, "liq_rejected": 0, "deferred_orders": 0, "untradable": 0,
                "no_vol": 0, "kill_switch_days": 0, "spot_buys_scaled": 0}
    eq_vals, w_rows, ks_rows = [], [], []
    fmult = cost.funding_mult

    for k, gi in enumerate(sim):
        d = dates[gi]
        opens = O.iloc[gi]

        # 1. Settlement at 00:00 with the position held before the rebalance (tau-).
        bar_settle = {s: _settlements(funding[s], d, d + ONE_DAY) for s in tradable} \
            if market == "futures" else {}
        pre_qty = dict(book.qty)
        for s, rows in bar_settle.items():
            for tau, rate in rows:
                if tau == d:
                    book.fund(d, s, pre_qty[s], opens[s], rate, fmult, tau)

        # 2. Fill the targets due at this open.
        carry.update(queue.pop(k, {}))
        if carry:
            nav_open = book.nav(opens.to_dict(), d)
            orders = []
            for s, w in list(carry.items()):
                px = opens[s]
                if not _finite(px):
                    counters["deferred_orders"] += 1
                    continue           # no bar today: keep the order pending
                del carry[s]
                target_qty = w * nav_open / px
                delta = target_qty - book.qty[s]
                if abs(delta * px) <= _TOL * max(nav_open, 1.0):
                    continue
                increase = abs(target_qty) > abs(book.qty[s]) or np.sign(target_qty) != np.sign(book.qty[s])
                row = inputs[s].iloc[gi - 1].to_dict() if gi > 0 else {}
                slip = resolve_slip(s, d, row, cost, fixed_slip_bps, exit_only=not increase)
                if slip is None:
                    slip = resolve_slip(s, d, row, cost, fixed_slip_bps, exit_only=True)
                orders.append([s, delta, px, slip])
            sells = [o for o in orders if o[1] < 0]
            buys = [o for o in orders if o[1] > 0]
            for s, delta, px, slip in sells:
                _rebalance_fill(book, d, s, delta, px, slip, stop, C, ATR, gi, catastrophe_atr_mult)
            if market == "spot" and buys:
                need = sum(dq * slipped_price(p, 1, sl) * (1 + cost.fee_rate("spot")) for _, dq, p, sl in buys)
                if need > book.cash:
                    scale = max(book.cash, 0.0) / need
                    counters["spot_buys_scaled"] += 1
                    for o in buys:
                        o[1] *= scale
            for s, delta, px, slip in buys:
                _rebalance_fill(book, d, s, delta, px, slip, stop, C, ATR, gi, catastrophe_atr_mult)

        # 3. Intrabar settlements with the post-rebalance position.
        for s, rows in bar_settle.items():
            if (pre_qty[s] != 0 or book.qty[s] != 0) and not rows:
                raise BTError(f"{s}: no funding settlement in bar {d} with an open position")
            for tau, rate in rows:
                if tau != d:
                    book.fund(d, s, book.qty[s], opens[s], rate, fmult, tau)

        # 4. Catastrophe stops (placed on the exchange since the entry).
        for s in symbols:
            q = book.qty[s]
            if q == 0 or not _finite(stop[s]):
                continue
            o, h, l = O.iloc[gi][s], H.iloc[gi][s], Lo.iloc[gi][s]
            if not (_finite(o) and _finite(h) and _finite(l)):
                raise BTError(f"{s}: missing bar {d} with an open position (no imputation)")
            side = 1 if q > 0 else -1
            row = inputs[s].iloc[gi - 1].to_dict() if gi > 0 else {}
            slip = resolve_slip(s, d, row, cost, fixed_slip_bps, exit_only=True)
            sf = check_stop(o, h, l, stop[s], side, stop_fill, slip)
            if sf.triggered:
                raw = stop_trigger_price(o, h, l, stop[s], side, stop_fill)
                book.fill(d, d, s, -q, raw, STOP_SLIP_MULT * slip, "stop_gap" if sf.gapped else "stop")
                stop[s] = math.nan
                lock[s] = side
                counters["stops"] += 1

        # 5. Mark to market at the close.
        closes = C.iloc[gi]
        nav = book.nav(closes.to_dict(), d)
        eq_vals.append(nav)
        w_rows.append({s: book.qty[s] * closes[s] / nav if book.qty[s] != 0 else 0.0 for s in symbols})

        # 6. Ratchet the catastrophe stops (once a day, after the close).
        for s in symbols:
            if book.qty[s] != 0 and _finite(stop[s]):
                a = ATR.iloc[gi][s]
                if _finite(a):
                    stop[s] = ratchet_stop(stop[s], closes[s], a, 1 if book.qty[s] > 0 else -1,
                                           catastrophe_atr_mult)

        # 7. Decide the next targets.
        state = ks.update(nav) if ks is not None else None
        if state is not None:
            ks_rows.append((d, state.level, state.risk_mult, state.daily_return, state.drawdown))
            if state.level != "normal":
                counters["kill_switch_days"] += 1
        if k + delay_bars >= len(sim):
            continue
        w_held = pd.Series(w_rows[-1], dtype=float)
        e = E.iloc[gi].fillna(0.0).copy()
        e_sign = np.sign(discretize(e, sizing.step) if sizing is not None else e)
        for s in symbols:
            if lock[s] != 0:
                if e_sign[s] != lock[s]:
                    lock[s] = 0
                else:
                    e[s] = 0.0
            if s not in tradable:
                e[s] = 0.0
            elif e[s] != 0 and resolve_slip(s, d, inputs[s].iloc[gi].to_dict(), cost, fixed_slip_bps) is None:
                e[s] = 0.0
                counters["untradable"] += 1

        if sizing is not None:
            e_q = discretize(e, sizing.step)
            sigma = annualized_vol(rets.iloc[: gi + 1], None, window=sizing.vol_window)
            no_vol = (e_q != 0) & ~np.isfinite(sigma)
            if no_vol.any():
                counters["no_vol"] += int(no_vol.sum())
                e_q[no_vol] = 0.0
            cov = stress_cov(rets.iloc[: gi + 1], d, lam=sizing.ewma_lambda, rho_floor=sizing.rho_floor,
                             vol_window=sizing.vol_window)
            w_new = target_weights(e_q, sigma, cov, sizing)
        else:
            w_new = e.copy()
            if w_new[w_new > 0].sum() > 1.0 + 1e-9 or -w_new[w_new < 0].sum() > 0.5 + 1e-9:
                raise BTError(f"raw weights at {d} break gross caps (long <= 1, short <= 0.5)")

        # Liquidation distance check before opening/increasing a perp position.
        if wick:
            for s in symbols:
                wn, wh = w_new[s], w_held.get(s, 0.0)
                if wn == 0 or (np.sign(wn) == np.sign(wh) and abs(wn) <= abs(wh)):
                    continue
                side = 1 if wn > 0 else -1
                if side == 1 and lev[s] <= 1.0:
                    continue   # isolated long at <= 1x: liquidation price is 0, it cannot be liquidated
                c, a = closes[s], ATR.iloc[gi][s]
                ok = _finite(c) and _finite(a) and a > 0 and check_liquidation(
                    s, c, c - side * (catastrophe_atr_mult or 3.0) * a, lev[s], side,
                    wick[side].iloc[gi][s], risk)
                if not ok:
                    counters["liq_rejected"] += 1
                    w_new[s] = wh if np.sign(wh) == side else 0.0

        w_ks = apply_kill_switch(w_new, w_held, state, lev_series).reindex(symbols) if state is not None \
            else w_new
        if sizing is not None:
            max_abs = coin_vol_cap(e_q, sigma, sizing)
            if state is not None and (state.risk_mult < 1 or state.entries_blocked):
                max_abs = np.minimum(max_abs, w_ks.abs())
            w_final = apply_band(w_ks, w_held.reindex(symbols).fillna(0.0), sizing.band, cfg=sizing,
                                 max_abs=max_abs).reindex(symbols)
            targets = {s: float(w_final[s]) for s in symbols if w_final[s] != w_held.get(s, 0.0)}
        else:
            targets = {}
            for s in symbols:
                wt = float(w_ks[s])
                if state is not None and state.entries_blocked and not state.flatten_leveraged \
                        and np.sign(wt) == np.sign(w_held.get(s, 0.0)) and abs(wt) >= abs(w_held.get(s, 0.0)) - 1e-9:
                    continue   # blocked entries: hold what is held
                if wt != last_raw[s] or (wt == 0 and book.qty[s] != 0):
                    targets[s] = wt
                    last_raw[s] = wt
        if targets:
            queue.setdefault(k + delay_bars, {}).update(targets)

    idx = dates[sim]
    equity = pd.Series(eq_vals, index=idx, name="equity")
    weights = pd.DataFrame(w_rows, index=idx, columns=symbols)
    trades, costs = book.frames()
    meta = {
        "engine": "portfolio_bt",
        "strategy": getattr(strategy, "name", type(strategy).__name__),
        "params": dict(getattr(strategy, "params", {}) or {}),
        "n_free_params": getattr(strategy, "n_free_params", None),
        "market": market,
        "start": str(idx[0]), "end": str(idx[-1]),
        "initial_equity": initial_equity,
        "cost": asdict(cost),
        "sizing": asdict(sizing) if sizing is not None else None,
        "risk": asdict(risk) if risk is not None else None,
        "stop_fill": stop_fill,
        "delay_bars": delay_bars,
        "catastrophe_atr_mult": catastrophe_atr_mult,
        "fixed_slip_bps": fixed_slip_bps,
        "leverage": lev,
        "funding_verified": False if market == "futures" else None,
        "git_sha": git_sha(),
        "trial_id": trial_id,
        "counters": counters,
        "kill_switch": pd.DataFrame(ks_rows, columns=["date", "level", "risk_mult", "daily_return",
                                                      "drawdown"]).set_index("date"),
        **provenance(panel, funding if market == "futures" else None),
    }
    returns = equity.pct_change()
    returns.iloc[0] = equity.iloc[0] / initial_equity - 1.0
    return BTResult(equity, returns.rename("returns"), weights, trades, costs, meta)
