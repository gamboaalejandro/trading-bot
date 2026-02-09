"""
Binance REST API Client - Native Implementation
Supports both Demo Mode and Production environments.

Implements HMAC SHA256 authentication as per Binance API documentation:
https://developers.binance.com/docs/binance-spot-api-docs/rest-api
"""
import time
import hmac
import hashlib
import requests
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from core.config import settings

logger = logging.getLogger(__name__)


class BinanceClient:
    """
    Native Binance REST API client with HMAC SHA256 authentication.
    
    Supports:
    - Demo Mode (https://demo-api.binance.com)
    - Production (https://api.binance.com)
    - Account queries
    - Order operations (MARKET, LIMIT, STOP)
    - Historical data (klines)
    - Rate limiting
    """
    
    # API Endpoints
    DEMO_BASE_URL = "https://demo-api.binance.com"
    PROD_BASE_URL = "https://api.binance.com"
    
    # Rate limits (weights per minute)
    RATE_LIMIT_WEIGHT = 1200  # Spot API: 1200 weight/minute
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        demo_mode: bool = True,
        timeout: int = 30
    ):
        """
        Initialize Binance API client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            demo_mode: If True, use Demo Mode. If False, use Production.
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.demo_mode = demo_mode
        self.timeout = timeout
        
        # Select base URL
        self.base_url = self.DEMO_BASE_URL if demo_mode else self.PROD_BASE_URL
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })
        
        # Server time offset (for timestamp sync)
        self._time_offset = 0
        
        logger.info(f"Binance Client initialized: {'DEMO MODE' if demo_mode else 'PRODUCTION'}")
        logger.info(f"Base URL: {self.base_url}")
    
    def _get_timestamp(self) -> int:
        """
        Get current timestamp in milliseconds, adjusted for server time.
        
        Returns:
            Timestamp in milliseconds
        """
        return int(time.time() * 1000) + self._time_offset
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for API request.
        
        Args:
            params: Request parameters
            
        Returns:
            Hex-encoded signature string
        """
        # Convert params to query string
        query_string = urlencode(params)
        
        # Generate HMAC SHA256
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _request(
        self,
        method: str,
        endpoint: str,
        signed: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Binance API.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., '/api/v3/account')
            signed: If True, sign request with HMAC SHA256
            **kwargs: Additional request parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.exceptions.RequestException: On network errors
            Exception: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        
        # Prepare parameters
        params = kwargs.get('params', {})
        
        if signed:
            # Add timestamp and recvWindow
            params['timestamp'] = self._get_timestamp()
            params['recvWindow'] = 5000  # 5 second window
            
            # Generate signature
            signature = self._generate_signature(params)
            params['signature'] = signature
        
        # Make request
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=self.timeout)
            elif method == 'POST':
                response = self.session.post(url, params=params, timeout=self.timeout)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for errors
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {method} {endpoint}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {endpoint} - {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def sync_time(self) -> None:
        """
        Synchronize with Binance server time to prevent timestamp errors.
        """
        try:
            response = self._request('GET', '/api/v3/time')
            server_time = response['serverTime']
            local_time = int(time.time() * 1000)
            self._time_offset = server_time - local_time
            logger.info(f"Time synchronized. Offset: {self._time_offset}ms")
        except Exception as e:
            logger.warning(f"Failed to sync time: {e}")
    
    # =========================
    # Account Endpoints
    # =========================
    
    def get_account(self) -> Dict[str, Any]:
        """
        Get current account information.
        
        Returns:
            Account info including balances
            
        Endpoint: GET /api/v3/account (SIGNED)
        Weight: 20
        """
        return self._request('GET', '/api/v3/account', signed=True)
    
    def get_balance(self, asset: str = 'USDT') -> float:
        """
        Get balance for specific asset.
        
        Args:
            asset: Asset symbol (e.g., 'USDT', 'BTC')
            
        Returns:
            Available balance as float
        """
        account = self.get_account()
        balances = account.get('balances', [])
        
        for balance in balances:
            if balance['asset'] == asset:
                return float(balance['free'])
        
        return 0.0
    
    # =========================
    # Market Data Endpoints
    # =========================
    
    def get_ticker_24hr(self, symbol: str) -> Dict[str, Any]:
        """
        Get 24hr ticker price change statistics.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            
        Returns:
            24hr ticker data
            
        Endpoint: GET /api/v3/ticker/24hr
        Weight: 2
        """
        return self._request('GET', '/api/v3/ticker/24hr', params={'symbol': symbol})
    
    def get_klines(
        self,
        symbol: str,
        interval: str = '1m',
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List]:
        """
        Get kline/candlestick data.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: Number of klines (max 1000)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            
        Returns:
            List of klines: [time, open, high, low, close, volume, ...]
            
        Endpoint: GET /api/v3/klines
        Weight: 2
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        return self._request('GET', '/api/v3/klines', params=params)
    
    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get exchange trading rules and symbol information.
        
        Args:
            symbol: Trading pair (optional)
            
        Returns:
            Exchange information including filters
            
        Endpoint: GET /api/v3/exchangeInfo
        Weight: 20
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return self._request('GET', '/api/v3/exchangeInfo', params=params)
    
    def round_quantity(self, symbol: str, quantity: float) -> float:
        """
        Round quantity to match symbol's LOT_SIZE stepSize filter.
        
        This prevents "Parameter 'quantity' has too much precision" errors.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            quantity: Raw quantity value
            
        Returns:
            Rounded quantity that matches Binance precision requirements
        """
        try:
            # Get symbol info
            exchange_info = self.get_exchange_info(symbol)
            symbols = exchange_info.get('symbols', [])
            
            if not symbols:
                logger.warning(f"No symbol info found for {symbol}, using 8 decimals")
                return round(quantity, 8)
            
            symbol_info = symbols[0]
            filters = symbol_info.get('filters', [])
            
            # Find LOT_SIZE filter
            lot_size_filter = None
            for f in filters:
                if f.get('filterType') == 'LOT_SIZE':
                    lot_size_filter = f
                    break
            
            if not lot_size_filter:
                logger.warning(f"LOT_SIZE filter not found for {symbol}, using 8 decimals")
                return round(quantity, 8)
            
            # Get stepSize and calculate precision
            step_size = float(lot_size_filter['stepSize'])
            
            # Calculate decimal places from stepSize
            # e.g., stepSize=0.001 -> 3 decimals
            step_str = f"{step_size:.10f}".rstrip('0')
            if '.' in step_str:
                precision = len(step_str.split('.')[1])
            else:
                precision = 0
            
            # Round to precision
            rounded = round(quantity, precision)
            
            logger.debug(f"Rounded {quantity} to {rounded} ({precision} decimals, stepSize={step_size})")
            
            return rounded
            
        except Exception as e:
            logger.error(f"Error rounding quantity for {symbol}: {e}")
            # Fallback to 8 decimals
            return round(quantity, 8)
    
    # =========================
    # Trading Endpoints
    # =========================

    
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = 'GTC',
        stop_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new order.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'BUY' or 'SELL'
            order_type: 'MARKET', 'LIMIT', 'STOP_LOSS', 'STOP_LOSS_LIMIT', etc.
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            time_in_force: 'GTC' (Good Till Cancel), 'IOC', 'FOK'
            stop_price: Stop price (required for STOP orders)
            
        Returns:
            Order information
            
        Endpoint: POST /api/v3/order (SIGNED)
        Weight: 1
        """
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': quantity
        }
        
        if order_type.upper() == 'LIMIT':
            if not price:
                raise ValueError("Price is required for LIMIT orders")
            params['price'] = price
            params['timeInForce'] = time_in_force
        
        if 'STOP' in order_type.upper():
            if not stop_price:
                raise ValueError("Stop price is required for STOP orders")
            params['stopPrice'] = stop_price
        
        logger.info(f"Creating order: {side} {quantity} {symbol} @ {price or 'MARKET'}")
        
        return self._request('POST', '/api/v3/order', signed=True, params=params)
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an active order.
        
        Args:
            symbol: Trading pair
            order_id: Order ID
            
        Returns:
            Cancellation result
            
        Endpoint: DELETE /api/v3/order (SIGNED)
        Weight: 1
        """
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        
        logger.info(f"Cancelling order: {order_id} for {symbol}")
        
        return self._request('DELETE', '/api/v3/order', signed=True, params=params)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Args:
            symbol: Trading pair (optional, returns all if None)
            
        Returns:
            List of open orders
            
        Endpoint: GET /api/v3/openOrders (SIGNED)
        Weight: 6 per symbol, 80 for all symbols
        """
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return self._request('GET', '/api/v3/openOrders', signed=True, params=params)
    
    def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Trading pair
            
        Returns:
            List of cancelled orders
            
        Endpoint: DELETE /api/v3/openOrders (SIGNED)
        Weight: 1
        """
        params = {'symbol': symbol}
        
        logger.info(f"Cancelling all orders for {symbol}")
        
        return self._request('DELETE', '/api/v3/openOrders', signed=True, params=params)
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.info("Binance client session closed")


# Convenience function for testing
async def test_client():
    """Test the Binance client connection."""
    from core.config import settings
    
    client = BinanceClient(
        api_key=settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_SECRET,
        demo_mode=True
    )
    
    try:
        # Sync time
        client.sync_time()
        
        # Test account endpoint
        print("\n=== Testing Account Endpoint ===")
        account = client.get_account()
        print(f" Account retrieved")
        
        # Get USDT balance
        usdt_balance = client.get_balance('USDT')
        print(f" USDT Balance: {usdt_balance:.2f}")
        
        # Test market data
        print("\n=== Testing Market Data ===")
        ticker = client.get_ticker_24hr('BTCUSDT')
        print(f" BTC/USDT Price: ${float(ticker['lastPrice']):,.2f}")
        
        # Test klines
        klines = client.get_klines('BTCUSDT', interval='1m', limit=5)
        print(f" Fetched {len(klines)} klines")
        
        print("\n All tests passed!")
        
    except Exception as e:
        print(f" Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_client())
