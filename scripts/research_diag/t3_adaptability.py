"""Usage: PYTHONPATH=. python scripts/research_diag/t3_adaptability.py <out_dir>

Diagnostic (no new trial, no registration): A_k and OOS series of TREND T3 alone per market."""
import json, sys
from pathlib import Path
import pandas as pd
from apps.research.run import Runner, Settings, _trend_specs, _daily_data, symbol_contributions, _closes
from apps.research.validation.walkforward import walk_forward, BacktestCandidate, oos_weights
from apps.research.features.regime import ex_ante_cells
from apps.research.validation.adaptability import adaptability_score
from apps.research.validation.metrics import sharpe

out_dir = Path(sys.argv[1])
r = Runner(Settings(agent="diag", resume=True, reports_dir=out_dir))

res = {}
for market in ("spot", "futures"):
    spec = _trend_specs(r, ("T3",))[0]
    tid = r.trials.find(spec.family, spec.params); assert tid, "T3 not registered"
    spec.trial_id = tid
    data = _daily_data(r, market, r.common)
    cand = BacktestCandidate("T3", spec.build(market, data), dict(spec.params), spec.n_free_params, tid)
    wf = walk_forward([cand], data["panel"], r.folds)
    full = cand.result(r.anchor, r.folds[-1].test_end)
    contrib = oos_weights(wf.selections, {"T3": symbol_contributions(full, _closes(data["panel"]))})
    cells = ex_ante_cells(data["btc"])
    a = adaptability_score(contrib, cells, spec.n_free_params)
    oos = wf.oos_returns.dropna()
    oos.to_csv(out_dir / f"t3_{market}_oos.csv")
    res[market] = {"trial_id": tid, "sharpe_oos": float(sharpe(oos)), "sharpe_contrib_sum": float(sharpe(contrib.sum(axis=1))),
                   **{k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in a.items() if k not in ("cells", "n_eff")}}
print(json.dumps(res, indent=1))
json.dump(res, open(out_dir / "t3_ak.json", "w"), indent=1)
