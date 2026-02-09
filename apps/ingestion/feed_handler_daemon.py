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
        # self.zmq_socket will be initialized in start()
        
        # Metrics per symbol
        self.messages_sent = {symbol: 0 for symbol in self.symbols}
        self.start_time = None
        
    async def start(self):
        try:
            print("\n" + "=" * 60)
            print("🚀 MULTI-SYMBOL FEED HANDLER")
            print("=" * 60)
            print(f"Symbols: {self.symbols}")
            print(f"ZMQ URL: {self.zmq_url}")
            print("=" * 60 + "\n")
            
            print("STEP 1: Setting up ZeroMQ...")
            # Setup ZeroMQ
            self.zmq_socket = self.zmq_context.socket(zmq.PUB)
            self.zmq_socket.bind(self.zmq_url)
            print(f"✓ ZeroMQ bound to {self.zmq_url}\n")
            
            # SKIP load_markets() - CAUSA LOOP INFINITO
            # Es opcional para watch_tickers, no lo necesitamos
            print("STEP 2: Skipping load_markets (causes infinite loop)")
            print("✓ Markets will load automatically on first watch_tickers call\n")
            
            print("STEP 3: Starting ticker stream...")
            print(f"Watching tickers for: {self.symbols}\n")
            # Start streaming
            await self._stream_tickers()
        except Exception as e:
            print(f"❌ ERROR starting feed handler: {e}")
            logger.error(f"Error starting feed handler: {e}", exc_info=True)
        
    
    async def _stream_tickers(self):
        """
        Stream ticker updates for all symbols with auto-recovery.
        
        Uses ccxt's watch_tickers (WebSocket) for real-time data.
        Automatically reconnects if connection is lost.
        """
        print("📡 Entering _stream_tickers loop...")
        
        reconnect_count = 0
        max_reconnects = 10
        
        while reconnect_count < max_reconnects:
            try:
                msg_count = 0
                print(f"🔄 Starting watch_tickers for {len(self.symbols)} symbols...")
                print("Waiting for first tick from Binance...\n")
                
                while True:
                    try:
                        # Watch ALL symbols at once with 90s timeout
                        tickers = await asyncio.wait_for(
                            self.exchange.watch_tickers(self.symbols),
                            timeout=90  # If no data for 90s, reconnect
                        )
                        
                        # Reset reconnect counter on successful receive
                        reconnect_count = 0
                        
                        print(f"✓ Received {len(tickers)} ticker updates")
                        
                        # Publish each ticker
                        published_count = 0
                        for symbol, ticker in tickers.items():
                            # Normalize symbol: remove :USDT suffix (Futures format)
                            normalized_symbol = symbol.split(':')[0]  # 'BTC/USDT:USDT' -> 'BTC/USDT'
                            
                            print(f"   {symbol} -> {normalized_symbol} ... match? {normalized_symbol in self.symbols}")
                            
                            if normalized_symbol in self.symbols:
                                # Normalize data before publishing
                                normalized_data = self._normalize_ticker(ticker)
                                # Publish with NORMALIZED symbol name
                                await self._publish(normalized_symbol, normalized_data)
                                msg_count += 1
                                published_count += 1
                                
                                # Track per-symbol metrics
                                if normalized_symbol not in self.messages_sent:
                                    self.messages_sent[normalized_symbol] = 0
                                self.messages_sent[normalized_symbol] += 1
                        
                        print(f"   ✅ Published: {published_count}/{len(tickers)}\n")
                        
                        # Log stats every 10 messages
                        if msg_count > 0 and msg_count % 10 == 0:
                            print(f"\n📊 Published {msg_count} total messages")
                            for symbol, count in self.messages_sent.items():
                                print(f"   {symbol}: {count} msgs")
                            print()
                    
                    except asyncio.TimeoutError:
                        print(f"⚠️ No data for 90 seconds - reconnecting...")
                        logger.warning("Feed handler timeout - reconnecting to Binance")
                        raise  # Trigger reconnection
                
            except Exception as e:
                reconnect_count += 1
                print(f"❌ ERROR in ticker stream: {e}")
                print(f"🔄 Reconnecting... (attempt {reconnect_count}/{max_reconnects})")
                logger.error(f"Error in ticker stream: {e}", exc_info=True)
                
                # Close and recreate exchange connection
                try:
                    await self.exchange.close()
                except:
                    pass
                
                # Wait before reconnecting
                await asyncio.sleep(5)
                
                # Recreate exchange
                self.exchange = ccxt.binance({
                    'apiKey': settings.BINANCE_API_KEY,
                    'secret': settings.BINANCE_SECRET,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'}
                })
                
                print("✓ Exchange connection recreated\n")
        
        print(f"❌ Max reconnection attempts ({max_reconnects}) reached - stopping")
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

