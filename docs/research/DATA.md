# Datos históricos de Binance para backtesting

Generado el 2026-10-15. **No hay datos sintéticos.** Todo viene de dos repositorios públicos de GitHub. El contenedor no puede acceder a `*.binance.com`, `data.binance.vision`, HuggingFace, Kaggle ni CryptoDataDownload (el proxy devuelve 403 o hay timeout). Solo se reagregaron velas reales: las de futuros pasaron de 15m a 1h, 4h y 1d.

## Formato

- `spot/{SYMBOL}_{tf}.csv` y `futures/{SYMBOL}_{tf}.csv` tienen las columnas `timestamp,open,high,low,close,volume`.
  - `timestamp` es el **open time** de la vela, en ms UTC.
  - `volume` está en moneda base.
- `funding/{SYMBOL}.csv` tiene las columnas `timestamp,funding_rate`. Es una fracción: 0.0001 equivale a 0.01%.
- `meta/coverage.csv` guarda el resultado del control de calidad por archivo.
- `meta/futures_manifests/` contiene los manifiestos y el `verification_report.json` originales de la fuente de futuros, con sha256 y procedencia.
- Scripts: `/home/user/harness/scripts/normalize_data.py` y `/home/user/harness/scripts/check_data.py`. Para volver a correrlos hay que clonar otra vez las fuentes en `data/raw/bt` y `data/raw/sk`, porque los clones crudos se borraron.

## Fuentes (evidencia)

| Mercado | Repo | Commit | Licencia |
|---|---|---|---|
| Futuros USDT-M (perpetuos) y funding | https://github.com/kbsingh1399/Backtesting_Data (`Binance_Data/*_15m_master_2020_2026.parquet`) | `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47` (2026-10-02) | **No declarada** (no hay archivo LICENSE). Úsalo solo para investigación interna. |
| Spot | https://github.com/finom/static-klines (`.klines-cache/{SYM}/{tf}/*.json`, filas kline del REST de Binance, formato de 12 campos) | `4d33a56f2b3930376fc778522770c6e84855be7e` (2026-10-15) | **No declarada** en el repo ni en package.json. El README del repo dice: "Experimental — not audit-grade data… fine for backtests". |

## Cobertura

### Futuros USDT-M (18 símbolos; 15m nativo, 1h/4h/1d agregados)
Fin para todos: entre 2026-09-09 y 2026-09-10.
- Desde **2020-09-01**: BTC, ETH, BNB, XRP, DOGE, ADA, LINK, DOT, TRX, LTC, BCH.
- Inicio posterior: SOL 2020-09-14, AVAX 2020-09-23, NEAR 2020-10-15, OP 2022-06-01, APT 2022-10-19, ARB 2023-03-23, SUI 2023-05-03.
- Funding de los mismos 18 símbolos, con los mismos rangos (unas 6.600 filas cada uno en los símbolos completos).

### Spot (10 símbolos: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT)
Fin: 2026-10-15 (solo velas cerradas antes del commit).
- **15m**: desde 2024-12-30, para los 10 símbolos.
- **1h**: desde 2022-01-01, para los 10 símbolos (41.959 velas cada uno).
- **4h y 1d**: desde que el par existe en Binance. BTC y ETH empiezan el 2017-08-17, BNB el 2017-11-06, ADA el 2018-04-17, XRP el 2018-05-04, LINK el 2019-01-16, DOGE el 2019-07-05, SOL el 2020-08-11, DOT el 2020-08-18 y AVAX el 2020-09-22.

## Control de calidad (resultados de `check_data.py`)

- **Duplicados**: 0 en todos los archivos. **Velas OHLC inválidas** (high < max(o,c), low > min(o,c) o precio ≤ 0): 0. Todos los timestamps están alineados al timeframe.
- **Plausibilidad**: el cierre diario de BTC en 2021 fue de 29.3k a 67.5k en spot y de 29.3k a 67.6k en futuros, lo que coincide con lo esperado. Rangos de 2022: 15.8k a 47.7k. 2024: 39.6k a 106k. 2025: 76k a 125k.
- **Validación cruzada entre las dos fuentes independientes**: el `close` spot 15m de static-klines coincide **exactamente (100%)** con la columna `spot_close` del dataset de futuros. Se comprobó en BTC, ETH, SOL, DOGE y DOT, con unas 59.4k velas cada uno. La base futuros/spot tiene una mediana de unos -5 bps y |p99| < 0.25%, lo que es plausible.
- **Huecos en spot**:
  - En 1h hay un hueco de 2h, igual en los 10 símbolos, y 1 vela con volumen 0. Probablemente es un mantenimiento de Binance.
  - En 4h hay entre 0 y 8 huecos, todos en 2017-2019, el mayor de 32h. Coinciden con caídas conocidas del exchange. **No se rellenaron.**
- **Futuros (precaución)**:
  - La serie 15m no tiene **ningún hueco** en 6 años. La fuente rellenó las caídas: hay unas 6 velas por símbolo con volumen 0 y OHLC plano, por ejemplo en BTC el 2021-03-02 a las 01:15-01:45 y el 2022-05-28 a las 16:45-17:00.
  - En backtests conviene filtrar `volume == 0`.
  - Las velas 1h, 4h y 1d solo se emitieron cuando estaban presentes todas sus sub-velas de 15m.
- **Funding (derivado, no es el endpoint oficial)**: la fuente trae `funding_rate_pct` propagado a cada vela de 15m.
  - Se exportó el valor en cada frontera 00/08/16 UTC y en cualquier otra vela donde el valor cambió. Así quedan cubiertos los periodos con intervalo de 4h; hay pocos casos, por ejemplo en SOL.
  - Los cambios ocurren casi siempre a las 00/08/16, lo que es consistente con un funding liquidado y luego propagado. **No se pudo verificar contra la API oficial `fapi/v1/fundingRate`.**
  - Hay valores extremos: SOL llega a -2%, que cae en el periodo de FTX (nov-2022), y varios símbolos tocan el tope de -0.75%.
- La fuente de futuros marca `is_imputed_metrics` en muchas barras de 2022 (86% en BTC). Esa marca se refiere a métricas de OI y long/short, que **no se exportaron**. No afecta al OHLCV.

## Qué falta (no se consiguió)

- **Spot de TRX, LTC, BCH, NEAR, OP, APT, ARB y SUI**: static-klines solo cubre el top 10.
- **Spot 1h antes de 2022-01-01** y **spot 15m antes de 2024-12-30**. Se podrían reconstruir desde los repos de 1m por símbolo de https://github.com/parshant231234-eng (por ejemplo, `BTCUSDT-Historical-Data`), pero no se descargaron.
- **Futuros posteriores al 2026-09-10**: falta aproximadamente el último mes.
- **Funding oficial verificado, open interest y long/short**: no se exportaron. Están en la fuente como columnas extra, pero con imputación.
- **Datos de sentimiento** (Fear & Greed, etc.) y cualquier símbolo fuera de los 18 de futuros.
- **Licencias**: ninguna de las dos fuentes declara licencia.
