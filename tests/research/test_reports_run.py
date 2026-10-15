"""Reports and the experiment CLI (PLAN §6.2 R16).

The CLI tests run on a tiny deterministic fixture data root written to a temp
directory (plumbing only: these numbers are never research results) and on a
temp trials directory, so the project's trials log is never touched.
"""
import dataclasses
import json
import math

import numpy as np
import pandas as pd
import pytest

from apps.research import run as runmod
from apps.research.reports.report import (
    FUNDING_WARNING,
    SURVIVORSHIP_WARNING,
    ReportData,
    md_table,
    metrics_by_regime,
    metrics_by_year,
    render_report,
    write_report,
)
from apps.research.validation.holdout import HoldoutAlreadyOpened
from apps.research.validation.trials_log import BudgetExceeded, TrialsLog
from apps.research.validation.walkforward import make_folds

IDX = pd.date_range("2022-01-01", "2024-12-31", freq="D", tz="UTC")


def _toy():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, len(IDX)), index=IDX)
    sym = pd.DataFrame({"BTCUSDT": r * 0.6, "ETHUSDT": r * 0.4}, index=IDX)
    labs = np.array(["up_low", "down_high", "up_mid"])
    cells = pd.Series(labs[np.arange(len(IDX)) % 3], index=IDX)
    cells.iloc[:5] = None
    return r, sym, cells


# --------------------------------------------------------------------------- report
def test_report_has_year_symbol_regime_and_warnings():
    r, sym, cells = _toy()
    man = {"digest": "abc123", "files": {"spot/BTCUSDT_1d.csv": "f" * 64}}
    md = render_report(ReportData("E2", "TREND toy", r, market="futures", trial_ids=["TREND-01"],
                                  symbol_returns=sym, cells=cells, manifest=man, funding_used=True), reps=100)
    for section in ("## By year", "## By symbol", "## By regime", "## Data provenance", "## Warnings"):
        assert section in md
    for year in ("2022", "2023", "2024"):
        assert f"| {year} |" in md
    for s in ("BTCUSDT", "ETHUSDT"):
        assert f"| {s} |" in md
    for c in ("up_low", "down_high", "up_mid", "undefined"):
        assert f"| {c} |" in md
    assert SURVIVORSHIP_WARNING in md and FUNDING_WARNING in md
    assert "735eb87ffafb5c431162d7fec0d9bb3bf88d6d47" in md and "4d33a56f2b3930376fc778522770c6e84855be7e" in md
    assert "abc123" in md and "spot/BTCUSDT_1d.csv" in md
    assert "`TREND-01`" in md


def test_report_funding_warning_only_when_funding_used():
    r, _, _ = _toy()
    md = render_report(ReportData("E1", "spot only", r, market="spot"), reps=50)
    assert SURVIVORSHIP_WARNING in md and FUNDING_WARNING not in md
    assert "_Regime labels not available._" in md


def test_metrics_by_year_and_regime_values():
    r, _, cells = _toy()
    by_year = metrics_by_year(r, reps=50)
    assert list(by_year.index) == ["2022", "2023", "2024"]
    assert by_year.loc["2023", "n_days"] == 365
    lo, hi = by_year.loc["2022", "sharpe_ci"]
    assert lo < by_year.loc["2022", "sharpe"] < hi
    by_reg = metrics_by_regime(r, cells, reps=50)
    assert by_reg["n_days"].sum() == len(r)
    sub = r[cells == "up_low"]
    assert by_reg.loc["up_low", "sharpe"] == pytest.approx(sub.mean() / sub.std() * math.sqrt(365))


def test_write_report_files(tmp_path):
    r, sym, cells = _toy()
    p = write_report(ReportData("E2", "TREND T1-T5 spot", r, symbol_returns=sym, cells=cells), tmp_path,
                     reps=50, summary={"level": "C"})
    assert p == tmp_path / "E2" / "trend_t1_t5_spot.md"
    js = json.loads((tmp_path / "E2" / "trend_t1_t5_spot.json").read_text())
    assert js["level"] == "C" and js["data_commit"]["spot"].startswith("4d33a56")
    assert (tmp_path / "E2" / "trend_t1_t5_spot_returns.csv").exists()


def test_md_table_escapes_and_formats():
    df = pd.DataFrame({"a": [1.23456, float("nan")], "b": ["x|y", None]}, index=["r1", "r2"])
    out = md_table(df)
    assert "x/y" in out and "n/a" in out and "1.235" in out


# --------------------------------------------------------------------------- CLI fixtures
SYMS = ("BTCUSDT", "ETHUSDT")


def _bars(start, end, seed, base, freq="D"):
    idx = pd.date_range(start, end, freq=freq, tz="UTC")
    rng = np.random.default_rng(seed)
    scale = math.sqrt(pd.Timedelta(freq) / pd.Timedelta(days=1)) if freq != "D" else 1.0
    # Deterministic trending path (plumbing fixture only).
    logp = np.log(base) + np.cumsum(scale * (0.0008 * scale + 0.025 * rng.standard_normal(len(idx))))
    close = np.exp(logp)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    ts = (idx.as_unit("ms").asi8).astype("int64")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close,
                         "volume": 1e6})


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    for d in ("spot", "futures", "funding"):
        (root / d).mkdir()
    for i, s in enumerate(SYMS):
        _bars("2017-08-17", "2026-10-15", 10 + i, 4000.0 / (i + 1)).to_csv(root / "spot" / f"{s}_1d.csv", index=False)
        _bars("2019-09-08", "2026-09-10", 20 + i, 9000.0 / (i + 1)).to_csv(root / "futures" / f"{s}_1d.csv",
                                                                           index=False)
        for tf, freq in (("4h", "4h"), ("1h", "1h")):
            _bars("2025-08-01", "2026-10-15", 30 + i, 4000.0 / (i + 1), freq).to_csv(
                root / "spot" / f"{s}_{tf}.csv", index=False)
            _bars("2025-08-01", "2026-09-10 20:00" if tf == "4h" else "2026-09-10 23:00", 30 + i,
                  4004.0 / (i + 1), freq).to_csv(root / "futures" / f"{s}_{tf}.csv", index=False)
        t = pd.date_range("2019-09-10", "2026-09-10", freq="8h", tz="UTC")
        # Alternating calm / crowded 30-day blocks (APR ~11 % and ~44 %).
        rate = np.where((np.arange(len(t)) // 90) % 2 == 0, 1e-4, 4e-4)
        pd.DataFrame({"timestamp": t.as_unit("ms").asi8, "funding_rate": rate}).to_csv(
            root / "funding" / f"{s}.csv", index=False)
    return root


@pytest.fixture
def runner(tmp_path, data_root, monkeypatch):
    monkeypatch.setenv("RESEARCH_DATA_ROOT", str(data_root))
    monkeypatch.setattr(runmod.Runner, "common", property(lambda self: list(SYMS)))
    s = runmod.Settings(agent="pytest", trials_dir=tmp_path / "trials", reports_dir=tmp_path / "results",
                        reps=50, seeds=3, markets=("spot",))
    r = runmod.Runner(s)
    # Short windows keep the plumbing tests fast (the real split is tested in test_validation_walkforward).
    r.folds = make_folds("2025-12-01", "2026-03-09", 2, train_start="2025-10-01", n_folds=2)
    r.anchor = r.folds[0].train_start
    r.wf_start = "2025-12-01"
    splits = {**r.cfg.splits, "frozen_oos_spot": {"start": "2019-06-01", "end": "2020-08-31", "warmup_days": 360}}
    universe = {**r.cfg.universe, "spot": list(SYMS), "futures": list(SYMS)}
    r.cfg = dataclasses.replace(r.cfg, splits=splits, universe=universe)
    return r


@pytest.fixture
def two_configs(monkeypatch):
    orig = runmod._trend_specs
    monkeypatch.setattr(runmod, "_trend_specs", lambda runner, ids=("T1", "T3"): orig(runner, ids))


def test_trials_are_registered_before_any_computation(runner, monkeypatch):
    seen = {}

    def spy(r, market, symbols, with_spot=True):
        seen["trend"] = [t["params"]["config"] for t in r.trials.trials("TREND")]
        raise RuntimeError("stop before computing")

    monkeypatch.setattr(runmod, "_daily_data", spy)
    with pytest.raises(RuntimeError, match="stop before computing"):
        runmod.exp_e2(runner)
    assert seen["trend"] == ["T1", "T2", "T3", "T4", "T5"]
    assert (runner.trials_dir / "trials.jsonl").exists()


def test_budget_exceeded_stops_before_loading_data(runner, monkeypatch):
    for i in range(5):
        runner.trials.register("TREND", {"other": i}, agent="pytest")
    loaded = []
    monkeypatch.setattr(runmod, "_daily_data", lambda *a, **k: loaded.append(1))
    with pytest.raises(BudgetExceeded):
        runmod.exp_e2(runner)
    assert not loaded


def test_reregistering_same_config_is_idempotent(runner):
    specs = runmod._trend_specs(runner)
    ids = runner.register(specs)
    again = runner.register(runmod._trend_specs(runner))
    assert ids == again
    assert runner.trials.n_family("TREND") == 5


def test_stress_suite_is_mandatory():
    assert {"cost_x2", "delay_1", "worst_bar", "funding_x0.5", "funding_x2"} <= set(runmod.STRESS_RUNS)
    assert runmod.STRESS_RUNS["cost_x2"] == {"cost_mult": 2.0}
    assert runmod.STRESS_RUNS["delay_1"] == {"delay_bars": 2}


def test_e2_end_to_end_on_fixture_data(runner, two_configs):
    paths = runmod.exp_e2(runner)
    md = paths[0].read_text()
    for section in ("## By year", "## By symbol", "## By regime", "## Mandatory stress",
                    "## Gate (PLAN §5.6)", "## Walk-forward selections", "## Adaptability"):
        assert section in md, section
    assert SURVIVORSHIP_WARNING in md
    assert "735eb87ffafb5c431162d7fec0d9bb3bf88d6d47" in md
    for k in ("cost_x2", "delay_1", "worst_bar"):
        assert f"| {k} |" in md
    assert "Frozen spot 2017-2020" in md
    verdicts = json.loads((runner.reports_dir / "verdicts.json").read_text())
    v = verdicts["TREND:spot"]
    assert v["level"] in ("A", "B", "C") and "holdout" in v["failed_A"]   # holdout never opened
    log = TrialsLog(runner.trials_dir / "trials.jsonl")
    assert all(t["metrics"] and "sharpe" in t["metrics"] for t in log.trials("TREND"))
    assert not runner.holdout.is_open()


def test_futures_report_flags_unverified_funding(runner, monkeypatch):
    orig = runmod._trend_specs
    monkeypatch.setattr(runmod, "_trend_specs", lambda r, ids=("T3",): orig(r, ids))
    runner.s.markets = ("futures",)
    paths = runmod.exp_e2(runner)
    md = paths[0].read_text()
    assert FUNDING_WARNING in md
    assert "| funding_x0.5 |" in md and "| funding_x2 |" in md


def test_e9_opens_holdout_once(runner, monkeypatch):
    runner.s.finalists = ["TREND:T3:spot"]
    out = runmod.exp_e9(runner)
    assert out and runner.holdout.is_open()
    assert runner.holdout.info()["finalists"] == ["TREND:T3:spot"]
    with pytest.raises(HoldoutAlreadyOpened):
        runmod.exp_e9(runner)


def test_e8_and_e10_without_accepted_engines(runner):
    n0 = runner.trials.n_total()
    md8 = runmod.exp_e8(runner)[0].read_text()
    assert "Not run" in md8 and runner.trials.n_total() == n0
    md10 = runmod.exp_e10(runner)[0].read_text()
    assert "No engine reached level A or B" in md10 and "cash" in md10


def test_cli_parses_and_dispatches(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setitem(runmod.EXPERIMENTS, "E10", lambda r: called.setdefault("ok", r) and [])
    assert runmod.main(["E10", "--trials-dir", str(tmp_path / "t"), "--reports-dir", str(tmp_path / "r"),
                        "--reps", "10", "--market", "spot"]) == 0
    r = called["ok"]
    assert r.trials_dir == tmp_path / "t" and r.s.markets == ("spot",) and r.reps == 10
    with pytest.raises(SystemExit):
        runmod.main(["E11"])


# --------------------------------------------------------------------------- smoke tests of E3-E8
def _subset(monkeypatch, module, name, keys):
    full = getattr(module, name)
    monkeypatch.setattr(module, name, {k: full[k] for k in keys})


def test_e3_overlays_smoke(runner, monkeypatch):
    runner.s.families = ("REGIME",)
    md = runmod.exp_e3(runner)[0].read_text()
    assert "Overlay increment" in md and "## By regime" in md
    assert {t["params"]["regime"] for t in runner.trials.trials("REGIME")} == {"R1", "R2", "R3"}
    assert runner.trials.n_family("TREND") == 1                 # T3 base, registered once


def test_e3_fveto_reports_funding(runner, monkeypatch):
    from apps.research.strategies import overlays
    _subset(monkeypatch, overlays, "FVETO_CONFIGS", ["F2"])
    runner.s.families = ("FVETO",)
    md = runmod.exp_e3(runner)[0].read_text()
    assert FUNDING_WARNING in md


def test_e4_short_smoke(runner):
    md = runmod.exp_e4(runner)[0].read_text()
    assert FUNDING_WARNING in md and "| funding_x2 |" in md
    assert runner.trials.n_family("SHORT") == 2


def test_e5_breakout_smoke(runner, monkeypatch):
    from apps.research.strategies import breakout4h
    _subset(monkeypatch, breakout4h, "BRK4H_CONFIGS", ["B1", "B2"])
    runner.s.markets = ("futures",)
    md = runmod.exp_e5(runner)[0].read_text()
    assert "## Gate (PLAN §5.6)" in md and "| delay_1 |" in md
    assert runner.trials.n_family("BRK4H") == 2


def test_e6_carry_smoke(runner, monkeypatch):
    from apps.research.strategies import carry
    monkeypatch.setattr(carry, "CARRY_UNIVERSE", SYMS)
    md = runmod.exp_e6(runner)[0].read_text()
    assert "unverified P&L" in md and FUNDING_WARNING in md
    assert runner.trials.n_family("CARRY") == 3


def test_e7_pullback_and_shock_smoke(runner, monkeypatch):
    from apps.research.strategies import shock
    _subset(monkeypatch, shock, "SHOCK_CONFIGS", ["H1", "H2"])
    out = runmod.exp_e7(runner)
    assert len(out) == 2
    assert "Incremental net return per unit of turnover" in out[0].read_text()
    assert "PAPER ONLY" in out[1].read_text()
    assert runner.trials.n_family("PULLBACK") == 3 and runner.trials.n_family("SHOCK") == 2


def test_e8_selector_with_two_engines(runner):
    idx = pd.date_range("2025-10-01", "2026-03-09", tz="UTC")
    rng = np.random.default_rng(1)
    runner.reports_dir.mkdir(parents=True)
    for k in ("TREND:spot", "BRK4H:futures"):
        f = k.replace(":", "_") + ".csv"
        pd.Series(rng.normal(0.001, 0.01, len(idx)), index=idx, name="returns").to_csv(
            runner.reports_dir / f, index_label="date")
        runner.save_verdict(k, {"level": "B", "returns_csv": f})
    md = runmod.exp_e8(runner)[0].read_text()
    assert "Adopted" in md
    assert runner.trials.n_family("SELECTOR") == 3
    assert runner.load_verdicts()["SELECTOR"]["choice"] in ("M1", "M2", "M3")


def test_event_family_benchmarks_use_wf_oos_windows(runner, monkeypatch):
    """Checks 3 and 10 of BRK4H come from the per-fold choices on their test windows (no final-selection run)."""
    from apps.research.strategies import benchmarks, breakout4h
    _subset(monkeypatch, breakout4h, "BRK4H_CONFIGS", ["B1", "B2"])
    runner.s.markets = ("futures",)
    seen = {}
    orig_oos, orig_rnd, orig_gate = benchmarks.wf_event_oos, benchmarks.random_entry_event_wf_test, runmod.gate_report

    def spy_oos(selections, make, run):
        def run_spy(strat, s0, s1):
            seen.setdefault("windows", []).append((s0, s1))
            return run(strat, s0, s1)
        out = orig_oos(selections, make, run_spy)
        seen["oos"], seen["selections"] = out, selections
        return out

    def spy_rnd(*a, **k):
        seen["rnd"] = orig_rnd(*a, **k)
        return seen["rnd"]

    def spy_gate(gi, gb, *a, **k):
        seen["gi"], seen["gb"] = gi, gb
        return orig_gate(gi, gb, *a, **k)

    monkeypatch.setattr(benchmarks, "wf_event_oos", spy_oos)
    monkeypatch.setattr(benchmarks, "random_entry_event_wf_test", spy_rnd)
    monkeypatch.setattr(runmod, "gate_report", spy_gate)
    runmod.exp_e5(runner)
    folds = runner.folds
    assert seen["windows"] and all(s0 >= folds[0].test_start and s1 < folds[-1].test_end + pd.Timedelta(days=1)
                                   for s0, s1 in seen["windows"])
    assert seen["gb"].random_sharpes is seen["rnd"]
    assert seen["rnd"].candidate_sharpe == seen["oos"].sharpe
    tr = seen["gi"].trade_returns
    if seen["oos"].trade_returns is None:
        assert tr is None
    else:
        pd.testing.assert_series_equal(tr, seen["oos"].trade_returns)
