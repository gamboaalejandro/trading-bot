"""Strict loaders for the local historical data (no network, never generates data).

Layout under the data root (see /home/user/harness/data/README.md):

- ``spot/{SYMBOL}_{tf}.csv`` and ``futures/{SYMBOL}_{tf}.csv``:
  ``timestamp,open,high,low,close,volume`` (timestamp = bar open time, ms UTC;
  volume in base asset).
- ``funding/{SYMBOL}.csv``: ``timestamp,funding_rate`` (fraction, 0.0001 = 0.01%).

Rules (docs/research/PLAN.md §5.2):

- Bars with ``volume == 0`` are masked as NaN (never forward-filled).
- Missing bars (exchange outages) are reindexed as NaN rows; never filled.
- Any missing file, uncovered range, duplicate, misaligned timestamp or
  invalid OHLC raises :class:`DataError`.
- BNBUSDT funding is excluded unless ``allow_bnb=True``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd

from apps.research.config import get_config
from apps.research.data.manifest import sha256_file, source_commit

Market = Literal["spot", "futures"]
Timeframe = Literal["15m", "1h", "4h", "1d"]

TF_DELTA: dict[str, pd.Timedelta] = {
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}
MARKETS = ("spot", "futures")
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
FUNDING_EXCLUDED = frozenset({"BNBUSDT"})
# Sanity bound for a single funding print as a fraction (exchange caps are ~2-3%).
# A value above it almost certainly means the file is in percent, not fraction.
MAX_ABS_FUNDING = 0.05

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}$")


class DataError(Exception):
    """Raised whenever requested data is missing, incomplete or invalid."""


def _default_root() -> Path:
    """Data root from config/research.yml, overridden by ``RESEARCH_DATA_ROOT``."""
    return get_config().data_root


#: Default data root at import time. Loaders resolve it again on every call
#: (``root=None``) so ``RESEARCH_DATA_ROOT`` can be changed at runtime.
DATA_ROOT: Path = _default_root()


def _root(root: str | os.PathLike | None) -> Path:
    return Path(root) if root is not None else _default_root()


def _check_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
        raise DataError(f"Invalid symbol {symbol!r}")
    return symbol


def ohlcv_path(symbol: str, market: str, tf: str, root: str | os.PathLike | None = None) -> Path:
    if market not in MARKETS:
        raise DataError(f"Unknown market {market!r}; expected one of {MARKETS}")
    if tf not in TF_DELTA:
        raise DataError(f"Unknown timeframe {tf!r}; expected one of {tuple(TF_DELTA)}")
    return _root(root) / market / f"{_check_symbol(symbol)}_{tf}.csv"


def funding_path(symbol: str, root: str | os.PathLike | None = None) -> Path:
    return _root(root) / "funding" / f"{_check_symbol(symbol)}.csv"


def _to_utc(ts: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if ts is None:
        return None
    try:
        t = pd.Timestamp(ts)
    except (ValueError, TypeError) as exc:
        raise DataError(f"Invalid timestamp {ts!r}") from exc
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise DataError(f"Data file not found: {path}")
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError) as exc:
        raise DataError(f"Cannot read {path}: {exc}") from exc
    missing = [c for c in ["timestamp", *columns] if c not in df.columns]
    if missing:
        raise DataError(f"{path}: missing columns {missing}")
    if df.empty:
        raise DataError(f"{path}: file is empty")
    df = df[["timestamp", *columns]]
    if df.isna().any().any():
        raise DataError(f"{path}: contains empty/NaN cells")
    try:
        ts = pd.to_numeric(df["timestamp"], errors="raise").astype("int64")
        values = df[columns].apply(pd.to_numeric, errors="raise").astype("float64")
    except (ValueError, TypeError) as exc:
        raise DataError(f"{path}: non-numeric values ({exc})") from exc
    if not np.isfinite(values.to_numpy()).all():
        raise DataError(f"{path}: non-finite values")
    index = pd.DatetimeIndex(pd.to_datetime(ts.to_numpy(), unit="ms", utc=True), name="open_time")
    if index.has_duplicates:
        dups = index[index.duplicated()].unique()[:5]
        raise DataError(f"{path}: duplicated timestamps, e.g. {list(map(str, dups))}")
    out = pd.DataFrame(values.to_numpy(), index=index, columns=columns)
    return out.sort_index()


def _validate_ohlcv(df: pd.DataFrame, path: Path, tf: str) -> None:
    step = TF_DELTA[tf]
    epoch = pd.Timestamp(0, tz="UTC")
    offsets = (df.index - epoch) % step
    if (offsets != pd.Timedelta(0)).any():
        bad = df.index[offsets != pd.Timedelta(0)][:5]
        raise DataError(f"{path}: timestamps not aligned to {tf}, e.g. {list(map(str, bad))}")
    o, h, l, c, v = (df[k] for k in OHLCV_COLUMNS)
    bad = (
        (o <= 0) | (h <= 0) | (l <= 0) | (c <= 0) | (v < 0)
        | (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)
    )
    if bad.any():
        raise DataError(f"{path}: {int(bad.sum())} invalid OHLC rows, first at {df.index[bad][0]}")


_RAW_CACHE: dict[tuple[str, int, int], pd.DataFrame] = {}


def _load_raw_ohlcv(path: Path, tf: str) -> pd.DataFrame:
    if not path.is_file():
        raise DataError(f"Data file not found: {path}")
    st = path.stat()
    key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    cached = _RAW_CACHE.get(key)
    if cached is None:
        cached = _read_csv(path, OHLCV_COLUMNS)
        _validate_ohlcv(cached, path, tf)
        if len(_RAW_CACHE) > 64:
            _RAW_CACHE.clear()
        _RAW_CACHE[key] = cached
    return cached.copy()


def _check_range(
    first: pd.Timestamp,
    last: pd.Timestamp,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
    step: pd.Timedelta,
    what: str,
) -> None:
    if start is not None and end is not None and start > end:
        raise DataError(f"{what}: start {start} is after end {end}")
    if start is not None and first > start.ceil(step):
        raise DataError(f"{what}: requested start {start} but data starts at {first}")
    if end is not None and last < end.floor(step):
        raise DataError(f"{what}: requested end {end} but data ends at {last}")


def load_ohlcv(
    symbol: str,
    market: Market,
    tf: Timeframe,
    start: str | None = None,
    end: str | None = None,
    root: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """Load closed OHLCV bars for ``symbol``.

    Returns a frame indexed by bar open time (UTC ``DatetimeIndex`` on a regular
    ``tf`` grid) with columns ``open, high, low, close, volume, quote_volume``
    (``quote_volume ~= volume * close``). ``start``/``end`` are inclusive bar
    open times. Bars with ``volume == 0`` and missing bars are NaN rows (no
    forward fill). Raises :class:`DataError` if the file or the requested range
    is missing, or if the file has duplicates, misaligned timestamps or
    invalid OHLC. Never generates data.
    """
    path = ohlcv_path(symbol, market, tf, root)
    step = TF_DELTA[tf]
    t0, t1 = _to_utc(start), _to_utc(end)

    df = _load_raw_ohlcv(path, tf)
    _check_range(df.index[0], df.index[-1], t0, t1, step, f"{market}/{symbol}_{tf}")

    if t0 is not None:
        df = df.loc[df.index >= t0]
    if t1 is not None:
        df = df.loc[df.index <= t1]
    if df.empty:
        raise DataError(f"{market}/{symbol}_{tf}: no bars in [{t0}, {t1}]")

    # Missing bars become explicit NaN rows; nothing is filled.
    grid = pd.date_range(df.index[0], df.index[-1], freq=step, name="open_time")
    df = df.reindex(grid)
    df.index.freq = None

    # Zero-volume bars are exchange outages padded by the source: mask them.
    df.loc[df["volume"] == 0, OHLCV_COLUMNS] = np.nan
    df["quote_volume"] = df["volume"] * df["close"]

    root_p = _root(root)
    df.attrs = {
        "symbol": symbol,
        "market": market,
        "tf": tf,
        "path": str(path),
        "relpath": str(path.relative_to(root_p)) if path.is_relative_to(root_p) else str(path),
        "sha256": sha256_file(path),
        "source_commit": source_commit(market),
        "proxy": False,
    }
    return df


def load_funding(
    symbol: str,
    root: str | os.PathLike | None = None,
    allow_bnb: bool = False,
    start: str | None = None,
    end: str | None = None,
) -> pd.Series:
    """Funding rate as a FRACTION (0.0001 = 0.01%), indexed by settlement time (UTC).

    The local funding is derived from the source (sampled at 00/08/16 UTC and on
    every change) and has NOT been verified against ``/fapi/v1/fundingRate``.
    BNBUSDT raises :class:`DataError` unless ``allow_bnb`` is set (PLAN §5.2.2).
    """
    if symbol in FUNDING_EXCLUDED and not allow_bnb:
        raise DataError(f"{symbol} funding is excluded (anomalous source data, PLAN §5.2.2)")
    path = funding_path(symbol, root)
    df = _read_csv(path, ["funding_rate"])
    rate = df["funding_rate"]
    if (rate.abs() > MAX_ABS_FUNDING).any():
        raise DataError(
            f"{path}: |funding_rate| > {MAX_ABS_FUNDING}; the file is probably in percent, not fraction"
        )
    t0, t1 = _to_utc(start), _to_utc(end)
    if t0 is not None and t1 is not None and t0 > t1:
        raise DataError(f"funding/{symbol}: start {t0} is after end {t1}")
    if t0 is not None and rate.index[0] > t0:
        raise DataError(f"funding/{symbol}: requested start {t0} but data starts at {rate.index[0]}")
    if t1 is not None and rate.index[-1] < t1.floor("8h"):
        raise DataError(f"funding/{symbol}: requested end {t1} but data ends at {rate.index[-1]}")
    if t0 is not None:
        rate = rate.loc[rate.index >= t0]
    if t1 is not None:
        rate = rate.loc[rate.index <= t1]
    rate = rate.rename("funding_rate")
    rate.index.name = "settlement_time"
    root_p = _root(root)
    rate.attrs = {
        "symbol": symbol,
        "market": "funding",
        "path": str(path),
        "relpath": str(path.relative_to(root_p)) if path.is_relative_to(root_p) else str(path),
        "sha256": sha256_file(path),
        "source_commit": source_commit("funding"),
        "verified": False,
    }
    return rate


def load_panel(
    symbols: Iterable[str],
    market: Market,
    tf: Timeframe,
    start: str | None = None,
    end: str | None = None,
    root: str | os.PathLike | None = None,
    allow_late_start: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load several symbols with :func:`load_ohlcv`.

    With ``allow_late_start=True`` a symbol listed after ``start`` is loaded from
    its first bar instead of raising (the end of the range must still be covered).
    """
    panel: dict[str, pd.DataFrame] = {}
    symbols = list(symbols)
    if not symbols:
        raise DataError("load_panel: empty symbol list")
    for sym in symbols:
        sym_start = start
        if allow_late_start and start is not None:
            raw = _load_raw_ohlcv(ohlcv_path(sym, market, tf, root), tf)
            first = raw.index[0]
            t0 = _to_utc(start)
            if first > t0:
                sym_start = str(first)
        panel[sym] = load_ohlcv(sym, market, tf, sym_start, end, root)
    return panel


def load_fng(path: str | os.PathLike) -> pd.Series:
    """Fear & Greed index (alternative.me export) as a daily UTC series named ``fng``.

    Accepts a CSV with a date column (``date`` or ``timestamp``; unix seconds,
    unix ms, ISO dates or alternative.me's ``DD-MM-YYYY``) and a value column
    (``fng_value``, ``value`` or ``fng``). Raises :class:`DataError` if the file
    is missing or invalid; there is no fallback.
    """
    p = Path(path)
    if not p.is_file():
        raise DataError(f"Fear & Greed file not found: {p} (provide the alternative.me CSV)")
    try:
        df = pd.read_csv(p)
    except (OSError, ValueError) as exc:
        raise DataError(f"Cannot read {p}: {exc}") from exc
    cols = {c.strip().lower(): c for c in df.columns}
    time_col = next((cols[c] for c in ("date", "timestamp", "time") if c in cols), None)
    value_col = next((cols[c] for c in ("fng_value", "value", "fng") if c in cols), None)
    if time_col is None or value_col is None or df.empty:
        raise DataError(f"{p}: expected a date/timestamp column and a value column")
    raw_t = df[time_col]
    try:
        if pd.api.types.is_numeric_dtype(raw_t):
            unit = "ms" if raw_t.abs().max() > 10**11 else "s"
            idx = pd.to_datetime(raw_t, unit=unit, utc=True)
        else:
            s = raw_t.astype(str).str.strip()
            if s.str.match(r"^\d{2}-\d{2}-\d{4}$").all():
                idx = pd.to_datetime(s, format="%d-%m-%Y", utc=True)
            else:
                idx = pd.to_datetime(s, utc=True)
        values = pd.to_numeric(df[value_col], errors="raise").astype("float64")
    except (ValueError, TypeError) as exc:
        raise DataError(f"{p}: cannot parse ({exc})") from exc
    idx = pd.DatetimeIndex(idx).normalize()
    fng = pd.Series(values.to_numpy(), index=idx, name="fng")
    fng.index.name = "date"
    if fng.index.has_duplicates:
        raise DataError(f"{p}: duplicated dates")
    if fng.isna().any() or ((fng < 0) | (fng > 100)).any():
        raise DataError(f"{p}: values must be in [0, 100] without gaps")
    fng = fng.sort_index()
    fng.attrs = {"path": str(p), "sha256": sha256_file(p)}
    return fng
