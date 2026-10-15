"""
BENCH: null benchmarks every candidate must beat (PLAN.md §2.11, §5.5, §5.6 items 3-5).

1. **Vol-matched buy & hold**: BTC and the equal-weight basket of the same
   universe, scaled by ONE constant multiplier so that their realized vol over
   the candidate's OOS dates equals the candidate's
   (:func:`vol_matched_bh`, :func:`vol_matched_benchmarks`).
2. **Random entries (100 seeds)**:

   - Target-weight strategies (TREND and overlays): per symbol, the exposure
     episodes of the candidate (maximal runs of non-zero weight with the same
     sign) are moved to random, non-overlapping start dates inside the
     symbol's life, keeping each episode's duration and weight path
     (:func:`permute_episodes`, :func:`random_weight_paths`). Candidate and
     random paths are evaluated with the same function
     (:func:`weights_returns` by default: close-to-close returns of the
     weights held from the previous close, minus a linear cost on turnover and
     optional funding).
   - Strategies with stops (BRK4H, SHOCK): entries at random bars with the
     same number of entries per symbol (and the same sides) as the candidate,
     with the candidate's own exit rules and the engine's sizing
     (:class:`RandomEntryEventStrategy`, :func:`random_entry_event_test`).

   The candidate must sit above the 95th percentile of the random net Sharpe
   ratios. Seeds are ``seed0, seed0 + 1, ...`` and every draw uses its own
   ``numpy.random.default_rng(seed)``: results are reproducible.

The benchmark is not a trial (PLAN §2.1) and never runs on synthetic prices:
inputs are the candidate's own outputs and the local market data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.engine.portfolio_bt import BTResult, wilder_atr
from apps.research.strategies.base import Context, OrderIntent
from apps.research.validation.stats import sharpe_ratio

__all__ = [
    "BenchmarkError",
    "N_SEEDS",
    "PCTL",
    "Episode",
    "RandomEntryResult",
    "closes_frame",
    "bh_returns",
    "vol_matched_bh",
    "vol_matched_benchmarks",
    "exposure_episodes",
    "permute_episodes",
    "random_weight_paths",
    "weights_returns",
    "random_entry_weights_test",
    "entry_schedule",
    "RandomEntryEventStrategy",
    "random_entry_event_test",
]

N_SEEDS = 100
PCTL = 95.0
PERIODS_PER_YEAR = 365
_EPS = 1e-12


class BenchmarkError(ValueError):
    """A benchmark cannot be built from the given inputs."""


# --------------------------------------------------------------------------- buy & hold
def closes_frame(panel: Mapping[str, pd.DataFrame] | pd.DataFrame) -> pd.DataFrame:
    """Close prices per symbol (columns) from a loader panel or an existing frame."""
    if isinstance(panel, pd.DataFrame):
        return panel.astype(float)
    if not panel:
        raise BenchmarkError("empty panel")
    return pd.DataFrame({s: df["close"] for s, df in panel.items()}).astype(float).sort_index()


def bh_returns(closes: pd.DataFrame | pd.Series) -> pd.Series:
    """
    Buy & hold daily simple returns. A Series is one asset; a DataFrame is the
    equal-weight basket rebalanced every day over the symbols with a return
    that day (a symbol enters the basket after its first two closes). Days
    without any return are NaN (never filled).
    """
    if isinstance(closes, pd.Series):
        return (closes.astype(float) / closes.astype(float).shift(1) - 1.0).rename(closes.name or "bh")
    r = closes.astype(float) / closes.astype(float).shift(1) - 1.0
    return r.mean(axis=1, skipna=True).rename("basket")


def vol_matched_bh(candidate_returns: pd.Series, bench_returns: pd.Series) -> tuple[pd.Series, float]:
    """
    Scale ``bench_returns`` by a constant ``k`` so that its realized vol on the
    candidate's dates equals the candidate's (``k = std(cand) / std(bench)``,
    both on the dates where both are finite). Returns ``(k * bench, k)``
    indexed by those common dates.
    """
    both = pd.concat([candidate_returns.rename("c"), bench_returns.rename("b")], axis=1, join="inner")
    both = both[np.isfinite(both["c"]) & np.isfinite(both["b"])]
    if len(both) < 2:
        raise BenchmarkError("fewer than two common dates between the candidate and the benchmark")
    sd_c, sd_b = both["c"].std(ddof=1), both["b"].std(ddof=1)
    if not (sd_b > 0 and math.isfinite(sd_b)):
        raise BenchmarkError("benchmark returns have zero dispersion")
    k = float(sd_c / sd_b)
    return (both["b"] * k).rename(f"{bench_returns.name or 'bh'}_volmatched"), k


def vol_matched_benchmarks(candidate_returns: pd.Series, panel: Mapping[str, pd.DataFrame] | pd.DataFrame,
                           btc: str = "BTCUSDT") -> dict:
    """
    BTC and equal-weight-basket buy & hold, vol-matched to the candidate.

    Returns ``{"BTC": Series, "basket": Series, "mult": {"BTC": k, "basket": k}}``.
    """
    closes = closes_frame(panel)
    if btc not in closes:
        raise BenchmarkError(f"{btc} is not in the panel")
    btc_r, k_btc = vol_matched_bh(candidate_returns, bh_returns(closes[btc]).rename("BTC"))
    bsk_r, k_bsk = vol_matched_bh(candidate_returns, bh_returns(closes))
    return {"BTC": btc_r, "basket": bsk_r, "mult": {"BTC": k_btc, "basket": k_bsk}}


# --------------------------------------------------------------------------- episodes
@dataclass(frozen=True)
class Episode:
    """A maximal run of non-zero weights with one sign (positions in the index)."""

    start: int
    weights: tuple[float, ...]

    @property
    def length(self) -> int:
        return len(self.weights)

    @property
    def sign(self) -> int:
        return 1 if self.weights[0] > 0 else -1


def exposure_episodes(w: pd.Series | np.ndarray) -> list[Episode]:
    """Episodes of a weight path (NaN counts as flat; a sign flip starts a new episode)."""
    arr = np.nan_to_num(np.asarray(w, dtype=float), nan=0.0)
    sgn = np.sign(np.where(np.abs(arr) > _EPS, arr, 0.0))
    out: list[Episode] = []
    i, n = 0, len(arr)
    while i < n:
        if sgn[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and sgn[j + 1] == sgn[i]:
            j += 1
        out.append(Episode(i, tuple(arr[i:j + 1].tolist())))
        i = j + 1
    return out


def _life_bounds(life: np.ndarray) -> tuple[int, int]:
    idx = np.flatnonzero(life)
    if idx.size == 0:
        return 0, -1
    return int(idx[0]), int(idx[-1])


def permute_episodes(w: pd.Series, life: Optional[pd.Series], rng: np.random.Generator) -> pd.Series:
    """
    Random placement of the episodes of ``w`` inside the symbol's life.

    The life is the span between the first and last True of ``life`` (default:
    the whole index). Episodes keep their duration and weight path, are shuffled,
    never overlap and, when there is room, keep at least one flat bar between
    them (so they are not merged into a longer episode). Placement is uniform
    over the compositions of the free bars.
    """
    n = len(w)
    life_arr = np.ones(n, dtype=bool) if life is None else life.reindex(w.index).fillna(False).to_numpy(bool)
    lo, hi = _life_bounds(life_arr)
    eps = exposure_episodes(w)
    out = np.zeros(n)
    if not eps:
        return pd.Series(out, index=w.index, name=w.name)
    span = hi - lo + 1
    total = sum(e.length for e in eps)
    if total > span:
        raise BenchmarkError(f"{w.name}: episodes ({total} bars) do not fit in the symbol's life ({span} bars)")
    k = len(eps)
    order = rng.permutation(k)
    free = span - total
    min_gap = 1 if free >= k - 1 else 0
    free -= min_gap * (k - 1)
    offsets = np.sort(rng.integers(0, free + 1, size=k))
    pos = lo
    prev_off = 0
    for rank, e_idx in enumerate(order):
        e = eps[e_idx]
        pos += int(offsets[rank] - prev_off)
        prev_off = int(offsets[rank])
        out[pos:pos + e.length] = e.weights
        pos += e.length + min_gap
    return pd.Series(out, index=w.index, name=w.name)


def random_weight_paths(weights: pd.DataFrame, closes: pd.DataFrame, seed: int) -> pd.DataFrame:
    """
    One random draw of the whole weight matrix: every symbol's episodes are
    permuted inside its life (dates with a finite close).
    """
    rng = np.random.default_rng(seed)
    closes = closes.reindex(weights.index)
    out = {}
    for s in weights.columns:
        life = closes[s].notna() if s in closes else pd.Series(True, index=weights.index)
        out[s] = permute_episodes(weights[s].rename(s), life, rng)
    return pd.DataFrame(out, index=weights.index)


def weights_returns(weights: pd.DataFrame, closes: pd.DataFrame, cost_rate: float = 0.0,
                    funding_daily: Optional[pd.DataFrame] = None) -> pd.Series:
    """
    Daily net returns of a weight path: ``sum_i w_i,t-1 * r_i,t
    - cost_rate * sum_i |w_i,t - w_i,t-1| - sum_i w_i,t-1 * F_i,t``.

    ``r`` are close-to-close simple returns (a NaN return contributes 0: no
    price, no P&L), ``cost_rate`` is the one-way cost per unit of turnover
    (fee + slippage) and ``funding_daily`` the sum of the funding rates of the
    settlements of each day (perps; longs pay when positive).
    """
    if not math.isfinite(cost_rate) or cost_rate < 0:
        raise BenchmarkError(f"cost_rate must be finite and >= 0, got {cost_rate!r}")
    w = weights.astype(float).fillna(0.0)
    r = (closes.reindex(index=w.index, columns=w.columns).astype(float)
         .pipe(lambda c: c / c.shift(1) - 1.0)).fillna(0.0)
    held = w.shift(1).fillna(0.0)
    pnl = (held * r).sum(axis=1)
    turnover = w.diff().abs().fillna(w.abs()).sum(axis=1)
    out = pnl - cost_rate * turnover
    if funding_daily is not None:
        f = funding_daily.reindex(index=w.index, columns=w.columns).astype(float).fillna(0.0)
        out = out - (held * f).sum(axis=1)
    return out.rename("returns")


@dataclass
class RandomEntryResult:
    """Distribution of random-entry Sharpe ratios and where the candidate falls."""

    sharpes: np.ndarray
    candidate_sharpe: float
    seeds: list[int]
    pctl: float = PCTL
    extra: dict = field(default_factory=dict)

    @property
    def threshold(self) -> float:
        """The ``pctl`` percentile of the random Sharpes (NaN draws dropped)."""
        s = self.sharpes[np.isfinite(self.sharpes)]
        return float(np.percentile(s, self.pctl)) if s.size else float("nan")

    @property
    def percentile(self) -> float:
        """Share (0-100) of random Sharpes strictly below the candidate."""
        s = self.sharpes[np.isfinite(self.sharpes)]
        return float(100.0 * np.mean(s < self.candidate_sharpe)) if s.size else float("nan")

    @property
    def passed(self) -> bool:
        """True when the candidate is above the ``pctl`` percentile (PLAN §5.6 item 3)."""
        return bool(math.isfinite(self.candidate_sharpe) and self.candidate_sharpe > self.threshold)


def _sharpe(returns) -> float:
    return sharpe_ratio(np.asarray(returns, dtype=float), periods_per_year=PERIODS_PER_YEAR)


def random_entry_weights_test(
    weights: pd.DataFrame,
    closes: pd.DataFrame,
    n_seeds: int = N_SEEDS,
    seed0: int = 0,
    cost_rate: float = 0.0,
    funding_daily: Optional[pd.DataFrame] = None,
    evaluator: Optional[Callable[[pd.DataFrame], pd.Series]] = None,
) -> RandomEntryResult:
    """
    Random-entry benchmark for target-weight strategies.

    ``weights``: the candidate's weights (e.g. ``BTResult.weights``, signed
    notional / NAV at each close). The candidate and every permuted path are
    evaluated with ``evaluator`` (default :func:`weights_returns` with
    ``cost_rate`` and ``funding_daily``), so the comparison is like-for-like.
    """
    if n_seeds < 1:
        raise BenchmarkError("n_seeds must be >= 1")
    closes = closes.reindex(weights.index)
    if evaluator is None:
        def evaluator(w: pd.DataFrame) -> pd.Series:
            return weights_returns(w, closes, cost_rate, funding_daily)
    seeds = list(range(seed0, seed0 + n_seeds))
    sharpes = np.array([_sharpe(evaluator(random_weight_paths(weights, closes, sd))) for sd in seeds])
    return RandomEntryResult(sharpes, _sharpe(evaluator(weights.fillna(0.0))), seeds)


# --------------------------------------------------------------------------- event strategies
def _round_trips(result: BTResult | pd.DataFrame) -> pd.DataFrame:
    rt = result.meta.get("round_trips") if isinstance(result, BTResult) else result
    if rt is None:
        raise BenchmarkError("the candidate result has no round_trips (run it with run_event_bt)")
    return rt


def entry_schedule(round_trips: pd.DataFrame, panel: Mapping[str, pd.DataFrame], rng: np.random.Generator,
                   start=None, end=None) -> dict[str, dict[pd.Timestamp, int]]:
    """
    Random decision bars with the candidate's entry count and sides per symbol.

    One entry is a distinct ``(symbol, entry_time)`` of the round trips
    (partial exits are not extra entries). For each symbol, that many bars are
    drawn without replacement among the bars of its life (finite close, inside
    ``[start, end]``, excluding the last bar, which cannot be filled), and the
    candidate's sides are shuffled onto them. Returns ``{symbol: {t: side}}``.
    """
    entries = round_trips.drop_duplicates(["symbol", "entry_time"])
    out: dict[str, dict[pd.Timestamp, int]] = {}
    for s in panel:
        sides = entries.loc[entries["symbol"] == s, "side"].astype(int).to_numpy()
        if sides.size == 0:
            out[s] = {}
            continue
        df = panel[s]
        idx = df.index[df["close"].notna().to_numpy()]
        if start is not None:
            idx = idx[idx >= pd.Timestamp(start)]
        if end is not None:
            idx = idx[idx <= pd.Timestamp(end)]
        idx = idx[idx < df.index[-1]]
        if len(idx) < sides.size:
            raise BenchmarkError(f"{s}: {sides.size} entries do not fit in {len(idx)} bars")
        picks = np.sort(rng.choice(len(idx), size=sides.size, replace=False))
        out[s] = dict(zip(idx[picks], rng.permutation(sides).tolist()))
    return out


class RandomEntryEventStrategy:
    """
    Wraps a candidate :class:`EventStrategy`: entries happen only at the
    scheduled random bars, exits and stop updates are the candidate's.

    - Entries: ``candidate.make_entry(symbol, side, t, bars, ctx)`` when the
      candidate defines it (its own stop and sizing rules); otherwise a market
      entry with a stop at ``close -/+ stop_atr_mult * ATR14`` of the bars seen
      so far (``stop_atr_mult`` from ``candidate.params``, default 2) and the
      engine's risk sizing.
    - Management: ``candidate.manage(t, bars, ctx)`` when defined; otherwise
      the candidate's ``on_bar`` output restricted to reduce-only intents for
      symbols with an open position (its exits must therefore depend on
      ``ctx.positions``, as BRK4H and SHOCK do).
    """

    def __init__(self, candidate, schedule: Mapping[str, Mapping[pd.Timestamp, int]]):
        self.candidate = candidate
        self.schedule = {s: dict(v) for s, v in schedule.items()}
        self.name = f"RANDOM[{getattr(candidate, 'name', 'candidate')}]"
        self.params = dict(getattr(candidate, "params", {}) or {})
        self.n_free_params = 0
        self.entries_requested = 0

    def _default_entry(self, symbol: str, side: int, ctx: Context) -> Optional[OrderIntent]:
        hist = ctx.history(symbol)
        if len(hist) < 15:
            return None
        atr = wilder_atr(hist.iloc[-200:], 14).iloc[-1]
        close = float(hist["close"].iloc[-1])
        if not (math.isfinite(atr) and atr > 0 and math.isfinite(close)):
            return None
        mult = float(self.params.get("stop_atr_mult", 2.0))
        stop = close - side * mult * atr
        if stop <= 0:
            return None
        return OrderIntent(symbol, "BUY" if side == 1 else "SELL", stop_price=stop, tag="random_entry")

    def on_bar(self, t, bars: dict[str, pd.Series], ctx: Context) -> list[OrderIntent]:
        held = set(ctx.positions)
        if hasattr(self.candidate, "manage"):
            intents = list(self.candidate.manage(t, bars, ctx))
        else:
            intents = [it for it in self.candidate.on_bar(t, bars, ctx)
                       if it.reduce_only and it.symbol in held]
        for s, plan in self.schedule.items():
            side = plan.get(t)
            if side is None or s not in bars or s in held:
                continue
            self.entries_requested += 1
            if hasattr(self.candidate, "make_entry"):
                it = self.candidate.make_entry(s, side, t, bars, ctx)
            else:
                it = self._default_entry(s, side, ctx)
            if it is not None:
                intents.append(it)
        return intents


def random_entry_event_test(
    make_candidate: Callable[[], object],
    candidate_result: BTResult,
    run: Callable[[object], BTResult],
    panel: Mapping[str, pd.DataFrame],
    n_seeds: int = N_SEEDS,
    seed0: int = 0,
    start=None,
    end=None,
) -> RandomEntryResult:
    """
    Random-entry benchmark for strategies with stops.

    ``make_candidate()`` builds a fresh candidate (its internal state must not
    leak between seeds), ``run(strategy)`` runs the SAME engine configuration
    used for the candidate (e.g. a ``functools.partial`` of
    :func:`apps.research.engine.event_bt.run_event_bt`) and ``panel`` is the
    intraday panel. The candidate's Sharpe is taken from ``candidate_result``.
    """
    if n_seeds < 1:
        raise BenchmarkError("n_seeds must be >= 1")
    rt = _round_trips(candidate_result)
    seeds = list(range(seed0, seed0 + n_seeds))
    sharpes, requested, realized = [], [], []
    for sd in seeds:
        rng = np.random.default_rng(sd)
        sched = entry_schedule(rt, panel, rng, start, end)
        strat = RandomEntryEventStrategy(make_candidate(), sched)
        res = run(strat)
        sharpes.append(_sharpe(res.returns))
        requested.append(strat.entries_requested)
        realized.append(int(res.meta.get("counters", {}).get("entries", -1)))
    n_entries = int(rt.drop_duplicates(["symbol", "entry_time"]).shape[0]) if len(rt) else 0
    return RandomEntryResult(np.array(sharpes), _sharpe(candidate_result.returns), seeds,
                             extra={"candidate_entries": n_entries, "entries_requested": requested,
                                    "entries_realized": realized})
