"""
Quick test to verify Binance WebSocket connection works
"""
import asyncio
import sys
sys.path.insert(0, '.')

from core.binance_websocket import BinanceWebSocket

async def test():
    print("Testing Binance WebSocket connection...")
    
    message_count = 0
    
    async def on_message(data):
        nonlocal message_count
        message_count += 1
        print(f"[{message_count}] Received: {data.get('e')} - {data.get('s', 'N/A')}")
        
        if message_count >= 5:
            print("\n[OK] WebSocket is working!")
            return
    
    ws = BinanceWebSocket(
        demo_mode=True,
        on_message=on_message
    )
    
    streams = [
        ws.ticker_stream('BTCUSDT'),
        ws.ticker_stream('ETHUSDT')
    ]
    
    print(f"Connecting to: {streams}")
    print("Waiting for messages...\n")
    
    try:
        await asyncio.wait_for(
            ws.connect_combined_streams(streams),
            timeout=15
        )
    except asyncio.TimeoutError:
        if message_count > 0:
            print(f"\n[OK] Received {message_count} messages - WebSocket working!")
        else:
            print("\n[ERROR] No messages received")
    finally:
        await ws.close()

if __name__ == "__main__":
    asyncio.run(test())
