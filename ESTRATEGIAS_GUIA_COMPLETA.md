#  Guía Completa de Estrategias de Trading

##  Resumen Ejecutivo

Tu bot actualmente usa **2 estrategias complementarias** que funcionan en diferentes condiciones de mercado:

| Estrategia | Mejor Para | Condición de Mercado |
|---|---|---|
| **Momentum** | Tendencias fuertes | Mercado direccional (subida/bajada clara) |
| **Mean Reversion** | Rangos laterales | Mercado lateral (oscilación entre niveles) |

**Combinación actual:** El bot usa **consensus** - solo opera cuando ambas estrategias coinciden, lo que reduce señales falsas pero puede perder oportunidades.

---

##  Estrategias Actuales

### 1. **Momentum Strategy** (Seguimiento de Tendencia)

#### ¿Qué Hace?
Detecta cuando el precio tiene **inercia direccional** (subida o bajada) y opera en esa dirección.

#### Indicadores Usados:
```
 RSI (14 períodos): Mide la fuerza del movimiento
   - RSI > 50 = Momentum alcista
   - RSI < 50 = Momentum bajista

 EMA Crossover (10 y 30 períodos):
   - EMA rápida cruza arriba de lenta = COMPRA
   - EMA rápida cruza abajo de lenta = VENDE
```

#### Señal de COMPRA:
```python
BUY si:
   EMA(10) cruza ARRIBA de EMA(30)  # Golden cross
   RSI > 50                          # Momentum positivo
   Precio subiendo consistentemente
  
Ejemplo:
  Precio: $70,000 → $71,000 → $72,000
  EMA(10) = $71,500
  EMA(30) = $70,800  # Acaba de cruzar!
  RSI = 62
  → SEÑAL: BUY (confianza: 75%)
```

#### Stop Loss & Take Profit:
```
SL = Precio - (2 × ATR)    # Protección contra reversión
TP = Precio + (6 × ATR)    # Ratio 1:3 (ganas 3x lo que arriesgas)

Ejemplo con BTC @ $72,000, ATR = $1,000:
  Entry:  $72,000
  SL:     $70,000  (-$2,000)
  TP:     $78,000  (+$6,000)
```

#### **Mejor Para:**
-  BTC/USDT cuando hay noticias que mueven el precio
-  ETH/USDT en fases de "bull run"
-  Activos con volumen alto
-  Timeframes: 5m, 15m, 1h

---

### 2. **Mean Reversion Strategy** (Reversión a la Media)

#### ¿Qué Hace?
Apuesta a que cuando el precio se **estira demasiado** (arriba o abajo), volverá al promedio.

#### Indicadores Usados:
```
 Bollinger Bands (20 períodos, 2σ):
   BB Superior = SMA(20) + (2 × Desviación Estándar)
   BB Medio    = SMA(20)
   BB Inferior = SMA(20) - (2 × Desviación Estándar)

 RSI (14 períodos):
   - RSI < 30 = Sobreventa (precio muy bajo)
   - RSI > 70 = Sobrecompra (precio muy alto)
```

#### Señal de COMPRA:
```python
BUY si:
   Precio toca/cruza banda INFERIOR  # Precio muy bajo
   RSI < 30                           # Confirmación sobreventa
   Expectativa: rebote hacia la media
  
Ejemplo:
  Precio actual: $65,000
  BB Superior:   $68,000
  BB Medio:      $66,000  ← Objetivo del trade
  BB Inferior:   $64,000  ← Precio está aquí!
  RSI = 28  # Sobreventa
  → SEÑAL: BUY (confianza: 68%)
```

#### Stop Loss & Take Profit:
```
SL = BB Inferior - 1%     # Si sigue cayendo, salir
TP = BB Medio (SMA)       # Reversión al promedio

Ejemplo:
  Entry:  $65,000 (banda inferior)
  SL:     $63,360  (-2.5%)
  TP:     $66,000  (+1.5%)    # Ratio 1:0.6 (conservador)
```

#### **Mejor Para:**
-  Mercado lateral (sin tendencia clara)
-  Pares estables (USDT, USDC pares)
-  **SOL/USDT**, **MATIC/USDT** (alta volatilidad intraday)
-  Timeframes: 1m, 5m, 15m

---

##  Combinación de Estrategias

### **Modo Actual: CONSENSUS**

```python
# strategy_manager.py línea 75
combination_method = "consensus"

# Solo opera si AMBAS estrategias coinciden
if momentum.signal == "BUY" AND mean_reversion.signal == "BUY":
    → Ejecutar trade 
else:
    → HOLD (no operar)
```

**Ventajas:**
-  **Alta precisión** - Pocas señales falsas
-  **Menor riesgo** - Confirmación doble
-  **Ideal para principiantes**

**Desventajas:**
-  **Pocas señales** - Se pierden oportunidades
-  **Lento en mercados activos**

---

### **Alternativa 1: MAJORITY (Mayoría)**

```python
combination_method = "majority"

# Opera si al menos 2 de 3 estrategias coinciden
Strategies: [Momentum, Mean Reversion, Breakout]
  Momentum:      BUY
  Mean Reversion: HOLD
  Breakout:      BUY
  → 2/3 = BUY 
```

**Mejor Para:**
- Mercados con múltiples señales
- Cuando tienes 3+ estrategias
- Balance entre precisión y frecuencia

---

### **Alternativa 2: ANY (Cualquiera)**

```python
combination_method = "any"

# Opera si CUALQUIER estrategia da señal
if momentum.signal == "BUY" OR mean_reversion.signal == "BUY":
    → Ejecutar trade
```

**Mejor Para:**
- ️ **Solo con altísima confianza** (>80%)
- Mercados muy volátiles
- Day trading agresivo

---

##  Otras Estrategias Recomendadas

### **3. Breakout Strategy** (Rupturas de Niveles)

#### Concepto:
Compra cuando el precio **rompe resistencias** clave con volumen alto.

#### Implementación:
```python
def generate_signal():
    resistance = max(close[-20:])  # Máximo de 20 velas
    
    if current_price > resistance * 1.005 and volume > avg_volume * 1.5:
        # Ruptura de resistencia + volumen = COMPRA
        return BUY
        
    support = min(close[-20:])
    if current_price < support * 0.995 and volume > avg_volume * 1.5:
        # Ruptura de soporte + volumen = VENDE
        return SELL
```

#### **Mejor Para:**
- BTC/USDT en momentos de "pump"
- Anuncios importantes (halving, ETF approval)
- Timeframes: 15m, 1h, 4h

---

### **4. Grid Trading** (Trading en Cuadrícula)

#### Concepto:
Coloca **órdenes de compra/venta** en niveles equidistantes, aprovechando oscilaciones pequeñas.

#### Implementación:
```python
def setup_grid():
    current_price = 70000
    grid_size = 500  # $500 entre órdenes
    
    # Crear grid
    buy_levels  = [69500, 69000, 68500]  # Compra abajo
    sell_levels = [70500, 71000, 71500]  # Vende arriba
    
    # Cuando precio toca nivel:
    if price <= buy_levels[i]:
        buy(amount)
    if price >= sell_levels[i]:
        sell(amount)
```

#### **Mejor Para:**
-  **STABLECOINS pairs** (USDT/USDC)
-  Mercado lateral prolongado
-  Baja volatilidad
-  **Genera income constante** (scalping)

---

### **5. VWAP Strategy** (Volume-Weighted Average Price)

#### Concepto:
Opera basado en el **precio promedio ponderado por volumen**.

#### Lógica:
```python
VWAP = Σ(Price × Volume) / Σ(Volume)

if price < VWAP and volume_increasing:
    # Precio barato + interés creciente = COMPRA
    return BUY
    
if price > VWAP * 1.02 and RSI > 70:
    # Precio caro + sobrecompra = VENDE
    return SELL
```

#### **Mejor Para:**
- Alta frecuencia (scalping)
- Pares con volumen masivo
- Timeframes: 1m, 5m

---

### **6. Arbitrage (Multi-Exchange)**

#### Concepto:
Compra en un exchange barato, vende en otro caro.

#### Ejemplo:
```
Binance:  BTC = $70,000
Kraken:   BTC = $70,200
Spread:   $200 (0.28%)

Acción:
1. Compra 1 BTC en Binance @ $70,000
2. Transfiere a Kraken (fee: ~$10)
3. Vende en Kraken @ $70,200
4. Profit: $200 - $10 - fees = ~$180
```

#### **Mejor Para:**
- ️ **Requiere capital alto**
- Exchanges con fees bajos
- BTC, ETH (liquidez)

---

##  Estrategia Óptima por Par de Activos

### **BTC/USDT** 🪙
```
Mejor combinación:
 Momentum (tendencias fuertes)
 Breakout (noticias, halving)
 Mean Reversion (correcciones)

Recomendación:
- Timeframe: 15m, 1h
- Combination: MAJORITY (2/3)
- Max Risk: 1-2% por trade
```

### **ETH/USDT** 
```
Mejor combinación:
 Momentum (por correlación con BTC)
 Mean Reversion (oscila más que BTC)
 VWAP (gran volumen)

Recomendación:
- Timeframe: 5m, 15m
- Combination: MAJORITY
- Más volátil → ajustar stop loss
```

### **SOL/USDT, MATIC/USDT**  (Altcoins)
```
Mejor combinación:
 Mean Reversion (altísima volatilidad intraday)
 Grid Trading (oscilaciones constantes)
 Evitar Momentum (falsos breakouts)

Recomendación:
- Timeframe: 1m, 5m
- Combination: ANY (agresivo)
- Max Risk: 0.5-1% (más riesgoso)
```

### **USDC/USDT**  (Stablecoins)
```
Mejor combinación:
 Grid Trading (oscila 0.01-0.03%)
 Arbitrage (explotar diferencias)

Recomendación:
- Timeframe: 1m
- Grid size: 0.0001 ($0.01 de diferencia)
- Alto volumen, bajo riesgo
- **Ideal para generar passive income**
```

---

##  Cómo Implementar Nuevas Estrategias

### **Paso 1: Crear la estrategia**
```bash
# Crear archivo en apps/executor/strategies/
touch apps/executor/strategies/breakout_strategy.py
```

### **Paso 2: Heredar de BaseStrategy**
```python
from .base_strategy import BaseStrategy, Signal, SignalType

class BreakoutStrategy(BaseStrategy):
    def __init__(self, lookback_periods=20, name="Breakout"):
        super().__init__(name)
        self.lookback_periods = lookback_periods
    
    def get_required_candles(self):
        return self.lookback_periods + 5
    
    async def generate_signal(self, df):
        # Tu lógica aquí
        resistance = df['high'].rolling(self.lookback_periods).max().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        if current_price > resistance * 1.005:
            return Signal(
                signal_type=SignalType.BUY,
                confidence=0.75,
                entry_price=current_price,
                stop_loss=resistance * 0.98,
                take_profit=current_price * 1.03
            )
        
        return None
```

### **Paso 3: Registrar en Trading Engine**
```python
# trading_engine.py
from strategies.breakout_strategy import BreakoutStrategy

# En __init__:
self.strategy_manager.register_strategy(MomentumStrategy())
self.strategy_manager.register_strategy(MeanReversionStrategy())
self.strategy_manager.register_strategy(BreakoutStrategy())  # ← Nueva!
```

### **Paso 4: Cambiar método de combinación**
```python
# strategy_manager.py línea 75
self.combination_method = "majority"  # Cambiar de "consensus"
```

---

##  Optimización por Condiciones de Mercado

### **Mercado BULL (Subida Fuerte)**
```python
Estrategias activas:
 Momentum (prioridad alta)
 Breakout
 Desactivar Mean Reversion (contra-tendencia)

Config:
- Timeframe: 1h, 4h (tendencias largas)
- Risk: 2-3% por trade
- Take Profit: Más agresivo (1:4, 1:5)
```

### **Mercado BEAR (Bajada Fuerte)**
```python
Estrategias activas:
 Mean Reversion (compra en pánico)
 SHORT con Momentum
 Evitar Breakout (fakeouts frecuentes)

Config:
- Timeframe: 15m, 1h
- Risk: 1% (conservador)
- Preferir DRY_RUN hasta confirmation
```

### **Mercado LATERAL (Rango)**
```python
Estrategias activas:
 Mean Reversion (excelente)
 Grid Trading (perfecto)
 Desactivar Momentum

Config:
- Timeframe: 1m, 5m
- Risk: 1-2%
- Tomar profits rápidos (1:1 ratio)
```

---

##  Backtesting Recomendado

Antes de activar una estrategia nueva:

```python
# 1. Descargar datos históricos
data = download_binance_data("BTC/USDT", "1h", days=90)

# 2. Backtest
results = backtest(
    data=data,
    strategy=BreakoutStrategy(),
    initial_capital=10000,
    risk_per_trade=0.02
)

# 3. Analizar métricas
print(f"Total Trades: {results.total_trades}")
print(f"Win Rate: {results.win_rate:.2%}")
print(f"Sharpe Ratio: {results.sharpe:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")

# 4. Solo implementar si:
if results.sharpe > 1.5 and results.win_rate > 0.50:
    print(" Estrategia aprobada")
else:
    print(" Necesita optimización")
```

---

##  Mejores Prácticas

### **1. Diversificación**
```
NO poner todo en una estrategia:
 40% Momentum
 40% Mean Reversion
 20% Breakout/Grid
```

### **2. Risk Management**
```
Por estrategia:
- Max risk: 1-2% del balance
- Max positions simultáneas: 3
- Daily loss limit: 5%
```

### **3. Monitoreo**
```bash
# Revisar diariamente:
- Win rate por estrategia
- Tiempo promedio de trades
- Drawdown actual

# Desactivar estrategia si:
- Win rate < 45% en últimos 20 trades
- Pérdida > 10% en una semana
```

---

##  Recursos Adicionales

- **Documentación técnica completa:** [`TRADING_STRATEGIES.md`](./TRADING_STRATEGIES.md)
- **Paper de Momentum:** Jegadeesh & Titman (1993)
- **Bollinger Bands:** John Bollinger - "Bollinger on Bollinger Bands"
- **Risk Management:** Ralph Vince - "The Mathematics of Money Management"

---

**Última actualización:** 2026-02-05  
**Versión:** 2.0
