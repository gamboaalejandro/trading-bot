# PowerShell script to run the trading bot with proper environment
# Usage: .\run_bot.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MULTI-SYMBOL TRADING BOT - DRY RUN MODE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Trading Pairs: BTC/USDT, ETH/USDT, SOL/USDT" -ForegroundColor Green
Write-Host "Mode: SIMULATION (DRY_RUN=true)" -ForegroundColor Green
Write-Host ""
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Start Multi-Symbol Feed Handler (ZeroMQ)" -ForegroundColor Yellow
Write-Host "  2. Start Multi-Symbol Trading Engine" -ForegroundColor Yellow
Write-Host "  3. Process signals for 3 pairs simultaneously" -ForegroundColor Yellow
Write-Host "  4. NOT execute real trades (simulation only)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get project root directory
$PROJECT_ROOT = $PSScriptRoot

# Set PYTHONPATH to include project root
$env:PYTHONPATH = $PROJECT_ROOT

Write-Host "Setting PYTHONPATH to: $PROJECT_ROOT" -ForegroundColor Gray
Write-Host ""

# Check if virtual environment exists
$VENV_PYTHON = Join-Path $PROJECT_ROOT "venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: python -m venv venv" -ForegroundColor Yellow
    Write-Host "Then: .\venv\Scripts\activate" -ForegroundColor Yellow
    Write-Host "Then: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment (set environment variables)
$VENV_DIR = Join-Path $PROJECT_ROOT "venv"
$env:VIRTUAL_ENV = $VENV_DIR
$env:PATH = "$VENV_DIR\Scripts;$env:PATH"

Write-Host "Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Run orchestrator
try {
    & $VENV_PYTHON (Join-Path $PROJECT_ROOT "orchestrator.py")
}
catch {
    Write-Host "ERROR: Failed to start trading bot" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
