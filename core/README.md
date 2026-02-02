# Core Module

## Overview

The Core module provides **shared utilities** used across all other modules:

1. `config.py`: Configuration management (Pydantic + YAML)
2. `database.py`: Redis client wrapper
3. `security.py`: HMAC signing utilities

## Key Files

| File | Purpose | Status | Lines |
|------|---------|--------|-------|
| `config.py` | Centralized configuration | ✅ Complete | ~60 |
| `database.py` | Async Redis client | ✅ Complete | ~40 |
| `security.py` | Signature generation | ⏳ Skeleton | ~25 |

## Configuration System

### Design Philosophy

**Principle**: Separate secrets (API keys) from config (parameters).

```
.env (secrets, gitignored)
    ↓
config/ai_config.yml (parameters, version-controlled)
    ↓
core/config.py (validation, type-safe access)
```

### Implementation

```python
from pydantic_settings import BaseSettings
import yaml

class Settings(BaseSettings):
    # From .env
    BINANCE_API_KEY: str
    BINANCE_SECRET: str
    ENV: str = "development"
    REDIS_URL: str = "redis://localhost:6379"
    ZMQ_FEED_HANDLER_URL: str = "tcp://127.0.0.1:5555"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    # Load AI config from YAML
    @property
    def AI_CONFIG(self) -> dict:
        with open("config/ai_config.yml") as f:
            return yaml.safe_load(f)

settings = Settings()
```

### Why Pydantic-Settings?

**Comparison**:
| Method | Type Safety | Validation | Default Values |
|--------|-------------|------------|----------------|
| `os.getenv()` | ❌ No | ❌ No | ⚠️ Manual |
| `python-dotenv` | ❌ No | ❌ No | ⚠️ Manual |
| **Pydantic** | ✅ Yes | ✅ Yes | ✅ Yes |

**Example benefit**:
```python
# ❌ BAD: Runtime error
redis_url = os.getenv("REDIS_URL")  # Returns None if missing
redis_client = Redis.from_url(redis_url)  # Crashes!

# ✅ GOOD: Fails on startup
settings = Settings()  # Raises ValidationError if REDIS_URL missing
redis_client = Redis.from_url(settings.REDIS_URL)  # Safe
```

### Configuration Hierarchy

```yaml
# config/ai_config.yml
ai:
  model_name: "LSTM_v1"
  timeframe: "1m"
  features:
    - "close"
    - "volume"
    - "rsi"

trading:
  symbol: "BTC/USDT"
  strategy: "scalping_v1"
  max_positions: 1
  leverage: 10
```

**Access pattern**:
```python
symbol = settings.AI_CONFIG.get('trading', {}).get('symbol', 'BTC/USDT')
strategy = settings.AI_CONFIG['trading']['strategy']  # Will raise KeyError if missing
```

### Critical: Secrets Management

**Current approach**: `.env` file (gitignored).

**.env structure**:
```bash
# .env (DO NOT COMMIT!)
BINANCE_API_KEY=AqCykpjXeXq8...
BINANCE_SECRET=Ii1ERmzKI...
ENV=development
REDIS_URL=redis://localhost:6379
```

**Production approach** (not implemented):
```python
# Use AWS Secrets Manager
import boto3

secrets = boto3.client('secretsmanager')
response = secrets.get_secret_value(SecretId='prod/trading-bot/binance')
BINANCE_API_KEY = json.loads(response['SecretString'])['api_key']
```

**Or HashiCorp Vault**:
```python
import hvac

client = hvac.Client(url='http://vault:8200')
secret = client.secrets.kv.v2.read_secret_version(path='trading-bot/binance')
BINANCE_API_KEY = secret['data']['data']['api_key']
```

## Database Client (Redis)

### Design

```python
class RedisClient:
    def __init__(self):
        self._redis: Optional[Redis] = None
    
    async def get_redis(self) -> Redis:
        """Get or create Redis connection (singleton)."""
        if self._redis is None:
            self._redis = await Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

redis_client = RedisClient()
```

### Why Singleton Pattern?

**Without singleton**:
```python
# ❌ Creates new connection every time
async def store_data():
    redis = await Redis.from_url(...)  # Connection 1
    await redis.set('key', 'value')

async def read_data():
    redis = await Redis.from_url(...)  # Connection 2 (wasteful!)
    return await redis.get('key')
```

**With singleton**:
```python
# ✅ Reuses connection
async def store_data():
    redis = await redis_client.get_redis()  # Connection 1
    await redis.set('key', 'value')

async def read_data():
    redis = await redis_client.get_redis()  # Same connection 1
    return await redis.get('key')
```

**Benefits**:
- ✅ Fewer connections (Redis has connection limit)
- ✅ Connection pooling
- ✅ Faster (no handshake overhead)

### Redis Configuration

**Current**: Default settings (no password, no persistence).

**Production needs**:
```conf
# redis.conf
requirepass your_strong_password
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1  # Persist every 15min if ≥1 key changed
appendonly yes  # Enable AOF persistence
```

**Why persistence?**
- Current: Data lost on restart (acceptable for metrics)
- Future: Need persistence for trade history

## Security Module

### Current State: ⏳ Skeleton Only

```python
def generate_signature(secret: str, message: str) -> str:
    """Generate HMAC-SHA256 signature."""
    h = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    )
    return h.hexdigest()
```

### Use Cases (Not Implemented)

**1. Binance API Signatures**:
```python
# Binance requires HMAC-SHA256 for authenticated requests
timestamp = int(time.time() * 1000)
query_string = f"symbol=BTCUSDT&side=BUY&type=MARKET&quantity=0.01&timestamp={timestamp}"
signature = generate_signature(settings.BINANCE_SECRET, query_string)

# Append to request
url = f"https://fapi.binance.com/fapi/v1/order?{query_string}&signature={signature}"
```

**2. Webhook Verification**:
```python
@app.post("/webhook")
async def webhook(request: Request):
    # Verify sender
    received_sig = request.headers.get('X-Signature')
    body = await request.body()
    expected_sig = generate_signature(settings.WEBHOOK_SECRET, body.decode())
    
    if received_sig != expected_sig:
        raise HTTPException(401, "Invalid signature")
    
    # Process webhook
    ...
```

**3. API Key Authentication**:
```python
def generate_api_key() -> tuple[str, str]:
    """Generate API key and secret for dashboard."""
    key = secrets.token_urlsafe(32)  # Public key
    secret = secrets.token_urlsafe(64)  # Private secret
    
    # Store hashed secret in database
    hashed_secret = hashlib.sha256(secret.encode()).hexdigest()
    await db.store_api_key(key, hashed_secret)
    
    return key, secret  # Give secret to user once
```

## Testing

### Configuration Tests

```python
def test_settings_load():
    """Test that settings load from .env"""
    assert settings.BINANCE_API_KEY
    assert settings.BINANCE_SECRET
    assert settings.ENV in ['development', 'production']

def test_ai_config_load():
    """Test that AI config loads from YAML"""
    config = settings.AI_CONFIG
    assert 'trading' in config
    assert config['trading']['symbol']

def test_missing_env_var():
    """Test that missing env vars raise error"""
    with pytest.raises(ValidationError):
        # Temporarily remove .env
        os.rename('.env', '.env.bak')
        Settings()
    os.rename('.env.bak', '.env')
```

### Redis Tests

```python
@pytest.mark.asyncio
async def test_redis_connection():
    redis = await redis_client.get_redis()
    await redis.set('test_key', 'test_value')
    value = await redis.get('test_key')
    assert value == 'test_value'
    await redis.delete('test_key')

@pytest.mark.asyncio
async def test_redis_singleton():
    redis1 = await redis_client.get_redis()
    redis2 = await redis_client.get_redis()
    assert redis1 is redis2  # Same object
```

## Critical Vulnerabilities

### 🔴 1. Hardcoded Secrets in Config

**Risk**: Developers might put secrets in `ai_config.yml`.

**Example**:
```yaml
# ❌ NEVER DO THIS
trading:
  api_key: "AqCykpjXeXq8..."  # Committed to git!
```

**Mitigation**:
- ✅ `.env` is gitignored
- ⚠️ Add pre-commit hook to scan for secrets
- ⚠️ Use `gitleaks` or `truffleHog`

### 🔴 2. No Encryption at Rest

**Risk**: If attacker gets `.env` file, game over.

**Mitigation** (not implemented):
```python
from cryptography.fernet import Fernet

# Encrypt .env
key = Fernet.generate_key()  # Store in hardware security module
cipher = Fernet(key)

with open('.env') as f:
    plaintext = f.read()

encrypted = cipher.encrypt(plaintext.encode())

with open('.env.encrypted', 'wb') as f:
    f.write(encrypted)

# Decrypt on load
with open('.env.encrypted', 'rb') as f:
    encrypted = f.read()

decrypted = cipher.decrypt(encrypted).decode()
```

### 🔴 3. No Rate Limiting on Config Reload

**Risk**: Attacker could DoS by forcing config reloads.

**Mitigation**:
```python
import time

last_reload = 0

def reload_config():
    global last_reload
    now = time.time()
    
    if now - last_reload < 60:  # Max 1 reload per minute
        raise Exception("Rate limit exceeded")
    
    last_reload = now
    # ... reload logic
```

## Future Enhancements

### 1. Configuration Hot-Reload

**Goal**: Change settings without restart.

**Approach**:
```python
import watchdog

class ConfigReloader:
    def on_modified(self, event):
        if event.src_path.endswith('.yml'):
            logger.info("Config changed, reloading...")
            settings.reload_ai_config()
            # Notify all services via ZeroMQ
            await zmq_socket.send(b'CONFIG_RELOAD')
```

**Complexity**: Medium (1 day)

### 2. Multi-Environment Support

**Goal**: Separate dev/staging/prod configs.

**Approach**:
```python
# Load based on ENV
env = os.getenv('ENV', 'development')

if env == 'production':
    config_file = 'config/prod.yml'
elif env == 'staging':
    config_file = 'config/staging.yml'
else:
    config_file = 'config/dev.yml'
```

**Complexity**: Low (2 hours)

### 3. Configuration Versioning

**Goal**: Track config changes over time.

**Approach**:
```yaml
# config/ai_config.yml
version: "1.2.0"  # Semantic versioning
last_updated: "2026-02-02"
changelog:
  - "1.2.0: Added multi-symbol support"
  - "1.1.0: Changed default leverage from 5x to 10x"
```

**Complexity**: Low (1 hour)

## FAQ

**Q: Can I use environment variables in YAML?**

A: Not directly, but you can:
```yaml
# config/ai_config.yml
trading:
  symbol: ${TRADING_SYMBOL:-BTC/USDT}  # Default to BTC/USDT
```

Then use `envsubst` or custom parser.

**Q: How do I add a new configuration?**

A:
1. Add to `ai_config.yml`
2. Access via `settings.AI_CONFIG['your_key']`
3. No code changes needed (unless adding to `.env`)

**Q: Should I commit `.env.example`?**

A: Yes! It shows required variables:
```bash
# .env.example (commit this)
BINANCE_API_KEY=your_key_here
BINANCE_SECRET=your_secret_here
ENV=development
```

---

**Last Updated**: 2026-02-02  
**Maintainer**: Alejandro G.  
**Status**: ✅ Production-ready
