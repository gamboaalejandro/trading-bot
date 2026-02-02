#!/bin/bash
# Run Dashboard API with full logging

export PYTHONPATH=/home/alejandrog/Desktop/trading-bot

echo "=========================================="
echo "Starting Dashboard API (Port 8000)"
echo "=========================================="
echo ""

./venv/bin/uvicorn apps.dashboard.main:app --host 0.0.0.0 --port 8000 --log-level debug
