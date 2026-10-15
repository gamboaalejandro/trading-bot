"""Tests for apps.research.portfolio.sizing (PLAN §6.2 R05)."""
import math

import numpy as np
import pandas as pd
import pytest

from apps.research.portfolio.sizing import (
    SizingConfig,
    SizingError,
    annualized_vol,
    apply_band,
    discretize,
    ewma_corr,
    stress_cov,
    target_weights,
)


# --------------------------------------------------------------------------- discretize
def test_discretize_to_quarters():
    E = pd.DataFrame({"a": [0.0, 0.1, 0.13, 0.4, 0.62, 0.88, 1.0, 1.3],
                      "b": [-0.1, -0.13, -0.4, -0.7, -1.0, -2.0, np.nan, 0.5]})
    q = discretize(E)
    assert q["a"].tolist() == [0.0, 0.0, 0.25, 0.5, 0.5, 1.0, 1.0, 1.0]
    assert q["b"].iloc[:6].tolist() == [0.0, -0.25, -0.5, -0.75, -1.0, -1.0]
    assert np.isnan(q["b"].iloc[6])
    vals = set(q.stack().dropna().abs().tolist())
    assert vals <= {0.0, 0.25, 0.5, 0.75, 1.0}


def test_discretize_halves_round_away_from_zero():
    q = discretize(pd.DataFrame({"a": [0.125, 0.375, -0.125]}))
    assert q["a"].tolist() == [0.25, 0.5, -0.25]


# --------------------------------------------------------------------------- stress cov
def _returns(n=300, seed=1, rho=0.2):
    rng = np.random.default_rng(seed)  # unit-test fixture only, not used for any backtest result
    z = rng.standard_normal((n, 3))
    common = rng.standard_normal(n)
    x = math.sqrt(rho) * common[:, None] + math.sqrt(1 - rho) * z
    vols = np.array([0.02, 0.04, 0.05])
    idx = pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame(x * vols, index=idx, columns=["BTCUSDT", "ETHUSDT", "SOLUSDT"])


def test_stress_cov_correlation_floor_and_diagonal():
    r = _returns(rho=0.1)
    t = r.index[-1]
    cov = stress_cov(r, t)
    sig = annualized_vol(r, t, 90).to_numpy()
    corr = cov / np.outer(sig, sig)
    assert np.allclose(np.diag(corr), 1.0)
    off = corr[~np.eye(3, dtype=bool)]
    assert (off >= 0.75 - 1e-12).all()
    assert np.allclose(cov, cov.T)
    assert np.allclose(np.sqrt(np.diag(cov)), r.iloc[-90:].std().to_numpy() * math.sqrt(365))


def test_stress_cov_keeps_high_correlation_above_floor():
    r = _returns(rho=0.95)
    t = r.index[-1]
    raw = ewma_corr(r, t)
    cov = stress_cov(r, t)
    sig = annualized_vol(r, t).to_numpy()
    corr = cov / np.outer(sig, sig)
    assert raw[0, 1] > 0.9
    assert corr[0, 1] == pytest.approx(raw[0, 1])


def test_stress_cov_is_causal():
    r = _returns()
    t = r.index[200]
    a = stress_cov(r, t)
    b = stress_cov(r.loc[:t], t)
    assert np.allclose(a, b)


def test_ewma_corr_handles_missing_history():
    r = _returns()
    r.iloc[:250, 2] = np.nan  # SOL listed later
    c = ewma_corr(r)
    assert np.isfinite(c).all()
    r2 = r.copy()
    r2.iloc[:, 2] = np.nan
    cov = stress_cov(r2, r2.index[-1])
    assert np.isnan(cov[2, 2])


# --------------------------------------------------------------------------- target weights
def _cov(sig, rho=0.75):
    sig = np.asarray(sig, dtype=float)
    R = np.full((len(sig), len(sig)), rho)
    np.fill_diagonal(R, 1.0)
    return R * np.outer(sig, sig)


def test_target_weights_hits_vol_target_when_no_cap_binds():
    cfg = SizingConfig()
    E = pd.Series([1.0, 1.0], index=["BTCUSDT", "ETHUSDT"])
    sig = pd.Series([0.6, 0.8], index=E.index)
    cov = _cov(sig)
    w = target_weights(E, sig, cov, cfg)
    port_vol = math.sqrt(w.to_numpy() @ cov @ w.to_numpy())
    assert port_vol == pytest.approx(0.15)
    # Inverse-vol proportions survive the scaling.
    assert w["BTCUSDT"] / w["ETHUSDT"] == pytest.approx(0.8 / 0.6)


def test_target_weights_zero_and_missing_signal():
    cfg = SizingConfig()
    E = pd.Series([0.0, np.nan], index=["BTCUSDT", "SOLUSDT"])
    w = target_weights(E, pd.Series([0.5, np.nan], index=E.index), _cov([0.5, 0.5]), cfg)
    assert (w == 0).all()


def test_target_weights_active_without_vol_raises():
    cfg = SizingConfig()
    E = pd.Series([1.0], index=["SOLUSDT"])
    with pytest.raises(SizingError):
        target_weights(E, pd.Series([np.nan], index=E.index), np.array([[np.nan]]), cfg)


def test_per_coin_caps():
    cfg = SizingConfig(sigma_target=5.0, sigma_coin_target=10.0)  # force caps to bind
    E = pd.Series([1.0, 1.0], index=["BTCUSDT", "SOLUSDT"])
    sig = pd.Series([0.2, 0.2], index=E.index)
    w = target_weights(E, sig, _cov(sig), cfg)
    assert w["BTCUSDT"] == pytest.approx(0.35)
    assert w["SOLUSDT"] == pytest.approx(0.20)


def test_alt_cluster_and_gross_long_caps_in_order():
    alts = [f"ALT{i}USDT" for i in range(8)]
    syms = ["BTCUSDT", "ETHUSDT"] + alts
    cfg = SizingConfig(sigma_target=5.0, sigma_coin_target=10.0)
    E = pd.Series(1.0, index=syms)
    sig = pd.Series(0.3, index=syms)
    w = target_weights(E, sig, _cov(sig), cfg)
    # Per-coin cap first: 0.35/0.35 and 8 x 0.20 = 1.6 alts -> alt cap 0.60 -> 0.075 each.
    assert w[alts].tolist() == pytest.approx([0.075 / 1.3] * 8)
    # Then gross long = 0.70 + 0.60 = 1.30 -> scaled to 1.0 proportionally.
    assert w.sum() == pytest.approx(1.0)
    assert w["BTCUSDT"] == pytest.approx(0.35 / 1.3)
    assert w[alts].sum() == pytest.approx(0.60 / 1.3)


def test_gross_long_never_above_one_random_inputs():
    rng = np.random.default_rng(7)  # fixture for an invariant check only
    syms = ["BTCUSDT", "ETHUSDT"] + [f"A{i}USDT" for i in range(10)]
    cfg = SizingConfig(sigma_target=3.0)
    for _ in range(200):
        E = pd.Series(discretize(pd.DataFrame({"e": rng.uniform(-1, 1, len(syms))}))["e"].to_numpy(), index=syms)
        sig = pd.Series(rng.uniform(0.1, 1.5, len(syms)), index=syms)
        w = target_weights(E, sig, _cov(sig, rho=rng.uniform(0.75, 1.0)), cfg)
        assert w[w > 0].sum() <= 1.0 + 1e-9
        assert -w[w < 0].sum() <= 0.5 + 1e-9
        alts = [s for s in syms if s not in cfg.majors]
        assert w[alts].clip(lower=0).sum() <= 0.60 + 1e-9
        assert (w.abs() <= pd.Series([cfg.coin_cap(s) for s in syms], index=syms) + 1e-12).all()
        assert (w.abs() <= E.abs() * np.minimum(0.25 / sig, 1.0) + 1e-12).all()
        assert (np.sign(w[w != 0]) == np.sign(E[w != 0])).all()


def test_gross_short_cap():
    syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    cfg = SizingConfig(sigma_target=5.0, sigma_coin_target=10.0)
    E = pd.Series(-1.0, index=syms)
    sig = pd.Series(0.3, index=syms)
    w = target_weights(E, sig, _cov(sig), cfg)
    assert -w.sum() == pytest.approx(0.5)
    assert (w < 0).all()


def test_coin_vol_cap_is_last_and_binding():
    cfg = SizingConfig(sigma_target=5.0)
    E = pd.Series([0.5], index=["BTCUSDT"])
    sig = pd.Series([1.0], index=E.index)
    w = target_weights(E, sig, _cov(sig), cfg)
    # 0.5 * min(0.25 / 1.0, 1) = 0.125 < 0.35 coin cap.
    assert w["BTCUSDT"] == pytest.approx(0.125)


def test_sizing_config_rejects_leverage_on_long_book():
    with pytest.raises(SizingError):
        SizingConfig(gross_long_cap=1.5)


# --------------------------------------------------------------------------- band
def test_band_keeps_small_changes():
    held = pd.Series({"BTCUSDT": 0.30, "ETHUSDT": 0.20})
    new = pd.Series({"BTCUSDT": 0.33, "ETHUSDT": 0.10})
    out = apply_band(new, held, 0.20)
    assert out["BTCUSDT"] == 0.30      # |0.03| <= 0.2*0.33
    assert out["ETHUSDT"] == 0.10      # |0.10| > 0.2*0.20


def test_band_always_opens_closes_and_flips():
    held = pd.Series({"A": 0.0, "B": 0.10, "C": 0.05})
    new = pd.Series({"A": 0.01, "B": 0.0, "C": -0.05})
    out = apply_band(new, held, 0.20)
    assert out.to_dict() == {"A": 0.01, "B": 0.0, "C": -0.05}


def test_band_missing_symbols_count_as_zero():
    out = apply_band(pd.Series({"A": 0.2}), pd.Series({"B": 0.1}), 0.2)
    assert out.to_dict() == {"A": 0.2, "B": 0.0}


def test_band_zero_trades_everything():
    held = pd.Series({"A": 0.30})
    out = apply_band(pd.Series({"A": 0.301}), held, 0.0)
    assert out["A"] == 0.301
