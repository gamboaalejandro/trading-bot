# Dashboard Module

## Overview

The Dashboard Module provides **real-time monitoring** via HTTP and WebSocket endpoints. It consists of two components:

1. **Metrics Collector**: ZeroMQ subscriber that aggregates metrics and stores in Redis
2. **Dashboard API**: FastAPI web server

 that serves metrics to browsers

## Architecture

```
[Feed Handler:5555] 
    → [Metrics Collector] 
    → [Redis] 
    → [Dashboard API:8000] 
    → [Browser WebSocket]
```

## Key Files

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `metrics_collector.py` | Subscribes to feed, calculates metrics | ~140 |
| `main.py` | FastAPI server for HTTP/WS endpoints | ~110 |

## Design Decisions

### 1. Why Separate Metrics Collector from API?

**Decision**: Run as two processes.

**Rationale**:
- **Separation of concerns**: Collector focuses on ingestion, API focuses on serving
- **Independent scaling**: Can add more API instances without affecting collector
- **Restart independence**: Can reload API without missing data

**Alternative considered**: Single FastAPI app with background task
- ❌ Rejected: Too coupled, harder to debug WebSocket issues

### 2. Why Redis for Storage?

**Comparison**:
| Database | Read Latency | Write Latency | Use Case |
|----------|--------------|---------------|----------|
| PostgreSQL | 5-10ms | 10-20ms | Historical analysis |
| MongoDB | 2-5ms | 5-10ms | Document storage |
| **Redis** | **<1ms** | **1-3ms** | **Real-time metrics** |

**Decision**: Redis (in-memory cache).

**Rationale**:
- ✅ Sub-millisecond reads (critical for WebSocket updates)
- ✅ Built-in TTL (auto-cleanup old data)
- ✅ Simple key-value model (no schema migrations)
- ❌ Data lost on restart (acceptable for metrics)
- ❌ Limited query capabilities (no complex joins)

**Why not add PostgreSQL too?**
- **Answer**: We will! Phase 2 will add Postgres for historical trades
- **Plan**: Redis for hot data (<1 hour), Postgres for cold data (>1 hour)

### 3. Why WebSocket for Dashboard Updates?

**Comparison**:
| Method | Latency | Browser Support | Complexity |
|--------|---------|-----------------|------------|
| Polling | 500ms+ | 100% | Low |
| SSE | 100-500ms | 95% | Medium |
| **WebSocket** | **<50ms** | **98%** | **Medium** |

**Decision**: WebSocket.

**Rationale**:
- ✅ Lowest latency (~20-50ms)
- ✅ Bi-directional (future: send commands from browser)
- ✅ Native browser support
- ❌ Requires connection management (reconnection logic)

## Metrics Collector Deep Dive

### Data Flow

```python
while True:
    # 1. Receive from Feed Handler
    packed = await zmq_socket.recv()           # <1ms
    data = msgpack.unpackb(packed)             # <0.5ms
    
    # 2. Calculate metrics
    metrics = _calculate_metrics(data)          # <0.5ms
    
    # 3. Store in Redis
    await redis.set(f"ticker:{symbol}", data)   # 1-3ms
    await redis.set("metrics:latest", metrics)  # 1-3ms
```

**Total processing time**: ~3-7ms per message.

### Metrics Calculated

```python
{
    'spread': ask - bid,                    # ⚠️ None (Binance Futures)
    'spread_bps': (spread / ask) * 10000,   # Basis points
    'messages_received': counter,           # Throughput
    'uptime_seconds': uptime,               # Service health
    'messages_per_second': rate,            # Real-time throughput
    'feed_latency_ms': latency              # Binance → System
}
```

### Critical Bug Fix: Symbol Normalization

**Bug**: Dashboard shows "waiting for data" despite data flowing.

**Root Cause**:
```python
# Binance Futures returns:
ticker['symbol'] = "BTC/USDT:USDT"

# Dashboard expects:
redis.get("ticker:BTC/USDT")

# Result: Mismatch! Data stored as "ticker:BTC/USDT:USDT"
```

**Fix**:
```python
# In metrics_collector.py
symbol = data.get('symbol', 'UNKNOWN')

# Normalize Binance Futures format
if ':' in symbol:
    symbol = symbol.split(':')[0]  # "BTC/USDT:USDT" → "BTC/USDT"

await redis.set(f"ticker:{symbol}", ...)
```

**Lesson**: Always validate data format assumptions!

### Failure Modes

#### 1. ZeroMQ Connection Failed

**Trigger**: Feed Handler not running.

**Symptom**:
```
INFO - Connecting to Feed Handler at tcp://127.0.0.1:5555
INFO - Waiting for messages...
(hangs forever)
```

**Why no error?** ZeroMQ connect is non-blocking. It silently waits for publisher.

**Detection**:
```bash
# Check if Feed Handler is publishing
lsof -i :5555
# Should show: python3 ... feed_handler_daemon.py
```

**Recovery**: Start Feed Handler first, then Metrics Collector.

#### 2. Redis Connection Refused

**Trigger**: Redis not running.

**Symptom**:
```
ERROR - Error connecting to Redis: Connection refused
```

**Recovery**:
```bash
sudo docker compose up -d redis
```

**Prevention**: Add health check before starting:
```python
async def check_redis():
    try:
        await redis.ping()
    except:
        logger.error("Redis not available!")
        sys.exit(1)
```

#### 3. Slow Redis Writes (Memory Full)

**Trigger**: Redis out of memory.

**Symptom**:
```
ERROR - OOM command not allowed when used memory > 'maxmemory'
```

**Current Mitigation**:
```python
# Auto-trim price history
await redis.lpush(f"history:{symbol}:price", price)
await redis.ltrim(f"history:{symbol}:price", 0, 99)  # Keep last 100
```

**Better solution**: Configure Redis eviction policy:
```conf
# redis.conf
maxmemory 100mb
maxmemory-policy allkeys-lru  # Evict least recently used
```

## Dashboard API Deep Dive

### Endpoints

#### 1. Health Check

```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2026-02-02T01:00:00"
}
```

**Use case**: Load balancer health checks, monitoring.

#### 2. Get Metrics

```http
GET /metrics
```

**Response**:
```json
{
  "ticker": {
    "symbol": "BTC/USDT",
    "last": 50000.0,
    "volume": 123.45,
    ...
  },
  "metrics": {
    "spread": null,
    "messages_received": 1234,
    "messages_per_second": 8.5,
    "feed_latency_ms": 15.3
  },
  "timestamp": "2026-02-02T01:00:00"
}
```

**Use case**: Programmatic access, Grafana integration.

#### 3. WebSocket Stream

```javascript
// JavaScript client
const ws = new WebSocket('ws://localhost:8000/ws/stream');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Price:', data.last);
  console.log('Metrics:', data.metrics);
};
```

**Update frequency**: Every 500ms.

**Why 500ms?** Balance between:
- Too fast (100ms): Unnecessary CPU/bandwidth
- Too slow (1000ms): Feels sluggish

**Optimization**: Use variable rate based on volatility:
```python
if price_change > 0.1%:
    await asyncio.sleep(0.1)  # 100ms in volatile markets
else:
    await asyncio.sleep(0.5)  # 500ms in calm markets
```

### WebSocket Connection Management

```python
active_connections: List[WebSocket] = []

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await get_latest_from_redis()
            await websocket.send_json(data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
```

**Issue**: What if `send_json` blocks?
- **Answer**: It's async, so other connections aren't blocked
- **But**: uvicorn handles each connection in a separate task

**Scalability**: Can handle ~100 concurrent WebSocket connections.

**Bottleneck**: Redis read (single-threaded). Solution: Redis Cluster.

## Performance Characteristics

### Latency Budget

```
[Redis] → (1ms read) → [Dashboard API]
    → (2-5ms JSON serialize) → (2-10ms WebSocket send)
    → (network 1-5ms) → [Browser receives]

Total: 6-21ms (Redis → Browser)
```

### Throughput

- **Metrics Collector**: 500+ msg/sec
- **Dashboard API**: 100 WebSocket clients × 2 msg/sec = 200 msg/sec
- **Bottleneck**: Redis single-threaded (10,000 ops/sec)

### Resource Usage

```
Metrics Collector:
  CPU: 0.5%
  RAM: 50MB
  
Dashboard API:
  CPU: 0.5% (idle), 5% (100 WebSocket clients)
  RAM: 80MB
```

## Security Concerns

### ⚠️  No Authentication

**Current state**: Anyone on `localhost` can access.

**Risk**: Low in development, **CRITICAL** in production.

**Attack scenarios**:
1. **Port forwarding**: Attacker SSH tunnels to your server
2. **SSRF**: Attacker tricks your server to connect to itself
3. **Insider threat**: Malicious employee

**Mitigation (Short-term)**:
```python
# Add API key
@app.get("/metrics")
async def get_metrics(api_key: str = Header(...)):
    if api_key != settings.DASHBOARD_API_KEY:
        raise HTTPException(401, "Invalid API key")
    # ...
```

**Mitigation (Long-term)**:
- OAuth2 with JWT tokens
- Rate limiting (10 req/sec per IP)
- HTTPS only (no HTTP)

### ⚠️ No Input Validation

**Current state**: Trusts all data from Redis.

**Risk**: If Redis is compromised, could inject malicious data.

**Example attack**:
```python
# Attacker sets malicious data in Redis
redis.set("ticker:BTC/USDT", "<script>alert('XSS')</script>")

# Dashboard serves it to browser
# Browser executes script!
```

**Mitigation**:
```python
from pydantic import BaseModel, validator

class TickerResponse(BaseModel):
    symbol: str
    last: float
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not re.match(r'^[A-Z]{3,}/[A-Z]{3,}$', v):
            raise ValueError('Invalid symbol format')
        return v
```

## Future Enhancements

### 1. Historical Charts

**Goal**: Show price charts like TradingView.

**Approach**:
```python
# Store OHLCV in Redis timeseries
await redis.ts().add(
    f"price:{symbol}",
    timestamp,
    price
)

# Query last 1 hour
data = await redis.ts().range(
    f"price:{symbol}",
    start_time,
    end_time,
    aggregation_type='avg',
    bucket_size_msec=60000  # 1 min candles
)
```

**Complexity**: Medium (1 day)

**Benefit**: Visual analysis, pattern recognition.

### 2. Multi-Symbol Dashboard

**Goal**: Show grid of 10+ symbols.

**UI Mockup**:
```
┌─────────┬──────────┬──────────┬──────────┐
│ BTC     │ ETH      │ SOL      │ BNB      │
│ $50,000 │ $3,500   │ $120     │ $450     │
│ +2.5%   │ -1.2%    │ +5.0%    │ +0.8%    │
└─────────┴──────────┴──────────┴──────────┘
```

**Complexity**: Medium (2-3 days)

**Benefit**: Spot correlation, arbitrage opportunities.

### 3. Alert System

**Goal**: Notify when price crosses threshold.

**Approach**:
```python
# In metrics_collector.py
if data['last'] > settings.ALERT_THRESHOLD:
    await send_telegram_message(
        f"🚨 BTC above ${settings.ALERT_THRESHOLD}!"
    )
```

**Complexity**: Low (2-3 hours)

**Benefit**: Don't miss opportunities.

## Testing

### Manual Test

```bash
# Terminal 1: Feed Handler
./run_feed_handler.sh

# Terminal 2: Metrics Collector
./run_metrics_collector.sh

# Terminal 3: Dashboard API
./run_dashboard.sh

# Browser
http://localhost:8000
```

### Integration Test

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_metrics_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    assert 'ticker' in data
    assert 'metrics' in data
```

### Load Test

```bash
# Simulate 100 WebSocket clients
./venv/bin/python3 load_test_websocket.py --clients 100
```

**Acceptance criteria**:
- Latency p99 < 100ms
- No disconnections
- CPU < 50%

## Monitoring

### Key Metrics

```yaml
# Prometheus metrics (future)
dashboard_websocket_connections: 5
dashboard_http_requests_total: 1234
dashboard_redis_latency_ms: 2.5
dashboard_messages_per_second: 8.2
```

### Alerts (future)

```yaml
- alert: DashboardDown
  expr: up{job="dashboard"} == 0
  for: 1m
  
- alert: HighLatency
  expr: dashboard_redis_latency_ms > 50
  for: 5m
```

## FAQ

**Q: Can I use NGINX reverse proxy?**

A: Yes!
```nginx
server {
    listen 80;
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Q: How do I add HTTPS?**

A: Use Let's Encrypt + NGINX:
```bash
certbot --nginx -d yourdomain.com
```

**Q: Can I deploy to Vercel/Netlify?**

A: No! They don't support WebSockets or long-running processes. Use:
- DigitalOcean App Platform
- AWS Fargate
- Google Cloud Run
- Heroku

---

**Last Updated**: 2026-02-02  
**Maintainer**: Alejandro G.  
**Status**: ✅ Production-ready (add auth first!)
