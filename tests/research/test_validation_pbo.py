"""Tests for apps.research.validation.pbo (PLAN §6.2 R03).

- Pure-noise configurations: PBO ~ 0.5 (the IS winner is a random draw OOS).
- One dominant configuration: PBO ~ 0.
- The vectorised implementation equals a naive, literal transcription of the
  CSCV algorithm of Bailey, Borwein, Lopez de Prado & Zhu (2017).
"""
from itertools import combinations
from math import comb

import numpy as np
import pandas as pd
import pytest

from apps.research.validation.pbo import cscv, pbo_cscv


def _naive_pbo(M: np.ndarray, S: int) -> float:
    T, N = M.shape
    L = T // S
    M = M[T - L * S:]
    blocks = [M[i * L:(i + 1) * L] for i in range(S)]
    logits = []
    for c in combinations(range(S), S // 2):
        is_ = np.vstack([blocks[i] for i in c])
        oos = np.vstack([blocks[i] for i in range(S) if i not in c])
        sr_is = is_.mean(axis=0) / is_.std(axis=0, ddof=1)
        sr_oos = oos.mean(axis=0) / oos.std(axis=0, ddof=1)
        best = int(np.argmax(sr_is))
        rank = pd.Series(sr_oos).rank(method="average").iloc[best]
        w = rank / (N + 1)
        logits.append(np.log(w / (1 - w)))
    return float(np.mean(np.array(logits) <= 0))


def test_pbo_noise_is_about_half():
    vals = []
    for seed in range(30):
        rng = np.random.default_rng(seed)
        M = pd.DataFrame(rng.normal(0.0, 0.01, size=(1600, 20)))
        vals.append(pbo_cscv(M, S=16))
    assert np.mean(vals) == pytest.approx(0.5, abs=0.1)


def test_pbo_dominant_configuration_is_about_zero():
    rng = np.random.default_rng(0)
    M = rng.normal(0.0, 0.01, size=(1600, 20))
    M[:, 7] += 0.004  # daily SR ~0.4 vs 0 for the rest
    res = cscv(pd.DataFrame(M), S=16)
    assert res.pbo == pytest.approx(0.0, abs=0.01)
    assert np.all(res.best_index == 7)
    assert res.prob_oos_loss == 0.0


def test_cscv_shapes_and_combination_count():
    rng = np.random.default_rng(1)
    M = rng.normal(0, 0.01, size=(1605, 6))  # 5 oldest rows dropped
    res = cscv(M, S=16)
    assert res.n_combinations == comb(16, 8) == 12870
    assert res.rows_used == 1600
    assert res.logits.shape == (12870,)
    assert 0.0 <= res.pbo <= 1.0


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cscv_matches_naive_implementation(seed):
    rng = np.random.default_rng(seed)
    M = rng.normal(0.0002, 0.01, size=(243, 9))
    M[:, 2] += 0.001 * seed
    assert pbo_cscv(pd.DataFrame(M), S=8) == pytest.approx(_naive_pbo(M, 8))


def test_cscv_overfit_selection_has_negative_degradation():
    # Noise configurations: high IS Sharpe does not carry OOS.
    rng = np.random.default_rng(5)
    res = cscv(rng.normal(0, 0.01, size=(1600, 50)), S=16)
    assert res.degradation_slope < 0.0
    assert np.all(res.sr_is_best >= res.sr_oos_best.min())


def test_cscv_input_validation():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        cscv(rng.normal(size=(100, 1)))          # one configuration
    with pytest.raises(ValueError):
        cscv(rng.normal(size=(100, 4)), S=15)    # odd S
    with pytest.raises(ValueError):
        cscv(rng.normal(size=(20, 4)), S=16)     # too short
    bad = rng.normal(size=(200, 4))
    bad[3, 1] = np.nan
    with pytest.raises(ValueError):
        cscv(bad)
