"""
Feed Handler Daemon - Multi-Symbol Market Data Streaming Service
NOW USING NATIVE BINANCE WEBSOCKET (NO CCXT)

Connects to Binance WebSocket and publishes normalized data via ZeroMQ.

Key Features:
- Multi-symbol support (efficient combined WebSocket stream)
- Topic-based publishing (subscribers can filter by symbol)
- Fault tolerance with auto-reconnection
"""
import asyncio
import zmq
import zmq.asyncio
import msgpack
import logging
from typing import Dict, Any, List
from datetime import datetime

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging.info("Using uvloop for optimized event loop")
except ImportError:
    logging.warning("uvloop not available, using standard asyncio")

# CHANGED: Import native WebSocket client instead of ccxt
from core.binance_websocket import BinanceWebSocket
from core.config import settings
from config.safe_list import get_active_symbols

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('logs/feed_handler.log')  # File
    ]
)
logger = logging.getLogger(__name__)


class MultiSymbolFeedHandler:
    """
    Multi-Symbol Feed Handler using Native Binance WebSocket
    
    Subscribes to multiple trading pairs and publishes data with topics.
    More efficient than running multiple instances (single WebSocket connection).
    """
    
    def __init__(self, symbols: List[str] = None, zmq_port: int = 5555):
        """
        Initialize multi-symbol feed handler.
        
        Args:
            symbols: List of symbols to subscribe (defaults to active from safe_list)
            zmq_port: ZeroMQ publisher port
        """
        self.symbols = symbols or get_active_symbols()
        self.zmq_url = f"tcp://127.0.0.1:{zmq_port}"
        
        # CHANGED: Use native WebSocket client
        # Demo mode is controlled by settings
        demo_mode = getattr(settings, 'BINANCE_MODE', 'demo') == 'demo'
        
        self.websocket = BinanceWebSocket(
            demo_mode=demo_mode,
            on_message=self._handle_message,
            on_error=self._handle_error,
            on_close=self._handle_close
        )
        
        # ZeroMQ Publisher
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_socket = None
        
        # Metrics per symbol
        self.messages_sent = {symbol: 0 for symbol in self.symbols}
        self.start_time = None
        
    async def start(self):
        try:
            print("\n" + "=" * 60)
            print("MULTI-SYMBOL FEED HANDLER (NATIVE BINANCE API)")
            print("=" * 60)
            print(f"Symbols: {self.symbols}")
            print(f"ZMQ URL: {self.zmq_url}")
            print("=" * 60 + "\n")
            
            print("STEP 1: Setting up ZeroMQ...")
            # Setup ZeroMQ
            self.zmq_socket = self.zmq_context.socket(zmq.PUB)
            self.zmq_socket.bind(self.zmq_url)
            print(f"[OK] ZeroMQ bound to {self.zmq_url}\n")
            
            print("STEP 2: Preparing WebSocket streams...")
            # Build stream names for all symbols
            # CHANGED: Generate stream names using native format
            streams = []
            for symbol in self.symbols:
                # Convert 'BTC/USDT' to 'btcusdt@ticker'
                normalized = self.websocket.normalize_symbol(symbol)
                
                # Use ticker stream for real-time price updates
                stream = self.websocket.ticker_stream(normalized)
                streams.append(stream)
                
                print(f"  {symbol} -> {stream}")
            
            print(f"\n[OK] Prepared {len(streams)} streams\n")
            
            print("STEP 3: Connecting to Binance WebSocket...")
            print("Waiting for first tick from Binance...\n")
            
            # CHANGED: Connect using native WebSocket (combined streams)
            await self.websocket.connect_combined_streams(streams)
            
        except Exception as e:
            print(f"[ERROR] starting feed handler: {e}")
            logger.error(f"Error starting feed handler: {e}", exc_info=True)
    
    async def _handle_message(self, data: Dict[str, Any]):
        """
        Handle incoming WebSocket message.
        
        CHANGED: Parse native Binance ticker format instead of ccxt format
        
        Args:
            data: Raw message from Binance WebSocket
        """
        try:
            # Get event type
            event_type = data.get('e')
            
            if event_type == '24hrTicker':
                # 24hr Ticker Stream
                # Convert Binance ticker to our normalized format
                symbol_raw = data.get('s', '')  # 'BTCUSDT'
                
                # Convert back to 'BTC/USDT' format
                # Assume all symbols end with 'USDT'
                if symbol_raw.endswith('USDT'):
                    base = symbol_raw[:-4]  # Remove 'USDT'
                    symbol = f"{base}/USDT"
                else:
                    symbol = symbol_raw
                
                # Check if this symbol is in our watchlist
                if symbol not in self.symbols:
                    return
                
                # Normalize ticker data
                normalized = {
                    'symbol': symbol,
                    'timestamp': data.get('E'),  # Event time
                    'datetime': datetime.fromtimestamp(data.get('E', 0) / 1000).isoformat(),
                    'bid': float(data.get('b', 0)),  # Best bid price
                    'ask': float(data.get('a', 0)),  # Best ask price
                    'last': float(data.get('c', 0)),  # Last price
                    'volume': float(data.get('v', 0)),  # Total traded base asset volume
                    'high': float(data.get('h', 0)),  # High price
                    'low': float(data.get('l', 0)),  # Low price
                    'change_percent': float(data.get('P', 0))  # Price change percent
                }
                
                # Publish to ZeroMQ
                await self._publish(symbol, normalized)
                
                # Track metrics
                self.messages_sent[symbol] += 1
                
                # Log periodically
                total_messages = sum(self.messages_sent.values())
                if total_messages > 0 and total_messages % 20 == 0:
                    print(f"\n[STATS] Published {total_messages} total messages")
                    for sym, count in self.messages_sent.items():
                        print(f"   {sym}: {count} msgs")
                    print()
            
            else:
                # Log unknown event types
                logger.debug(f"Unknown event type: {event_type}")
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def _handle_error(self, error: Exception):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
    
    async def _handle_close(self):
        """Handle WebSocket close."""
        logger.warning("WebSocket connection closed")
    
    async def _publish(self, symbol: str, data: Dict[str, Any]):
        """
        Publish data to ZMQ socket with topic.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            data: Normalized ticker data
            
        Topic-based publishing allows subscribers to filter:
        - Subscribe to "BTC/USDT" only
        - Subscribe to all (empty filter)
        """
        # Topic = symbol (allows filtering on subscriber side)
        topic = symbol.encode('utf-8')
        
        # Serialize with msgpack (faster than JSON)
        packed = msgpack.packb(data, use_bin_type=True)
        
        # Send: [topic, data]
        await self.zmq_socket.send_multipart([topic, packed])
    
    async def close(self):
        """Cleanup resources."""
        logger.info("Closing connections...")
        await self.websocket.close()
        if self.zmq_socket:
            self.zmq_socket.close()
        self.zmq_context.term()
        logger.info("Feed Handler stopped")


async def main():
    """Main entry point."""
    # Load symbols from safe_list configuration
    feed_handler = MultiSymbolFeedHandler()
    await feed_handler.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Feed Handler stopped by user")
