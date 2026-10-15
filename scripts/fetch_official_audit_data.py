#!/usr/bin/env python
"""
Download official Binance data to audit the local research dataset.

Meant to run on the user's machine (this project's container gets HTTP 403
from Binance). Only public GET endpoints are used, plus an optional signed GET
(``/fapi/v1/commissionRate``) when ``--with-commission`` is passed and the
production keys are exported (read-only use; nothing is ever traded).

Downloads (PLAN §8.6):
    - /fapi/v1/fundingRate (full history, 18 perps) -> funding/{SYM}.csv (fraction)
    - /fapi/v1/fundingInfo                          -> funding_info.json
    - /fapi/v1/markPriceKlines 1d (18 perps)        -> mark_klines_1d/{SYM}.csv
    - /fapi/v1/klines 1d (18 perps)                 -> futures_klines_1d/{SYM}.csv
    - /api/v3/klines 1d (10 spot symbols)           -> spot_klines_1d/{SYM}.csv
    - /fapi/v1/exchangeInfo, /api/v3/exchangeInfo   -> *_exchange_info.json (minNotional)
    - optional: /fapi/v1/commissionRate, Fear & Greed CSV (alternative.me)
Every file is listed in manifest.json with its sha256, source URL and row count.

With ``--local-data /path/to/harness/data`` an audit_report.json compares the
official funding and daily closes with the local CSVs.

Usage:
    python scripts/fetch_official_audit_data.py --out data/audit/2026-10-15 \\
        --local-data /path/to/harness/data [--with-commission] [--fng]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.binance_futures_client import PRODUCTION_BASE_URL, BinanceFuturesClient  # noqa: E402

SPOT_BASE_URL = "https://api.binance.com"
FNG_URL = "https://api.alternative.me/fng/?limit=0&format=csv"

FUTURES_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT",
                   "DOTUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "SOLUSDT", "AVAXUSDT", "NEARUSDT",
                   "OPUSDT", "APTUSDT", "ARBUSDT", "SUIUSDT"]
SPOT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
                "AVAXUSDT", "LINKUSDT", "DOTUSDT"]
FUTURES_START = "2019-09-01"
SPOT_START = "2017-08-01"
DAY_MS = 86_400_000


def to_ms(date: str) -> int:
    return int(pd.Timestamp(date, tz="UTC").value // 1_000_000)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def paginate_klines(fetch: Callable[[int, int], list], start_ms: int, end_ms: int,
                    limit: int, pause: float = 0.0) -> list:
    """Generic kline pagination: ``fetch(start, limit)`` returns raw kline rows."""
    rows: list = []
    cursor = start_ms
    while cursor < end_ms:
        batch = fetch(cursor, limit)
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= cursor or len(batch) < limit:
            break
        cursor = nxt
        if pause:
            time.sleep(pause)
    # de-duplicate by open time, keep order
    seen, out = set(), []
    for r in rows:
        if int(r[0]) < end_ms and int(r[0]) not in seen:
            seen.add(int(r[0]))
            out.append(r)
    return out


def klines_to_frame(rows: list, server_time_ms: int) -> pd.DataFrame:
    """Closed klines only, in the local CSV layout (timestamp = open time, ms UTC)."""
    df = pd.DataFrame([r[:7] for r in rows],
                      columns=["timestamp", "open", "high", "low", "close", "volume", "close_time"])
    if df.empty:
        return df[["timestamp", "open", "high", "low", "close", "volume"]]
    df = df.astype({"timestamp": "int64", "close_time": "int64", "open": float, "high": float,
                    "low": float, "close": float, "volume": float})
    df = df[df["close_time"] < server_time_ms]
    return df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def compare_funding(official: pd.DataFrame, local_csv: Path) -> Dict[str, Any]:
    """
    Compare official settled funding (timestamp ms, funding_rate fraction) with a
    local ``timestamp,funding_rate`` CSV. Timestamps are floored to the minute
    (official fundingTime carries a few ms of jitter).
    """
    if not local_csv.exists():
        return {"status": "local_missing"}
    local = pd.read_csv(local_csv)
    o = official.assign(ts=(official["timestamp"] // 60_000) * 60_000).drop_duplicates("ts").set_index("ts")
    l = local.assign(ts=(local["timestamp"] // 60_000) * 60_000).drop_duplicates("ts").set_index("ts")
    lo, hi = max(o.index.min(), l.index.min()), min(o.index.max(), l.index.max())
    o_w = o.loc[lo:hi, "funding_rate"]
    l_w = l.loc[lo:hi, "funding_rate"]
    joined = pd.concat([o_w.rename("official"), l_w.rename("local")], axis=1, join="inner")
    diff = (joined["official"] - joined["local"]).abs()
    hours = pd.to_datetime(o_w.index, unit="ms", utc=True).hour
    off_8h = int((~pd.Index(hours).isin([0, 8, 16])).sum())
    return {
        "status": "ok",
        "overlap_start": int(lo), "overlap_end": int(hi),
        "n_official": int(len(o_w)), "n_local": int(len(l_w)), "n_matched": int(len(joined)),
        "official_missing_locally": int(len(o_w.index.difference(l_w.index))),
        "local_not_official": int(len(l_w.index.difference(o_w.index))),
        "share_exact": float((diff < 1e-12).mean()) if len(diff) else None,
        "max_abs_diff": float(diff.max()) if len(diff) else None,
        "median_abs_diff": float(diff.median()) if len(diff) else None,
        "official_settlements_off_8h_grid": off_8h,
        "official_sum": float(o_w.sum()), "local_sum": float(l_w.sum()),
    }


def compare_closes(official: pd.DataFrame, local_csv: Path) -> Dict[str, Any]:
    """Compare official daily closes with a local OHLCV CSV (same open-time timestamps)."""
    if not local_csv.exists():
        return {"status": "local_missing"}
    local = pd.read_csv(local_csv).set_index("timestamp")
    off = official.set_index("timestamp")
    joined = off[["close"]].join(local[["close"]], how="inner", lsuffix="_official", rsuffix="_local")
    if joined.empty:
        return {"status": "no_overlap", "n_official": int(len(off)), "n_local": int(len(local))}
    rel = (joined["close_official"] / joined["close_local"] - 1.0).abs()
    return {
        "status": "ok",
        "n_official": int(len(off)), "n_local": int(len(local)), "n_matched": int(len(joined)),
        "share_exact": float((rel < 1e-9).mean()),
        "max_rel_diff": float(rel.max()),
        "p99_rel_diff": float(np.quantile(rel, 0.99)),
    }


class AuditDownloader:
    def __init__(self, out: Path, futures: BinanceFuturesClient, session: requests.Session,
                 spot_base_url: str = SPOT_BASE_URL, pause: float = 0.25):
        self.out = out
        self.fut = futures
        self.session = session
        self.spot_base_url = spot_base_url.rstrip("/")
        self.pause = pause
        self.manifest: Dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(),
                                         "futures_base_url": futures.base_url,
                                         "spot_base_url": self.spot_base_url, "files": {}}
        out.mkdir(parents=True, exist_ok=True)

    def _record(self, path: Path, source: str, rows: Optional[int] = None) -> None:
        self.manifest["files"][str(path.relative_to(self.out))] = {
            "sha256": sha256_file(path), "source": source, "rows": rows}

    def _write_json(self, rel: str, data: Any, source: str) -> Path:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=1, sort_keys=True))
        self._record(p, source, len(data) if isinstance(data, list) else None)
        return p

    def _write_csv(self, rel: str, df: pd.DataFrame, source: str) -> Path:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)
        self._record(p, source, int(len(df)))
        return p

    def _spot_get(self, path: str, params: Dict[str, Any]) -> Any:
        r = self.session.get(f"{self.spot_base_url}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def funding(self, symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
        df = self.fut.funding_rate(symbol, start_ms=start_ms, end_ms=end_ms)
        out = pd.DataFrame({"timestamp": df["funding_time_ms"].to_numpy(),
                            "funding_rate": df["funding_rate"].to_numpy(),
                            "mark_price": df["mark_price"].to_numpy()})
        self._write_csv(f"funding/{symbol}.csv", out, f"{self.fut.base_url}/fapi/v1/fundingRate")
        return out

    def futures_klines(self, symbol: str, start_ms: int, end_ms: int, server_ms: int,
                       mark: bool = False) -> pd.DataFrame:
        path = "/fapi/v1/markPriceKlines" if mark else "/fapi/v1/klines"
        rows = paginate_klines(
            lambda s, lim: self.fut._request("GET", path, {"symbol": symbol, "interval": "1d",
                                                           "startTime": s, "endTime": end_ms, "limit": lim}),
            start_ms, end_ms, 1500, self.pause)
        df = klines_to_frame(rows, server_ms)
        folder = "mark_klines_1d" if mark else "futures_klines_1d"
        self._write_csv(f"{folder}/{symbol}.csv", df, f"{self.fut.base_url}{path}")
        return df

    def spot_klines(self, symbol: str, start_ms: int, end_ms: int, server_ms: int) -> pd.DataFrame:
        rows = paginate_klines(
            lambda s, lim: self._spot_get("/api/v3/klines", {"symbol": symbol, "interval": "1d",
                                                             "startTime": s, "endTime": end_ms, "limit": lim}),
            start_ms, end_ms, 1000, self.pause)
        df = klines_to_frame(rows, server_ms)
        self._write_csv(f"spot_klines_1d/{symbol}.csv", df, f"{self.spot_base_url}/api/v3/klines")
        return df

    def save_manifest(self) -> Path:
        p = self.out / "manifest.json"
        p.write_text(json.dumps(self.manifest, indent=1, sort_keys=True))
        return p


def main(argv: Optional[List[str]] = None, session: Optional[requests.Session] = None) -> int:
    ap = argparse.ArgumentParser(description="Download official Binance data to audit local CSVs (read-only).")
    ap.add_argument("--out", default=f"data/audit/{datetime.now(timezone.utc):%Y-%m-%d}")
    ap.add_argument("--local-data", default=None, help="harness data root (spot/, futures/, funding/)")
    ap.add_argument("--futures-symbols", default=",".join(FUTURES_SYMBOLS))
    ap.add_argument("--spot-symbols", default=",".join(SPOT_SYMBOLS))
    ap.add_argument("--futures-start", default=FUTURES_START)
    ap.add_argument("--spot-start", default=SPOT_START)
    ap.add_argument("--futures-base-url", default=PRODUCTION_BASE_URL,
                    help="public market data comes from production by default (testnet data is not real)")
    ap.add_argument("--spot-base-url", default=SPOT_BASE_URL)
    ap.add_argument("--with-commission", action="store_true",
                    help="also GET /fapi/v1/commissionRate with BINANCE_API_KEY/SECRET (read-only)")
    ap.add_argument("--fng", action="store_true", help="also download the Fear & Greed CSV")
    ap.add_argument("--pause", type=float, default=0.25, help="seconds between paginated requests")
    args = ap.parse_args(argv)

    session = session or requests.Session()
    out = Path(args.out)
    key = secret = ""
    if args.with_commission:
        from core.secrets import get_credentials
        creds = get_credentials("live")
        key, secret = creds.api_key, creds.api_secret
    fut = BinanceFuturesClient(key, secret, base_url=args.futures_base_url, read_only=True, session=session)
    dl = AuditDownloader(out, fut, session, spot_base_url=args.spot_base_url, pause=args.pause)

    fsyms = [s for s in args.futures_symbols.split(",") if s]
    ssyms = [s for s in args.spot_symbols.split(",") if s]
    server_ms = fut.server_time()
    report: Dict[str, Any] = {"server_time": server_ms, "funding": {}, "futures_close": {}, "spot_close": {}}
    errors: Dict[str, str] = {}

    def guarded(name: str, fn: Callable[[], Any]) -> Any:
        try:
            print(f"- {name}")
            return fn()
        except Exception as e:  # noqa: BLE001 - keep going, report at the end
            errors[name] = f"{type(e).__name__}: {e}"
            print(f"  ERROR {errors[name]}")
            return None

    guarded("futures exchangeInfo", lambda: dl._write_json(
        "futures_exchange_info.json", fut.exchange_info(), f"{fut.base_url}/fapi/v1/exchangeInfo"))
    guarded("spot exchangeInfo", lambda: dl._write_json(
        "spot_exchange_info.json", dl._spot_get("/api/v3/exchangeInfo", {}), f"{dl.spot_base_url}/api/v3/exchangeInfo"))
    guarded("fundingInfo", lambda: dl._write_json(
        "funding_info.json", fut.funding_info(), f"{fut.base_url}/fapi/v1/fundingInfo"))

    local = Path(args.local_data) if args.local_data else None
    f_start, s_start = to_ms(args.futures_start), to_ms(args.spot_start)
    for sym in fsyms:
        fr = guarded(f"{sym} fundingRate", lambda: dl.funding(sym, f_start, server_ms))
        guarded(f"{sym} markPriceKlines 1d", lambda: dl.futures_klines(sym, f_start, server_ms, server_ms, mark=True))
        fk = guarded(f"{sym} futures klines 1d", lambda: dl.futures_klines(sym, f_start, server_ms, server_ms))
        if local is not None and fr is not None and len(fr):
            report["funding"][sym] = compare_funding(fr, local / "funding" / f"{sym}.csv")
        if local is not None and fk is not None and len(fk):
            report["futures_close"][sym] = compare_closes(fk, local / "futures" / f"{sym}_1d.csv")
    for sym in ssyms:
        sk = guarded(f"{sym} spot klines 1d", lambda: dl.spot_klines(sym, s_start, server_ms, server_ms))
        if local is not None and sk is not None and len(sk):
            report["spot_close"][sym] = compare_closes(sk, local / "spot" / f"{sym}_1d.csv")

    if args.with_commission:
        guarded("commissionRate", lambda: dl._write_json(
            "commission_rate.json", {s: fut.commission_rate(s) for s in fsyms},
            f"{fut.base_url}/fapi/v1/commissionRate"))
    if args.fng:
        def _fng() -> None:
            r = session.get(FNG_URL, timeout=30)
            r.raise_for_status()
            p = out / "fear_greed.csv"
            p.write_bytes(r.content)
            dl._record(p, FNG_URL)
        guarded("Fear & Greed", _fng)

    report["errors"] = errors
    if local is not None:
        (out / "audit_report.json").write_text(json.dumps(report, indent=1, sort_keys=True))
        dl._record(out / "audit_report.json", "computed")
    dl.save_manifest()
    print(f"\nDone: {len(dl.manifest['files'])} files in {out} ({len(errors)} errors)")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
