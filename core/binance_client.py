"""
Binance REST API Client - Native Implementation
Supports both Demo Mode and Production environments.

Implements HMAC SHA256 authentication as per Binance API documentation:
https://developers.binance.com/docs/binance-spot-api-docs/rest-api
"""
import time
from decimal import Decimal, ROUND_DOWN
import hmac
import hashlib
import requests
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from core.config import settings

logger = logging.getLogger(__name__)


class CancelReplaceError(Exception):
    """A POST /api/v3/order/cancelReplace call did not fully succeed.

    Binance answers HTTP 4xx with code -2022 (cancel failed, new order not
    attempted under STOP_ON_FAILURE) or -2021 (cancel succeeded, new order
    failed). ``cancel_result``/``new_order_result`` hold SUCCESS, FAILURE or
    NOT_ATTEMPTED; None when the outcome is unknown (network error, timeout,
    unparsable body).
    """

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        cancel_result: Optional[str] = None,
        new_order_result: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.cancel_result = cancel_result
        self.new_order_result = new_order_result
        self.data = data or {}

    @property
    def cancel_succeeded(self) -> bool:
        """The old order was cancelled (the position may now be unprotected)."""
        return self.cancel_result == "SUCCESS"

    @property
    def outcome_unknown(self) -> bool:
        """Nothing is known about what the exchange did."""
        return self.cancel_result is None

    @property
    def cancel_error_code(self) -> Optional[int]:
        """Binance error code of the cancel leg (e.g. -2011 unknown order)."""
        resp = self.data.get("cancelResponse") or {}
        return resp.get("code")


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
        if demo_mode:
            # Fallback to api.binance.us for demo (mocking) if restricted,
            # or try the visual testnet.
            # NOTE: If we are geo-blocked on testnet, we should probably fail gracefully or use a mock.
            import os
            # If default testnet fails, users can set BINANCE_TESTNET_URL in .env
            self.base_url = os.getenv('BINANCE_TESTNET_URL', 'https://testnet.binance.vision')
        else:
            self.base_url = self.PROD_BASE_URL
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })
        
        # Server time offset (for timestamp sync)
        self._time_offset = 0
        self._exchange_info_cache: Dict[str, Dict[str, Any]] = {}
        
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
    
    def get_server_time(self) -> int:
        """
        Exchange server time in milliseconds.

        Endpoint: GET /api/v3/time
        Weight: 1
        """
        return int(self._request('GET', '/api/v3/time')['serverTime'])

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
        end_time: Optional[int] = None,
        closed_only: bool = False,
    ) -> List[List]:
        """
        Get kline/candlestick data.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: Number of klines (max 1000)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            closed_only: If True, drop every row whose closeTime >= serverTime
                (the candle still forming is never returned; PLAN §4.3)
            
        Returns:
            List of klines: [time, open, high, low, close, volume, closeTime, ...]
            
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
        
        rows = self._request('GET', '/api/v3/klines', params=params)
        if closed_only and rows:
            server_time = self.get_server_time()
            rows = [r for r in rows if int(r[6]) < server_time]
        return rows
    
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
        # Trading rules rarely change: cache per symbol (weight 20 per call)
        cache_key = symbol or '*'
        if cache_key in self._exchange_info_cache:
            return self._exchange_info_cache[cache_key]

        params = {}
        if symbol:
            params['symbol'] = symbol
        
        info = self._request('GET', '/api/v3/exchangeInfo', params=params)
        self._exchange_info_cache[cache_key] = info
        return info
    
    def round_price(self, symbol: str, price: float) -> float:
        """Round a price DOWN to the symbol's PRICE_FILTER tickSize."""
        try:
            symbols = self.get_exchange_info(symbol).get('symbols', [])
            filters = symbols[0].get('filters', []) if symbols else []
            for f in filters:
                if f.get('filterType') == 'PRICE_FILTER':
                    tick = Decimal(f['tickSize']).normalize()
                    ticks = (Decimal(str(price)) / tick).to_integral_value(rounding=ROUND_DOWN)
                    return float(ticks * tick)
        except Exception as e:
            logger.error(f"Error rounding price for {symbol}: {e}")
        return round(price, 8)

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
            
            # Round DOWN to a multiple of stepSize: rounding up can ask for
            # more than the available balance (insufficient balance errors)
            step = Decimal(lot_size_filter['stepSize'])
            steps = (Decimal(str(quantity)) / step).to_integral_value(rounding=ROUND_DOWN)
            rounded = float(round(steps * step, precision))
            
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
        stop_price: Optional[float] = None,
        new_client_order_id: Optional[str] = None,
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
            new_client_order_id: Optional deterministic id (idempotent retries)
            
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

        if new_client_order_id:
            params['newClientOrderId'] = new_client_order_id
        
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
    
    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query an order (open or closed) by id or by client order id.

        Args:
            symbol: Trading pair
            order_id: Order ID
            orig_client_order_id: Client order id (used when order_id is None)

        Returns:
            Order status (status, executedQty, cummulativeQuoteQty, stopPrice...)

        Endpoint: GET /api/v3/order (SIGNED)
        Weight: 4
        """
        if order_id is None and not orig_client_order_id:
            raise ValueError("order_id or orig_client_order_id is required")
        params: Dict[str, Any] = {'symbol': symbol}
        if order_id is not None:
            params['orderId'] = order_id
        else:
            params['origClientOrderId'] = orig_client_order_id
        return self._request('GET', '/api/v3/order', signed=True, params=params)

    def cancel_replace_order(
        self,
        symbol: str,
        cancel_order_id: int,
        side: str,
        order_type: str,
        quantity: float,
        stop_price: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        cancel_replace_mode: str = 'STOP_ON_FAILURE',
        new_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atomically cancel an order and place a new one (e.g. move a stop).

        With ``cancelReplaceMode=STOP_ON_FAILURE`` the new order is only
        attempted if the cancel succeeded, so a failed cancel leaves the old
        order untouched. [VERIFICAR parameters against
        https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints]

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            cancel_order_id: orderId of the order to cancel
            side: 'BUY' or 'SELL'
            order_type: New order type (e.g., 'STOP_LOSS')
            quantity: New order quantity
            stop_price: Stop price (required for STOP order types)
            price: Limit price (LIMIT / *_LIMIT order types)
            time_in_force: Required with a limit price
            cancel_replace_mode: 'STOP_ON_FAILURE' (default) or 'ALLOW_FAILURE'
            new_client_order_id: Optional deterministic id for the new order

        Returns:
            Response with cancelResult, newOrderResult, cancelResponse and
            newOrderResponse (both results SUCCESS).

        Raises:
            CancelReplaceError: when either leg failed or the outcome is unknown.

        Endpoint: POST /api/v3/order/cancelReplace (SIGNED)
        Weight: 1
        """
        params: Dict[str, Any] = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'cancelReplaceMode': cancel_replace_mode,
            'cancelOrderId': cancel_order_id,
            'quantity': quantity,
        }
        if 'STOP' in order_type.upper() or 'TAKE_PROFIT' in order_type.upper():
            if not stop_price:
                raise ValueError("Stop price is required for STOP orders")
            params['stopPrice'] = stop_price
        if price is not None:
            params['price'] = price
            params['timeInForce'] = time_in_force or 'GTC'
        if new_client_order_id:
            params['newClientOrderId'] = new_client_order_id

        logger.info(
            f"Cancel-replace {symbol}: cancel {cancel_order_id} -> "
            f"{side.upper()} {order_type.upper()} {quantity} stop={stop_price} ({cancel_replace_mode})"
        )
        try:
            result = self._request('POST', '/api/v3/order/cancelReplace', signed=True, params=params)
        except requests.exceptions.HTTPError as e:
            raise self._cancel_replace_error(e) from e
        except requests.exceptions.RequestException as e:
            raise CancelReplaceError(f"cancelReplace outcome unknown: {e}") from e

        if result.get('cancelResult') != 'SUCCESS' or result.get('newOrderResult') != 'SUCCESS':
            raise CancelReplaceError(
                "cancelReplace did not fully succeed",
                cancel_result=result.get('cancelResult'),
                new_order_result=result.get('newOrderResult'),
                data=result,
            )
        return result

    @staticmethod
    def _cancel_replace_error(error: requests.exceptions.HTTPError) -> CancelReplaceError:
        """Translate a 4xx cancelReplace answer into a CancelReplaceError."""
        status = getattr(error.response, 'status_code', None)
        if status is None or status >= 500:
            # 5xx: Binance does not know whether the request was executed
            return CancelReplaceError(f"cancelReplace outcome unknown (HTTP {status}): {error}")
        try:
            body = error.response.json()
        except Exception:
            return CancelReplaceError(f"cancelReplace failed: {error}")
        data = body.get('data') or {}
        return CancelReplaceError(
            f"cancelReplace failed: {body.get('code')} {body.get('msg')}",
            code=body.get('code'),
            # Without a data payload the request was rejected before any leg ran
            cancel_result=data.get('cancelResult', 'NOT_ATTEMPTED' if not data else None),
            new_order_result=data.get('newOrderResult', 'NOT_ATTEMPTED' if not data else None),
            data=data,
        )

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
