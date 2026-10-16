"""
CARRY: conditional delta-neutral funding carry (PLAN.md §2.7; report 04 E1). PAPER ONLY.

Long spot ``Q`` + short perp ``Q`` (same quantity, hence the same notional at
entry) while the funding paid by longs is high. Configurations ``(theta_in,
theta_out)`` in APR: K1 (25 %, 8 %), K2 (20 %, 5 %), K3 (35 %, 10 %).

Timeline (labels are 4h bar OPEN times, UTC):

- The 4h bars that close at 00:00, 08:00 and 16:00 UTC close exactly on a
  funding settlement ``tau``. Signals are evaluated only there, with data
  available at ``tau``: ``basis = C_perp / C_spot - 1`` of the bar closing at
  ``tau``, ``F_bar_3d`` (mean of the last 9 settlements on the 8h grid, NaN if
  any is missing) and the last settlement rate ``F(tau)``.
- Entry: ``APR(F_bar_3d) >= theta_in`` and ``F(tau) > 0`` (and the exit
  condition must not already hold, so a cycle is never opened to be closed at
  the next settlement). Exit: ``APR(F_bar_3d) < theta_out`` or
  ``basis < -0.2 %``. NaN inputs never open a cycle and never close one.
- Decisions taken at ``tau`` are filled at ``open`` of the next 4h bar (the
  bar labelled ``tau``), on both legs, with slippage and commission. The
  settlement at ``tau`` itself is paid with the position held just BEFORE
  those fills (``tau-``): a new cycle never collects the funding that
  triggered it.
- Funding: every settlement in the funding file (also off-grid prints) is a
  cash flow ``+Q * P * F(tau) * funding_mult`` for the short perp (shorts
  receive when ``F > 0``). ``P`` is the perp open at ``tau`` (exact when
  ``tau`` is a bar boundary, the bar close otherwise).
- Cost of a cycle: four legs, ``2 x spot_fee`` (0.10 %) + ``2 x fut_taker``
  (0.05 %), each with its own slippage (volume tier of the leg's market,
  widened by the ATR ratio, PLAN §5.4), all scaled by ``cost_mult``.
- Basis drift: the price P&L of the two legs at reference (unslipped) prices,
  ``Q * [(S_exit - S_entry) - (P_exit - P_entry)]``, is booked as it is: the
  hedge is not assumed perfect.

Sizing (PLAN §2.7): at most ``max_symbol`` (20 %) of NAV of capital per symbol,
``max_symbols`` (5) cycles and ``max_total`` (70 %) of NAV in carry. The
capital of a cycle is the spot purchase plus the isolated margin of the short
(``Q * P / L``). ``L`` is the largest leverage <= ``short_leverage`` (1x) whose
isolated liquidation price is at least ``1 + squeeze_move`` (+100 %) above the
entry (``engine.liquidation.liq_price``; about 0.98x with MMR = 1 %).
Candidates are ranked by APR. If the perp's high ever reaches the liquidation
price the short is liquidated and the spot leg is sold at the bar's close
(``liquidations`` counter). As on Binance isolated margin, the short loses its
whole isolated margin ``Q * P_fill / L``: the perp exit is booked at the
bankruptcy price ``P_fill * (1 + 1/L)``, the gap between it and the liquidation
price is the liquidation clearance fee (booked as commission) and the
``cycles`` table carries the margin lost in ``liquidation_loss``.

Universe: BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT. BNBUSDT is never
used (anomalous funding, PLAN §5.2.2): passing it raises :class:`CarryError`.

The P&L is UNVERIFIED until the local funding has been checked against
``/fapi/v1/fundingRate`` and ``/fapi/v1/fundingInfo`` (PLAN §2.7, §8); the
result's ``meta`` says so. Any missing price while a cycle is open raises
(no imputation).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.config import git_sha
from apps.research.engine.costs import CostModel, commission, slipped_price
from apps.research.engine.event_bt import merge_daily_asof
from apps.research.engine.liquidation import DEFAULT_MMR, liq_price
from apps.research.engine.portfolio_bt import BTResult, _ts, daily_inputs, provenance, resolve_slip
from apps.research.features.funding import SETTLEMENT_STEP, apr, f_bar_3d, settlement_grid

__all__ = [
    "CarryError",
    "CarryConfig",
    "CARRY_CONFIGS",
    "CARRY_UNIVERSE",
    "CARRY_EXCLUDED",
    "UNVERIFIED_WARNING",
    "TF_4H",
    "CarryStrategy",
    "make_carry",
    "carry_leverage",
    "carry_inputs",
    "daily_from_4h",
    "load_carry_data",
    "run_carry_bt",
]

TF_4H = pd.Timedelta(hours=4)
ONE_DAY = pd.Timedelta(days=1)
CARRY_UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
                  "AVAXUSDT", "LINKUSDT", "DOTUSDT")
CARRY_EXCLUDED = frozenset({"BNBUSDT"})
UNVERIFIED_WARNING = ("unverified P&L: local funding not checked against /fapi/v1/fundingRate and "
                      "/fapi/v1/fundingInfo (PLAN §2.7, §8)")
CYCLE_COLUMNS = ["symbol", "entry_time", "exit_time", "qty", "leverage", "spot_entry", "perp_entry",
                 "spot_exit", "perp_exit", "funding", "basis_pnl", "commission", "slippage", "net",
                 "exit_reason", "liquidation_loss"]
TRADE_COLUMNS = ["time", "symbol", "leg", "qty", "ref_price", "price", "notional", "commission",
                 "slippage", "reason"]
LEDGER_COLUMNS = ["commission", "slippage", "funding"]


class CarryError(ValueError):
    """CARRY cannot run without imputing data or breaking a rule."""


@dataclass(frozen=True)
class CarryConfig:
    """One CARRY configuration (thresholds in APR, fractions of NAV)."""

    name: str
    theta_in: float
    theta_out: float
    basis_exit: float = -0.002
    max_symbol: float = 0.20
    max_symbols: int = 5
    max_total: float = 0.70
    short_leverage: float = 1.0
    squeeze_move: float = 1.0
    mmr: float = DEFAULT_MMR
    min_capital: float = 0.01

    def __post_init__(self) -> None:
        for k in ("theta_in", "theta_out", "max_symbol", "max_total", "short_leverage", "squeeze_move",
                  "min_capital"):
            v = getattr(self, k)
            if not math.isfinite(v) or v <= 0:
                raise CarryError(f"{k} must be finite and > 0, got {v!r}")
        if self.theta_out >= self.theta_in:
            raise CarryError("theta_out must be below theta_in (hysteresis)")
        if self.max_symbol > self.max_total or self.max_total > 1.0:
            raise CarryError("need max_symbol <= max_total <= 1")
        if self.short_leverage > 1.0:
            raise CarryError("the carry short runs at L <= 1 (PLAN §2.7)")
        if not isinstance(self.max_symbols, int) or self.max_symbols < 1:
            raise CarryError("max_symbols must be a positive int")
        if not math.isfinite(self.basis_exit):
            raise CarryError("basis_exit must be finite")


CARRY_CONFIGS: dict[str, CarryConfig] = {
    "K1": CarryConfig("K1", theta_in=0.25, theta_out=0.08),
    "K2": CarryConfig("K2", theta_in=0.20, theta_out=0.05),
    "K3": CarryConfig("K3", theta_in=0.35, theta_out=0.10),
}


def carry_leverage(cfg: CarryConfig) -> float:
    """
    Largest leverage ``<= cfg.short_leverage`` whose isolated short liquidation
    price is at least ``(1 + squeeze_move) * entry``:
    ``(1 + 1/L) / (1 + MMR) >= 1 + m``  <=>  ``L <= 1 / ((1 + m)(1 + MMR) - 1)``.
    """
    bound = 1.0 / ((1.0 + cfg.squeeze_move) * (1.0 + cfg.mmr) - 1.0)
    lev = min(cfg.short_leverage, bound)
    if liq_price(1.0, lev, -1, cfg.mmr) < 1.0 + cfg.squeeze_move - 1e-9:
        raise CarryError("short leverage does not survive the required squeeze")
    return lev


class CarryStrategy:
    """Entry / exit rules of one CARRY configuration (sizing lives in :func:`run_carry_bt`)."""

    n_free_params = 2

    def __init__(self, config: CarryConfig | str = "K1"):
        self.config = CARRY_CONFIGS[config] if isinstance(config, str) else config
        self.name = f"CARRY-{self.config.name}"
        self.params = {"theta_in": self.config.theta_in, "theta_out": self.config.theta_out}

    def entry_ok(self, inputs: pd.DataFrame) -> pd.Series:
        """True at the settlements where a new cycle may open (NaN inputs -> False)."""
        c = self.config
        ok = (inputs["apr_3d"] >= c.theta_in) & (inputs["f_last"] > 0)
        return (ok & ~self.exit_now(inputs) & inputs["basis"].notna()).fillna(False).astype(bool)

    def exit_now(self, inputs: pd.DataFrame) -> pd.Series:
        """True at the settlements where an open cycle must close (NaN inputs -> False)."""
        c = self.config
        return ((inputs["apr_3d"] < c.theta_out) | (inputs["basis"] < c.basis_exit)).fillna(False).astype(bool)


def make_carry(config: str = "K1", **overrides) -> CarryStrategy:
    """CARRY strategy for ``K1``/``K2``/``K3`` with optional field overrides (debug only)."""
    base = CARRY_CONFIGS[config]
    cfg = CarryConfig(**{**asdict(base), **overrides}) if overrides else base
    return CarryStrategy(cfg)


# --------------------------------------------------------------------------- inputs
def _check_symbol(symbol: str) -> None:
    if symbol in CARRY_EXCLUDED:
        raise CarryError(f"{symbol} is excluded from CARRY (anomalous funding, PLAN §5.2.2)")


def _check_4h(df: pd.DataFrame, what: str) -> None:
    if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_monotonic_increasing:
        raise CarryError(f"{what}: index must be a sorted DatetimeIndex")
    if df.index.has_duplicates:
        raise CarryError(f"{what}: duplicated bars")
    if df.attrs.get("tf") not in (None, "4h"):
        raise CarryError(f"{what}: CARRY needs 4h bars, got {df.attrs.get('tf')}")
    epoch = pd.Timestamp(0, tz=df.index.tz)
    if (((df.index - epoch) % TF_4H) != pd.Timedelta(0)).any():
        raise CarryError(f"{what}: bars are not on the 4h UTC grid")
    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise CarryError(f"{what}: missing columns {sorted(missing)}")


def carry_inputs(spot: pd.DataFrame, perp: pd.DataFrame, funding: pd.Series) -> pd.DataFrame:
    """
    Signal inputs at every settlement ``tau`` of the 8h grid (00/08/16 UTC) that
    closes a 4h bar present in both markets. Index = ``tau``; columns
    ``spot_close, perp_close, basis, f_last, f_bar_3d, apr_3d``. Every value
    uses only data available at ``tau``; nothing is filled.
    """
    _check_symbol(funding.attrs.get("symbol", ""))
    _check_4h(spot, "spot")
    _check_4h(perp, "perp")
    labels = spot.index.union(perp.index)
    closes = labels + TF_4H
    epoch = pd.Timestamp(0, tz=labels.tz)
    on_grid = ((closes - epoch) % SETTLEMENT_STEP) == pd.Timedelta(0)
    labels, closes = labels[on_grid], closes[on_grid]
    c_spot = spot["close"].reindex(labels).astype(float).to_numpy()
    c_perp = perp["close"].reindex(labels).astype(float).to_numpy()
    grid = settlement_grid(funding)
    fb = f_bar_3d(funding)
    out = pd.DataFrame(
        {
            "spot_close": c_spot,
            "perp_close": c_perp,
            "basis": c_perp / c_spot - 1.0,
            "f_last": grid.reindex(closes).to_numpy(),
            "f_bar_3d": fb.reindex(closes).to_numpy(),
        },
        index=pd.DatetimeIndex(closes, name="settlement_time"),
    )
    out["basis"] = out["basis"].replace([np.inf, -np.inf], np.nan)
    out["apr_3d"] = apr(out["f_bar_3d"])
    out.attrs = {"symbol": funding.attrs.get("symbol"), "funding_verified": False}
    return out


def daily_from_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1d bars from 4h bars (UTC days); a day missing any of its 6 bars is NaN."""
    agg = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    qv = df["quote_volume"] if "quote_volume" in df else df["volume"] * df["close"]
    agg["quote_volume"] = qv.resample("1D").sum(min_count=6)
    complete = df["close"].resample("1D").count() == 6
    agg.loc[~complete.reindex(agg.index, fill_value=False)] = np.nan
    return agg


def _exec_inputs(df: pd.DataFrame, times: pd.DatetimeIndex) -> pd.DataFrame:
    """Slippage inputs known at ``open[t]``: daily bars with ``D + 1 day <= t`` only."""
    extra = daily_inputs(daily_from_4h(df))
    return merge_daily_asof(pd.DataFrame(index=times), extra, pd.Timedelta(0), prefix="")


def load_carry_data(symbols=CARRY_UNIVERSE, start: Optional[str] = None, end: Optional[str] = None,
                    root=None) -> tuple[dict, dict, dict]:
    """Spot 4h, perp 4h and funding of ``symbols`` from the local data (BNBUSDT raises)."""
    from apps.research.data.loader import load_funding, load_ohlcv

    spot, perp, fund = {}, {}, {}
    for s in symbols:
        _check_symbol(s)
        spot[s] = load_ohlcv(s, "spot", "4h", start, end, root)
        perp[s] = load_ohlcv(s, "futures", "4h", start, end, root)
        fund[s] = load_funding(s, root=root)
    return spot, perp, fund


# --------------------------------------------------------------------------- simulator
@dataclass
class _Cycle:
    symbol: str
    qty: float
    lev: float
    entry_time: pd.Timestamp
    spot_ref: float
    perp_ref: float
    spot_fill: float
    perp_fill: float
    margin: float
    liq: float
    funding: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float, np.floating)) and math.isfinite(x)


def run_carry_bt(
    strategy: CarryStrategy,
    spot: Mapping[str, pd.DataFrame],
    perp: Mapping[str, pd.DataFrame],
    funding: Mapping[str, pd.Series],
    cost: CostModel,
    start=None,
    end=None,
    *,
    initial_equity: float = 10_000.0,
    fixed_slip_bps: Optional[float] = None,
    trial_id: Optional[str] = None,
) -> BTResult:
    """
    Paper simulation of one CARRY configuration (see the module docstring).

    ``spot`` / ``perp``: 4h OHLCV per symbol (loader format); ``funding``:
    settlement series per symbol (fraction). Returns a :class:`BTResult` with
    ``equity`` per 4h bar, daily ``returns`` (NAV at each UTC day close),
    ``weights`` (spot notional / NAV; the perp is the same quantity short),
    ``trades`` (one row per leg), ``costs`` (commission, slippage and funding
    per bar and symbol) and ``meta`` with the ``cycles`` table, the P&L
    breakdown (funding, basis drift, commission, slippage) and the
    unverified-funding warning.
    """
    cfg = strategy.config
    symbols = list(spot)
    if not symbols:
        raise CarryError("empty universe")
    for s in symbols:
        _check_symbol(s)
        if s not in perp or s not in funding:
            raise CarryError(f"{s}: CARRY needs spot, perp and funding data")
        _check_4h(spot[s], f"spot/{s}")
        _check_4h(perp[s], f"perp/{s}")
    if not _finite(initial_equity) or initial_equity <= 0:
        raise CarryError("initial_equity must be > 0")
    lev = carry_leverage(cfg)
    fmult = cost.funding_mult

    times = spot[symbols[0]].index
    for s in symbols:
        times = times.union(spot[s].index).union(perp[s].index)
    t0, t1 = _ts(start, times[0]), _ts(end, times[-1])
    times = times[(times >= t0) & (times <= t1)]
    if len(times) < 2:
        raise CarryError(f"need at least 2 bars in [{t0}, {t1}]")

    def mat(src: Mapping[str, pd.DataFrame], col: str) -> np.ndarray:
        return pd.DataFrame({s: src[s][col].reindex(times) for s in symbols}).astype(float).to_numpy()

    SO, SC = mat(spot, "open"), mat(spot, "close")
    PO, PH, PC = mat(perp, "open"), mat(perp, "high"), mat(perp, "close")
    inputs = {s: carry_inputs(spot[s], perp[s], funding[s]) for s in symbols}
    entry_ok = {s: strategy.entry_ok(inputs[s]) for s in symbols}
    exit_now = {s: strategy.exit_now(inputs[s]) for s in symbols}
    ex_spot = {s: _exec_inputs(spot[s], times) for s in symbols}
    ex_perp = {s: _exec_inputs(perp[s], times) for s in symbols}
    fund_rows = {}
    for s in symbols:
        f = funding[s].sort_index()
        f = f[(f.index >= times[0]) & (f.index < times[-1] + TF_4H)]
        fund_rows[s] = list(zip(f.index, f.to_numpy(dtype=float)))
    fptr = dict.fromkeys(symbols, 0)
    col = {s: i for i, s in enumerate(symbols)}

    cash = float(initial_equity)
    cycles: dict[str, _Cycle] = {}
    done: list[tuple] = []
    trades: list[tuple] = []
    ledger: dict[tuple, list[float]] = {}
    pending: list[tuple[str, str]] = []           # (action, symbol) decided at the last close
    counters = {"entries": 0, "exits": 0, "liquidations": 0, "skipped_capacity": 0,
                "skipped_untradable": 0, "skipped_missing_price": 0, "settlements_evaluated": 0}
    eq_vals, w_rows = [], []

    def led(t, s) -> list[float]:
        return ledger.setdefault((t, s), [0.0, 0.0, 0.0])

    def leg_fill(t, s, leg: str, delta: float, ref: float, slip: float, reason: str) -> tuple[float, float, float]:
        market = "spot" if leg == "spot" else "futures"
        side = 1 if delta > 0 else -1
        price = slipped_price(ref, side, slip)
        fee = commission(delta * price, market, cost)
        slip_cost = abs(delta) * abs(price - ref)
        row = led(t, s)
        row[0] += fee
        row[1] += slip_cost
        trades.append((t, s, leg, delta, ref, price, delta * price, fee, slip_cost, reason))
        return price, fee, slip_cost

    def mark(i: int, prices_spot, prices_perp) -> float:
        nav = cash
        for s, c in cycles.items():
            ps, pp = prices_spot[col[s]], prices_perp[col[s]]
            if not (_finite(ps) and _finite(pp)):
                raise CarryError(f"{s}: missing price at {times[i]} with an open cycle (no imputation)")
            nav += c.qty * ps - c.qty * (pp - c.perp_fill)
        return nav

    def close_cycle(t, s, spot_ref: float, perp_ref: float, reason: str, liquidated: bool = False) -> None:
        nonlocal cash
        c = cycles.pop(s)
        side_slip = resolve_slip(s, t, ex_spot[s].loc[t].to_dict(), cost, fixed_slip_bps, exit_only=True)
        sp, sfee, sslip = leg_fill(t, s, "spot", -c.qty, spot_ref, side_slip, reason)
        cash += c.qty * sp - sfee
        liq_loss = 0.0
        if liquidated:
            # Binance isolated liquidation: the position is taken over at ``perp_ref`` (the
            # liquidation price) and whatever margin is left between it and the bankruptcy
            # price ``perp_fill + margin / qty`` goes to the insurance fund as the
            # liquidation clearance fee. The short therefore loses its WHOLE isolated
            # margin. The fill is booked at the bankruptcy price and the clearance fee
            # (``qty * (bankruptcy - liq)``) as commission; basis drift stays at ``perp_ref``.
            pp = c.perp_fill + c.margin / c.qty
            pfee, pslip = max(c.qty * (pp - perp_ref), 0.0), 0.0
            led(t, s)[0] += pfee
            trades.append((t, s, "perp", c.qty, perp_ref, pp, c.qty * pp, pfee, 0.0, reason))
            liq_loss = c.margin
        else:
            perp_slip = resolve_slip(s, t, ex_perp[s].loc[t].to_dict(), cost, fixed_slip_bps, exit_only=True)
            pp, pfee, pslip = leg_fill(t, s, "perp", c.qty, perp_ref, perp_slip, reason)
        cash += -c.qty * (pp - c.perp_fill) - (0.0 if liquidated else pfee)
        comm = c.commission + sfee + pfee
        slip = c.slippage + sslip + pslip
        basis_pnl = c.qty * ((spot_ref - c.spot_ref) - (perp_ref - c.perp_ref))
        net = c.funding + basis_pnl - comm - slip
        done.append((s, c.entry_time, t, c.qty, c.lev, c.spot_fill, c.perp_fill, sp, pp, c.funding,
                     basis_pnl, comm, slip, net, reason, liq_loss))
        counters["exits"] += 1

    for i, t in enumerate(times):
        so, po = SO[i], PO[i]
        # 1. Settlements at exactly t are paid with the position held before the fills (tau-).
        for s in symbols:
            rows, k = fund_rows[s], fptr[s]
            while k < len(rows) and rows[k][0] <= t:
                tau, rate = rows[k]
                if tau == t and s in cycles:
                    c = cycles[s]
                    p = po[col[s]]
                    if not (_finite(rate) and _finite(p)):
                        raise CarryError(f"{s}: missing funding or perp price at {tau} with an open cycle")
                    flow = c.qty * p * rate * fmult
                    cash += flow
                    c.funding += flow
                    led(t, s)[2] += flow
                k += 1
            fptr[s] = k

        # 2. Decisions taken at the previous close (a settlement) are filled at open[t]: exits first.
        decided, pending = pending, []
        for action, s in decided:
            if action == "exit" and s in cycles:
                ps, pp = so[col[s]], po[col[s]]
                if not (_finite(ps) and _finite(pp)):
                    raise CarryError(f"{s}: missing open at {t} to close the cycle (no imputation)")
                close_cycle(t, s, ps, pp, "signal_exit")
        nav_open = mark(i, so, po) if decided else cash
        used = sum(c.qty * so[col[s]] + c.margin for s, c in cycles.items())
        for action, s in decided:
            if action != "enter" or s in cycles:
                continue
            ps, pp = so[col[s]], po[col[s]]
            if not (_finite(ps) and _finite(pp)):
                counters["skipped_missing_price"] += 1
                continue
            if len(cycles) >= cfg.max_symbols:
                counters["skipped_capacity"] += 1
                continue
            capital = min(cfg.max_symbol * nav_open, cfg.max_total * nav_open - used)
            if capital < cfg.min_capital * nav_open:
                counters["skipped_capacity"] += 1
                continue
            s_slip = resolve_slip(s, t, ex_spot[s].loc[t].to_dict(), cost, fixed_slip_bps)
            p_slip = resolve_slip(s, t, ex_perp[s].loc[t].to_dict(), cost, fixed_slip_bps)
            if s_slip is None or p_slip is None:
                counters["skipped_untradable"] += 1
                continue
            s_est, p_est = slipped_price(ps, 1, s_slip), slipped_price(pp, -1, p_slip)
            # Capital = spot purchase + isolated margin of the short + entry commissions.
            qty = capital / (s_est * (1.0 + cost.fee_rate("spot")) + p_est / lev + p_est * cost.fee_rate("futures"))
            sp, sfee, sslip = leg_fill(t, s, "spot", qty, ps, s_slip, "carry_entry")
            pf, pfee, pslip = leg_fill(t, s, "perp", -qty, pp, p_slip, "carry_entry")
            cash -= qty * sp + sfee + pfee
            margin = qty * pf / lev
            cycles[s] = _Cycle(s, qty, lev, t, ps, pp, sp, pf, margin, liq_price(pf, lev, -1, cfg.mmr),
                               commission=sfee + pfee, slippage=sslip + pslip)
            used += qty * sp + margin
            counters["entries"] += 1

        # 3. Intrabar: off-grid settlements (paid with the new position at the bar close) and liquidation.
        for s in symbols:
            rows, k = fund_rows[s], fptr[s]
            while k < len(rows) and rows[k][0] < t + TF_4H:
                tau, rate = rows[k]
                if s in cycles:
                    c = cycles[s]
                    p = PC[i, col[s]]
                    if not (_finite(rate) and _finite(p)):
                        raise CarryError(f"{s}: missing funding or perp price at {tau} with an open cycle")
                    flow = c.qty * p * rate * fmult
                    cash += flow
                    c.funding += flow
                    led(t, s)[2] += flow
                k += 1
            fptr[s] = k
        for s in list(cycles):
            h = PH[i, col[s]]
            if _finite(h) and h >= cycles[s].liq:
                sc = SC[i, col[s]]
                if not _finite(sc):
                    raise CarryError(f"{s}: missing spot close at {t} after a liquidation")
                close_cycle(t, s, sc, cycles[s].liq, "liquidation", liquidated=True)
                counters["liquidations"] += 1

        # 4. Close: mark to market and, on a settlement close, decide the next fills.
        nav = mark(i, SC[i], PC[i])
        eq_vals.append(nav)
        w_rows.append({s: c.qty * SC[i, col[s]] / nav for s, c in cycles.items()})
        close_t = t + TF_4H
        if i + 1 < len(times) and ((close_t - pd.Timestamp(0, tz=t.tz)) % SETTLEMENT_STEP) == pd.Timedelta(0):
            counters["settlements_evaluated"] += 1
            for s in list(cycles):
                if close_t in exit_now[s].index and exit_now[s].loc[close_t]:
                    pending.append(("exit", s))
            cands = [s for s in symbols if s not in cycles and close_t in entry_ok[s].index
                     and entry_ok[s].loc[close_t]]
            cands.sort(key=lambda s: -float(inputs[s].at[close_t, "apr_3d"]))
            pending.extend(("enter", s) for s in cands)

    equity = pd.Series(eq_vals, index=times, name="equity")
    weights = pd.DataFrame(w_rows, index=times, columns=symbols).fillna(0.0)
    day_close = equity[(equity.index + TF_4H).normalize() == equity.index + TF_4H]
    daily_nav = pd.Series(day_close.to_numpy(), index=(day_close.index + TF_4H - ONE_DAY), name="nav")
    returns = daily_nav.pct_change().dropna().rename("returns")
    trades_df = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    if ledger:
        idx = pd.MultiIndex.from_tuples(list(ledger), names=["date", "symbol"])
        costs = pd.DataFrame(list(ledger.values()), index=idx, columns=LEDGER_COLUMNS).sort_index()
    else:
        costs = pd.DataFrame(columns=LEDGER_COLUMNS, index=pd.MultiIndex.from_tuples([], names=["date", "symbol"]))
    cycles_df = pd.DataFrame(done, columns=CYCLE_COLUMNS)
    last = len(times) - 1
    open_basis = sum(c.qty * ((SC[last, col[s]] - c.spot_ref) - (PC[last, col[s]] - c.perp_ref))
                     for s, c in cycles.items())
    breakdown = {
        "funding": float(cycles_df["funding"].sum() + sum(c.funding for c in cycles.values())),
        "basis_pnl": float(cycles_df["basis_pnl"].sum() + open_basis),
        "commission": float(costs["commission"].sum()) if len(costs) else 0.0,
        "slippage": float(costs["slippage"].sum()) if len(costs) else 0.0,
    }
    breakdown["net"] = breakdown["funding"] + breakdown["basis_pnl"] - breakdown["commission"] - breakdown["slippage"]
    meta = {
        "strategy": strategy.name,
        "params": dict(strategy.params),
        "config": asdict(cfg),
        "market": "spot+futures",
        "paper_only": True,
        "pnl_verified": False,
        "funding_verified": False,
        "warning": UNVERIFIED_WARNING,
        "short_leverage": lev,
        "cost": asdict(cost),
        "fixed_slip_bps": fixed_slip_bps,
        "git_sha": git_sha(),
        "trial_id": trial_id,
        "counters": counters,
        "cycles": cycles_df,
        "open_cycles": sorted(cycles),
        "pnl_breakdown": breakdown,
        "equity_daily": daily_nav,
        **provenance({f"spot/{s}": spot[s] for s in symbols} | {f"perp/{s}": perp[s] for s in symbols},
                     funding),
    }
    return BTResult(equity, returns, weights, trades_df, costs, meta)
