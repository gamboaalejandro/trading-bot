"""Strict data loader (PLAN R01).

Unit tests use tiny hand-written CSV fixtures; integration tests read the real
data under /home/user/harness/data and are skipped when it is not present.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.data import loader
from apps.research.data.loader import (
    DataError,
    load_fng,
    load_funding,
    load_ohlcv,
    load_panel,
)
from apps.research.data.manifest import manifest_from_frames

DAY_MS = 86_400_000
T0 = 1_600_000_000_000 - (1_600_000_000_000 % DAY_MS)  # 2020-09-13 00:00 UTC


def _write_ohlcv(root, market, symbol, tf, rows):
    d = Path(root) / market
    d.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.to_csv(d / f"{symbol}_{tf}.csv", index=False)


def _daily_rows(n, start_ms=T0, skip=(), zero_vol=()):
    rows = []
    for i in range(n):
        if i in skip:
            continue
        price = 100.0 + i
        vol = 0.0 if i in zero_vol else 10.0
        rows.append([start_ms + i * DAY_MS, price, price + 2, price - 2, price + 1, vol])
    return rows


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DATA_ROOT", str(tmp_path))
    _write_ohlcv(tmp_path, "futures", "AAAUSDT", "1d", _daily_rows(10, skip=(4,), zero_vol=(6,)))
    _write_ohlcv(tmp_path, "spot", "AAAUSDT", "1d", _daily_rows(10))
    _write_ohlcv(tmp_path, "futures", "LATEUSDT", "1d", _daily_rows(5, start_ms=T0 + 5 * DAY_MS))
    fdir = tmp_path / "funding"
    fdir.mkdir()
    ts = [T0 + i * 8 * 3_600_000 for i in range(9)]
    pd.DataFrame({"timestamp": ts, "funding_rate": [0.0001] * 9}).to_csv(fdir / "AAAUSDT.csv", index=False)
    pd.DataFrame({"timestamp": ts, "funding_rate": [0.0] * 9}).to_csv(fdir / "BNBUSDT.csv", index=False)
    return tmp_path


# ------------------------------------------------------------------ unit
def test_basic_frame_layout(root):
    df = load_ohlcv("AAAUSDT", "spot", "1d")
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "quote_volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    assert df.index[0] == pd.Timestamp(T0, unit="ms", tz="UTC")
    assert np.allclose(df["quote_volume"], df["volume"] * df["close"])
    assert df.attrs["source_commit"].startswith("4d33a56")
    assert len(df.attrs["sha256"]) == 64


def test_gap_is_nan_not_filled(root):
    df = load_ohlcv("AAAUSDT", "futures", "1d")
    assert len(df) == 10  # regular grid incl. the missing bar
    gap = pd.Timestamp(T0 + 4 * DAY_MS, unit="ms", tz="UTC")
    assert df.loc[gap].isna().all()
    assert df["close"].notna().sum() == 8


def test_zero_volume_masked(root):
    df = load_ohlcv("AAAUSDT", "futures", "1d")
    zero = pd.Timestamp(T0 + 6 * DAY_MS, unit="ms", tz="UTC")
    assert df.loc[zero].isna().all()
    # neighbours untouched: no forward fill
    nxt = pd.Timestamp(T0 + 7 * DAY_MS, unit="ms", tz="UTC")
    assert df.loc[nxt, "close"] == 108.0


def test_range_slicing_inclusive(root):
    start = pd.Timestamp(T0 + 2 * DAY_MS, unit="ms", tz="UTC")
    end = pd.Timestamp(T0 + 5 * DAY_MS, unit="ms", tz="UTC")
    df = load_ohlcv("AAAUSDT", "spot", "1d", str(start), str(end))
    assert df.index[0] == start and df.index[-1] == end and len(df) == 4


def test_missing_file_raises(root):
    with pytest.raises(DataError):
        load_ohlcv("ZZZUSDT", "spot", "1d")
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "4h")


def test_uncovered_range_raises(root):
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "1d", start="2020-01-01")
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "1d", end="2030-01-01")
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "1d", start="2020-09-20", end="2020-09-15")


def test_bad_arguments_raise(root):
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "margin", "1d")
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "1m")
    with pytest.raises(DataError):
        load_ohlcv("../etc/passwd", "spot", "1d")


def test_duplicates_raise(root):
    rows = _daily_rows(3)
    rows.append(rows[-1])
    _write_ohlcv(root, "spot", "DUPUSDT", "1d", rows)
    with pytest.raises(DataError, match="duplicated"):
        load_ohlcv("DUPUSDT", "spot", "1d")


def test_invalid_ohlc_raises(root):
    rows = _daily_rows(3)
    rows[1][2] = rows[1][4] - 5  # high below close
    _write_ohlcv(root, "spot", "BADUSDT", "1d", rows)
    with pytest.raises(DataError, match="invalid OHLC"):
        load_ohlcv("BADUSDT", "spot", "1d")


def test_non_positive_price_raises(root):
    rows = _daily_rows(3)
    rows[0][3] = 0.0
    _write_ohlcv(root, "spot", "ZEROUSDT", "1d", rows)
    with pytest.raises(DataError):
        load_ohlcv("ZEROUSDT", "spot", "1d")


def test_misaligned_timestamp_raises(root):
    rows = _daily_rows(3)
    rows[1][0] += 3_600_000
    _write_ohlcv(root, "spot", "MISUSDT", "1d", rows)
    with pytest.raises(DataError, match="aligned"):
        load_ohlcv("MISUSDT", "spot", "1d")


def test_empty_cell_raises(root):
    d = root / "spot"
    (d / "NANUSDT_1d.csv").write_text(
        f"timestamp,open,high,low,close,volume\n{T0},1,2,0.5,1.5,\n", encoding="utf-8"
    )
    with pytest.raises(DataError):
        load_ohlcv("NANUSDT", "spot", "1d")


def test_explicit_root_argument(root, tmp_path_factory, monkeypatch):
    other = tmp_path_factory.mktemp("other")
    monkeypatch.setenv("RESEARCH_DATA_ROOT", str(other))
    with pytest.raises(DataError):
        load_ohlcv("AAAUSDT", "spot", "1d")
    assert len(load_ohlcv("AAAUSDT", "spot", "1d", root=root)) == 10


def test_funding_fraction_and_index(root):
    f = load_funding("AAAUSDT")
    assert f.name == "funding_rate"
    assert f.index.name == "settlement_time"
    assert str(f.index.tz) == "UTC"
    assert (f == 0.0001).all()
    assert f.attrs["verified"] is False


def test_bnb_funding_excluded(root):
    with pytest.raises(DataError, match="excluded"):
        load_funding("BNBUSDT")
    assert len(load_funding("BNBUSDT", allow_bnb=True)) == 9


def test_funding_in_percent_rejected(root):
    pd.DataFrame({"timestamp": [T0], "funding_rate": [0.01 * 10]}).to_csv(
        root / "funding" / "PCTUSDT.csv", index=False
    )
    with pytest.raises(DataError, match="percent"):
        load_funding("PCTUSDT")


def test_funding_missing_file_and_range(root):
    with pytest.raises(DataError):
        load_funding("ZZZUSDT")
    with pytest.raises(DataError):
        load_funding("AAAUSDT", start="2019-01-01")
    with pytest.raises(DataError):
        load_funding("AAAUSDT", end="2030-01-01")


def test_panel_strict_and_late_start(root):
    start = str(pd.Timestamp(T0, unit="ms", tz="UTC"))
    end = str(pd.Timestamp(T0 + 9 * DAY_MS, unit="ms", tz="UTC"))
    with pytest.raises(DataError):
        load_panel(["AAAUSDT", "LATEUSDT"], "futures", "1d", start, end)
    panel = load_panel(["AAAUSDT", "LATEUSDT"], "futures", "1d", start, end, allow_late_start=True)
    assert panel["AAAUSDT"].index[0] == pd.Timestamp(T0, unit="ms", tz="UTC")
    assert panel["LATEUSDT"].index[0] == pd.Timestamp(T0 + 5 * DAY_MS, unit="ms", tz="UTC")
    m = manifest_from_frames(panel.values())
    assert set(m["files"]) == {"futures/AAAUSDT_1d.csv", "futures/LATEUSDT_1d.csv"}
    with pytest.raises(DataError):
        load_panel([], "futures", "1d")


def test_cache_does_not_leak_mutations(root):
    df = load_ohlcv("AAAUSDT", "spot", "1d")
    df.iloc[0, 0] = -1.0
    assert load_ohlcv("AAAUSDT", "spot", "1d").iloc[0, 0] == 100.0


def test_fng_loader(tmp_path):
    with pytest.raises(DataError):
        load_fng(tmp_path / "missing.csv")
    p = tmp_path / "fng.csv"
    p.write_text("date,fng_value,fng_classification\n02-01-2024,40,Fear\n01-01-2024,55,Greed\n", encoding="utf-8")
    s = load_fng(p)
    assert s.name == "fng"
    assert list(s.index.strftime("%Y-%m-%d")) == ["2024-01-01", "2024-01-02"]
    assert list(s) == [55.0, 40.0]
    p2 = tmp_path / "fng2.csv"
    p2.write_text("timestamp,value\n1704067200,10\n1704153600,120\n", encoding="utf-8")
    with pytest.raises(DataError):
        load_fng(p2)


# ------------------------------------------------------------ integration
REAL_ROOT = Path(os.environ.get("RESEARCH_DATA_ROOT_REAL", "/home/user/harness/data"))
real = pytest.mark.skipif(not (REAL_ROOT / "futures").is_dir(), reason="historical data not available")


@real
def test_real_btc_funding_median_is_fraction():
    f = load_funding("BTCUSDT", root=REAL_ROOT)
    assert 5e-5 < f.median() < 2e-4  # ~1e-4 = 0.01% per 8h
    assert f.index.is_monotonic_increasing


@real
def test_real_bnb_funding_excluded():
    with pytest.raises(DataError):
        load_funding("BNBUSDT", root=REAL_ROOT)


@real
def test_real_futures_zero_volume_masked():
    raw = pd.read_csv(REAL_ROOT / "futures" / "BTCUSDT_15m.csv")
    n_zero = int((raw["volume"] == 0).sum())
    assert n_zero > 0
    df = load_ohlcv("BTCUSDT", "futures", "15m", root=REAL_ROOT)
    assert int(df["close"].isna().sum()) == n_zero
    assert pd.isna(df.loc[pd.Timestamp("2021-03-02 01:15", tz="UTC"), "close"])
    assert (df["volume"].dropna() > 0).all()


@real
def test_real_spot_gaps_are_nan():
    df = load_ohlcv("BTCUSDT", "spot", "4h", root=REAL_ROOT)
    raw_rows = len(pd.read_csv(REAL_ROOT / "spot" / "BTCUSDT_4h.csv"))
    assert len(df) > raw_rows  # gaps were reindexed, not dropped
    diffs = df.index.to_series().diff().dropna()
    assert (diffs == pd.Timedelta(hours=4)).all()


@real
def test_real_range_errors_and_panel():
    with pytest.raises(DataError):
        load_ohlcv("SUIUSDT", "futures", "1d", start="2021-01-01", root=REAL_ROOT)
    with pytest.raises(DataError):
        load_ohlcv("BTCUSDT", "futures", "1d", end="2026-12-31", root=REAL_ROOT)
    with pytest.raises(DataError):
        load_ohlcv("TRXUSDT", "spot", "1d", root=REAL_ROOT)
    panel = load_panel(["BTCUSDT", "ETHUSDT"], "spot", "1d", "2018-01-01", "2020-08-31", root=REAL_ROOT)
    assert set(panel) == {"BTCUSDT", "ETHUSDT"}
    btc = panel["BTCUSDT"]
    assert btc.index[0] == pd.Timestamp("2018-01-01", tz="UTC")
    assert btc.index[-1] == pd.Timestamp("2020-08-31", tz="UTC")
    assert 29_000 < load_ohlcv("BTCUSDT", "spot", "1d", "2021-01-01", "2021-12-31", root=REAL_ROOT)["close"].max() < 70_000
