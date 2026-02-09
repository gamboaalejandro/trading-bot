"""
Script para ver el estado de tus posiciones y balance

Uso:
  python3 examples/check_status.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.executor.testnet_connector import TestnetConnector


async def check_status():
    """Mostrar estado completo de la cuenta."""
    connector = TestnetConnector(use_testnet=True)
    await connector.initialize()
    
    try:
        print("=" * 60)
        print("ESTADO DE CUENTA - FUTURES TESTNET")
        print("=" * 60)
        
        # Balance
        balance_info = await connector.get_balance()
        usdt_balance = balance_info.get('USDT', {})
        
        print("\n BALANCE:")
        print(f"   Disponible:    ${usdt_balance.get('free', 0):,.2f} USDT")
        print(f"   En órdenes:    ${usdt_balance.get('used', 0):,.2f} USDT")
        print(f"   Total:         ${usdt_balance.get('total', 0):,.2f} USDT")
        
        # Posiciones
        print("\n POSICIONES ABIERTAS:")
        positions = await connector.get_positions()
        
        if not positions:
            print("   (ninguna)")
        else:
            for pos in positions:
                side = pos.get('side', 'unknown')
                symbol = pos.get('symbol', '')
                contracts = pos.get('contracts', 0)
                entry_price = pos.get('entryPrice', 0)
                mark_price = pos.get('markPrice', 0)
                unrealized_pnl = pos.get('unrealizedPnl', 0)
                leverage = pos.get('leverage', 1)
                
                pnl_color = "🟢" if unrealized_pnl >= 0 else ""
                
                print(f"\n   {symbol}:")
                print(f"      Lado:         {side.upper()}")
                print(f"      Contratos:    {contracts}")
                print(f"      Precio Entry: ${entry_price:,.2f}")
                print(f"      Precio Mark:  ${mark_price:,.2f}")
                print(f"      Apalancamiento: {leverage}x")
                print(f"      P&L:          {pnl_color} ${unrealized_pnl:,.2f}")
        
        # Ticker de los pares principales
        print("\n PRECIOS ACTUALES:")
        symbols = ['BTC/USDT', 'ETH/USDT']
        for symbol in symbols:
            try:
                ticker = await connector.get_ticker(symbol)
                price = ticker.get('last', 0)
                change = ticker.get('percentage', 0)
                
                change_color = "🟢" if change >= 0 else ""
                print(f"   {symbol}: ${price:,.2f} {change_color} {change:+.2f}%")
            except:
                pass
        
        print("\n" + "=" * 60)
        
    finally:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(check_status())
