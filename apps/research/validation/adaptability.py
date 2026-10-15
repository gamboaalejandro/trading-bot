"""
Adaptability score A_k (PLAN.md §3.3, §5.1, task R15). OOS walk-forward only.

1. Cells ``(coin i, regime j)`` with the ex-ante regime of
   :func:`apps.research.features.regime.ex_ante_cells`. In each cell: the
   annualised net Sharpe ``SR_ij``, its ``T_ij`` days and its standard error
   ``se_ij = sqrt((1 - g3 SR + (g4 - 1)/4 SR^2) / T_ij)`` (per-period SR,
   plain kurtosis), annualised like the Sharpe.
2. Empirical-Bayes shrinkage to the engine mean:
   ``SR~_ij = SRbar + (1 - B_ij)(SR_ij - SRbar)``, ``B_ij = se_ij^2 / (se_ij^2 + tau^2)``
   with ``tau^2 = max(0, Var(SR_ij) - mean(se_ij^2))`` (method of moments).
   When ``se -> inf``, ``B -> 1`` and the cell collapses to the mean.
3. ``A_k = Q20_w(SR~_ij) - lambda * p_k / sqrt(T_years)``; weights
   ``T_ij / (1 + (n_cluster - 1) * rho_bar)`` and ``lambda = 0.1`` [OPINION,
   fixed]. Clusters: single linkage of the coins' OOS return correlation at
   ``rho > 0.8`` (PLAN §7.3) unless given explicitly.
4. Also reported: share of cells with ``SR~ > 0``, the daily CVaR95 of the
   worst regime (portfolio returns), N_eff and, when the trials log figures
   are passed, the global DSR.

N_eff (PLAN §5.1): participation ratio of the correlation eigenvalues
``(sum l)^2 / sum l^2`` and ``n / (1 + (n - 1) rho_bar)``.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.validation.metrics import PERIODS_PER_YEAR, cvar
from apps.research.validation.stats import dsr, moments

__all__ = [
    "LAMBDA",
    "Q_LEVEL",
    "CLUSTER_RHO",
    "MIN_CELL_DAYS",
    "cell_stats",
    "eb_shrink",
    "weighted_quantile",
    "correlation_clusters",
    "cluster_weights",
    "n_eff",
    "adaptability_score",
]

LAMBDA = 0.1
Q_LEVEL = 0.20
CLUSTER_RHO = 0.8
MIN_CELL_DAYS = 20
_K = math.sqrt(PERIODS_PER_YEAR)


def _cells_frame(cells, index: pd.Index, columns: pd.Index) -> pd.DataFrame:
    """Broadcast a common regime Series (or one-column frame) to dates x symbols."""
    if isinstance(cells, pd.DataFrame):
        if set(columns).issubset(cells.columns):
            return cells.reindex(index=index, columns=columns)
        if cells.shape[1] == 1:
            cells = cells.iloc[:, 0]
        else:
            raise ValueError("cells must be a Series, a one-column frame or a dates x symbols frame")
    s = pd.Series(cells).reindex(index)
    return pd.DataFrame({c: s for c in columns}, index=index)


def cell_stats(oos_returns: pd.DataFrame, cells, min_days: int = MIN_CELL_DAYS) -> pd.DataFrame:
    """
    One row per ``(symbol, cell)`` with ``T``, annualised ``sr`` and ``se``.

    Cells with fewer than ``min_days`` returns or zero dispersion are dropped
    (their Sharpe is not estimable). A day without a return (NaN: coin not
    listed yet) does not count.
    """
    cf = _cells_frame(cells, oos_returns.index, oos_returns.columns)
    rows = []
    for s in oos_returns.columns:
        r = oos_returns[s].astype(float)
        lab = cf[s]
        ok = r.notna() & lab.notna()
        for cell, grp in r[ok].groupby(lab[ok].astype(str)):
            x = grp.to_numpy()
            if x.size < max(min_days, 3) or not x.std(ddof=1) > 0:
                continue
            sr = float(x.mean() / x.std(ddof=1))
            g3, g4 = moments(x)
            v = 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr * sr
            se = math.sqrt(max(v, 1e-12) / x.size)
            rows.append({"symbol": s, "cell": cell, "T": int(x.size), "sr": sr * _K, "se": se * _K})
    return pd.DataFrame(rows, columns=["symbol", "cell", "T", "sr", "se"])


def eb_shrink(sr, se) -> tuple[np.ndarray, np.ndarray, float, float]:
    """
    Empirical-Bayes shrinkage of cell Sharpes to their mean.

    Returns ``(sr_tilde, B, tau2, sr_bar)``. ``tau2`` is the method-of-moments
    between-cell variance, truncated at 0 (then ``B = 1`` everywhere).
    """
    sr = np.asarray(sr, dtype=float)
    se = np.asarray(se, dtype=float)
    if sr.shape != se.shape or sr.size == 0:
        raise ValueError("sr and se must be non-empty and aligned")
    if (se < 0).any() or not np.isfinite(sr).all():
        raise ValueError("se must be >= 0 and sr finite")
    sr_bar = float(sr.mean())
    se2 = se * se
    fin = np.isfinite(se2)
    # Cells with an infinite se carry no information: they are left out of tau^2 and get B = 1.
    var = float(sr[fin].var(ddof=1)) if fin.sum() > 1 else 0.0
    tau2 = max(0.0, var - float(se2[fin].mean())) if fin.any() else 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        B = np.where(np.isinf(se2), 1.0, se2 / (se2 + tau2))
    B = np.where(np.isnan(B), 1.0, B)   # se = 0 and tau2 = 0: nothing to learn, full shrink
    return sr_bar + (1.0 - B) * (sr - sr_bar), B, float(tau2), sr_bar


def weighted_quantile(values, weights, q: float) -> float:
    """
    Weighted quantile (inverted CDF): the smallest value whose cumulative
    normalised weight reaches ``q``. With equal weights it equals
    ``np.quantile(values, q, method="inverted_cdf")``.
    """
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if v.shape != w.shape or v.size == 0:
        raise ValueError("values and weights must be non-empty and aligned")
    if (w < 0).any() or not w.sum() > 0:
        raise ValueError("weights must be >= 0 with a positive sum")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    order = np.argsort(v, kind="mergesort")
    v, w = v[order], w[order]
    cw = np.cumsum(w) / w.sum()
    i = int(np.searchsorted(cw, q - 1e-12, side="left"))
    return float(v[min(i, v.size - 1)])


def correlation_clusters(corr: pd.DataFrame, rho: float = CLUSTER_RHO) -> dict[str, int]:
    """Single-linkage clusters of the symbols whose pairwise correlation exceeds ``rho``."""
    names = list(corr.columns)
    parent = list(range(len(names)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    c = corr.to_numpy(dtype=float)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if np.isfinite(c[i, j]) and c[i, j] > rho:
                parent[find(i)] = find(j)
    roots = {find(i) for i in range(len(names))}
    ids = {r: k for k, r in enumerate(sorted(roots))}
    return {names[i]: ids[find(i)] for i in range(len(names))}


def cluster_weights(corr: pd.DataFrame, clusters: Optional[Mapping[str, object]] = None,
                    rho: float = CLUSTER_RHO) -> pd.Series:
    """Per-symbol deflator ``1 / (1 + (n_cluster - 1) * rho_bar)`` (rho_bar = mean pairwise corr)."""
    cl = dict(clusters) if clusters is not None else correlation_clusters(corr, rho)
    out = {}
    for s in corr.columns:
        members = [m for m in corr.columns if cl.get(m) == cl.get(s)]
        n = len(members)
        if n <= 1:
            out[s] = 1.0
            continue
        sub = corr.loc[members, members].to_numpy(dtype=float)
        off = sub[~np.eye(n, dtype=bool)]
        rho_bar = float(np.nanmean(off)) if np.isfinite(off).any() else 0.0
        out[s] = 1.0 / (1.0 + (n - 1) * max(rho_bar, 0.0))
    return pd.Series(out)


def n_eff(data: pd.DataFrame, is_corr: bool = False) -> dict:
    """
    Effective number of independent coins (PLAN §5.1): the participation ratio
    of the correlation eigenvalues and ``n / (1 + (n - 1) rho_bar)``.
    """
    corr = data if is_corr else data.corr()
    c = corr.to_numpy(dtype=float)
    n = c.shape[0]
    if n == 0:
        return {"n": 0, "participation_ratio": float("nan"), "n_over_rho": float("nan"), "rho_bar": float("nan")}
    c = np.where(np.isfinite(c), c, 0.0)
    np.fill_diagonal(c, 1.0)
    lam = np.clip(np.linalg.eigvalsh((c + c.T) / 2.0), 0.0, None)
    pr = float(lam.sum() ** 2 / (lam ** 2).sum()) if (lam ** 2).sum() > 0 else float("nan")
    rho_bar = float(c[~np.eye(n, dtype=bool)].mean()) if n > 1 else 0.0
    return {"n": int(n), "participation_ratio": pr,
            "n_over_rho": float(n / (1.0 + (n - 1) * rho_bar)) if n > 1 else 1.0, "rho_bar": rho_bar}


def adaptability_score(oos_returns: pd.DataFrame, cells: pd.DataFrame, n_free: int, lam: float = LAMBDA,
                       *, clusters: Optional[Mapping[str, object]] = None, q: float = Q_LEVEL,
                       min_days: int = MIN_CELL_DAYS, n_trials: Optional[int] = None,
                       sr_trials_var: Optional[float] = None) -> dict:
    """
    A_k of one engine from its OOS daily net returns per coin (dates x symbols)
    and the ex-ante regime cells (a Series of labels per date, or dates x
    symbols). ``n_free`` is the engine's number of free parameters ``p_k``.

    ``n_trials`` / ``sr_trials_var`` (variance of the per-day Sharpes of every
    trial) enable the global DSR of the portfolio returns.
    """
    if not isinstance(oos_returns, pd.DataFrame) or oos_returns.empty:
        raise ValueError("oos_returns must be a non-empty dates x symbols frame")
    stats = cell_stats(oos_returns, cells, min_days)
    port = oos_returns.sum(axis=1, min_count=1).dropna()
    t_years = len(port) / PERIODS_PER_YEAR
    out: dict = {"n_cells": int(len(stats)), "n_free": int(n_free), "lambda": lam, "q": q,
                 "t_years": t_years}
    corr = oos_returns.corr()
    out["n_eff"] = n_eff(corr, is_corr=True)
    if stats.empty or t_years <= 0:
        out.update({"A_k": float("nan"), "q20": float("nan"), "frac_positive": float("nan"),
                    "tau2": float("nan"), "sr_bar": float("nan"), "cells": stats,
                    "worst_regime": None, "worst_regime_cvar95": float("nan")})
        return out
    sr_t, B, tau2, sr_bar = eb_shrink(stats["sr"], stats["se"])
    stats = stats.assign(sr_tilde=sr_t, B=B)
    deflator = cluster_weights(corr, clusters).reindex(stats["symbol"]).fillna(1.0).to_numpy()
    stats["weight"] = stats["T"].to_numpy() * deflator
    q20 = weighted_quantile(stats["sr_tilde"], stats["weight"], q)
    penalty = lam * n_free / math.sqrt(t_years)
    out.update({
        "A_k": q20 - penalty,
        "q20": q20,
        "penalty": penalty,
        "tau2": tau2,
        "sr_bar": sr_bar,
        "frac_positive": float(np.mean(stats["sr_tilde"] > 0)),
        "cells": stats,
    })
    # Worst regime by daily CVaR95 of the portfolio returns.
    cf = _cells_frame(cells, oos_returns.index, oos_returns.columns).iloc[:, 0].reindex(port.index)
    worst, worst_c = None, -math.inf
    for cell, grp in port.groupby(cf.dropna().astype(str)):
        if len(grp) >= min_days:
            c = cvar(grp.to_numpy(), 0.95)
            if c > worst_c:
                worst, worst_c = cell, c
    out["worst_regime"] = worst
    out["worst_regime_cvar95"] = worst_c if worst is not None else float("nan")
    if n_trials is not None and sr_trials_var is not None and len(port) > 3 and port.std() > 0:
        sr_d = float(port.mean() / port.std(ddof=1))
        g3, g4 = moments(port.to_numpy())
        try:
            out["dsr"] = dsr(sr_d, len(port), g3, g4, sr_trials_var, max(int(n_trials), 1))
        except ValueError:
            out["dsr"] = float("nan")
    return out
