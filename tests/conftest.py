import os
import sys
from pathlib import Path

# Settings require keys at import time; tests never hit the network
os.environ.setdefault("BINANCE_API_KEY", "test")
os.environ.setdefault("BINANCE_SECRET", "test")
os.environ.setdefault("DRY_RUN", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
