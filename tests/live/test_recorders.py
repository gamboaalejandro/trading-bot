import gzip
import json
from datetime import datetime, timezone

import responses

from apps.live.recorders import PROD_REST, DailyJsonlWriter, Recorder

DAY = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_writer_appends_and_compresses_closed_days(tmp_path):
    w = DailyJsonlWriter(tmp_path)
    w.write("oi", [{"a": 1}], now=datetime(2026, 10, 25, 23, tzinfo=timezone.utc))
    w.write("oi", [{"a": 2}], now=DAY)
    gz = w.compress_closed_days(now=DAY)
    assert [p.name for p in gz] == ["2026-10-25.jsonl.gz"]
    with gzip.open(gz[0], "rt") as f:
        assert json.loads(f.readline())["a"] == 1
    assert _read(tmp_path / "oi" / "2026-10-26.jsonl")[0]["a"] == 2


@responses.activate
def test_poll_round_records_every_stream_and_survives_failures(tmp_path):
    responses.get(f"{PROD_REST}/fapi/v1/openInterest", json={"openInterest": "123.5", "time": 1})
    for path in ("globalLongShortAccountRatio", "topLongShortPositionRatio"):
        responses.get(f"{PROD_REST}/futures/data/{path}", json=[{"longShortRatio": "1.2", "timestamp": 1}])
    responses.get(f"{PROD_REST}/futures/data/takerlongshortRatio", status=500)  # failing stream
    responses.get(f"{PROD_REST}/fapi/v1/premiumIndex",
                  json=[{"symbol": "BTCUSDT", "markPrice": "1"}, {"symbol": "PEPEUSDT", "markPrice": "1"}])
    responses.get(f"{PROD_REST}/fapi/v1/fundingRate",
                  json=[{"fundingTime": 1000, "fundingRate": "0.0001"}, {"fundingTime": 2000, "fundingRate": "0.0002"}])

    rec = Recorder(out_dir=tmp_path, symbols=("BTCUSDT",))
    written = rec.poll_due(force=True)
    assert written == {"open_interest": 1, "global_lsr": 1, "top_lsr": 1, "premium_index": 1, "funding": 2}
    assert rec.errors == {"taker_ratio:BTCUSDT": 1}
    # premium index keeps only the universe
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert [r["symbol"] for r in _read(tmp_path / "premium_index" / f"{day}.jsonl")] == ["BTCUSDT"]
    # funding resumes after the last settlement it saw (also across restarts)
    assert Recorder(out_dir=tmp_path, symbols=("BTCUSDT",)).state["funding_last"]["BTCUSDT"] == 2000


def test_jobs_respect_their_interval(tmp_path):
    t = [0.0]
    rec = Recorder(out_dir=tmp_path, symbols=(), clock=lambda: t[0])
    calls = []
    for job in rec.jobs:
        job.per_symbol = False
        job.fetch = lambda s, sym, name=job.stream: calls.append(name) or []
    rec.poll_due()
    t[0] = 61
    rec.poll_due()
    assert calls.count("premium_index") == 2 and calls.count("open_interest") == 1


def test_liquidation_messages_filtered_by_universe(tmp_path):
    rec = Recorder(out_dir=tmp_path, symbols=("BTCUSDT",))
    msg = {"e": "forceOrder", "E": 5, "o": {"s": "BTCUSDT", "S": "SELL", "q": "0.1", "ap": "60000"}}
    assert rec.handle_liquidation(json.dumps(msg)) == 1
    assert rec.handle_liquidation(json.dumps({**msg, "o": {**msg["o"], "s": "PEPEUSDT"}})) == 0
