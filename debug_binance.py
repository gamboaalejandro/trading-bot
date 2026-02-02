#!/usr/bin/env python3
"""
Debug Feed Handler - Shows raw ticker data from CCXT
"""
import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

import ccxt.pro as ccxt
from core.config import settings

async def main():
    print("Testing Binance connection and ticker data...")
    print(f"Symbol: {settings.AI_CONFIG.get('trading', {}).get('symbol', 'BTC/USDT')}")
    print("")
    
    exchange = ccxt.binance({
        'apiKey': settings.BINANCE_API_KEY,
        'secret': settings.BINANCE_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    try:
        await exchange.load_markets()
        print("✅ Connected to Binance Futures\n")
        
        symbol = settings.AI_CONFIG.get('trading', {}).get('symbol', 'BTC/USDT')
        
        print(f"Watching {symbol} ticker (5 ticks)...\n")
        for i in range(5):
            ticker = await exchange.watch_ticker(symbol)
            print(f"Tick {i+1}:")
            print(f"  Symbol: {ticker.get('symbol')}")
            print(f"  Last: {ticker.get('last')}")
            print(f"  Bid: {ticker.get('bid')}")
            print(f"  Ask: {ticker.get('ask')}")
            print(f"  Volume: {ticker.get('baseVolume')}")
            print(f"  Timestamp: {ticker.get('timestamp')}")
            print("")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
