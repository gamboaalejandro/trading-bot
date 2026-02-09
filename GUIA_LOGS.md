#  Guía: Ver Señales de Trading en Vivo

## Opción 1: Ver Logs en Vivo (Recomendado)

### **Terminal 1: Iniciar el bot**
```bash
./run_multi_symbol.sh
```

### **Terminal 2: Ver logs en vivo**
```bash
./ver_logs.sh
```

Esto mostrará la actividad del Trading Engine en tiempo real.

---

## Opción 2: Ver Todo desde una Terminal

```bash
./run_multi_symbol.sh
```

Verás los logs del orchestrator, pero no los detalles del engine.

---

##  Qué Esperar Ver

### **Actividad Normal (Sin Señales):**

```
2026-02-06 00:25:00 - INFO - BTC/USDT: Updated 100 candles
2026-02-06 00:25:05 - INFO - ETH/USDT: Updated 100 candles
2026-02-06 00:25:10 - INFO - SOL/USDT: Updated 100 candles
```

Esto significa que el bot está:
-  Recibiendo datos de Binance
-  Actualizando candles OHLCV
-  Analizando el mercado

---

### **Cuando HAY una Señal de Trading:**

```
 BTC/USDT - Signal: BUY (confidence: 67%)
   Entry: $42,350.00
   Stop Loss: $41,800.00
   Risk/Reward: 1:2.5

 Portfolio approved (exposure: $500/$1000)
   Position Size: $200.00 (0.0047 BTC)
   Stop Loss: $41,800.00
   Risk per Trade: 1.0%

 DRY RUN MODE - Trade NOT executed
   (En modo real, se habría ejecutado)
```

---

### **Cuando una Señal es RECHAZADA:**

```
 ETH/USDT - Signal: BUY (confidence: 62%)

 Portfolio REJECTED: Total exposure would be $1500 > $1000 (10%)
   Reason: Ya tienes $1000 en BTC, agregar ETH excedería límite
```

O:

```
 ETH/USDT - Signal: BUY (confidence: 62%)

 Portfolio REJECTED: Too many correlated positions
   BTC already open, ETH correlates with BTC
   Max correlated positions: 2
```

---

##  Monitoreo Avanzado

### **Ver solo señales de trading:**
```bash
./ver_logs.sh | grep "Signal:"
```

### **Ver solo trades ejecutados:**
```bash
./ver_logs.sh | grep "DRY RUN"
```

### **Ver rechazos de portfolio:**
```bash
./ver_logs.sh | grep "REJECTED"
```

---

## ⏱️ Frecuencia de Señales

**Normal:** 1-5 señales por hora (depende del mercado)

**Factores que afectan:**
- **Volatilidad del mercado:** Más volátil = más señales
- **Min Confidence:** Conservative (65%) = menos señales
- **Condiciones de mercado:** Sideways = pocas señales

**Si no ves señales después de 30 minutos:**
-  Normal si el mercado está estable
-  El bot sigue funcionando correctamente
-  Está esperando condiciones óptimas

---

##  Probar Generación de Señales

Si quieres ver señales más rápido para testing:

**Opción 1: Reducir min_confidence temporalmente**

Editar `.env`:
```bash
MIN_CONFIDENCE_THRESHOLD=0.50  # Reducir de 0.65 a 0.50
```

Reiniciar el bot:
```bash
./run_multi_symbol.sh
```

**Opción 2: Cambiar a perfil Moderate**

Editar `.env`:
```bash
TRADING_PROFILE=moderate  # Confidence 60% vs 65%
```

---

##  Estado del Sistema

### **Ver si está corriendo:**
```bash
ps aux | grep multi_symbol
```

### **Ver consumo de recursos:**
```bash
htop -p $(pgrep -f multi_symbol)
```

---

##  Detener el Bot

En la terminal donde corre:
```
Ctrl+C
```

O desde otra terminal:
```bash
pkill -f "multi_symbol"
```

---

**Recuerda:** En DRY_RUN mode, el bot **NO ejecuta órdenes reales**. Solo las simula y registra en logs.

Para trading real:
1. Cambiar `DRY_RUN=false` en `.env`
2. Asegurarte de tener fondos suficientes
3. Monitorear constantemente
