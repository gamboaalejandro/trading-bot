"""Tests for apps.research.engine.costs (PLAN §6.2 R02)."""
import math

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import (
    CostError,
    CostModel,
    commission,
    funding_cashflow,
    liquidity_tier,
    slipped_price,
    slippage_bps,
)


# --------------------------------------------------------------------------- commission
def test_commission_exact_spot_and_futures():
    cm = CostModel()
    assert commission(10_000.0, "spot", cm) == pytest.approx(10.0, abs=1e-12)
    assert commission(-10_000.0, "spot", cm) == pytest.approx(10.0, abs=1e-12)
    assert commission(10_000.0, "futures", cm) == pytest.approx(5.0, abs=1e-12)
    assert commission(10_000.0, "futures", cm, maker=True) == pytest.approx(2.0, abs=1e-12)


def test_commission_round_trip_spot_is_20bp():
    cm = CostModel()
    assert commission(1_000.0, "spot", cm) * 2 / 1_000.0 == pytest.approx(0.0020)


def test_cost_mult_doubles_commission_and_slippage():
    cm2 = CostModel().stressed(cost_mult=2.0)
    assert commission(10_000.0, "spot", cm2) == pytest.approx(20.0)
    assert slippage_bps("BTCUSDT", None, 1e9, 0.02, 0.02, cm2) == pytest.approx(4.0)
    assert cm2.funding_mult == 1.0


def test_unknown_market_raises():
    with pytest.raises(CostError):
        CostModel().fee_rate("margin")


# --------------------------------------------------------------------------- slippage
@pytest.mark.parametrize(
    "qv, tier",
    [(2e9, "A"), (500e6 + 1, "A"), (500e6, "B"), (50e6, "B"), (49.9e6, "C"), (5e6, "C"), (4.99e6, None)],
)
def test_liquidity_tiers(qv, tier):
    assert liquidity_tier(qv) == tier


def test_slippage_by_tier_without_vol_scaling():
    cm = CostModel()
    assert slippage_bps("BTCUSDT", None, 1e9, 0.03, 0.03, cm) == 2.0
    assert slippage_bps("SOLUSDT", None, 1e8, 0.03, 0.03, cm) == 5.0
    assert slippage_bps("APTUSDT", None, 1e7, 0.03, 0.03, cm) == 15.0


def test_slippage_scales_with_atr_ratio_but_never_below_base():
    cm = CostModel()
    # ATR% twice its 90d median -> twice the base.
    assert slippage_bps("SOLUSDT", None, 1e8, 0.06, 0.03, cm) == pytest.approx(10.0)
    # Calm market: multiplier is floored at 1.
    assert slippage_bps("SOLUSDT", None, 1e8, 0.01, 0.03, cm) == pytest.approx(5.0)


def test_slippage_excluded_tier_and_missing_inputs_raise():
    cm = CostModel()
    with pytest.raises(CostError, match="excluded"):
        slippage_bps("XUSDT", "2024-01-01", 1e6, 0.03, 0.03, cm)
    with pytest.raises(CostError):
        slippage_bps("BTCUSDT", None, 1e9, float("nan"), 0.03, cm)
    with pytest.raises(CostError):
        slippage_bps("BTCUSDT", None, float("nan"), 0.03, 0.03, cm)


def test_slipped_price_direction():
    assert slipped_price(100.0, +1, 10) == pytest.approx(100.1)
    assert slipped_price(100.0, -1, 10) == pytest.approx(99.9)


# --------------------------------------------------------------------------- funding
def _ts(s):
    return pd.Timestamp(s, tz="UTC")


def test_funding_sign_long_pays_short_receives_when_positive():
    settle = pd.DatetimeIndex([_ts("2024-01-01 08:00")])
    funding = pd.Series([0.0001], index=settle)
    idx = pd.DatetimeIndex([_ts("2024-01-01 00:00")])
    notional = pd.Series([10_000.0], index=idx)

    long_cf = funding_cashflow(notional, funding, pd.Series([1], index=idx), 1.0)
    short_cf = funding_cashflow(notional, funding, pd.Series([-1], index=idx), 1.0)
    assert long_cf.iloc[0] == pytest.approx(-1.0)   # long pays 0.01 % of 10k
    assert short_cf.iloc[0] == pytest.approx(1.0)   # short receives

    neg = funding_cashflow(notional, -funding, pd.Series([1], index=idx), 1.0)
    assert neg.iloc[0] == pytest.approx(1.0)        # long receives when F < 0


def test_funding_uses_position_just_before_settlement():
    # Position changes exactly at the 00:00 settlement (daily rebalance).
    pos_idx = pd.DatetimeIndex([_ts("2024-01-01 00:00"), _ts("2024-01-02 00:00")])
    notional = pd.Series([10_000.0, 30_000.0], index=pos_idx)
    side = pd.Series([1, 1], index=pos_idx)
    settle = pd.date_range(_ts("2024-01-01 00:00"), periods=5, freq="8h")
    funding = pd.Series(0.0001, index=settle)

    cf = funding_cashflow(notional, funding, side, 1.0)
    # 2024-01-01 00:00: no position before it -> 0.
    assert cf.iloc[0] == 0.0
    # 08:00 and 16:00 on day 1 use 10k.
    assert cf.iloc[1] == pytest.approx(-1.0)
    assert cf.iloc[2] == pytest.approx(-1.0)
    # 2024-01-02 00:00: tau- is still the 10k position, not the new 30k one.
    assert cf.iloc[3] == pytest.approx(-1.0)
    # 08:00 on day 2 uses 30k.
    assert cf.iloc[4] == pytest.approx(-3.0)


def test_funding_closed_position_and_mult():
    pos_idx = pd.DatetimeIndex([_ts("2024-01-01 00:00"), _ts("2024-01-01 12:00")])
    notional = pd.Series([10_000.0, 0.0], index=pos_idx)
    side = pd.Series([-1, 0], index=pos_idx)
    settle = pd.DatetimeIndex([_ts("2024-01-01 08:00"), _ts("2024-01-01 16:00")])
    funding = pd.Series([0.0003, 0.0003], index=settle)
    cf = funding_cashflow(notional, funding, side, 2.0)
    assert cf.iloc[0] == pytest.approx(6.0)  # short receives 3bp * 10k * 2
    assert cf.iloc[1] == 0.0                 # flat after 12:00


def test_funding_missing_rate_with_open_position_raises():
    pos_idx = pd.DatetimeIndex([_ts("2024-01-01 00:00")])
    settle = pd.DatetimeIndex([_ts("2024-01-01 08:00")])
    with pytest.raises(CostError, match="missing funding"):
        funding_cashflow(pd.Series([1.0], index=pos_idx), pd.Series([np.nan], index=settle),
                         pd.Series([1], index=pos_idx), 1.0)


def test_funding_missing_rate_while_flat_is_zero():
    pos_idx = pd.DatetimeIndex([_ts("2024-01-01 00:00")])
    settle = pd.DatetimeIndex([_ts("2024-01-01 08:00")])
    cf = funding_cashflow(pd.Series([0.0], index=pos_idx), pd.Series([np.nan], index=settle),
                          pd.Series([0], index=pos_idx), 1.0)
    assert cf.iloc[0] == 0.0 and not math.copysign(1, cf.iloc[0]) < 0
