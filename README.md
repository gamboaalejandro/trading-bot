# Sistema de Trading Algorítmico

Sistema profesional de trading automatizado para Binance Futures con estrategias técnicas, gestión de riesgo avanzada y monitoreo en tiempo real.

## 🎯 Características Principales

- **Estrategias de Trading Implementadas**
  - Momentum Strategy (RSI + Moving Average Crossover)
  - Mean Reversion Strategy (Bollinger Bands + RSI)
  
- **Gestión Profesional de Riesgo**
  - Circuit breakers (límites de pérdida diaria)
  - Fractional Kelly Criterion para sizing
  - Stop Loss automático basado en ATR
  - Validación de volatilidad
  
- **Conexión a Binance**
  - Testnet/Demo Trading (dinero de prueba)
  - Producción (trading real) ⚠️
  - Sistema ZeroMQ para datos en tiempo real
  
- **Motor de Trading**
  - Ejecución automatizada de estrategias
  - Monitoreo de posiciones
  - Tracking de P&L
  - Modo DRY_RUN para simulación

## 📁 Estructura del Proyecto

```
trading-bot/
├── apps/
│   ├── ingestion/          # Sistema ZeroMQ - Datos en tiempo real
│   │   ├── feed_handler.py # Conexión a Binance WebSocket
│   │   └── binance_ws_manager.py
│   │
│   └── executor/           # Sistema de Trading
│       ├── strategies/     # Estrategias implementadas
│       │   ├── base_strategy.py
│       │   ├── momentum_strategy.py
│       │   ├── mean_reversion_strategy.py
│       │   └── strategy_manager.py
│       │
│       ├── testnet_connector.py  # Conexión a Binance
│       ├── risk_manager.py       # Gestión de riesgo
│       ├── account_manager.py    # Tracking de cuenta
│       └── trading_engine.py     # Motor principal
│
├── examples/               # Scripts de ejemplo
│   ├── check_status.py    # Ver balance y posiciones
│   ├── open_first_position.py  # Abrir posición manual
│   └── close_position.py  # Cerrar posiciones
│
├── core/
│   └── config.py          # Configuración central
│
├── .env                   # Variables de entorno
└── run_trading_engine.sh  # Iniciar trading automático
```

## 🚀 Inicio Rápido

### 1. Configuración Inicial

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env con tus API keys
```

### 2. Obtener API Keys de Testnet

1. Ve a https://testnet.binancefuture.com/
2. Inicia sesión o crea cuenta
3. Ve a "API Management"
4. Genera API Key + Secret
5. Actualiza `.env`:
   ```env
   BINANCE_TESTNET_API_KEY=tu_key_aqui
   BINANCE_TESTNET_SECRET=tu_secret_aqui
   USE_TESTNET=true
   ```

### 3. Primeros Pasos

#### Ver Estado de Cuenta
```bash
python3 examples/check_status.py
```

#### Abrir Primera Posición (Manual)
```bash
python3 examples/open_first_position.py
```

#### Trading Automático
```bash
./run_trading_engine.sh
```

## 📊 Estrategias de Trading

### 1. Momentum Strategy

**Concepto Económico:**
Capitaliza la tendencia de que los activos que han subido recientemente tienden a seguir subiendo (y viceversa). Se basa en el principio de que "la tendencia es tu amiga".

**Funcionamiento:**
- **Indicadores:** RSI (Relative Strength Index) + EMA Crossover
- **Señal LONG:** RSI > 50 Y EMA rápida cruza por encima de EMA lenta
- **Señal SHORT:** RSI < 50 Y EMA rápida cruza por debajo de EMA lenta
- **Stop Loss:** 2x ATR desde el precio de entrada
- **Take Profit:** 3x el riesgo (ratio 1:3)

**Contabilidad:**
```
Ejemplo LONG en BTC/USDT:
- Precio entrada: $50,000
- Cantidad: 0.1 BTC (calculada por risk manager)
- Stop Loss: $49,000 (2% riesgo)
- Take Profit: $53,000 (6% ganancia)

Riesgo: 0.1 BTC × $1,000 = $100 USDT
Ganancia potencial: 0.1 BTC × $3,000 = $300 USDT
Risk/Reward: 1:3
```

### 2. Mean Reversion Strategy

**Concepto Económico:**
Se basa en que los precios tienden a volver a su media histórica. Cuando el precio se aleja mucho de la media, es probable que regrese.

**Funcionamiento:**
- **Indicadores:** Bollinger Bands + RSI
- **Señal LONG:** Precio toca banda inferior Y RSI < 30 (sobreventa)
- **Señal SHORT:** Precio toca banda superior Y RSI > 70 (sobrecompra)
- **Stop Loss:** Fuera de las bandas
- **Take Profit:** Banda del medio (media móvil)

**Contabilidad:**
```
Ejemplo LONG en ETH/USDT:
- Precio entrada: $3,000 (banda inferior)
- Media móvil (target): $3,150
- Stop Loss: $2,950
- Cantidad: calculada para arriesgar 2% del balance

Si balance = $10,000:
Riesgo máximo = $200
Riesgo por unidad = $3,000 - $2,950 = $50
Cantidad segura = $200 / $50 = 4 ETH
```

## ⚙️ Gestión de Riesgo

El sistema implementa múltiples capas de protección:

### 1. Circuit Breakers
```python
MAX_DAILY_DRAWDOWN = 5%  # Si pierdes 5% en un día, se detiene
```

### 2. Kelly Criterion (Fraccional)
```python
# Calcula el tamaño óptimo basado en:
kelly = (win_rate - (1 - win_rate) / reward_ratio) × kelly_fraction

# Ejemplo:
# win_rate = 55%, reward_ratio = 2.0, kelly_fraction = 0.25
kelly = (0.55 - 0.45/2.0) × 0.25 = 0.08125  # 8.125% del balance
```

### 3. Hard Caps
```python
MAX_RISK_PER_TRADE = 2%  # Nunca arriesgar más del 2% por operación
```

### 4. ATR-Based Stop Loss
```python
stop_loss = entry_price ± (ATR × 2.0)  # 2x el rango promedio
```

## 🔧 Configuración Avanzada

### Variables de Entorno `.env`

```env
# Conexión
USE_TESTNET=true                    # true = testnet, false = producción
BINANCE_TESTNET_API_KEY=your_key
BINANCE_TESTNET_SECRET=your_secret

# Trading Engine
DRY_RUN=true                        # true = simulación, false = real
TRADING_SYMBOL=BTC/USDT
TRADING_TIMEFRAME=5m                # 1m, 5m, 15m, 1h, etc.
CHECK_INTERVAL=60                   # Segundos entre checks

# Risk Management
MAX_DAILY_DRAWDOWN=0.05             # 5%
MAX_RISK_PER_TRADE=0.02             # 2%
KELLY_FRACTION=0.25                 # 1/4 Kelly
MIN_NOTIONAL_USDT=10.0              # Mínimo $10 por operación

# Redis (para ZeroMQ)
REDIS_URL=redis://localhost:6379/0
```

## 📈 Sistema ZeroMQ - Datos en Tiempo Real

El sistema usa ZeroMQ para recibir actualizaciones de precio en tiempo real:

```bash
# Iniciar feed handler
./run_feed_handler.sh

# Los datos fluyen automáticamente al trading engine
```

**Ventajas:**
- Latencia ultra-baja
- No polling innecesario
- Escalable a múltiples suscriptores

## 🎓 Conceptos Económicos

### P&L (Profit & Loss)
```
P&L Realizado = Precio Salida - Precio Entrada × Cantidad
P&L No Realizado = Precio Actual - Precio Entrada × Cantidad

Ejemplo:
Compra: 1 BTC @ $50,000
Precio actual: $51,000
P&L no realizado = ($51,000 - $50,000) × 1 = +$1,000
```

### Apalancamiento
```
Apalancamiento = Valor Total Posición / Margen Usado

Ejemplo 10x:
Balance: $1,000
Con apalancamiento 10x: Puedes controlar $10,000
Margen requerido: $1,000

⚠️ Mayor ganancia potencial = Mayor riesgo de liquidación
```

### Liquidación
```
Precio Liquidación (LONG) = Precio Entrada × (1 - 1/Apalancamiento)

Ejemplo:
Entrada: $50,000 con 10x
Liquidación: $50,000 × (1 - 1/10) = $45,000

Si BTC cae a $45,000, pierdes todo el margen ❌
```

## ⚠️ Advertencias

- **Testnet primero:** Siempre prueba en testnet antes de usar dinero real
- **DRY_RUN mode:** Usa simulación hasta estar 100% seguro
- **Risk management:** Nunca desactives los límites de riesgo
- **Apalancamiento:** Usa 1x-3x máximo hasta tener experiencia
- **Monitoreo:** Supervisa las operaciones regularmente

## 🚨 Modo Producción

Para activar trading real:

```env
USE_TESTNET=false
DRY_RUN=false
BINANCE_API_KEY=tu_key_producción
BINANCE_SECRET=tu_secret_producción
```

**⚠️ SOLO CUANDO ESTÉS COMPLETAMENTE SEGURO**

## 📚 Comandos Útiles

```bash
# Ver estado
python3 examples/check_status.py

# Abrir posición manual
python3 examples/open_first_position.py

# Cerrar todas las posiciones
python3 examples/close_position.py

# Trading automático
./run_trading_engine.sh

# Monitorear logs
tail -f logs/trading_engine.log
```

## 🛠️ Troubleshooting

### "Invalid API Key"
- Verifica que las keys sean de testnet si `USE_TESTNET=true`
- Regenera las keys en https://testnet.binancefuture.com/

### "Insufficient balance"
- Ve a testnet y haz clic en "Get Test Funds"

### Estrategias no generan señales
- Verifica que hay suficiente historial de precios
- Ajusta los parámetros de las estrategias
- Revisa los logs para ver por qué no se generan señales

## 📄 Licencia

MIT License - Ver archivo LICENSE

## ⚡ Soporte

Para problemas o preguntas, revisa los logs en `logs/` o el código fuente en `apps/executor/`.

---

**Desarrollado para trading algorítmico profesional con gestión de riesgo institucional.**
