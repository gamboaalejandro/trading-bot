#!/bin/bash
# Diagnostic script to check system status

export PYTHONPATH=/home/alejandrog/Desktop/trading-bot

echo "=========================================="
echo "QuantMind-Alpha System Diagnostics"
echo "=========================================="
echo ""

# Check Redis
echo "1. Checking Redis..."
if sudo docker ps | grep -q quantmind_redis; then
    echo "   ✅ Redis is running"
    sudo docker exec quantmind_redis redis-cli ping 2>&1 | head -1
else
    echo "   ❌ Redis is NOT running"
    echo "   Run: sudo docker compose up -d redis"
fi
echo ""

# Check Python environment
echo "2. Checking Python environment..."
if [ -d "venv" ]; then
    echo "   ✅ Virtual environment exists"
    ./venv/bin/python3 --version
else
    echo "   ❌ Virtual environment NOT found"
fi
echo ""

# Check if modules can be imported
echo "3. Checking module imports..."
./venv/bin/python3 -c "import zmq; import ccxt; import redis; print('   ✅ All modules can be imported')" 2>&1
echo ""

# Check ZMQ port
echo "4. Checking ZMQ port 5555..."
if lsof -i :5555 > /dev/null 2>&1; then
    echo "   ✅ Something is listening on port 5555"
    lsof -i :5555
else
    echo "   ⚠️  Nothing listening on port 5555 (Feed Handler not running)"
fi
echo ""

# Check Dashboard port
echo "5. Checking Dashboard port 8000..."
if lsof -i :8000 > /dev/null 2>&1; then
    echo "   ✅ Something is listening on port 8000"
    lsof -i :8000
else
    echo "   ⚠️  Nothing listening on port 8000 (Dashboard not running)"
fi
echo ""

# Test Binance API credentials
echo "6. Testing Binance API credentials..."
./venv/bin/python3 -c "
from core.config import settings
import ccxt
try:
    exchange = ccxt.binance({
        'apiKey': settings.BINANCE_API_KEY,
        'secret': settings.BINANCE_SECRET
    })
    print('   ✅ API credentials loaded')
    print(f'   API Key: {settings.BINANCE_API_KEY[:10]}...')
except Exception as e:
    print(f'   ❌ Error: {e}')
" 2>&1
echo ""

# Check Redis data
echo "7. Checking Redis data..."
sudo docker exec quantmind_redis redis-cli --scan --pattern "ticker:*" 2>&1 | head -5
echo ""

echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="
