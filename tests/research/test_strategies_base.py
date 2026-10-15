"""Tests for apps.research.strategies.base (PLAN §4.2)."""
import dataclasses

import pandas as pd
import pytest

from apps.research.strategies.base import (
    Context,
    EventStrategy,
    OrderIntent,
    OrderIntentError,
    TargetWeightStrategy,
)


def test_order_intent_kinds():
    entry = OrderIntent("BTCUSDT", "BUY", stop_price=90.0, tag="brk")
    assert entry.is_entry and not entry.is_exit and not entry.is_order_update
    assert entry.direction == 1 and entry.order_type == "MARKET"
    exit_ = OrderIntent("BTCUSDT", "SELL", reduce_only=True)
    assert exit_.is_exit and exit_.direction == -1
    trail = OrderIntent("BTCUSDT", "SELL", reduce_only=True, stop_price=95.0)
    assert trail.is_order_update and not trail.is_exit
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.qty = 1.0  # type: ignore[misc]


@pytest.mark.parametrize("kwargs", [
    {"side": "LONG"},
    {"order_type": "STOP"},
    {"qty": 0.0},
    {"qty": float("nan")},
    {"target_weight": 1.5},
    {"qty": 1.0, "target_weight": 0.5},
    {"stop_price": -1.0},
    {"take_profit": float("inf")},
])
def test_order_intent_validation(kwargs):
    base = {"symbol": "BTCUSDT", "side": "BUY"}
    base.update(kwargs)
    with pytest.raises(OrderIntentError):
        OrderIntent(**base)


def test_context_history_is_truncated_at_t():
    idx = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    df = pd.DataFrame({"close": range(10)}, index=idx)
    ctx = Context(market="spot", frames={"BTCUSDT": df})
    assert len(ctx.history("BTCUSDT")) == 10
    ctx.t = idx[4]
    h = ctx.history("BTCUSDT")
    assert h.index[-1] == idx[4] and len(h) == 5
    assert ctx.history("BTCUSDT", n=2).index.tolist() == [idx[3], idx[4]]
    assert ctx.position("BTCUSDT") is None


def test_protocols_are_structural():
    class W:
        name = "w"
        params: dict = {}
        n_free_params = 0

        def signal(self, panel, ctx):
            return pd.DataFrame()

    class E:
        name = "e"
        params: dict = {}
        n_free_params = 0

        def on_bar(self, t, bars, ctx):
            return []

    assert isinstance(W(), TargetWeightStrategy)
    assert isinstance(E(), EventStrategy)
    assert not isinstance(E(), TargetWeightStrategy)
