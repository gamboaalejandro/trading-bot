#!/bin/bash

# Script para ver TODOS los logs en tiempo real
# Muestra feed handler + trading engine lado a lado

echo "════════════════════════════════════════════════════════════"
echo " DASHBOARD DE LOGS - Trading Bot"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Mostrando logs en tiempo real de:"
echo "  • Feed Handler (datos de Binance)"
echo "  • Trading Engine (señales y trades)"
echo ""
echo "Presiona Ctrl+C para salir"
echo "════════════════════════════════════════════════════════════"
echo ""

# Crear directorio de logs si no existe
mkdir -p logs

# Verificar si los archivos de log existen
if [ ! -f "logs/feed_handler.log" ]; then
    echo "️  logs/feed_handler.log no existe aún"
    echo "   El feed handler generará este archivo al iniciar"
fi

if [ ! -f "logs/trading_engine.log" ]; then
    echo "️  logs/trading_engine.log no existe aún"
    echo "   El trading engine generará este archivo al iniciar"
fi

echo ""
echo "Iniciando monitoreo..."
echo ""

# Usar tail -f en ambos archivos (se crearán si no existen)
tail -f logs/feed_handler.log logs/trading_engine.log 2>/dev/null
