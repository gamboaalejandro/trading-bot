"""
Testnet Connector - Binance Futures Testnet Interface
Provides safe testing environment for trading strategies.

NOTE: Binance Futures Testnet is no longer officially supported by CCXT,
so we use manual URL configuration to connect to testnet.binancefuture.com
"""
import ccxt.pro as ccxt
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.config import settings
from ccxt.base.errors import RequestTimeout, NetworkError

logger = logging.getLogger(__name__)

# Configuración para reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos


class TestnetConnector:
    """
    Connector for Binance Futures Testnet.
    
    Provides:
    - Account balance tracking
    - Position management
    - Order execution (market, limit)
    - Historical data fetching
    - P&L calculation
    """
    
    def __init__(self, use_testnet: bool = True):
        """
        Initialize testnet connector.
        
        Args:
            use_testnet: If True, use testnet. If False, use production (DANGEROUS!)
        """
        self.use_testnet = use_testnet
        
        if use_testnet:
            api_key = getattr(settings, 'BINANCE_TESTNET_API_KEY', settings.BINANCE_API_KEY)
            secret = getattr(settings, 'BINANCE_TESTNET_SECRET', settings.BINANCE_SECRET)
            logger.info("🧪 Initializing TESTNET connector")
        else:
            api_key = settings.BINANCE_API_KEY
            secret = settings.BINANCE_SECRET
            logger.warning("⚠️ Initializing PRODUCTION connector - REAL MONEY AT RISK!")
        
        # Configure options
        options = {
            'defaultType': 'future',  # Crucial: specify futures
        }
        
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': options,
            'timeout': 30000,  # 30 segundos (el testnet es lento)
            'rateLimit': 500,  # ms entre requests
        })
        self.exchange.enable_demo_trading(True)

        
        
        if use_testnet:
            # CCXT ya tiene las URLs de testnet en urls['test']
            # Solo necesitamos copiar las URLs de test a api para que las use
            
            # Copiar todas las URLs de futures testnet de 'test' a 'api'
            if 'test' in self.exchange.urls and 'api' in self.exchange.urls:
                test_urls = self.exchange.urls['test']
                
                # Sobrescribir las URLs de futures en 'api' con las de 'test'
                for key in ['fapiPublic', 'fapiPrivate', 'fapiPublicV2', 'fapiPrivateV2', 'fapiPublicV3', 'fapiPrivateV3']:
                    if key in test_urls:
                        self.exchange.urls['api'][key] = test_urls[key]
                
                logger.debug(f"Configured testnet futures endpoints from urls['test']")
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize connection and test it."""
        if self._initialized:
            return
        
        try:
            logger.info("Testing connection...")
            
            # Test connection by fetching balance
            balance = await self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            logger.info(f"✓ Connected successfully. USDT Balance: {usdt_balance:.2f}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to connect to exchange: {e}")
            raise
    
    async def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance.
        
        Returns:
            Dict with balance information
        """
        if not self._initialized:
            await self.initialize()
        
        balance = await self.exchange.fetch_balance()
        return balance
    
    async def get_usdt_balance(self) -> float:
        """Get available USDT balance."""
        balance = await self.get_balance()
        return balance.get('USDT', {}).get('free', 0.0)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get open positions.
        
        Args:
            symbol: Filter by symbol (e.g., 'BTC/USDT'). If None, get all positions.
            
        Returns:
            List of position dictionaries
        """
        if not self._initialized:
            await self.initialize()
        
        positions = await self.exchange.fetch_positions(symbols=[symbol] if symbol else None)
        
        # Filter out zero positions
        open_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
        
        return open_positions
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get specific position for symbol.
        
        Returns:
            Position dict or None if no position
        """
        positions = await self.get_positions(symbol)
        return positions[0] if positions else None
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Create market order with retry logic.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity in base currency
            reduce_only: If True, only reduce existing position
            
        Returns:
            Order information
        """
        if not self._initialized:
            await self.initialize()
        
        params = {}
        if reduce_only:
            params['reduceOnly'] = True
        
        logger.info(f"Creating MARKET {side.upper()} order: {amount} {symbol}")
        
        # Retry logic para manejar timeouts del testnet
        for attempt in range(MAX_RETRIES):
            try:
                order = await self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=amount,
                    params=params
                )
                
                logger.info(f"✓ Order created: {order.get('id')} | Status: {order.get('status')}")
                return order
                
            except (RequestTimeout, NetworkError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** attempt)  # Backoff exponencial
                    logger.warning(
                        f"⚠️ Timeout/Network error (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed after {MAX_RETRIES} attempts")
                    raise
            except Exception as e:
                # Otros errores no se reintenta
                logger.error(f"❌ Order creation failed: {e}")
                raise
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Create limit order.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Quantity
            price: Limit price
            reduce_only: If True, only reduce existing position
            
        Returns:
            Order information
        """
        if not self._initialized:
            await self.initialize()
        
        params = {}
        if reduce_only:
            params['reduceOnly'] = True
        
        logger.info(
            f"Creating LIMIT {side.upper()} order: "
            f"{amount} {symbol} @ ${price:.2f}"
        )
        
        order = await self.exchange.create_order(
            symbol=symbol,
            type='limit',
            side=side,
            amount=amount,
            price=price,
            params=params
        )
        
        logger.info(f"✓ Order created: {order.get('id')} | Status: {order.get('status')}")
        
        return order
    
    async def create_stop_loss(
        self,
        symbol: str,
        side: str,
        amount: float,
        stop_price: float
    ) -> Dict[str, Any]:
        """
        Create stop loss order.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell' (opposite of position side)
            amount: Quantity
            stop_price: Stop trigger price
            
        Returns:
            Order information
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info(
            f"Creating STOP LOSS {side.upper()} order: "
            f"{amount} {symbol} @ ${stop_price:.2f}"
        )
        
        order = await self.exchange.create_order(
            symbol=symbol,
            type='stop_market',
            side=side,
            amount=amount,
            params={
                'stopPrice': stop_price,
                'reduceOnly': True
            }
        )
        
        logger.info(f"✓ Stop loss created: {order.get('id')}")
        
        return order
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order."""
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Cancelling order {order_id} for {symbol}")
        result = await self.exchange.cancel_order(order_id, symbol)
        logger.info(f"✓ Order cancelled: {order_id}")
        
        return result
    
    async def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Cancel all open orders for a symbol."""
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Cancelling all orders for {symbol}")
        result = await self.exchange.cancel_all_orders(symbol)
        logger.info(f"✓ Cancelled {len(result)} orders")
        
        return result
    
    async def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Close an open position with market order.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Order information or None if no position
        """
        position = await self.get_position(symbol)
        
        if not position:
            logger.info(f"No open position for {symbol}")
            return None
        
        contracts = float(position.get('contracts', 0))
        side_str = position.get('side', 'long')
        
        if contracts == 0:
            logger.info(f"Position size is 0 for {symbol}")
            return None
        
        # Determine closing side (opposite of position side)
        close_side = 'sell' if side_str == 'long' else 'buy'
        
        logger.info(f"Closing {side_str.upper()} position: {contracts} {symbol}")
        
        order = await self.create_market_order(
            symbol=symbol,
            side=close_side,
            amount=abs(contracts),
            reduce_only=True
        )
        
        return order
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1m',
        limit: int = 100
    ) -> List[List]:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, etc.)
            limit: Number of candles to fetch
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        if not self._initialized:
            await self.initialize()
        
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        
        return ohlcv
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker information."""
        if not self._initialized:
            await self.initialize()
        
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
        logger.info("Exchange connection closed")


# Convenience function for quick testing
async def test_connection():
    """Test testnet connection."""
    connector = TestnetConnector(use_testnet=True)
    
    try:
        await connector.initialize()
        
        # Get balance
        balance = await connector.get_usdt_balance()
        print(f"✓ USDT Balance: {balance:.2f}")
        
        # Get ticker
        ticker = await connector.get_ticker('BTC/USDT')
        print(f"✓ BTC/USDT Price: ${ticker.get('last', 0):.2f}")
        
        # Get positions
        positions = await connector.get_positions()
        print(f"✓ Open positions: {len(positions)}")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
