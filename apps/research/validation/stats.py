"""
Statistical validation helpers for the research harness.

Implements the formulas of PLAN.md §5.5 / report 07 §2.5:

- Sharpe ratio, its standard error under non-normal returns (Mertens 2002,
  Lo 2002, Opdyke 2007).
- Probabilistic Sharpe Ratio, PSR (Bailey & Lopez de Prado 2012,
  "The Sharpe Ratio Efficient Frontier").
- Expected maximum of N standard normal draws and the Deflated Sharpe Ratio,
  DSR (Bailey & Lopez de Prado 2014, "The Deflated Sharpe Ratio").
- Minimum Backtest Length, MinBTL (Bailey, Borwein, Lopez de Prado & Zhu 2014,
  "Pseudo-Mathematics and Financial Charlatanism").
- Stationary bootstrap (Politis & Romano 1994) and a one-sided bootstrap test
  of a paired difference.
- Holm step-down correction for multiple hypotheses (Holm 1979).

Conventions (they matter, the formulas are frequency dependent):

- ``sr`` passed to ``psr``/``dsr``/``sharpe_se`` is the Sharpe ratio per
  observation (NOT annualised), measured on the same frequency as ``T``.
- ``kurt`` is the plain kurtosis (normal = 3), NOT the excess kurtosis.
- ``sr_trials_var`` in ``dsr`` is the variance of the per-observation Sharpe
  ratios of all the trials recorded in the trials log.

Only the standard library and numpy are required; the normal distribution
comes from ``statistics.NormalDist`` so the module has no scipy dependency.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Callable, Sequence

import numpy as np

EULER_GAMMA = 0.5772156649015329
_NORM = NormalDist()

__all__ = [
    "EULER_GAMMA",
    "sharpe_ratio",
    "annualize_sharpe",
    "deannualize_sharpe",
    "moments",
    "sharpe_se",
    "psr",
    "expected_max_z",
    "expected_max_sharpe",
    "dsr",
    "min_btl",
    "min_track_record",
    "stationary_bootstrap",
    "bootstrap_ci",
    "bootstrap_pvalue_diff",
    "holm",
]


# --------------------------------------------------------------------------- #
# Sharpe ratio and moments
# --------------------------------------------------------------------------- #
def _clean(x) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    return arr[np.isfinite(arr)]


def sharpe_ratio(returns, periods_per_year: float | None = None) -> float:
    """Sharpe ratio ``mean / std(ddof=1)`` of per-period returns (NaN dropped).

    With ``periods_per_year`` (365 for daily crypto) the result is annualised
    with sqrt(K); otherwise it is per observation. Returns NaN when the sample
    has fewer than two observations or zero dispersion.
    """
    r = _clean(returns)
    if r.size < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if not sd > 0:
        return float("nan")
    sr = float(r.mean() / sd)
    if periods_per_year is not None:
        sr *= math.sqrt(periods_per_year)
    return sr


def annualize_sharpe(sr: float, periods_per_year: float = 365.0) -> float:
    """Per-period Sharpe -> annual Sharpe (sqrt-time rule, no autocorrelation)."""
    return float(sr) * math.sqrt(periods_per_year)


def deannualize_sharpe(sr_annual: float, periods_per_year: float = 365.0) -> float:
    """Annual Sharpe -> per-period Sharpe."""
    return float(sr_annual) / math.sqrt(periods_per_year)


def moments(returns) -> tuple[float, float]:
    """Sample skewness and plain (non-excess) kurtosis of ``returns``.

    Population (biased) moment estimators, as used by Bailey & Lopez de Prado.
    A normal sample gives approximately (0, 3).
    """
    r = _clean(returns)
    if r.size < 3:
        raise ValueError("at least 3 finite observations are required")
    d = r - r.mean()
    m2 = np.mean(d**2)
    if not m2 > 0:
        raise ValueError("returns have zero variance")
    skew = float(np.mean(d**3) / m2**1.5)
    kurt = float(np.mean(d**4) / m2**2)
    return skew, kurt


def _sr_variance_factor(sr: float, skew: float, kurt: float) -> float:
    """``1 - g3*SR + (g4 - 1)/4 * SR^2``; guarded to stay positive."""
    v = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if not v > 0:
        raise ValueError(
            f"non-positive Sharpe variance factor ({v:.4g}); check skew/kurt "
            "(kurt must be the plain kurtosis, normal = 3)"
        )
    return v


def sharpe_se(sr: float, T: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Standard error of the per-period Sharpe ratio estimator.

    ``SE = sqrt((1 - g3*SR + (g4 - 1)/4 * SR^2) / T)`` (Mertens 2002); with
    normal returns (g3=0, g4=3) it reduces to Lo's ``sqrt((1 + SR^2/2)/T)``.
    ``sr`` is per period and the result is per period too: multiply by
    sqrt(K) to express it in annual units.
    """
    if T < 2:
        raise ValueError("T must be >= 2")
    return math.sqrt(_sr_variance_factor(sr, skew, kurt) / T)


# --------------------------------------------------------------------------- #
# PSR / DSR / MinBTL
# --------------------------------------------------------------------------- #
def psr(sr: float, T: int, skew: float, kurt: float, sr_star: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio.

    ``PSR(SR*) = Phi((SR - SR*) * sqrt(T - 1) / sqrt(1 - g3*SR + (g4-1)/4*SR^2))``

    Probability that the true Sharpe exceeds ``sr_star``. ``sr`` and
    ``sr_star`` are per observation, ``T`` the number of observations.
    """
    if T < 2:
        raise ValueError("T must be >= 2")
    z = (sr - sr_star) * math.sqrt(T - 1) / math.sqrt(_sr_variance_factor(sr, skew, kurt))
    return float(_NORM.cdf(z))


def expected_max_z(n_trials: int) -> float:
    """Approximate E[max] of ``n_trials`` i.i.d. standard normals.

    ``(1 - g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N e))`` with g the
    Euler-Mascheroni constant (Bailey & Lopez de Prado 2014). Reference
    values: N=10 -> 1.57, N=36 -> 2.15, N=100 -> 2.53. ``N = 1`` -> 0.
    """
    n = int(n_trials)
    if n < 1:
        raise ValueError("n_trials must be >= 1")
    if n == 1:
        return 0.0
    return float(
        (1.0 - EULER_GAMMA) * _NORM.inv_cdf(1.0 - 1.0 / n)
        + EULER_GAMMA * _NORM.inv_cdf(1.0 - 1.0 / (n * math.e))
    )


def expected_max_sharpe(n_trials: int, sr_trials_var: float, sr_mean: float = 0.0) -> float:
    """Expected maximum Sharpe among ``n_trials`` trials whose true SR is ``sr_mean``.

    ``SR0 = sr_mean + sqrt(V[SR_n]) * E[max Z_N]``. This is the rejection
    threshold the DSR deflates against. Units follow ``sr_trials_var``.
    """
    if sr_trials_var < 0:
        raise ValueError("sr_trials_var must be >= 0")
    return float(sr_mean + math.sqrt(sr_trials_var) * expected_max_z(n_trials))


def dsr(sr: float, T: int, skew: float, kurt: float, sr_trials_var: float, n_trials: int) -> float:
    """Deflated Sharpe Ratio: ``PSR(SR0)`` with ``SR0 = expected_max_sharpe``.

    ``sr`` is the selected (best) per-observation Sharpe; ``sr_trials_var`` is
    the variance of the per-observation Sharpes of ALL trials and
    ``n_trials`` the number of (effective) independent trials, i.e.
    ``TrialsLog.n_total()``.

    Reference (Bailey & Lopez de Prado 2014): annual SR 2.5, T = 1250 daily
    obs, skew -3, kurt 10, N = 100, V[SR annual] = 0.5 -> DSR ~ 0.90.
    """
    sr0 = expected_max_sharpe(n_trials, sr_trials_var)
    return psr(sr, T, skew, kurt, sr_star=sr0)


def min_btl(n_trials: int, target_sr: float) -> float:
    """Minimum Backtest Length in years (Bailey, Borwein, Lopez de Prado & Zhu 2014).

    ``MinBTL = (E[max Z_N] / SR_target)^2``, i.e. the number of years below
    which ``n_trials`` skill-less configurations are expected to produce a
    best in-sample ANNUAL Sharpe of at least ``target_sr``. It is bounded by
    ``2 ln(N) / SR_target^2``. Example from the paper: N = 45, SR = 1 ->
    ~5 years.
    """
    if target_sr <= 0:
        raise ValueError("target_sr must be > 0")
    return float((expected_max_z(n_trials) / target_sr) ** 2)


def min_track_record(sr: float, skew: float = 0.0, kurt: float = 3.0,
                     sr_star: float = 0.0, z: float = 3.0) -> float:
    """Observations needed for ``(SR - SR*)/SE >= z`` (PLAN §5.6 point 10).

    ``n >= (z / (SR - SR*))^2 * (1 - g3*SR + (g4-1)/4*SR^2)``; ``sr`` per
    observation (per trade for trade-based strategies). Returns +inf when
    ``sr <= sr_star``. With ``z = Phi^-1(0.95)`` it is the MinTRL of Bailey &
    Lopez de Prado (up to the ``+1``).
    """
    if sr <= sr_star:
        return float("inf")
    return float((z / (sr - sr_star)) ** 2 * _sr_variance_factor(sr, skew, kurt))


# --------------------------------------------------------------------------- #
# Stationary bootstrap
# --------------------------------------------------------------------------- #
def _stationary_indices(n: int, reps: int, block_mean: float, rng: np.random.Generator) -> np.ndarray:
    """Index matrix (reps x n) of Politis-Romano stationary bootstrap draws.

    Each row is a concatenation of blocks with geometric length (mean
    ``block_mean``) starting at uniform positions, wrapping circularly.
    """
    p = 1.0 / block_mean
    new_block = rng.random((reps, n)) < p
    new_block[:, 0] = True
    starts = rng.integers(0, n, size=(reps, n))
    pos = np.arange(n)
    block_start_pos = np.where(new_block, pos, 0)
    np.maximum.accumulate(block_start_pos, axis=1, out=block_start_pos)
    first = np.take_along_axis(starts, block_start_pos, axis=1)
    return (first + (pos - block_start_pos)) % n


def stationary_bootstrap(x: np.ndarray, stat: Callable, block_mean: int = 20,
                         reps: int = 10_000, seed: int = 0) -> np.ndarray:
    """Stationary bootstrap distribution of ``stat(x*)`` (Politis & Romano 1994).

    ``x`` may be 1-D (a return series) or 2-D (T x k, rows resampled jointly,
    e.g. paired strategy/benchmark returns so the cross-dependence is kept).
    ``stat`` receives an array shaped like ``x`` and returns a scalar.
    Returns an array of ``reps`` statistics. NaN rows must be removed by the
    caller (the function refuses them so gaps are never silently filled).
    Deterministic for a given ``seed``.
    """
    arr = np.asarray(x, dtype=float)
    if arr.ndim not in (1, 2):
        raise ValueError("x must be 1-D or 2-D")
    if not np.isfinite(arr).all():
        raise ValueError("x contains NaN/inf; drop or align them before bootstrapping")
    n = arr.shape[0]
    if n < 2:
        raise ValueError("need at least 2 observations")
    if block_mean < 1:
        raise ValueError("block_mean must be >= 1")
    if reps < 1:
        raise ValueError("reps must be >= 1")

    rng = np.random.default_rng(seed)
    out = np.empty(reps, dtype=float)
    # Chunk the index matrix to bound memory (~8 MB of int64 per chunk).
    chunk = max(1, min(reps, 1_000_000 // n))
    done = 0
    while done < reps:
        m = min(chunk, reps - done)
        idx = _stationary_indices(n, m, block_mean, rng)
        for j in range(m):
            out[done + j] = stat(arr[idx[j]])
        done += m
    return out


def bootstrap_ci(x: np.ndarray, stat: Callable, alpha: float = 0.05, block_mean: int = 20,
                 reps: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """Percentile confidence interval of ``stat`` from the stationary bootstrap."""
    dist = stationary_bootstrap(x, stat, block_mean=block_mean, reps=reps, seed=seed)
    lo, hi = np.nanquantile(dist, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def bootstrap_pvalue_diff(a, b, stat: Callable | None = None, block_mean: int = 20,
                          reps: int = 10_000, seed: int = 0) -> float:
    """One-sided p-value of H0: ``stat(a) - stat(b) <= 0`` (PLAN §5.6 point 4).

    ``a`` and ``b`` are aligned return series (same dates); rows are
    resampled jointly with the stationary bootstrap. The bootstrap
    distribution of the difference is centred on zero under H0 and the
    p-value is the fraction of centred draws ``>=`` the observed difference
    (with the usual +1 correction). ``stat`` defaults to the mean.
    """
    xa = np.asarray(a, dtype=float).ravel()
    xb = np.asarray(b, dtype=float).ravel()
    if xa.shape != xb.shape:
        raise ValueError("a and b must be aligned and have the same length")
    f = stat if stat is not None else np.mean
    pair = np.column_stack([xa, xb])

    def diff(m: np.ndarray) -> float:
        return float(f(m[:, 0]) - f(m[:, 1]))

    observed = diff(pair)
    dist = stationary_bootstrap(pair, diff, block_mean=block_mean, reps=reps, seed=seed)
    centred = dist - dist.mean()
    return float((np.sum(centred >= observed) + 1) / (reps + 1))


# --------------------------------------------------------------------------- #
# Multiple testing
# --------------------------------------------------------------------------- #
def holm(pvalues: Sequence[float], alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Holm-Bonferroni step-down correction.

    Returns ``(reject, p_adjusted)`` in the original order. Adjusted p-values
    are ``max_{j<=i} min(1, (m - j + 1) * p_(j))`` over the sorted p-values,
    identical to ``statsmodels.stats.multitest.multipletests(method="holm")``.
    """
    p = np.asarray(pvalues, dtype=float).ravel()
    if p.size == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=float)
    if np.isnan(p).any() or (p < 0).any() or (p > 1).any():
        raise ValueError("p-values must be in [0, 1] and not NaN")
    m = p.size
    order = np.argsort(p, kind="mergesort")
    scaled = np.minimum(1.0, (m - np.arange(m)) * p[order])
    adj_sorted = np.maximum.accumulate(scaled)
    p_adj = np.empty(m, dtype=float)
    p_adj[order] = adj_sorted
    return p_adj <= alpha, p_adj
