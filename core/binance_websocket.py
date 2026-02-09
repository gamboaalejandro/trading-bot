"""
Binance WebSocket Client - Native Implementation
Supports both Demo Mode and Production WebSocket streams.

Implements WebSocket streams as per Binance documentation:
https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
"""
import asyncio
import json
import logging
import websockets
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class BinanceWebSocket:
    """
    Native Binance WebSocket client for market data streams.
    
    Supports:
    - Demo Mode (wss://demo-stream.binance.com/ws)
    - Production (wss://stream.binance.com/ws)
    - Kline/Candlestick streams
    - Ticker streams
    - Trade streams
    - Combined streams (multiple symbols)
    - Auto-reconnection
    - Ping/Pong heartbeat
    """
    
    # WebSocket URLs
    DEMO_WS_URL = "wss://demo-stream.binance.com"
    PROD_WS_URL = "wss://stream.binance.com"
    
    # Stream endpoints
    SINGLE_STREAM = "/ws"  # Single raw stream
    COMBINED_STREAM = "/stream"  # Combined streams
    
    def __init__(
        self,
        demo_mode: bool = True,
        on_message: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_close: Optional[Callable] = None
    ):
        """
        Initialize Binance WebSocket client.
        
        Args:
            demo_mode: If True, use Demo Mode. If False, use Production.
            on_message: Callback for incoming messages
            on_error: Callback for errors
            on_close: Callback when connection closes
        """
        self.demo_mode = demo_mode
        self.base_url = self.DEMO_WS_URL if demo_mode else self.PROD_WS_URL
        
        # Callbacks
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        
        # Connection state
        self.websocket = None
        self.is_running = False
        self.subscriptions: Set[str] = set()
        
        # Reconnection settings
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_count = 0
        
        logger.info(f"Binance WebSocket initialized: {'DEMO MODE' if demo_mode else 'PRODUCTION'}")
        logger.info(f"Base URL: {self.base_url}")
    
    async def connect_single_stream(self, stream_name: str):
        """
        Connect to a single raw stream.
        
        Args:
            stream_name: Stream name (e.g., 'btcusdt@ticker', 'ethusdt@kline_1m')
            
        Example:
            await ws.connect_single_stream('btcusdt@ticker')
        """
        url = f"{self.base_url}{self.SINGLE_STREAM}/{stream_name}"
        logger.info(f"Connecting to single stream: {stream_name}")
        
        await self._connect(url)
    
    async def connect_combined_streams(self, stream_names: List[str]):
        """
        Connect to combined streams (multiple symbols).
        
        Args:
            stream_names: List of stream names
            
        Example:
            await ws.connect_combined_streams([
                'btcusdt@ticker',
                'ethusdt@ticker',
                'solusdt@ticker'
            ])
        """
        # Build stream parameter
        streams_param = '/'.join(stream_names)
        url = f"{self.base_url}{self.COMBINED_STREAM}?streams={streams_param}"
        
        logger.info(f"Connecting to {len(stream_names)} combined streams")
        logger.debug(f"Streams: {stream_names}")
        
        self.subscriptions = set(stream_names)
        await self._connect(url)
    
    async def _connect(self, url: str):
        """
        Internal method to establish WebSocket connection.
        
        Args:
            url: Full WebSocket URL
        """
        self.is_running = True
        
        while self.is_running and self.reconnect_count < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to: {url}")
                
                async with websockets.connect(
                    url,
                    ping_interval=20,  # Send ping every 20s
                    ping_timeout=10,   # Timeout after 10s
                    close_timeout=5
                ) as websocket:
                    self.websocket = websocket
                    self.reconnect_count = 0  # Reset on successful connection
                    
                    logger.info(" WebSocket connected")
                    
                    # Start receiving messages
                    await self._receive_messages()
                    
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_reconnect()
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                if self.on_error:
                    await self.on_error(e)
                await self._handle_reconnect()
        
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            if self.on_close:
                await self.on_close()
    
    async def _receive_messages(self):
        """
        Receive and process messages from WebSocket.
        """
        try:
            async for message in self.websocket:
                try:
                    # Parse JSON message
                    data = json.loads(message)
                    
                    # Handle combined stream format
                    if 'stream' in data and 'data' in data:
                        # Combined stream: {"stream": "btcusdt@ticker", "data": {...}}
                        stream_name = data['stream']
                        payload = data['data']
                        
                        # Add stream info to payload
                        payload['_stream'] = stream_name
                        
                        if self.on_message:
                            await self.on_message(payload)
                    else:
                        # Single stream: direct payload
                        if self.on_message:
                            await self.on_message(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    logger.debug(f"Raw message: {message}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed while receiving messages")
            raise
    
    async def _handle_reconnect(self):
        """
        Handle reconnection logic with exponential backoff.
        """
        if not self.is_running:
            return
        
        self.reconnect_count += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_count - 1)), 60)
        
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_count}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)
    
    async def close(self):
        """
        Close WebSocket connection gracefully.
        """
        logger.info("Closing WebSocket connection...")
        self.is_running = False
        
        if self.websocket:
            await self.websocket.close()
        
        logger.info("WebSocket connection closed")
    
    # =========================
    # Stream Helpers
    # =========================
    
    @staticmethod
    def ticker_stream(symbol: str) -> str:
        """
        Generate ticker stream name.
        
        Args:
            symbol: Symbol in uppercase (e.g., 'BTCUSDT')
            
        Returns:
            Stream name (e.g., 'btcusdt@ticker')
        """
        return f"{symbol.lower()}@ticker"
    
    @staticmethod
    def kline_stream(symbol: str, interval: str = '1m') -> str:
        """
        Generate kline/candlestick stream name.
        
        Args:
            symbol: Symbol in uppercase (e.g., 'BTCUSDT')
            interval: Interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            
        Returns:
            Stream name (e.g., 'btcusdt@kline_1m')
        """
        return f"{symbol.lower()}@kline_{interval}"
    
    @staticmethod
    def trade_stream(symbol: str) -> str:
        """
        Generate trade stream name.
        
        Args:
            symbol: Symbol in uppercase (e.g., 'BTCUSDT')
            
        Returns:
            Stream name (e.g., 'btcusdt@trade')
        """
        return f"{symbol.lower()}@trade"
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Normalize symbol format from 'BTC/USDT' to 'BTCUSDT'.
        
        Args:
            symbol: Symbol with slash (e.g., 'BTC/USDT')
            
        Returns:
            Symbol without slash (e.g., 'BTCUSDT')
        """
        return symbol.replace('/', '').upper()


# Example usage and testing
async def test_websocket():
    """Test WebSocket connection with ticker streams."""
    
    messages_received = 0
    
    async def on_message(data: Dict[str, Any]):
        nonlocal messages_received
        messages_received += 1
        
        # Print ticker updates
        if data.get('e') == 'kline':
            kline = data['k']
            print(f"Kline: {data['s']} | Close: {kline['c']} | Volume: {kline['v']}")
        elif data.get('e') == '24hrTicker':
            print(f"Ticker: {data['s']} | Price: {data['c']} | 24h Change: {data['P']}%")
        else:
            print(f"Message: {data.get('e', 'unknown')} - {data.get('s', 'N/A')}")
        
        # Stop after 10 messages for testing
        if messages_received >= 10:
            print(f"\n Received {messages_received} messages. Test complete!")
    
    async def on_error(error: Exception):
        print(f" Error: {error}")
    
    async def on_close():
        print(" Connection closed")
    
    # Create WebSocket client
    ws = BinanceWebSocket(
        demo_mode=True,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Test combined streams
    streams = [
        ws.ticker_stream('BTCUSDT'),
        ws.ticker_stream('ETHUSDT'),
        ws.kline_stream('BTCUSDT', '1m')
    ]
    
    print(f" Connecting to {len(streams)} streams...")
    print(f"Streams: {streams}\n")
    
    try:
        # Run for 30 seconds or until 10 messages
        await asyncio.wait_for(
            ws.connect_combined_streams(streams),
            timeout=30
        )
    except asyncio.TimeoutError:
        print("\n⏱️ Test timeout reached")
    finally:
        await ws.close()


if __name__ == "__main__":
    asyncio.run(test_websocket())
