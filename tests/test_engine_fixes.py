"""Regression tests for the audit fixes (no network access)."""
import asyncio

import numpy as np
import pandas as pd
import pytest

import apps.executor.multi_symbol_engine as engine_mod
from apps.executor.strategies.base_strategy import Signal, SignalType
from apps.executor.strategies.momentum_strategy import MomentumStrategy
from core.binance_client import BinanceClient


class FakeConnector:
    """Minimal spot exchange: fills at the current price, fee in base asset."""

    def __init__(self, price=100.0, usdt=1000.0):
        self.price = price
        self.usdt = usdt
        self.base = 0.0
        self.orders = []

    async def get_ticker(self, symbol):
        return {"last": self.price}

    async def get_balance(self):
        return {"USDT": {"free": self.usdt}, "SOL": {"free": self.base}}

    async def place_order(self, symbol, side, quantity, price, order_type):
        self.orders.append((side, quantity))
        fills = []
        if side == "buy":
            self.base += quantity * 0.999
            self.usdt -= quantity * self.price
            fills = [{"commission": str(quantity * 0.001), "commissionAsset": "SOL"}]
        else:
            self.base -= quantity
            self.usdt += quantity * self.price
        return {
            "orderId": len(self.orders),
            "status": "FILLED",
            "executedQty": str(quantity),
            "cummulativeQuoteQty": str(quantity * self.price),
            "fills": fills,
        }

    async def create_stop_loss(self, symbol, side, quantity, stop_price):
        self.orders.append(("stop", quantity, stop_price))
        return {"orderId": 99}

    async def cancel_order(self, order_id, symbol):
        self.orders.append(("cancel", order_id))


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_mod, "STATE_FILE", str(tmp_path / "positions.json"))
    monkeypatch.setattr(
        "apps.ingestion.sentiment.SentimentAnalyzer.get_sentiment_multiplier", lambda self: 1.0
    )
    eng = engine_mod.MultiSymbolEngine(symbols=["SOL/USDT"], dry_run=False)
    eng.connector = FakeConnector()
    closes = np.linspace(90, 100, 300)
    eng.latest_candles["SOL/USDT"] = pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.5, "close": closes, "volume": 1.0}
    )
    return eng


def test_timeframe_to_seconds():
    assert engine_mod.timeframe_to_seconds("1m") == 60
    assert engine_mod.timeframe_to_seconds("4h") == 14400


def test_fill_summary_nets_base_commission():
    order = {
        "executedQty": "0.0100",
        "cummulativeQuoteQty": "600.0",
        "fills": [{"commission": "0.00001", "commissionAsset": "BTC"}],
    }
    qty, avg, quote_fee = engine_mod.fill_summary(order, "BTC")
    assert qty == pytest.approx(0.00999)
    assert avg == pytest.approx(60000.0)
    assert quote_fee == 0.0


def test_round_quantity_rounds_down():
    client = BinanceClient("k", "s")
    client.get_exchange_info = lambda s: {
        "symbols": [{"filters": [{"filterType": "LOT_SIZE", "stepSize": "0.00001000"}]}]
    }
    assert client.round_quantity("BTCUSDT", 0.0099999) == pytest.approx(0.00999)


def test_sell_signal_without_position_is_ignored(engine):
    signal = Signal(SignalType.SELL, 0.9, 100.0)

    async def run():
        engine.strategies["SOL/USDT"].get_combined_signal = _const(signal)
        await engine._check_signal("SOL/USDT")

    asyncio.run(run())
    assert engine.connector.orders == []
    assert engine.open_positions == {}


def test_buy_places_exchange_stop_and_tracks_net_quantity(engine):
    asyncio.run(engine._execute_trade("SOL/USDT", Signal(SignalType.BUY, 0.9, 100.0)))
    position = engine.open_positions["SOL/USDT"]
    bought = engine.connector.orders[0][1]
    assert position["quantity"] == pytest.approx(bought * 0.999)
    assert position["stop_order_id"] == 99
    assert engine.connector.orders[1][0] == "stop"
    # notional never exceeds free USDT
    assert bought * 100.0 <= 1000.0


def test_close_cancels_stop_and_records_daily_pnl(engine):
    asyncio.run(engine._execute_trade("SOL/USDT", Signal(SignalType.BUY, 0.9, 100.0)))
    engine.connector.price = 103.0
    asyncio.run(engine.close_position("SOL/USDT", "take_profit", 103.0))
    assert ("cancel", "99") in engine.connector.orders
    assert engine.connector.orders[-1][0] == "sell"
    assert engine.open_positions == {}
    assert engine.daily_realized_pnl > 0
    assert engine.risk_manager.current_daily_loss == engine.daily_realized_pnl


def test_positions_persist_across_restarts(engine, monkeypatch):
    asyncio.run(engine._execute_trade("SOL/USDT", Signal(SignalType.BUY, 0.9, 100.0)))
    restarted = engine_mod.MultiSymbolEngine(symbols=["SOL/USDT"], dry_run=False)
    assert restarted.open_positions["SOL/USDT"]["entry_price"] == pytest.approx(100.0)


def test_max_positions_enforced(engine):
    engine.open_positions["BTC/USDT"] = {"side": "buy", "entry_price": 1, "timestamp": "x"}
    engine.profile.max_positions = 1
    asyncio.run(engine._execute_trade("SOL/USDT", Signal(SignalType.BUY, 0.9, 100.0)))
    assert engine.connector.orders == []


def test_momentum_crossover_is_stateless():
    closes = np.r_[np.linspace(100, 90, 60), np.linspace(90, 110, 40)]
    df = pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1, "close": closes, "volume": 1.0})
    # Evaluating only the crossover candle (no prior calls) must still detect it
    buys = []
    for i in range(30, 101):
        fresh = MomentumStrategy(fast_ma_period=5, slow_ma_period=20)
        sig = asyncio.run(fresh.analyze(df.iloc[:i].copy()))
        if sig and sig.signal_type == SignalType.BUY:
            buys.append(i)
    assert len(buys) == 1


def _const(value):
    async def f(*args, **kwargs):
        return value
    return f
