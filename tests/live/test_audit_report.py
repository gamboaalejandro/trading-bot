import json

from scripts.audit_report import load, slippage_bps, summarize


def test_slippage_sign():
    assert slippage_bps({"side": "BUY", "ref_price": 100.0, "avg_price": 100.1}) > 0
    assert slippage_bps({"side": "SELL", "ref_price": 100.0, "avg_price": 100.1}) < 0


def test_summarize_journal(tmp_path):
    rows = [
        {"ts": "2026-11-01T00:05:00", "day": "2026-11-01", "event": "order", "mode": "spot_demo",
         "order": {"status": "filled", "side": "BUY", "ref_price": 100.0, "avg_price": 100.05}},
        {"ts": "2026-11-01T00:05:01", "day": "2026-11-01", "event": "stop", "mode": "spot_demo"},
        {"ts": "2026-11-01T00:05:02", "day": "2026-11-01", "event": "run_end", "mode": "spot_demo",
         "status": "ok", "nav": 100.0, "kill_level": "normal"},
        {"ts": "2026-11-02T00:05:02", "day": "2026-11-02", "event": "alert", "mode": "spot_demo",
         "message": "stop missing"},
        {"ts": "2026-11-02T00:05:03", "day": "2026-11-02", "event": "run_end", "mode": "spot_demo",
         "status": "ok", "nav": 98.0, "kill_level": "normal"},
    ]
    path = tmp_path / "j.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    out = summarize(load(path), 30)
    assert "| 2026-11-01 | spot_demo | ok | 100.00 |" in out
    assert "drawdown máximo -2.00%" in out
    assert "Incidencias/alertas: 1" in out
