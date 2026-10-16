"""
Audit report of the live executor from its JSONL journal (no network, no secrets).

Usage:
    python scripts/audit_report.py [--journal data/live/executor_journal.jsonl] [--days 30]

Summarizes per day: run status, NAV, orders (filled/failed/skipped/blocked),
slippage of fills versus the model price, stops placed, kill-switch levels
and alerts. These are the monthly execution criteria of FINAL_REPORT §7(c).
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_JOURNAL = Path(__file__).resolve().parents[1] / "data" / "live" / "executor_journal.jsonl"


def load(path: Path) -> list:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def slippage_bps(order: dict) -> float:
    """Signed cost of a fill in bps versus ref_price (positive = paid more than the model)."""
    ref, avg = order.get("ref_price"), order.get("avg_price")
    if not ref or avg is None or not math.isfinite(avg) or avg <= 0:
        return float("nan")
    sign = 1 if order.get("side") == "BUY" else -1
    return sign * (avg / ref - 1) * 1e4


def summarize(records: list, days: int) -> str:
    by_day = defaultdict(lambda: {"status": None, "nav": None, "kill": None, "orders": defaultdict(int),
                                  "slip": [], "stops": 0, "alerts": [], "mode": None})
    for r in records:
        d = by_day[r.get("day") or r["ts"][:10]]
        d["mode"] = r.get("mode", d["mode"])
        ev = r["event"]
        if ev == "run_end":
            d["status"], d["nav"], d["kill"] = r.get("status"), r.get("nav"), r.get("kill_level")
        elif ev == "order":
            o = r["order"]
            d["orders"][o.get("status", "?")] += 1
            if o.get("status") == "filled":
                s = slippage_bps(o)
                if math.isfinite(s):
                    d["slip"].append(s)
        elif ev in ("order_skipped", "order_blocked"):
            d["orders"][ev.replace("order_", "")] += 1
        elif ev == "stop":
            d["stops"] += 1
        elif ev == "alert":
            d["alerts"].append(r.get("message", ""))

    keys = sorted(by_day)[-days:]
    lines = ["# Auditoría del bot", "",
             "| día | modo | estado | NAV | kill | filled | failed | skipped | blocked | slippage medio (pb) | stops | alertas |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    all_slip, incidents, navs = [], [], []
    for k in keys:
        d = by_day[k]
        o = d["orders"]
        slip = sum(d["slip"]) / len(d["slip"]) if d["slip"] else float("nan")
        all_slip += d["slip"]
        if d["nav"] is not None:
            navs.append(d["nav"])
        incidents += [f"{k}: {a}" for a in d["alerts"]]
        nav = f"{d['nav']:.2f}" if isinstance(d["nav"], (int, float)) else "-"
        lines.append(f"| {k} | {d['mode']} | {d['status'] or '-'} | {nav} | {d['kill'] or '-'} | {o['filled']} | "
                     f"{o['failed']} | {o['skipped']} | {o['blocked']} | "
                     f"{'-' if math.isnan(slip) else f'{slip:.1f}'} | {d['stops']} | {len(d['alerts'])} |")
    lines += ["", "## Resumen", ""]
    if navs:
        peak, mdd = navs[0], 0.0
        for v in navs:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1) if peak else mdd
        lines.append(f"- NAV: {navs[0]:.2f} -> {navs[-1]:.2f} ({(navs[-1] / navs[0] - 1) * 100:+.2f}%), "
                     f"drawdown máximo {mdd * 100:.2f}%")
    if all_slip:
        srt = sorted(all_slip)
        p95 = srt[min(len(srt) - 1, int(0.95 * len(srt)))]
        lines.append(f"- Slippage de fills: medio {sum(all_slip) / len(all_slip):.1f} pb, p95 {p95:.1f} pb "
                     f"(modelo: 2-15 pb según liquidez)")
    lines.append(f"- Incidencias/alertas: {len(incidents)}")
    lines += [f"  - {i}" for i in incidents[-20:]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    p.add_argument("--days", type=int, default=30)
    args = p.parse_args(argv)
    if not args.journal.exists():
        print(f"journal not found: {args.journal}", file=sys.stderr)
        return 1
    print(summarize(load(args.journal), args.days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
