# 04 — Futuros perpetuos USDT-M de Binance: funding, OI, liquidaciones, basis, apalancamiento, costes, API y estrategias

Fecha: 2026-10-15. Autor: subagente investigador cuantitativo (punto de vista: analítico/crítico).

> **Nota metodológica (importante).** Desde este contenedor **WebFetch/curl no pudo abrir ninguna fuente** (DNS/proxy bloquea binance.com, developers.binance.com, arxiv.org, bitmex.com, bis.org…). Las fuentes se conocen a través de **resúmenes de WebSearch** (abstracts, fragmentos de FAQ, resúmenes secundarios). Sí pude **descargar desde PyPI** el código de `ccxt 4.5.88` y `binance-futures-connector 4.2.0` y **clonar** `github.com/binance/binance-public-data`, de donde salen las rutas de endpoints, pesos (weights) y límites de históricos citados en §5 (verificado en código, no en la doc web).
> - **[EVIDENCIA]** = respaldada por una fuente citada.
> - **[CÓDIGO]** = verificado leyendo el código fuente de las librerías oficiales/ccxt descargadas.
> - **[CONOCIMIENTO PREVIO – VERIFICAR]** = dato que conozco pero que no pude confirmar con una fuente abierta en esta sesión; debe validarse contra la API en vivo (p. ej. `exchangeInfo`, `leverageBracket`, `commissionRate`) antes de usarlo en producción.
> - **[OPINIÓN]** = juicio propio / decisión de diseño.

---

## 1. Resumen ejecutivo

1. **[EVIDENCIA]** El funding de Binance USDT-M es `F = P̄ + clamp(I − P̄, −0.05%, +0.05%)`, con `I` = 0.01% por intervalo de 8h (0.03%/día) por defecto. En la práctica, cuando el premium medio está entre −0.04% y +0.06%, el funding queda **exactamente en 0.01%/8h** ([Binance FAQ](https://www.binance.com/en/support/faq/introduction-to-binance-futures-funding-rates-360033525031), [mirror](https://www.binance.info/en/support/faq/detail/360033525031)). Un análisis secundario reporta que ~78% de un trimestre el funding estuvo en 0.01% ([Coincub](https://coincub.com/?p=14476)). Consecuencia: **el funding "normal" no contiene información**; solo las desviaciones del 0.01% la contienen.
2. **[EVIDENCIA]** Los intervalos ya **no son siempre 8h**: Binance cambia símbolos a 4h, 2h o 1h, con caps de hasta ±3% por intervalo en algunos altcoins, y desde 2025-09-01 existe una regla automática de vuelta de 1h a 4h ([ChainCatcher](https://www.chaincatcher.com/en/article/2196595), [Odaily](https://www.odaily.news/en/newsflash/337143), [TechFlow](https://www.techflowpost.com/en-US/newsletter/75976)). **El bot debe leer el intervalo por símbolo** (`GET /fapi/v1/fundingInfo`) y anualizar con él, nunca asumir 3 pagos/día.
3. **[EVIDENCIA]** La "prima" futuro–spot (carry) en cripto es grande y variable (puede superar 40% anual) y se explica por demanda apalancada de inversores pequeños que persiguen tendencia + capital de arbitraje limitado (BIS WP 1087, Schmeling, Schrimpf & Todorov, [BIS](https://www.bis.org/publ/work1087.htm), [PDF](https://www.bis.org/publ/work1087.pdf)). El mismo trabajo reporta que el carry **predice liquidaciones de cortos**: +10% de carry estandarizado ≈ +22% en liquidaciones de venta relativas a OI el mes siguiente (según resumen de WebSearch).
4. **[EVIDENCIA]** He, Manela, Ross & von Wachter (*Fundamentals of Perpetual Futures*, arXiv 2212.06888) muestran desviaciones perp–spot mucho mayores que en divisas, que co-mueven entre criptos y **se reducen con la madurez del mercado**; una estrategia simple obtiene Sharpe alto incluso con las comisiones más altas de Binance ([arXiv abs v6](https://arxiv.org/abs/2212.06888v6), [HTML v5](https://arxiv.org/html/2212.06888v5)). **No pude leer las cifras exactas** [VERIFICAR-PDF]. El hecho de que las desviaciones se reduzcan con el tiempo es una advertencia de **decaimiento del alfa**.
5. **[EVIDENCIA, mixta]** El carry delta-neutral (spot largo + perp corto) es la única estrategia "de futuros" con respaldo académico serio, pero:
   - Un resumen de Borri, Liu, Tsyvinski & Wu (arXiv 2510.14435) indica que el carry tiene media ≈8% con volatilidad ≈0.8% en muestra completa, **pero Sharpe negativo en 2025** (fragmento de WebSearch, no confirmado en el PDF) ([arXiv](https://arxiv.org/html/2510.14435v3), [Quantpedia](https://quantpedia.com/cryptocurrency-as-an-investable-asset-class-10-lessons/)).
   - Un estudio MDPI 2026 sobre oportunidades de funding entre venues encuentra que **solo el 40%** de las mejores oportunidades son rentables tras costes y spread, con **salidas forzadas en el 95%** de los casos ([MDPI Mathematics 14(2):346](https://www.mdpi.com/2227-7390/14/2/346)).
   - Cifras de 100%+ anual (Springer 2026 CEX–DEX; "115.9% en 6 meses" citado en Medium) son **outliers** con supuestos no verificados → tratarlas como sospechosas ([Springer](https://link.springer.com/article/10.1007/s42521-026-00213-3), [Medium](https://arbitrageghost.medium.com/funding-rate-arbitrage-in-2026-the-complete-guide-with-real-calculations-40e6cf341e52)).
6. **[EVIDENCIA, débil]** "Funding extremo como señal contraria": los datos a favor (VanEck, K33, Real Vision) son **no académicos, con 7–14 episodios**, sin test fuera de muestra. BitMEX, el análisis más riguroso de los encontrados, concluye que el funding **no tiene poder predictivo significativo** sobre el retorno de las 8h siguientes en una regresión simple, y que el PnL de su estrategia contraria venía **del cobro del funding, no del precio** ([BitMEX blog](https://www.bitmex.com/blog/xbtusd-funding-mean-reversion-strategy), [The Block/K33](https://www.theblock.co/post/315831/perp-signal-bitcoin-bottom-bullish-year-end-k33)).
7. **[EVIDENCIA, negativa]** Señales cross-sectional de funding + OHLCV a 8h en 10 perps de Binance (jul-2022 a abr-2026): IC ≈ 0 y **Sharpe neto negativo** (Fayez Junior, SSRN 6701738, [PDF](https://papers.ssrn.com/sol3/Delivery.cfm/6701738.pdf?abstractid=6701738&mirid=1)). Es un único estudio, pero es justamente el diseño que un bot ingenuo implementaría.
8. **[EVIDENCIA, ausencia]** Long/short ratio de Binance: **no encontré ningún test riguroso** de su poder predictivo; solo afirmaciones de vendedores de datos con umbrales sin metodología ([sharpe.ai](https://www.sharpe.ai/futures/bitcoin/long-short-ratio)). Un preprint sobre 7 cascadas de liquidación en BTCUSDT encuentra que las señales de alerta temprana (OI, L/S global, flujo taker) **no se replican entre eventos** ([arXiv 2607.27070](https://arxiv.org/html/2607.27070v1)).
9. **[OPINIÓN]** Para el bot: (a) el carry delta-neutral es la estrategia de futuros con mejor relación evidencia/riesgo, pero su rendimiento es **muy dependiente del régimen** (alcista apalancado) y debe activarse solo con funding alto; (b) funding/OI/L-S deben usarse principalmente como **filtros de riesgo y de régimen** (evitar entrar largo en "crowded longs", reducir apalancamiento) y **no como generadores de señal autónomos**; (c) el apalancamiento debe ser bajo (≤2–3x) y la distancia a liquidación ≥3× la distancia al stop.

---

## 2. Mecánica: hallazgos con evidencia

### 2.1 Funding rate
| Elemento | Detalle | Fuente / estatus |
|---|---|---|
| Fórmula | `F = P̄ + clamp(I − P̄, −0.05%, +0.05%)` | [EVIDENCIA] [Binance FAQ](https://www.binance.com/en/support/faq/introduction-to-binance-futures-funding-rates-360033525031) |
| Tipo de interés `I` | 0.03%/día = 0.01% por 8h; 0% en ETHBTC; Binance puede cambiarlo | [EVIDENCIA] misma FAQ |
| Premium index | `P = [max(0, ImpactBid − PriceIndex) − max(0, PriceIndex − ImpactAsk)] / PriceIndex` | [CONOCIMIENTO PREVIO – VERIFICAR]; la FAQ confirma que se basa en impact bid/ask vs price index |
| Impact Margin Notional | `IMN = 200 USDT / initial margin rate` a máximo apalancamiento (p. ej. 20x → 4.000 USDT) | [EVIDENCIA] FAQ (vía resumen WebSearch) |
| Promedio de P | Media **ponderada por tiempo** (peso creciente) de muestreos del premium durante el intervalo | [CONOCIMIENTO PREVIO – VERIFICAR]; un script de TradingView admite que "el método exacto no está claro" ([TV](https://in.tradingview.com/script/NAgcIjlZ)) |
| Ajuste por intervalo | Un artículo afirma que desde 2025-09-18 la fórmula se escala por `N/8` (N = horas del intervalo) | [EVIDENCIA DÉBIL, 1 fuente secundaria] ([Futu](https://news.futunn.com/en/post/62346087/how-does-binance-s-algorithm-update-cut-off-the-fee)) |
| Caps / floors | Por símbolo; ±0.05% hasta ±3% por intervalo según contrato; se consultan en `fundingInfo` | [EVIDENCIA] anuncios citados en §1.2; campos `adjustedFundingRateCap/Floor`, `fundingIntervalHours` [CÓDIGO: docstring connector] |
| Pago | `Funding fee = tamaño × MarkPrice × F`; F>0 ⇒ largos pagan a cortos; solo si tienes posición **en el instante** de settlement | [CONOCIMIENTO PREVIO – VERIFICAR] (estándar de la industria) |
| Horarios | Contratos 8h: 00:00, 08:00, 16:00 UTC; resto según `fundingIntervalHours` | [CONOCIMIENTO PREVIO – VERIFICAR] |

**Variables cuantitativas derivadas (exactas, para implementar):**
- `n_dia = 24 / fundingIntervalHours`
- `funding_APR = F_medio × n_dia × 365` (simple, sin componer). Ejemplo: 0.01%/8h → 0.0001×3×365 = **10.95% APR**.
- `funding_dev = F − I_intervalo` (lo único informativo), con `I_intervalo = 0.0001 × fundingIntervalHours / 8` [OPINIÓN: escalado coherente con la regla N/8; verificar].
- `funding_z = (F_media_7d − media_365d) / std_365d` por símbolo (los altcoins tienen distribuciones muy distintas a BTC).
- `funding_pctl` = percentil del F medio de 3 días frente a su propio histórico de 1 año.

### 2.2 Basis
- **[EVIDENCIA]** BIS WP 1087 define carry = diferencia futuro–spot; puede superar 40% anual y está ligada a demanda apalancada minorista ([BIS](https://www.bis.org/publ/work1087.htm)).
- Para perps: `basis_bps = (MarkPrice − IndexPrice)/IndexPrice × 1e4`, o la serie `premiumIndexKlines` (OHLC del premium) [CÓDIGO]. Para trimestrales: `basis_anual = (F_q/S − 1) × 365/días_a_vencimiento`; endpoint `GET /futures/data/basis` (`contractType`= PERPETUAL/CURRENT_QUARTER/NEXT_QUARTER) [CÓDIGO: ccxt `fapiData basis`].

### 2.3 Open interest (OI)
- `GET /fapi/v1/openInterest` (instantáneo) y `GET /futures/data/openInterestHist` (periodos 5m…1d, **solo últimos 30 días**, máx 500 filas) [CÓDIGO].
- **[EVIDENCIA]** Existen ficheros diarios públicos `data/futures/um/daily/metrics/<SYMBOL>/` en data.binance.vision con OI (en contratos y en valor), ratios top-trader/global y ratio taker ([issue #211 binance-public-data](https://github.com/binance/binance-public-data/issues/211)) — **esta es la única vía para backtests largos de OI/L-S**. El repo oficial también trae scripts para `markPriceKlines`, `premiumIndexKlines`, `indexPriceKlines` desde 2020 [CÓDIGO: `binance-public-data/python/README.md`].
- **[EVIDENCIA]** El preprint arXiv 2607.27070 no encuentra señales de OI que se repliquen entre cascadas.

### 2.4 Liquidaciones
- Datos públicos: **solo websocket** `!forceOrder@arr` (todas) o `<symbol>@forceOrder`. **Solo se envía la última liquidación por símbolo cada 1000 ms** → el stream **infra-cuenta** las liquidaciones en cascadas [CÓDIGO: docstring `liquidation_order` del connector]. `GET /fapi/v1/forceOrders` es **privado** (solo tus propias liquidaciones; weight 20, 50 sin símbolo) [CÓDIGO].
- **[EVIDENCIA]** arXiv 2607.27070 confirma que el dato público carece de registro intradía completo de liquidaciones. Implicación: **no hay histórico de liquidaciones para backtest** salvo grabarlo uno mismo (o proveedores de pago tipo Coinglass, no accesibles aquí).

### 2.5 Long/short ratio
- Endpoints: `globalLongShortAccountRatio` (cuentas, todos), `topLongShortAccountRatio` (cuentas top traders), `topLongShortPositionRatio` (posición top traders), `takerlongshortRatio` (volumen taker comprador/vendedor). Todos en `/futures/data/`, periodos 5m–1d, **30 días** de historial vía API [CÓDIGO].
- **[EVIDENCIA]** En venues minoristas (Binance) el ratio de cuentas está estructuralmente >1 ([sharpe.ai](https://www.sharpe.ai/futures/bitcoin/long-short-ratio)) → usar z-score por símbolo, no umbrales absolutos. Umbrales tipo ">2.8 ⇒ caída 71% de las veces" son **anecdóticos sin metodología** ([blog](https://sites.google.com/view/decentralised-news/home/longshort-ratio-analysis)).

### 2.6 Margen, apalancamiento y matemática de liquidación
- **[EVIDENCIA]** Binance define las variables oficiales: `WB` (wallet balance: cruzado o aislado), `TMM1` (maintenance margin de los demás contratos), `UPNL1` (PnL no realizado de los demás), `cumB/cumL/cumS` (maintenance amount del tier), y en aislado `TMM1 = UPNL1 = 0`. Si el notional a precio de liquidación cae en otro tier, hay que recalcular con ese tier ([Binance FAQ liquidación](https://www.binance.com/en/support/faq/how-to-calculate-liquidation-price-of-usd%E2%93%A2-m-futures-contracts-b3c689c1f50a44cabb3a84e663b81d93), [foro dev](https://dev.binance.vision/t/how-to-calculate-cumb-while-calculating-liquidation-price/883)).
- Fórmula one-way (BOTH) [CONOCIMIENTO PREVIO – VERIFICAR, consistente con las variables anteriores]:

  `LP = (WB − TMM1 + UPNL1 + cumB − Side·Q·EP) / (Q·MMR_B − Side·Q)`, con `Side=+1` largo, `−1` corto, `Q` = tamaño absoluto, `EP` = precio de entrada.

  Comprobación aislada con `cumB=0`, `WB = Q·EP/L`: largo → `LP = EP·(1 − 1/L)/(1 − MMR)`; corto → `LP = EP·(1 + 1/L)/(1 + MMR)`. Aproximación habitual: largo `≈ EP·(1 − 1/L + MMR)` ([ejemplo spark.money](https://www.spark.money/tools/liquidation-price-calculator)).
- Maintenance margin = `notional × MMR_tier − maintenance_amount_tier`; tiers por símbolo desde `GET /fapi/v1/leverageBracket` (privado, firmado) [CÓDIGO]. Los MMR de BTCUSDT en el tier más bajo rondan 0.4% según fuentes secundarias ([spark.money](https://www.spark.money/tools/liquidation-price-calculator)); **altcoins tienen MMR mucho mayores** → leerlos siempre de la API.
- Liquidación se dispara con **Mark Price**, no con last price [CONOCIMIENTO PREVIO – VERIFICAR] → los stops del bot deben razonarse sobre mark price (`workingType=MARK_PRICE` en órdenes STOP_MARKET) [OPINIÓN].
- **Aislado vs cruzado [OPINIÓN]:** para un bot multi-moneda, **aislado** por posición direccional (el riesgo de una altcoin no contamina la cuenta); **cruzado** solo para la pata corta del carry delta-neutral, porque necesita colchón grande y rebalanceo, y su riesgo direccional está cubierto por el spot (que, ojo, está en otra cuenta: el spot **no** cuenta como margen del perp salvo Portfolio Margin).

**Regla dura de riesgo (implementable) [OPINIÓN]:**
`dist_liq = |EP − LP| / EP`; `dist_stop = |EP − SL| / EP`. Rechazar la orden si `dist_liq < 3 × dist_stop` o si `L > L_max(símbolo)` (L_max = 3 para BTC/ETH, 2 para el resto).

### 2.7 Comisiones (VIP0) y break-even
| Mercado | Maker | Taker | Descuento BNB | Fuente |
|---|---|---|---|---|
| Spot | 0.10% | 0.10% | 25% (→0.075%) | [EVIDENCIA] [CryptoPotato](https://cryptopotato.com/binance-fees/), [Finhay](https://www.finhay.com.vn/en/phi-giao-dich-binance) |
| USDT-M futuros | 0.02% | 0.05% | 10% (BNB en cuenta de futuros) | [EVIDENCIA] [Binance support 360033544231](https://www.binance.com/es/support/articles/360033544231), [CryptoPotato](https://cryptopotato.com/binance-fees/) |
| USDC-M futuros | 0.00% | 0.04% | — | [EVIDENCIA, 1 fuente secundaria] |

Las tarifas cambian: **leer en vivo** `GET /fapi/v1/commissionRate` (futuros, weight 20) y `GET /api/v3/account/commission` o `/sapi/v1/asset/tradeFee` (spot) [CÓDIGO para fapi; spot CONOCIMIENTO PREVIO – VERIFICAR].

**Break-even del carry (exacto con VIP0 taker en las 4 patas):** `coste_ida_vuelta = 2×0.10% + 2×0.05% = 0.30%`. Con funding base 0.01%/8h (0.03%/día) se necesitan **10 días** solo para cubrir costes; con 0.03%/8h (~33% APR) → 3.3 días. Con maker en ambas patas (spot 0.1% + perp 0.02%): 0.24%. Conclusión: **el carry solo tiene sentido cuando el funding esperado sostenido ≥ 2–3× el base y el horizonte esperado ≥ 1–2 semanas**.

### 2.8 Límites de API
- Futuros USDT-M: `REQUEST_WEIGHT` 2400/min y `ORDERS` 1200/min ([Binance legacy docs](https://developers.binance.com/legacy-docs/derivatives/portfolio-margin/common-definition)); límite por 10 s de órdenes (300/10s) **[CONOCIMIENTO PREVIO – VERIFICAR]**. 429 al exceder; 418 = baneo de IP si no se hace back-off; cabeceras `X-MBX-USED-WEIGHT-1M` y `X-MBX-ORDER-COUNT-*` ([futures-data general info](https://developers.binance.com/docs/derivatives/futures-data/general-info)).
- Spot: 6000 weight/min **[CONOCIMIENTO PREVIO – VERIFICAR]** (ccxt aún muestra un ejemplo antiguo de 1200 en comentarios, línea ~3476 de `ccxt/binance.py`).
- **Regla [OPINIÓN]:** leer `exchangeInfo.rateLimits` al arrancar y presupuestar; para muchas monedas usar **websockets** (`!markPrice@arr@1s` trae mark, index, funding estimado y next funding time de todos los símbolos en un único stream [CÓDIGO]; `<symbol>@kline_<int>`; `!forceOrder@arr`) y REST solo para históricos.
- Pesos REST relevantes [CÓDIGO: ccxt]: `klines` 1–10 según `limit` (≤99:1, ≤499:2, ≤1000:5); `premiumIndex` 1 con símbolo (10 sin símbolo en una entrada de ccxt); `fundingRate` 1; `openInterest` 1; `/futures/data/*` 1; `ticker/24hr` 1 (40 sin símbolo); `commissionRate` 20; `forceOrders` 20/50.
- **[CÓDIGO]** Bug detectado en `binance-futures-connector 4.2.0`: `funding_info()` llama a `/fapi/v1/fundingRate` en lugar de `/fapi/v1/fundingInfo` → no usar ese método (o llamar a la ruta a mano).

---

## 3. Qué sirve y qué no en cripto (síntesis crítica)

| Idea | Veredicto | Por qué |
|---|---|---|
| Carry delta-neutral (spot largo + perp corto) cuando funding alto | **Sirve, condicionado** | Respaldo académico (BIS, He et al.); pero alfa decreciente, Sharpe negativo reportado en 2025, costes de 0.24–0.30% por ciclo, salidas forzadas frecuentes. Solo en regímenes de funding alto. |
| Funding muy negativo como señal larga (BTC/ETH, horizonte 30–90 días) | **Débil / experimental** | 7–14 episodios, sin OOS, posible sesgo de selección; BitMEX no halla predictibilidad a 8h. |
| Funding muy positivo como señal corta | **No sirve como entrada** | Funding alto puede persistir semanas en tendencias alcistas (shortear tendencia = pagar funding + perder precio). Útil como **filtro** (no abrir largos nuevos / reducir tamaño). |
| Ranking cross-sectional por funding a 8h | **No sirve** | SSRN 6701738: Sharpe neto negativo. |
| Long/short ratio | **Sin evidencia** | Solo marketing de vendors. Como mucho, componente menor de un índice de "crowding". |
| OI como señal | **Débil**; útil como **contexto** | Subida de OI + funding alto = apalancamiento acumulado (riesgo de squeeze); no se replica como predictor puntual. |
| Rebote tras cascada de liquidaciones | **Experimental** | Solo estudios de evento; datos públicos infra-cuentan liquidaciones; no backtestable sin grabar datos propios. |
| Apalancamiento alto (>5x) | **No** | Con vol diaria de altcoins 5–10%, 10x implica liquidación con movimientos de 1 día normales. [OPINIÓN basada en la fórmula de §2.6] |
| Tendencia en perps (long/short) con sizing por volatilidad | **Sirve** (ver informe 01) | Los perps permiten cortos baratos; el funding es un coste/ingreso a modelar explícitamente. |

---

## 4. Estrategias candidatas (reglas implementables)

Convenciones: `F_k` = funding del intervalo k de un símbolo; `F̄_3d` = media de los funding de los últimos 3 días (9 pagos en 8h; ajustar al intervalo real); `APR(x) = x × n_dia × 365`. Todas las decisiones se toman **al cierre de vela** y se ejecutan en la siguiente. Costes en backtest: VIP0 taker salvo que se usen órdenes post-only.

### E1 — Funding carry delta-neutral (cash-and-carry) multi-moneda
- **Mercado:** spot (pata larga) + futuros USDT-M (pata corta), mismo activo.
- **Universo:** símbolos con par spot `XXXUSDT` y perp `XXXUSDT`; volumen perp 24h ≥ 50 M USDT y volumen spot 24h ≥ 10 M USDT; excluir los 14 días posteriores al listado.
- **Timeframe de decisión:** cada settlement (8h, o el intervalo del símbolo), evaluado 10 min antes.
- **Entrada:** `APR(F̄_3d) ≥ 25%` **y** `F_pred` (campo `lastFundingRate` de `premiumIndex`, funding estimado del intervalo en curso) `≥ 0.02%` por 8h-equivalente **y** basis actual `(Mark−Index)/Index > 0` **y** `APR(F̄_3d)` estimado para 14 días cubre `≥ 2×` el coste ida-vuelta (0.30% taker / 0.24% maker).
- **Ejecución:** comprar spot y vender perp por el mismo nocional (diferencia ≤0.5%), preferir órdenes limit post-only; si una pata no se llena en 60 s, cancelar y deshacer la otra.
- **Salida:** cualquiera de: (a) `APR(F̄_3d) < 5%`; (b) 2 funding consecutivos negativos; (c) basis < −0.1% y `F_pred < 0`; (d) delisting/alerta de cambio de cap/intervalo.
- **Stop / riesgo:** la pata corta en **margen cruzado con 1x–2x** máximo; rebalancear (transferir USDT de spot a futuros o reducir ambas patas) si `margin ratio > 40%`; cierre forzado de ambas patas si `margin ratio > 60%`. Esto sustituye al stop de precio (la posición es delta-neutral).
- **Sizing:** máx 20% del capital por símbolo, máx 5 símbolos, máx 70% del capital total en carry; mantener ≥30% en USDT de colchón.
- **Parámetros y rangos:** umbral de entrada 15–40% APR; salida 0–10% APR; ventana de media 1–7 días; apalancamiento de la pata corta 1–2x.
- **Variables:** funding histórico (`/fapi/v1/fundingRate`), funding estimado y mark/index (`/fapi/v1/premiumIndex` o `!markPrice@arr@1s`), `fundingInfo`, klines spot y perp, `commissionRate`, `leverageBracket`, balances de ambas cuentas.
- **Régimen:** funciona en mercados alcistas apalancados (funding persistentemente alto: 2021, 1T-2024). Falla en mercados laterales/bajistas (funding ≈0.01% o negativo → no cubre costes), en reversiones bruscas de funding (salidas forzadas, 95% en MDPI 2026), y ante riesgo de contraparte del exchange (FTX 2022).
- **Evidencia:** BIS WP 1087; He et al. arXiv 2212.06888; MDPI 2026 (40% rentables tras costes); Borri et al. arXiv 2510.14435 (Sharpe negativo 2025, a verificar). **Evidencia moderada; alfa en decaimiento.**

### E2 — Filtro de "crowding" (overlay de riesgo para cualquier estrategia direccional)
- **Mercado:** ambos (se aplica a las señales de las estrategias de tendencia/mean reversion de otros informes).
- **Cálculo por símbolo (cada 1h):** `C_long = 1` si se cumplen ≥2 de: (i) `funding_pctl(F̄_3d) ≥ 95` del último año; (ii) OI (en USDT) sube ≥ 20% en 7 días mientras el precio sube < 10%; (iii) `basis_bps` ≥ percentil 95 de 90 días. Simétrico `C_short` con percentil ≤5, OI +20% y precio bajando.
- **Reglas:** si `C_long=1` → **no abrir largos nuevos** y reducir a la mitad el tamaño de los largos existentes con stop sin mover; si `C_short=1` → no abrir cortos nuevos. No genera entradas propias.
- **Parámetros:** percentiles 90–99; ventana OI 3–14 días; umbral OI 10–30%.
- **Variables:** funding histórico, `openInterestHist` (o ficheros `metrics` de data.binance.vision para el backtest), premiumIndexKlines/basis.
- **Régimen:** útil en techos apalancados y squeezes; en tendencias fuertes recortará beneficio (falsos positivos).
- **Evidencia:** indirecta. BIS: carry alto predice liquidaciones de cortos (es decir, el carry alto precede *squeezes* que van contra quien está mal posicionado); anecdótica para techos. **Evidencia débil; justificado como gestión de riesgo, no como alfa** [OPINIÓN]. Debe validarse comparando la estrategia base con y sin filtro (mismos datos).

### E3 — Larga contraria tras funding negativo sostenido (BTC/ETH, baja frecuencia)
- **Mercado:** spot (preferido) o perp 1x.
- **Timeframe:** diario (cierre 00:00 UTC).
- **Entrada:** media de funding de 7 días < 0 **y** al menos 14 de los últimos 21 días con funding medio diario < 0 **y** precio de cierre ≥ mínimo de 20 días × 1.0 (no comprar mientras hace nuevos mínimos: exigir que el cierre de hoy > cierre de hace 3 días).
- **Salida:** a los 30 días, o si la media 7d de funding pasa a percentil ≥ 80 del año, o trailing stop `Chandelier = máx(cierre desde entrada) − 3×ATR(14,1D)`.
- **Stop inicial:** `entrada − 2.5×ATR(14,1D)`.
- **Sizing:** riesgo 0.5% del capital por operación (`tamaño = 0.005×capital / (entrada − stop)`).
- **Parámetros:** ventana funding 5–14 días; persistencia 10–21 días; holding 20–60 días; ATR mult 2–4.
- **Variables:** funding histórico, klines 1D.
- **Régimen:** capitulaciones/finales de bear market (2022, mediados de 2024). Falla en mercados bajistas prolongados con funding negativo persistente (sigue cayendo) — por eso el filtro de "no nuevos mínimos".
- **Evidencia:** VanEck/K33/Real Vision (no académicos, 7–14 episodios); BitMEX en contra a 8h. **Evidencia débil, alto riesgo de sobreajuste. Solo paper trading hasta acumular muestra.**

### E4 — Tendencia en perps con contabilidad de funding (long/short)
- **Mercado:** futuros USDT-M (permite cortos); en spot se ejecuta solo la parte larga.
- **Señal base:** la de tendencia del informe 01 (ensemble Donchian / precio vs SMA, timeframe 4h–1D).
- **Modificaciones específicas de futuros:**
  1. **Coste de carry en la expectativa:** no abrir un corto si `APR(F̄_3d) < −20%` (pagarías >20% APR); no abrir un largo si `APR(F̄_3d) > +50%` (pagarías >50% APR) salvo que la señal sea en 1D.
  2. **Apalancamiento:** `L = min(L_max, vol_objetivo / vol_realizada_anual)` con `vol_objetivo` 30–50% anual y `L_max` 3 (BTC/ETH) / 2 (resto); margen **aislado**.
  3. **Regla de liquidación:** `dist_liq ≥ 3 × dist_stop` (calculada con la fórmula de §2.6 y tiers de `leverageBracket`); si no se cumple, reducir L.
  4. **Stops con `workingType=MARK_PRICE`** y `reduceOnly=true`.
  5. **E2 activo** como filtro.
- **Salida/stop:** las del informe 01 (canal contrario / trailing ATR).
- **Variables:** klines (perp y mark), funding, `leverageBracket`, `exchangeInfo` (filtros `LOT_SIZE`, `MIN_NOTIONAL`, `PRICE_FILTER`).
- **Régimen:** tendencias sostenidas (ambos sentidos); falla en rangos laterales (whipsaw), igual que cualquier trend-following.
- **Evidencia:** la de TSMOM del informe 01 (moderada-fuerte en 1D); los ajustes de funding son [OPINIÓN] lógica de costes, no testados en papers.

### E5 — Rebote tras cascada de liquidaciones largas (experimental)
- **Mercado:** perp (1x–2x) o spot.
- **Timeframe:** 15m para detección, 1h para gestión.
- **Detección:** en una ventana de 60 min se cumplen: (i) nocional de liquidaciones `SELL` (largos liquidados) del stream `!forceOrder@arr` ≥ percentil 99 de los últimos 30 días **para ese símbolo** (grabado por el propio bot); (ii) caída ≥ 3×ATR(14, 1h); (iii) OI cae ≥ 5% en la ventana.
- **Entrada:** tras la primera vela de 15m que cierra por encima de su apertura y por encima del 50% del rango de la vela de mayor caída.
- **Stop:** mínimo de la cascada − 0.5×ATR(14,1h). **Take profit:** 50% de retroceso de la caída total, o salida por tiempo a 24h.
- **Sizing:** riesgo 0.25% del capital.
- **Parámetros:** percentil 95–99.5; ATR mult 2–4; OI −3% a −10%; time-stop 6–48h.
- **Variables:** stream de liquidaciones grabado, OI 5m, klines 15m/1h.
- **Régimen:** cascadas por apalancamiento excesivo (p. ej. 10–11 oct 2025) en mercado no bajista estructural. Falla cuando la cascada es el inicio de un bear market o ante noticias fundamentales (hack, delisting).
- **Evidencia:** estudios de evento (SSRN 6579278, [enlace](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278); arXiv 2607.27070) — **no hay evidencia de rentabilidad**; además el stream infra-cuenta. **No apto para dinero real sin ≥6 meses de datos propios grabados.**

---

## 5. Endpoints exactos (USDT-M, base `https://fapi.binance.com`) [CÓDIGO salvo indicación]

| Dato | Endpoint | Notas |
|---|---|---|
| Info de mercado | `GET /fapi/v1/exchangeInfo` | filtros, `rateLimits`, estado |
| Velas | `GET /fapi/v1/klines`, `/fapi/v1/continuousKlines`, `/fapi/v1/markPriceKlines`, `/fapi/v1/indexPriceKlines`, `/fapi/v1/premiumIndexKlines` | máx 1500 por llamada [CONOCIMIENTO PREVIO – VERIFICAR] |
| Mark/index/funding estimado | `GET /fapi/v1/premiumIndex` | campos `markPrice`, `indexPrice`, `lastFundingRate` (estimado), `interestRate`, `nextFundingTime` |
| Funding histórico | `GET /fapi/v1/fundingRate` | `startTime/endTime`, `limit` ≤1000 (def. 500) |
| Caps / intervalos | `GET /fapi/v1/fundingInfo` | solo símbolos con ajustes; resto = defecto |
| OI actual | `GET /fapi/v1/openInterest` | |
| OI histórico | `GET /futures/data/openInterestHist` | `period` 5m–1d, `limit` ≤500, **30 días** |
| L/S ratios | `GET /futures/data/globalLongShortAccountRatio`, `/topLongShortAccountRatio`, `/topLongShortPositionRatio`, `/takerlongshortRatio` | 30 días |
| Basis | `GET /futures/data/basis` | `pair`, `contractType`, `period` |
| 24h | `GET /fapi/v1/ticker/24hr` | 40 de weight sin símbolo |
| Tiers margen | `GET /fapi/v1/leverageBracket` (firmado) | MMR y `cum` por tier |
| Comisiones | `GET /fapi/v1/commissionRate` (firmado) | |
| Posiciones | `GET /fapi/v2/positionRisk` o `/fapi/v3/positionRisk` (firmado) | incluye `liquidationPrice` calculado por Binance → **usar para validar la fórmula propia** |
| Mis liquidaciones | `GET /fapi/v1/forceOrders` (firmado) | |
| Config. cuenta | `POST /fapi/v1/leverage`, `POST /fapi/v1/marginType` (ISOLATED/CROSSED), `POST /fapi/v1/positionSide/dual` | [CONOCIMIENTO PREVIO – VERIFICAR rutas] |
| WS | `wss://fstream.binance.com/ws/...`: `!markPrice@arr@1s`, `<s>@kline_<i>`, `!forceOrder@arr`, `<s>@aggTrade` | |
| Histórico masivo | `https://data.binance.vision/data/futures/um/{daily,monthly}/{klines,markPriceKlines,premiumIndexKlines,fundingRate?,metrics}/...` | `metrics` diario confirmado por issue #211; carpeta `fundingRate` mensual [CONOCIMIENTO PREVIO – VERIFICAR] |

**Restricción del entorno:** este contenedor no alcanza `fapi.binance.com` ni `data.binance.vision` (proxy 403) → los backtests de E1–E5 deben ejecutarse en la máquina del usuario o con datos que él suba.

---

## 6. Riesgos y sesgos señalados
- **Sesgo de publicación:** los informes que promueven "funding como señal contraria" son de casas de research/brokers que publican cuando la señal acaba de funcionar (K33 lo publicó en la 7.ª ocurrencia). Los trabajos que la testean formalmente (BitMEX, SSRN 6701738) son negativos.
- **Decaimiento del alfa:** He et al. documentan que las desviaciones se reducen con la madurez; Borri et al. reportan carry con Sharpe negativo en 2025 (a verificar).
- **Riesgo de cambio de reglas:** Binance cambia caps, intervalos e incluso la fórmula (2025-09) sin aviso largo → monitorizar `fundingInfo` y anuncios; tests unitarios deben tener el intervalo como parámetro.
- **Riesgo de contraparte y ADL:** en cascadas el exchange puede aplicar ADL (auto-deleverage) a posiciones ganadoras (existe `fapiPublic symbolAdlRisk` en ccxt [CÓDIGO]); el carry no está libre de riesgo.
- **Datos:** sin histórico largo de OI/L-S vía API (30 días) ni de liquidaciones; backtests de E2/E5 dependerán de `metrics` de data.binance.vision o de grabación propia → muestra corta, riesgo de sobreajuste.

## 7. Preguntas abiertas para el usuario / próximos pasos
1. ¿La cuenta tiene futuros USDT-M habilitados y qué nivel VIP / ¿paga comisiones con BNB? (cambia el break-even de E1).
2. ¿Modo de posición deseado: one-way o hedge? (afecta a `cumB` vs `cumL/cumS` y a la lógica de órdenes).
3. ¿Capital mínimo? E1 necesita ≥ ~1.000–2.000 USDT por símbolo para que `MIN_NOTIONAL` y los costes fijos no dominen [OPINIÓN].
4. Validar en vivo con la API (desde la máquina del usuario): `fundingInfo`, `leverageBracket` de BTCUSDT y un altcoin, `commissionRate`, `exchangeInfo.rateLimits`, y comparar la `liquidationPrice` de `positionRisk` con la fórmula de §2.6 en testnet.
