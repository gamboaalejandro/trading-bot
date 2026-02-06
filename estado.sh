#!/bin/bash

# Script para verificar si el bot está operativo
# Muestra el estado actual del sistema de trading

echo "════════════════════════════════════════"
echo "📊 ESTADO DEL TRADING BOT"
echo "════════════════════════════════════════"
echo ""

# Verificar Feed Handler
FEED_PID=$(ps aux | grep "feed_handler_daemon" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$FEED_PID" ]; then
    echo "✅ Feed Handler: ACTIVO (PID: $FEED_PID)"
else
    echo "❌ Feed Handler: NO ESTÁ CORRIENDO"
    echo "   Inicia con: ./run_multi_symbol.sh"
fi

# Verificar Trading Engine
ENGINE_PID=$(ps aux | grep "multi_symbol_engine" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$ENGINE_PID" ]; then
    echo "✅ Trading Engine: ACTIVO (PID: $ENGINE_PID)"
    
    # Verificar hace cuánto está corriendo
    UPTIME=$(ps -o etime= -p $ENGINE_PID | tr -d ' ')
    echo "   Tiempo activo: $UPTIME"
else
    echo "❌ Trading Engine: NO ESTÁ CORRIENDO"
fi

# Verificar puerto ZeroMQ
echo ""
echo "🔌 Puerto ZeroMQ (5555):"
ZMQ_CHECK=$(lsof -i :5555 2>/dev/null | grep -v COMMAND)
if [ -n "$ZMQ_CHECK" ]; then
    echo "✅ Puerto en uso (normal si feed está corriendo)"
    echo "$ZMQ_CHECK"
else
    echo "❌ Puerto libre (feed handler no está activo)"
fi

echo ""
echo "════════════════════════════════════════"
echo ""

# Resumen
if [ -n "$FEED_PID" ] && [ -n "$ENGINE_PID" ]; then
    echo "🎯 SISTEMA OPERATIVO"
    echo ""
    echo "El bot está escuchando y esperando señales."
    echo ""
    echo "Para ver logs en vivo:"
    echo "  tail -f /proc/$ENGINE_PID/fd/2"
    echo ""
    echo "O usa:"
    echo "  ./ver_logs.sh"
elif [ -z "$FEED_PID" ] && [ -z "$ENGINE_PID" ]; then
    echo "⚠️ SISTEMA DETENIDO"
    echo ""
    echo "Para iniciar el bot:"
    echo "  ./run_multi_symbol.sh"
else
    echo "⚠️ SISTEMA PARCIAL"
    echo ""
    echo "Solo uno de los componentes está corriendo."
    echo "Detén todo y reinicia:"
    echo "  pkill -f 'feed_handler|multi_symbol'"
    echo "  ./run_multi_symbol.sh"
fi

echo "════════════════════════════════════════"
