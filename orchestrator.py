"""
Trading Bot Orchestrator

Manages the lifecycle of all trading bot services:
- Feed Handler: ZeroMQ data feed from Binance WebSocket
- Trading Engine: Main trading logic and execution

Usage:
    python3 orchestrator.py

This will start both services and monitor them.
Press Ctrl+C to gracefully shutdown all services.
"""
import asyncio
import subprocess
import signal
import sys
import logging
import os
from typing import List
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get Python interpreter (system or venv)
PYTHON_CMD = sys.executable

class ProcessManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        # Set PYTHONPATH to include project root
        self.env = os.environ.copy()
        project_root = str(Path(__file__).parent)
        self.env['PYTHONPATH'] = project_root
    
    def start_process(self, name: str, command: List[str]):
        """Start a subprocess."""
        logger.info(f"Starting {name}...")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env  # Pass environment with PYTHONPATH
        )
        self.processes.append(process)
        logger.info(f"{name} started (PID: {process.pid})")
        return process
    
    def stop_all(self):
        """Stop all processes."""
        logger.info("Stopping all processes...")
        for process in self.processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        logger.info("All processes stopped")

def signal_handler(sig, frame, manager: ProcessManager):
    """Handle shutdown signals."""
    logger.info("\nReceived shutdown signal...")
    manager.stop_all()
    sys.exit(0)

async def main():
    manager = ProcessManager()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, manager))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, manager))
    
    logger.info("="*60)
    logger.info("MULTI-SYMBOL TRADING BOT ORCHESTRATOR")
    logger.info("="*60)
    logger.info("Starting services...")
    logger.info("")
    
    # 1. Start Multi-Symbol Feed Handler (ZeroMQ Publisher)
    feed_handler = manager.start_process(
        "Multi-Symbol Feed Handler",
        [PYTHON_CMD, "-m", "apps.ingestion.feed_handler_daemon"]
    )
    
    # Wait for feed handler to initialize
    logger.info("Waiting 3 seconds for feed handler to initialize...")
    await asyncio.sleep(3)
    
    # 2. Start Multi-Symbol Trading Engine (ZeroMQ Subscriber)
    trading_engine = manager.start_process(
        "Multi-Symbol Trading Engine",
        [PYTHON_CMD, "-m", "apps.executor.multi_symbol_engine"]
    )
    
    logger.info("")
    logger.info("="*60)
    logger.info("ALL SERVICES RUNNING")
    logger.info("="*60)
    logger.info(" Multi-Symbol Feed Handler (ZeroMQ Publisher)")
    logger.info(" Multi-Symbol Trading Engine (ZeroMQ Subscriber)")
    logger.info("")
    logger.info("Trading pairs: BTC/USDT, ETH/USDT, SOL/USDT")
    logger.info("")
    logger.info("Press Ctrl+C to stop all services")
    logger.info("="*60)
    
    # Monitor processes
    try:
        while True:
            # Check if any process has died
            for process in manager.processes:
                if process.poll() is not None:
                    logger.error(f"Process {process.pid} died unexpectedly")
                    logger.error("Stderr:")
                    stderr = process.stderr.read() if process.stderr else "N/A"
                    logger.error(stderr)
                    manager.stop_all()
                    sys.exit(1)
            
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        manager.stop_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped")
