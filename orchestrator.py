"""
Orchestrator - Manages all system processes
"""
import asyncio
import subprocess
import signal
import sys
import logging
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
    
    def start_process(self, name: str, command: List[str]):
        """Start a subprocess."""
        logger.info(f"Starting {name}...")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
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
    
    logger.info("=" * 60)
    logger.info("QuantMind-Alpha Orchestrator")
    logger.info("=" * 60)
    
    # Start Feed Handler
    manager.start_process(
        "Feed Handler",
        ["python", "apps/ingestion/feed_handler_daemon.py"]
    )
    await asyncio.sleep(2)  # Wait for initialization
    
    # Start Metrics Collector
    manager.start_process(
        "Metrics Collector",
        ["python", "apps/dashboard/metrics_collector.py"]
    )
    await asyncio.sleep(1)
    
    # Start Dashboard API
    manager.start_process(
        "Dashboard API",
        ["uvicorn", "apps.dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
    )
    
    logger.info("=" * 60)
    logger.info("All services started!")
    logger.info("Dashboard: http://localhost:8000")
    logger.info("Press Ctrl+C to stop all services")
    logger.info("=" * 60)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
            # Check if any process died
            for process in manager.processes:
                if process.poll() is not None:
                    logger.error(f"Process {process.pid} died unexpectedly!")
    except KeyboardInterrupt:
        manager.stop_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped")
