"""
Metrics Collector - Subscribes to Feed Handler and stores metrics in Redis
"""
import asyncio
import zmq
import zmq.asyncio
import msgpack
import logging
from datetime import datetime
from typing import Dict, Any
import json

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from core.database import redis_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, zmq_url: str = "tcp://127.0.0.1:5555"):
        self.zmq_url = zmq_url
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        
        self.messages_received = 0
        self.start_time = None
    
    async def start(self):
        """Connect to Feed Handler and start collecting metrics."""
        logger.info(f"Connecting to Feed Handler at {self.zmq_url}")
        
        # Connect to Feed Handler
        self.zmq_socket.connect(self.zmq_url)
        self.zmq_socket.subscribe(b'')  # Subscribe to all messages
        
        logger.info("Waiting for messages from Feed Handler...")
        self.start_time = datetime.now()
        
        # Get Redis connection
        redis_conn = await redis_client.get_redis()
        
        try:
            while True:
                # Receive message
                packed = await self.zmq_socket.recv()
                data = msgpack.unpackb(packed, raw=False)
                
                self.messages_received += 1
                
                # Calculate metrics
                metrics = self._calculate_metrics(data)
                
                # Store in Redis
                await self._store_metrics(redis_conn, data, metrics)
                
                if self.messages_received % 50 == 0:
                    logger.info(f"Processed {self.messages_received} messages | "
                              f"Last price: {data.get('last')}")
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
        finally:
            await self.close()
    
    def _calculate_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived metrics."""
        spread = None
        if data.get('bid') and data.get('ask'):
            spread = data['ask'] - data['bid']
            spread_bps = (spread / data['ask']) * 10000  # basis points
        else:
            spread_bps = None
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        msg_per_sec = self.messages_received / uptime if uptime > 0 else 0
        
        return {
            'spread': spread,
            'spread_bps': spread_bps,
            'messages_received': self.messages_received,
            'uptime_seconds': uptime,
            'messages_per_second': msg_per_sec,
            'feed_latency_ms': self._estimate_latency(data)
        }
    
    def _estimate_latency(self, data: Dict[str, Any]) -> float:
        """Estimate feed latency (Binance timestamp -> now)."""
        if data.get('timestamp'):
            now_ms = datetime.now().timestamp() * 1000
            latency = now_ms - data['timestamp']
            return max(0, latency)  # Avoid negative values
        return None
    
    async def _store_metrics(self, redis_conn, data: Dict[str, Any], metrics: Dict[str, Any]):
        """Store latest data and metrics in Redis."""
        symbol = data.get('symbol', 'UNKNOWN')
        
        # Store latest ticker
        await redis_conn.set(
            f"ticker:{symbol}",
            json.dumps(data),
            ex=60  # Expire after 60 seconds
        )
        
        # Store metrics
        await redis_conn.set(
            "metrics:latest",
            json.dumps(metrics),
            ex=60
        )
        
        # Store price history (last 100 ticks)
        await redis_conn.lpush(f"history:{symbol}:price", data.get('last'))
        await redis_conn.ltrim(f"history:{symbol}:price", 0, 99)
    
    async def close(self):
        """Cleanup."""
        logger.info("Closing metrics collector...")
        self.zmq_socket.close()
        self.zmq_context.term()
        await redis_client.close()

async def main():
    collector = MetricsCollector()
    await collector.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Metrics Collector stopped by user")
