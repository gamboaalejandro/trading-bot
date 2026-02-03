# Estrategias de Trading - Documentación Técnica

## Índice
1. [Momentum Strategy](#momentum-strategy)
2. [Mean Reversion Strategy](#mean-reversion-strategy)
3. [Gestión de Riesgo](#gestión-de-riesgo)
4. [Cálculos Contables](#cálculos-contables)

---

## Momentum Strategy

### Concepto Económico

La estrategia Momentum se basa en el principio de **persistencia de tendencias** en los mercados financieros. Históricamente, los activos que han mostrado un movimiento direccional fuerte tienden a continuar en esa dirección a corto plazo, antes de una eventual reversión.

**Fundamento académico:**
- Papers de Jegadeesh y Titman (1993): "Returns to Buying Winners and Selling Losers"
- Fenómeno conductual: Reacción tardía de inversores a nueva información
- Auto-correlación positiva en retornos de corto plazo

### Indicadores Técnicos

#### 1. RSI (Relative Strength Index)
```
RSI = 100 - (100 / (1 + RS))
RS = Promedio de ganancias / Promedio de pérdidas (14 períodos)

Interpretación:
- RSI > 70: Sobrecompra (potencial reversión bajista)
- RSI < 30: Sobreventa (potencial reversión alcista)
- RSI > 50: Momentum alcista
- RSI < 50: Momentum bajista
```

#### 2. EMA Crossover (Cruce de Medias Móviles Exponenciales)
```
EMA = Precio_t × (2/(N+1)) + EMA_(t-1) × (1 - 2/(N+1))

Sistema:
- EMA rápida: 12 períodos
- EMA lenta: 26 períodos

Señal LONG: EMA(12) cruza ARRIBA de EMA(26)
Señal SHORT: EMA(12) cruza ABAJO de EMA(26)
```

### Lógica de Señales

```python
def generate_signal():
    if RSI > 50 and ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow:
        # Cruce alcista con momentum positivo
        return LONG
    
    elif RSI < 50 and ema_fast < ema_slow and prev_ema_fast >= prev_ema_slow:
        # Cruce bajista con momentum negativo
        return SHORT
    
    else:
        return NEUTRAL
```

### Cálculo de Stop Loss y Take Profit

```
ATR = Average True Range (14 períodos)
True Range = max(High - Low, |High - Close_prev|, |Low - Close_prev|)

Stop Loss:
- LONG: Entry Price - (2.0 × ATR)
- SHORT: Entry Price + (2.0 × ATR)

Take Profit:
- Ratio Risk/Reward = 1:3
- LONG: Entry Price + (3.0 × Risk)
- SHORT: Entry Price - (3.0 × Risk)
```

### Ejemplo Numérico

```
BTC/USDT
Precio actual: $50,000
ATR(14): $1,000
RSI: 62 (momentum alcista)
EMA(12): $49,800
EMA(26): $49,500
Cruce: EMA(12) acaba de cruzar arriba ✓

SEÑAL: LONG

Cálculos:
Entry: $50,000
Stop Loss: $50,000 - (2.0 × $1,000) = $48,000
Risk: $2,000 por BTC
Take Profit: $50,000 + (3.0 × $2,000) = $56,000

Si balance = $10,000 y max_risk = 2%:
Risk máximo = $200
Cantidad segura = $200 / $2,000 = 0.1 BTC
```

---

## Mean Reversion Strategy

### Concepto Económico

La estrategia de Reversión a la Media se fundamenta en la **tendencia de los precios a regresar a su promedio histórico** después de desviaciones extremas.

**Fundamento académico:**
- Teoría de Random Walk con reversión
- Fenómeno de "overshooting" por pánico/euforia
- Arbitraje estadístico

**Supuestos:**
- Los mercados son eficientes a largo plazo
- Las desviaciones temporales crean oportunidades
- La volatilidad tiende a normalizarse

### Indicadores Técnicos

#### 1. Bollinger Bands
```
Banda Media = SMA(20)
Banda Superior = SMA(20) + (2 × σ)
Banda Inferior = SMA(20) - (2 × σ)

Donde σ = Desviación Estándar de precios (20 períodos)

Interpretación probabilística:
- 95% de precios deberían estar dentro de las bandas
- Tocar banda superior = sobrecompra
- Tocar banda inferior = sobreventa
```

#### 2. RSI para Confirmación
```
RSI < 30: Sobreventa confirmada
RSI > 70: Sobrecompra confirmada
```

### Lógica de Señales

```python
def generate_signal():
    if price <= lower_band and RSI < 30:
        # Precio muy abajo + sobreventa = COMPRAR
        # Esperamos reversión al alza
        return LONG
    
    elif price >= upper_band and RSI > 70:
        # Precio muy arriba + sobrecompra = VENDER
        # Esperamos reversión a la baja
        return SHORT
    
    else:
        return NEUTRAL
```

### Cálculo de Stop Loss y Take Profit

```
Stop Loss:
- LONG: Por debajo de banda inferior (precio sigue cayendo)
  SL = Lower Band - (0.5 × (Upper Band - Lower Band))

- SHORT: Por encima de banda superior (precio sigue subiendo)
  SL = Upper Band + (0.5 × (Upper Band - Lower Band))

Take Profit:
- El objetivo es la banda del medio (SMA)
- LONG: TP = Middle Band (SMA)
- SHORT: TP = Middle Band (SMA)
```

### Ejemplo Numérico

```
ETH/USDT
Precio actual: $3,000
SMA(20): $3,150 (banda del medio)
Desviación Estándar: $75
Banda Superior: $3,150 + (2 × $75) = $3,300
Banda Inferior: $3,150 - (2 × $75) = $3,000
RSI: 28 (sobreventa)

SEÑAL: LONG (precio en banda inferior + RSI bajo)

Cálculos:
Entry: $3,000
Stop Loss: $3,000 - (0.5 × $300) = $2,850
Take Profit: $3,150 (banda del medio)
Risk por ETH: $150
Reward por ETH: $150

Si balance = $10,000 y max_risk = 2%:
Risk máximo = $200
Cantidad segura = $200 / $150 = 1.33 ETH
```

---

## Gestión de Riesgo

### 1. Kelly Criterion (Fraccional)

Fórmula completa:
```
Kelly% = (P × B - Q) / B

Donde:
P = Probabilidad de ganar (win_rate)
Q = Probabilidad de perder (1 - win_rate)
B = Ratio de ganancia/pérdida (reward_ratio)

Ejemplo:
P = 0.55 (55% win rate)
Q = 0.45
B = 2.0 (ganas el doble de lo que arriesgas)

Kelly% = (0.55 × 2.0 - 0.45) / 2.0 = 0.325 = 32.5%

Kelly Fraccional (1/4):
Position Size = 32.5% × 0.25 = 8.125% del balance
```

**Por qué fraccional:**
- Kelly completo es muy agresivo
- 1/4 o 1/2 Kelly reduce la volatilidad
- Protege contra estimaciones incorrectas de P y B

### 2. Circuit Breakers

```python
class CircuitBreaker:
    def check_daily_drawdown(self, daily_pnl, balance):
        max_loss = balance * MAX_DAILY_DRAWDOWN  # 5%
        
        if daily_pnl <= -max_loss:
            # STOP TRADING por hoy
            return BLOCKED
        
        return ALLOWED
```

**Razón económica:**
- Evita "revenge trading" (operar por emociones)
- Protege de días anómalos
- Limita pérdidas catastróficas

### 3. Position Sizing con ATR

```
Position Size = Risk Amount / (ATR × Multiplier)

Ejemplo:
Balance: $10,000
Max Risk: 2% = $200
ATR: $1,000
Multiplier: 2.0

Position Size = $200 / ($1,000 × 2.0) = 0.1 BTC
```

---

## Cálculos Contables

### P&L (Profit & Loss)

#### P&L No Realizado
```
Long Position:
Unrealized P&L = (Current Price - Entry Price) × Quantity

Short Position:
Unrealized P&L = (Entry Price - Current Price) × Quantity

Ejemplo LONG:
Entry: 1 BTC @ $50,000
Current: $51,500
Unrealized P&L = ($51,500 - $50,000) × 1 = +$1,500
```

#### P&L Realizado
```
Long Position:
Realized P&L = (Exit Price - Entry Price) × Quantity - Fees

Short Position:
Realized P&L = (Entry Price - Exit Price) × Quantity - Fees

Fees típicas Binance Futures: 0.04% (maker) / 0.06% (taker)

Ejemplo:
Entry: 1 BTC @ $50,000
Exit: 1 BTC @ $52,000
Fees: ($50,000 + $52,000) × 0.0006 = $61.20

Realized P&L = $2,000 - $61.20 = $1,938.80
```

### Margen y Apalancamiento

```
Margen Requerido = Posición Notional / Apalancamiento

Ejemplo:
Quieres controlar: 1 BTC @ $50,000 = $50,000 notional
Apalancamiento: 10x
Margen requerido: $50,000 / 10 = $5,000

⚠️ Precio de Liquidación:
Long con 10x: $50,000 × (1 - 1/10) = $45,000
Si BTC cae a $45,000, pierdes el margen completo
```

### ROI (Return on Investment)

```
ROI% = (P&L Realizado / Margen Inicial) × 100%

Ejemplo SIN apalancamiento:
Margen: $5,000
P&L: +$500
ROI = ($500 / $5,000) × 100% = 10%

Ejemplo CON apalancamiento 10x:
Margen: $5,000
Posición: $50,000
Movimiento 1%: $500
ROI = ($500 / $5,000) × 100% = 10% (mismo %)

Pero:
- Sin apalancamiento: necesitas $50,000 para ganar $500
- Con 10x: solo necesitas $5,000 para ganar $500
```

### Tracking de Performance

```python
class AccountMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_fees: float
    
    @property
    def win_rate(self):
        return self.winning_trades / self.total_trades
    
    @property
    def profit_factor(self):
        gross_profit = sum(winning_pnl)
        gross_loss = abs(sum(losing_pnl))
        return gross_profit / gross_loss  # > 1.0 es bueno
    
    @property
    def avg_win(self):
        return total_winning_pnl / winning_trades
    
    @property
    def avg_loss(self):
        return total_losing_pnl / losing_trades
    
    @property
    def expectancy(self):
        # Ganancia esperada por trade
        return (win_rate × avg_win) - ((1 - win_rate) × avg_loss)
```

### Ejemplo Completo de Trade

```
=== APERTURA ===
Balance inicial: $10,000
Símbolo: BTC/USDT
Estrategia: Momentum
Señal: LONG

Precio entrada: $50,000
ATR: $1,000
Stop Loss: $48,000
Take Profit: $56,000
Risk por BTC: $2,000
Win rate estimado: 55%
Reward ratio: 3:1

Kelly%: (0.55 × 3 - 0.45) / 3 = 0.40 = 40%
Kelly 1/4: 10% del balance = $1,000
Max risk: 2% = $200 (override, más conservador)

Position size: $200 / $2,000 = 0.1 BTC
Notional: 0.1 × $50,000 = $5,000
Apalancamiento usado: 1x (sin apalancamiento)

Fee entrada: $5,000 × 0.0006 = $3.00
Balance disponible: $10,000 - $5,000 - $3.00 = $4,997

=== SI GANA (TP) ===
Precio salida: $56,000
P&L bruto: ($56,000 - $50,000) × 0.1 = $600
Fee salida: $5,600 × 0.0006 = $3.36
P&L neto: $600 - $3.00 - $3.36 = $593.64

Balance final: $10,593.64
ROI: 5.94%

=== SI PIERDE (SL) ===
Precio salida: $48,000
P&L bruto: ($48,000 - $50,000) × 0.1 = -$200
Fee salida: $4,800 × 0.0006 = $2.88
P&L neto: -$200 - $3.00 - $2.88 = -$205.88

Balance final: $9,794.12
Pérdida: 2.06% ✓ (dentro del límite de 2%)
```

---

## Consideraciones Importantes

### ¿Cuándo NO operar?

1. **Alta volatilidad extrema:**
   ```python
   if current_atr > historical_atr_avg × 3:
       return NO_TRADE  # Mercado muy volátil
   ```

2. **Bajo volumen:**
   ```python
   if current_volume < avg_volume × 0.5:
       return NO_TRADE  # Liquidez insuficiente
   ```

3. **Circuit breaker activado:**
   ```python
   if daily_loss >= max_daily_drawdown:
       return STOP_ALL_TRADING
   ```

### Psicología del Trading Algorítmico

**Ventajas:**
- ✅ Sin emociones
- ✅ Disciplina perfecta
- ✅ Backtesting objetivo
- ✅ Ejecución instantánea

**Desafíos:**
- ❌ Overfitting (optimizar para el pasado)
- ❌ Cambios de régimen de mercado
- ❌ Eventos de cisne negro
- ❌ Costos de transacción ignorados

---

**Última actualización:** 2026-02-03
