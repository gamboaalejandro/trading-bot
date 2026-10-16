# 05 — Sentimiento: Fear & Greed, funding/OI, long/short ratio, social/news

> Informe de investigación para el rediseño del bot (spot + futuros USDT-M de Binance, multi-moneda).
> Convención: **[EVIDENCIA]** = afirmación respaldada por una fuente citada. **[OPINIÓN]** = criterio propio del investigador o inferencia, no probada. **[NO VERIFICADO]** = conocido de documentación previa, pero no pude confirmarlo en esta sesión porque la mayoría de dominios (alternative.me, binance.com, bis.org, arxiv.org, k33.com, bitmex.com) devolvieron error DNS o 403 desde el contenedor. Los resultados de WebSearch sí estaban disponibles; los de WebFetch casi nunca.
> Fecha: 2026-10-15.

---

## 1. Resumen ejecutivo

1. **El sentimiento no es una estrategia; como mucho es un filtro o un multiplicador de tamaño.** La evidencia académica de que el Crypto Fear & Greed Index (F&G) predice retornos es **débil y frágil**: muestras cortas, frecuencia mensual o semanal, pocos tests fuera de muestra y casi nunca tras controlar por retornos pasados. Además, cerca del 50 % del índice se calcula a partir del propio precio (volatilidad y momentum/volumen), así que es muy colineal con señales técnicas que el bot ya tiene.
2. **La señal de sentimiento con mejor respaldo es el posicionamiento apalancado en derivados**, es decir la *carry* o *basis*, el funding y el open interest (OI). Un working paper del BIS (Schmeling, Schrimpf y Todorov) concluye que **una carry alta predice caídas bruscas futuras**. Los informes de K33 y VanEck sobre periodos de funding negativo apuntan a retornos medios positivos a 30–90 días, pero son *sell-side* o de proveedores y se basan en pocos episodios independientes (unos 7 desde 2018).
3. **El long/short ratio de Binance no tiene ningún estudio independiente serio** que lo respalde. Además, la API **solo sirve 30 días de histórico**, así que no se puede hacer backtest largo sin recolectar datos propios o usar los ficheros `metrics` de data.binance.vision.
4. **El sentimiento social y de noticias (CryptoPanic, LunarCrush, Santiment)** tiene literatura contradictoria. Unos estudios encuentran predictibilidad a 6 h, otros ninguna, y algunos indican que la causalidad va del precio al sentimiento. Los proveedores no publican backtests auditables. **No lo recomiendo como entrada del bot en la fase 1.**
5. **Recomendación [OPINIÓN]:**
   - Usar el funding y el OI por moneda como **veto o reductor de tamaño** contra el *crowding*, y como señal contrarian solo en extremos y con confirmación del precio.
   - Usar el F&G como **multiplicador de exposición global** muy acotado (0,5×–1×), nunca como disparador.
   - Validar todo con walk-forward y comparar contra la misma estrategia sin el filtro.

---

## 2. Hallazgos con evidencia

### 2.1 Crypto Fear & Greed Index (alternative.me)

**Cómo se calcula.** No pude leer la página oficial por bloqueo DNS; los pesos proceden de varias fuentes secundarias concordantes.
- **[EVIDENCIA, secundaria]** Componentes y pesos:
  - Volatilidad (25 %): volatilidad y drawdown actuales frente a las medias de 30 y 90 días.
  - Momentum/volumen de mercado (25 %): volumen y momentum actuales frente a las medias de 30 y 90 días.
  - Redes sociales (15 %).
  - Encuestas (15 %, **pausadas**).
  - Dominancia de BTC (10 %).
  - Google Trends (10 %).
  - Fuentes: https://www.datawallet.com/crypto/crypto-fear-and-greed-index, https://stealthex.io/blog/crypto-fear-and-greed-index/, https://www.kucoin.com/learn/trading/what-is-the-fear-and-greed-index-and-how-to-use-it-in-crypto-trading, https://unchainedcrypto.com/fear-and-greed-index/
- **[EVIDENCIA, secundaria]** Con las encuestas pausadas, los pesos activos suman 85 % y el índice se renormaliza. Al menos una fuente afirma que la descripción actual habla de un índice calculado solo con datos de mercado de Bitcoin. **Hay ambigüedad sobre los inputs vigentes.**
- **[EVIDENCIA, secundaria]** Varias fuentes lo describen como un indicador *rezagado*, no como herramienta de timing. Al menos el 50 % del índice se deriva del precio, lo que crea un bucle de realimentación (https://www.spark.money/glossary/fear-greed-index).
- **Escala:** 0–100. Bandas habituales: 0–24 Extreme Fear, 25–49 Fear, 50 neutral, 51–74 Greed, 75–100 Extreme Greed.
- **Frecuencia y publicación:** un valor diario para todo el mercado, centrado en BTC. No hay un valor por moneda.

**Poder predictivo (literatura):**

| Estudio | Datos | Resultado | Crítica |
|---|---|---|---|
| Cavalheiro, Vieira y Thue (2024), *Review of Behavioral Finance* — https://www.emerald.com/insight/content/doi/10.1108/RBF-08-2023-0224/full/html | Semanal, jul-2022 a jun-2023 | El F&G Granger-causa los retornos de BTC y ETH en ciertos lags; no hay causalidad no lineal significativa | **Un año de datos semanales (unas 52 observaciones).** Muestra ínfima; riesgo alto de falso positivo. |
| Huang, Xu, Xue y Zhang (2024), *Corporate Ownership & Control* — https://virtusinterpress.org/How-does-the-Bitcoin-Sentiment-Index-of-Fear-Greed-affect-Bitcoin-returns.html | Mensual, 2016–2021, ARDL/ECM | Correlación positiva y significativa; se mantiene con controles macro | Mide asociación contemporánea o a corto plazo, no predicción operable. No controla retornos pasados. |
| Estudio en revista checa — https://journal.fsv.cuni.cz/storage/1548_attachment.pdf | — | El F&G predice retornos de 1 semana a 1 mes tras un cambio de sentimiento | No pude verificar la metodología. |
| Estudio A-ARDL diario 2018–2022 — https://www.shs-conferences.org/articles/shsconf/pdf/2024/01/shsconf_icdeba2023_02015.pdf | Diario | Efecto positivo a corto y largo plazo, con controles de VIX y estrés financiero | Paper de conferencia; no hay test fuera de muestra. |

**Backtests contrarian ("buy extreme fear"):**
- **[EVIDENCIA, mixta]** Un análisis de julio de 2026 sobre unos 8 años de historia concluye que **"buy the fear" rinde peor que una compra aleatoria en varios horizontes, mientras que "sell the greed" aguanta mejor**. Fuente vista solo en el snippet de búsqueda; no pude abrirla: https://san-1510.aid.brainsum.com/news/analysis/cryptos-favourite-adage-half-fails-bitcoin-hits-extreme-fear
- **[EVIDENCIA, mixta]** K33 afirma que comprar en "extreme fear" fue rentable en media y mediana, pero con ventas continuadas posteriores en varios episodios: https://k33.com/research/archive/articles/fear-and-greed-index-touched-2020-lows
- **[EVIDENCIA débil]** Hay guías que publican "23 trades, 74 % win rate, Sharpe 1,84" sin separación entre entrenamiento y test y sin datos primarios. **Hay que descartar estas cifras.**

**Conclusión [OPINIÓN]:**
- El F&G es un resumen tardío de volatilidad y momentum de BTC.
- No aporta información por moneda.
- Si añade algo sobre una señal técnica bien construida, es probablemente en el extremo de *greed* (como reductor de riesgo para longs) y no en el de *fear* (como disparador de compra).
- La asimetría que reportan los estudios coincide con la literatura de redes sociales: el sentimiento negativo tiene más impacto (https://doi.org/10.1108/JRF-09-2023-0241).

### 2.2 Funding rate, basis y open interest como sentimiento

**Mecánica:**
- **[EVIDENCIA]** He, Manela, Ross y von Wachter, "Fundamentals of Perpetual Futures" (arXiv 2212.06888, https://arxiv.org/abs/2212.06888): los longs pagan a los shorts un funding proporcional a la diferencia entre el precio del perpetuo y el spot. Se liquida cada 8 h y es aproximadamente la media del spread futuro-spot de las 8 h anteriores. **Por tanto, el funding es una medida directa de la demanda apalancada neta.**
- **[NO VERIFICADO aquí, documentación de Binance]** USDT-M: `F = P + clamp(I − P, +0,05 %, −0,05 %)`, con `I` = 0,01 %/8 h por defecto, `P` = media del premium index y topes por símbolo. Algunos símbolos liquidan cada 4 h o cada 1 h, así que hay que normalizar el funding a una tasa por hora o anualizada.

**Poder predictivo:**
- **[EVIDENCIA, la más sólida del área]** BIS Working Paper 1087, "Crypto carry", de Schmeling, Schrimpf y Todorov (2023, revisado en octubre de 2025): https://www.bis.org/publ/work1087.htm
  - La carry (futuro frente a spot) llega al 60 % anual y varía mucho en el tiempo.
  - La impulsan la persecución de tendencia de pequeños inversores apalancados y la escasez de capital de arbitraje.
  - **Una carry alta predice caídas bruscas (crashes) futuras** y coincide con un precio más alto del seguro contra crash.
  - Resumen en VoxEU: https://cepr.org/voxeu/columns/crypto-carry-market-segmentation-and-price-distortions-digital-asset-markets
  - *Crítica:* predice **riesgo de cola**, no necesariamente retornos medios negativos a corto plazo. Es un argumento para **reducir exposición long**, no para abrir shorts sin más.
- **[EVIDENCIA, proveedor o sell-side]** K33, vía The Block:
  - Desde 2018, tras pasar la media de 30 días del funding a negativo, el retorno medio a 90 días fue del 79 % (mediana 55 %).
  - Solo hay **unos 7 episodios**.
  - En 2025, comprar en periodos de funding medio de 30 días negativo dio un *win rate* del 83–96 % entre 30 y 360 días, frente a un 55–70 % comprando al azar.
  - Fuentes: https://www.theblock.co/news/markets/2024-09-11-perp-signal-bitcoin-bottom-bullish-year-end-k33-315831 y https://www.theblock.co/post/400182/bitcoin-longest-negative-funding-streak-this-decade-k33-flags-short-squeeze-risk
  - *Crítica:* las ventanas se solapan (los win rates a 360 días se autocorrelacionan), los episodios son pocos y la muestra está dominada por un mercado alcista secular.
- **[EVIDENCIA, sell-side]** VanEck (abril de 2026): desde 2020, el retorno a 30 días de BTC en periodos de funding negativo promedió +11,5 %, frente a +4,5 % en general, con un 77 % de aciertos. https://www.vaneck.com/us/en/blogs/digital-assets/matthew-sigel-vaneck-mid-april-2026-bitcoin-chaincheck/
- **[EVIDENCIA, contraria y a corto plazo]** BitMEX Research, "XBTUSD Funding Mean Reversion Strategy": un funding muy negativo predice un retorno positivo en las 8 h siguientes, pero **las tasas de acierto de la tabla son en su mayoría inferiores al 50 %** y los buckets extremos tienen pocas observaciones. https://www.bitmex.com/blog/xbtusd-funding-mean-reversion-strategy
- **[EVIDENCIA]** Predecir el funding en sí es difícil: Ridge y XGBoost no baten una cartera estática equiponderada en arbitraje de funding en Binance. https://ph03.tci-thaijo.org/index.php/JSTKU/article/view/4724
- **[EVIDENCIA, calidad del dato]** Algunos grandes exchanges reportan mal el OI de perpetuos de BTC y podrían retrasar los mensajes de liquidación (datos tick de 7 exchanges, 2023). https://ledger.pitt.edu/ojs/ledger/article/view/325
- **[EVIDENCIA]** Liquidaciones en BitMEX: aproximadamente un 3,51 % de los longs abiertos y un 1,89 % de los shorts se liquidan al día, con un apalancamiento medio de unas 60× entre los liquidados. Las colas son más gruesas que una normal. https://arxiv.org/abs/2102.04591

**Conclusión [OPINIÓN]:**
- El funding y la basis son el mejor proxy de sentimiento disponible.
- Ventajas:
  - Es específico por moneda.
  - Es de alta frecuencia.
  - Tiene histórico completo vía API.
  - Hay un mecanismo económico claro: el crowding apalancado lleva a cascadas de liquidación.
- La evidencia más sólida respalda usarlo para **evitar o reducir longs con funding o basis extremos**, más que como señal de entrada contraria.

### 2.3 Long/short ratio de Binance

- **[EVIDENCIA, código oficial del SDK de Binance; verificado clonando `binance/binance-connector-python`]** Endpoints USDT-M, todos con *"Only the data of the latest 30 days is available"* (el de OI dice "latest 1 month") y un límite de IP de 1000 peticiones cada 5 minutos:

  | Endpoint | Qué mide |
  |---|---|
  | `GET /futures/data/globalLongShortAccountRatio` | Todas las cuentas |
  | `GET /futures/data/topLongShortAccountRatio` | Top 20 % por saldo de margen; cada cuenta cuenta una vez. Ratio = %cuentas net long / %cuentas net short |
  | `GET /futures/data/topLongShortPositionRatio` | Top 20 % ponderado por tamaño de posición. Ratio = %posición long / %posición short |
  | `GET /futures/data/takerlongshortRatio` | Volumen taker comprador frente a vendedor |
  | `GET /futures/data/openInterestHist` | OI histórico, 30 días |
  | `GET /futures/data/basis` | Basis, 30 días |

  Por contraste, `GET /fapi/v1/fundingRate` **no** indica límite de 30 días: devuelve 200 registros por defecto, se pagina con `startTime`/`endTime`/`limit` y comparte el límite de 500 peticiones cada 5 minutos con `/fapi/v1/fundingInfo`.
- **[EVIDENCIA, secundaria]** data.binance.vision publica ficheros diarios `data/futures/um/daily/metrics/<SYMBOL>/`. Contienen `sum_open_interest`, `sum_open_interest_value`, `count_toptrader_long_short_ratio`, `sum_toptrader_long_short_ratio`, `count_long_short_ratio` y `sum_taker_long_short_vol_ratio` (https://github.com/binance/binance-public-data/issues/211).
  - **[NO VERIFICADO]** Granularidad de 5 minutos y comienzo hacia finales de 2021 según el símbolo. Hay que comprobarlo desde una máquina con acceso.
  - El script oficial del repositorio (que clonamos) solo trae descargadores de klines, aggTrades, trades, mark/index/premiumIndex klines, **no de metrics**. Habrá que bajarlos por URL directa.
- **[EVIDENCIA]** **No encontré ningún estudio independiente** con muestra, costes y comparación contra un baseline. Lo que circula es:
  - Contenido de proveedores, como "cuando top-trader L/S > 2,8, BTC cayó en 48 h el 71 % de las veces", sin metodología (https://sites.google.com/view/decentralised-news/home/longshort-ratio-analysis).
  - Afirmaciones contradictorias: contrarian en Binance, de confirmación en Bybit.
  - La observación de que los ratios de retail están estructuralmente por encima de 1 (2–4× es normal), lo que hace que **los umbrales absolutos se disparen constantemente** (https://www.sharpe.ai/futures/long-short-ratio).
- **Conclusión [OPINIÓN]:**
  - El L/S es una hipótesis, no una evidencia.
  - Si se usa, debe normalizarse por moneda (z-score o percentil frente a su propio histórico).
  - Solo debe entrar tras validarse con datos `metrics` históricos o con datos recolectados por el bot durante semanas.

### 2.4 Social y noticias (CryptoPanic, LunarCrush, Santiment, Twitter/Reddit)

- **[EVIDENCIA, fuerte pero antigua]** Liu y Tsyvinski, "Risks and Returns of Cryptocurrency" (*Review of Financial Studies*, 2021; NBER w24877, https://www.nber.org/system/files/working_papers/w24877/w24877.pdf):
  - Hay un fuerte momentum de serie temporal.
  - Los **proxies de atención de los inversores** (búsquedas en Google, Twitter) predicen retornos a horizonte semanal.
  - Un aumento de búsquedas *negativas* precede a retornos negativos.
  - Muestra hasta 2018; **no hay garantía de que persista** (crítica habitual de decaimiento post-publicación).
- **[EVIDENCIA, mixta]** Twitter:
  - Predictibilidad a 6 h con estrategia rentable en un estudio de 1,1 M de tweets, citado en una revisión de CBS: https://research.cbs.dk/en/studentProjects/the-implications-of-bitcoin-within-economics-and-finance-a-review/
  - **Sin poder predictivo** en una tesis de Erasmus de 2024 ("el mercado se volvió más eficiente"): https://thesis.eur.nl/pub/73761/Bachelor-Thesis-Jeroen-Frasa.pdf
  - La atención predice volumen, pero no retornos (https://opus.lib.uts.edu.au/handle/10453/161851).
  - Altcoins: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6279012/
- **[EVIDENCIA]** El sentimiento sigue al precio: los usuarios de Twitter reaccionan a las subidas y caídas, lo que apunta a causalidad inversa (citado en los mismos resultados). StockTwits: en 425 criptos, los índices de sentimiento son informativos sobre retornos y volatilidad del índice de mercado (https://eprints.gla.ac.uk/214034).
- **Santiment:**
  - **[EVIDENCIA, proveedor]** Afirma que la euforia social extrema "a menudo" precede caídas y viceversa, sin tasas de acierto ni tamaños de muestra publicados (cobertura secundaria: https://www.mexc.com/news/309699).
  - Plan gratuito: 1 año de histórico y **30 días de retraso en métricas restringidas**; 1000 llamadas al mes (https://academy.santiment.net/products-and-plans/sanapi-plans, https://academy.santiment.net/sanapi/historical-and-realtime-data-restrictions/).
  - **Con 30 días de retraso no sirve para operar en tiempo real.**
- **CryptoPanic:**
  - API de noticias con votos de usuarios (positive/negative/important). No encontré documentación oficial de los límites del plan gratuito en esta sesión.
  - El único paper encontrado que la usa es un trabajo estudiantil con evidencia débil.
  - **[OPINIÓN]** Útil como *kill-switch* de eventos (hack, delisting, regulador) más que como señal direccional.
- **LunarCrush (Galaxy Score / AltRank):** **no encontré ningún backtest independiente.** API de pago. **[OPINIÓN]** Descartar en la fase 1.

---

## 3. Qué sirve y qué no (síntesis)

| Variable | ¿Sirve? | Uso recomendado | Fuerza de la evidencia |
|---|---|---|---|
| Funding / basis extremo positivo (por moneda) | **Sí** | Veto o reducción de longs; short contrarian solo con confirmación del precio | Media (BIS más mecanismo económico) |
| Funding medio de 30 días negativo (BTC/ETH) | Probablemente | Sesgo long en spot a horizonte de semanas | Débil-media (vendor, n≈7 episodios) |
| ΔOI con precio (OI sube y el precio no avanza) | Plausible | Detector de crowding, junto con el funding | Débil (mecanismo, datos ruidosos) |
| F&G extremo greed (>80) | Quizá | Multiplicador 0,5–0,75× en longs nuevos | Débil |
| F&G extremo fear (<20) como compra | **No** como disparador | Como mucho, no recortar shorts más | Débil y contradictoria |
| L/S ratio (global o top) | No probado | Solo en investigación, normalizado por moneda | Ninguna independiente |
| Social/news (Santiment, LunarCrush) | No en fase 1 | Fuera del bot; quizá un kill-switch de noticias | Contradictoria, de proveedor |
| Google Trends / atención | Histórica | No es accesible en tiempo real de forma fiable | Media pero antigua (pre-2018) |

---

## 4. Variables cuantitativas exactas (definiciones para implementar)

Todas se calculan **por símbolo** salvo el F&G.

**Fear & Greed y funding:**

| Variable | Definición |
|---|---|
| `fg_t` | Valor F&G del día t (0–100). **Para operar el día t usar `fg_{t-1}`** (se publica una vez al día; hay que evitar el look-ahead y registrar el timestamp UTC de recepción) |
| `fg_ema7` | EMA de 7 días de `fg` |
| `fg_pct365` | Percentil de `fg_ema7` en los últimos 365 días |
| `fr_i` | Funding liquidado en el periodo i (fracción) |
| `fr_1h` | `fr_i / horas_del_intervalo_i` (normaliza 8 h, 4 h y 1 h). `fr_ann = fr_1h × 24 × 365` |
| `fr_pred` | `lastFundingRate` de `/fapi/v1/premiumIndex`: funding estimado en curso (tiempo real, sin look-ahead) |
| `fr_ma3d` | Media de `fr_1h` en 72 h |
| `fr_ma30d` | Media de `fr_1h` en 30 días |
| `fr_z` | `(fr_ma3d − media_90d(fr_1h)) / std_90d(fr_1h)`, con std con suelo 1e-6 |
| `fr_pct` | Percentil de `fr_ma3d` frente a su propio histórico de 180 días. **Se prefiere al umbral absoluto** para un universo multi-moneda |

**Basis, open interest y liquidez:**

| Variable | Definición |
|---|---|
| `basis` | `(markPrice − indexPrice) / indexPrice`, de `premiumIndex` en tiempo real o de `premiumIndexKlines` en histórico |
| `oi` | Open interest en contratos y `oi_usd = sum_open_interest_value` |
| `doi_24h` | `oi_usd_t / oi_usd_{t−24h} − 1` |
| `doi_px_div` | `doi_24h − ret_24h` (OI que crece más que el precio indica posiciones nuevas apalancadas) |
| `oi_mcap` | No hay market cap accesible desde Binance. Usar `oi_usd / quote_volume_spot_30d_media` como proxy del apalancamiento relativo a la liquidez |

**Long/short ratio y riesgo:**

| Variable | Definición |
|---|---|
| `lsr_global`, `lsr_top_acc`, `lsr_top_pos` | Endpoints de la sección 2.3, o ficheros `metrics` |
| `lsr_div` | `log(lsr_top_pos) − log(lsr_global)` (smart money frente a crowd) |
| `lsr_z` | z-score de 30 días de `log(lsr_global)` |
| `atr_4h` | ATR(14) en velas de 4 h, para stops |
| `ret_7d`, `vol_30d` | Controles obligatorios en cualquier test: la señal de sentimiento debe aportar sobre ellos |

---

## 5. Estrategias candidatas

### S1 — Crowding Veto (filtro sobre las estrategias técnicas existentes y futuras)

- **Mercado:** spot y futuros.
- **Tipo:** filtro y multiplicador. No genera entradas propias.
- **Reglas:** se evalúan sobre cada señal de entrada long que produzca otra estrategia (tendencia, breakout o mean reversion), justo al cierre de la vela de señal.
  1. Si `fr_pct ≥ 95` **y** `doi_24h ≥ +8 %` → **rechazar el long** (veto). En futuros también se rechazan longs con apalancamiento superior a 1×.
  2. Si no, si `fr_pct ≥ 85` **o** `basis ≥ percentil 90 (180 d)` → tamaño ×0,5.
  3. Simétrico para shorts en futuros: si `fr_pct ≤ 5` **y** `doi_24h ≥ +8 %` → rechazar el short (riesgo de short squeeze). Si `fr_pct ≤ 15` → tamaño ×0,5.
  4. Para posiciones ya abiertas: si se activa la condición 1 en contra de la posición, mover el stop a break-even o a 1×`atr_4h` del precio, lo que esté más cerca. No hay cierre forzado.
- **Gestión:** salida, stop y take profit los dicta la estrategia base. Este módulo solo filtra o escala.
- **Parámetros (rangos razonables):**
  - Percentil de veto: 90–97.
  - Percentil de reducción: 80–90.
  - Umbral de `doi_24h`: 5–15 %.
  - Ventana del percentil: 90–365 días.
  - **Fijar los valores a priori** (95/85/8 %/180 d) y hacer solo un análisis de sensibilidad, no optimizarlos.
- **Timeframes:** las señales se evalúan en el timeframe de la estrategia base (15m–4h). El funding se actualiza cada 8 h o en tiempo real con `fr_pred`.
- **Datos:** `/fapi/v1/fundingRate` (histórico completo), `/fapi/v1/premiumIndex` (tiempo real), OI (`/fapi/v1/openInterest` en tiempo real; el histórico viene de `metrics` o de recolección propia), `premiumIndexKlines`.
- **Régimen:**
  - Funciona en las fases finales de rallies apalancados (*blow-off*) y en altcoins con funding disparado.
  - Falla o cuesta rentabilidad en tendencias alcistas fuertes y persistentes, donde el funding se mantiene alto semanas y el veto deja fuera el tramo bueno.
  - Spot puro sin perpetuo listado: no aplica, y se usa el funding de BTC como proxy del mercado.
- **Evidencia:** BIS WP 1087 (la carry alta predice crashes). El mecanismo de liquidaciones lo respalda arXiv 2102.04591.
- **Criterio de aceptación:**
  - Mejora el máximo drawdown o el CVaR de la estrategia base sin reducir el Sharpe más de un 10 %, en walk-forward y sobre al menos 20 símbolos.
  - Si solo mejora en BTC, se rechaza.

### S2 — Funding Extreme Reversal con confirmación (solo futuros USDT-M)

- **Mercado:** futuros.
- **Tipo:** contrarian de sentimiento con disparador técnico.
- **Universo:** perpetuos USDT-M con volumen medio de 30 días superior a 20 M USDT/día y al menos 180 días de listado.
- **Señal SHORT** (las tres condiciones al cierre de una vela de 4 h):
  1. `fr_z ≥ +2,5` **y** `fr_ann ≥ 30 %` (equivale a ≥0,0274 %/8 h).
  2. `doi_px_div ≥ +5 %` (el OI sube 5 puntos más que el precio en 24 h).
  3. Confirmación: el cierre de la vela de 4 h queda por debajo de la EMA20 de 4 h **y** por debajo del mínimo de la vela anterior.
- **Señal LONG (simétrica):**
  1. `fr_z ≤ −2,5` **y** `fr_ann ≤ −10 %`.
  2. `doi_px_div ≥ +5 %` (se abren shorts nuevos con el precio cayendo).
  3. Cierre de 4 h por encima de la EMA20 de 4 h y por encima del máximo de la vela anterior.
- **Entrada:** a mercado en la apertura de la vela siguiente.
- **Stop:** el más restrictivo entre 1,5×`atr_4h` y el máximo o mínimo (swing) de las últimas 6 velas de 4 h, más 0,1 %.
- **Salida (la primera que se cumpla):**
  - Take profit a 2R.
  - `|fr_z| < 0,5` (el crowding se ha normalizado): cerrar.
  - Stop por tiempo de 72 h.
  - Trailing a break-even al alcanzar 1R.
- **Sizing:** riesgo del 0,5 % del equity por trade, con apalancamiento máximo de 3×. Como máximo 3 posiciones S2 simultáneas y como máximo 2 en la misma dirección. Se aplica el multiplicador global de S4.
- **Filtros:**
  - No entrar en las 2 h previas a la liquidación del funding cuando la posición pagaría funding superior a 0,1 %.
  - No operar si `fr_pred` y el último funding liquidado tienen signo contrario (dato inestable).
- **Parámetros:**
  - Umbral de `fr_z`: 2–3.
  - Umbral de `fr_ann`: 20–50 % para shorts y −5 a −20 % para longs.
  - `doi_px_div`: 3–10 %.
  - EMA: 20–50.
  - Take profit: 1,5–3R.
  - Stop por tiempo: 48–120 h.
- **Datos:** fundingRate, premiumIndex, OI histórico (metrics), klines de 4 h y 1 h.
- **Régimen:**
  - Funciona en mercados laterales o en techos y suelos locales con apalancamiento desequilibrado, sobre todo en altcoins.
  - **Falla en tendencias fuertes**, donde el funding alto persiste y el precio sigue subiendo. Por eso la confirmación técnica es obligatoria.
  - Las señales son escasas.
- **Evidencia:**
  - BIS WP 1087 (dirección del efecto en crashes).
  - BitMEX Research (efecto a 8 h débil, con tasa de acierto inferior al 50 %). Hay que esperar **pocas señales y un edge pequeño**.
  - Ningún paper publica exactamente esta regla. **[OPINIÓN]** La regla es una construcción propia que hay que validar.

### S3 — Negative-Funding Accumulation (spot, BTC y ETH, baja frecuencia)

- **Mercado:** spot.
- **Tipo:** contrarian de régimen, con horizonte de semanas.
- **Entrada:**
  - Se evalúa una vez al día a las 00:05 UTC.
  - Si `fr_ma30d` de BTCUSDT-perp (o ETH para ETH) es menor que 0, se compra un tramo del 25 % de la asignación objetivo de S3.
  - Como máximo 4 tramos (100 %), con un mínimo de 7 días entre tramos.
- **Salida:**
  - Vender todo cuando `fr_ma30d > percentil 80` de su histórico de 365 días.
  - O, alternativamente, al cumplirse 120 días desde el primer tramo.
  - O si el precio cierra a diario por debajo de la EMA200 diaria **y** `ret_30d < −25 %` (catástrofe).
- **Stop:** el de catástrofe descrito arriba, más un stop duro de −30 % sobre el precio medio de entrada.
- **Sizing:** asignación objetivo de S3 igual al 10–20 % del capital total del bot. Sin apalancamiento.
- **Parámetros:**
  - Ventana de la media: 14–45 días.
  - Umbral de entrada: 0 a −0,005 %/8 h.
  - Percentil de salida: 70–90.
  - Horizonte: 60–180 días.
- **Datos:** `/fapi/v1/fundingRate` de BTCUSDT y ETHUSDT (histórico desde 2019), klines diarias de spot.
- **Régimen:**
  - Funciona tras capitulaciones apalancadas en mercados alcistas seculares (todos los episodios de la muestra de K33 y VanEck están en ese contexto).
  - **Falla en un mercado bajista prolongado** como el de 2022: VanEck reporta su única pérdida a 180 días (−3,5 %) en junio de 2022.
  - Las señales son muy escasas (2–3 al año como mucho).
- **Evidencia:** K33 (The Block 2024 y 2025) y VanEck (2026). **Débil:** n≈7 episodios independientes, ventanas solapadas y posible sesgo de supervivencia del activo (BTC). No es estadísticamente significativo por sí solo.

### S4 — Sentiment Exposure Throttle (multiplicador global con F&G y funding de mercado)

- **Mercado:** spot y futuros.
- **Tipo:** multiplicador de riesgo agregado de la cartera.
- **Reglas:** se calcula una vez al día con datos del día t−1.
  - `mkt_fr` = media ponderada por OI de `fr_ma3d` de los 20 perpetuos de mayor OI.
  - `mult_long`:
    - 0,5 si `fg_ema7 ≥ 80` **y** `pct(mkt_fr, 365 d) ≥ 90`.
    - 0,75 si se cumple solo una de las dos condiciones.
    - 1,0 en otro caso.
  - `mult_short` (solo futuros):
    - 0,5 si `fg_ema7 ≤ 20` **y** `pct(mkt_fr) ≤ 10`.
    - 0,75 si se cumple solo una.
    - 1,0 en otro caso.
  - **Nunca se usa un multiplicador mayor que 1.** El sentimiento solo reduce riesgo y no lo apalanca.
- **Entrada, salida y stop:** los de las estrategias base. Los multiplicadores solo afectan al sizing de posiciones nuevas.
- **Parámetros:**
  - Umbrales de F&G: 75–85 y 15–25.
  - EMA: 5–14 días.
  - Percentiles de `mkt_fr`: 85–95 y 5–15.
- **Datos:**
  - Histórico de F&G de alternative.me. **[NO VERIFICADO aquí]** `https://api.alternative.me/fng/?limit=0&format=json`, diario desde el 1 de febrero de 2018 aproximadamente. **No es accesible desde este contenedor:** hay que descargarlo en la máquina del usuario y versionarlo como CSV.
  - Funding de los 20 perpetuos principales.
- **Régimen:**
  - Reduce el daño en euforias tardías.
  - Cuesta rentabilidad en rallies largos con greed sostenido, como finales de 2020 a 2021, cuando el F&G estuvo por encima de 75 durante semanas.
- **Evidencia:**
  - Asimetría de "sell the greed" frente a "buy the fear" (análisis de 2026, ver 2.1).
  - El BIS para la parte de funding.
  - La literatura sobre F&G es débil. **Por eso el efecto se limita a 0,5–1×.**

### S5 — LSR Divergence (EXPERIMENTAL, solo paper trading)

- **Mercado:** futuros.
- **Tipo:** hipótesis de smart money frente a crowd.
- **Reglas:** se evalúan cada 1 h.
  - **Long:** `lsr_div ≥ percentil 90` (30 días, por símbolo) **y** `lsr_z ≤ −1` (la crowd está más short de lo normal) **y** cierre de 1 h por encima de la EMA50 de 1 h.
  - **Short:** espejo de la regla long.
  - **Stop:** 2×ATR(14, 1 h).
  - **Take profit:** 2R.
  - **Salida por tiempo:** 24 h.
  - **Riesgo:** 0,25 % por trade.
- **Parámetros:**
  - Percentil: 80–95.
  - `lsr_z`: −0,5 a −1,5.
  - Horizonte: 12–48 h.
- **Datos:** `topLongShortPositionRatio` y `globalLongShortAccountRatio` (**solo 30 días en la API**). Para el backtest: ficheros `metrics` de data.binance.vision o recolección propia cada 5 minutos desde ya.
- **Régimen:** desconocido.
- **Evidencia:**
  - **Ninguna independiente**, solo afirmaciones de proveedores.
  - Promover a real solo si después de **al menos 3 meses** de paper trading sobre al menos 20 símbolos el PF > 1,2 tras costes y la mejora frente a la misma regla sin `lsr_div` es significativa (bootstrap, p < 0,05).

---

## 6. Protocolo anti-overfitting para señales de sentimiento

1. **Alineación temporal estricta:**
   - F&G del día t−1.
   - Funding liquidado solo después de su `fundingTime`.
   - Para lo que va antes, usar `fr_pred`.
   - Los ficheros `metrics` desplazados una barra.
2. **Umbrales relativos** (percentiles o z-scores por símbolo con ventana *rolling*), nunca absolutos calibrados en BTC y aplicados a altcoins.
3. **Pocos parámetros y fijados a priori.** Solo análisis de sensibilidad: la estrategia debe ser rentable en todo el rango indicado, no en un punto.
4. **Test incremental:** comparar la estrategia base con la estrategia base más el filtro. El filtro debe mejorar el Sharpe, el máximo drawdown o el CVaR. Hay que incluir `ret_7d` y `vol_30d` como controles, porque el F&G es en buena medida precio.
5. **Walk-forward** con ventanas de entrenamiento de 12 meses y test de 3 meses, más purga o embargo igual al horizonte máximo de holding.
6. **Corrección por pruebas múltiples:** registrar cada variante probada y aplicar el Deflated Sharpe Ratio (Bailey y López de Prado) o Bonferroni.
7. **Baseline aleatorio:** misma frecuencia de entradas en fechas aleatorias, con 1000 simulaciones.
8. **Costes reales:** comisiones de taker y maker de Binance, slippage, y **funding pagado o cobrado** en las posiciones de futuros.
9. **Robustez cruzada:**
   - Al menos 20 símbolos.
   - Regímenes 2019–2020, 2021 alcista, 2022 bajista y 2023 en adelante, reportados por separado.
   - Con n≈7 episodios (como en S3), **no se puede afirmar significancia**: se trata como prior, no como prueba.

---

## 7. Fuentes de datos históricos (accesibilidad)

| Dato | Fuente | Histórico | Acceso desde el contenedor | Nota |
|---|---|---|---|---|
| Funding USDT-M | `GET /fapi/v1/fundingRate` | Completo, paginado con `startTime` (desde el listado) | **No** (403/DNS) | En la máquina del usuario; 500 peticiones cada 5 minutos |
| Mark/Index/Premium klines | data.binance.vision (`download-futures-premiumIndexKlines.py`, etc., del repo oficial) | Desde el listado | **No** | El script está verificado en el repo clonado |
| OI y L/S histórico | data.binance.vision `futures/um/daily/metrics/` | **[NO VERIFICADO]** desde finales de 2021 aproximadamente | **No** | La API solo da 30 días |
| OI y L/S en tiempo real | `/futures/data/*`, `/fapi/v1/openInterest` | 30 días | **No** | Recolectar con un cron propio |
| Fear & Greed | `api.alternative.me/fng/?limit=0` | Desde 2018-02 aproximadamente [NO VERIFICADO] | **No** | Gratuito, sin clave |
| Santiment | SanAPI / sanpy | Gratuito: 1 año y 30 días de retraso en métricas restringidas | **No** (pip install sí) | No apto para tiempo real en plan gratuito |
| CryptoPanic | API REST con token | Limitado (sin verificar) | **No** | Solo como kill-switch de noticias |
| LunarCrush | API v4 de pago | — | **No** | Descartado en la fase 1 |

**Acción requerida al usuario:** desde su máquina (con acceso a Binance), descargar el funding completo, los ficheros `metrics` y el CSV del F&G para el universo de símbolos, y subirlos al repositorio privado o a un almacenamiento accesible. Sin esos datos no se puede ejecutar el backtest de S1–S5 en este contenedor.

---

## 8. Sesgos y límites de esta investigación

- **Sesgo de publicación:** los papers que encuentran efecto del F&G o del sentimiento se publican más (revistas menores, muestras cortas). Los resultados nulos aparecen en tesis (Erasmus 2024).
- **Proveedores con incentivos:** K33, VanEck, Santiment y Coinglass venden datos o productos. Sus cifras no están auditadas.
- **Decaimiento:** el efecto de atención de Liu y Tsyvinski se mide antes de 2018. La literatura sugiere una eficiencia creciente.
- **Lo que no pude leer en esta sesión:**
  - La página oficial de alternative.me.
  - El PDF del BIS.
  - Los artículos de BitMEX y K33 (bloqueados).
  - Las cifras de esas fuentes provienen de resúmenes de búsqueda y deben verificarse leyendo los originales antes de darlas por definitivas.
