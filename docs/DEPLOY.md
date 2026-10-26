# Despliegue del bot y auditoría

El bot (`apps/live/portfolio_executor.py`) corre **24/7 en una máquina tuya** (VPS o PC siempre encendido).
Las sesiones de Claude en la nube son efímeras (se reinician y se reciclan), así que **no** sirven para tener el bot operando.
La auditoría se hace leyendo lo que el bot publica en la rama `audit-logs` de GitHub.

```
 tu VPS / PC                                   GitHub (repo privado)             Claude
 ┌───────────────────────────┐   cron diario   ┌─────────────────────┐  lee   ┌──────────────┐
 │ docker: portfolio_executor│ ─────────────▶  │ rama audit-logs     │ ─────▶ │ auditoría    │
 │ data/live/*.jsonl (journal)│ export_audit.sh│ live/*.jsonl, REPORT│        │ (sesión o    │
 └───────────────────────────┘                 └─────────────────────┘        │  programada) │
            │  órdenes (claves solo aquí, en .env)                            └──────────────┘
            ▼
         Binance (spot demo / futures testnet / live)
```

## 1. Máquina

- Recomendado: VPS Linux pequeño (1 vCPU, 1-2 GB RAM) **en un país con acceso a Binance**, con IP fija para la whitelist de las claves.
- Requisitos: `git`, `docker` + `docker compose` (o Python 3.13 si no usas Docker).

## 2. Instalación

```bash
git clone https://github.com/gamboaalejandro/trading-bot.git
cd trading-bot && git checkout main
cp .env.example .env        # .env está en .gitignore: NUNCA se sube
nano .env                    # rellena las claves y el modo (ver abajo)
```

Contenido mínimo de `.env` para la **fase (a), demo/testnet**:

```
BINANCE_TESTNET_API_KEY=...          # Spot Demo (demo.binance.com > API Management)
BINANCE_TESTNET_API_SECRET=...
BINANCE_FUTURES_TESTNET_API_KEY=...  # Futures Testnet (testnet.binancefuture.com)
BINANCE_FUTURES_TESTNET_API_SECRET=...
TRADING_MODE=spot_demo
BOT_ENGINE=T3
BOT_SYMBOLS=BTCUSDT,ETHUSDT          # vacío = universo de 10 monedas
```

Claves siempre **sin permiso de retiro** y con **whitelist de IP** de la VPS.

## 3. Comprobar conexión (solo lectura)

```bash
set -a; source .env; set +a
pip install -r requirements.txt -r requirements-research.txt   # o usa el contenedor
python scripts/check_connection.py            # debe terminar con código 0
python -m apps.live.portfolio_executor --engine T3 --symbols BTCUSDT,ETHUSDT --once   # una ejecución
```

## 4. Arrancar 24/7

```bash
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f bot
```

El bot decide una vez al día (00:05 UTC) y reconcilia con el exchange cada 5 minutos. El estado y el journal quedan en `data/live/` (persisten aunque reinicies).
Parar: `docker compose -f deploy/docker-compose.yml down`.

## 5. Publicar los datos para la auditoría

```bash
crontab -e
# 00:15 UTC, después de la ejecución diaria:
15 0 * * * cd /ruta/a/trading-bot && scripts/export_audit.sh >> logs/export_audit.log 2>&1
```

El script copia `data/live/*.json(l)` a la rama `audit-logs`, genera `REPORT.md` con `scripts/audit_report.py` y hace push.
Aborta si detecta algo con forma de clave (64 caracteres). Para hacer push necesita credenciales de git en la VPS
(deploy key con permiso de escritura o token de GitHub).

Informe local en cualquier momento: `python scripts/audit_report.py --days 30`.

## 6. Grabación de datos de mercado (recorder)

El servicio `recorder` del mismo `docker compose` graba datos públicos de futuros USDT-M (sin claves, no opera)
en `data/recorders/<stream>/<día>.jsonl` (los días cerrados se comprimen en `.gz`):

| stream | fuente | frecuencia | tamaño aprox. (18 monedas, sin comprimir) |
|---|---|---|---|
| `open_interest` | `/fapi/v1/openInterest` | 5 min | ~0.5 MB/día |
| `global_lsr`, `top_lsr`, `taker_ratio` | `/futures/data/*` | 5 min | ~2.3 MB/día |
| `premium_index` (mark, índice, funding previsto) | `/fapi/v1/premiumIndex` | 1 min | ~8.6 MB/día |
| `funding` (oficial; historial completo en el primer arranque) | `/fapi/v1/fundingRate` | 8 h | ~12 MB una vez |
| `liquidations` | WS `!forceOrder@arr` | continuo | 1-6 MB/día (hasta ~50 MB en días de pánico) |

Total: ~13-18 MB/día sin comprimir (~5-6.5 GB/año) y **~0.6-1 GB/año comprimido**. Un disco de 20 GB sobra.
Prueba rápida: `python -m apps.live.recorders --once`.

## 7. Fases

| fase | `TRADING_MODE` | duración | criterio para avanzar |
|---|---|---|---|
| (a) demo/testnet | `spot_demo` (y `futures_testnet` en paralelo) | ≥ 4 semanas | 0 incidencias de ejecución, slippage dentro del modelo |
| (b) real pequeño | `live` + `LIVE_TRADING_CONFIRM=I_UNDERSTAND` + claves de producción | 1-3 meses | igual que (a); **no** se juzga por el P&L |
| escalar | — | — | solo si un motor pasa el gate en un ciclo nuevo de investigación |

Límites de riesgo: `config/risk_limits.yml` (-2%/-5% diario, 10%/20% drawdown). Ver `docs/research/results/FINAL_REPORT.md` §7.
