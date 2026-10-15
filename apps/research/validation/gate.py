"""
Acceptance gate, levels A / B / C (PLAN.md §5.6, task R14).

Level A ("accepted": real capital after >= 4 weeks of demo) needs EVERY check:

1.  ``dsr``: DSR >= 0.95 with N = ``TrialsLog.n_total()`` and the variance of
    the Sharpe ratios of all the logged trials.
2.  ``pbo``: PBO (CSCV, S = 16) of the family <= 0.30.
3.  ``random_entries``: OOS net Sharpe > 95th percentile of the random entries.
4.  ``vs_bh``: one-sided stationary-bootstrap test of the daily return
    difference against the vol-matched buy & hold of BTC AND of the basket,
    p < 0.05 for both.
5.  ``no_catastrophe``: in each sub-period (2022, 2023-24, 2025-26) and
    against both vol-matched benchmarks, ``dSR > -1 SE`` (Jobson-Korkie /
    Memmel SE) and ``MaxDD <= MaxDD(B&H)``.
6.  ``cost_stress`` / ``delay_stress``: costs x2 -> Sharpe > 0 and >= 50 % of
    the base; +1 bar delay -> Sharpe >= 50 % of the base.
7.  ``frozen_spot``: frozen spot 2017-2020 -> Sharpe > 0 and MaxDD <= that of
    the vol-matched B&H (daily families only; ``n/a`` otherwise).
8.  ``max_dd``: OOS MaxDD <= 20 % in spot AND futures (user tolerance; PLAN
    says 25 % / 20 %, tightened by the user, ``config/research.yml``).
9.  ``holdout``: the holdout return is above the 5th percentile of the
    bootstrap distribution of WF windows of the same length, and its DD <=
    1.5 x the WF MaxDD. ``pending`` until the holdout is opened (E9), which
    keeps a candidate out of level A.
10. ``significance``: t >= 3, or for discrete-trade strategies the number of
    OOS trades reaches ``(3 / SR_t)^2 (1 - g3 SR_t + (g4 - 1)/4 SR_t^2)``.

Level B ("paper candidate"): PSR(0) >= 0.90, above the random 95th
percentile, PBO <= 0.30, A_k > 0, costs x2 Sharpe > 0 and no catastrophe in
the frozen spot 2017-2020 (``dSR > -1 SE`` and MaxDD <= B&H there).

Level C: rejected. The gate is never relaxed after the fact; "nothing passes"
is a valid outcome (the final report then recommends cash or a bounded BTC
B&H / DCA, the user's decision).

Overlays (SHORT, REGIME, FVETO, PULLBACK) are judged as an INCREMENT over
their base (T3 or the accepted TREND): accepted if they reduce CVaR95 or
MaxDD, or improve MAR, with p < 0.05 (stationary bootstrap of the
difference), without worsening the Sharpe by more than 1 SE, and with the
family PBO <= 0.30. A rejected increment gives level C; an accepted one keeps
the level the combined strategy earns on its own.

Status of a check: ``pass``, ``fail``, ``pending`` (input not available yet)
or ``n/a`` (does not apply). Only ``pass`` and ``n/a`` count as met. Missing
inputs that the plan requires FAIL (no silent pass).

Units: ``TrialsLog`` metrics store ANNUALISED Sharpe ratios under ``sharpe``;
they are converted to per-day units (/ 365) for the DSR variance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.config import get_config
from apps.research.validation.metrics import (
    PERIODS_PER_YEAR,
    compounded,
    cvar,
    mar,
    max_drawdown,
    sharpe,
    sharpe_diff_se,
)
from apps.research.validation.pbo import pbo_cscv
from apps.research.validation.stats import (
    bootstrap_pvalue_diff,
    dsr,
    min_track_record,
    moments,
    psr,
    sharpe_ratio,
    stationary_bootstrap,
)

__all__ = [
    "SUBPERIODS",
    "Level",
    "Check",
    "GateInputs",
    "GateBench",
    "GateReport",
    "trials_sharpe_var",
    "overlay_increment",
    "gate_report",
    "evaluate_gate",
]

Level = Literal["A", "B", "C"]
Status = Literal["pass", "fail", "pending", "n/a"]

SUBPERIODS: dict[str, tuple[str, str]] = {
    "2022": ("2022-01-01", "2022-12-31"),
    "2023-24": ("2023-01-01", "2024-12-31"),
    "2025-26": ("2025-01-01", "2026-12-31"),
}
_OK = ("pass", "n/a")


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    value: object = None
    threshold: object = None
    detail: str = ""

    @property
    def met(self) -> bool:
        return self.status in _OK


@dataclass
class GateInputs:
    """
    The candidate side of the gate (``result`` in ``evaluate_gate``).

    ``returns``: OOS walk-forward daily net returns (family selection).
    ``family_returns``: T x N OOS returns of every configuration of the family
    (for the PBO; or pass ``pbo`` directly). ``stress``: stressed OOS returns
    keyed ``cost_x2``, ``delay_1`` (optional extras: ``worst_bar``,
    ``funding_x0.5``, ``funding_x2``). ``frozen_returns``: frozen spot
    2017-2020 run (required when ``frozen_required``). ``holdout_returns``:
    only after E9. ``trade_returns``: per-trade returns of discrete-trade
    engines (point 10). ``adaptability``: A_k. ``overlay_base``: base returns
    when the candidate is an overlay.
    """

    name: str
    market: Literal["spot", "futures"]
    returns: pd.Series
    family_returns: Optional[pd.DataFrame] = None
    pbo: Optional[float] = None
    stress: Mapping[str, pd.Series] = field(default_factory=dict)
    frozen_returns: Optional[pd.Series] = None
    frozen_required: bool = False
    holdout_returns: Optional[pd.Series] = None
    trade_returns: Optional[pd.Series] = None
    adaptability: Optional[float] = None
    overlay_base: Optional[pd.Series] = None


@dataclass
class GateBench:
    """
    The benchmark side: vol-matched B&H of BTC and of the basket over the OOS
    dates, the random-entry Sharpe ratios (array or ``RandomEntryResult``) and
    the vol-matched B&H of the frozen spot period.
    """

    bh_btc: pd.Series
    bh_basket: pd.Series
    random_sharpes: object
    frozen_bh: Optional[pd.Series] = None


@dataclass
class GateReport:
    name: str
    level: Level
    checks_a: dict
    checks_b: dict
    overlay: Optional[dict] = None
    summary: dict = field(default_factory=dict)

    def failed(self, level: str = "A") -> list[str]:
        checks = self.checks_a if level == "A" else self.checks_b
        return [k for k, c in checks.items() if not c.met]

    def table(self) -> pd.DataFrame:
        rows = []
        for lvl, checks in (("A", self.checks_a), ("B", self.checks_b)):
            for c in checks.values():
                rows.append({"level": lvl, "check": c.name, "status": c.status, "value": c.value,
                             "threshold": c.threshold, "detail": c.detail})
        return pd.DataFrame(rows)


# --------------------------------------------------------------------------- helpers
def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _r(x: Optional[pd.Series]) -> pd.Series:
    if x is None:
        return pd.Series(dtype=float)
    return pd.Series(x, dtype=float).dropna()


def _align(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    return pd.concat([_r(a).rename("a"), _r(b).rename("b")], axis=1, join="inner").dropna()


def _window(x: pd.Series, start: str, end: str) -> pd.Series:
    t0, t1 = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    return x[(x.index >= t0) & (x.index < t1)]


def _random_sharpes(rs) -> np.ndarray:
    arr = getattr(rs, "sharpes", rs)
    a = np.asarray(arr if arr is not None else [], dtype=float)
    return a[np.isfinite(a)]


def trials_sharpe_var(trials, family_returns: Optional[pd.DataFrame] = None) -> float:
    """
    Variance of the per-day Sharpe ratios of the logged trials (DSR input).
    Falls back to the family's own configurations when fewer than two trials
    have recorded a Sharpe. NaN when neither is available.
    """
    vals = np.asarray(trials.sharpe_values() if trials is not None else [], dtype=float)
    vals = vals[np.isfinite(vals)] / math.sqrt(PERIODS_PER_YEAR)
    if vals.size >= 2:
        return float(vals.var(ddof=1))
    if family_returns is not None and family_returns.shape[1] >= 2:
        srs = [sharpe_ratio(family_returns[c].dropna().to_numpy()) for c in family_returns]
        srs = np.asarray([s for s in srs if math.isfinite(s)])
        if srs.size >= 2:
            return float(srs.var(ddof=1))
    return float("nan")


def _bootstrap_kw(reps: Optional[int], seed: int) -> dict:
    boot = get_config().bootstrap
    return {"block_mean": int(boot.get("block_mean", 20)),
            "reps": int(reps if reps is not None else boot.get("reps", 10_000)), "seed": seed}


def _no_catastrophe(x: pd.Series, bench: pd.Series) -> tuple[bool, str]:
    both = _align(x, bench)
    if len(both) < 30:
        return False, f"only {len(both)} common days"
    d, se = sharpe_diff_se(both["a"], both["b"])
    dd_x, dd_b = max_drawdown(both["a"]), max_drawdown(both["b"])
    ok = math.isfinite(d) and math.isfinite(se) and d > -se and dd_x <= dd_b + 1e-12
    return ok, f"dSR={d:.2f} (SE {se:.2f}), MaxDD {dd_x:.1%} vs B&H {dd_b:.1%}"


# --------------------------------------------------------------------------- overlays
def overlay_increment(overlay: pd.Series, base: pd.Series, pbo: Optional[float],
                      reps: Optional[int] = None, seed: int = 0, alpha: Optional[float] = None) -> dict:
    """
    Increment test of an overlay over its base (PLAN §5.6, overlays).

    p-values are one-sided stationary-bootstrap tests that the overlay
    reduces CVaR95, reduces MaxDD or improves MAR. Accepted when any p <
    ``alpha``, ``dSR > -1 SE`` and ``pbo <= pbo_max``.
    """
    gate = get_config().gate
    alpha = float(gate["bootstrap_p"]) if alpha is None else alpha
    both = _align(overlay, base)
    kw = _bootstrap_kw(reps, seed)
    out = {"n_days": int(len(both)), "pbo": _f(pbo)}
    if len(both) < 30:
        return {**out, "accepted": False, "detail": "fewer than 30 common days"}
    a, b = both["a"].to_numpy(), both["b"].to_numpy()
    out["p_cvar"] = bootstrap_pvalue_diff(b, a, stat=lambda x: cvar(x, 0.95), **kw)
    out["p_maxdd"] = bootstrap_pvalue_diff(b, a, stat=max_drawdown, **kw)
    out["p_mar"] = bootstrap_pvalue_diff(a, b, stat=lambda x: _f(np.nan_to_num(mar(x), nan=0.0)), **kw)
    d, se = sharpe_diff_se(a, b)
    out.update({"d_sharpe": d, "se_d_sharpe": se, "cvar_overlay": cvar(a), "cvar_base": cvar(b),
                "maxdd_overlay": max_drawdown(a), "maxdd_base": max_drawdown(b)})
    improves = min(out["p_cvar"], out["p_maxdd"], out["p_mar"]) < alpha
    sharpe_ok = math.isfinite(d) and math.isfinite(se) and d > -se
    pbo_ok = math.isfinite(out["pbo"]) and out["pbo"] <= float(gate["pbo_max"])
    out.update({"improves": bool(improves), "sharpe_ok": bool(sharpe_ok), "pbo_ok": bool(pbo_ok),
                "accepted": bool(improves and sharpe_ok and pbo_ok)})
    return out


# --------------------------------------------------------------------------- gate
def gate_report(result: GateInputs, bench: GateBench, trials, *, reps: Optional[int] = None,
                seed: int = 0) -> GateReport:
    """Evaluate every check of §5.6 and return the detailed report."""
    gate = get_config().gate
    r = _r(result.returns)
    if len(r) < 3 or not r.std() > 0:
        raise ValueError(f"{result.name}: need at least 3 non-constant OOS returns")
    kw = _bootstrap_kw(reps, seed)
    sr_ann = sharpe(r)
    sr_d = sr_ann / math.sqrt(PERIODS_PER_YEAR)
    g3, g4 = moments(r.to_numpy())
    T = len(r)
    A: dict[str, Check] = {}
    B: dict[str, Check] = {}

    # 1. DSR
    n_trials = int(trials.n_total()) if trials is not None else 0
    var = trials_sharpe_var(trials, result.family_returns)
    if n_trials >= 1 and math.isfinite(var):
        try:
            v = dsr(sr_d, T, g3, g4, var, n_trials)
        except ValueError:
            v = float("nan")
    else:
        v = float("nan")
    A["dsr"] = Check("dsr", "pass" if v >= gate["dsr_min"] else "fail", v, gate["dsr_min"],
                     f"N={n_trials}, V[SR]={var:.3g}/day")

    # 2. PBO
    pbo = result.pbo
    if pbo is None and result.family_returns is not None and result.family_returns.shape[1] >= 2:
        try:
            pbo = pbo_cscv(result.family_returns.dropna(), S=int(gate.get("pbo_cscv_splits", 16)))
        except ValueError:
            pbo = None
    pbo = _f(pbo)
    pbo_chk = Check("pbo", "pass" if pbo <= gate["pbo_max"] else "fail", pbo, gate["pbo_max"],
                    "" if math.isfinite(pbo) else "PBO not computable (needs >= 2 configurations)")
    A["pbo"] = B["pbo"] = pbo_chk

    # 3. Random entries
    rs = _random_sharpes(bench.random_sharpes)
    thr = float(np.percentile(rs, float(gate["random_entry_pctl"]))) if rs.size else float("nan")
    # Like-for-like: a RandomEntryResult carries the candidate Sharpe under the same evaluator.
    sr_cmp = _f(getattr(bench.random_sharpes, "candidate_sharpe", sr_ann))
    rnd = Check("random_entries", "pass" if (rs.size and sr_cmp > thr) else "fail", sr_cmp, thr,
                f"{rs.size} random draws")
    A["random_entries"] = B["random_entries"] = rnd

    # 4. Bootstrap of the difference vs vol-matched B&H (BTC and basket)
    pvals = {}
    for key, bser in (("BTC", bench.bh_btc), ("basket", bench.bh_basket)):
        both = _align(r, bser)
        pvals[key] = bootstrap_pvalue_diff(both["a"].to_numpy(), both["b"].to_numpy(), **kw) \
            if len(both) >= 30 else float("nan")
    ok4 = all(math.isfinite(p) and p < gate["bootstrap_p"] for p in pvals.values())
    A["vs_bh"] = Check("vs_bh", "pass" if ok4 else "fail", pvals, gate["bootstrap_p"], "one-sided p")

    # 5. No catastrophe per sub-period
    details, ok5 = [], True
    for label, (s0, s1) in SUBPERIODS.items():
        x = _window(r, s0, s1)
        if len(x) == 0:
            continue
        for key, bser in (("BTC", bench.bh_btc), ("basket", bench.bh_basket)):
            ok, det = _no_catastrophe(x, _window(_r(bser), s0, s1))
            ok5 &= ok
            details.append(f"{label}/{key}: {'ok' if ok else 'FAIL'} {det}")
    A["no_catastrophe"] = Check("no_catastrophe", "pass" if ok5 and details else "fail", None, "dSR>-1SE, DD<=B&H",
                                "; ".join(details))

    # 6. Stress
    cost2 = result.stress.get("cost_x2")
    delay = result.stress.get("delay_1")
    sr_c2 = sharpe(_r(cost2)) if cost2 is not None else float("nan")
    sr_dl = sharpe(_r(delay)) if delay is not None else float("nan")
    min_c, min_d = float(gate["cost_stress_min_ratio"]), float(gate["delay_stress_min_ratio"])
    ok_c = sr_ann > 0 and sr_c2 > 0 and sr_c2 >= min_c * sr_ann
    A["cost_stress"] = Check("cost_stress", "pass" if ok_c else "fail", sr_c2, f">0 and >= {min_c:.0%} of {sr_ann:.2f}",
                             "" if cost2 is not None else "costs x2 run missing")
    ok_d = sr_ann > 0 and sr_dl >= min_d * sr_ann
    A["delay_stress"] = Check("delay_stress", "pass" if ok_d else "fail", sr_dl, f">= {min_d:.0%} of {sr_ann:.2f}",
                              "" if delay is not None else "+1 bar delay run missing")
    B["cost_stress"] = Check("cost_stress", "pass" if sr_c2 > 0 else "fail", sr_c2, "> 0")

    # 7. Frozen spot 2017-2020
    if not result.frozen_required:
        A["frozen_spot"] = B["frozen_spot"] = Check("frozen_spot", "n/a", detail="not a daily family")
    elif result.frozen_returns is None or bench.frozen_bh is None:
        A["frozen_spot"] = B["frozen_spot"] = Check("frozen_spot", "fail", detail="frozen spot run missing")
    else:
        fr, fb = _r(result.frozen_returns), _r(bench.frozen_bh)
        sr_f, dd_f, dd_b = sharpe(fr), max_drawdown(fr), max_drawdown(fb)
        okA = sr_f > 0 and dd_f <= dd_b + 1e-12
        A["frozen_spot"] = Check("frozen_spot", "pass" if okA else "fail", {"sharpe": sr_f, "max_dd": dd_f},
                                 f"SR>0, DD<={dd_b:.1%}")
        okB, det = _no_catastrophe(fr, fb)
        B["frozen_spot"] = Check("frozen_spot", "pass" if okB else "fail", None, "no catastrophe", det)

    # 8. MaxDD OOS
    dd = max_drawdown(r)
    dd_max = float(gate["max_dd_oos_spot" if result.market == "spot" else "max_dd_oos_futures"])
    A["max_dd"] = Check("max_dd", "pass" if dd <= dd_max else "fail", dd, dd_max)

    # 9. Holdout
    if result.holdout_returns is None or len(_r(result.holdout_returns)) == 0:
        A["holdout"] = Check("holdout", "pending", detail="holdout not opened (E9)")
    else:
        h = _r(result.holdout_returns)
        L = min(len(h), T)
        dist = stationary_bootstrap(r.to_numpy(), lambda x: float(np.prod(1.0 + x[:L]) - 1.0), **kw)
        p5 = float(np.percentile(dist, 5))
        ret_h, dd_h, dd_wf = compounded(h), max_drawdown(h), max_drawdown(r)
        mult = float(gate["holdout_dd_mult"])
        okh = ret_h > p5 and dd_h <= mult * dd_wf + 1e-12
        A["holdout"] = Check("holdout", "pass" if okh else "fail", {"return": ret_h, "max_dd": dd_h},
                             {"p5": p5, "max_dd": mult * dd_wf})

    # 10. Significance
    t = sr_d * math.sqrt(T)
    t_min = float(gate["t_stat_min"])
    detail = f"t={t:.2f}"
    ok10 = t >= t_min
    tr = _r(result.trade_returns)
    if not ok10 and len(tr) >= 3 and tr.std() > 0:
        sr_t = float(tr.mean() / tr.std(ddof=1))
        tg3, tg4 = moments(tr.to_numpy())
        try:
            need = min_track_record(sr_t, tg3, tg4, z=t_min)
        except ValueError:
            need = float("inf")
        ok10 = len(tr) >= need
        detail += f"; trades {len(tr)} vs needed {need:.0f}"
    A["significance"] = Check("significance", "pass" if ok10 else "fail", t, t_min, detail)

    # Level B extras
    p0 = psr(sr_d, T, g3, g4, 0.0)
    B["psr"] = Check("psr", "pass" if p0 >= gate["level_b_psr_min"] else "fail", p0, gate["level_b_psr_min"])
    ak = _f(result.adaptability)
    B["adaptability"] = Check("adaptability", "pass" if ak > 0 else "fail", ak, "> 0",
                              "" if result.adaptability is not None else "A_k missing")

    level: Level = "A" if all(c.met for c in A.values()) else "B" if all(c.met for c in B.values()) else "C"
    overlay = None
    if result.overlay_base is not None:
        overlay = overlay_increment(r, result.overlay_base, pbo, reps=reps, seed=seed)
        if not overlay["accepted"]:
            level = "C"
    summary = {"sharpe": sr_ann, "max_dd": dd, "psr0": p0, "t": t, "n_days": T, "n_trials": n_trials}
    return GateReport(result.name, level, A, B, overlay, summary)


def evaluate_gate(result, bench, trials, **kwargs) -> Level:
    """Level A, B or C of ``result`` (a :class:`GateInputs`) against ``bench`` (a :class:`GateBench`)."""
    return gate_report(result, bench, trials, **kwargs).level
