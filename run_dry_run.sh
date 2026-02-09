#!/bin/bash
# Script simple para ejecutar Trading Engine con logs visibles

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         Trading Bot - DRY RUN Mode                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "️  Configuración:"
echo "   - Modo: SIMULACIÓN (DRY_RUN=true)"
echo "   - Testnet: Sí (consultas de balance/precios)"
echo "   - Órdenes: NO se ejecutarán"
echo ""
echo "ℹ️  Verás en tiempo real:"
echo "   - Señales de estrategias (Momentum, Mean Reversion)"
echo "   - Cálculos de position sizing"
echo "   - Operaciones que SE HABRÍAN ejecutado"
echo ""
echo "  Para detener: Presiona Ctrl+C"
echo "════════════════════════════════════════════════════════════"

# Obtener directorio del proyecto (donde está este script)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configurar PYTHONPATH para que Python encuentre los módulos
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Activar entorno virtual si existe
if [ -d "${PROJECT_ROOT}/venv" ]; then
    source "${PROJECT_ROOT}/venv/bin/activate"
fi

# Ejecutar Trading Engine desde el directorio raíz
cd "${PROJECT_ROOT}"
python3 orchestrator.py


