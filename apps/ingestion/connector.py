import ccxt.pro as ccxt  # Use ccxt.pro for WebSocket support (now merged in ccxt)
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.config import settings
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExchangeConnector(ABC):
    """Abstract Base Class for Exchange Connectors."""
    
    @abstractmethod
    async def connect(self):
        """Establish connection to the exchange."""
        pass

    @abstractmethod
    async def close(self):
        """Close connection."""
        pass
    
    @abstractmethod
    async def watch_ticker(self, symbol: str):
        """Stream real-time ticker data."""
        pass

class BinanceConnector(ExchangeConnector):
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Default to Futures
            }
        })
        # Set sandbox mode if valid for the specific exchange instance if needed
        # self.exchange.set_sandbox_mode(True) 

    async def connect(self):
        """CCXT handles connection lazily, but we can verify credentials here."""
        try:
            await self.exchange.load_markets()
            logger.info("Connected to Binance Futures successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            raise

    async def close(self):
        await self.exchange.close()

    async def watch_ticker(self, symbol: str):
        """
        Generator that yields ticker data in real-time.
        """
        try:
            while True:
                ticker = await self.exchange.watch_ticker(symbol)
                yield ticker
        except Exception as e:
            logger.error(f"Error in watching ticker {symbol}: {e}")
            raise
        finally:
            await self.close()

    async def fetch_balance(self) -> Dict[str, Any]:
        return await self.exchange.fetch_balance()
