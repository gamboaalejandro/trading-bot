#  Estrategias Óptimas por Par de Activos

Este documento define qué estrategias usar para cada par de trading según sus características de mercado.

---

##  Matriz de Estrategias por Asset

| Par de Monedas | Estrategia Principal | Estrategia Secundaria | Por Qué |
|---|---|---|---|
| **BTC/USDT** | Momentum + Breakout | Mean Reversion (correcciones) | Tendencias fuertes, alta liquidez, eventos que rompen niveles |
| **ETH/USDT** | Momentum | VWAP (scalping) | Correla con BTC pero más volátil, buen volumen para VWAP |
| **SOL/USDT, MATIC/USDT** | Mean Reversion | Grid Trading | Alta volatilidad intraday, muchos rangos laterales |
| **Altcoins < top 20** | Breakout | Grid Trading | Falsos breakouts frecuentes, mejor esperar confirmación |
| **USDC/USDT** | Grid Trading | Arbitrage (multi-exchange) | Oscilaciones microscópicas, casi sin tendencia |
| **Pares DEFI (UNI, AAVE)** | Mean Reversion | Momentum (eventos protocolo) | Volatilidad extrema, revertir a media es más seguro |
| **Pares MEME (DOGE, SHIB)** | Breakout | Ninguna (muy riesgoso) | Movimientos por hype/Reddit, solo rupturas con volumen |

---

##  Implementación por Categoría

### **Tier 1: Majors (BTC, ETH)**

**Configuración:**
```python
# btc_config.py
SYMBOL = "BTC/USDT"
STRATEGIES = [
    MomentumStrategy(rsi_period=14, fast_ma=10, slow_ma=30),
    BreakoutStrategy(lookback_periods=20, volume_multiplier=1.5),
    MeanReversionStrategy(bb_period=20, bb_std=2.0)  # Solo correcciones
]
COMBINATION_METHOD = "majority"  # 2 de 3
TIMEFRAME = "15m"
MAX_RISK_PER_TRADE = 0.02  # 2%
```

**Razón:**
- Alta liquidez → entradas/salidas rápidas sin slippage
- Eventos macroeconómicos → Breakout eficiente
- Tendencias largas → Momentum rentable

---

### **Tier 2: Large-cap Altcoins (SOL, MATIC, AVAX)**

**Configuración:**
```python
# altcoin_config.py
SYMBOL = "SOL/USDT"
STRATEGIES = [
    MeanReversionStrategy(bb_period=20, bb_std=2.5),  # Bandas más anchas
    GridTradingStrategy(grid_size=5, levels=10)
]
COMBINATION_METHOD = "any"  # Agresivo
TIMEFRAME = "5m"
MAX_RISK_PER_TRADE = 0.01  # 1% (más volátil)
```

**Razón:**
- Oscilaciones intraday frecuentes → Mean Reversion ideal
- Rangos laterales prolongados → Grid Trading genera income
- Menos líquido que BTC → Risk menor

---

### **Tier 3: Mid-cap (< Top 20)**

**Configuración:**
```python
# midcap_config.py
STRATEGIES = [
    BreakoutStrategy(lookback_periods=30, volume_multiplier=2.0),  # Más conservador
    GridTradingStrategy(grid_size=10, levels=5)
]
COMBINATION_METHOD = "consensus"  # Confirmación doble
TIMEFRAME = "15m"
MAX_RISK_PER_TRADE = 0.005  # 0.5%
```

**Razón:**
- Falsos breakouts frecuentes → Necesita confirmación
- Liquidez variable → Esperar volumen alto
- Riesgo mayor → Position sizing muy conservador

---

### **Tier 4: Stablecoins (USDC/USDT, DAI/USDT)**

**Configuración:**
```python
# stable_config.py
SYMBOL = "USDC/USDT"
STRATEGIES = [
    GridTradingStrategy(
        base_price=1.0000,
        grid_size=0.0001,  # $0.01 centavo
        levels=20
    ),
    ArbitrageStrategy(exchanges=["binance", "kraken", "coinbase"])
]
COMBINATION_METHOD = "any"
TIMEFRAME = "1m"
MAX_RISK_PER_TRADE = 0.10  # 10% (riesgo bajo, profit bajo)
```

**Razón:**
- Oscilación microscópica (0.01-0.03%)
- Grid Trading captura cada movimiento
- Arbitrage explota spreads entre exchanges
- **Passive income confiable**

---

### **Tier 5: DeFi Tokens (UNI, AAVE, COMP)**

**Configuración:**
```python
# defi_config.py
STRATEGIES = [
    MeanReversionStrategy(bb_period=20, bb_std=3.0),  # Bandas MUY anchas
    MomentumStrategy(rsi_period=14, fast_ma=12, slow_ma=26)  # Solo eventos
]
COMBINATION_METHOD = "consensus"
TIMEFRAME = "1h"
MAX_RISK_PER_TRADE = 0.01
EVENT_FILTER = True  # Solo operar en anuncios de protocolo
```

**Razón:**
- Volatilidad extrema → Bandas amplias
- Movimientos por governance/upgrades → Filtrar por eventos
- Mean Reversion más seguro que momentum

---

### **Tier 6: Meme Coins (DOGE, SHIB, PEPE)** ️

**Configuración:**
```python
# meme_config.py (️ MUY RIESGOSO)
STRATEGIES = [
    BreakoutStrategy(
        lookback_periods=50,
        volume_multiplier=3.0,  # Solo CON volumen masivo
        social_sentiment_filter=True  # Reddit/Twitter API
    )
]
COMBINATION_METHOD = "any"
TIMEFRAME = "5m"
MAX_RISK_PER_TRADE = 0.002  # 0.2% máximo
MAX_POSITIONS = 1  # Solo 1 posición a la vez
```

**Razón:**
- ️ **Extremadamente volátil y manipulable**
- Solo operar breakouts con:
  - Volumen 3x+ del promedio
  - Sentiment social positivo
  - Confirmación de varias fuentes
- **NO recomendado para principiantes**

---

##  Plantilla de Configuración

Para agregar un nuevo par, copia y modifica:

```python
# config/pairs/NEW_PAIR_config.py
from strategies import MomentumStrategy, MeanReversionStrategy, BreakoutStrategy

PAIR_CONFIG = {
    "symbol": "XXX/USDT",
    "tier": 2,  # 1=Major, 2=Large-cap, 3=Mid, 4=Stable, 5=DeFi, 6=Meme
    
    "strategies": [
        MomentumStrategy(rsi_period=14, fast_ma=10, slow_ma=30),
        MeanReversionStrategy(bb_period=20, bb_std=2.0),
    ],
    
    "combination_method": "majority",  # consensus, majority, any
    "timeframe": "15m",
    
    "risk_management": {
        "max_risk_per_trade": 0.02,  # 2%
        "max_positions": 3,
        "daily_loss_limit": 0.05,  # 5%
    },
    
    "filters": {
        "min_volume_24h": 1000000,  # $1M volumen mínimo
        "min_liquidity": 500000,     # $500K liquidez
        "blackout_hours": [],        # Horas de no trading
    }
}
```

---

##  Selección Rápida

### **Quiero Profit Consistente (Bajo Riesgo):**
```
Pares: BTC/USDT, ETH/USDT
Estrategias: Momentum + Mean Reversion
Combination: Consensus
Risk: 1-2%
```

### **Quiero Alta Frecuencia (Scalping):**
```
Pares: BTC/USDT, ETH/USDT, SOL/USDT
Estrategias: VWAP + Grid Trading
Timeframe: 1m, 5m
Risk: 0.5-1%
```

### **Quiero Passive Income (Estable):**
```
Pares: USDC/USDT
Estrategias: Grid Trading
Timeframe: 1m
Risk: 10% (bajo riesgo real)
```

### **Quiero Alto Riesgo/Alto Reward:**
```
Pares: Altcoins < top 20, Meme coins
Estrategias: Breakout con confirmación
Combination: Consensus
Risk: 0.2-0.5%
```

---

##  Adaptación Dinámica

El bot puede cambiar estrategias según condiciones:

```python
def select_strategy_by_market_condition(symbol, market_condition):
    if market_condition == "trending_up":
        return [MomentumStrategy(), BreakoutStrategy()]
    
    elif market_condition == "trending_down":
        return [MeanReversionStrategy()]  # Solo compras en oversold
    
    elif market_condition == "sideways":
        return [MeanReversionStrategy(), GridTradingStrategy()]
    
    elif market_condition == "high_volatility":
        return []  # STOP TRADING
```

---

##  Métricas de Validación

Antes de implementar una configuración nueva, validar con backtesting:

| Métrica | Mínimo Aceptable |
|---|---|
| **Sharpe Ratio** | > 1.5 |
| **Win Rate** | > 50% |
| **Profit Factor** | > 1.3 |
| **Max Drawdown** | < 15% |
| **Avg Trade Duration** | Según strategy |

---

##  Implementación en Trading Engine

```python
# trading_engine.py
from config.pairs import btc_config, eth_config, sol_config

ACTIVE_PAIRS = {
    "BTC/USDT": btc_config.PAIR_CONFIG,
    "ETH/USDT": eth_config.PAIR_CONFIG,
    "SOL/USDT": sol_config.PAIR_CONFIG,
}

# Multi-pair trading
for symbol, config in ACTIVE_PAIRS.items():
    engine = TradingEngine(
        symbol=symbol,
        strategies=config["strategies"],
        combination_method=config["combination_method"],
        timeframe=config["timeframe"],
        risk_config=config["risk_management"]
    )
    
    engines.append(engine)
```

---

## ️ Advertencias Importantes

1. **Nunca operar todos los pares** - Diversifica pero no te disperses
2. **Empezar con Tier 1** - BTC/ETH primero, luego expandir
3. **DRY_RUN obligatorio** - Probar configuración 1-2 semanas
4. **Backtesting SIEMPRE** - Validar con datos históricos
5. **Meme coins = Gambling** - Solo con capital que puedes perder

---

**Última actualización:** 2026-02-05  
**Versión:** 1.0

**Próximos pasos:**
- [ ] Implementar configuraciones por tier
- [ ] Crear sistema de selección dinámica
- [ ] Agregar filtros de volumen/liquidez
- [ ] Integrar social sentiment para meme coins
