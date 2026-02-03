"""
Script de Ejemplo: Primeras Operaciones en Futures Testnet

Este script muestra cómo:
1. Conectarse al testnet
2. Ver tu balance
3. Calcular posiciones seguras con risk management
4. Abrir posición LONG
5. Colocar stop loss y take profit
6. Cerrar posiciones

IMPORTANTE: Este script usa TESTNET (dinero falso)
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.executor.testnet_connector import TestnetConnector
from apps.executor.risk_manager import ProfessionalRiskManager, RiskConfig


async def main():
    print("=" * 60)
    print("DEMO: TRADING EN FUTURES TESTNET")
    print("=" * 60)
    
    # 1. CONECTAR AL TESTNET
    print("\n[1/6] Conectando al testnet...")
    connector = TestnetConnector(use_testnet=True)
    await connector.initialize()
    
    # 2. VER BALANCE INICIAL
    print("\n[2/6] Obteniendo balance...")
    balance = await connector.get_usdt_balance()
    print(f"💰 Balance disponible: ${balance:,.2f} USDT")
    
    if balance < 10:
        print("⚠️ Balance muy bajo. Ve a https://testnet.binancefuture.com/ para recibir USDT de prueba")
        await connector.close()
        return
    
    # 3. CONFIGURAR RISK MANAGER
    print("\n[3/6] Configurando risk management...")
    risk_config = RiskConfig(
        max_account_risk_per_trade=0.02,  # Riesgo máximo 2% del balance
        max_daily_drawdown=0.05,           # Máxima pérdida diaria 5%
        kelly_fraction=0.25,                # Kelly conservador (1/4)
        min_notional_usdt=10.0             # Mínimo $10 por operación
    )
    risk_manager = ProfessionalRiskManager(risk_config, current_daily_pnl=0.0)
    
    # 4. OBTENER PRECIO Y CALCULAR PARÁMETROS
    print("\n[4/6] Analizando BTC/USDT...")
    ticker = await connector.get_ticker('BTC/USDT')
    current_price = ticker['last']
    print(f"📈 Precio actual BTC: ${current_price:,.2f}")
    
    # Estrategia de ejemplo: LONG con stop loss al 2% y take profit al 4%
    entry_price = current_price
    stop_loss_price = entry_price * 0.98   # -2%
    take_profit_price = entry_price * 1.04  # +4%
    
    print(f"\n📊 Parámetros de la operación:")
    print(f"   Entrada:      ${entry_price:,.2f}")
    print(f"   Stop Loss:    ${stop_loss_price:,.2f} (-2%)")
    print(f"   Take Profit:  ${take_profit_price:,.2f} (+4%)")
    
    # 5. CALCULAR TAMAÑO SEGURO DE POSICIÓN
    print("\n[5/6] Calculando tamaño seguro de posición...")
    safe_size = risk_manager.calculate_safe_size(
        balance=balance,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        win_rate=0.55,      # 55% de probabilidad de ganar (ejemplo)
        reward_ratio=2.0    # Ratio riesgo/beneficio 1:2
    )
    
    if safe_size == 0:
        print("❌ No se puede abrir posición (risk manager bloqueó)")
        await connector.close()
        return
    
    notional_value = safe_size * entry_price
    risk_amount = safe_size * (entry_price - stop_loss_price)
    potential_profit = safe_size * (take_profit_price - entry_price)
    
    print(f"\n✅ Tamaño calculado:")
    print(f"   Cantidad BTC:     {safe_size:.6f}")
    print(f"   Valor Notional:   ${notional_value:.2f}")
    print(f"   Riesgo (si SL):   ${risk_amount:.2f} ({risk_amount/balance*100:.2f}% del balance)")
    print(f"   Ganancia (si TP): ${potential_profit:.2f} ({potential_profit/balance*100:.2f}% del balance)")
    
    # 6. PREGUNTAR CONFIRMACIÓN
    print("\n" + "=" * 60)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("=" * 60)
    response = input("\n¿Ejecutar esta operación en el TESTNET? (si/no): ").lower()
    
    if response != 'si':
        print("\n❌ Operación cancelada por el usuario")
        await connector.close()
        return
    
    # 7. ABRIR POSICIÓN LONG
    print("\n[6/6] Ejecutando operación...")
    try:
        # Orden de mercado para entrar
        order = await connector.create_market_order(
            symbol='BTC/USDT',
            side='buy',  # LONG
            amount=safe_size
        )
        print(f"\n✅ Posición LONG abierta:")
        print(f"   Order ID: {order['id']}")
        print(f"   Estado: {order['status']}")
        print(f"   Cantidad: {order.get('filled', safe_size):.6f} BTC")
        
        # Colocar Stop Loss
        print("\n⚙️  Colocando Stop Loss...")
        sl_order = await connector.create_stop_loss(
            symbol='BTC/USDT',
            side='sell',  # Cerrar LONG = vender
            amount=safe_size,
            stop_price=stop_loss_price
        )
        print(f"✅ Stop Loss colocado en ${stop_loss_price:,.2f}")
        
        # Colocar Take Profit (orden límite)
        print("\n⚙️  Colocando Take Profit...")
        tp_order = await connector.create_limit_order(
            symbol='BTC/USDT',
            side='sell',  # Cerrar LONG = vender
            amount=safe_size,
            price=take_profit_price,
            reduce_only=True
        )
        print(f"✅ Take Profit colocado en ${take_profit_price:,.2f}")
        
        # Ver posición actual
        print("\n📊 Verificando posición...")
        await asyncio.sleep(1)  # Esperar a que se actualice
        position = await connector.get_position('BTC/USDT')
        
        if position:
            print(f"\n✅ Posición confirmada:")
            print(f"   Lado: {position.get('side')}")
            print(f"   Contratos: {position.get('contracts')}")
            print(f"   Precio promedio: ${position.get('entryPrice', 0):,.2f}")
            print(f"   P&L no realizado: ${position.get('unrealizedPnl', 0):.2f}")
            
            print("\n" + "=" * 60)
            print("🎯 OPERACIÓN COMPLETADA")
            print("=" * 60)
            print("\nTu posición está activa con:")
            print(f"  ✅ Stop Loss en ${stop_loss_price:,.2f}")
            print(f"  ✅ Take Profit en ${take_profit_price:,.2f}")
            print("\nPuedes monitorear en: https://testnet.binancefuture.com/")
            print("\nPara cerrar manualmente:")
            print(f"  python3 examples/close_position.py")
        
    except Exception as e:
        print(f"\n❌ Error ejecutando operación: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await connector.close()


if __name__ == "__main__":
    print("\n⚠️  ADVERTENCIA: Este script opera en TESTNET (dinero de prueba)")
    print("Para operar en PRODUCCIÓN, cambia USE_TESTNET=false en .env\n")
    
    asyncio.run(main())
