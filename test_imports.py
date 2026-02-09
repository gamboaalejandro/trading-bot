"""
Simple test to verify imports work correctly
Run from project root with PYTHONPATH set
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("TESTING IMPORTS")
print("=" * 60)
print(f"Python path: {sys.path[0]}")
print("")

try:
    print("1. Testing core.config import...")
    from core.config import settings
    print("   SUCCESS")
    print(f"   - Settings loaded: {type(settings)}")
except Exception as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

try:
    print("\n2. Testing core.binance_client import...")
    from core.binance_client import BinanceClient
    print("   SUCCESS")
    print(f"   - BinanceClient: {BinanceClient}")
except Exception as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

try:
    print("\n3. Testing core.binance_websocket import...")
    from core.binance_websocket import BinanceWebSocket
    print("   SUCCESS")
    print(f"   - BinanceWebSocket: {BinanceWebSocket}")
except Exception as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

try:
    print("\n4. Testing apps.executor.testnet_connector import...")
    from apps.executor.testnet_connector import TestnetConnector
    print("   SUCCESS")
    print(f"   - TestnetConnector: {TestnetConnector}")
except Exception as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

try:
    print("\n5. Testing apps.ingestion.feed_handler_daemon import...")
    from apps.ingestion.feed_handler_daemon import MultiSymbolFeedHandler
    print("   SUCCESS")
    print(f"   - MultiSymbolFeedHandler: {MultiSymbolFeedHandler}")
except Exception as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL IMPORTS SUCCESSFUL!")
print("=" * 60)
print("\nYou can now run the trading bot:")
print("  PowerShell: .\\run_bot.ps1")
print("  Or manually: python orchestrator.py")
