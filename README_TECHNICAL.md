# 📚 Documentación Técnica: Sistema Multi-Par

Guía técnica para desarrolladores del sistema de trading multi-par.

---

## 📐 Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                     Safe List Config                        │
│         (config/safe_list.py)                              │
│  BTC/USDT, ETH/USDT, SOL/USDT + matemáticas específicas   │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
┌────────▼────────┐         ┌────────▼────────┐
│ Feed Handler    │         │ Trading Engine  │
│ (Multi-Symbol)  │────────▶│ (Multi-Symbol)  │
└─────────────────┘  ZeroMQ  └─────────────────┘
         │            Topics         │
         │                           │
    Binance WS                  ┌────▼────┐
    (1 socket)                  │Portfolio│
                                │  Risk   │
                                │ Manager │
                                └─────────┘
```

---

## 🔧 Componentes Clave

### **1. Safe List** ([`config/safe_list.py`](config/safe_list.py))

**Propósito:** Configuración centralizada de qué pares operar y cómo.

**Estructura:**
```python
SAFE_LIST = {
    "SYMBOL/USDT": {
        "enabled": bool,           # Activar/desactivar
        "tier": str,               # STABLE | VOLATILE | MEME
        "strategy": str,           # momentum | mean_reversion
        "leverage": int,
        "max_position_size_usd": float,
        "params": {                # Parámetros estrategia-específicos
            "rsi_period": int,
            "bb_std": float,
            ...
        }
    }
}
```

**Funciones helper:**
```python
from config.safe_list import get_active_symbols, get_symbol_config

symbols = get_active_symbols()  # ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
config = get_symbol_config('BTC/USDT')  # Config dict
```

---

### **2. Multi-Symbol Feed Handler** ([`apps/ingestion/feed_handler_daemon.py`](apps/ingestion/feed_handler_daemon.py))

**Responsabilidad:** Conectar a Binance y publicar precios vía ZeroMQ.

**Características:**
- Usa `watch_tickers()` (plural) para múltiples pares en 1 WebSocket
- Publica con topics: `[symbol, data]`
- Eficiente: 3 pares = 1 conexión (antes: 3 instancias)

**ZeroMQ Publishing:**
```python
# Topic-based: permite filtrar en subscriber
await socket.send_multipart([
    b'BTC/USDT',  # Topic
    msgpack.packb(data)  # Data
])
```

---

### **3. Multi-Symbol Trading Engine** ([`apps/executor/multi_symbol_engine.py`](apps/executor/multi_symbol_engine.py))

**Responsabilidad:** Procesar ticks y ejecutar trades para múltiples pares.

**Arquitectura Event-Driven:**
```python
# Diccionarios de estado por símbolo
self.strategies = {
    'BTC/USDT': StrategyManager(...),
    'ETH/USDT': StrategyManager(...),
    'SOL/USDT': StrategyManager(...)
}

self.candles = {
    'BTC/USDT': DataFrame,
    'ETH/USDT': DataFrame,
    ...
}

# Event loop
while True:
    topic, data = await zmq_socket.recv_multipart()
    symbol = topic.decode()
    await self.on_tick(symbol, data)  # Procesar solo ese par
```

**Factory Pattern:**
```python
# Crea estrategias dinámicamente según safe_list
config = get_symbol_config('BTC/USDT')
if config['strategy'] == 'momentum':
    strategy = MomentumStrategy(**config['params'])
elif config['strategy'] == 'mean_reversion':
    strategy = MeanReversionStrategy(**config['params'])
```

---

### **4. Portfolio Risk Manager** ([`apps/executor/risk_manager.py`](apps/executor/risk_manager.py))

**Responsabilidad:** Control de riesgo a nivel portfolio.

#### **a) Exposición Global**
```python
max_total_exposure = 10%  # del capital total

# Ejemplo:
# BTC posición: $500
# ETH quiere abrir: $600
# Total: $1100
# Si capital = $10k, max = $1000 → RECHAZADO
```

#### **b) Correlación**
```python
correlation_matrix = {
    "BTC/USDT": ["ETH/USDT"],  # BTC y ETH caen juntos
    "ETH/USDT": ["BTC/USDT"]
}

# Si BTC está abierto y viene señal de ETH → revisar límite
max_correlated_positions = 2
```

#### **c) ATR Normalization**
```python
# BTC volátil: compra menos units
# PEPE estable: compra más units
# Mismo RIESGO en $$$

position_size = max_risk_usd / (ATR × multiplier)
```

---

## 🔄 Flow de Datos Completo

```
1. INGESTA
   Binance WS → watch_tickers(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
                    ↓
                Normalizar ticker
                    ↓
                ZeroMQ: publish([b'BTC/USDT', data])

2. PROCESAMIENTO (por cada símbolo)
   Engine recibe: topic='BTC/USDT', data={...}
                    ↓
                on_tick('BTC/USDT', data)
                    ↓
                Fetch OHLCV candles
                    ↓
                Run Strategy BTC → Signal?
                    ↓
                Si hay señal → Portfolio Risk Check
                    ↓
                Ejecutar trade

3. RISK CHECKS
   Signal generado
        ↓
   [Individual] Stop loss válido? Confidence >60%?
        ↓
   [Portfolio] Exposición total OK? Correlación OK?
        ↓
   Ejecutar (o rechazar)
```

---

## ➕ Cómo Agregar un Nuevo Par

### **Paso 1: Agregar a Safe List**

Editar [`config/safe_list.py`](config/safe_list.py):

```python
"MATIC/USDT": {
    "enabled": True,
    "tier": "VOLATILE",
    "strategy": "momentum",
    "leverage": 2,
    "max_position_size_usd": 800,
    "params": {
        "rsi_period": 9,
        "ma_fast": 8,
        "ma_slow": 21
    }
}
```

### **Paso 2: Reiniciar Sistema**

```bash
./run_multi_symbol.sh
```

**Automático:** El sistema detecta el nuevo par y:
1. Feed Handler lo suscribe en Binance
2. Engine crea estrategia según config
3. Empieza a procesarlo

---

## ➕ Cómo Agregar Nueva Estrategia

### **Paso 1: Crear Strategy Class**

```python
# apps/executor/strategies/breakout_strategy.py

from .base_strategy import BaseStrategy, Signal, SignalType
import pandas as pd

class BreakoutStrategy(BaseStrategy):
    def __init__(self, lookback_period: int = 20, **kwargs):
        super().__init__(**kwargs)
        self.lookback = lookback_period
    
    async def analyze(self, df: pd.DataFrame) -> Signal:
        # Tu lógica de breakout
        high_20 = df['high'].rolling(self.lookback).max()
        
        if df['close'].iloc[-1] > high_20.iloc[-2]:
            return Signal(
                signal_type=SignalType.BUY,
                confidence=0.70,
                entry_price=df['close'].iloc[-1],
                stop_loss=df['low'].iloc[-1],
                reasoning="20-day breakout"
            )
        
        return Signal(signal_type=SignalType.HOLD, confidence=0.0)
```

### **Paso 2: Registrar en Engine**

Editar [`apps/executor/multi_symbol_engine.py`](apps/executor/multi_symbol_engine.py):

```python
from apps.executor.strategies import BreakoutStrategy

# En _initialize_strategies():
elif config['strategy'] == 'breakout':
    breakout = BreakoutStrategy(
        name=f"Breakout-{symbol}",
        lookback_period=config['params'].get('lookback', 20)
    )
    strategy_manager.register_strategy(breakout)
```

### **Paso 3: Exportar en __init__.py**

Editar [`apps/executor/strategies/__init__.py`](apps/executor/strategies/__init__.py):

```python
from .breakout_strategy import BreakoutStrategy

__all__ = [
    'BaseStrategy',
    'Signal',
    'SignalType',
    'StrategyManager',
    'MomentumStrategy',
    'MeanReversionStrategy',
    'BreakoutStrategy'  # Agregar aquí
]
```

### **Paso 4: Usar en Safe List**

```python
"BTC/USDT": {
    "strategy": "breakout",  # Nuevo!
    "params": {
        "lookback": 20
    }
}
```

---

## 🐛 Troubleshooting

### **Error: "No module named 'zmq'"**

**Solución:**
```bash
source venv/bin/activate
pip install pyzmq
```

### **Error: "Connection refused (ZeroMQ)"**

**Causa:** Feed Handler no está corriendo.

**Solución:**
```bash
# Iniciar manualmente feed handler primero
python3 -m apps.ingestion.feed_handler_daemon

# En otra terminal:
python3 -m apps.executor.multi_symbol_engine
```

### **Warning: "Portfolio REJECTED: Total exposure..."**

**Causa:** Ya tienes demasiado capital comprometido.

**Solución:** Ajustar `max_total_exposure` en [`multi_symbol_engine.py`](apps/executor/multi_symbol_engine.py):
```python
# Línea ~85
risk_config = PortfolioRiskConfig(
    max_total_exposure=0.15  # Subir de 10% a 15%
)
```

### **Logs: "Insufficient data for ATR"**

**Causa:** No hay suficientes candles (< 14).

**Solución:** Esperar 1-2 minutos para acumular candles.

---

## 🧪 Testing

### **Test 1: Safe List**
```bash
python3 config/safe_list.py

# Expected: Lista de pares activos
```

### **Test 2: Feed Handler Solo**
```bash
python3 -m apps.ingestion.feed_handler_daemon

# Expected: 
# "Streaming 3 symbols..."
# "Published 100 total messages"
```

### **Test 3: Engine con Feed**
```bash
# Terminal 1:
python3 -m apps.ingestion.feed_handler_daemon

# Terminal 2:
python3 -m apps.executor.multi_symbol_engine

# Expected en Engine:
# "BTC/USDT - Signal: BUY (confidence: 65%)"
```

---

## 🔮 Extensiones Futuras

### **1. Database Persistence**

Agregar SQLite para recuperar estado después de crashes:

```python
# apps/executor/database.py (crear)
import sqlite3

class TradingDatabase:
    def save_position(self, symbol, size, entry_price):
        """Guardar posición activa."""
        self.cursor.execute(
            "INSERT INTO positions VALUES (?, ?, ?)",
            (symbol, size, entry_price)
        )
    
    def get_open_positions(self):
        """Recuperar posiciones después de crash."""
        return self.cursor.execute(
            "SELECT * FROM positions WHERE status='open'"
        ).fetchall()
```

### **2. ML Interface para RL**

Preparar para modelos de Reinforcement Learning:

```python
# apps/executor/ml_interface.py (crear)
import numpy as np

class MLInterface:
    def get_state_vector(self, symbol, candles, portfolio_state):
        """
        Convertir estado del mercado a vector para RL.
        
        Returns:
            np.array([rsi, bb_pos, atr, exposure, pnl, correlation])
        """
        rsi = self.calculate_rsi(candles)
        bb_pos = self.get_bb_position(candles)
        atr = self.get_atr(candles)
        exposure = portfolio_state['total_exposure']
        pnl = portfolio_state['daily_pnl']
        
        return np.array([rsi, bb_pos, atr, exposure, pnl])
    
    def action_to_order(self, action: int):
        """Convertir acción del modelo a orden de trading."""
        # 0 = HOLD, 1 = BUY, 2 = SELL
        actions = {
            0: SignalType.HOLD,
            1: SignalType.BUY,
            2: SignalType.SELL
        }
        return actions.get(action, SignalType.HOLD)
```

---

## 📊 Métricas y Observabilidad

### **Logs Importantes:**

```python
logger.info(f"Trading Profile: {self.profile.name}")
logger.info(f"✓ {symbol}: {strategy_type} (params)")
logger.info(f"🔔 {symbol} - Signal: {signal_type} (confidence: {conf}%)")
logger.info(f"✓ Portfolio approved (exposure: ${exp}/${max})")
logger.info(f"❌ {symbol} - Portfolio REJECTED: {reason}")
```

### **Métricas por símbolo:**

```python
self.messages_sent = {
    'BTC/USDT': 100,
    'ETH/USDT': 85,
    'SOL/USDT': 70
}
```

---

## 🏗️ Estructura de Código

### **Naming Conventions:**

- **Classes:** `PascalCase` (e.g., `MultiSymbolEngine`)
- **Functions:** `snake_case` (e.g., `get_active_symbols`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `SAFE_LIST`)
- **Private methods:** `_leading_underscore` (e.g., `_update_candles`)

### **Async Patterns:**

```python
# Bueno
async def fetch_data(self):
    result = await self.connector.get_ticker()
    return result

# Malo (blocking)
def fetch_data(self):
    result = self.connector.get_ticker_sync()  # Bloquea event loop
    return result
```

---

## 📖 Referencias

- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [CCXT Documentation](https://docs.ccxt.com/en/latest/)
- [ZeroMQ Guide](https://zeromq.org/get-started/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

---

**Última actualización:** 2026-02-06  
**Versión:** Multi-Par 1.0  
**Mantenedor:** Sistema de Trading Automatizado
