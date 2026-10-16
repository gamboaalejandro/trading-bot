"""Walk-forward, holdout lock and gate (PLAN §6.2 R14).

Unit tests use small deterministic return fixtures ("toy results"); no
backtest result is produced from synthetic prices.
"""
import json
import math

import numpy as np
import pandas as pd
import pytest

from apps.research.validation.gate import (
    SUBPERIODS,
    GateBench,
    GateInputs,
    evaluate_gate,
    gate_report,
    overlay_increment,
    trials_sharpe_var,
)
from apps.research.validation.holdout import (
    HoldoutAlreadyOpened,
    HoldoutLock,
    HoldoutLockCorrupted,
    HoldoutViolation,
    check_outside_holdout,
    holdout_window,
)
from apps.research.validation.trials_log import TrialsLog
from apps.research.validation.walkforward import (
    BacktestCandidate,
    Fold,
    WalkForwardError,
    apply_selection,
    make_folds,
    oos_weights,
    select_best_sharpe,
    validate_folds,
    walk_forward,
)

DAYS = pd.date_range("2020-09-01", "2026-03-09", freq="D", tz="UTC")


class Toy:
    """Candidate returning a fixed return series (the 'toy result')."""

    def __init__(self, name, r):
        self.name = name
        self.r = r
        self.calls = []

    def returns(self, panel, start, end):
        self.calls.append((start, end))
        return self.r[(self.r.index >= start) & (self.r.index <= end)]


def _noise(seed, mu=0.0, sd=0.02, index=DAYS):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mu, sd, len(index)), index=index)


# --------------------------------------------------------------------------- folds
def test_seventeen_quarterly_folds_without_overlap():
    folds = make_folds()
    assert len(folds) == 17
    assert folds[0].test_start == pd.Timestamp("2022-01-01", tz="UTC")
    assert folds[0].test_end == pd.Timestamp("2022-03-31", tz="UTC")
    assert folds[-1].test_start == pd.Timestamp("2026-01-01", tz="UTC")
    assert folds[-1].test_end == pd.Timestamp("2026-03-09", tz="UTC")
    for a, b in zip(folds, folds[1:]):
        assert b.test_start == a.test_end + pd.Timedelta(days=1)       # contiguous, no overlap
    for f in folds:
        assert f.train_start == pd.Timestamp("2020-09-01", tz="UTC")   # anchored
        assert f.train_end == f.test_start - pd.Timedelta(days=1)
    # The holdout (2026-03-10..) is never part of a test window.
    assert folds[-1].test_end < holdout_window("futures")[0]


def test_validate_folds_rejects_overlap_and_unanchored():
    t = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    overlapping = [(t("2020-09-01"), t("2021-12-31"), t("2022-01-01"), t("2022-03-31")),
                   (t("2020-09-01"), t("2022-03-30"), t("2022-03-31"), t("2022-06-30"))]
    with pytest.raises(WalkForwardError):
        validate_folds(overlapping)
    unanchored = [(t("2020-09-01"), t("2021-12-31"), t("2022-01-01"), t("2022-03-31")),
                  (t("2021-01-01"), t("2022-03-31"), t("2022-04-01"), t("2022-06-30"))]
    with pytest.raises(WalkForwardError):
        validate_folds(unanchored)
    with pytest.raises(WalkForwardError):
        validate_folds([(t("2022-01-01"), t("2022-02-01"), t("2022-01-15"), t("2022-03-31"))])


# --------------------------------------------------------------------------- selection
def test_selection_only_sees_training_data():
    a, b = Toy("A", _noise(1)), Toy("B", _noise(2))
    seen = []

    def spy(train):
        seen.append(train.index.max())
        return "A"

    folds = make_folds()
    wf = walk_forward([a, b], None, folds, select=spy)
    for f, last in zip(folds, seen):
        assert last <= f.train_end < f.test_start
    assert wf.selected == ["A"] * 17
    # OOS = test windows only, without duplicates, starting at the first test day.
    assert wf.oos_returns.index.min() == folds[0].test_start
    assert wf.oos_returns.index.is_unique
    assert wf.oos_returns.index.max() == folds[-1].test_end


def test_selection_follows_training_not_test_performance():
    """A config that is great in training and terrible OOS is still chosen: no peeking at the test."""
    idx = DAYS
    good_train = pd.Series(np.where(idx < pd.Timestamp("2022-01-01", tz="UTC"), 0.01, -0.01), index=idx)
    good_train += _noise(3, sd=0.001)
    flat = _noise(4, mu=0.0005, sd=0.001)
    wf = walk_forward([Toy("TRAIN_WINNER", good_train), Toy("OTHER", flat)], None, make_folds())
    assert wf.selections["selected"].iloc[0] == "TRAIN_WINNER"
    assert wf.oos_returns.loc["2022-01-01":"2022-03-31"].mean() < 0


def test_best_sharpe_selector_and_per_config_oos():
    hi = _noise(5, mu=0.003, sd=0.01)
    lo = _noise(6, mu=0.0, sd=0.01)
    wf = walk_forward([Toy("LO", lo), Toy("HI", hi)], None, make_folds())
    assert set(wf.selected) == {"HI"}
    assert list(wf.config_oos.columns) == ["LO", "HI"]
    pd.testing.assert_series_equal(wf.config_oos["HI"], wf.oos_returns.rename("HI"), check_names=False)
    assert select_best_sharpe(pd.DataFrame({"x": [np.nan] * 3})) == "x"


def test_fold_returns_hook_for_fitted_candidates():
    class Fitted:
        name = "FIT"

        def __init__(self):
            self.folds = []

        def fold_returns(self, panel, fold: Fold):
            self.folds.append(fold)
            r = _noise(7)
            return r[r.index <= fold.train_end], r[r.index >= fold.test_start]

    fit = Fitted()
    wf = walk_forward([fit, Toy("B", _noise(8))], None, make_folds())
    assert len(fit.folds) == 17
    assert len(wf.config_oos["FIT"].dropna()) == len(wf.config_oos["B"].dropna())


def test_names_must_be_unique_and_select_valid():
    with pytest.raises(WalkForwardError):
        walk_forward([Toy("A", _noise(1)), Toy("A", _noise(2))], None, make_folds())
    with pytest.raises(WalkForwardError):
        walk_forward([Toy("A", _noise(1))], None, make_folds(), select=lambda tr: "ZZZ")


def test_apply_selection_and_backtest_candidate_cache():
    calls = []

    class Res:
        def __init__(self, r, w):
            self.returns, self.weights = r, w

    def run(start, end, **kw):
        calls.append(kw)
        r = _noise(9) * (2.0 if kw.get("cost_mult") == 2.0 else 1.0)
        w = pd.DataFrame({"BTCUSDT": 0.5}, index=DAYS)
        return Res(r[(r.index >= start) & (r.index <= end)], w)

    cand = BacktestCandidate("C", run)
    wf = walk_forward([cand], None, make_folds())
    wf2 = walk_forward([cand], None, make_folds())
    assert len(calls) == 1                         # cached per (start, end, overrides)
    stressed = apply_selection(wf.selections, {"C": cand.returns(None, wf.folds[0].train_start,
                                                                 wf.folds[-1].test_end, cost_mult=2.0)})
    np.testing.assert_allclose(stressed.to_numpy(), 2.0 * wf.oos_returns.to_numpy())
    w = oos_weights(wf2.selections, {"C": cand.result(wf.folds[0].train_start, wf.folds[-1].test_end).weights})
    assert w.index.min() == wf.folds[0].test_start and (w["BTCUSDT"] == 0.5).all()


# --------------------------------------------------------------------------- holdout
def test_holdout_lock_opens_once(tmp_path):
    lock = HoldoutLock(tmp_path)
    assert not lock.is_open() and lock.info() is None
    grant = lock.open("tester", ["TREND:T3:spot"], reason="unit")
    assert lock.path == tmp_path / "holdout.lock"
    rec = lock.info()
    assert rec["agent"] == "tester" and rec["finalists"] == ["TREND:T3:spot"]
    assert rec["windows"]["futures"] == ["2026-03-10", "2026-09-10"]
    assert grant.record["seal"] == rec["seal"]
    with pytest.raises(HoldoutAlreadyOpened, match="tester"):
        lock.open("other", ["X"])
    # Another instance (another process) sees the same lock.
    with pytest.raises(HoldoutAlreadyOpened):
        HoldoutLock(tmp_path).open("other", ["X"])


def test_holdout_lock_tamper_and_validation(tmp_path):
    lock = HoldoutLock(tmp_path)
    with pytest.raises(ValueError):
        lock.open("tester", [])
    lock.open("tester", ["A"])
    rec = json.loads(lock.path.read_text())
    rec["agent"] = "someone-else"
    lock.path.chmod(0o644)
    lock.path.write_text(json.dumps(rec))
    with pytest.raises(HoldoutLockCorrupted):
        lock.info()
    with pytest.raises(HoldoutAlreadyOpened):      # corrupted counts as opened
        lock.open("again", ["A"])


def test_holdout_default_dir_is_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_TRIALS_DIR", str(tmp_path / "custom"))
    assert HoldoutLock().path == tmp_path / "custom" / "holdout.lock"
    monkeypatch.delenv("RESEARCH_TRIALS_DIR")
    assert HoldoutLock().path.parts[-3:] == ("data", "trials", "holdout.lock")


def test_runs_cannot_reach_the_holdout():
    check_outside_holdout("2026-03-09", "futures")
    with pytest.raises(HoldoutViolation):
        check_outside_holdout("2026-03-10", "futures")
    with pytest.raises(HoldoutViolation):
        check_outside_holdout("2026-06-01", "spot")


# --------------------------------------------------------------------------- gate
OOS = pd.date_range("2022-01-01", "2026-03-09", freq="D", tz="UTC")


@pytest.fixture
def trials(tmp_path):
    log = TrialsLog(tmp_path / "trials.jsonl")
    for i, sr in enumerate([0.2, 0.5, 0.1, 0.4]):
        tid = log.register("TREND", {"cfg": i}, agent="unit")
        log.record_metrics(tid, {"sharpe": sr})
    return log


def _bench(seed=11, vol=0.02):
    rng = np.random.default_rng(seed)
    btc = pd.Series(rng.normal(0.0, vol, len(OOS)), index=OOS)
    basket = pd.Series(rng.normal(0.0, vol, len(OOS)), index=OOS)
    return GateBench(btc, basket, np.random.default_rng(seed + 1).normal(0.0, 0.3, 100))


def _strong(seed=21):
    """Toy OOS returns with annual Sharpe ~ 4 and low drawdown."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0021, 0.01, len(OOS)), index=OOS)


def _family(r, n=4, seed=31):
    rng = np.random.default_rng(seed)
    cols = {"best": r}
    for i in range(n - 1):
        cols[f"c{i}"] = pd.Series(rng.normal(0.0, 0.01, len(OOS)), index=OOS)
    return pd.DataFrame(cols)


def _inputs(r, **kw):
    base = dict(name="toy", market="spot", returns=r, family_returns=_family(r),
                stress={"cost_x2": r - 0.0002, "delay_1": r - 0.0001}, adaptability=0.3)
    base.update(kw)
    return GateInputs(**base)


def test_gate_level_b_when_holdout_pending(trials):
    r = _strong()
    rep = gate_report(_inputs(r), _bench(), trials, reps=300)
    assert rep.checks_a["holdout"].status == "pending"
    assert rep.failed("A") == ["holdout"]
    assert rep.level == "B"
    assert evaluate_gate(_inputs(r), _bench(), trials, reps=300) == "B"


def test_gate_level_a_with_a_passing_holdout(trials):
    r = _strong()
    hold = pd.Series(np.full(180, 0.002), index=pd.date_range("2026-03-10", periods=180, tz="UTC"))
    rep = gate_report(_inputs(r, holdout_returns=hold), _bench(), trials, reps=300)
    assert rep.checks_a["holdout"].status == "pass"
    assert rep.level == "A", rep.failed("A")


def test_gate_level_c_for_noise(trials):
    r = pd.Series(np.random.default_rng(5).normal(0.0, 0.02, len(OOS)), index=OOS)
    rep = gate_report(_inputs(r, adaptability=-0.1), _bench(), trials, reps=300)
    assert rep.level == "C"
    assert not rep.checks_b["psr"].met


def test_gate_max_dd_uses_user_limit_20pct(trials):
    r = _strong().copy()
    r.iloc[400:430] = -0.01                        # ~26 % drawdown
    rep = gate_report(_inputs(r), _bench(), trials, reps=200)
    assert rep.checks_a["max_dd"].threshold == pytest.approx(0.20)
    assert rep.checks_a["max_dd"].status == "fail"
    rep_f = gate_report(_inputs(r, market="futures"), _bench(), trials, reps=200)
    assert rep_f.checks_a["max_dd"].threshold == pytest.approx(0.20)


def test_gate_missing_inputs_fail_never_pass(trials):
    r = _strong()
    rep = gate_report(_inputs(r, stress={}, family_returns=None, adaptability=None, frozen_required=True),
                      _bench(), trials, reps=200)
    for name in ("cost_stress", "delay_stress", "pbo", "frozen_spot"):
        assert rep.checks_a[name].status == "fail", name
    assert rep.checks_b["adaptability"].status == "fail"
    assert rep.level == "C"


def test_gate_stress_and_random_thresholds(trials):
    r = _strong()
    weak_cost = gate_report(_inputs(r, stress={"cost_x2": r * 0.3 - 0.001, "delay_1": r}), _bench(), trials, reps=200)
    assert weak_cost.checks_a["cost_stress"].status == "fail"
    bench = _bench()
    bench.random_sharpes = np.full(100, 10.0)      # random entries beat the candidate
    rep = gate_report(_inputs(r), bench, trials, reps=200)
    assert rep.checks_a["random_entries"].status == "fail" and rep.level == "C"


def test_gate_frozen_spot_and_subperiods(trials):
    r = _strong()
    idx = pd.date_range("2018-08-12", "2020-08-31", tz="UTC")
    rng = np.random.default_rng(3)
    frozen = pd.Series(rng.normal(0.002, 0.01, len(idx)), index=idx)
    bh = pd.Series(rng.normal(0.0, 0.01, len(idx)), index=idx)
    bh.iloc[100:200] = -0.01                       # B&H with a deep drawdown
    bench = _bench()
    bench.frozen_bh = bh
    rep = gate_report(_inputs(r, frozen_required=True, frozen_returns=frozen), bench, trials, reps=200)
    assert rep.checks_a["frozen_spot"].status == "pass"
    assert rep.checks_b["frozen_spot"].status == "pass"
    assert set(SUBPERIODS) == {"2022", "2023-24", "2025-26"}
    assert "2023-24/basket" in rep.checks_a["no_catastrophe"].detail


def test_gate_dsr_uses_trials_log(trials):
    var = trials_sharpe_var(trials)
    vals = np.array([0.2, 0.5, 0.1, 0.4]) / math.sqrt(365)
    assert var == pytest.approx(vals.var(ddof=1))
    rep = gate_report(_inputs(_strong()), _bench(), trials, reps=200)
    assert rep.summary["n_trials"] == trials.n_total() == 12   # 8 debate + 4


def test_overlay_increment_accepts_risk_reduction():
    rng = np.random.default_rng(9)
    base = pd.Series(rng.normal(0.001, 0.02, len(OOS)), index=OOS)
    base.iloc[300:340] = -0.02                     # crash the overlay avoids
    over = base.copy()
    over.iloc[300:340] = -0.005
    res = overlay_increment(over, base, pbo=0.1, reps=300)
    assert res["accepted"] and res["p_maxdd"] < 0.05
    rejected = overlay_increment(over, base, pbo=0.6, reps=300)
    assert not rejected["accepted"]
    same = overlay_increment(base, base, pbo=0.1, reps=300)
    assert not same["accepted"]


def test_overlay_rejected_increment_gives_level_c(trials):
    r = _strong()
    rep = gate_report(_inputs(r, overlay_base=r), _bench(), trials, reps=200)
    assert rep.overlay is not None and not rep.overlay["accepted"]
    assert rep.level == "C"
