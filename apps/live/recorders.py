"""
Market data recorders (PLAN §4.6, phase F4).

Binance only serves ~30 days of open interest / long-short ratios and no
history of liquidations, so they must be RECORDED from now on to be usable
in a future research cycle (FINAL_REPORT §7(c)). This module polls public
USDT-M futures endpoints and listens to the liquidation stream, appending
one JSON object per line to

    data/recorders/<stream>/<YYYY-MM-DD>.jsonl      (UTC day)

Closed days are gzip-compressed. Nothing here trades and no API key is
needed; a failure of one stream never stops the others.

Streams (public, no key):
    open_interest   GET /fapi/v1/openInterest                     every 5 min, per symbol
    global_lsr      GET /futures/data/globalLongShortAccountRatio  every 5 min, per symbol
    top_lsr         GET /futures/data/topLongShortPositionRatio    every 5 min, per symbol
    taker_ratio     GET /futures/data/takerlongshortRatio          every 5 min, per symbol
    premium_index   GET /fapi/v1/premiumIndex (all symbols)        every 1 min
    funding         GET /fapi/v1/fundingRate                       every 8 h, per symbol (full history on first run)
    liquidations    WS  <ws_base>/ws/!forceOrder@arr               continuous

Usage:
    python -m apps.live.recorders                 # run forever
    python -m apps.live.recorders --once          # one polling round (smoke test)
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "recorders"
PROD_REST = "https://fapi.binance.com"
PROD_WS = "wss://fstream.binance.com"

# Researched futures universe (PLAN §5.1)
FUTURES_UNIVERSE = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "DOTUSDT",
    "TRXUSDT", "LTCUSDT", "BCHUSDT", "SOLUSDT", "AVAXUSDT", "NEARUSDT", "OPUSDT", "APTUSDT",
    "ARBUSDT", "SUIUSDT",
)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class DailyJsonlWriter:
    """Append records to <root>/<stream>/<UTC day>.jsonl; gzip closed days."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def path_for(self, stream: str, day: str) -> Path:
        return self.root / stream / f"{day}.jsonl"

    def write(self, stream: str, records: Iterable[Dict[str, Any]], now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        recv = int(now.timestamp() * 1000)
        path = self.path_for(stream, now.strftime("%Y-%m-%d"))
        path.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with open(path, "a") as f:
            for rec in records:
                f.write(json.dumps({"recv_ms": recv, **rec}, separators=(",", ":")) + "\n")
                n += 1
        return n

    def compress_closed_days(self, now: Optional[datetime] = None) -> List[Path]:
        """Gzip every .jsonl older than today (UTC). Returns the new .gz paths."""
        today = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        done = []
        for path in sorted(self.root.glob("*/*.jsonl")):
            if path.stem >= today:
                continue
            gz = path.with_suffix(".jsonl.gz")
            with open(path, "rb") as src, gzip.open(gz, "ab") as dst:
                shutil.copyfileobj(src, dst)
            path.unlink()
            done.append(gz)
        return done


# ---------------------------------------------------------------------------
# REST polling
# ---------------------------------------------------------------------------

@dataclass
class PollJob:
    """One polled stream: ``fetch(session, symbol_or_None) -> list of records``."""

    stream: str
    interval_s: float
    fetch: Callable[[requests.Session, Optional[str]], List[Dict[str, Any]]]
    per_symbol: bool = True
    next_due: float = 0.0


def _get(session: requests.Session, base: str, path: str, params: Dict[str, Any]) -> Any:
    resp = session.get(f"{base}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def build_jobs(base: str, state: Dict[str, Any]) -> List[PollJob]:
    """Polling jobs against ``base``. ``state`` keeps the last funding time per symbol."""

    def open_interest(s, sym):
        d = _get(s, base, "/fapi/v1/openInterest", {"symbol": sym})
        return [{"symbol": sym, "open_interest": float(d["openInterest"]), "time": d.get("time")}]

    def ratio(path):
        def fetch(s, sym):
            rows = _get(s, base, path, {"symbol": sym, "period": "5m", "limit": 1})
            return [{"symbol": sym, **r} for r in rows]
        return fetch

    def premium_index(s, _):
        rows = _get(s, base, "/fapi/v1/premiumIndex", {})
        rows = rows if isinstance(rows, list) else [rows]
        return [r for r in rows if r.get("symbol") in FUTURES_UNIVERSE]

    def funding(s, sym):
        # First run: whole history (1000 per page); then only new settlements
        last = state.setdefault("funding_last", {}).get(sym, 0)
        out = []
        while True:
            rows = _get(s, base, "/fapi/v1/fundingRate", {"symbol": sym, "startTime": last + 1, "limit": 1000})
            if not rows:
                break
            out.extend({"symbol": sym, **r} for r in rows)
            last = max(int(r["fundingTime"]) for r in rows)
            if len(rows) < 1000:
                break
        state["funding_last"][sym] = last
        return out

    return [
        PollJob("open_interest", 300, open_interest),
        PollJob("global_lsr", 300, ratio("/futures/data/globalLongShortAccountRatio")),
        PollJob("top_lsr", 300, ratio("/futures/data/topLongShortPositionRatio")),
        PollJob("taker_ratio", 300, ratio("/futures/data/takerlongshortRatio")),
        PollJob("premium_index", 60, premium_index, per_symbol=False),
        PollJob("funding", 8 * 3600, funding),
    ]


@dataclass
class Recorder:
    """Runs the polling jobs and the liquidation stream; never trades."""

    out_dir: Path = DEFAULT_OUT_DIR
    symbols: tuple = FUTURES_UNIVERSE
    rest_base: str = PROD_REST
    ws_base: str = PROD_WS
    session: requests.Session = field(default_factory=requests.Session)
    clock: Callable[[], float] = time.monotonic
    state_path: Optional[Path] = None

    def __post_init__(self):
        self.writer = DailyJsonlWriter(self.out_dir)
        self.state_path = self.state_path or Path(self.out_dir) / "recorder_state.json"
        self.state = self._load_state()
        self.jobs = build_jobs(self.rest_base, self.state)
        self.errors: Dict[str, int] = {}

    def _load_state(self) -> Dict[str, Any]:
        try:
            return json.loads(Path(self.state_path).read_text())
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        Path(self.state_path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(self.state_path) + ".tmp")
        tmp.write_text(json.dumps(self.state))
        os.replace(tmp, self.state_path)

    def poll_due(self, force: bool = False) -> Dict[str, int]:
        """Run every job that is due (all of them with ``force``). Returns records written per stream."""
        written: Dict[str, int] = {}
        now = self.clock()
        for job in self.jobs:
            if not force and now < job.next_due:
                continue
            job.next_due = now + job.interval_s
            targets = self.symbols if job.per_symbol else (None,)
            for sym in targets:
                try:
                    recs = job.fetch(self.session, sym)
                    written[job.stream] = written.get(job.stream, 0) + self.writer.write(job.stream, recs)
                except Exception as exc:  # one failing symbol/stream never stops the rest
                    key = f"{job.stream}:{sym}"
                    self.errors[key] = self.errors.get(key, 0) + 1
                    logger.warning("recorder %s failed: %s", key, exc)
        self._save_state()
        return written

    def handle_liquidation(self, message: str) -> int:
        """Store one !forceOrder@arr message (``o`` holds the order)."""
        data = json.loads(message)
        order = data.get("o", {})
        if order.get("s") not in self.symbols:
            return 0
        return self.writer.write("liquidations", [{"event_time": data.get("E"), **order}])

    async def _liquidations_forever(self) -> None:
        import websockets

        url = f"{self.ws_base}/ws/!forceOrder@arr"
        delay = 1.0
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    delay = 1.0
                    async for msg in ws:
                        self.handle_liquidation(msg)
            except Exception as exc:
                logger.warning("liquidation stream error: %s (reconnect in %.0fs)", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

    async def _poll_forever(self) -> None:
        last_day = datetime.now(timezone.utc).date()
        while True:
            await asyncio.to_thread(self.poll_due)
            today = datetime.now(timezone.utc).date()
            if today != last_day:
                await asyncio.to_thread(self.writer.compress_closed_days)
                last_day = today
            await asyncio.sleep(5)

    async def run_forever(self) -> None:
        self.writer.compress_closed_days()
        await asyncio.gather(self._poll_forever(), self._liquidations_forever())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Record futures OI, ratios, premium index, funding and liquidations")
    p.add_argument("--once", action="store_true", help="one polling round, then exit")
    p.add_argument("--out", type=Path, default=Path(os.getenv("RECORDER_OUT_DIR", DEFAULT_OUT_DIR)))
    p.add_argument("--rest-base", default=os.getenv("RECORDER_REST_BASE", PROD_REST))
    p.add_argument("--ws-base", default=os.getenv("RECORDER_WS_BASE", PROD_WS))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    rec = Recorder(out_dir=args.out, rest_base=args.rest_base, ws_base=args.ws_base)
    if args.once:
        written = rec.poll_due(force=True)
        logger.info("written %s, errors %s", written, rec.errors)
        return 0 if written else 1
    asyncio.run(rec.run_forever())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
