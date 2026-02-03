#!/bin/bash
# Launch Trading Engine

# Activate virtual environment
source venv/bin/activate

# Default to DRY RUN mode for safety
export DRY_RUN=${DRY_RUN:-true}
export USE_TESTNET=${USE_TESTNET:-true}

echo "=================================================="
echo "  QuantMind-Alpha Trading Engine"
echo "=================================================="
echo "DRY RUN: $DRY_RUN"
echo "TESTNET: $USE_TESTNET"
echo "=================================================="
echo ""

# Run trading engine
python apps/executor/trading_engine.py
