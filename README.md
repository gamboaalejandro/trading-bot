# QuantMind-Alpha 🤖💹

> **Event-Driven, Low-Latency Cryptocurrency Trading Bot**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)]()

## 🎯 Overview

QuantMind-Alpha is a **high-frequency trading system** for cryptocurrency futures, built with:
- ⚡ **Sub-10ms internal latency** using ZeroMQ
- 🏗️ **Event-driven architecture** (no polling!)
- 📊 **Real-time monitoring** dashboard
- 🛡️ **Risk management first** (Kelly Criterion, ATR stop loss)
- 🧠 **Designed for AI** (RL meta-agent for strategy fusion)

### Current Status: v0.1-alpha

**✅ Implemented**:
- Real-time market data ingestion (Binance Futures)
- ZeroMQ publish-subscribe messaging
- Redis-backed metrics collection
- WebSocket dashboard
- Risk management framework

**⏳ In Progress**:
- Trading strategies (Momentum, Mean Reversion)
- RL meta-agent
- Live order execution

## 📖 Documentation (200+ Pages)

 | Document | Description |
|----------|-------------|
| **[📚 TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md)** | Complete system breakdown (50+ pages) |
| **[⚠️ RISK_ANALYSIS.md](docs/RISK_ANALYSIS.md)** | All failure points + mitigations (20+ pages) |
| [apps/ingestion/README.md](apps/ingestion/README.md) | Feed Handler deep-dive (40+ pages) |
| [apps/dashboard/README.md](apps/dashboard/README.md) | Dashboard & metrics (35+ pages) |
| [apps/executor/README.md](apps/executor/README.md) | Risk management (30+ pages) |
| [core/README.md](core/README.md) | Core utilities (25+ pages) |
| [debugging_guide.md](docs/debugging_guide.md) | Troubleshooting (15+ pages) |
| [quick_reference.md](docs/quick_reference.md) | Cheat sheet |

## 🚀 Quick Start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit with your Binance API keys
nano .env

# 3. Run setup script
chmod +x start.sh
./start.sh

# 4. Open dashboard
http://localhost:8000
```

- HMAC signing for signal integrity

## 🧪 Development

### Run Tests
```bash
pytest
```

### Manual Testing
```bash
# Test Feed Handler
python apps/ingestion/feed_handler_daemon.py

# Subscribe to stream (in another terminal)
python -c "
import zmq, msgpack
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect('tcp://127.0.0.1:5555')
sock.subscribe(b'')
while True:
    print(msgpack.unpackb(sock.recv(), raw=False))
"
```

## ⚠️ Disclaimer

**THIS IS FOR EDUCATIONAL PURPOSES**. Cryptocurrency trading carries significant risk. Always:
- Test on Binance Testnet first
- Use proper risk management
- Never risk more than you can afford to lose
- Understand the code before deploying

## 📈 Roadmap

- [x] Event-driven architecture with ZeroMQ
- [x] Real-time WebSocket dashboard
- [x] Binance WebSocket integration
- [ ] Multiple trading strategies
- [ ] RL meta-agent for strategy combination
- [ ] Backtesting framework
- [ ] Advanced charting dashboard

