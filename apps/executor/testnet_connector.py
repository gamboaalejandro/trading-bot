"""
Testnet Connector - Binance Demo Mode Interface
NOW USING NATIVE BINANCE API (NO CCXT)

Provides safe testing environment for trading strategies.

NOTE: Uses Binance Demo Mode (demo-api.binance.com) which provides
realistic market data with virtual funds.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# CHANGED: Import native Binance client instead of ccxt
from core.binance_client import BinanceClient
from core.config import settings

logger = logging.getLogger(__name__)


class TestnetConnector:
    """
    Connector for Binance Demo Mode using Native API.
    
    Provides:
    - Account balance tracking
    - Position management (spot trading)
    - Order execution (market, limit)
    - Historical data fetching
    - P&L calculation
    """
    
    def __init__(self, use_testnet: bool = True):
        """
        Initialize Demo Mode connector.
        
        Args:
            use_testnet: If True, use Demo Mode. If False, use production (DANGEROUS!)
        """
        self.use_testnet = use_testnet
        
        if use_testnet:
            api_key = getattr(settings, 'BINANCE_TESTNET_API_KEY', settings.BINANCE_TESTNET_API_KEY)
            secret = getattr(settings, 'BINANCE_TESTNET_SECRET', settings.BINANCE_TESTNET_SECRET)
            logger.info("Initializing SPOT DEMO MODE connector")
        else:
            api_key = settings.BINANCE_API_KEY
            secret = settings.BINANCE_SECRET
            logger.warning("Initializing PRODUCTION connector - REAL MONEY AT RISK!")
        
        logger.info(f"Using API Key: {api_key[:10]}...")  # Only show first 10 chars for security
        
        # CHANGED: Use native Binance client
        self.client = BinanceClient(
            api_key=api_key,
            api_secret=secret,
            demo_mode=use_testnet,
            timeout=30
        )
        
        self._initialized = False
        
        if use_testnet:
            logger.info(" Spot Demo Mode configured: demo-api.binance.com")
            logger.info(" Using REAL market prices with virtual funds")
            logger.info(" Strategy: Swing trading with wide TP/SL (3:1 R/R)")
        else:
            logger.warning(" LIVE TRADING MODE - Using real funds")
    
    async def initialize(self):
        """Initialize connection and test it."""
        if self._initialized:
            return
        
        try:
            logger.info("Testing connection...")
            
            # Sync time with server
            self.client.sync_time()
            
            # Test connection by fetching balance
            usdt_balance = self.client.get_balance('USDT')
            logger.info(f"[OK] Connected successfully. USDT Balance: {usdt_balance:.2f}")
            
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
        
        # CHANGED: Use native client
        account = self.client.get_account()
        
        # Convert to ccxt-like format for compatibility
        balances = {}
        for balance in account.get('balances', []):
            asset = balance['asset']
            balances[asset] = {
                'free': float(balance['free']),
                'used': float(balance['locked']),
                'total': float(balance['free']) + float(balance['locked'])
            }
        
        return balances
    
    async def get_usdt_balance(self) -> float:
        """Get available USDT balance."""
        if not self._initialized:
            await self.initialize()
        
        # CHANGED: Use native client
        return self.client.get_balance('USDT')
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get open positions.
        
        NOTE: For SPOT trading, this returns open orders instead of positions.
        Futures positions don't exist in spot mode.
        
        Args:
            symbol: Filter by symbol (e.g., 'BTC/USDT'). If None, get all.
            
        Returns:
            List of open orders
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '') if symbol else None
        
        # CHANGED: Use native client
        open_orders = self.client.get_open_orders(binance_symbol)
        
        return open_orders
    
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
        Create market order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity in base currency
            reduce_only: Ignored for spot trading
            
        Returns:
            Order information
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        # Round quantity to proper precision to avoid "too much precision" errors
        rounded_amount = self.client.round_quantity(binance_symbol, amount)
        
        logger.info(f"Creating MARKET {side.upper()} order: {rounded_amount} {symbol}")
        
        # CHANGED: Use native client
        order = self.client.create_order(
            symbol=binance_symbol,
            side=side.upper(),
            order_type='MARKET',
            quantity=rounded_amount
        )
        
        logger.info(f"[OK] Order created: {order.get('orderId')} | Status: {order.get('status')}")
        return order
    
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
            reduce_only: Ignored for spot trading
            
        Returns:
            Order information
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        logger.info(
            f"Creating LIMIT {side.upper()} order: "
            f"{amount} {symbol} @ ${price:.2f}"
        )
        
        # CHANGED: Use native client
        order = self.client.create_order(
            symbol=binance_symbol,
            side=side.upper(),
            order_type='LIMIT',
            quantity=amount,
            price=price,
            time_in_force='GTC'
        )
        
        logger.info(f"[OK] Order created: {order.get('orderId')} | Status: {order.get('status')}")
        
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
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        logger.info(
            f"Creating STOP LOSS {side.upper()} order: "
            f"{amount} {symbol} @ ${stop_price:.2f}"
        )
        
        # CHANGED: Use native client  
        order = self.client.create_order(
            symbol=binance_symbol,
            side=side.upper(),
            order_type='STOP_LOSS',
            quantity=amount,
            stop_price=stop_price
        )
        
        logger.info(f"[OK] Stop loss created: {order.get('orderId')}")
        
        return order
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order."""
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        logger.info(f"Cancelling order {order_id} for {symbol}")
        
        # CHANGED: Use native client
        result = self.client.cancel_order(binance_symbol, int(order_id))
        logger.info(f"[OK] Order cancelled: {order_id}")
        
        return result
    
    async def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Cancel all open orders for a symbol."""
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        logger.info(f"Cancelling all orders for {symbol}")
        
        # CHANGED: Use native client
        result = self.client.cancel_all_orders(binance_symbol)
        logger.info(f"[OK] Cancelled {len(result)} orders")
        
        return result
    
    async def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Close an open position with market order.
        
        NOTE: For SPOT trading, this cancels all open orders.
        True positions don't exist in spot mode.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Cancellation result or None
        """
        logger.info(f"Closing position (cancelling orders) for {symbol}")
        
        result = await self.cancel_all_orders(symbol)
        return result if result else None
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1m',
        limit: int = 100
    ) -> List[List]:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, etc.)
            limit: Number of candles to fetch
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        # CHANGED: Use native client
        klines = self.client.get_klines(
            symbol=binance_symbol,
            interval=timeframe,
            limit=limit
        )
        
        # Binance klines format: [time, open, high, low, close, volume, close_time, ...]
        # We only need first 6 values to match ccxt format
        return [[k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] 
                for k in klines]
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = None,
        order_type: str = 'market'
    ) -> Dict[str, Any]:
        """
        Unified order placement method (wrapper for compatibility).
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            quantity: Amount to trade
            price: Limit price (ignored for market orders)
            order_type: 'market' or 'limit'
            
        Returns:
            Order information
        """
        if order_type.lower() == 'market':
            return await self.create_market_order(symbol, side, quantity)
        elif order_type.lower() == 'limit' and price:
            return await self.create_limit_order(symbol, side, quantity, price)
        else:
            raise ValueError(f"Invalid order_type: {order_type}")
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker information."""
        if not self._initialized:
            await self.initialize()
        
        # Convert 'BTC/USDT' to 'BTCUSDT'
        binance_symbol = symbol.replace('/', '')
        
        # CHANGED: Use native client
        ticker = self.client.get_ticker_24hr(binance_symbol)
        
        # Convert to ccxt-like format
        return {
            'symbol': symbol,
            'last': float(ticker['lastPrice']),
            'bid': float(ticker.get('bidPrice', 0)),
            'ask': float(ticker.get('askPrice', 0)),
            'high': float(ticker['highPrice']),
            'low': float(ticker['lowPrice']),
            'volume': float(ticker['volume']),
            'timestamp': ticker['closeTime']
        }
    
    async def close(self):
        """Close exchange connection."""
        self.client.close()
        logger.info("Exchange connection closed")


# Convenience function for quick testing
async def test_connection():
    """Test Demo Mode connection."""
    connector = TestnetConnector(use_testnet=True)
    
    try:
        await connector.initialize()
        
        # Get balance
        balance = await connector.get_usdt_balance()
        print(f"[OK] USDT Balance: {balance:.2f}")
        
        # Get ticker
        ticker = await connector.get_ticker('BTC/USDT')
        print(f"[OK] BTC/USDT Price: ${ticker.get('last', 0):,.2f}")
        
        # Get klines
        klines = await connector.fetch_ohlcv('BTC/USDT', '1m', 5)
        print(f"[OK] Fetched {len(klines)} klines")
        print(f"  Latest candle: O:{klines[-1][1]} H:{klines[-1][2]} L:{klines[-1][3]} C:{klines[-1][4]}")
        
        print("\n All tests passed!")
        
    except Exception as e:
        print(f" Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
