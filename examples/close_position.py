"""
Script para cerrar posiciones abiertas

Uso:
  python3 examples/close_position.py BTC/USDT
  python3 examples/close_position.py  # Cierra todas
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.executor.testnet_connector import TestnetConnector


async def close_positions(symbol=None):
    """Cerrar posiciones específicas o todas."""
    connector = TestnetConnector(use_testnet=True)
    await connector.initialize()
    
    try:
        if symbol:
            # Cerrar posición específica
            print(f"Cerrando posición en {symbol}...")
            result = await connector.close_position(symbol)
            if result:
                print(f" Posición cerrada: {result['id']}")
            else:
                print(f"ℹ️  No hay posición abierta en {symbol}")
        else:
            # Cerrar todas las posiciones
            print("Obteniendo todas las posiciones...")
            positions = await connector.get_positions()
            
            if not positions:
                print("ℹ️  No hay posiciones abiertas")
                return
            
            print(f"Encontradas {len(positions)} posiciones abiertas")
            
            for pos in positions:
                symbol = pos['symbol']
                print(f"\nCerrando {symbol}...")
                result = await connector.close_position(symbol)
                if result:
                    print(f"   Cerrada: {result['id']}")
        
        # Mostrar balance final
        balance = await connector.get_usdt_balance()
        print(f"\n Balance final: ${balance:,.2f} USDT")
        
    finally:
        await connector.close()


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(close_positions(symbol))
