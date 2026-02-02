import asyncio
from typing import Dict, Any
from apps.ingestion.connector import ExchangeConnector
from apps.executor.risk_manager import RiskManager
import logging

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, connector: ExchangeConnector, risk_manager: RiskManager):
        self.connector = connector
        self.risk_manager = risk_manager

    async def execute_signal(self, signal: Dict[str, Any]):
        """
        Receives a signal from Brain, validates with RiskManager, and executes order.
        Signal format: {'symbol': 'BTC/USDT', 'side': 'buy', 'price': 50000, 'type': 'limit'}
        """
        symbol = signal.get('symbol')
        side = signal.get('side') # 'buy' or 'sell'
        price = signal.get('price')
        
        # 1. Check Balance
        balance = await self.connector.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        # 2. Calculate Size (Risk Management)
        position_size = self.risk_manager.calculate_kelly_size(usdt_balance)
        
        if position_size <= 0:
            logger.warning("Risk Manager denied trade execution (Size 0).")
            return

        logger.info(f"Executing {side.upper()} order for {symbol} | Size: {position_size} USDT | Price: {price}")

        # 3. Place Order (Stub for now)
        try:
            # order = await self.connector.exchange.create_order(symbol, 'limit', side, amount, price)
            logger.info("Order placed successfully (STUB).")
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
