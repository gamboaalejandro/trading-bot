# Changelog

## [2.0.0] - 2026-10-16

Rediseño completo: investigación, backtesting riguroso y ejecución spot + futuros.

### Added
- `docs/research/`: 7 informes de investigación, PLAN.md (debate de 5 perspectivas) y resultados E0-E10 con `FINAL_REPORT.md`.
- `apps/research/`: loader de datos reales, features causales, motores de backtest (cartera diaria y eventos) con comisiones, slippage, funding y liquidación, estrategias TREND/SHORT/REGIME/FVETO/BRK4H/PULLBACK/SHOCK/CARRY, benchmarks nulos, walk-forward, DSR/PBO, gate A/B/C, score de adaptabilidad, TrialsLog append-only y CLI `python -m apps.research.run`.
- `apps/live/`: ejecutor diario de cartera (velas cerradas, IDs idempotentes, stop inmediato tras fill), reconciliación con el exchange, kill-switch con `config/risk_limits.yml`, `--symbols` para cuentas pequeñas.
- `core/binance_futures_client.py` (margen aislado, one-way, stops vía `/fapi/v1/algoOrder`), `core/secrets.py`, `.env.example`, `scripts/check_connection.py`, `scripts/fetch_official_audit_data.py`.

### Changed
- `TRADING_MODE` (`dry_run` por defecto, `spot_demo`, `futures_testnet`, `live` con `LIVE_TRADING_CONFIRM`); el bot legado de 1m queda forzado a dry-run.
- Stop spot movido con `cancelReplace` (STOP_ON_FAILURE); el backtester legado ya no genera datos simulados.

### Resultado de la investigación
- Ninguna estrategia pasa el gate (todas nivel C); el holdout no se abrió. Recomendación: operar solo para validar la ejecución (testnet y luego 100 USD en BTC/ETH spot).

## [Unreleased]

### Security
- `TRADING_MODE` (`dry_run` por defecto, `spot_demo`, `futures_testnet`, `live`); `live` exige `LIVE_TRADING_CONFIRM=I_UNDERSTAND`. Los perfiles de 1m (timeframe <= 15m) y el motor legado `multi_symbol_engine` (con cualquier `DEFAULT_TIMEFRAME`) se fuerzan a `dry_run` salvo `ALLOW_1M_LIVE=true`. `DRY_RUN=true` solo puede forzar `dry_run`; `USE_TESTNET` se ignora en el motor.

### Fixed
- Stop spot movido con `POST /api/v3/order/cancelReplace` (`STOP_ON_FAILURE`), con reintentos, reconciliación con las órdenes abiertas y alerta si la posición queda sin stop; el monitor vuelve a colocar stops perdidos.
- Stop spot desaparecido (`-2011` o resultado desconocido sin stop abierto): se consulta la orden antigua y el saldo del activo base antes de actuar; si se ejecutó (`FILLED`) o el saldo no cubre la posición se registra el cierre por stop del exchange y no se recoloca. Un fallo al listar órdenes abiertas ya no se interpreta como "sin stop".
- `apps/analytics/backtester.py` marcado DEPRECATED: sin `_generate_mock_data` ni fallback, cualquier fallo de descarga lanza `BacktestDataError`.
- WebSocket: `BinanceWebSocket.closed_kline` solo devuelve velas con `x == true`.

## [1.1.0] - 2026-10-15

Correcciones de la auditoría del bot (spot).

### Fixed
- Orquestador: la salida de los procesos va a `logs/` en vez de pipes sin leer que congelaban el feed y el motor.
- Motor: señales solo sobre velas cerradas, con historial suficiente para EMA200 y MA200 (antes 110 velas); sin llamada REST por tick.
- Spot: no se abren ventas sin posición; cantidades reales ejecutadas netas de comisión; tamaño limitado por USDT libre y mínimo notional; `orderId` correcto; redondeo hacia abajo a `stepSize`.
- Riesgo: kill switch de pérdida diaria conectado al PnL realizado; `max_positions` y `max_daily_trades` aplicados; sentimiento refrescado cada hora.
- E/S: llamadas HTTP fuera del event loop (`asyncio.to_thread`); caché de `exchangeInfo`; feed WebSocket alineado con `USE_TESTNET`.
- Stop loss colocado como orden `STOP_LOSS` real en Binance (movido en trailing/breakeven) y posiciones persistidas en `state/open_positions.json`.

### Added
- Tests de regresión con pytest (`tests/`).
