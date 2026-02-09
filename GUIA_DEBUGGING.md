#  Cómo Ver Prints y Logs del Trading Bot

## Diferencia entre print() y logger

**`print()`** → Va a **stdout** (file descriptor 1)
**`logger.info()`** → Va a **stderr** (file descriptor 2)

---

##  Opción 1: Usar ver_logs.sh (Actualizado)

```bash
./ver_logs.sh
```

Ahora muestra **ambos** (stdout + stderr), por lo que verás:
-  Tu `print("Dry Run: ", dry_run)`
-  Todos los logs del logger

---

##  Opción 2: Ejecutar Directamente

Si ejecutas el engine directamente (sin orchestrator), verás todo en la terminal:

```bash
# Terminal 1: Feed Handler
python3 -m apps.ingestion.feed_handler_daemon

# Terminal 2: Trading Engine
python3 -m apps.executor.multi_symbol_engine
```

Aquí **SÍ** verás los prints directamente en la terminal.

---

##  Opción 3: Ver Manualmente

```bash
# Obtener PID del engine
ENGINE_PID=$(ps aux | grep multi_symbol_engine | grep -v grep | awk '{print $2}')

# Ver SOLO prints (stdout)
tail -f /proc/$ENGINE_PID/fd/1

# Ver SOLO logs (stderr)
tail -f /proc/$ENGINE_PID/fd/2

# Ver AMBOS
tail -f /proc/$ENGINE_PID/fd/1 /proc/$ENGINE_PID/fd/2
```

---

##  Recomendación para Ver Todo

**Mejor forma:**
```bash
# Iniciar
./run_multi_symbol.sh

# Ver logs completos
./ver_logs.sh
```

Ahora verás tu print cuando el engine inicie:
```
Dry Run:  False
```

---

##  Tip para Debugging

Si quieres ver prints en tiempo real durante desarrollo:

**Usar logger en lugar de print:**
```python
# Antes
print("Dry Run: ", dry_run)

# Mejor
logger.info(f" Dry Run Mode: {dry_run}")
```

**Ventajas:**
-  Siempre visible en logs
-  Incluye timestamp
-  Incluye nivel (INFO, ERROR, etc.)
-  Más profesional
