"""
Feed Handler Daemon - Multi-Symbol Market Data Streaming Service
Connects to Binance WebSocket and publishes normalized data via ZeroMQ.

Key Features:
- Multi-symbol support (efficient single WebSocket)
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

import ccxt.pro as ccxt
from core.config import settings
from config.safe_list import get_active_symbols

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiSymbolFeedHandler:
    """
    Multi-Symbol Feed Handler
    
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
        
        # Binance Connector
        self.exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # ZeroMQ Publisher
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.PUB)
        
        # Metrics per symbol
        self.messages_sent = {symbol: 0 for symbol in self.symbols}
        self.start_time = None
        
    async def start(self):
        """Initialize connections and start streaming."""
        logger.info(f"Starting Multi-Symbol Feed Handler")
        logger.info(f"Symbols: {self.symbols}")
        
        # Bind ZMQ Publisher
        self.zmq_socket.bind(self.zmq_url)
        logger.info(f"ZMQ Publisher bound to {self.zmq_url}")
        
        # Load markets
        await self.exchange.load_markets()
        logger.info("Connected to Binance Futures")
        
        self.start_time = datetime.now()
        
        # Start streaming
        await self.stream_tickers()
    
    async def stream_tickers(self):
        """
        Main loop: Watch tickers from Binance and publish to ZMQ.
        
        Uses watch_tickers (plural) for efficient multi-symbol subscription.
        """
        logger.info(f"Streaming {len(self.symbols)} symbols...")
        
        try:
            while True:
                # Receive tickers from Binance WebSocket (ALL symbols in one call)
                tickers = await self.exchange.watch_tickers(self.symbols)
                
                # Process each ticker
                for symbol, ticker in tickers.items():
                    if symbol not in self.symbols:
                        continue  # Skip unexpected symbols
                    
                    # Normalize data
                    normalized_data = self._normalize_ticker(ticker)
                    
                    # Publish via ZMQ with topic (symbol-specific)
                    await self._publish(symbol, normalized_data)
                    
                    self.messages_sent[symbol] += 1
                
                # Log metrics every 100 total messages
                total_messages = sum(self.messages_sent.values())
                if total_messages % 100 == 0:
                    logger.info(f"Published {total_messages} total messages")
                    for sym in self.symbols:
                        logger.debug(f"  {sym}: {self.messages_sent[sym]} msgs")
                        
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in stream: {e}", exc_info=True)
        finally:
            await self.close()
    
    def _normalize_ticker(self, ticker: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CCXT ticker to internal format."""
        normalized = {
            'symbol': ticker.get('symbol', 'UNKNOWN'),
            'timestamp': ticker.get('timestamp'),
            'datetime': ticker.get('datetime'),
            'bid': ticker.get('bid'),
            'ask': ticker.get('ask'),
            'last': ticker.get('last'),
            'volume': ticker.get('baseVolume'),
            'high': ticker.get('high'),
            'low': ticker.get('low'),
            'change_percent': ticker.get('percentage')
        }
        
        # Log if critical fields are missing
        if not normalized['last']:
            logger.warning(f"Missing 'last' price in ticker: {ticker}")
        
        return normalized
    
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
        await self.exchange.close()
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

