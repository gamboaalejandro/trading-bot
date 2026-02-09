#!/bin/bash

# Script para ver logs en vivo del Multi-Symbol Trading Bot
# Muestra la actividad del bot en tiempo real

echo "========================================"
echo "LOGS EN VIVO - Multi-Symbol Trading Bot"
echo "========================================"
echo ""
echo "Conectando a los logs del sistema..."
echo "Presiona Ctrl+C para salir"
echo ""
echo "========================================"
echo ""

# Función para mostrar logs de un proceso
show_process_logs() {
    local process_name=$1
    local process_id=$(ps aux | grep "$process_name" | grep -v grep | awk '{print $2}' | head -1)
    
    if [ -z "$process_id" ]; then
        echo " Proceso $process_name no está corriendo"
        echo "   Ejecuta primero: ./run_multi_symbol.sh"
        return 1
    fi
    
    echo " Proceso encontrado: $process_name (PID: $process_id)"
    return 0
}

# Verificar que los procesos estén corriendo
if ! show_process_logs "multi_symbol_engine"; then
    echo ""
    echo "Para iniciar el bot ejecuta:"
    echo "  ./run_multi_symbol.sh"
    exit 1
fi

echo ""
echo "Mostrando logs del Trading Engine..."
echo "Esperando señales de trading..."
echo ""
echo "════════════════════════════════════════"
echo ""

# Obtener PID del engine
ENGINE_PID=$(ps aux | grep "multi_symbol_engine" | grep -v grep | awk '{print $2}' | head -1)

echo "Mostrando TODOS los logs (stdout + stderr)..."
echo ""

# Combinar stdout y stderr usando tail con multiples archivos
tail -f /proc/$ENGINE_PID/fd/1 /proc/$ENGINE_PID/fd/2 2>/dev/null || {
    echo " No se pueden leer los logs"
    echo "El proceso puede haber terminado"
}
