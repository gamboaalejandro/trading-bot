# Changelog

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
