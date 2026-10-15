# Changelog

## [Unreleased]

### Security
- `TRADING_MODE` (`dry_run` por defecto, `spot_demo`, `futures_testnet`, `live`); `live` exige `LIVE_TRADING_CONFIRM=I_UNDERSTAND`. Los perfiles de 1m (timeframe < 15m) se fuerzan a `dry_run` salvo `ALLOW_1M_LIVE=true`. `DRY_RUN=true` solo puede forzar `dry_run`; `USE_TESTNET` se ignora en el motor.

### Fixed
- Stop spot movido con `POST /api/v3/order/cancelReplace` (`STOP_ON_FAILURE`), con reintentos, reconciliación con las órdenes abiertas y alerta si la posición queda sin stop; el monitor vuelve a colocar stops perdidos.
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
