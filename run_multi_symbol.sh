#!/bin/bash

# Multi-Symbol Trading Bot - Dry Run Mode
# Runs the bot in simulation mode (no real trades)

echo "========================================"
echo "MULTI-SYMBOL TRADING BOT - DRY RUN MODE"
echo "========================================"
echo ""
echo "Trading Pairs: BTC/USDT, ETH/USDT, SOL/USDT"
echo "Mode: SIMULATION (DRY_RUN=true)"
echo ""
echo "This will:"
echo "  1. Start Multi-Symbol Feed Handler (ZeroMQ)"
echo "  2. Start Multi-Symbol Trading Engine"
echo "  3. Process signals for 3 pairs simultaneously"
echo "  4. NOT execute real trades (simulation only)"
echo ""
echo "Press Ctrl+C to stop"
echo "========================================"
echo

# Activate virtual environment
# source venv/Scripts/activate

# Force simulation: TRADING_MODE is authoritative (live also needs
# LIVE_TRADING_CONFIRM=I_UNDERSTAND and 1m profiles need ALLOW_1M_LIVE=true)
export TRADING_MODE=dry_run
export DRY_RUN=true

# Run orchestrator
python3 orchestrator.py
