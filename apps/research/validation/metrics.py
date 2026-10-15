"""
Performance metrics shared by the gate, the adaptability score and the reports
(PLAN.md §5.5).

Conventions:

- Inputs are daily SIMPLE net returns (``BTResult.returns``); NaN days are
  dropped (no price, no return), never filled.
- Annualisation uses 365 periods per year (crypto trades every day).
- Losses are reported as POSITIVE numbers: ``max_drawdown`` = 0.25 means a
  25 % peak-to-trough loss and ``cvar`` = 0.04 means the mean of the worst 5 %
  daily returns is -4 %.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from apps.research.validation.stats import bootstrap_ci, sharpe_ratio

__all__ = [
    "PERIODS_PER_YEAR",
    "clean_returns",
    "sharpe",
    "cagr",
    "annual_vol",
    "sortino",
    "max_drawdown",
    "drawdown_series",
    "mar",
    "cvar",
    "profit_factor",
    "t_stat",
    "sharpe_diff_se",
    "compounded",
    "perf_metrics",
]

PERIODS_PER_YEAR = 365


def clean_returns(returns) -> np.ndarray:
    """Finite values of ``returns`` as a 1-D float array."""
    arr = np.asarray(returns, dtype=float).ravel()
    return arr[np.isfinite(arr)]


def sharpe(returns, periods: int = PERIODS_PER_YEAR) -> float:
    """Annualised Sharpe ratio (mean / std, ddof = 1, times sqrt(periods))."""
    return sharpe_ratio(clean_returns(returns), periods_per_year=periods)


def compounded(returns) -> float:
    """Total compounded return ``prod(1 + r) - 1``."""
    r = clean_returns(returns)
    return float(np.prod(1.0 + r) - 1.0) if r.size else float("nan")


def cagr(returns, periods: int = PERIODS_PER_YEAR) -> float:
    """Compound annual growth rate over the number of observed days."""
    r = clean_returns(returns)
    if r.size == 0:
        return float("nan")
    growth = float(np.prod(1.0 + r))
    if growth <= 0:
        return -1.0
    return growth ** (periods / r.size) - 1.0


def annual_vol(returns, periods: int = PERIODS_PER_YEAR) -> float:
    r = clean_returns(returns)
    return float(r.std(ddof=1) * math.sqrt(periods)) if r.size >= 2 else float("nan")


def sortino(returns, periods: int = PERIODS_PER_YEAR) -> float:
    """Annualised Sortino ratio: mean / downside deviation (target 0)."""
    r = clean_returns(returns)
    if r.size < 2:
        return float("nan")
    downside = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2))
    if not downside > 0:
        return float("nan")
    return float(r.mean() / downside * math.sqrt(periods))


def drawdown_series(returns: pd.Series) -> pd.Series:
    """Drawdown (positive fraction) of the compounded equity of ``returns``."""
    r = returns.dropna().astype(float)
    eq = (1.0 + r).cumprod()
    peak = np.maximum(eq.cummax(), 1.0)
    return (1.0 - eq / peak).rename("drawdown")


def max_drawdown(returns) -> float:
    """Maximum peak-to-trough loss of the compounded equity (starting at 1)."""
    r = clean_returns(returns)
    if r.size == 0:
        return float("nan")
    eq = np.cumprod(1.0 + r)
    peak = np.maximum(np.maximum.accumulate(eq), 1.0)
    return float(np.max(1.0 - eq / peak))


def mar(returns, periods: int = PERIODS_PER_YEAR) -> float:
    """MAR ratio: CAGR / MaxDD (NaN without drawdown)."""
    dd = max_drawdown(returns)
    if not dd > 0:
        return float("nan")
    return cagr(returns, periods) / dd


def cvar(returns, level: float = 0.95) -> float:
    """Daily CVaR (expected shortfall) at ``level`` as a positive loss."""
    r = clean_returns(returns)
    if r.size == 0:
        return float("nan")
    k = max(1, int(math.ceil((1.0 - level) * r.size)))
    worst = np.sort(r)[:k]
    return float(-worst.mean())


def profit_factor(returns) -> float:
    """Sum of positive returns / |sum of negative returns| (daily, not per trade)."""
    r = clean_returns(returns)
    losses = -r[r < 0].sum()
    if not losses > 0:
        return float("nan")
    return float(r[r > 0].sum() / losses)


def t_stat(returns) -> float:
    """t statistic of the mean return (= per-period Sharpe * sqrt(T))."""
    r = clean_returns(returns)
    sr = sharpe_ratio(r)
    return float(sr * math.sqrt(r.size)) if math.isfinite(sr) else float("nan")


def sharpe_diff_se(a, b, periods: int = PERIODS_PER_YEAR) -> tuple[float, float]:
    """
    Annualised Sharpe difference ``SR_a - SR_b`` of two aligned series and its
    standard error (Jobson-Korkie with Memmel's 2003 correction):

    ``Var = (2 - 2 rho + 0.5 (SR_a^2 + SR_b^2 - 2 rho^2 SR_a SR_b)) / T``

    with per-period Sharpe ratios; the SE is then annualised by sqrt(periods).
    """
    df = pd.concat([pd.Series(np.asarray(a, dtype=float)), pd.Series(np.asarray(b, dtype=float))],
                   axis=1).dropna()
    if len(df) < 3:
        return float("nan"), float("nan")
    xa, xb = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    sa, sb = sharpe_ratio(xa), sharpe_ratio(xb)
    if not (math.isfinite(sa) and math.isfinite(sb)):
        return float("nan"), float("nan")
    rho = float(np.corrcoef(xa, xb)[0, 1]) if xa.std() > 0 and xb.std() > 0 else 0.0
    var = (2.0 - 2.0 * rho + 0.5 * (sa * sa + sb * sb - 2.0 * rho * rho * sa * sb)) / len(df)
    k = math.sqrt(periods)
    return (sa - sb) * k, math.sqrt(max(var, 0.0)) * k


def perf_metrics(returns: pd.Series, periods: int = PERIODS_PER_YEAR, ci: bool = True,
                 reps: int = 2000, block_mean: int = 20, seed: int = 0) -> dict:
    """
    Standard metric set of PLAN §5.5 for one daily return series.

    ``sharpe_ci`` is the 95 % percentile interval of the annualised Sharpe from
    the stationary bootstrap (mean block 20 days); it is ``(nan, nan)`` with
    fewer than 30 observations or when ``ci`` is False.
    """
    r = pd.Series(returns, dtype=float).dropna()
    out = {
        "n_days": int(len(r)),
        "total_return": compounded(r),
        "cagr": cagr(r, periods),
        "vol": annual_vol(r, periods),
        "sharpe": sharpe(r, periods),
        "sortino": sortino(r, periods),
        "max_dd": max_drawdown(r),
        "mar": mar(r, periods),
        "cvar95": cvar(r, 0.95),
        "profit_factor": profit_factor(r),
        "t_stat": t_stat(r),
        "sharpe_ci": (float("nan"), float("nan")),
    }
    if ci and len(r) >= 30 and r.std() > 0:
        k = math.sqrt(periods)
        out["sharpe_ci"] = bootstrap_ci(r.to_numpy(), lambda x: _sr(x) * k, block_mean=block_mean,
                                        reps=reps, seed=seed)
    return out


def _sr(x: np.ndarray) -> float:
    sd = x.std(ddof=1)
    return float(x.mean() / sd) if sd > 0 else 0.0
