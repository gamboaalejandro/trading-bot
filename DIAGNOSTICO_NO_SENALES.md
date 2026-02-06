# 🔴 Diagnóstico: Por qué el bot no hizo nada en 7 horas

## Problemas Encontrados

### **1. El engine NO está generando logs**
Después de 7 horas corriendo, cuando intenté ver los últimos 50 logs del engine, **no retornó NADA**.

**Esto significa:**
- ❌ NO está procesando ticks
- ❌ NO está actualizando candles
- ❌ NO está ejecutando estrategias
- ❌ Posiblemente está bloqueado o en un loop infinito sin logs

---

### **2. Logging insuficiente**
El código actual usa `logger.debug()` para actividad normal, que por defecto NO se muestra (solo INFO y superior).

**Cambios aplicados:**
```python
# Antes
logger.debug(f"{symbol}: Updated {len(df)} candles...")

# Ahora
logger.info(f"{symbol}: Updated {len(df)} candles...")
```

---

### **3. No hay confirmación de actividad**
No había forma de saber si el bot estaba realmente procesando datos o simplemente "colgado".

**Solución:**
- Agregado contador de ticks
- Log cada 100 ticks: `📊 Processed 100 ticks total`
- Log cuando NO hay señales (para saber qué está pasando)

---

## ✅ Cambios Aplicados

### **1. Logging de Actualización de Candles**
```python
# Línea 276
logger.info(f"{symbol}: Updated {len(df)} candles, last at {self.last_candle_time[symbol]}")
```

**Efecto:** Ahora verás actividad cuando el bot actualiza datos.

---

### **2. Logging de Señales No Actionables**
```python
# Líneas 307-314
if signal:
    logger.debug(f"{symbol}: Signal below threshold ({signal.confidence:.2%} < {min_conf:.2%})")
else:
    logger.debug(f"{symbol}: No signal generated")
```

**Efecto:** Sabrás por qué no se ejecutan trades.

---

### **3. Contador de Ticks**
```python
# Línea 240-242
self.tick_count += 1
if self.tick_count % 100 == 0:
    logger.info(f"📊 Processed {self.tick_count} ticks total")
```

**Efecto:** Confirmación cada 100 ticks de que el sistema está vivo.

---

## 🔍 Próximos Pasos para Diagnosticar

### **1. Reiniciar con nuevo logging**
```bash
# Detener procesos viejos
pkill -f "multi_symbol"

# Reiniciar
./run_multi_symbol.sh
```

### **2. Ver logs en vivo**
```bash
# En otra terminal
./ver_logs.sh
```

**Deberías ver AHORA:**
```
2026-02-06 08:00:00 - INFO - BTC/USDT: Updated 100 candles, last at 2026-02-06 08:00:00
2026-02-06 08:00:05 - INFO - ETH/USDT: Updated 100 candles, last at 2026-02-06 08:00:05
2026-02-06 08:00:10 - INFO - SOL/USDT: Updated 100 candles, last at 2026-02-06 08:00:10
2026-02-06 08:01:00 - INFO - 📊 Processed 100 ticks total
```

---

### **3. Si SIGUE sin logs**

Entonces el problema está en el feed handler o la conexión ZeroMQ:

**Verificar feed handler:**
```bash
FEED_PID=$(ps aux | grep feed_handler_daemon | grep -v grep | awk '{print $2}')
tail -f /proc/$FEED_PID/fd/2
```

**Deberías ver:**
```
Published 100 total messages
  BTC/USDT: 30 msgs
  ETH/USDT: 35 msgs
  SOL/USDT: 35 msgs
```

---

## 📊 Razones Normales para No Ver Señales

Incluso con el sistema funcionando, es NORMAL no ver señales si:

### **1. Mercado en rango (sideways)**
- Mean Reversion: necesita oversold/overbought
- Momentum: necesita tendencia fuerte
- Si BTC está en $42k-$43k durante horas → no hay señales

### **2. Confidence threshold alto (60-65%)**
- Conservative profile es MUY restrictivo
- Solo señales de muy alta calidad pasan

### **3. Condiciones no se cumplen**
Ejemplo BTC Mean Reversion necesita:
- RSI < 30 (oversold) OR RSI > 70 (overbought)
- Precio cerca de banda de Bollinger
- Volumen adecuado

Si BTC está en RSI 45-55 (neutral) → no hay señal.

---

## 🎯 Prueba Rápida: Reducir Threshold

**Para testing, bajar confidence temporalmente:**

Editar `.env`:
```bash
MIN_CONFIDENCE_THRESHOLD=0.40  # Bajar de 0.60 a 0.40
```

Reiniciar:
```bash
pkill -f "multi_symbol"
./run_multi_symbol.sh
```

Deberías ver señales más frecuentes (aunque de menor calidad).

---

## 🔴 Si Después de Esto NO Ves Logs

Entonces hay un bug crítico en el engine. Posibles causas:

1. **ZeroMQ no está conectando**
   - Feed handler publica pero engine no recibe

2. **Excepción silenciosa**
   - Error en try/except que no se loggea

3. **Loop infinito sin await**
   - Código bloqueado en algún lado

En ese caso, necesitaríamos run en modo debug directo:
```bash
python3 -m apps.executor.multi_symbol_engine
```

Y ver la salida completa en stdout para identificar el problema.

---

**Resumen:** Agregué logging crítico. Reinicie el bot y verifique si ahora ve actividad en los logs.
