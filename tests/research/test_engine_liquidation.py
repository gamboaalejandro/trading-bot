"""Tests for apps.research.engine.liquidation (PLAN §6.2 R05)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.liquidation import (
    LiquidationError,
    liq_distance,
    liq_ok,
    liq_price,
    max_safe_leverage,
    worst_wick,
)

DATA_ROOT = Path("/home/user/harness/data")


# --------------------------------------------------------------------------- liq_price
def test_liq_price_isolated_formula():
    assert liq_price(100.0, 2, +1, 0.01) == pytest.approx(100 * 0.5 / 0.99)
    assert liq_price(100.0, 2, -1, 0.01) == pytest.approx(100 * 1.5 / 1.01)


def test_liq_l2_is_about_minus_50pct():
    dist = liq_price(100.0, 2, +1) / 100.0 - 1.0
    assert dist == pytest.approx(-0.495, abs=1e-3)
    assert -0.51 < dist < -0.48


def test_liq_l1_long_never_liquidates_short_needs_about_double():
    assert liq_price(100.0, 1, +1) == 0.0
    assert liq_distance(100.0, 1, +1) == 1.0
    assert liq_price(100.0, 1, -1) / 100.0 - 1 == pytest.approx(2 / 1.01 - 1)


def test_liq_monotone_in_leverage():
    d = [liq_distance(100.0, lev, +1) for lev in (1, 1.5, 2, 3, 5, 10)]
    assert all(a > b for a, b in zip(d, d[1:]))


def test_liq_price_invalid():
    with pytest.raises(LiquidationError):
        liq_price(100.0, 0, +1)
    with pytest.raises(LiquidationError):
        liq_price(100.0, 2, 0)
    with pytest.raises(LiquidationError):
        liq_price(-1.0, 2, 1)


# --------------------------------------------------------------------------- worst_wick
@pytest.fixture
def ohlc():
    idx = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 130.0, 102.0, 104.0, 101.0],
            "low": [99.0, 98.0, 60.0, 97.0, 95.0],
            "close": [100.0, 100.0, 100.0, 100.0, 100.0],
        },
        index=idx,
    )


def test_worst_wick_expanding_values(ohlc):
    ww_long = worst_wick(ohlc, +1)
    assert ww_long.tolist() == pytest.approx([0.01, 0.02, 0.40, 0.40, 0.40])
    ww_short = worst_wick(ohlc, -1)
    assert ww_short.tolist() == pytest.approx([0.01, 0.30, 0.30, 0.30, 0.30])


def test_worst_wick_uses_prev_close_on_gaps():
    idx = pd.date_range("2024-01-01", periods=2, freq="1D", tz="UTC")
    df = pd.DataFrame({"open": [100.0, 80.0], "high": [100.0, 82.0],
                       "low": [100.0, 78.0], "close": [100.0, 80.0]}, index=idx)
    # Gap down from 100 to an 80 open, low 78: adverse move vs previous close is 22 %.
    assert worst_wick(df, +1).iloc[-1] == pytest.approx(0.22)


def test_worst_wick_is_causal(ohlc):
    full = worst_wick(ohlc, +1)
    for k in range(1, len(ohlc) + 1):
        trunc = worst_wick(ohlc.iloc[:k], +1)
        assert trunc.iloc[-1] == pytest.approx(full.iloc[k - 1])
    # The day-3 crash is not visible before day 3.
    assert full.iloc[1] < 0.40


def test_worst_wick_skips_nan_bars(ohlc):
    df = ohlc.copy()
    df.iloc[3] = np.nan
    ww = worst_wick(df, +1)
    assert ww.iloc[3] == pytest.approx(0.40)
    assert np.isfinite(ww).all()


# --------------------------------------------------------------------------- liq_ok
def test_liq_ok_stop_rule():
    # L=2: liquidation ~49.5 % away. Stop 10 % away -> needs 30 %: ok.
    assert liq_ok(100.0, 90.0, 2, +1, 0.05, 0.01)
    # Stop 20 % away -> needs 60 %: not ok.
    assert not liq_ok(100.0, 80.0, 2, +1, 0.05, 0.01)


def test_liq_ok_worst_wick_rule(ohlc):
    ww = worst_wick(ohlc, +1)
    # Before the 40 % wick L=3 passes (33 % >= max(15 %, 2 %)); once the wick is
    # known it fails, while L=2 (49.5 %) and L=1 still pass.
    assert liq_ok(100.0, 95.0, 3, +1, ww.iloc[1], 0.01)
    assert liq_ok(100.0, 95.0, 2, +1, ww.iloc[2], 0.01)          # 49.5 % >= 40 %
    assert not liq_ok(100.0, 95.0, 3, +1, ww.iloc[2], 0.01)      # 33 % < 40 %
    assert liq_ok(100.0, 95.0, 1, +1, ww.iloc[2], 0.01)


def test_liq_ok_short_and_errors():
    assert liq_ok(100.0, 110.0, 1, -1, 0.5, 0.01)
    assert not liq_ok(100.0, 110.0, 2, -1, 0.6, 0.01)
    with pytest.raises(LiquidationError):
        liq_ok(100.0, 110.0, 1, +1, 0.1, 0.01)   # stop above entry for a long
    assert not liq_ok(100.0, 90.0, 1, +1, float("nan"), 0.01)


def test_max_safe_leverage_boundary():
    lev = max_safe_leverage(100.0, 95.0, +1, 0.40, 0.01, lev_cap=10.0)
    assert liq_ok(100.0, 95.0, lev, +1, 0.40, 0.01)
    assert not liq_ok(100.0, 95.0, lev * 1.001, +1, 0.40, 0.01)
    assert max_safe_leverage(100.0, 95.0, +1, 0.40, 0.01, lev_cap=1.0) == 1.0
    assert max_safe_leverage(100.0, 95.0, +1, float("nan")) == 0.0


# --------------------------------------------------------------------------- real data
@pytest.mark.skipif(not (DATA_ROOT / "futures" / "SUIUSDT_1d.csv").exists(), reason="harness data not present")
def test_real_sui_wick_2025_10_10_blocks_2x():
    raw = pd.read_csv(DATA_ROOT / "futures" / "SUIUSDT_1d.csv")
    df = raw.set_index(pd.to_datetime(raw["timestamp"], unit="ms", utc=True))
    df = df[["open", "high", "low", "close", "volume"]]
    df = df[df["volume"] > 0]
    ww = worst_wick(df, +1)
    before = ww.loc[:"2025-10-09"].iloc[-1]
    after = ww.loc["2025-10-10"]
    assert after > before          # the crash is only known from its own close on
    assert after > 0.5             # PLAN §1.1: SUI wick ~ -79/-83 %
    entry = float(df.loc["2025-10-11", "open"])
    assert not liq_ok(entry, entry * 0.9, 2, +1, after, 0.01)
    assert liq_ok(entry, entry * 0.9, 1, +1, after, 0.01)
