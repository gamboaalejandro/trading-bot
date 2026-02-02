#!/bin/bash
# Quick status check

export PYTHONPATH=/home/alejandrog/Desktop/trading-bot

echo "========================================"
echo "QuantMind-Alpha Status Check"
echo "========================================"
echo ""

# Check processes
echo "1. Running Processes:"
if ps aux | grep -E "feed_handler_daemon" | grep -v grep > /dev/null; then
    echo "   ✅ Feed Handler is running"
else
    echo "   ❌ Feed Handler NOT running"
    echo "      Start with: ./run_feed_handler.sh"
fi

if ps aux | grep -E "metrics_collector" | grep -v grep > /dev/null; then
    echo "   ✅ Metrics Collector is running"
else
    echo "   ❌ Metrics Collector NOT running"
    echo "      Start with: ./run_metrics_collector.sh"
fi

if ps aux | grep -E "uvicorn.*dashboard" | grep -v grep > /dev/null; then
    echo "   ✅ Dashboard API is running"
else
    echo "   ❌ Dashboard API NOT running"
    echo "      Start with: ./run_dashboard.sh"
fi

echo ""

# Check ports
echo "2. Listening Ports:"
if lsof -i :5555 > /dev/null 2>&1; then
    echo "   ✅ Port 5555 (Feed Handler) is active"
else
    echo "   ❌ Port 5555 NOT listening"
fi

if lsof -i :8000 > /dev/null 2>&1; then
    echo "   ✅ Port 8000 (Dashboard) is active"
else
    echo "   ❌ Port 8000 NOT listening"
fi

echo ""

# Check Redis
echo "3. Redis Status:"
if sudo docker ps | grep -q quantmind_redis; then
    echo "   ✅ Redis container running"
    
    # Check for data
    KEY_COUNT=$(sudo docker exec quantmind_redis redis-cli DBSIZE 2>/dev/null | grep -oP '\d+')
    if [ "$KEY_COUNT" -gt 0 ]; then
        echo "   ✅ Redis has $KEY_COUNT keys"
        echo ""
        echo "   Sample keys:"
        sudo docker exec quantmind_redis redis-cli KEYS "*" 2>/dev/null | head -5
    else
        echo "   ⚠️  Redis is EMPTY (no data)"
        echo "      This means Metrics Collector is not writing data"
    fi
else
    echo "   ❌ Redis NOT running"
    echo "      Start with: sudo docker compose up -d redis"
fi

echo ""
echo "========================================"
echo "Quick Fix:"
echo "========================================"
echo "If services are not running, execute in separate terminals:"
echo ""
echo "Terminal 1: ./run_feed_handler.sh"
echo "Terminal 2: ./run_metrics_collector.sh"  
echo "Terminal 3: ./run_dashboard.sh"
echo ""
