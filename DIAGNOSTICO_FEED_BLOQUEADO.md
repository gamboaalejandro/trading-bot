# 🔴 DIAGNÓSTICO: Feed Handler Bloqueado

## Problema

El feed handler se ejecuta pero "se queda pegado" sin mostrar actividad.

## Causa Probable

El código se está bloqueando en uno de estos puntos:

### **1. `exchange.load_markets()` - ALTO RIESGO**
```python
await self.exchange.load_markets()
```
**Por qué se bloquea:**
- Conexión lenta a Binance
- API rate limits
- Timeout de red
- Problemas con asyncio/ccxt

### **2. `exchange.watch_tickers()` - ALTO RIESGO**
```python
tickers = await self.exchange.watch_tickers(self.symbols)
```
**Por qué se bloquea:**
- WebSocket no conecta
- Binance rechaza la conexión
- Loop infinito esperando primer tick

### **3. ZMQ bind - MEDIO RIESGO**
```python
self.zmq_socket.bind(self.zmq_url)
```
**Por qué se bloquea:**
- Puerto 5555 ya en uso
- Permisos

---

## ✅ Solución Aplicada

Agregué logging DETALLADO en cada paso:

```python
logger.info("STEP 1: Setting up ZeroMQ...")
# ...
logger.info("✓ ZeroMQ bound to {self.zmq_url}")

logger.info("STEP 2: Initializing exchange...")
# ...
logger.info(f"✓ Loaded {len(markets)} markets from Binance")

logger.info("STEP 3: Starting ticker stream...")
logger.info(f"Watching tickers for: {self.symbols}")
```

---

## 🔍 Cómo Diagnosticar

**Reinicia el feed handler y observa DÓNDE se detiene el log:**

```bash
python3 -m apps.ingestion.feed_handler_daemon
```

**Casos:**

### **Caso A: Se detiene en STEP 1**
```
STEP 1: Setting up ZeroMQ...
[STUCK]
```
**Problema:** Puerto 5555 ocupado  
**Solución:**
```bash
lsof -i :5555
kill -9 <PID>
```

### **Caso B: Se detiene en STEP 2**
```
STEP 1: Setting up ZeroMQ...
✓ ZeroMQ bound...
STEP 2: Initializing exchange...
[STUCK]
```
**Problema:** No puede conectar a Binance  
**Solución:**
- Verificar internet
- Verificar API keys en `.env`
- Probar `curl https://testnet.binancefuture.com`

### **Caso C: Se detiene en STEP 3**
```
STEP 1: Setting up ZeroMQ...
✓ ZeroMQ bound...
STEP 2: Initializing exchange...
✓ Loaded 2000 markets...
STEP 3: Starting ticker stream...
Watching tickers for: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
[STUCK]
```
**Problema:** `watch_tickers()` no retorna  
**Causa:** WebSocket esperando primer mensaje

**ESTO ES NORMAL SI:**
- El mercado está cerrado (unlikely crypto)
- Binance no envía updates inmediatamente
- Espera un tick para empezar

**Espera 1-2 minutos**. Si sigue bloqueado:
```python
# El problema es que watch_tickers() nunca retorna el primer batch
```

---

## 🎯 Prueba Ahora

1. **Detén** el feed handler actual (Ctrl+C)

2. **Reinicia** con nuevo logging:
```bash
python3 -m apps.ingestion.feed_handler_daemon
```

3. **Observa** qué STEP se muestra último

4. **Comparte** el output para diagnosticar el problema exacto

---

## 🔧 Workaround Temporal

Si `watch_tickers()` está bloqueado, usar alternativa:

```python
# En lugar de watch_tickers (WebSocket)
# Usar fetch_tickers (REST API - polling)

while True:
    tickers = await exchange.fetch_tickers(symbols)
    # Publicar...
    await asyncio.sleep(1)  # Poll cada 1 segundo
```

Menos eficiente pero funciona SIEMPRE.

---

**Siguiente paso:** Reinicia feed handler y dime en qué STEP se queda bloqueado.
