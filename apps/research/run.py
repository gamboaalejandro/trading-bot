"""
Experiment runner of the research harness (PLAN.md §6.3, task R16).

    python -m apps.research.run <E0..E10> [--market spot|futures|both] [--agent NAME]
                                [--trials-dir DIR] [--reports-dir DIR] [--reps N] [--seeds N]
                                [--finalists FAMILY:CONFIG:MARKET ...]

This is the ONLY entry point allowed to compute anything on 2022+ data
(PLAN §6.1). Rules enforced here:

- Every configuration is registered in the append-only :class:`TrialsLog`
  BEFORE any data is loaded or any metric computed (re-registering the same
  configuration is idempotent and consumes no budget; a quota overrun raises
  :class:`BudgetExceeded` and nothing is computed).
- Walk-forward and debug runs never reach the holdout
  (:func:`check_outside_holdout`; data are loaded up to 2026-03-09 only). The
  holdout is opened once, by E9, through :class:`HoldoutLock`.
- The mandatory stress of §5.4 runs with every family: costs x2, +1 bar delay,
  stop at the worst price of the bar and, in perps, funding x0.5 / x2 (they
  are robustness runs of the same configuration, not new trials).
- Reports (markdown + JSON summary + OOS returns CSV) go to
  ``docs/research/results/<experiment>/``; every report carries the data
  commits, the survivorship warning and, when funding is involved, the
  "funding not verified" warning. Gate verdicts are collected in
  ``docs/research/results/verdicts.json`` for E8 (SELECTOR) and E10.

Experiments: E0 data audit, E1 benchmarks, E2 TREND T1-T5 (WF spot and perp on
the 9 common coins, spot-vs-perp comparison, frozen spot 2017-2020), E3
REGIME / FVETO over T3, E4 SHORT, E5 BRK4H, E6 CARRY (paper, unverified
funding), E7 PULLBACK / SHOCK, E8 SELECTOR vs parity, E9 holdout (finalists,
once), E10 final report.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from apps.research.config import get_config
from apps.research.data.loader import DataError, load_funding, load_panel
from apps.research.data.manifest import manifest_from_frames
from apps.research.engine.costs import CostModel
from apps.research.engine.portfolio_bt import BTResult, run_portfolio_bt
from apps.research.features.regime import ex_ante_cells
from apps.research.portfolio.risk import load_risk_config
from apps.research.reports.report import ReportData, md_table, metrics_table, write_report
from apps.research.validation.adaptability import adaptability_score
from apps.research.validation.gate import GateBench, GateInputs, gate_report
from apps.research.validation.holdout import HoldoutLock, check_outside_holdout
from apps.research.validation.metrics import compounded, max_drawdown, sharpe
from apps.research.validation.pbo import pbo_cscv
from apps.research.validation.stats import bootstrap_pvalue_diff, stationary_bootstrap
from apps.research.validation.trials_log import TrialsLog
from apps.research.validation.walkforward import (
    TRAIN_ANCHOR,
    BacktestCandidate,
    apply_selection,
    make_folds,
    oos_weights,
    walk_forward,
)

__all__ = [
    "EXPERIMENTS",
    "DEFAULT_REPORTS_DIR",
    "Settings",
    "Runner",
    "ConfigSpec",
    "STRESS_RUNS",
    "symbol_contributions",
    "main",
]

DEFAULT_REPORTS_DIR = get_config().reports_dir   # ${REPO}/docs/research/results
ONE_DAY = pd.Timedelta(days=1)
#: Mandatory stress of PLAN §5.4 (overrides of the same configuration; not trials).
STRESS_RUNS: dict[str, dict] = {
    "cost_x2": {"cost_mult": 2.0},
    "delay_1": {"delay_bars": 2},
    "worst_bar": {"stop_fill": "worst_bar"},
    "funding_x0.5": {"funding_mult": 0.5},
    "funding_x2": {"funding_mult": 2.0},
}
FUNDING_STRESS = ("funding_x0.5", "funding_x2")
TAIL_DAYS = ("2021-05-19", "2022-11-09", "2025-10-10")


# --------------------------------------------------------------------------- settings
@dataclass
class Settings:
    agent: str = "run.py"
    trials_dir: Optional[Path] = None
    reports_dir: Path = DEFAULT_REPORTS_DIR
    data_root: Optional[Path] = None
    reps: Optional[int] = None
    seeds: int = 100
    markets: tuple = ("spot", "futures")
    finalists: Sequence[str] = ()
    families: Sequence[str] = ()


@dataclass
class ConfigSpec:
    """
    One preregistered configuration. ``params`` is what goes into the trials
    log (it must be identical every time the configuration is run);
    ``build(market, data)`` returns ``run(start, end, **overrides) -> BTResult``.
    """

    family: str
    config_id: str
    params: dict
    build: Callable[[str, dict], Callable[..., BTResult]]
    n_free_params: int = 0
    trial_id: Optional[str] = None


def symbol_contributions(result: BTResult, closes: pd.DataFrame) -> pd.DataFrame:
    """
    Daily contribution of each symbol to the NAV return, net of its own costs:
    ``w_{i,t-1} * r_{i,t} - costs_{i,t} / NAV_{t-1}`` (approximation: the
    rebalance happens at the open). Funding is a signed cash flow.
    """
    w = result.weights.astype(float).fillna(0.0)
    c = closes.reindex(index=w.index, columns=w.columns).astype(float)
    r = (c / c.shift(1) - 1.0).fillna(0.0)
    contrib = w.shift(1).fillna(0.0) * r
    if result.costs is not None and len(result.costs):
        cost = result.costs.copy()
        net = (cost["commission"] + cost["slippage"] - cost["funding"]).unstack("symbol")
        net = net.reindex(index=w.index, columns=w.columns).fillna(0.0)
        nav_prev = result.equity.shift(1)
        nav_prev.iloc[0] = result.meta.get("initial_equity", result.equity.iloc[0])
        contrib = contrib - net.div(nav_prev, axis=0)
    return contrib


def _closes(panel: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame({s: df["close"] for s, df in panel.items()}).astype(float)


def _cut(panel: Mapping[str, pd.DataFrame], end) -> dict:
    t = pd.Timestamp(end, tz="UTC")
    return {s: df[df.index <= t] for s, df in panel.items()}


def _cut_funding(funding: Mapping[str, pd.Series], end) -> dict:
    t = pd.Timestamp(end, tz="UTC") + ONE_DAY
    return {s: f[f.index < t] for s, f in funding.items()}


def _funding_daily(funding: Mapping[str, pd.Series], index: pd.DatetimeIndex) -> pd.DataFrame:
    cols = {}
    for s, f in funding.items():
        cols[s] = f.groupby(f.index.floor("D")).sum().reindex(index).fillna(0.0)
    return pd.DataFrame(cols, index=index)


# --------------------------------------------------------------------------- runner
class Runner:
    """Holds the shared state of one CLI invocation (config, trials log, holdout lock)."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.cfg = get_config()
        if settings.data_root is not None:
            os.environ["RESEARCH_DATA_ROOT"] = str(settings.data_root)
        trials_dir = Path(settings.trials_dir) if settings.trials_dir else self.cfg.trials_log.parent
        self.trials_dir = trials_dir
        self.trials = TrialsLog(trials_dir / self.cfg.trials_log.name)
        self.holdout = HoldoutLock(trials_dir)
        self.reports_dir = Path(settings.reports_dir)
        self.reps = int(settings.reps if settings.reps is not None else self.cfg.bootstrap.get("reps", 10_000))
        c = self.cfg.costs
        self.cost = CostModel(spot_fee=float(c["spot_fee"]), fut_taker=float(c["fut_taker"]),
                              fut_maker=float(c["fut_maker"]),
                              slip_bps={t["tier"]: float(t["bps"]) for t in c["slippage_tiers"]})
        self.risk = load_risk_config()
        wf = self.cfg.splits["walk_forward"]
        self.wf_start, self.wf_end = str(wf["start"]), str(wf["end"])
        self.folds = make_folds(self.wf_start, self.wf_end, int(wf["fold_months"]),
                                train_start=TRAIN_ANCHOR, n_folds=int(wf["n_folds"]))
        self.anchor = self.folds[0].train_start

    # ------------------------------------------------------------ bookkeeping
    @property
    def common(self) -> list[str]:
        u = self.cfg.universe
        excl = set(u.get("funding_excluded", ()))
        return [s for s in u["spot"] if s in u["futures"] and s not in excl]

    def register(self, specs: Sequence[ConfigSpec], tag: str = "") -> list[str]:
        """Register every configuration BEFORE computing (PLAN §6.1)."""
        ids = []
        for spec in specs:
            spec.trial_id = self.trials.register(spec.family, spec.params, agent=self.s.agent, tag=tag)
            ids.append(spec.trial_id)
        return ids

    def _verdicts_path(self) -> Path:
        return self.reports_dir / "verdicts.json"

    def load_verdicts(self) -> dict:
        p = self._verdicts_path()
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def save_verdict(self, key: str, verdict: dict) -> None:
        v = self.load_verdicts()
        v[key] = verdict
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._verdicts_path().write_text(json.dumps(v, indent=2, sort_keys=True, default=str), encoding="utf-8")

    # ------------------------------------------------------------ data
    def daily_panel(self, symbols: Sequence[str], market: str, end: Optional[str] = None) -> dict:
        end = end or self.wf_end
        if end == self.wf_end:
            check_outside_holdout(end, market)
        return load_panel(symbols, market, "1d", None, end, allow_late_start=True)

    def funding(self, symbols: Sequence[str], end: Optional[str] = None) -> dict:
        excl = set(self.cfg.universe.get("funding_excluded", ()))
        out = {}
        for s in symbols:
            if s in excl:
                continue
            out[s] = load_funding(s)
        return _cut_funding(out, end or self.wf_end)

    # ------------------------------------------------------------ families
    def weight_spec(self, family: str, config_id: str, params: dict, make: Callable[[dict], Any],
                    sizing, n_free: int) -> ConfigSpec:
        """Spec of a target-weight configuration run by :func:`run_portfolio_bt`."""

        def build(market: str, data: dict) -> Callable[..., BTResult]:
            def run(start, end, cost_mult: float = 1.0, delay_bars: int = 1, stop_fill: str = "gap_aware",
                    funding_mult: float = 1.0) -> BTResult:
                cost = self.cost.stressed(cost_mult, funding_mult)
                return run_portfolio_bt(make(data), data["panel"], market, cost, sizing, self.risk, start, end,
                                        stop_fill, delay_bars,
                                        funding=data.get("funding") if market == "futures" else None,
                                        trial_id=spec.trial_id)
            return run

        spec = ConfigSpec(family, config_id, params, build, n_free)
        return spec

    def run_family(self, experiment: str, family: str, specs: Sequence[ConfigSpec], market: str, data: dict,
                   *, frozen: bool = False, overlay_base: Optional[pd.Series] = None, title: str = "",
                   funding_used: bool = False, notes: Sequence[str] = (), event: bool = False,
                   stress_keys: Optional[Sequence[str]] = None, per_symbol: bool = True) -> dict:
        """
        Walk-forward of one family on ``data`` (already loaded, trials already
        registered), stress suite, benchmarks, gate, A_k, report and verdict.
        """
        panel = data["panel"]
        cands = [BacktestCandidate(s.config_id, s.build(market, data), dict(s.params), s.n_free_params,
                                   s.trial_id) for s in specs]
        wf = walk_forward(cands, panel, self.folds)
        full_end = self.folds[-1].test_end
        by_name = {c.name: c for c in cands}

        # Mandatory stress (§5.4) on every configuration, re-using the WF selections.
        keys = list(stress_keys) if stress_keys is not None else [
            k for k in STRESS_RUNS if market == "futures" or k not in FUNDING_STRESS]
        stress = {}
        for k in keys:
            per_cfg = {c.name: c.returns(panel, self.anchor, full_end, **STRESS_RUNS[k]) for c in cands}
            stress[k] = apply_selection(wf.selections, per_cfg)

        # Record the OOS metrics of every configuration (after computing; trial already logged).
        for spec in specs:
            r = wf.config_oos[spec.config_id].dropna()
            self.trials.record_metrics(spec.trial_id, {
                "experiment": experiment, "market": market, "sharpe": _finite_or_none(sharpe(r)),
                "max_dd": _finite_or_none(max_drawdown(r)), "n_days": int(len(r))})

        results = {c.name: c.result(self.anchor, full_end) for c in cands}
        closes = _closes(data.get("closes_panel", panel))
        oos = wf.oos_returns.dropna()
        w_oos = oos_weights(wf.selections, {n: res.weights for n, res in results.items()})

        # Benchmarks: vol-matched B&H (BTC + basket) and random entries.
        from apps.research.strategies.benchmarks import (
            random_entry_event_wf_test,
            random_entry_weights_test,
            vol_matched_benchmarks,
            wf_event_oos,
        )
        bench_panel = data.get("bench_panel", panel)
        vm = vol_matched_benchmarks(oos, bench_panel)
        final = wf.final_selection
        if event:
            # Checks 3 and 10 must use OOS data only: the configuration chosen in each fold, run on
            # that fold's test window, and random entries with the same per-window schedule. The
            # final selection over the whole window would be in-sample (look-ahead through selection).
            def run_window(strat, s0, s1):
                return data["run_strategy"](strat, start=s0, end=s1)

            cand_oos = wf_event_oos(wf.selections, data["make"], run_window)
            rnd = random_entry_event_wf_test(data["make"], run_window, panel, wf.selections,
                                             n_seeds=self.s.seeds, candidate=cand_oos)
            trade_returns = cand_oos.trade_returns
        else:
            fee = self.cost.fee_rate(market) + 5e-4
            w_day = w_oos.groupby(w_oos.index.floor("D")).last() if len(w_oos) else w_oos
            fd = _funding_daily(data.get("funding") or {}, w_day.index) if market == "futures" else None
            rnd = random_entry_weights_test(w_day, closes, n_seeds=self.s.seeds, cost_rate=fee, funding_daily=fd)
            trade_returns = None

        # Frozen spot 2017-2020 (daily families): same frozen configuration.
        frozen_r = frozen_bh = None
        if frozen:
            frozen_r, frozen_bh = self.frozen_run(by_name[final], data)

        # Regime cells, per-symbol contributions and A_k.
        btc = data.get("btc")
        cells = ex_ante_cells(btc) if btc is not None else None
        contrib = None
        if per_symbol and not event:
            parts = {n: symbol_contributions(res, closes) for n, res in results.items()}
            contrib = oos_weights(wf.selections, parts)
        adapt = None
        if cells is not None:
            # Engines without a per-coin decomposition (event, carry) use the portfolio series as one cell column.
            cell_input = contrib if contrib is not None and not contrib.empty else oos.to_frame(family)
            adapt = adaptability_score(cell_input, cells, by_name[final].n_free_params)
        a_k = adapt.get("A_k") if adapt else None

        gi = GateInputs(name=f"{family}-{market}", market=market, returns=oos, family_returns=wf.config_oos.dropna(),
                        stress=stress, frozen_returns=frozen_r, frozen_required=frozen, trade_returns=trade_returns,
                        adaptability=a_k, overlay_base=overlay_base)
        gb = GateBench(vm["BTC"], vm["basket"], rnd, frozen_bh)
        greport = gate_report(gi, gb, self.trials, reps=self.reps)

        cost_tot = {}
        for n, res in results.items():
            if n == final and len(res.costs):
                tot = res.costs[["commission", "slippage", "funding"]].sum()
                cost_tot = {k: float(v) for k, v in tot.items()}
        exposure = {"gross_mean": float(w_oos.abs().sum(axis=1).mean()) if len(w_oos) else float("nan"),
                    "turnover_daily": float(w_oos.diff().abs().sum(axis=1).mean()) if len(w_oos) else float("nan"),
                    "n_trades_final_cfg": int(len(results[final].trades))}
        tail = _tail_table({n: res for n, res in results.items()})
        sections = [("Frozen spot 2017-2020 (frozen configuration " + final + ")", md_table(metrics_table(
            {"candidate": frozen_r, "B&H BTC vol-matched": frozen_bh}, 500),
            pct_cols=["total_return", "cagr", "vol", "max_dd", "cvar95"])) if frozen_r is not None else
            ("Frozen spot 2017-2020", "_not applicable_")]
        all_files = list(panel.values()) + list((data.get("funding") or {}).values())
        rd = ReportData(
            experiment=experiment, title=title or f"{family} {market}", returns=oos, market=market,
            trial_ids=[s.trial_id for s in specs], symbol_returns=contrib, cells=cells,
            manifest=manifest_from_frames(all_files), funding_used=funding_used or market == "futures",
            configs=wf.config_oos, selections=wf.selections, stress=stress, costs=cost_tot, exposure=exposure,
            bench={"B&H BTC (vol-matched)": vm["BTC"], "B&H basket (vol-matched)": vm["basket"]},
            random_entry=rnd, tail_events=tail, gate=greport, adaptability=adapt, sections=sections,
            notes=list(notes), holdout_status="opened" if self.holdout.is_open() else "closed (not used)")
        summary = {"family": family, "level": greport.level, "final_selection": final,
                   "sharpe": greport.summary.get("sharpe"), "max_dd": greport.summary.get("max_dd"),
                   "A_k": a_k, "failed_A": greport.failed("A"), "failed_B": greport.failed("B"),
                   "configs": {s.config_id: s.params for s in specs}}
        path = write_report(rd, self.reports_dir, reps=min(self.reps, 2000), summary=summary)
        returns_csv = str(path.with_name(path.stem + "_returns.csv").relative_to(self.reports_dir))
        self.save_verdict(f"{family}:{market}", {**summary, "report": str(path.relative_to(self.reports_dir)),
                                                 "returns_csv": returns_csv, "market": market,
                                                 "experiment": experiment})
        return {"wf": wf, "gate": greport, "report": path, "oos": oos, "stress": stress, "results": results}

    def frozen_run(self, cand: BacktestCandidate, data: dict) -> tuple[pd.Series, pd.Series]:
        """Frozen spot 2017-08-17..2020-08-31 run of a daily configuration (warm-up 360 days)."""
        from apps.research.strategies.benchmarks import vol_matched_bh

        fz = self.cfg.splits["frozen_oos_spot"]
        start = pd.Timestamp(fz["start"], tz="UTC") + pd.Timedelta(days=int(fz["warmup_days"]))
        end = pd.Timestamp(fz["end"], tz="UTC")
        spot = data.get("spot_panel")
        if spot is None:
            spot = self.daily_panel(self.common, "spot")
        min_hist = int(self.cfg.universe.get("min_history_days", 365))
        panel = {s: df for s, df in _cut(spot, fz["end"]).items()
                 if len(df) and df.index[0] <= end - pd.Timedelta(days=min_hist)}
        if "BTCUSDT" not in panel:
            raise DataError("frozen spot run needs BTCUSDT spot data")
        funding = _cut_funding(data["funding"], fz["end"]) if data.get("funding") else None
        spec_data = {**data, "panel": panel, "funding": funding, "btc": panel["BTCUSDT"]}
        run = data["frozen_build"](cand.name, spec_data)
        res = run(start, end)
        r = res.returns.dropna()
        btc = _closes(panel)["BTCUSDT"]
        bh, _ = vol_matched_bh(r, (btc / btc.shift(1) - 1.0).rename("BTC"))
        return r, bh


def _finite_or_none(x) -> Optional[float]:
    return float(x) if x is not None and math.isfinite(float(x)) else None


def _tail_table(results: Mapping[str, BTResult]) -> pd.DataFrame:
    rows = []
    for name, res in results.items():
        r = res.returns
        for d in TAIL_DAYS:
            t = pd.Timestamp(d, tz="UTC")
            if t in r.index:
                c = res.meta.get("counters", {})
                rows.append({"config": name, "day": d, "return": float(r.loc[t]),
                             "stops_total": c.get("stops"), "liq_rejected_total": c.get("liq_rejected")})
    return pd.DataFrame(rows).set_index(["config", "day"]) if rows else pd.DataFrame()


# --------------------------------------------------------------------------- experiments
def _trend_specs(runner: Runner, ids: Sequence[str] = ("T1", "T2", "T3", "T4", "T5")) -> list[ConfigSpec]:
    from apps.research.strategies.trend import TREND_CONFIGS, make_trend, sizing_config

    specs = []
    for cid in ids:
        c = TREND_CONFIGS[cid]
        params = {"config": cid, "signal": c.signal, "sigma_target": c.sigma_target, "band": c.band}
        specs.append(runner.weight_spec("TREND", cid, params, lambda data, cid=cid: make_trend(cid),
                                        sizing_config(cid), make_trend(cid).n_free_params))
    return specs


def _daily_data(runner: Runner, market: str, symbols: Sequence[str], with_spot: bool = True) -> dict:
    panel = runner.daily_panel(symbols, market)
    funding = runner.funding(symbols)
    data = {"panel": panel, "funding": funding, "btc": panel.get("BTCUSDT")}
    if with_spot:
        data["spot_panel"] = panel if market == "spot" else runner.daily_panel(symbols, "spot")
    return data


def exp_e0(runner: Runner) -> list[Path]:
    """E0: data audit (coverage, BNB funding, funding intervals, volume == 0). Not a trial."""
    from apps.research.data.loader import load_ohlcv

    u = runner.cfg.universe
    rows = []
    frames = []
    for market in ("spot", "futures"):
        for s in u[market]:
            for tf in ("1d", "4h", "1h", "15m"):
                try:
                    df = load_ohlcv(s, market, tf)
                except DataError as exc:
                    rows.append({"market": market, "symbol": s, "tf": tf, "status": f"missing: {exc}"[:80]})
                    continue
                frames.append(df)
                rows.append({"market": market, "symbol": s, "tf": tf, "status": "ok",
                             "first": df.index[0], "last": df.index[-1], "bars": int(len(df)),
                             "nan_bars": int(df["close"].isna().sum()), "proxy": bool(df.attrs.get("proxy", False))})
    cov = pd.DataFrame(rows)
    frows = []
    for s in u["futures"]:
        try:
            f = load_funding(s, allow_bnb=True)
        except DataError as exc:
            frows.append({"symbol": s, "status": str(exc)[:80]})
            continue
        frames.append(f)
        gaps = f.index.to_series().diff().dropna()
        frows.append({"symbol": s, "status": "ok", "n": int(len(f)), "median_bps": float(f.median()) * 1e4,
                      "mean_apr": float(f.mean()) * 3 * 365,
                      "share_zero": float((f == 0).mean()), "share_1e-4": float((f.round(8) == 1e-4).mean()),
                      "share_8h": float((gaps == pd.Timedelta(hours=8)).mean()),
                      "other_intervals": int((gaps != pd.Timedelta(hours=8)).sum()),
                      "annual_sums": "; ".join(f"{y}:{v:.3f}" for y, v in f.groupby(f.index.year).sum().items())})
    fund = pd.DataFrame(frows)
    rd = ReportData("E0", "Data audit", pd.Series(dtype=float), market="spot+futures",
                    manifest=manifest_from_frames(frames), funding_used=True,
                    sections=[("Coverage", md_table(cov, index=False)), ("Funding audit", md_table(fund, index=False))],
                    notes=["volume == 0 bars are masked as NaN by the loader (counted in nan_bars).",
                           "BNBUSDT funding is excluded from every perp P&L (PLAN §5.2.2)."])
    return [write_report(rd, runner.reports_dir, reps=200, summary={"rows": len(cov)})]


def exp_e1(runner: Runner) -> list[Path]:
    """E1: buy & hold benchmarks (BTC and equal-weight basket) over the WF period. Not a trial."""
    from apps.research.strategies.benchmarks import bh_returns

    paths = []
    for market in runner.s.markets:
        panel = runner.daily_panel(runner.common, market)
        closes = _closes(panel)
        start = pd.Timestamp(runner.wf_start, tz="UTC")
        series = {"B&H BTC": bh_returns(closes["BTCUSDT"]), "B&H basket (EW)": bh_returns(closes)}
        series = {k: v[v.index >= start] for k, v in series.items()}
        btc = panel["BTCUSDT"]
        rd = ReportData("E1", f"Benchmarks {market}", series["B&H BTC"], market=market,
                        cells=ex_ante_cells(btc), manifest=manifest_from_frames(panel.values()),
                        bench=series, notes=["Benchmarks are not trials (PLAN §2.1). Vol matching is done per "
                                             "candidate in each family report."])
        paths.append(write_report(rd, runner.reports_dir, reps=min(runner.reps, 2000), summary={}))
    return paths


def _trend_frozen_build(runner: Runner, specs: Sequence[ConfigSpec]) -> Callable:
    by_id = {s.config_id: s for s in specs}

    def build(config_id: str, data: dict):
        return by_id[config_id].build("spot", data)
    return build


def exp_e2(runner: Runner) -> list[Path]:
    """E2: TREND T1-T5 walk-forward on spot and perps (9 common coins), spot vs perp, frozen spot."""
    specs = _trend_specs(runner)
    runner.register(specs)                               # BEFORE computing anything
    out, oos = [], {}
    for market in runner.s.markets:
        data = _daily_data(runner, market, runner.common)
        data["frozen_build"] = _trend_frozen_build(runner, specs)
        res = runner.run_family("E2", "TREND", specs, market, data, frozen=True,
                                title=f"TREND T1-T5 {market}",
                                notes=["T3 is the primary preregistered configuration.",
                                       "The perp run (L = 1) reports the funding cost; it is not a new trial."])
        out.append(res["report"])
        oos[market] = res["oos"]
    if {"spot", "futures"} <= set(oos):
        both = pd.concat([oos["futures"].rename("perp"), oos["spot"].rename("spot")], axis=1).dropna()
        p = bootstrap_pvalue_diff(both["perp"].to_numpy(), both["spot"].to_numpy(), reps=runner.reps)
        verdict = "perp" if p < 0.05 else "spot"
        rd = ReportData("E2", "TREND spot vs perp", both["spot"] - both["perp"], market="spot vs futures",
                        funding_used=True, bench={"spot": both["spot"], "perp": both["perp"]},
                        notes=[f"One-sided bootstrap p (perp > spot) = {p:.4f}. Preregistered rule: the long leg goes "
                               f"to spot unless perp wins with p < 0.05 -> **{verdict}**."])
        out.append(write_report(rd, runner.reports_dir, reps=min(runner.reps, 2000),
                                summary={"p_perp_gt_spot": p, "long_leg": verdict}))
    return out


def _t3_base(runner: Runner, market: str, data: dict) -> pd.Series:
    """OOS walk-forward returns of T3 alone (base of the overlays)."""
    t3 = _trend_specs(runner, ("T3",))
    runner.register(t3)
    cand = BacktestCandidate("T3", t3[0].build(market, data))
    return walk_forward([cand], data["panel"], runner.folds).oos_returns


def exp_e3(runner: Runner) -> list[Path]:
    """E3: REGIME R1-R3 and FVETO F1-F3 over T3 (increments)."""
    from apps.research.strategies.overlays import FVETO_CONFIGS, FundingVeto, RegimeOverlay
    from apps.research.strategies.trend import make_trend, sizing_config

    fams = runner.s.families or ("REGIME", "FVETO")
    specs: dict[str, list[ConfigSpec]] = {}
    if "REGIME" in fams:
        specs["REGIME"] = [runner.weight_spec(
            "REGIME", r, {"base": "T3", "regime": r},
            lambda data, r=r: RegimeOverlay(make_trend("T3"), r, btc=data.get("btc")),
            sizing_config("T3"), RegimeOverlay(make_trend("T3"), r).n_free_params) for r in ("R1", "R2", "R3")]
    if "FVETO" in fams:
        specs["FVETO"] = [runner.weight_spec(
            "FVETO", f, {"base": "T3", "fveto": f},
            lambda data, f=f: FundingVeto(make_trend("T3"), f, funding=data.get("funding")),
            sizing_config("T3"), FundingVeto(make_trend("T3"), f).n_free_params) for f in FVETO_CONFIGS]
    for fam_specs in specs.values():
        runner.register(fam_specs)                       # BEFORE computing anything
    out = []
    for market in runner.s.markets:
        data = _daily_data(runner, market, runner.common)
        base = _t3_base(runner, market, data)
        for fam, fam_specs in specs.items():
            data["frozen_build"] = _trend_frozen_build(runner, fam_specs)
            res = runner.run_family("E3", fam, fam_specs, market, data, frozen=True, overlay_base=base,
                                    funding_used=(fam == "FVETO"), title=f"{fam} over T3 {market}",
                                    notes=["Overlays only reduce exposure; judged as an increment over T3."])
            out.append(res["report"])
    return out


def exp_e4(runner: Runner) -> list[Path]:
    """E4: SHORT S1/S2 over T3 in perps (BTC < SMA200 gate, funding veto)."""
    from apps.research.strategies.trend import SHORT_CONFIGS, make_short, sizing_config

    specs = [runner.weight_spec("SHORT", s, {"base": "T3", "k": k, "config": s},
                                lambda data, s=s: make_short(s, btc=data.get("btc"), funding=data.get("funding")),
                                sizing_config(s), make_short(s).n_free_params) for s, k in SHORT_CONFIGS.items()]
    runner.register(specs)                               # BEFORE computing anything
    data = _daily_data(runner, "futures", runner.common, with_spot=False)
    base = _t3_base(runner, "futures", data)
    res = runner.run_family("E4", "SHORT", specs, "futures", data, overlay_base=base, funding_used=True,
                            title="SHORT S1-S2 over T3 futures")
    return [res["report"]]


def _event_family(runner: Runner, experiment: str, family: str, ids: Sequence[str], make: Callable[[str], Any],
                  params_of: Callable[[str], dict], market: str, tf: str, symbols: Sequence[str],
                  paper_only: bool = False, start: Optional[str] = None) -> Path:
    """Shared pipeline of the event-driven families (BRK4H, SHOCK)."""
    from apps.research.engine.event_bt import run_event_bt

    specs = []
    for cid in ids:
        def build(mkt: str, data: dict, cid=cid) -> Callable[..., BTResult]:
            def run(s0, s1, cost_mult: float = 1.0, delay_bars: int = 1, stop_fill: str = "gap_aware",
                    funding_mult: float = 1.0) -> BTResult:
                strat = data["make"](cid)
                return data["run_strategy"](strat, start=s0, end=s1, cost=runner.cost.stressed(cost_mult, funding_mult),
                                            delay_bars=delay_bars, stop_fill=stop_fill)
            return run
        specs.append(ConfigSpec(family, cid, params_of(cid), build, make(cid).n_free_params))
    runner.register(specs)                               # BEFORE computing anything
    check_outside_holdout(runner.wf_end, market)
    panel = load_panel(symbols, market, tf, start, runner.wf_end, allow_late_start=True)
    daily = load_panel(symbols, market, "1d", None, runner.wf_end, allow_late_start=True)
    if "BTCUSDT" not in daily:
        daily["BTCUSDT"] = runner.daily_panel(["BTCUSDT"], market)["BTCUSDT"]
    funding = runner.funding(symbols) if market == "futures" or family == "BRK4H" else {}

    def make_prepared(cid: str):
        strat = make(cid)
        if family == "SHOCK":
            return strat.prepare(panel, daily, btc_daily=daily["BTCUSDT"])
        return strat.prepare(panel, daily, funding, btc_daily=daily["BTCUSDT"])

    def run_strategy(strat, start=None, end=None, cost=None, delay_bars: int = 1, stop_fill: str = "gap_aware"):
        return run_event_bt(strat, panel, market, cost or runner.cost, runner.risk, start, end, stop_fill, delay_bars,
                            daily=daily, funding=funding if market == "futures" else None)

    data = {"panel": panel, "funding": funding, "btc": daily["BTCUSDT"], "make": make_prepared,
            "run_strategy": run_strategy, "closes_panel": daily, "bench_panel": daily}
    notes = ["PAPER ONLY (PLAN §2.1)."] if paper_only else []
    res = runner.run_family(experiment, family, specs, market, data, event=True, funding_used=bool(funding),
                            title=f"{family} {market}", notes=notes)
    return res["report"]


def exp_e5(runner: Runner) -> list[Path]:
    """E5: BRK4H B1-B5 (perp long/short, spot long)."""
    from apps.research.strategies.breakout4h import BRK4H_CONFIGS, make_breakout4h

    out = []
    for market in runner.s.markets:
        syms = [s for s in runner.cfg.universe[market]]
        out.append(_event_family(runner, "E5", "BRK4H", list(BRK4H_CONFIGS), make_breakout4h,
                                 lambda c: {k: v for k, v in BRK4H_CONFIGS[c].items()} | {"config": c},
                                 market, "4h", syms, start=str(runner.anchor.date())))
    return out


def exp_e6(runner: Runner) -> list[Path]:
    """E6: CARRY K1-K3 (paper only, unverified funding)."""
    from apps.research.strategies.carry import (
        CARRY_CONFIGS,
        CARRY_UNIVERSE,
        UNVERIFIED_WARNING,
        make_carry,
        run_carry_bt,
    )

    specs = []
    for cid in CARRY_CONFIGS:
        c = CARRY_CONFIGS[cid]
        def build(mkt: str, data: dict, cid=cid) -> Callable[..., BTResult]:
            def run(s0, s1, cost_mult: float = 1.0, funding_mult: float = 1.0, **_ignored) -> BTResult:
                return run_carry_bt(make_carry(cid), data["spot"], data["perp"], data["funding"],
                                    runner.cost.stressed(cost_mult, funding_mult), s0, s1)
            return run
        specs.append(ConfigSpec("CARRY", cid, {"config": cid, "theta_in": c.theta_in, "theta_out": c.theta_out},
                                build, make_carry(cid).n_free_params))
    runner.register(specs)                               # BEFORE computing anything
    check_outside_holdout(runner.wf_end, "futures")
    syms = list(CARRY_UNIVERSE)
    a0 = str(runner.anchor.date())
    spot = load_panel(syms, "spot", "4h", a0, runner.wf_end, allow_late_start=True)
    perp = load_panel(syms, "futures", "4h", a0, runner.wf_end, allow_late_start=True)
    fund = runner.funding(syms)
    daily = runner.daily_panel(list(CARRY_UNIVERSE), "spot")
    data = {"panel": spot, "spot": spot, "perp": perp, "funding": fund, "btc": daily["BTCUSDT"],
            "closes_panel": daily, "bench_panel": daily}
    res = runner.run_family("E6", "CARRY", specs, "futures", data, funding_used=True, title="CARRY K1-K3 (paper)",
                            per_symbol=False,
                            stress_keys=["cost_x2", "funding_x0.5", "funding_x2"],
                            notes=[UNVERIFIED_WARNING, "PAPER ONLY. The +1 bar delay stress is not supported by the "
                                   "carry simulator, so the delay check of the gate fails by construction."])
    return [res["report"]]


def exp_e7(runner: Runner) -> list[Path]:
    """E7: PULLBACK P1-P3 (execution overlay over T3) and SHOCK H1-H3 (paper)."""
    from apps.research.portfolio.sizing import discretize
    from apps.research.strategies.pullback import PULLBACK_CONFIGS, make_pullback
    from apps.research.strategies.shock import SHOCK_CONFIGS, make_shock
    from apps.research.strategies.trend import make_trend

    fams = runner.s.families or ("PULLBACK", "SHOCK")
    out = []
    if "PULLBACK" in fams:
        specs = [ConfigSpec("PULLBACK", c, {"base": "T3", **PULLBACK_CONFIGS[c], "config": c}, lambda m, d: None,
                            make_pullback(c).n_free_params) for c in PULLBACK_CONFIGS]
        runner.register(specs)                           # BEFORE computing anything
        for market in runner.s.markets:
            daily = runner.daily_panel(runner.common, market)
            h1 = load_panel(runner.common, market, "1h", None, runner.wf_end, allow_late_start=True)
            E_q = discretize(make_trend("T3").signal(daily), 0.25)
            E_q = E_q[(E_q.index >= pd.Timestamp(runner.wf_start, tz="UTC"))]
            rows, sections = {}, []
            for spec in specs:
                ev = make_pullback(spec.config_id).schedule(E_q, h1, daily)
                rep = make_pullback(spec.config_id).report(ev, runner.cost.fee_rate(market))
                ok = ev.dropna(subset=["base_price", "fill_price"])
                impr = (1.0 - ok["fill_price"].astype(float) / ok["base_price"].astype(float)).to_numpy()
                p = _one_sample_p(impr, runner.reps)
                rep["p_improvement_gt_0"] = p
                rep["accepted"] = bool(p < 0.05 and rep.get("incremental_per_turnover", 0) > 0)
                rows[spec.config_id] = rep
                runner.trials.record_metrics(spec.trial_id, {"experiment": "E7", "market": market,
                                                             **{k: _finite_or_none(v) if isinstance(v, float) else v
                                                                for k, v in rep.items()}})
                by_year = ev.assign(year=pd.to_datetime(ev["decision"]).dt.year).groupby("year").apply(
                    lambda g: pd.Series(make_pullback(spec.config_id).report(g, runner.cost.fee_rate(market))),
                    include_groups=False)
                sections.append((f"{spec.config_id} by year", md_table(by_year)))
            table = pd.DataFrame(rows).T
            rd = ReportData("E7", f"PULLBACK P1-P3 {market}", pd.Series(dtype=float), market=market,
                            trial_ids=[s.trial_id for s in specs],
                            manifest=manifest_from_frames(list(daily.values()) + list(h1.values())),
                            sections=[("Incremental net return per unit of turnover vs T3", md_table(table))]
                            + sections,
                            notes=["Accepted only if the improvement is positive with p < 0.05 (stationary "
                                   "bootstrap over events)."], proxy=False)
            out.append(write_report(rd, runner.reports_dir, reps=200, summary={"configs": rows}))
            runner.save_verdict(f"PULLBACK:{market}", {"family": "PULLBACK", "level": "C" if not any(
                r["accepted"] for r in rows.values()) else "overlay-accepted", "configs": rows})
    if "SHOCK" in fams:
        out.append(_event_family(runner, "E7", "SHOCK", list(SHOCK_CONFIGS), make_shock,
                                 lambda c: {**SHOCK_CONFIGS[c], "config": c}, "futures", "1h",
                                 list(runner.cfg.universe["futures"]), paper_only=True, start=str(runner.anchor.date())))
    return out


def _one_sample_p(x: np.ndarray, reps: int) -> float:
    """One-sided stationary-bootstrap p-value of H0: mean(x) <= 0."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 10:
        return float("nan")
    dist = stationary_bootstrap(x, np.mean, reps=reps)
    centred = dist - dist.mean()
    return float((np.sum(centred >= x.mean()) + 1) / (reps + 1))


def exp_e8(runner: Runner) -> list[Path]:
    """E8: SELECTOR M1 (risk parity) vs M2/M3 (regime tables fitted on training only)."""
    from apps.research.validation.adaptability import eb_shrink

    verdicts = runner.load_verdicts()
    engines = {k: v for k, v in verdicts.items() if v.get("level") in ("A", "B") and v.get("returns_csv")}
    if len(engines) < 2:
        rd = ReportData("E8", "SELECTOR vs parity", pd.Series(dtype=float),
                        notes=[f"Not run: {len(engines)} engine(s) at level A/B (need >= 2). No trial registered. "
                               "M1 (risk parity over the accepted engines) stays the default."])
        return [write_report(rd, runner.reports_dir, reps=200, summary={"run": False, "engines": list(engines)})]

    def m1_weights(R: pd.DataFrame) -> pd.DataFrame:
        vol = R.rolling(365, min_periods=60).std().shift(1)
        inv = 1.0 / vol
        return inv.div(inv.sum(axis=1), axis=0)

    specs = [ConfigSpec("SELECTOR", m, {"config": m, "engines": sorted(engines)}, lambda *_: None, n)
             for m, n in (("M1", 1), ("M2", 3), ("M3", 4))]
    runner.register(specs)                               # BEFORE computing anything
    R = pd.DataFrame({k: pd.read_csv(runner.reports_dir / v["returns_csv"], index_col=0, parse_dates=True)
                      .iloc[:, 0] for k, v in engines.items()}).dropna(how="all").fillna(0.0)
    R.index = pd.DatetimeIndex(R.index).tz_convert("UTC") if R.index.tz is not None else \
        pd.DatetimeIndex(R.index).tz_localize("UTC")
    btc = runner.daily_panel(["BTCUSDT"], "spot")["BTCUSDT"]
    cells = ex_ante_cells(btc).reindex(R.index)

    class Sel:
        def __init__(self, name):
            self.name = name

        def fold_returns(self, panel, fold):
            w1 = m1_weights(R)
            tr = R[R.index <= fold.train_end]
            if self.name == "M1":
                port = (w1 * R).sum(axis=1)
                return port[port.index <= fold.train_end], port[port.index >= fold.test_start]
            table = {}
            for cell in cells.dropna().unique():
                m = cells.reindex(tr.index) == cell
                srs = tr[m].mean() / tr[m].std() * math.sqrt(365) if m.sum() > 20 else None
                if srs is None or not np.isfinite(srs).all():
                    continue
                se = np.sqrt((1 + srs.pow(2) / 2) / m.sum()) * math.sqrt(365)
                st, _, _, _ = eb_shrink(srs.to_numpy(), se.to_numpy())
                w = np.maximum(st, 0.0)
                if w.sum() > 0:
                    table[cell] = pd.Series(w / w.sum(), index=R.columns)
            w2 = pd.DataFrame([table.get(c, w1.loc[t]) if isinstance(c, str) else w1.loc[t]
                               for t, c in cells.items()], index=R.index)
            w = w2 if self.name == "M2" else 0.5 * w2 + 0.5 * w1
            port = (w.fillna(0.0) * R).sum(axis=1)
            return port[port.index <= fold.train_end], port[port.index >= fold.test_start]

    wf = walk_forward([Sel("M1"), Sel("M2"), Sel("M3")], None, runner.folds,
                      select=lambda tr: "M1")   # M1 is the baseline; M2/M3 must beat it explicitly
    cfg = wf.config_oos.dropna()
    pbo = pbo_cscv(cfg) if len(cfg) >= 32 else float("nan")
    rows = {}
    for m in ("M2", "M3"):
        p = bootstrap_pvalue_diff(cfg[m].to_numpy(), cfg["M1"].to_numpy(), reps=runner.reps)
        rows[m] = {"p_vs_M1": p, "adopt": bool(p < 0.05 and pbo <= 0.3), "sharpe": sharpe(cfg[m])}
    for spec in specs:
        runner.trials.record_metrics(spec.trial_id, {"experiment": "E8", "sharpe": _finite_or_none(sharpe(cfg[spec.config_id]))})
    choice = next((m for m in ("M2", "M3") if rows[m]["adopt"]), "M1")
    rd = ReportData("E8", "SELECTOR vs parity", cfg[choice], cells=cells, configs=cfg, trial_ids=[s.trial_id for s in specs],
                    sections=[("Increment over M1", md_table(pd.DataFrame(rows).T))],
                    notes=[f"PBO of the selector family = {pbo:.3f}. Adopted: **{choice}**."])
    runner.save_verdict("SELECTOR", {"family": "SELECTOR", "choice": choice, "pbo": pbo, "rows": rows})
    return [write_report(rd, runner.reports_dir, reps=min(runner.reps, 2000), summary={"choice": choice, "rows": rows})]


def exp_e9(runner: Runner) -> list[Path]:
    """E9: open the holdout ONCE for the named finalists (``FAMILY:CONFIG:MARKET``) and evaluate them."""
    from apps.research.strategies.overlays import FundingVeto, RegimeOverlay
    from apps.research.strategies.trend import make_short, make_trend, sizing_config

    if not runner.s.finalists:
        raise SystemExit("E9 needs --finalists FAMILY:CONFIG:MARKET (e.g. TREND:T3:spot)")
    grant = runner.holdout.open(runner.s.agent, runner.s.finalists, reason="E9 sanity holdout")
    verdicts = runner.load_verdicts()
    out = []
    for fin in runner.s.finalists:
        family, cid, market = fin.split(":")
        h0, h1 = grant.window(market)
        syms = runner.common
        panel = load_panel(syms, market, "1d", None, str(h1.date()), allow_late_start=True)
        funding = {s: f[f.index < h1 + ONE_DAY] for s, f in
                   ((s, load_funding(s)) for s in syms if s not in runner.cfg.universe.get("funding_excluded", ()))}
        btc = panel["BTCUSDT"]
        if family == "TREND":
            strat, sizing = make_trend(cid), sizing_config(cid)
        elif family == "REGIME":
            strat, sizing = RegimeOverlay(make_trend("T3"), cid, btc=btc), sizing_config("T3")
        elif family == "FVETO":
            strat, sizing = FundingVeto(make_trend("T3"), cid, funding=funding), sizing_config("T3")
        elif family == "SHORT":
            strat, sizing = make_short(cid, btc=btc, funding=funding), sizing_config(cid)
        else:
            raise SystemExit(f"E9 supports daily finalists only (got {family})")
        res = run_portfolio_bt(strat, panel, market, runner.cost, sizing, runner.risk, h0, h1,
                               funding=funding if market == "futures" else None)
        h = res.returns.dropna()
        v = verdicts.get(f"{family}:{market}", {})
        wf_r = pd.read_csv(runner.reports_dir / v["returns_csv"], index_col=0).iloc[:, 0].dropna() \
            if v.get("returns_csv") else pd.Series(dtype=float)
        mult = float(runner.cfg.gate["holdout_dd_mult"])
        if len(wf_r) > len(h) > 0:
            L = len(h)
            dist = stationary_bootstrap(wf_r.to_numpy(), lambda x: float(np.prod(1 + x[:L]) - 1), reps=runner.reps)
            p5 = float(np.percentile(dist, 5))
            ok = compounded(h) > p5 and max_drawdown(h) <= mult * max_drawdown(wf_r)
        else:
            p5, ok = float("nan"), False
        # The holdout is an A-only criterion: it can promote B -> A (if it was the only A failure), never B.
        level = "A" if ok and v.get("failed_A") == ["holdout"] else v.get("level", "C")
        rd = ReportData("E9", f"Holdout {fin}", h, market=market, cells=ex_ante_cells(btc),
                        manifest=manifest_from_frames(list(panel.values())), funding_used=market == "futures",
                        holdout_status=f"opened {grant.record['opened_at']} by {grant.record['agent']}",
                        notes=[f"Holdout return {compounded(h):.2%} vs WF 5th percentile {p5:.2%}; DD "
                               f"{max_drawdown(h):.2%} vs {mult}x WF MaxDD. Check {'passed' if ok else 'FAILED'}.",
                               "The holdout is partially contaminated for TREND (debate saw 2026 YTD): sanity "
                               "control only."])
        out.append(write_report(rd, runner.reports_dir, reps=min(runner.reps, 2000),
                                summary={"holdout_ok": ok, "level_after_holdout": level}))
        runner.save_verdict(f"{family}:{market}", {**v, "holdout_ok": ok, "level": level})
    return out


def exp_e10(runner: Runner) -> list[Path]:
    """E10: final report (trials budget, verdicts, most adaptable engine, recommendation)."""
    verdicts = runner.load_verdicts()
    fams = sorted(runner.trials.quotas)
    budget = pd.DataFrame([{"family": f, "used": runner.trials.n_family(f), "quota": runner.trials.quotas[f]}
                           for f in fams]).set_index("family")
    rows = [{"engine": k, "level": v.get("level"), "sharpe": v.get("sharpe"), "max_dd": v.get("max_dd"),
             "A_k": v.get("A_k"), "final_selection": v.get("final_selection")} for k, v in sorted(verdicts.items())]
    table = pd.DataFrame(rows).set_index("engine") if rows else pd.DataFrame()
    passing = [r for r in rows if r["level"] in ("A", "B") and r.get("A_k") is not None]
    if passing:
        best = max(passing, key=lambda r: r["A_k"])
        rec = (f"Most adaptable engine among those passing the gate: **{best['engine']}** (A_k = {best['A_k']:.3f}, "
               f"level {best['level']}). Level B goes to paper for >= 3 months before real capital.")
    else:
        rec = ("**No engine reached level A or B.** Recommendation: cash, or a bounded BTC buy & hold / DCA "
               "(user's decision). The gate is not relaxed.")
    sel = verdicts.get("SELECTOR", {}).get("choice", "M1")
    rd = ReportData("E10", "Final report", pd.Series(dtype=float),
                    sections=[("Trial budget (N <= 40)", md_table(budget) + f"\n\nN total = {runner.trials.n_total()}"),
                              ("Verdicts", md_table(table) if rows else "_no verdicts yet_"),
                              ("Recommendation", rec + f"\n\nAllocation between engines: **{sel}**.")],
                    funding_used=True)
    return [write_report(rd, runner.reports_dir, reps=200, summary={"recommendation": rec, "allocation": sel})]


EXPERIMENTS: dict[str, Callable[[Runner], list[Path]]] = {
    "E0": exp_e0, "E1": exp_e1, "E2": exp_e2, "E3": exp_e3, "E4": exp_e4, "E5": exp_e5,
    "E6": exp_e6, "E7": exp_e7, "E8": exp_e8, "E9": exp_e9, "E10": exp_e10,
}


# --------------------------------------------------------------------------- CLI
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m apps.research.run", description=__doc__.split("\n\n")[0])
    p.add_argument("experiment", choices=sorted(EXPERIMENTS, key=lambda e: int(e[1:])))
    p.add_argument("--market", choices=["spot", "futures", "both"], default="both")
    p.add_argument("--agent", default=os.environ.get("RESEARCH_AGENT", "run.py"))
    p.add_argument("--trials-dir", type=Path, default=None,
                   help="directory of trials.jsonl and holdout.lock (default ${REPO}/data/trials)")
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    p.add_argument("--data-root", type=Path, default=None)
    p.add_argument("--reps", type=int, default=None, help="bootstrap replications (default config: 10000)")
    p.add_argument("--seeds", type=int, default=100, help="random-entry seeds (PLAN: 100)")
    p.add_argument("--family", action="append", default=[], help="restrict E3/E7 to one family")
    p.add_argument("--finalists", nargs="*", default=[], help="E9 only: FAMILY:CONFIG:MARKET")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    trials_dir = args.trials_dir or (Path(os.environ["RESEARCH_TRIALS_DIR"]) if os.environ.get("RESEARCH_TRIALS_DIR")
                                     else None)
    markets = ("spot", "futures") if args.market == "both" else (args.market,)
    settings = Settings(agent=args.agent, trials_dir=trials_dir, reports_dir=args.reports_dir,
                        data_root=args.data_root, reps=args.reps, seeds=args.seeds, markets=markets,
                        finalists=args.finalists, families=tuple(args.family))
    runner = Runner(settings)
    paths = EXPERIMENTS[args.experiment](runner)
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
