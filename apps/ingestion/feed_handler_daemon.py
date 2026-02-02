"""
Feed Handler Daemon - Market Data Streaming Service
Connects to Binance WebSocket and publishes normalized data via ZeroMQ.
"""
import asyncio
import zmq
import zmq.asyncio
import msgpack
import logging
from typing import Dict, Any
from datetime import datetime

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging.info("Using uvloop for optimized event loop")
except ImportError:
    logging.warning("uvloop not available, using standard asyncio")

import ccxt.pro as ccxt
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeedHandler:
    def __init__(self, symbol: str = "BTC/USDT", zmq_port: int = 5555):
        self.symbol = symbol
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
        
        # Metrics
        self.messages_sent = 0
        self.start_time = None
        
    async def start(self):
        """Initialize connections and start streaming."""
        logger.info(f"Starting Feed Handler for {self.symbol}")
        
        # Bind ZMQ Publisher
        self.zmq_socket.bind(self.zmq_url)
        logger.info(f"ZMQ Publisher bound to {self.zmq_url}")
        
        # Load markets
        await self.exchange.load_markets()
        logger.info("Connected to Binance Futures")
        
        self.start_time = datetime.now()
        
        # Start streaming
        await self.stream_ticker()
    
    async def stream_ticker(self):
        """
        Main loop: Watch ticker from Binance and publish to ZMQ.
        """
        logger.info(f"Streaming {self.symbol} ticker...")
        
        try:
            while True:
                # Receive ticker from Binance WebSocket
                ticker = await self.exchange.watch_ticker(self.symbol)
                
                # Normalize data
                normalized_data = self._normalize_ticker(ticker)
                
                # Publish via ZMQ (using msgpack for speed)
                await self._publish(normalized_data)
                
                self.messages_sent += 1
                
                if self.messages_sent % 100 == 0:
                    logger.info(f"Published {self.messages_sent} messages")
                    
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in stream: {e}", exc_info=True)
        finally:
            await self.close()
    
    def _normalize_ticker(self, ticker: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CCXT ticker to internal format."""
        return {
            'symbol': ticker['symbol'],
            'timestamp': ticker['timestamp'],
            'datetime': ticker['datetime'],
            'bid': ticker.get('bid'),
            'ask': ticker.get('ask'),
            'last': ticker.get('last'),
            'volume': ticker.get('baseVolume'),
            'high': ticker.get('high'),
            'low': ticker.get('low'),
            'change_percent': ticker.get('percentage')
        }
    
    async def _publish(self, data: Dict[str, Any]):
        """Publish data to ZMQ socket."""
        # Serialize with msgpack (faster than JSON)
        packed = msgpack.packb(data, use_bin_type=True)
        await self.zmq_socket.send(packed)
    
    async def close(self):
        """Cleanup resources."""
        logger.info("Closing connections...")
        await self.exchange.close()
        self.zmq_socket.close()
        self.zmq_context.term()
        logger.info("Feed Handler stopped")

async def main():
    symbol = settings.AI_CONFIG.get('trading', {}).get('symbol', 'BTC/USDT')
    feed_handler = FeedHandler(symbol=symbol)
    await feed_handler.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Feed Handler stopped by user")
