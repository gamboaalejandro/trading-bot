"""
Common portfolio construction, layer D (PLAN.md §2.0, §7.3). Fixed a priori, 0 trials.

1. Discretise the exposure signal to quarters: ``E_q = round(4E)/4``.
2. Raw weight per coin: ``u_i = E_q,i / sigma_90,i``.
3. Stress covariance ``Sigma_s = D R_s D`` with
   ``R_s,ij = max(rho_ewma_ij(lambda=0.97), 0.75)``.
4. Scale to the portfolio volatility target: ``w = u * sigma_p* / sqrt(u' Sigma_s u)``.
5. Caps, in this order: per coin (0.20 alts, 0.35 BTC/ETH); sum of long alts
   <= 0.60; gross long <= 1.0; gross short <= 0.5; and finally
   ``|w_i| <= |E_q,i| * min(sigma*_coin / sigma_90,i, 1)`` with sigma*_coin = 25 %.
6. No-trade band: rebalance symbol i only if
   ``|w_new - w_held| > b * max(|w_held|, |w_new|)`` or the position opens/closes.

All the caps only scale weights down, so the final weights satisfy every cap.
The same code runs in the backtest and in the live executor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "SizingConfig",
    "SizingError",
    "ANNUALIZATION",
    "discretize",
    "annualized_vol",
    "ewma_corr",
    "stress_cov",
    "target_weights",
    "apply_band",
]

ANNUALIZATION = 365  # crypto trades every day


class SizingError(ValueError):
    """Invalid sizing inputs (missing volatility for an active signal, bad config...)."""


@dataclass(frozen=True)
class SizingConfig:
    """Parameters of layer D. Defaults are the preregistered values of PLAN §2.0."""

    sigma_target: float = 0.15          # sigma_p*, annualised portfolio vol target
    band: float = 0.20                  # no-trade band b
    step: float = 0.25                  # signal discretisation step
    cap_major: float = 0.35             # |w_i| cap for BTC/ETH
    cap_alt: float = 0.20               # |w_i| cap for every other coin
    alt_long_cap: float = 0.60          # sum of long alt weights (one cluster)
    gross_long_cap: float = 1.0
    gross_short_cap: float = 0.5
    sigma_coin_target: float = 0.25     # sigma*_coin for the per-coin vol cap
    rho_floor: float = 0.75
    ewma_lambda: float = 0.97
    vol_window: int = 90
    majors: tuple = field(default=("BTCUSDT", "ETHUSDT"))

    def __post_init__(self) -> None:
        positives = ("sigma_target", "step", "cap_major", "cap_alt", "alt_long_cap",
                     "gross_long_cap", "gross_short_cap", "sigma_coin_target")
        for name in positives:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise SizingError(f"{name} must be > 0, got {value!r}")
        if not 0 <= self.band < 1:
            raise SizingError(f"band must be in [0, 1), got {self.band!r}")
        if not -1 <= self.rho_floor <= 1:
            raise SizingError(f"rho_floor must be in [-1, 1], got {self.rho_floor!r}")
        if not 0 < self.ewma_lambda < 1:
            raise SizingError(f"ewma_lambda must be in (0, 1), got {self.ewma_lambda!r}")
        if self.gross_long_cap > 1.0:
            raise SizingError("gross long exposure above 1x is not allowed (PLAN §1.4, §7.3)")

    def is_major(self, symbol: str) -> bool:
        return symbol in self.majors or symbol.split("/")[0] + "USDT" in self.majors

    def coin_cap(self, symbol: str) -> float:
        return self.cap_major if self.is_major(symbol) else self.cap_alt


def discretize(E: pd.DataFrame, step: float = 0.25) -> pd.DataFrame:
    """
    Round an exposure signal to multiples of ``step`` (quarters by default), clipped to [-1, 1].

    Halves round away from zero (0.125 -> 0.25, -0.125 -> -0.25). NaN stays NaN.
    """
    if not math.isfinite(step) or step <= 0:
        raise SizingError(f"step must be > 0, got {step!r}")
    scaled = E / step
    rounded = np.sign(scaled) * np.floor(np.abs(scaled) + 0.5 + 1e-12)
    return (rounded * step).clip(lower=-1.0, upper=1.0)


def annualized_vol(returns: pd.DataFrame, t=None, window: int = 90, min_frac: float = 2 / 3) -> pd.Series:
    """
    ``sigma_n(t)``: std of the last ``window`` daily returns up to ``t`` times sqrt(365).

    NaN for symbols with fewer than ``min_frac * window`` valid observations in the window.
    """
    hist = returns.loc[:t] if t is not None else returns
    tail = hist.iloc[-window:]
    vol = tail.std(ddof=1) * math.sqrt(ANNUALIZATION)
    enough = tail.notna().sum() >= max(2, math.ceil(min_frac * window))
    return vol.where(enough)


def ewma_corr(returns: pd.DataFrame, t=None, lam: float = 0.97) -> np.ndarray:
    """
    Zero-mean EWMA (RiskMetrics) correlation matrix using data up to ``t``.

    Pairs are estimated on their jointly observed dates (missing values are
    skipped, never filled). Pairs with no overlap get NaN.
    """
    hist = returns.loc[:t] if t is not None else returns
    x = hist.to_numpy(dtype=float)
    n = x.shape[0]
    mask = np.isfinite(x).astype(float)
    y = np.where(mask > 0, x, 0.0)
    w = lam ** np.arange(n - 1, -1, -1, dtype=float)  # newest observation has weight 1
    wy = y * w[:, None]
    cross = wy.T @ y                       # sum w * y_i * y_j over joint dates
    var_pair = (wy * y).T @ mask           # [i, j] = sum w * y_i^2 over dates where j observed
    denom = np.sqrt(var_pair * var_pair.T)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(denom > 0, cross / denom, np.nan)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def stress_cov(returns: pd.DataFrame, t, lam: float = 0.97, rho_floor: float = 0.75,
               vol_window: int = 90) -> np.ndarray:
    """
    Stress covariance ``D R_s D`` at ``t`` (rows/cols follow ``returns.columns``).

    ``returns`` are daily log returns indexed by bar date; only rows ``<= t`` are
    used. ``D = diag(sigma_vol_window)`` (annualised) and
    ``R_s,ij = max(rho_ewma_ij, rho_floor)``. A pair with no overlapping history
    gets correlation 1 (the most conservative value). Symbols without enough
    history for their volatility have NaN rows/columns.
    """
    sigma = annualized_vol(returns, t, window=vol_window).to_numpy(dtype=float)
    corr = ewma_corr(returns, t, lam=lam)
    corr = np.where(np.isfinite(corr), np.maximum(corr, rho_floor), 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr * np.outer(sigma, sigma)


def _scale_group(w: pd.Series, mask: pd.Series, cap: float) -> pd.Series:
    """Scale the weights selected by ``mask`` so that their absolute sum is <= cap."""
    total = w[mask].abs().sum()
    if total > cap:
        w = w.copy()
        w[mask] = w[mask] * (cap / total)
    return w


def target_weights(E_q: pd.Series, sigma: pd.Series, cov_s: np.ndarray, cfg: SizingConfig) -> pd.Series:
    """
    Target portfolio weights for one rebalance date (layer D, PLAN §2.0).

    ``E_q`` is the discretised signal per symbol (in [-1, 1]); ``sigma`` the
    annualised sigma_90 per symbol; ``cov_s`` the stress covariance whose
    rows/columns follow ``E_q.index``. Symbols with ``E_q`` 0 or NaN get 0. An
    active symbol without a valid volatility raises ``SizingError``.
    """
    symbols = E_q.index
    cov = np.asarray(cov_s, dtype=float)
    if cov.shape != (len(symbols), len(symbols)):
        raise SizingError(f"cov_s shape {cov.shape} does not match {len(symbols)} symbols")
    e = E_q.astype(float).fillna(0.0).clip(-1.0, 1.0)
    sig = sigma.reindex(symbols).astype(float)
    active = e != 0
    bad = active & ~(np.isfinite(sig) & (sig > 0))
    if bad.any():
        raise SizingError(f"no valid volatility for active symbols {list(symbols[bad.to_numpy()])}")

    w = pd.Series(0.0, index=symbols, name="weight")
    if not active.any():
        return w

    # 1-2. Inverse-vol raw weights, scaled to the stress portfolio vol target.
    act = active.to_numpy()
    u = (e[active] / sig[active]).to_numpy()
    sub = cov[np.ix_(act, act)]
    if not np.isfinite(sub).all():
        raise SizingError("stress covariance has missing entries for active symbols")
    port_var = float(u @ sub @ u)
    if port_var <= 0:
        return w
    w[active] = u * cfg.sigma_target / math.sqrt(port_var)

    # 3. Caps, in the order of PLAN §2.0.
    caps = pd.Series([cfg.coin_cap(s) for s in symbols], index=symbols)
    w = w.clip(lower=-caps, upper=caps)
    is_alt = pd.Series([not cfg.is_major(s) for s in symbols], index=symbols)
    w = _scale_group(w, is_alt & (w > 0), cfg.alt_long_cap)
    w = _scale_group(w, w > 0, cfg.gross_long_cap)
    w = _scale_group(w, w < 0, cfg.gross_short_cap)
    coin_vol_cap = e.abs() * np.minimum(cfg.sigma_coin_target / sig.where(active, np.inf), 1.0)
    w = w.clip(lower=-coin_vol_cap, upper=coin_vol_cap)
    return w + 0.0  # normalise -0.0


def apply_band(w_new: pd.Series, w_held: pd.Series, band: float) -> pd.Series:
    """
    No-trade band: keep the held weight unless the change is large enough.

    Symbol i trades to ``w_new`` if ``|w_new - w_held| > band * max(|w_held|, |w_new|)``,
    or if the position opens (held 0, new != 0), closes (new 0) or flips sign.
    Symbols missing on either side count as 0.
    """
    if not 0 <= band < 1:
        raise SizingError(f"band must be in [0, 1), got {band!r}")
    idx = w_new.index.union(w_held.index)
    new = w_new.reindex(idx).astype(float).fillna(0.0)
    held = w_held.reindex(idx).astype(float).fillna(0.0)
    big_move = (new - held).abs() > band * np.maximum(held.abs(), new.abs())
    opens_or_closes = (new == 0) != (held == 0)
    flips = np.sign(new) * np.sign(held) < 0
    trade = big_move | opens_or_closes | flips
    out = held.where(~trade, new)
    out.name = w_new.name
    return out
