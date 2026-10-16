"""
Markdown research reports (PLAN.md §5.5, task R16).

Every report contains, whatever the experiment:

- the data provenance: upstream commits of the sources (``data_commit``), the
  digest and SHA-256 of every CSV read (``apps.research.data.manifest``) and
  the git sha of the harness;
- the survivorship-bias warning (PLAN §5.1) and, when perp funding enters the
  P&L or a signal, the "funding not verified" warning (PLAN §5.2.3, §2.7);
- metrics of the main OOS series with the 95 % CI of the Sharpe (stationary
  bootstrap, mean block 20 days), and the same metrics by YEAR, by SYMBOL and
  by ex-ante REGIME cell;
- optional sections: per-configuration results, walk-forward selections,
  costs, stress runs, benchmarks, tail events, the gate and A_k.

Reports are plain markdown (no extra dependency) written by
:func:`write_report` to ``docs/research/results/`` by the CLI.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from apps.research.config import git_sha
from apps.research.data.manifest import data_commit
from apps.research.validation.metrics import perf_metrics

__all__ = [
    "SURVIVORSHIP_WARNING",
    "FUNDING_WARNING",
    "PROXY_WARNING",
    "ReportData",
    "md_table",
    "metrics_table",
    "metrics_by_year",
    "metrics_by_symbol",
    "metrics_by_regime",
    "render_report",
    "write_report",
]

SURVIVORSHIP_WARNING = (
    "**Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins "
    "(LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result "
    "carries this warning (PLAN §5.1).")
FUNDING_WARNING = (
    "**Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted "
    "rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on "
    "funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` "
    "(PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.")
PROXY_WARNING = ("**Proxy data.** Part of the intraday spot history is replaced by futures OHLC "
                 "(`proxy=True`, median basis about -5 bp; PLAN §5.2.6).")

_METRIC_COLS = ["n_days", "total_return", "cagr", "vol", "sharpe", "sharpe_ci", "sortino", "max_dd", "mar",
                "cvar95", "profit_factor"]
_PCT = {"total_return", "cagr", "vol", "max_dd", "cvar95"}


@dataclass
class ReportData:
    """Everything a report can show; only ``experiment``, ``title`` and ``returns`` are required."""

    experiment: str
    title: str
    returns: pd.Series
    market: str = "spot"
    trial_ids: Sequence[str] = ()
    symbol_returns: Optional[pd.DataFrame] = None
    cells: Optional[pd.Series] = None
    manifest: Optional[Mapping[str, Any]] = None
    funding_used: bool = False
    proxy: bool = False
    configs: Optional[pd.DataFrame] = None
    selections: Optional[pd.DataFrame] = None
    stress: Mapping[str, pd.Series] = field(default_factory=dict)
    costs: Optional[Mapping[str, float]] = None
    exposure: Optional[Mapping[str, float]] = None
    bench: Mapping[str, pd.Series] = field(default_factory=dict)
    random_entry: Optional[Any] = None
    tail_events: Optional[pd.DataFrame] = None
    gate: Optional[Any] = None
    adaptability: Optional[Mapping[str, Any]] = None
    sections: Sequence[tuple[str, str]] = ()
    notes: Sequence[str] = ()
    holdout_status: str = "closed"


# --------------------------------------------------------------------------- formatting
def _fmt(x, pct: bool = False) -> str:
    if x is None:
        return "—"
    if isinstance(x, (tuple, list)) and len(x) == 2 and all(isinstance(v, (int, float, np.floating)) for v in x):
        return f"[{_fmt(x[0], pct)}, {_fmt(x[1], pct)}]"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else "no"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        if not math.isfinite(x):
            return "n/a"
        return f"{x:.2%}" if pct else f"{x:.3f}"
    if isinstance(x, pd.Timestamp):
        return str(x.date())
    if isinstance(x, dict):
        return ", ".join(f"{k}: {_fmt(v, pct)}" for k, v in x.items())
    return str(x).replace("|", "/").replace("\n", " ")


def md_table(df: pd.DataFrame, index: bool = True, pct_cols: Sequence[str] = ()) -> str:
    """Render a DataFrame as a GitHub markdown table (no external dependency)."""
    if df is None or len(df.columns) == 0:
        return "_(empty)_"
    cols = ([df.index.name or ""] if index else []) + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for idx, row in df.iterrows():
        cells = [_fmt(idx)] if index else []
        cells += [_fmt(v, pct=str(c) in pct_cols) for c, v in row.items()]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def metrics_table(series: Mapping[str, pd.Series], reps: int = 1000, seed: int = 0,
                  index_name: str = "series") -> pd.DataFrame:
    """One row of :func:`perf_metrics` per named return series."""
    rows = {}
    for name, r in series.items():
        r = pd.Series(r, dtype=float).dropna()
        if len(r) == 0:
            continue
        m = perf_metrics(r, reps=reps, seed=seed)
        rows[str(name)] = {k: m[k] for k in _METRIC_COLS}
    df = pd.DataFrame.from_dict(rows, orient="index", columns=_METRIC_COLS)
    df.index.name = index_name
    return df


def metrics_by_year(returns: pd.Series, reps: int = 1000, seed: int = 0) -> pd.DataFrame:
    r = pd.Series(returns, dtype=float).dropna()
    return metrics_table({str(y): g for y, g in r.groupby(r.index.year)}, reps, seed, "year")


def metrics_by_symbol(symbol_returns: pd.DataFrame, reps: int = 1000, seed: int = 0) -> pd.DataFrame:
    return metrics_table({s: symbol_returns[s] for s in symbol_returns.columns}, reps, seed, "symbol")


def metrics_by_regime(returns: pd.Series, cells: pd.Series, reps: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Metrics of the returns grouped by the ex-ante regime cell attached to each day."""
    r = pd.Series(returns, dtype=float).dropna()
    lab = pd.Series(cells).reindex(r.index)
    ok = lab.notna()
    groups = {str(c): g for c, g in r[ok].groupby(lab[ok].astype(str))}
    if (~ok).any():
        groups["undefined"] = r[~ok]
    return metrics_table(groups, reps, seed, "regime")


def _pct_cols() -> list[str]:
    return sorted(_PCT)


# --------------------------------------------------------------------------- render
def _provenance(data: ReportData) -> list[str]:
    commits = data_commit()
    out = ["## Data provenance", "",
           f"- Harness git sha: `{git_sha()}`",
           "- Data commits (upstream sources): " + ", ".join(f"{k} `{v}`" for k, v in commits.items())]
    man = dict(data.manifest or {})
    if man:
        out.append(f"- Manifest digest: `{man.get('digest', 'n/a')}`")
        files = man.get("files") or {}
        if files:
            out += ["", "<details><summary>CSV SHA-256 (" + str(len(files)) + " files)</summary>", ""]
            out += [f"- `{k}`: `{v}`" for k, v in sorted(files.items())]
            out += ["", "</details>"]
    else:
        out.append("- Manifest: not recorded for this report")
    return out + [""]


def render_report(data: ReportData, reps: int = 1000, seed: int = 0) -> str:
    """Render the markdown report (see the module docstring for the mandatory sections)."""
    pct = _pct_cols()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# {data.experiment} — {data.title}", "",
           f"Generated {now}. Market: **{data.market}**. Trials: "
           + (", ".join(f"`{t}`" for t in data.trial_ids) if data.trial_ids else "none (not a trial)")
           + f". Holdout: {data.holdout_status}.", ""]
    out += ["## Warnings", "", f"- {SURVIVORSHIP_WARNING}"]
    if data.funding_used:
        out.append(f"- {FUNDING_WARNING}")
    if data.proxy:
        out.append(f"- {PROXY_WARNING}")
    out.append("- Published figures (papers, debate) are not targets; only these OOS numbers count.")
    out.append("")
    out += _provenance(data)

    r = pd.Series(data.returns, dtype=float).dropna()
    out += ["## Summary (OOS)", ""]
    if len(r):
        out += [md_table(metrics_table({"OOS": r}, reps, seed), pct_cols=pct), ""]
        if data.exposure:
            out += [md_table(pd.DataFrame([data.exposure], dtype=object), index=False), ""]
    else:
        out += ["_No returns._", ""]

    if data.configs is not None and not data.configs.empty:
        out += ["## Configurations (each alone, OOS)", "",
                md_table(metrics_table({c: data.configs[c] for c in data.configs}, reps, seed, "config"),
                         pct_cols=pct), ""]
    if data.selections is not None and not data.selections.empty:
        out += ["## Walk-forward selections (training only)", "", md_table(data.selections, index=False), ""]

    out += ["## By year", "", md_table(metrics_by_year(r, reps, seed), pct_cols=pct) if len(r) else "_n/a_", ""]
    out += ["## By symbol", ""]
    if data.symbol_returns is not None and not data.symbol_returns.empty:
        out += ["Daily contribution of each symbol to the portfolio return (net of its costs).", "",
                md_table(metrics_by_symbol(data.symbol_returns, reps, seed), pct_cols=pct), ""]
    else:
        out += ["_Single series: no per-symbol breakdown available._", ""]
    out += ["## By regime (ex-ante cell: trend_BTC x vol tercile)", ""]
    if data.cells is not None and len(r):
        out += [md_table(metrics_by_regime(r, data.cells, reps, seed), pct_cols=pct), ""]
    else:
        out += ["_Regime labels not available._", ""]

    if data.costs:
        out += ["## Costs (USDT, final configuration)", "", md_table(pd.DataFrame([data.costs], dtype=object),
                                                                       index=False), ""]
    if data.stress:
        out += ["## Mandatory stress (PLAN §5.4; not new trials)", "",
                md_table(metrics_table(dict(data.stress), reps, seed, "run"), pct_cols=pct), ""]
    if data.bench:
        out += ["## Benchmarks", "", md_table(metrics_table(dict(data.bench), reps, seed, "benchmark"),
                                              pct_cols=pct), ""]
    if data.random_entry is not None:
        re_ = data.random_entry
        out += ["## Random entries", "",
                f"- Candidate Sharpe {_fmt(getattr(re_, 'candidate_sharpe', None))}, "
                f"95th percentile of {len(getattr(re_, 'sharpes', []))} random draws "
                f"{_fmt(getattr(re_, 'threshold', None))}, percentile {_fmt(getattr(re_, 'percentile', None))}.", ""]
    if data.tail_events is not None and len(data.tail_events):
        out += ["## Tail events (2021-05-19, 2022-11-09, 2025-10-10)", "",
                md_table(data.tail_events.reset_index(), index=False), ""]
    if data.gate is not None:
        g = data.gate
        out += ["## Gate (PLAN §5.6)", "", f"**Level: {g.level}**", "", md_table(g.table(), index=False), ""]
        if g.overlay:
            out += ["Overlay increment:", "", md_table(pd.DataFrame([g.overlay], dtype=object), index=False), ""]
    if data.adaptability:
        a = data.adaptability
        keys = ["A_k", "q20", "penalty", "frac_positive", "worst_regime", "worst_regime_cvar95", "tau2",
                "n_cells", "t_years", "dsr"]
        row = {k: a.get(k) for k in keys if k in a}
        ne = a.get("n_eff") or {}
        row.update({"N_eff (PR)": ne.get("participation_ratio"), "N_eff n/(1+(n-1)rho)": ne.get("n_over_rho")})
        out += ["## Adaptability A_k (PLAN §3.3)", "", md_table(pd.DataFrame([row], dtype=object), index=False), ""]
    for title, body in data.sections:
        out += [f"## {title}", "", body, ""]
    if data.notes:
        out += ["## Notes", ""] + [f"- {n}" for n in data.notes] + [""]
    return "\n".join(out)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower() or "report"


def write_report(data: ReportData, out_dir: str | Path, reps: int = 1000, seed: int = 0,
                 summary: Optional[Mapping[str, Any]] = None) -> Path:
    """
    Write ``<out_dir>/<experiment>/<slug>.md`` (and ``.json`` with ``summary``
    plus the OOS returns as CSV) and return the markdown path.
    """
    d = Path(out_dir) / data.experiment
    d.mkdir(parents=True, exist_ok=True)
    stem = _slug(data.title)
    path = d / f"{stem}.md"
    path.write_text(render_report(data, reps, seed), encoding="utf-8")
    r = pd.Series(data.returns, dtype=float).dropna()
    if len(r):
        r.rename("returns").to_csv(d / f"{stem}_returns.csv", index_label="date")
    cfg = data.configs
    if isinstance(cfg, pd.DataFrame) and not cfg.empty:
        # Per-configuration OOS returns (ablations and DSR comparisons without new trials).
        cfg.astype(float).to_csv(d / f"{stem}_configs_returns.csv", index_label="date")
    if summary is not None:
        payload = {"experiment": data.experiment, "title": data.title, "market": data.market,
                   "trial_ids": list(data.trial_ids), "git_sha": git_sha(), "data_commit": data_commit(),
                   "manifest_digest": (data.manifest or {}).get("digest"), **dict(summary)}
        (d / f"{stem}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
                                        encoding="utf-8")
    return path


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        v = o.item()
        return None if isinstance(v, float) and not math.isfinite(v) else v
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Series, pd.DataFrame)):
        return None
    return str(o)
