"""
Probability of Backtest Overfitting via Combinatorially Symmetric
Cross-Validation (CSCV), Bailey, Borwein, Lopez de Prado & Zhu (2017),
"The Probability of Backtest Overfitting", J. Computational Finance.

Algorithm (PLAN §5.5, report 07 §2.5):

1. ``M`` is a T x N matrix of per-period (daily) returns of N configurations.
2. The rows are split into S contiguous blocks of equal size (S even).
3. For every combination C of S/2 blocks (C(16, 8) = 12 870 for S = 16):
   IS = blocks in C, OOS = the complementary blocks.
4. ``n*`` = argmax of the IS Sharpe ratio; ``w`` = relative rank of ``n*``
   among the OOS Sharpe ratios, ``rank / (N + 1)`` in (0, 1);
   ``lambda = ln(w / (1 - w))``.
5. PBO = fraction of combinations with ``lambda <= 0`` (the IS winner ends at
   or below the OOS median).

All S/2-combinations are evaluated in closed form from per-block sums, so
S = 16 runs in milliseconds for typical N.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

__all__ = ["CSCVResult", "cscv", "pbo_cscv"]


@dataclass(frozen=True)
class CSCVResult:
    """Full CSCV output; ``pbo`` is the headline number."""

    pbo: float
    logits: np.ndarray        # lambda per combination
    sr_is_best: np.ndarray    # IS Sharpe of the IS winner, per combination
    sr_oos_best: np.ndarray   # OOS Sharpe of the IS winner, per combination
    best_index: np.ndarray    # column index of the IS winner, per combination
    prob_oos_loss: float      # P(SR_OOS of the IS winner < 0)
    degradation_slope: float  # OLS slope of SR_OOS on SR_IS (performance degradation)
    n_combinations: int
    rows_used: int            # rows kept (T truncated to a multiple of S)


def _block_sharpes(cnt: np.ndarray, s1: np.ndarray, s2: np.ndarray) -> np.ndarray:
    """Per-period Sharpe (ddof=1) from counts, sums and sums of squares."""
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = s1 / cnt
        var = (s2 - cnt * mean * mean) / (cnt - 1.0)
        sd = np.sqrt(np.where(var > 0, var, np.nan))
        return mean / sd


def _rank_of(values: np.ndarray, col: np.ndarray) -> np.ndarray:
    """Average rank (1..N, ascending) of ``values[i, col[i]]`` within row i.

    Non-finite values rank lowest (they are treated as -inf).
    """
    v = np.where(np.isfinite(values), values, -np.inf)
    target = v[np.arange(v.shape[0]), col][:, None]
    less = (v < target).sum(axis=1)
    equal = (v == target).sum(axis=1)  # includes the element itself
    return less + (equal + 1) / 2.0


def cscv(M: pd.DataFrame | np.ndarray, S: int = 16) -> CSCVResult:
    """Run CSCV on the T x N return matrix ``M`` and return all diagnostics.

    Rows with any NaN are not allowed: align configurations on a common
    calendar before calling (a flat day is a 0 return, not a NaN). If T is
    not a multiple of S, the OLDEST ``T mod S`` rows are dropped so every
    block has the same length.
    """
    arr = M.to_numpy(dtype=float) if isinstance(M, pd.DataFrame) else np.asarray(M, dtype=float)
    if arr.ndim != 2:
        raise ValueError("M must be a 2-D T x N matrix")
    T, N = arr.shape
    if N < 2:
        raise ValueError("CSCV needs at least 2 configurations")
    if S < 2 or S % 2:
        raise ValueError("S must be an even integer >= 2")
    if not np.isfinite(arr).all():
        raise ValueError("M contains NaN/inf; align the configurations first")
    block_len = T // S
    if block_len < 2:
        raise ValueError(f"T={T} too short for S={S} blocks (need >= {2 * S} rows)")
    arr = arr[T - block_len * S:]

    blocks = arr.reshape(S, block_len, N)
    b_sum = blocks.sum(axis=1)               # S x N
    b_sq = (blocks * blocks).sum(axis=1)     # S x N

    combos = list(combinations(range(S), S // 2))
    sel = np.zeros((len(combos), S))
    for i, c in enumerate(combos):
        sel[i, list(c)] = 1.0

    cnt = float(block_len * (S // 2))
    is_sum, is_sq = sel @ b_sum, sel @ b_sq
    oos_sum, oos_sq = b_sum.sum(axis=0) - is_sum, b_sq.sum(axis=0) - is_sq
    sr_is = _block_sharpes(cnt, is_sum, is_sq)
    sr_oos = _block_sharpes(cnt, oos_sum, oos_sq)

    best = np.argmax(np.where(np.isfinite(sr_is), sr_is, -np.inf), axis=1)
    rows = np.arange(len(combos))
    omega = _rank_of(sr_oos, best) / (N + 1.0)
    logits = np.log(omega / (1.0 - omega))

    sr_is_best = sr_is[rows, best]
    sr_oos_best = sr_oos[rows, best]
    finite = np.isfinite(sr_is_best) & np.isfinite(sr_oos_best)
    if finite.sum() >= 2 and np.var(sr_is_best[finite]) > 0:
        slope = float(np.polyfit(sr_is_best[finite], sr_oos_best[finite], 1)[0])
    else:
        slope = float("nan")

    return CSCVResult(
        pbo=float(np.mean(logits <= 0.0)),
        logits=logits,
        sr_is_best=sr_is_best,
        sr_oos_best=sr_oos_best,
        best_index=best,
        prob_oos_loss=float(np.mean(np.nan_to_num(sr_oos_best, nan=0.0) < 0.0)),
        degradation_slope=slope,
        n_combinations=len(combos),
        rows_used=block_len * S,
    )


def pbo_cscv(M: pd.DataFrame, S: int = 16) -> float:
    """Probability of Backtest Overfitting of the T x N return matrix ``M``."""
    return cscv(M, S=S).pbo
