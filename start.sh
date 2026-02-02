#!/bin/bash
# Quick start script for QuantMind-Alpha

echo "======================================"
echo " QuantMind-Alpha - Quick Start"
echo "======================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found!"
    echo "Please copy .env.example to .env and add your Binance API keys"
    exit 1
fi

# Start Redis if not running
if ! sudo docker ps | grep -q quantmind_redis; then
    echo "Starting Redis..."
    sudo docker compose up -d redis
    sleep 2
fi

# Start the orchestrator
echo "Starting QuantMind-Alpha..."
python3 orchestrator.py
