#  Multi-Symbol Portfolio Trading Bot

Sistema de trading automatizado para criptomonedas con soporte multi-par, gestión de riesgo a nivel portfolio, y estrategias personalizables.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

##  Características Principales

### **Multi-Symbol Trading**
-  Soporte para múltiples pares simultáneos (BTC, ETH, SOL...)
-  Un solo WebSocket para todos los pares (eficiente)
-  Arquitectura event-driven (procesamiento asíncrono)

### **Portfolio Risk Management**
-  Control de exposición global (límite 10% del capital)
-  Gestión de correlación (evita sobre-exposición BTC+ETH)
-  ATR normalization (mismo riesgo $ para volatilidades diferentes)

### **Estrategias Personalizables**
-  Mean Reversion para pares estables (BTC, ETH)
-  Momentum para pares volátiles (SOL, MATIC)
-  Parámetros específicos por par

### **Seguridad**
-  Modo DRY_RUN (simulación sin órdenes reales)
-  Testnet de Binance soportado
-  Circuit breakers y kill switches
-  Profiles de riesgo (Conservative, Moderate, Advanced)

---

##  Quick Start

### **1. Instalación**

```bash
# Clonar repositorio
git clone https://github.com/yourusername/trading-bot.git
cd trading-bot

# Crear virtual environment
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### **2. Configuración**

Copiar y editar `.env`:

```bash
cp .env.example .env
nano .env
```

**Configuración mínima:**
```bash
# Binance Testnet (recomendado para empezar)
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_SECRET=your_testnet_secret
USE_TESTNET=true

# Modo simulación (NO ejecuta órdenes reales)
DRY_RUN=true

# Perfil de trading
TRADING_PROFILE=conservative  # conservative | moderate | advanced
```

> **Obtener API Keys testnet:** https://testnet.binancefuture.com/

### **3. Ejecutar**

```bash
./run_multi_symbol.sh
```

**Output esperado:**
```
=========================================
MULTI-SYMBOL TRADING BOT
=========================================
 Multi-Symbol Feed Handler (BTC/ETH/SOL)
 Multi-Symbol Trading Engine
Trading pairs: BTC/USDT, ETH/USDT, SOL/USDT
Mode: DRY_RUN (simulación)
```

---

## ️ Configuración de Pares

### **Agregar nuevo par:**

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

Reiniciar el bot → detectará automáticamente el nuevo par.

### **Desactivar par:**

```python
"SOL/USDT": {
    "enabled": False,  # Solo cambiar esto
    ...
}
```

---

##  Perfiles de Trading

| Perfil | Capital | Combinación | Min Conf | Risk/Trade |
|---|---|---|---|---|
| **Conservative** | < $10k | Consensus (100%) | 65% | 1% |
| **Moderate** | $10k-$50k | Majority (>50%) | 60% | 2% |
| **Advanced** | > $50k | Weighted | 55% | 3% |

Ver [`PERFILES_GUIA.md`](PERFILES_GUIA.md) para detalles completos.

---

##  Estrategias Disponibles

### **1. Mean Reversion**
- **Para:** BTC, ETH (pares estables)
- **Lógica:** Compra oversold, vende overbought
- **Indicadores:** RSI + Bollinger Bands

### **2. Momentum**
- **Para:** SOL, MATIC (pares volátiles)
- **Lógica:** Sigue tendencias fuertes
- **Indicadores:** RSI + Moving Averages

Ver [`TRADING_STRATEGIES.md`](TRADING_STRATEGIES.md) para análisis económico completo.

---

## ️ Arquitectura

```
Safe List Config
       ↓
Feed Handler (Binance WS) ──→ Multi-Symbol Engine
       │                              │
    ZeroMQ                    Portfolio Risk Manager
   (Topics)                      (Exposure + Correlation)
```

**Componentes:**
1. **Safe List:** Configuración de pares ([`config/safe_list.py`](config/safe_list.py))
2. **Feed Handler:** WebSocket → ZeroMQ ([`apps/ingestion/`](apps/ingestion/))
3. **Multi-Symbol Engine:** Procesamiento y trading ([`apps/executor/multi_symbol_engine.py`](apps/executor/multi_symbol_engine.py))
4. **Portfolio Risk Manager:** Control global de riesgo ([`apps/executor/risk_manager.py`](apps/executor/risk_manager.py))

---

##  Estructura del Proyecto

```
trading-bot/
├── config/
│   └── safe_list.py              # Configuración de pares
├── apps/
│   ├── ingestion/
│   │   └── feed_handler_daemon.py   # WebSocket → ZeroMQ
│   └── executor/
│       ├── multi_symbol_engine.py   # Motor principal
│       ├── risk_manager.py          # Portfolio risk
│       ├── profiles.py              # Trading profiles
│       └── strategies/              # Estrategias de trading
├── orchestrator.py                  # Launch manager
├── run_multi_symbol.sh              # Script de ejecución
└── README_TECHNICAL.md              # Docs para desarrolladores
```

---

##  Para Desarrolladores

### **Agregar nueva estrategia:**

Ver guía completa en [`README_TECHNICAL.md`](README_TECHNICAL.md#-cómo-agregar-nueva-estrategia)

### **Extender sistema:**

- **Portfolio Risk:** Editar [`apps/executor/risk_manager.py`](apps/executor/risk_manager.py)
- **Nuevos indicadores:** Crear en [`apps/executor/strategies/`](apps/executor/strategies/)
- **Database persistence:** Ver roadmap en docs técnicas

---

## ️ Gestión de Riesgo

### **Portfolio-Level Controls:**

**1. Exposición Global:**
```
Max 10% del capital total en riesgo
Ejemplo: Capital $10k → Max $1000 en posiciones
```

**2. Correlación:**
```
BTC y ETH están correlacionados
Si BTC abierto → limitar ETH (máx 2 correlated)
```

**3. ATR Normalization:**
```
BTC volátil: compra menos units
SOL estable: compra más units
→ Mismo riesgo en $$$
```

---

##  Testing

```bash
# Test configuración
python3 config/safe_list.py

# Test feed handler
python3 -m apps.ingestion.feed_handler_daemon

# Test engine (requiere feed corriendo)
python3 -m apps.executor.multi_symbol_engine
```

---

##  Documentación

-  [`README_TECHNICAL.md`](README_TECHNICAL.md) - Guía técnica para desarrolladores
-  [`PERFILES_GUIA.md`](PERFILES_GUIA.md) - Guía de perfiles de trading
-  [`TRADING_STRATEGIES.md`](TRADING_STRATEGIES.md) - Análisis económico de estrategias
-  [`ESTRATEGIAS_POR_PAR.md`](ESTRATEGIAS_POR_PAR.md) - Configuración por par

---

##  Roadmap

- [ ] **Database Persistence:** State recovery con SQLite
- [ ] **ML Interface:** Preparación para RL agents (PPO, DQN)
- [ ] **Web Dashboard:** Visualización en tiempo real
- [ ] **Telegram Bot:** Alertas y control remoto
- [ ] **Backtesting:** Test histórico de estrategias

---

## ️ Seguridad

-  **DRY_RUN mode:** Prueba sin riesgo
-  **Testnet primero:** Nunca empieces en producción
-  **Kill Switch:** Detiene si pérdida diaria > 5%
-  **API Keys en .env:** Nunca en código
-  **Stop Loss dinámico:** Basado en ATR

---

## ️ Licencia

MIT License - Ver [LICENSE](LICENSE)

---

## ️ Disclaimer

**Este bot es para fines educacionales.** Trading de criptomonedas conlleva riesgo significativo de pérdida. 

**IMPORTANTE:**
- Prueba SIEMPRE en modo DRY_RUN primero
- Usa Binance Testnet antes de capital real
- Nunca inviertas más de lo que puedes perder
- El autor NO se responsabiliza por pérdidas

---

##  Contribuir

Contributions are welcome!

1. Fork el repositorio
2. Crea feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abre Pull Request

---

**Última actualización:** 2026-02-06  
**Versión:** 1.0.0 (Multi-Symbol)  
**Mantenedor:** [Tu Nombre]
