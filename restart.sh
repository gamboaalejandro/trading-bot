#!/bin/bash
# Script Rápido de Reinicio Completo

echo " Deteniendo todo..."
kill_process() {
    ps aux | grep "$1" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null
}

kill_process "orchestrator"
kill_process "feed_handler"
kill_process "multi_symbol"

sleep 2

echo "️  Limpiando logs viejos..."
> logs/trading_engine.log
> logs/pnl_tracker.log

echo " Iniciando sistema..."
python3 orchestrator.py

echo " Bot reiniciado con logs limpios"
