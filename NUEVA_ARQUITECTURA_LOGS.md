#  NUEVA ARQUITECTURA DE LOGGING - Instrucciones

##  Sistema Actualizado

Ahora el bot escribe logs a archivos permanentes que puedes ver en cualquier momento.

---

##  Cómo Usar

### **PASO 1: Iniciar el Bot**

```bash
./run_multi_symbol.sh
```

### **PASO 2: Ver Logs en Tiempo Real**

```bash
./ver_logs_archivos.sh
```

Esto mostrará:
- `logs/feed_handler.log` - Lo que recibe de Binance
- `logs/trading_engine.log` - Señales y trades

---

##  Qué Verás

### **Feed Handler:**
```
2026-02-06 08:00:00 - INFO - Starting Multi-Symbol Feed Handler
2026-02-06 08:00:01 - INFO - Symbols: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
2026-02-06 08:00:05 - INFO - Published 100 total messages
2026-02-06 08:00:05 - INFO -   BTC/USDT: 35 msgs
2026-02-06 08:00:05 - INFO -   ETH/USDT: 33 msgs
2026-02-06 08:00:05 - INFO -   SOL/USDT: 32 msgs
```

### **Trading Engine:**
```
2026-02-06 08:00:10 - INFO - MULTI-SYMBOL TRADING ENGINE
2026-02-06 08:00:10 - INFO - Trading Profile: Conservative
2026-02-06 08:00:15 - INFO - BTC/USDT: Updated 100 candles, last at 2026-02-06 08:00:00
2026-02-06 08:00:20 - INFO - ETH/USDT: Updated 100 candles, last at 2026-02-06 08:00:00
2026-02-06 08:00:25 - INFO -  Processed 100 ticks total
```

---

##  Opción Alternativa: Todo Visible en Terminal

Si prefieres ver TODO directamente sin archivos:

### **Terminal 1: Feed Handler**
```bash
python3 -m apps.ingestion.feed_handler_daemon
```

### **Terminal 2: Trading Engine**
```bash
python3 -m apps.executor.multi_symbol_engine
```

**Ventaja:** Ves CADA log directamente en las terminales.

---

##  Archivos de Log

Los logs se guardan en:
- `logs/feed_handler.log`
- `logs/trading_engine.log`

Puedes verlos manualmente:
```bash
# Ver últimas 50 líneas
tail -50 logs/trading_engine.log

# Ver en tiempo real
tail -f logs/trading_engine.log

# Buscar señales
grep "Signal:" logs/trading_engine.log
```

---

##  Si SIGUE sin funcionar

Si después de esto **NO ves logs**, entonces hay un problema fundamental:

1. Los procesos no están iniciando
2. Hay un error de permisos en la carpeta `logs/`
3. Bug en el código que impide ejecución

En ese caso, ejecuta SOLO el feed handler manualmente:
```bash
python3 -m apps.ingestion.feed_handler_daemon
```

Y mira si ves output. Si SÍ lo ves, el problema era el orchestrator. Si NO lo ves, hay un bug más profundo.

---

**Próximo paso:** Ejecuta `./run_multi_symbol.sh` y luego `./ver_logs_archivos.sh` y comparte qué ves.
