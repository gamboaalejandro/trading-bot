#!/bin/bash
# Run Metrics Collector with full logging

export PYTHONPATH=/home/alejandrog/Desktop/trading-bot

echo "=========================================="
echo "Starting Metrics Collector"
echo "=========================================="
echo ""

./venv/bin/python3 apps/dashboard/metrics_collector.py
