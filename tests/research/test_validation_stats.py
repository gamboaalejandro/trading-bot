"""Tests for apps.research.validation.stats (PLAN §6.2 R03).

Reference values come from the published examples of Bailey & Lopez de Prado:
- E[max Z_N] ~ 1.57 (N=10), 2.15 (N=36), 2.53 (N=100) (PLAN §6.2 R03).
- "The Deflated Sharpe Ratio" (2014) numerical example: annual SR 2.5,
  T=1250 daily observations, skew -3, kurt 10, N=100 trials, V[annual SR]=0.5
  -> E[max SR] ~ 0.1132 per day (1.7894 annual) and DSR ~ 0.9004.
- "Pseudo-Mathematics and Financial Charlatanism" (2014): with 5 years of
  data no more than 45 independent configurations should be tried for a
  target annual SR of 1 (MinBTL(45, 1) ~ 5 years), and MinBTL < 2 ln N / SR^2.
"""
import math

import numpy as np
import pytest

from apps.research.validation import stats as st


# --------------------------------------------------------------------------- #
# Sharpe, moments, SE
# --------------------------------------------------------------------------- #
def test_sharpe_ratio_matches_definition_and_annualizes():
    r = np.array([0.01, -0.005, 0.02, 0.0, 0.003, np.nan])
    clean = r[~np.isnan(r)]
    expected = clean.mean() / clean.std(ddof=1)
    assert st.sharpe_ratio(r) == pytest.approx(expected)
    assert st.sharpe_ratio(r, periods_per_year=365) == pytest.approx(expected * math.sqrt(365))
    assert st.annualize_sharpe(expected) == pytest.approx(expected * math.sqrt(365))
    assert st.deannualize_sharpe(st.annualize_sharpe(expected)) == pytest.approx(expected)


def test_sharpe_ratio_degenerate_returns_nan():
    assert math.isnan(st.sharpe_ratio([0.01]))
    assert math.isnan(st.sharpe_ratio([0.01, 0.01, 0.01]))


def test_moments_symmetric_fixture_and_plain_kurtosis():
    # Hand-built symmetric sample: skew 0; kurtosis = E[d^4]/E[d^2]^2
    r = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    skew, kurt = st.moments(r)
    assert skew == pytest.approx(0.0, abs=1e-12)
    assert kurt == pytest.approx((16 + 1 + 0 + 1 + 16) / 5 / (10 / 5) ** 2)  # 1.7
    rng = np.random.default_rng(0)
    skew_n, kurt_n = st.moments(rng.normal(size=200_000))
    assert skew_n == pytest.approx(0.0, abs=0.02)
    assert kurt_n == pytest.approx(3.0, abs=0.05)  # plain, not excess


def test_sharpe_se_normal_case_is_lo_formula():
    sr, T = 0.1, 500
    assert st.sharpe_se(sr, T) == pytest.approx(math.sqrt((1 + sr**2 / 2) / T))


def test_sharpe_se_negative_skew_fat_tails_increase_se():
    base = st.sharpe_se(0.1, 1000)
    assert st.sharpe_se(0.1, 1000, skew=-2.0, kurt=10.0) > base


def test_sharpe_se_matches_monte_carlo_for_skewed_returns():
    # Deterministic simulation of the estimator's sampling distribution
    # (unit test of a formula, not a backtest result).
    rng = np.random.default_rng(42)
    T, reps = 500, 4000
    k = 4.0  # gamma shape -> skew 2/sqrt(k) = 1, kurt 3 + 6/k = 4.5
    x = rng.gamma(k, 1.0, size=(reps, T)) - k + 0.2 * math.sqrt(k)
    true_sr = 0.2
    srs = x.mean(axis=1) / x.std(axis=1, ddof=1)
    se = st.sharpe_se(true_sr, T, skew=2 / math.sqrt(k), kurt=3 + 6 / k)
    assert srs.std(ddof=1) == pytest.approx(se, rel=0.06)


def test_sharpe_se_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        st.sharpe_se(0.1, 1)
    with pytest.raises(ValueError):
        # excess kurtosis passed by mistake with huge positive skew -> factor <= 0
        st.sharpe_se(1.0, 100, skew=5.0, kurt=0.0)


# --------------------------------------------------------------------------- #
# PSR
# --------------------------------------------------------------------------- #
def test_psr_is_half_at_threshold_and_normal_closed_form():
    assert st.psr(0.1, 252, -1.0, 6.0, sr_star=0.1) == pytest.approx(0.5)
    sr, T = 0.08, 730
    z = sr * math.sqrt(T - 1) / math.sqrt(1 + sr**2 / 2)
    expected = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    assert st.psr(sr, T, 0.0, 3.0) == pytest.approx(expected)


def test_psr_penalizes_negative_skew_and_fat_tails():
    normal = st.psr(0.08, 730, 0.0, 3.0)
    assert st.psr(0.08, 730, -2.0, 3.0) < normal
    assert st.psr(0.08, 730, 0.0, 12.0) < normal
    assert st.psr(0.08, 1460, 0.0, 3.0) > normal  # more data, more confidence


def test_psr_against_scipy_reference():
    sps = pytest.importorskip("scipy.stats")
    sr, T, g3, g4, star = 0.12, 400, -0.7, 7.5, 0.03
    z = (sr - star) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    assert st.psr(sr, T, g3, g4, star) == pytest.approx(sps.norm.cdf(z), abs=1e-12)


# --------------------------------------------------------------------------- #
# Expected max / DSR / MinBTL
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n, expected", [(10, 1.57), (36, 2.15), (100, 2.53)])
def test_expected_max_z_reference_values(n, expected):
    assert st.expected_max_z(n) == pytest.approx(expected, abs=0.006)


def test_expected_max_z_edge_cases_and_monotonic():
    assert st.expected_max_z(1) == 0.0
    vals = [st.expected_max_z(n) for n in (2, 5, 10, 40, 100, 1000)]
    assert all(b > a for a, b in zip(vals, vals[1:]))
    with pytest.raises(ValueError):
        st.expected_max_z(0)


def test_expected_max_z_close_to_monte_carlo():
    rng = np.random.default_rng(7)
    mc = rng.standard_normal((20_000, 40)).max(axis=1).mean()
    assert st.expected_max_z(40) == pytest.approx(mc, abs=0.05)


def test_dsr_bailey_lopez_de_prado_2014_example():
    sr_daily = 2.5 / math.sqrt(250)
    var_daily = 0.5 / 250
    sr0 = st.expected_max_sharpe(100, var_daily)
    assert sr0 == pytest.approx(0.1132, abs=5e-4)
    assert sr0 * math.sqrt(250) == pytest.approx(1.7894, abs=2e-3)
    assert st.dsr(sr_daily, 1250, -3.0, 10.0, var_daily, 100) == pytest.approx(0.9004, abs=1e-3)


def test_dsr_equals_psr_zero_with_single_trial_and_decreases_with_n():
    assert st.dsr(0.1, 500, 0.0, 3.0, 0.002, 1) == pytest.approx(st.psr(0.1, 500, 0.0, 3.0))
    vals = [st.dsr(0.1, 500, 0.0, 3.0, 0.002, n) for n in (1, 8, 40, 200)]
    assert all(b < a for a, b in zip(vals, vals[1:]))


def test_min_btl_published_example_and_bound():
    assert st.min_btl(45, 1.0) == pytest.approx(5.0, abs=0.02)
    for n in (2, 7, 45, 200, 1000):
        assert st.min_btl(n, 1.0) < 2 * math.log(n)
    # quadratic in 1/target
    assert st.min_btl(40, 0.5) == pytest.approx(4 * st.min_btl(40, 1.0))
    with pytest.raises(ValueError):
        st.min_btl(10, 0.0)


def test_min_track_record_hits_target_t_stat():
    sr, g3, g4 = 0.15, -0.5, 6.0
    n = st.min_track_record(sr, g3, g4, z=3.0)
    assert sr / st.sharpe_se(sr, n, g3, g4) == pytest.approx(3.0)
    assert st.min_track_record(-0.1) == math.inf


# --------------------------------------------------------------------------- #
# Stationary bootstrap
# --------------------------------------------------------------------------- #
def test_stationary_bootstrap_reproduces_mean_and_iid_se():
    rng = np.random.default_rng(3)
    x = rng.normal(0.001, 0.02, size=1500)
    dist = st.stationary_bootstrap(x, np.mean, block_mean=20, reps=4000, seed=1)
    assert dist.shape == (4000,)
    assert dist.mean() == pytest.approx(x.mean(), abs=3e-5)
    assert dist.std(ddof=1) == pytest.approx(x.std(ddof=1) / math.sqrt(x.size), rel=0.12)


def test_stationary_bootstrap_is_deterministic_and_seed_dependent():
    x = np.arange(100, dtype=float)
    a = st.stationary_bootstrap(x, np.mean, reps=50, seed=5)
    b = st.stationary_bootstrap(x, np.mean, reps=50, seed=5)
    c = st.stationary_bootstrap(x, np.mean, reps=50, seed=6)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_stationary_bootstrap_block_structure():
    # Draws are contiguous circular runs with mean length ~ block_mean.
    x = np.arange(1000, dtype=float)
    runs = []

    def mean_run(sample):
        breaks = np.flatnonzero(np.diff(sample) % 1000 != 1)
        runs.append(sample.size / (breaks.size + 1))
        return 0.0

    st.stationary_bootstrap(x, mean_run, block_mean=20, reps=200, seed=0)
    assert np.mean(runs) == pytest.approx(20, rel=0.15)


def test_stationary_bootstrap_captures_autocorrelation():
    rng = np.random.default_rng(11)
    n, phi = 2000, 0.6
    e = rng.normal(size=n)
    x = np.empty(n)
    x[0] = e[0]
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    iid = st.stationary_bootstrap(x, np.mean, block_mean=1, reps=2000, seed=0).std()
    blk = st.stationary_bootstrap(x, np.mean, block_mean=50, reps=2000, seed=0).std()
    # long-run SE / iid SE = sqrt((1+phi)/(1-phi)) = 2
    assert blk / iid == pytest.approx(2.0, rel=0.25)


def test_stationary_bootstrap_2d_keeps_rows_paired_and_rejects_nan():
    x = np.column_stack([np.arange(50.0), np.arange(50.0)])
    dist = st.stationary_bootstrap(x, lambda m: float(np.abs(m[:, 0] - m[:, 1]).max()), reps=100)
    assert np.all(dist == 0.0)
    with pytest.raises(ValueError):
        st.stationary_bootstrap(np.array([0.1, np.nan, 0.2]), np.mean)


def test_bootstrap_ci_contains_sample_mean():
    rng = np.random.default_rng(2)
    x = rng.normal(0.0005, 0.01, size=800)
    lo, hi = st.bootstrap_ci(x, np.mean, reps=2000, seed=0)
    assert lo < x.mean() < hi


def test_bootstrap_pvalue_diff_detects_edge_and_not_noise():
    rng = np.random.default_rng(9)
    b = rng.normal(0.0, 0.01, size=1500)
    a_edge = b + 0.002 + rng.normal(0, 0.002, size=1500)
    a_same = b + rng.normal(0, 0.002, size=1500)
    a_worse = b - 0.002 + rng.normal(0, 0.002, size=1500)
    assert st.bootstrap_pvalue_diff(a_edge, b, reps=2000) < 0.01
    assert st.bootstrap_pvalue_diff(a_worse, b, reps=2000) > 0.95
    assert 0.01 < st.bootstrap_pvalue_diff(a_same, b, reps=2000) < 0.99
    with pytest.raises(ValueError):
        st.bootstrap_pvalue_diff(a_edge[:-1], b)


# --------------------------------------------------------------------------- #
# Holm
# --------------------------------------------------------------------------- #
def test_holm_hand_computed():
    p = [0.01, 0.04, 0.03, 0.005]
    reject, adj = st.holm(p, alpha=0.05)
    # sorted: 0.005*4=0.02, 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> max-acc 0.06
    np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])
    np.testing.assert_array_equal(reject, [True, False, False, True])


def test_holm_matches_statsmodels():
    multitest = pytest.importorskip("statsmodels.stats.multitest")
    rng = np.random.default_rng(4)
    p = rng.uniform(0, 0.2, size=25)
    reject, adj = st.holm(p, alpha=0.05)
    ref_reject, ref_adj, _, _ = multitest.multipletests(p, alpha=0.05, method="holm")
    np.testing.assert_allclose(adj, ref_adj)
    np.testing.assert_array_equal(reject, ref_reject)


def test_holm_edge_cases():
    reject, adj = st.holm([])
    assert reject.size == 0 and adj.size == 0
    with pytest.raises(ValueError):
        st.holm([0.1, 1.2])
