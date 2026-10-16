"""Usage: PYTHONPATH=. python scripts/research_diag/e5_preregistered_rules.py <diag_dir> <spot_configs_csv|none> <spot,futures>

Pre-registered E5 rules (DSR vs T3, ablations B3/B4/B5) from committed OOS CSVs. Read-only on the trials log."""
import json, math, sys
import numpy as np, pandas as pd
from apps.research.validation.trials_log import TrialsLog
from apps.research.validation.gate import trials_sharpe_var
from apps.research.validation.stats import dsr, moments, sharpe_se, bootstrap_pvalue_diff, holm, psr
from apps.research.validation.metrics import sharpe, sharpe_diff_se, PERIODS_PER_YEAR

R = "docs/research/results/"
D = sys.argv[1]  # diagnostics dir (T3 OOS CSVs in, JSON out)
cfg_csv = {"spot": sys.argv[2], "futures": R + "E5/brk4h_futures_configs_returns.csv"}
markets = sys.argv[3].split(",")
tl = TrialsLog("data/trials/trials.jsonl")
N = tl.n_total(); V = trials_sharpe_var(tl)
K = math.sqrt(PERIODS_PER_YEAR)
def rd(p, col=None):
    d = pd.read_csv(p, index_col=0, parse_dates=True)
    return d if col is None else d[col] if col in d else d.iloc[:, 0]
def dsr_of(r):
    r = r.dropna(); sr_d = sharpe(r) / K; g3, g4 = moments(r.to_numpy())
    return {"sharpe": sharpe(r), "dsr": dsr(sr_d, len(r), g3, g4, V, N), "psr0": psr(sr_d, len(r), g3, g4), "T": len(r)}
out = {"N": N, "V_sr_daily": V, "trial_counts": {}}
for f in ("BRK4H", "CARRY", "TREND", "DEBATE"): out["trial_counts"][f] = tl.n_family(f)
out["carry"] = dsr_of(rd(R + "E6/carry_k1_k3_paper_returns.csv").iloc[:, 0])
for m in markets:
    fam = rd(R + f"E5/brk4h_{m}_returns.csv").iloc[:, 0]
    t3 = rd(f"{D}/t3_{m}_oos.csv").iloc[:, 0]
    d_f, d_t = dsr_of(fam), dsr_of(t3)
    both = pd.concat([fam.rename("f"), t3.rename("t")], axis=1).dropna()
    dS, seS = sharpe_diff_se(both["f"], both["t"])
    res = {"brk4h_family": d_f, "t3": d_t, "beats_t3_dsr": bool(d_f["dsr"] > d_t["dsr"]),
           "sharpe_diff_family_minus_t3": dS, "se_sharpe_diff": seS}
    C = rd(cfg_csv[m]).dropna()
    b1 = C["B1"]; g3, g4 = moments(b1.to_numpy())
    se_b1 = sharpe_se(sharpe(b1) / K, len(b1), g3, g4) * K
    tests = {"ADX (B1-B3)": ("B1", "B3"), "funding (B1-B4)": ("B1", "B4"), "volume (B5-B1)": ("B5", "B1")}
    ab = {}
    for name, (a, b) in tests.items():
        p = bootstrap_pvalue_diff(C[a].to_numpy(), C[b].to_numpy(), block_mean=20, reps=10_000, seed=0)
        ds = sharpe(C[a]) - sharpe(C[b])
        ab[name] = {"sharpe_a": sharpe(C[a]), "sharpe_b": sharpe(C[b]), "d_sharpe": ds, "se_b1": se_b1,
                    "p_boot": p, "adds_value": bool(p < 0.05 or ds > se_b1)}
    rej, padj = holm([v["p_boot"] for v in ab.values()])
    for (k, v), pa, rj in zip(ab.items(), padj, rej):
        v["p_holm"] = float(pa); v["holm_reject"] = bool(rj)
    res["ablations"] = ab; res["n_days_cfg"] = len(C)
    out[m] = res
json.dump(out, open(f"{D}/e5_rules_{'_'.join(markets)}.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
