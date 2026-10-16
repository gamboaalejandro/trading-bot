"""Adaptability score A_k (PLAN §3.3, §5.1; §6.2 R15)."""
import math

import numpy as np
import pandas as pd
import pytest

from apps.research.validation.adaptability import (
    LAMBDA,
    adaptability_score,
    cell_stats,
    cluster_weights,
    correlation_clusters,
    eb_shrink,
    n_eff,
    weighted_quantile,
)

IDX = pd.date_range("2022-01-01", periods=1200, freq="D", tz="UTC")


# --------------------------------------------------------------------------- EB shrinkage
def test_b_goes_to_one_when_se_goes_to_infinity():
    sr = np.array([1.5, -0.5, 0.3, 0.8])
    prev = None
    for big in (0.1, 1.0, 10.0, 1e3, 1e6):
        se = np.array([0.2, 0.2, 0.2, big])
        st, B, tau2, bar = eb_shrink(sr, se)
        if prev is not None:
            assert B[3] >= prev - 1e-12              # monotone towards 1
        prev = B[3]
    assert B[3] == pytest.approx(1.0, abs=1e-6)
    assert st[3] == pytest.approx(bar, abs=1e-5)  # collapses to the engine mean
    st, B, _, bar = eb_shrink(sr, np.array([0.2, 0.2, 0.2, np.inf]))
    assert B[3] == 1.0 and st[3] == pytest.approx(bar)


def test_eb_no_shrink_when_se_is_tiny_and_full_when_tau_zero():
    sr = np.array([1.0, -1.0, 0.5, 2.0])
    st, B, tau2, bar = eb_shrink(sr, np.full(4, 1e-6))
    assert tau2 > 0 and np.allclose(B, 0.0, atol=1e-9) and np.allclose(st, sr)
    # Dispersion fully explained by noise: tau^2 truncated at 0 -> everything shrinks to the mean.
    st, B, tau2, bar = eb_shrink(np.array([0.1, -0.1, 0.05]), np.full(3, 5.0))
    assert tau2 == 0.0 and np.allclose(B, 1.0) and np.allclose(st, bar)
    # Method of moments: tau^2 = Var(SR) - mean(se^2).
    sr = np.array([0.0, 1.0, 2.0, 3.0])
    _, _, tau2, _ = eb_shrink(sr, np.full(4, 0.5))
    assert tau2 == pytest.approx(sr.var(ddof=1) - 0.25)


def test_eb_rejects_bad_input():
    with pytest.raises(ValueError):
        eb_shrink([], [])
    with pytest.raises(ValueError):
        eb_shrink([1.0, 2.0], [0.1])


# --------------------------------------------------------------------------- weighted Q20
def test_weighted_quantile_equal_weights_matches_numpy():
    rng = np.random.default_rng(0)
    v = rng.normal(size=37)
    for q in (0.0, 0.2, 0.5, 0.9, 1.0):
        assert weighted_quantile(v, np.ones_like(v), q) == pytest.approx(np.quantile(v, q, method="inverted_cdf"))


def test_weighted_quantile_respects_weights():
    v = np.array([-1.0, 0.0, 1.0, 2.0])
    assert weighted_quantile(v, [1, 1, 1, 1], 0.2) == -1.0
    assert weighted_quantile(v, [0.1, 0.1, 10, 10], 0.2) == 1.0     # mass on the good cells
    assert weighted_quantile(v, [10, 0.1, 0.1, 0.1], 0.2) == -1.0
    with pytest.raises(ValueError):
        weighted_quantile(v, [0, 0, 0, 0], 0.2)


# --------------------------------------------------------------------------- N_eff and clusters
def test_n_eff_bounds():
    ident = pd.DataFrame(np.eye(4), columns=list("abcd"), index=list("abcd"))
    ne = n_eff(ident, is_corr=True)
    assert ne["participation_ratio"] == pytest.approx(4.0) and ne["n_over_rho"] == pytest.approx(4.0)
    ones = pd.DataFrame(np.ones((4, 4)), columns=list("abcd"), index=list("abcd"))
    ne = n_eff(ones, is_corr=True)
    assert ne["participation_ratio"] == pytest.approx(1.0) and ne["n_over_rho"] == pytest.approx(1.0)
    c = np.full((5, 5), 0.6)
    np.fill_diagonal(c, 1.0)
    ne = n_eff(pd.DataFrame(c), is_corr=True)
    assert ne["n_over_rho"] == pytest.approx(5 / (1 + 4 * 0.6))
    assert 1.0 < ne["participation_ratio"] < 5.0


def test_correlation_clusters_single_linkage():
    c = pd.DataFrame([[1, .9, .1, .85], [.9, 1, .1, .2], [.1, .1, 1, .1], [.85, .2, .1, 1]],
                     index=list("abcd"), columns=list("abcd"), dtype=float)
    cl = correlation_clusters(c, 0.8)
    assert cl["a"] == cl["b"] == cl["d"] != cl["c"]
    w = cluster_weights(c)
    assert w["c"] == 1.0
    rho_bar = np.mean([.9, .85, .2])
    assert w["a"] == pytest.approx(1 / (1 + 2 * rho_bar))


# --------------------------------------------------------------------------- A_k
def _cells():
    labs = np.array(["up_low", "up_mid", "down_high"])
    return pd.Series(labs[np.arange(len(IDX)) % 3], index=IDX)


def test_cell_stats_and_score():
    rng = np.random.default_rng(1)
    rets = pd.DataFrame({"BTCUSDT": rng.normal(0.001, 0.02, len(IDX)),
                         "ETHUSDT": rng.normal(0.0005, 0.03, len(IDX))}, index=IDX)
    cells = _cells()
    st = cell_stats(rets, cells)
    assert len(st) == 6 and (st["T"] == 400).all()
    x = rets["BTCUSDT"][cells == "up_low"]
    sr = x.mean() / x.std(ddof=1)
    assert st.query("symbol == 'BTCUSDT' and cell == 'up_low'")["sr"].iloc[0] == pytest.approx(sr * math.sqrt(365))
    out = adaptability_score(rets, cells, n_free=3)
    t_years = len(IDX) / 365
    assert out["A_k"] == pytest.approx(out["q20"] - LAMBDA * 3 / math.sqrt(t_years))
    assert 0.0 <= out["frac_positive"] <= 1.0
    assert out["worst_regime"] in {"up_low", "up_mid", "down_high"}
    assert out["n_eff"]["n"] == 2
    # More free parameters -> lower A_k.
    assert adaptability_score(rets, cells, n_free=6)["A_k"] < out["A_k"]


def test_score_is_low_quantile_not_mean():
    """An engine that wins big in one regime and loses in the others gets a low A_k."""
    cells = _cells()
    rng = np.random.default_rng(2)
    mu = np.where(cells == "up_low", 0.01, -0.002)
    rets = pd.DataFrame({"A": mu + rng.normal(0, 0.005, len(IDX)),
                         "B": mu + rng.normal(0, 0.005, len(IDX))}, index=IDX)
    out = adaptability_score(rets, cells, n_free=1)
    assert out["sr_bar"] > 0 and out["q20"] < 0 and out["A_k"] < 0


def test_score_accepts_frame_of_cells_and_dsr():
    rng = np.random.default_rng(4)
    rets = pd.DataFrame({"BTCUSDT": rng.normal(0.001, 0.02, len(IDX))}, index=IDX)
    cells = _cells().to_frame("cell")
    out = adaptability_score(rets, cells, n_free=1, n_trials=20, sr_trials_var=0.002)
    assert 0.0 <= out["dsr"] <= 1.0
    empty = adaptability_score(rets.iloc[:10], cells, n_free=1)
    assert math.isnan(empty["A_k"])
