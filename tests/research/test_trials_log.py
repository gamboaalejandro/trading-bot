"""Trials log: hash chain, quotas and the preloaded debate trials (PLAN R00)."""
import json

import pytest

from apps.research.config import get_config
from apps.research.validation.trials_log import (
    DEBATE_TRIALS,
    GENESIS_HASH,
    BudgetExceeded,
    TrialsLog,
    TrialsLogCorrupted,
)


@pytest.fixture
def log(tmp_path):
    return TrialsLog(tmp_path / "trials.jsonl")


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_debate_trials_preloaded(log):
    debate = log.trials("DEBATE")
    assert len(debate) == 8 == len(DEBATE_TRIALS)
    assert all(t["tag"] == "debate-exploratorio" for t in debate)
    assert log.n_total() == 8
    assert log.remaining("DEBATE") == 0
    assert log.records()[0]["prev_hash"] == GENESIS_HASH


def test_seeding_is_idempotent(tmp_path):
    path = tmp_path / "trials.jsonl"
    TrialsLog(path)
    TrialsLog(path)
    assert TrialsLog(path).n_total() == 8
    assert len(_lines(path)) == 8


def test_records_carry_required_fields(log):
    tid = log.register("TREND", {"config": "T3", "signal": "MIX", "sigma": 0.15, "band": 0.2}, agent="unit")
    rec = log.get(tid)
    for key in ("id", "ts", "agent", "family", "params", "data_commit", "git_sha", "metrics", "prev_hash", "hash"):
        assert key in rec
    assert rec["data_commit"]["spot"].startswith("4d33a56")
    assert rec["data_commit"]["futures"].startswith("735eb87")


def test_register_counts_and_ids(log):
    t1 = log.register("TREND", {"config": "T1"}, agent="unit")
    t2 = log.register("TREND", {"config": "T2"}, agent="unit")
    assert (t1, t2) == ("TREND-01", "TREND-02")
    assert log.n_total() == 10
    assert log.remaining("TREND") == 3


def test_identical_config_does_not_consume_budget(log):
    a = log.register("REGIME", {"config": "R1"}, agent="unit")
    b = log.register("REGIME", {"config": "R1"}, agent="other", tag="cost-x2")
    assert a == b
    assert log.n_family("REGIME") == 1


def test_budget_exceeded_on_family_quota(log):
    for i in range(2):
        log.register("SHORT", {"k": i}, agent="unit")
    assert log.remaining("SHORT") == 0
    with pytest.raises(BudgetExceeded):
        log.register("SHORT", {"k": 99}, agent="unit")
    assert log.n_family("SHORT") == 2


def test_debate_family_is_closed(log):
    with pytest.raises(BudgetExceeded):
        log.register("DEBATE", {"description": "one more"}, agent="unit")


def test_total_budget_is_enforced(tmp_path):
    log = TrialsLog(tmp_path / "t.jsonl", quotas={"DEBATE": 8, "A": 3, "B": 3}, total=10)
    log.register("A", {"i": 1}, agent="unit")
    log.register("B", {"i": 1}, agent="unit")
    with pytest.raises(BudgetExceeded):
        log.register("A", {"i": 2}, agent="unit")


def test_full_project_budget_is_40(log):
    cfg = get_config()
    for family, quota in cfg.budget.quotas.items():
        if family == "DEBATE":
            continue
        for i in range(quota):
            log.register(family, {"i": i}, agent="unit")
    assert log.n_total() == 40
    for family in cfg.budget.quotas:
        with pytest.raises(BudgetExceeded):
            log.register(family, {"i": "extra"}, agent="unit")


def test_unknown_family_rejected(log):
    with pytest.raises(KeyError):
        log.register("MOONSHOT", {}, agent="unit")
    with pytest.raises(KeyError):
        log.remaining("MOONSHOT")


def test_remaining_raises_when_quota_overspent(tmp_path):
    path = tmp_path / "t.jsonl"
    log = TrialsLog(path, quotas={"DEBATE": 8, "TREND": 5}, total=40)
    for i in range(3):
        log.register("TREND", {"i": i}, agent="unit")
    tight = TrialsLog(path, quotas={"DEBATE": 8, "TREND": 2}, total=40)
    with pytest.raises(BudgetExceeded):
        tight.remaining("TREND")


def test_edit_of_past_line_is_detected(log):
    log.register("TREND", {"config": "T1", "sigma": 0.15}, agent="unit")
    log.register("TREND", {"config": "T2"}, agent="unit")
    lines = _lines(log.path)
    rec = json.loads(lines[8])
    rec["params"]["sigma"] = 0.20  # tamper without fixing the hash
    lines[8] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(TrialsLogCorrupted):
        log.verify()
    with pytest.raises(TrialsLogCorrupted):
        log.register("TREND", {"config": "T3"}, agent="unit")


def test_rehashed_edit_breaks_the_chain(log):
    from apps.research.validation.trials_log import _canonical, _record_hash

    log.register("TREND", {"config": "T1"}, agent="unit")
    log.register("TREND", {"config": "T2"}, agent="unit")
    lines = _lines(log.path)
    rec = json.loads(lines[8])
    rec["params"]["config"] = "T1-edited"
    rec["hash"] = _record_hash(rec)  # attacker recomputes this line's hash
    lines[8] = _canonical(rec)
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(TrialsLogCorrupted):
        log.verify()


def test_deleted_line_is_detected(log):
    lines = _lines(log.path)
    del lines[3]
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(TrialsLogCorrupted):
        log.n_total()


def test_metrics_are_appended_not_rewritten(log):
    tid = log.register("TREND", {"config": "T3"}, agent="unit")
    before = _lines(log.path)
    log.record_metrics(tid, {"sharpe": 0.7, "max_dd": 0.18})
    after = _lines(log.path)
    assert after[: len(before)] == before
    assert len(after) == len(before) + 1
    assert log.get(tid)["metrics"]["sharpe"] == 0.7
    assert log.sharpe_values() == [0.7]
    assert log.n_total() == 9
    with pytest.raises(KeyError):
        log.record_metrics("TREND-99", {"sharpe": 1.0})


def test_non_finite_params_rejected(log):
    with pytest.raises(ValueError):
        log.register("TREND", {"sigma": float("nan")}, agent="unit")


def test_committed_project_log_is_intact():
    path = get_config().trials_log
    if not path.exists():
        pytest.skip("project trials log not created yet")
    log = TrialsLog(path, seed_debate=False)
    assert log.verify()
    debate = log.trials("DEBATE")
    assert len(debate) == 8
    assert all(t["tag"] == "debate-exploratorio" for t in debate)
    assert log.n_total() <= 40
