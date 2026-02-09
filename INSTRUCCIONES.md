# Ejecutar Trading Bot - Instrucciones

##  La migración está completa!

Todos los imports funcionan correctamente. Solo necesitas configurar tus API keys.

##  Pasos para ejecutar el bot:

### 1. Crear API Keys de Demo Mode

1. Ve a https://demo.binance.com/en/my/settings/api-management
2. Inicia sesión con tu cuenta de Binance regular
3. Crea una nueva API key
4. Copia tanto el **API Key** como el **Secret Key**

### 2. Configurar `.env`

Edita el archivo `.env` en la raíz del proyecto y actualiza estos valores:

```bash
# Reemplaza con tus claves de Demo Mode
BINANCE_TESTNET_API_KEY=tu_api_key_aquí
BINANCE_TESTNET_SECRET=tu_secret_key_aquí
```

### 3. Ejecutar el Bot

#### Opción A: PowerShell (Recomendado para Windows)
```powershell
.\run_bot.ps1
```

#### Opción B: Manualmente
```powershell
python orchestrator.py
```

#### Opción C: Bash (si tienes Git Bash)
```bash
bash run_multi_symbol.sh
```

##  Qué esperar ver:

```
 MULTI-SYMBOL FEED HANDLER (NATIVE BINANCE API)
Symbols: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
 ZeroMQ bound to tcp://127.0.0.1:5555
 Connected to Binance WebSocket
 Subscribed to 3 streams

MULTI-SYMBOL TRADING BOT
 Multi-Symbol Feed Handler (ZeroMQ Publisher)
 Multi-Symbol Trading Engine (ZeroMQ Subscriber)

 BTC/USDT - Signal: BUY (confidence: 67%)
 DRY RUN MODE - Trade NOT executed
```

##  Verificar que todo funciona:

```powershell
# Test de imports (ya funcionó )
python test_imports.py

# Test de connector (requiere API keys)
python -c "import sys; sys.path.insert(0, '.'); from apps.executor.testnet_connector import test_connection; import asyncio; asyncio.run(test_connection())"
```

## ️ Notas importantes:

1. **Demo Mode vs Testnet**: Ahora usas Demo Mode (mejores datos de mercado)
2. **DRY_RUN**: Por defecto está en modo simulación - no ejecutará trades reales
3. **API Keys**: Usa las keys de `BINANCE_TESTNET_API_KEY` y `BINANCE_TESTNET_SECRET` del `.env`

##  Solución de problemas:

### Error: "ModuleNotFoundError: No module named 'core'"
**Solución**: El script ya configura PYTHONPATH automáticamente. Si usas Python manualmente:
```powershell
$env:PYTHONPATH = "C:\Users\User\Desktop\trading-bot"
python orchestrator.py
```

### Error: "401 Unauthorized"
**Solución**: Necesitas crear API keys en https://demo.binance.com

### Error: "logs directory not found"
**Solución**: 
```powershell
mkdir logs
```

##  Cambios realizados:

-  Reem
plazado ccxt con API nativa de Binance
-  WebSocket nativo con auto-reconnection
-  REST API con HMAC SHA256 authentication
-  Soporte para Demo Mode de Binance
-  Imports funcionando correctamente

**¡Todo listo para ejecutar!** 
