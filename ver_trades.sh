#!/bin/bash

# Script para ver historial de trades del bot

echo "════════════════════════════════════════════════════════════"
echo " HISTORIAL DE TRADES - Trading Bot"
echo "════════════════════════════════════════════════════════════"
echo ""

LOG_FILE="logs/trading_engine.log"

if [ ! -f "$LOG_FILE" ]; then
    echo " No se encontró archivo de log: $LOG_FILE"
    echo "   El trading engine aún no ha generado logs"
    exit 1
fi

echo " SEÑALES GENERADAS:"
echo "════════════════════════════════════════════════════════════"
grep "" "$LOG_FILE" | tail -20
echo ""

echo " TRADES EJECUTADOS (Simulados en DRY_RUN):"
echo "════════════════════════════════════════════════════════════"

# Buscar bloques completos de TRADE EXECUTION
awk '/TRADE EXECUTION:/{flag=1} flag; /^=+$/ && flag{print ""; flag=0}' "$LOG_FILE" | tail -100

echo ""
echo "════════════════════════════════════════════════════════════"
echo " ESTADÍSTICAS:"
echo "════════════════════════════════════════════════════════════"

TOTAL_SIGNALS=$(grep -c "" "$LOG_FILE")
TOTAL_TRADES=$(grep -c "TRADE EXECUTION:" "$LOG_FILE")
BUY_SIGNALS=$(grep ".*BUY" "$LOG_FILE" | wc -l)
SELL_SIGNALS=$(grep ".*SELL" "$LOG_FILE" | wc -l)

echo "Total Señales Generadas: $TOTAL_SIGNALS"
echo "  - BUY: $BUY_SIGNALS"
echo "  - SELL: $SELL_SIGNALS"
echo "Total Trades Procesados: $TOTAL_TRADES"
echo ""

# Trades por símbolo
echo "Trades por Par:"
for symbol in "BTC/USDT" "ETH/USDT" "SOL/USDT"; do
    count=$(grep "TRADE EXECUTION: $symbol" "$LOG_FILE" | wc -l)
    echo "  $symbol: $count trades"
done

echo ""
echo "════════════════════════════════════════════════════════════"
