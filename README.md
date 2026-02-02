# QuantMind-Alpha

**QuantMind-Alpha** is a high-frequency trading (HFT) bot built with **event-driven architecture** for ultra-low latency. It uses ZeroMQ for inter-process communication and supports multiple trading strategies with RL-based meta-learning.

## 🏗️ Architecture

### Event-Driven Design (Low Latency)
```
Binance WebSocket → Feed Handler → ZMQ PUB (5555)
                                      ↓
                            [Market Data Stream]
                                      ↓
                    ┌─────────────────┼─────────────┐
                    ▼                 ▼             ▼
              Metrics Collector  Strategy 1   Strategy N
                    ↓
               Redis Cache
                    ↓
              Dashboard API ←─── Browser (WebSocket)
```

### Components
- **apps/ingestion**: WebSocket daemon publishing real-time data via ZeroMQ
- **apps/dashboard**: FastAPI + WebSocket for live monitoring
- **apps/brain**: AI strategies (future: RL meta-agent)
- **apps/executor**: Risk management + order execution
- **core**: Shared config, security, database utilities

## 🚀 Quick Start

See **[Getting Started Guide](getting_started.md)** for detailed instructions.

**TL;DR**:
```bash
# 1. Setup
cp .env.example .env
# Edit .env with your Binance API keys

# 2. Install
pip install -r requirements.txt

# 3. Start
./start.sh

# 4. Open browser
http://localhost:8000
```

## 📊 Features

- ✅ **Ultra-low latency** (<10ms internal messaging with ZeroMQ)
- ✅ **Real-time monitoring** via WebSocket dashboard
- ✅ **Event-driven** architecture (no HTTP polling)
- ✅ **Modular design** (strategies as independent subscribers)
- ✅ **Risk management** (Kelly Criterion + ATR Stop Loss)
- ✅ **Production-ready** with process orchestration

## 📦 Tech Stack

| Component | Technology |
|-----------|------------|
| Messaging | ZeroMQ (PUB/SUB) |
| Async Runtime | uvloop + asyncio |
| Exchange API | CCXT (WebSocket support) |
| Dashboard | FastAPI + WebSocket |
| Cache | Redis |
| Serialization | MessagePack |

## 🎯 Strategies & Risk Management

### Risk Management (Kelly Core)
The `apps/executor/risk_manager.py` implements:
1. **Kelly Criterion**: Dynamic position sizing based on win-rate and risk/reward
2. **ATR Stop Loss**: Volatility-adjusted stop losses

### Trading Strategies
- **Momentum**: Trend-following based on price momentum
- **Mean Reversion**: Bollinger Bands strategy
- **ML-Based**: LSTM predictions (future)
- **RL Meta-Agent**: Combines multiple strategies (future)

## 📚 Documentation

- [Architecture Guide](architecture_guide.md) - System design and data flow
- [Getting Started](getting_started.md) - Setup and deployment
- [Implementation Plan](implementation_plan.md) - Development roadmap

## 🔒 Security
- API keys managed via `pydantic-settings`
- Environment variables in `.env` (gitignored)
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

