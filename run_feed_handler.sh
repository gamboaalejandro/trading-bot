#!/bin/bash
# Run Feed Handler with full logging

export PYTHONPATH=/home/alejandrog/Desktop/trading-bot

echo "=========================================="
echo "Starting Feed Handler (Port 5555)"
echo "=========================================="
echo ""

./venv/bin/python3 apps/ingestion/feed_handler_daemon.py
