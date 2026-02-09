#!/bin/bash

# Script para dar permisos de ejecución a todos los scripts de ejemplo
chmod +x examples/*.py

echo " Scripts de ejemplo listos para usar:"
echo ""
echo "1. Ver estado de cuenta:"
echo "   python3 examples/check_status.py"
echo ""
echo "2. Abrir primera posición (con confirmación):"
echo "   python3 examples/open_first_position.py"
echo ""
echo "3. Cerrar posiciones:"
echo "   python3 examples/close_position.py BTC/USDT  # Específica"
echo "   python3 examples/close_position.py           # Todas"
echo ""
echo "4. Trading engine completo (automático):"
echo "   ./run_trading_engine.sh"
echo ""
