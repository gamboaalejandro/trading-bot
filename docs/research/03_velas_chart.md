# 03 — Análisis de velas y chart: qué tiene evidencia en cripto y cómo codificarlo

Fecha: 2026-10-15. Autor: subagente investigador (rol cuantitativo).

> **Nota de método y limitaciones (léase primero).**
> - En esta sesión **WebFetch no funcionó** (falla DNS `ENOTFOUND` en todos los dominios probados: ieeexplore, dspace.cuni.cz, cxoadvisory, abarbon.com, research.birmingham.ac.uk). `curl` a arXiv y SSRN devuelve 403 en el proxy. Por eso **todo lo marcado como [EVIDENCIA] procede de abstracts y resúmenes devueltos por WebSearch**, no de la lectura del texto completo. Las cifras exactas (Sharpe, CAGR, etc.) deben verificarse contra el paper antes de usarse como referencia de backtest.
> - Uso tres etiquetas: **[EVIDENCIA]** = resultado publicado con fuente; **[EVIDENCIA DÉBIL]** = tesis, working paper, resumen secundario o muestra pequeña; **[OPINIÓN]** = criterio propio o práctica de mercado sin test estadístico.
> - No se ha ejecutado ningún backtest en este informe. Las reglas de la sección 5 son **hipótesis a validar** en el harness con los datos de `/home/user/harness/data`.

---

## 1. Resumen ejecutivo

1. **Los patrones de velas clásicos (engulfing, doji, martillo, estrella fugaz, etc.) como señal aislada no tienen valor demostrado en cripto.** El estudio más amplio (68 patrones, 23 criptos top, IEEE BigData 2021) concluye que son de poca utilidad. En acciones, los tests con bootstrap y corrección de data-snooping llegan a lo mismo. Hay excepciones aisladas (Hammer, Shooting Star) en una tesis de máster, pero son evidencia débil y probablemente falsos positivos de múltiples comparaciones.
2. **Lo que sí tiene evidencia razonable es la *geometría del precio* respecto a extremos recientes:** las rupturas de rango (Donchian / "trading range breakout") y el trend-following multihorizonte en diario funcionan en BTC y en una cesta de altcoins líquidas, incluso tras corregir data-snooping en algunos estudios. El trabajo más reciente y completo (Zarattini, Pagani, Barbon 2025) usa un ensemble de canales Donchian con trailing stop y sizing por volatilidad.
3. **En horizontes intradía la evidencia es mixta y depende del horizonte:** a 1-4h hay autocorrelación negativa (reversión) en BTC, más fuerte tras movimientos grandes (atribuida a sobrerreacción y cascadas de liquidaciones). En cambio, hay momentum intradía (la primera media hora de la "sesión" medida por volumen predice la última). Coexisten, por lo que el horizonte y el filtro de régimen son críticos.
4. **El volumen contiene algo de información, pero sobre todo en las colas** (retornos extremos), y no en regímenes alcista o bajista marcados. No he encontrado ningún estudio serio que valide **OBV**, **volume profile** o **VWAP** como señales en cripto. Son herramientas de ejecución o contexto y no edges probados.
5. **Soportes y resistencias:** está documentado el *clustering* de precios en números redondos en BTC, pero **no hay retornos anómalos después de tocarlos**. La "cercanía al máximo de 52 semanas" sí predice retornos en sección cruzada (anclaje), lo que favorece las rupturas de máximos frente a "vender en la resistencia".
6. **La estructura de mercado (HH/HL, "smart money concepts", order blocks) no tiene ninguna validación académica que haya encontrado.** Como mucho es una forma discreta de medir tendencia, y es redundante con Donchian o pendiente de medias.
7. **Conclusión práctica para el bot:** las velas deben entrar como **features normalizadas por ATR** (cuerpo, mechas, rango, posición del cierre, volumen relativo) dentro de filtros o meta-etiquetado, **no como disparadores**. Los disparadores con evidencia son: ruptura de canal o tendencia multihorizonte (diario/4h) y reversión tras shock extremo (1h-4h, con filtro de régimen). Recomiendo abandonar el timeframe de 1m que usa hoy el bot, porque no hay evidencia a favor y los costes lo penalizan.

---

## 2. Hallazgos con evidencia

### 2.1 Patrones de velas

| Estudio | Datos | Resultado | Calidad |
|---|---|---|---|
| "Do Candlestick Patterns Work in Cryptocurrency Trading?", IEEE BigData 2021. https://ieeexplore.ieee.org/document/9671826 · https://repository.eduhk.hk/en/publications/do-candlestick-patterns-work-in-cryptocurrency-trading/ | 68 patrones, 23 criptos top por capitalización | Los patrones "son de poca utilidad" y muchos tienen baja precisión | **[EVIDENCIA]** (abstract) |
| "Candlesticks and graph patterns in cryptocurrencies", tesis de la Univ. Carolina de Praga. https://dspace.cuni.cz/handle/20.500.11956/197060 | 41 patrones, 5 datasets, t-test ajustado por asimetría y test binomial | 8 patrones con potencial predictivo en no-stablecoins (Hammer Bullish, Rising Window Bullish, On Neck Bearish, Shooting Star Bearish), pero 2 dan retornos **contrarios** a su clasificación | **[EVIDENCIA DÉBIL]**: tesis; 41 patrones × 5 datasets sin corrección clara de comparaciones múltiples, así que se esperan 2 falsos positivos al 5% |
| Marshall, Young & Rose, velas en acciones del DJIA 1992-2002. https://mro.massey.ac.nz/items/edc6c1cf-63d9-4c94-a13d-92ffe1a53481/full · https://www.cxoadvisory.com/technical-trading/candlesticks-fiddlesticks/ | 28 señales, bootstrap de OHLC aleatorios | Ninguna señal predice; una alcista predice retorno **negativo** | **[EVIDENCIA]** (acciones, no cripto) |
| Duvinage, Mazza & Petitjean, 83 reglas de velas a 5 min en las 30 acciones del DJIA. https://dial.uclouvain.be/pr/boreal/en/object/boreal%3A136070/datastream/PDF_02/view | 5 min intradía | Aproximadamente 1/3 supera buy-and-hold con Bonferroni, pero **ninguna** lo hace tras corregir data-snooping y costes | **[EVIDENCIA]** (acciones) |
| Kharazmi Univ., velas horarias de BTC 2017-2025 con lógica difusa. https://jfr.ut.ac.ir/article_107529_en.html | 1h | Reconoce que la interpretación clásica es "subjetiva y heurística" y propone codificación numérica | **[EVIDENCIA DÉBIL]** |

**Interpretación [OPINIÓN]:** el patrón con nombre japonés es una discretización arbitraria de 3 o 4 ratios continuos (cuerpo/rango, mechas/rango, cierre relativo). La información útil, si existe, está en esos ratios **y en su tamaño relativo a la volatilidad**, no en la etiqueta. Hay sesgo de publicación evidente: los blogs y PDFs que prometen "patrones de alta rentabilidad" (por ejemplo https://licm.mcgill.ca/fetch.php/G-09yk/445180/High%20Profit%20Candlestick%20Patterns.pdf) no tienen metodología verificable.

### 2.2 Reglas técnicas, rupturas y trend-following

- **Hudson & Urquhart (2019/2021), "Technical trading and cryptocurrencies", *Annals of Operations Research*.** Prueban unas 15.000 reglas en 5 familias: medias, filtros, soporte/resistencia, osciladores y ruptura de canal. Encuentran predictibilidad y rentabilidad que **sobreviven a la corrección de data-snooping**, con costes de breakeven por encima de los típicos de cripto. **Pero** en el periodo out-of-sample **no hay predictibilidad para BTC**. https://link.springer.com/article/10.1007/s10479-019-03357-1 **[EVIDENCIA]**. Esto indica decaimiento del edge.
- **Gerritsen, Bouri, Ramezanifar & Roubaud (2020), *Finance Research Letters* 34:101263.** BTC diario 2010-2019, 7 indicadores de tendencia. El **trading range breakout** tiene poder predictivo significativo (bootstrap) y supera a buy-and-hold en Sharpe, sobre todo **en mercados con tendencia fuerte**. Ventanas de 50, 150 y 200 días. Según un resumen secundario, **no incluye costes**. https://ideas.repec.org/a/eee/finlet/v34y2020ics1544612319303770.html · https://research-portal.uu.nl/en/publications/the-profitability-of-technical-trading-rules-in-the-bitcoin-marke/ **[EVIDENCIA]**
- **Zarattini, Pagani & Barbon (2025), "Catching Crypto Trends", SSRN 5209907.** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 · https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/ · https://www.quantifiedstrategies.com/crypto-trend-trading-strategy-for-bitcoin/ **[EVIDENCIA]**, con detalles por resúmenes secundarios:
  - Ensemble de canales Donchian con 9 lookbacks.
  - Entrada cuando el cierre diario supera el máximo del lookback.
  - Trailing stop diario igual a max(stop previo, punto medio entre máximo y mínimo del lookback).
  - Equal-weight entre lookbacks y sizing a una volatilidad objetivo del 25% anual (vol realizada de 90 días), con tope de apalancamiento que algunos resúmenes sitúan en 200%.
  - Resultados en BTC desde 2015: CAGR neto de unos 30% y Sharpe 1,56.
  - Cartera rotacional del top-20 líquido: Sharpe > 1,5 y alfa anual de 10,8% frente a BTC, netos de comisiones.
  - Una reproducción independiente en GitHub obtiene un CAGR de 16,9% con costes de 10 bps (https://github.com/zebadee2kk/DeFi-TraderStack-Agent/issues/137): **el resultado es sensible a costes e implementación**.
- **Bakker (tesis Erasmus).** 3.312 reglas intradía en BTC/USD a 5 min, 2013-2017. Hay reglas significativas tras data-snooping y costes, pero la rentabilidad **es inestable y cae con el tiempo**. https://thesis.eur.nl/pub/41546/Bakker.pdf **[EVIDENCIA DÉBIL]**
- **Wei (tesis doctoral Glasgow, 2021).** 6 criptos, 2013-2018. Las reglas de medias parecen batir a buy-and-hold, pero esa rentabilidad "puede venir del sesgo de data-snooping". https://theses.gla.ac.uk/82986/1/2021WeiMingzhePhD.pdf **[EVIDENCIA DÉBIL]**
- **J. Accounting & Finance (2023).** BTC/USDT y ETH/USDT con ajuste de data-snooping: **no hay estrategias técnicas rentables**. https://articlegateway.com/index.php/JAF/article/view/6453 **[EVIDENCIA]**
- **Liu & Tsyvinski (RFS 2021).** Momentum de serie temporal y atención predicen retornos de BTC, ETH y XRP. https://nber.org/papers/w24877 **[EVIDENCIA]**. Han, Kang & Ryu encuentran que el TS-momentum sobrevive a los costes y el cross-sectional es débil: https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf **[EVIDENCIA]**

**Lectura crítica:** la evidencia a favor de rupturas y tendencia en **diario** es la más consistente, pero:
- (a) se concentra en los periodos 2015-2021, con tendencias enormes;
- (b) hay un estudio de 2023 que no la encuentra para BTC/ETH;
- (c) Hudson & Urquhart ven desaparecer el edge out-of-sample en BTC.

Hay que esperar un Sharpe muy inferior al publicado. **[OPINIÓN]**: en una cesta de muchas monedas, el trend-following sigue siendo el candidato más robusto porque su payoff es convexo (pocas ganancias grandes) y se beneficia de la diversificación entre monedas y lookbacks.

### 2.3 Intradía: reversión frente a momentum

- **De Nicola (2021), "On the Intraday Behavior of Bitcoin", *Ledger*.** Autocorrelación de primer orden **negativa y significativa** a 1h, 2h y 4h, más fuerte cuanto mayor es el movimiento. La atribuye a sobrerreacción, exceso de volatilidad y **cascadas de liquidaciones por apalancamiento**. Incluye una estrategia simple de backtest. https://ledger.pitt.edu/ojs/ledger/article/view/213 · https://epub.ub.uni-muenchen.de/97651/ **[EVIDENCIA]**
- **J. Applied Economics (dic-2022).** En BTC hay sobrerreacción clara tras shocks **negativos** horarios. https://doaj.org/article/889af1e55ca44d83bcb079580903b1b0 **[EVIDENCIA]**
- **Caporale & Plastun (CESifo 2019).** Tras días de sobrerreacción, los retornos horarios siguen la dirección del shock (momentum), salvo excepciones contrarian. https://cesifo.org/en/publications/2019/working-paper/momentum-effects-cryptocurrency-market-after-one-day-abnormal **[EVIDENCIA]**. **Contradice parcialmente** a los dos anteriores, porque depende de la definición del shock y del horizonte.
- **Zaremba et al. (IRFA 2021).** Reversión diaria en más de 3.600 coins, atribuida a iliquidez; **las grandes y líquidas muestran momentum**. Resumido en https://earsiv.medeniyet.edu.tr/items/23a96c9f-3952-4bdf-aec5-abafb3aaab70/full **[EVIDENCIA]**
- **Shen, Urquhart & Wang (2022), *Financial Review* 57(2).** Usando el volumen como reloj, la primera media hora predice positivamente la última. Es más fuerte en sesiones de alto volumen o volatilidad y en caídas de BTC. https://reading-9.eprints-hosting.org/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf **[EVIDENCIA]**. Es difícil de trasladar a un bot 24/7 sin replicar exactamente su definición de sesión.
- **Concretum, "Seasonality in Bitcoin Intraday Trend Trading".** Ensemble long/short de trend intradía, 2018-2025, Sharpe bruto de unos 1,6. https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/ **[EVIDENCIA DÉBIL]**: es una publicación de gestora y la cifra es **bruta de comisiones**.

**Síntesis [OPINIÓN, apoyada en lo anterior]:** a 1-4h, los movimientos *extremos* tienden a revertir parcialmente, sobre todo los negativos, que suelen ser liquidaciones largas. En diario y semanal domina el momentum en monedas líquidas. Un bot que mezcle ambos debe separar claramente el horizonte y el régimen.

### 2.4 Volumen, OBV, VWAP y volume profile

- **Balcilar et al. (2017), *Economic Modelling*.** El volumen predice los retornos de BTC **salvo en regímenes bajista y alcista** (colas de la distribución), y no predice la volatilidad. https://repository.up.ac.za/handle/2263/60028 **[EVIDENCIA]**
- **Bouri, Lau, Lucey & Roubaud (2019), FRL.** En 7 criptos, el volumen causa en sentido Granger los retornos **extremos**, positivos y negativos. https://research.tees.ac.uk/en/publications/trading-volume-and-the-predictability-of-return-and-volatility-in/ **[EVIDENCIA]**
- **Fičura (2023).** El volumen y el tamaño modulan el momentum y la reversión, y la distancia al máximo de k semanas predice retornos con signo distinto en coins grandes y pequeñas. https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php **[EVIDENCIA DÉBIL]** (working paper)
- **OBV, VWAP y volume profile:** **no encontré ningún estudio con test estadístico en cripto.** Lo que aparece son scripts de TradingView y artículos divulgativos (por ejemplo https://www.coinapi.io/learn/academy/tutorials/market-trends-graphing-vwap-for-intraday-trend-identification). **[OPINIÓN]**:
  - VWAP es útil como referencia de ejecución y como "precio justo" de la sesión UTC.
  - Volume profile requiere datos de trades o velas finas, y su POC es una forma de medir dónde hubo liquidez, sin edge demostrado.
  - OBV es una suma acumulada de volumen con signo que se correlaciona fuertemente con el propio precio, así que es redundante.

### 2.5 Soportes, resistencias y anclaje

- **Urquhart (2017), *Economics Letters*.** Clustering significativo en números redondos en BTC (más del 10% de precios terminan en .00), pero **no hay patrón de retornos tras el número redondo**. https://ideas.repec.org/a/eee/ecolet/v159y2017icp145-148.html **[EVIDENCIA]**
- **Estudio de 2021 sobre barreras psicológicas.** Las barreras de soporte son robustas y las de resistencia menos claras. https://www.ceeol.com/search/article-detail?id=1043301 **[EVIDENCIA DÉBIL]**
- **Jia et al., "Psychological Anchoring Effect and Cross Section of Cryptocurrency Returns", SSRN 5386180.** La cercanía al máximo de 52 semanas predice positivamente los retornos en sección cruzada. Resumido por Quantpedia: https://vvv.quantpedia.com/?p=42289 **[EVIDENCIA DÉBIL]** (working paper, sin verificar costes)

**Implicación [OPINIÓN]:** la evidencia de anclaje favorece **comprar la proximidad o ruptura de máximos** en coins líquidas, no vender en resistencia. Los niveles redondos sirven para **colocar stops fuera** de ellos (evitar el clúster de órdenes), no como señal.

### 2.6 Estructura de mercado (HH/HL) y multi-timeframe

- **No encontré estudios académicos** que validen HH/HL, BOS/CHoCH, order blocks ni "smart money concepts" en cripto. **[OPINIÓN]**: HH/HL calculado con pivotes fractales de N barras es una medida de tendencia que se solapa con Donchian. Introduce parámetros extra (N del pivote) y **look-ahead bias** si no se respeta que un pivote solo se confirma N barras después.
- **Multi-timeframe:** tampoco hay test específico en cripto. La literatura sí apoya que el **diario/semanal tiene momentum** y que **1-4h tiene reversión** (2.2 y 2.3). El uso MTF con fundamento es: la dirección del timeframe alto filtra, y el bajo sirve para entrar en un pullback (reversión de corto plazo **a favor** de la tendencia de largo). Es una combinación de dos efectos documentados, aunque la combinación en sí no está testada. **[OPINIÓN]**

### 2.7 Datos de Binance relevantes

- La kline de Binance trae 12 campos: open time, OHLC, volumen base, close time, volumen quote, nº de trades, **taker buy base volume**, taker buy quote volume e ignore. https://developers.binance.com/en/docs/products/connect-prime/open-apis/11.get-kline-data **[EVIDENCIA]** (doc oficial de Connect Prime; el layout coincide con el REST spot).
- **Advertencia sobre el dataset local:** los CSV de `/home/user/harness/data` solo tienen `timestamp,open,high,low,close,volume`. **No incluyen taker buy volume ni nº de trades**, así que las variables de flujo taker (CVD, desequilibrio comprador) **no se pueden backtestear con lo disponible**. Habría que reconstruirlas desde la fuente cruda (static-klines trae 12 campos en spot) o desde la API en vivo.

---

## 3. Qué sirve y qué no en cripto

| Herramienta | Veredicto | Base |
|---|---|---|
| Patrones de vela con nombre como disparador | **No sirve** | 2.1 (IEEE 2021; bootstrap en acciones) |
| Geometría de vela normalizada por ATR como feature o filtro | **Plausible**, a validar | Opinión apoyada en 2.3: el tamaño del shock importa en la reversión |
| Ruptura de rango / Donchian en diario (y quizá 4h) | **Sirve, con la evidencia más fuerte** | 2.2 (Gerritsen, Zarattini, Hudson-Urquhart) |
| Ensemble multi-lookback más sizing por volatilidad | **Sirve**: reduce el riesgo de elegir mal el parámetro | 2.2 (Zarattini) |
| Reversión a 1-4h tras shock extremo | **Plausible**, con evidencia moderada y riesgo de cola | 2.3 (De Nicola, JAE 2022) |
| Momentum intradía por sesión | **Débil o difícil de implementar** | 2.3 (Shen et al.; Concretum bruto) |
| Volumen relativo como condicionante de colas | **Plausible** | 2.4 |
| OBV / VWAP / volume profile como señal | **Sin evidencia**; usar solo para ejecución o contexto | 2.4 |
| S/R en números redondos como señal | **No sirve como señal**; sí para colocar stops | 2.5 |
| Cercanía a máximos (52w o k semanas) | **Plausible** como ranking entre monedas | 2.5 |
| HH/HL / SMC | **Sin evidencia**; redundante con Donchian | 2.6 |
| Velas de 1m (bot actual) | **Desaconsejado** | Ninguna evidencia, costes muy altos relativos y ruido |

---

## 4. Variables cuantitativas exactas

Notación: vela *t* con O, H, L, C, V. ATR_n = ATR de Wilder de n barras calculado **hasta t-1** (para no usar información de la vela que se evalúa en la normalización de la señal; alternativa válida: hasta t si la señal se evalúa al cierre de t). ε = 1e-12.

### 4.1 Geometría de vela
| Variable | Fórmula | Rango |
|---|---|---|
| `range_atr` | (H − L) / ATR_14 | ≥0 |
| `body_atr` | (C − O) / ATR_14 | con signo |
| `body_frac` | \|C − O\| / (H − L + ε) | [0,1] |
| `upper_wick_frac` | (H − max(O,C)) / (H − L + ε) | [0,1] |
| `lower_wick_frac` | (min(O,C) − L) / (H − L + ε) | [0,1] |
| `close_loc` (CLV) | (C − L) / (H − L + ε) | [0,1]; 1 = cierre en el máximo |
| `gap_atr` | (O_t − C_{t−1}) / ATR_14 | casi 0 en cripto 24/7; útil solo en huecos de datos |
| `ret_z` | log(C_t/C_{t−1}) / σ_{logret,N} con N=96 para 1h (≈4 días) | z-score |
| `true_range_z` | (TR_t − media_N(TR)) / std_N(TR) | z-score |

**Equivalencias numéricas de patrones**, solo para auditar y comparar con la literatura, no como señal:
- **Doji**: `body_frac` < 0.1.
- **Pin bar alcista / martillo**: `lower_wick_frac` ≥ 0.6, `body_frac` ≤ 0.3, `close_loc` ≥ 0.6 y `range_atr` ≥ 1.0.
- **Estrella fugaz**: espejo del anterior.
- **Engulfing alcista**: C_{t−1} < O_{t−1}, C_t > O_t, O_t ≤ C_{t−1}, C_t ≥ O_{t−1} y `body_atr` ≥ 0.5.

### 4.2 Volumen
| Variable | Fórmula |
|---|---|
| `rvol` | V_t / mediana(V_{t−N..t−1}), con N=20 en diario y N = 24×7 = 168 en 1h, o la mediana de la misma hora UTC de los últimos 20 días para quitar estacionalidad intradía |
| `rvol_z` | (log V_t − media_N(log V)) / std_N(log V) |
| `dollar_vol_30d` | mediana de 30 días de (C × V); se usa como filtro de liquidez del universo |
| `taker_imb` (si hay datos) | (2·taker_buy_base − V) / V ∈ [−1,1]; **no disponible en el dataset local** |
| `vwap_dist_atr` | (C − VWAP_sesión_UTC) / ATR_14, con VWAP = Σ(tp·V)/ΣV y tp = (H+L+C)/3 desde las 00:00 UTC; solo contexto |
| `obv_slope` | pendiente OLS de OBV en N barras / std(V); **sin evidencia**, solo para descartarlo en ablación |

### 4.3 Estructura, niveles y tendencia
| Variable | Fórmula |
|---|---|
| `donch_hi_n`, `donch_lo_n` | máx(C) y mín(C) de las n barras previas (sin incluir t). Zarattini usa cierres; Gerritsen, highs y lows |
| `donch_pos_n` | (C − donch_lo_n) / (donch_hi_n − donch_lo_n + ε) ∈ [0,1] |
| `breakout_n` | 1 si C_t > donch_hi_n; −1 si C_t < donch_lo_n; 0 en otro caso |
| `near_high_k` | C_t / máx(H en k semanas), con k = 52 (anclaje) o k = 1 (Fičura) |
| `pivot_high(N)` | H_t es máximo en [t−N, t+N]; **se confirma en t+N**, así que solo puede usarse desde t+N |
| `hh_hl_score` | +1 si los dos últimos pivotes confirmados son HH y HL, −1 si son LH y LL, 0 en otro caso |
| `round_dist_atr` | \|C − R\| / ATR_14, con R el múltiplo más cercano de `step = 10^(floor(log10(C)) − 1)` (para BTC a 60.000 USD, step = 1.000 USD); solo para colocar stops |
| `trend_slope_n` | pendiente OLS de log(C) en n barras / σ de residuos (t-stat de tendencia) |
| `er_n` (Kaufman efficiency ratio) | \|C_t − C_{t−n}\| / Σ\|ΔC\| ∈ [0,1]; alto = tendencia y bajo = rango |
| `vol_ann_90` | std(logret diario, 90) · √365, para el sizing |

### 4.4 Multi-timeframe
- `htf_trend` = signo de `breakout_n` vigente en diario o `trend_slope_50d`, **tomado de la última vela diaria cerrada** (merge asof con la vela previa para evitar look-ahead).
- `ltf_pullback` = `ret_z` en 1h acumulado de las últimas 4-12 barras, en contra de `htf_trend`.

---

## 5. Estrategias candidatas (reglas implementables)

> Convenciones comunes:
> - Señales evaluadas **al cierre** de la vela; ejecución en la **apertura de la siguiente** (o con orden límite o mercado inmediatamente tras el cierre).
> - Costes a modelar como mínimo:
>   - spot: 0,10% por lado (taker sin BNB);
>   - futuros: 0,05% taker por lado;
>   - slippage: 2-5 bps en majors y 10-20 bps en altcoins;
>   - funding real en las posiciones de futuros abiertas a las 00, 08 y 16 UTC.
> - En spot solo hay largos; los cortos solo en futuros USDT-M.
> - Filtrar velas con `volume == 0`.

### C1 — Ensemble Donchian multi-lookback con volatility targeting (diario)
*Base: Zarattini, Pagani & Barbon 2025; Gerritsen et al. 2020.* **Es la candidata principal.**

- **Universo:** monedas con `dollar_vol_30d` ≥ 20 M USD (ajustable) y al menos 365 días de historia. En el dataset local son los 18 de futuros y los 10 de spot.
- **Timeframe:** 1d, con cierre a las 00:00 UTC. Variante a probar en 4h, con lookbacks ×6.
- **Lookbacks:** L ∈ {5, 10, 20, 30, 60, 90, 150, 250, 360} días. Es el conjunto usado en implementaciones públicas del paper; **hay que verificar el set exacto en el PDF**.
- **Sub-señal por lookback L (largo):**
  - Entrada: `C_t > max(C_{t−L..t−1})`, y la sub-posición L pasa de 0 a 1.
  - Stop trailing: `stop_L,t = max(stop_L,t−1, (max(C_{t−L..t}) + min(C_{t−L..t}))/2)`.
  - Salida: `C_t < stop_L,t`, y la sub-posición L pasa a 0.
- **Sub-señal corta (solo futuros, extensión no testada en el paper **[OPINIÓN]**):** espejo con `C_t < min(...)` y stop = min(stop previo, punto medio). Recomiendo activarla solo si `htf` (precio < SMA200 diaria) también es bajista y empezar con peso 0,5 respecto a los largos, porque el drift alcista histórico de cripto penaliza los cortos.
- **Señal agregada:** `s_t = media de las 9 sub-posiciones` ∈ [0,1] (o [−1,1] con cortos).
- **Sizing:**
  - Por moneda: `w_t = s_t · min(target_vol / vol_ann_90, lev_max)`, con target_vol = 25% anual (rango 15-40%) y lev_max = 1,0 en spot y 1,0-2,0 en futuros.
  - Cartera de N monedas: dividir target_vol entre √N_activo o aplicar un tope de exposición bruta total de 1,0-2,0. **[OPINIÓN]**
- **Rebalanceo:** diario, solo si |w_objetivo − w_actual| > 20% de w_actual (umbral de no-trading para costes, como en la reproducción de GitHub).
- **Stop de catástrofe (futuros):** stop de mercado colocado en el exchange a 3·ATR_14 diario del precio de entrada, para cubrir el gap intradía. **No forma parte del paper [OPINIÓN].**
- **Régimen:**
  - Funciona en tendencias persistentes (2017, 2020-21, 2023-24) y en rallies de altcoins.
  - Falla en rangos largos con falsas rupturas (por ejemplo, 2018-19 lateral y mediados de 2022 tras el desplome), donde sufre *whipsaw* y erosión por costes.
  - Las entradas tardías hacen que el drawdown de cada trade individual sea grande.
- **Datos:** OHLCV diario y, en futuros, funding.
- **Riesgo de sobreajuste:** bajo, porque el ensemble evita escoger L y hay pocos parámetros libres (target_vol y umbral de rebalanceo).

### C2 — Ruptura de rango con confirmación de volumen y filtro de eficiencia (4h)
*Base: trading range breakout (Gerritsen 2020; familia "channel breakout" en Hudson-Urquhart). Los filtros de volumen y ER son **[OPINIÓN]** apoyada en Bouri et al. 2019 (el volumen se asocia a movimientos extremos).*

- **Timeframe:** 4h, con filtro direccional en 1d.
- **Entrada larga:** todas las condiciones a la vez:
  1. `C_t > max(H_{t−n..t−1})` con n = 30 barras de 4h (5 días); rango 20-60.
  2. `rvol_t ≥ 1.5`, con mediana de 30 barras; rango 1,2-2,5.
  3. `close_loc_t ≥ 0.7`: la vela cierra en su tercio alto. Es la única variable "de vela" usada.
  4. Diario: `C_d > SMA_100(C_d)` de la última vela diaria cerrada; rango 50-200.
  5. `range_atr_t ≤ 3.0`: no perseguir velas de clímax, porque la reversión 1-4h tras shocks extremos (De Nicola) juega en contra.
- **Entrada corta (futuros):** espejo con `C_t < min(L…)`, `close_loc ≤ 0.3` y diario por debajo de la SMA100.
- **Stop inicial:** `entry − 2.0·ATR_14(4h)`; rango 1,5-3,0. Se coloca además 0,1·ATR por debajo del número redondo si queda a menos de 0,25·ATR de él.
- **Gestión:**
  - Trailing chandelier: `max(H desde entrada) − 3·ATR_14`.
  - Salida por tiempo si tras 12 barras (2 días) el P&L es < +0,5R.
  - Sin take-profit fijo, porque el payoff de las rupturas es asimétrico.
- **Sizing:** riesgo fijo del 0,5% del equity por trade, con `qty = 0.005·equity / (entry − stop)`. Topes: 3 posiciones en la misma dirección entre monedas con correlación > 0,8 y apalancamiento efectivo máximo de 2x en futuros.
- **Régimen:** funciona en expansiones de volatilidad tras compresión y falla en rangos con barridas de liquidez (*stop hunts*) frecuentes. Conviene añadir el filtro `er_30 ≥ 0.3` y probarlo en ablación.
- **Datos:** OHLCV en 4h y 1d; funding para el coste de futuros.
- **Advertencia:** la evidencia de las rupturas en 4h es más débil que en diario (Hudson-Urquhart no separa por timeframe en lo que pude ver, y Bakker muestra decaimiento intradía). Debe ganar a C1 out-of-sample para justificar su complejidad.

### C3 — Reversión tras shock extremo con mecha de rechazo (1h, contra-tendencia de corto plazo)
*Base: De Nicola 2021 (autocorrelación negativa a 1-4h, mayor tras movimientos grandes); JAE 2022 (sobrerreacción tras shocks negativos). La mecha y el volumen son **[OPINIÓN]**.*

- **Timeframe:** 1h, en spot (solo largo) y futuros (largo; corto opcional y con menor peso, porque la evidencia es más fuerte para shocks negativos).
- **Entrada larga al cierre de la vela t:** todas las condiciones:
  1. `ret_z_t ≤ −3.0` (σ de 96 barras), **o** el retorno acumulado de 3 barras / (σ·√3) ≤ −3.5. Umbral en el rango −2,5 a −4,0.
  2. `range_atr_t ≥ 2.0`.
  3. `lower_wick_frac_t ≥ 0.35` **o** `close_loc_t ≥ 0.4`: rechazo parcial dentro de la propia vela.
  4. `rvol_t ≥ 2.0` (capitulación o liquidaciones).
  5. Filtro de régimen: no hay ruptura bajista diaria activa (`C_d ≥ min(C_d, 20 días previos)`) **y** BTC no cae más del 8% en 24h, para no comprar en un crash sistémico en curso (por ejemplo, FTX o mayo de 2021).
- **Salida:**
  - Take-profit en la **reversión parcial del 50%** del movimiento de las 3 barras previas, o en el cruce de `C ≥ EMA_20(1h)`, lo que ocurra primero.
  - Salida por tiempo a las 12 barras (rango 4-24).
- **Stop:** `L_t − 1.0·ATR_14(1h)`, por debajo del mínimo del shock. En futuros, colocar como STOP_MARKET en el exchange.
- **Sizing:** riesgo del 0,25-0,5% del equity por trade. Como máximo 2 trades C3 simultáneos, porque en crash todos los shocks están correlacionados.
- **Régimen:**
  - Funciona en mercado lateral o en tendencia alcista con *flush* de apalancamiento: largos liquidados con funding previo positivo alto (combinar con el informe de funding/derivados).
  - **Falla gravemente** en crashes de cambio de régimen, que son el clásico "cuchillo cayendo". Por eso es esencial el filtro 5 y el stop real.
- **Datos:** OHLCV 1h y 1d, el retorno de BTC como filtro de mercado y, opcionalmente, funding/OI (el OI local está imputado y no se exportó).
- **Riesgo de sobreajuste:** medio-alto, con 4 umbrales. Hay que fijarlos a priori con los valores indicados y testear la sensibilidad en rejilla gruesa, no optimizar finamente.

### C4 — Pullback a favor de la tendencia diaria (MTF: diario filtra y 1h entra)
*Base: combinación de momentum en diario (Liu-Tsyvinski; Zarattini) y reversión a 1-4h (De Nicola). La combinación en sí **no está testada [OPINIÓN]**.*

- **Filtro diario:** C1 tiene `s_t ≥ 0.5` (la mayoría de los lookbacks Donchian en largo) **o** `near_high_52w ≥ 0.85`.
- **Entrada en 1h (largo):**
  - El retorno acumulado de 8 barras (rango 4-12) / (σ_1h·√8) es ≤ −1.5 (pullback de corto plazo);
  - la vela de 1h cierra con `close_loc ≥ 0.6` y `body_atr ≥ 0`, es decir, una vela de giro mínima;
  - y C > `donch_lo_20` diario (la tendencia no está rota).
- **Stop:** mínimo de las últimas 8 barras − 0,5·ATR_14(1h).
- **Salida:** C ≥ máximo de las últimas 24 barras (retorno al máximo local), trailing de 2·ATR, o la sub-señal diaria cae por debajo de 0,5 (salida forzosa).
- **Sizing:** riesgo del 0,5% por trade; la exposición total combinada con C1 en la misma moneda se limita al w objetivo de C1.
- **Mercado:** spot y futuros (largo). La versión corta es espejo y solo en futuros con s_t ≤ −0,5.
- **Régimen:** tendencias sanas con correcciones. Falla en el techo de tendencia, cuando el pullback se convierte en reversión, aunque el filtro de donch_lo_20 limita el daño.
- **Comparación obligatoria:** debe mejorar el Sharpe o el MAR de C1 puro con el mismo riesgo. Si no lo hace, es complejidad sin valor.

### C5 — Ranking de anclaje a máximos (rotación semanal entre monedas, solo largos)
*Base: Jia et al. (SSRN 5386180, Nearness52); Fičura 2023 (signo distinto en coins grandes y pequeñas). **[EVIDENCIA DÉBIL]**.*

- **Universo:** solo coins líquidas (top por `dollar_vol_30d`). Fičura indica que en illiquidas el efecto se invierte.
- **Rebalanceo:** semanal (lunes 00:00 UTC). Se calcula `near_high_52w = C / max(H, 365d)` y se compra el tercil superior en equal-weight o inverse-vol, con exposición bruta ≤ 1.
- **Filtro de mercado:** solo se invierte si BTC > SMA_200 diaria; en otro caso, USDT.
- **Stop:** no hay stop por trade; el riesgo se gestiona por rotación y filtro de mercado. Opcionalmente, salida si la moneda cae por debajo de `donch_lo_20` diario.
- **Régimen:** alt-seasons y mercados alcistas amplios. Falla en reversiones bruscas del mercado (todas las coins caen juntas) y en universos pequeños, como los 10-18 símbolos locales, donde el cross-section es demasiado estrecho para ser fiable.
- **Uso recomendado [OPINIÓN]:** más que como estrategia independiente, como **ponderación** dentro de C1 (sobreponderar monedas con mayor `near_high_52w`).

---

## 6. Protocolo de validación recomendado para el harness

1. **Pre-registro:** fijar los parámetros por defecto de este documento **antes** de ver los resultados y registrar el número total de configuraciones probadas.
2. **Split temporal:**
   - Futuros 2020-09 → 2024-06 como in-sample y 2024-07 → 2026-09 como out-of-sample.
   - Spot 4h/1d desde 2017 para C1 y C5.
   - Walk-forward con ventanas anuales.
3. **Corrección de data-snooping:** Deflated Sharpe Ratio (Bailey & López de Prado) o White's Reality Check / SPA de Hansen sobre el conjunto de variantes probadas. Hsu, Kuan & Shyu (2005) aplican el Reality Check a más de 40.000 reglas: https://ideas.repec.org/p/sin/wpaper/04-a003.html
4. **Ablaciones obligatorias:**
   - C2 sin `rvol` y sin `close_loc`;
   - C3 sin la condición de mecha;
   - C4 frente a C1 puro.

   Si la variable de vela no aporta, se elimina.
5. **Costes:** comisiones reales de Binance, slippage creciente con `range_atr` y funding real (dataset local, con la salvedad de que es derivado y no oficial).
6. **Robustez:** heatmap de sensibilidad por parámetro (±50%), resultados por moneda y por año, y comprobar que el beneficio no depende de 1-2 monedas o de un único año (2021).
7. **Look-ahead:** pivotes confirmados con retraso N; merge asof con la vela diaria **cerrada**; ATR y σ calculados con datos hasta t.

---

## 7. Sesgos y advertencias

- **Sesgo de publicación:** los resultados positivos de reglas técnicas en cripto se concentran en muestras 2013-2021. Los estudios con corrección estricta y muestras recientes (J. Accounting & Finance 2023; Hudson-Urquhart OOS en BTC) son más pesimistas.
- **Gestoras y blogs** (Concretum, QuantifiedStrategies, TradingView): tienen incentivos comerciales, y algunas cifras son brutas de comisiones.
- **Supervivencia:** usar universos que existían en cada fecha. Los 18 símbolos locales son supervivientes actuales y **sobreestimarán** el rendimiento; Zarattini et al. usan un universo libre de sesgo de supervivencia.
- **Patrones de velas:** con 41-68 patrones testados, es esperable encontrar 2-4 "significativos" por azar. Ningún resultado positivo de patrón individual en cripto ha sido replicado de forma independiente que yo haya encontrado.
- **Limitación de esta investigación:** no pude leer los textos completos (WebFetch caído). Todas las cifras proceden de abstracts o resúmenes y deben comprobarse.

## 8. Fuentes

- IEEE BigData 2021, velas en cripto: https://ieeexplore.ieee.org/document/9671826
- Tesis de la Univ. Carolina, velas y patrones gráficos: https://dspace.cuni.cz/handle/20.500.11956/197060
- Marshall, Young & Rose: https://mro.massey.ac.nz/items/edc6c1cf-63d9-4c94-a13d-92ffe1a53481/full
- Duvinage et al.: https://dial.uclouvain.be/pr/boreal/en/object/boreal%3A136070/datastream/PDF_02/view
- Hudson & Urquhart 2019: https://link.springer.com/article/10.1007/s10479-019-03357-1
- Gerritsen et al. 2020: https://ideas.repec.org/a/eee/finlet/v34y2020ics1544612319303770.html
- Zarattini, Pagani & Barbon 2025: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 · https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/
- Reproducción en GitHub: https://github.com/zebadee2kk/DeFi-TraderStack-Agent/issues/137
- Bakker (Erasmus): https://thesis.eur.nl/pub/41546/Bakker.pdf
- Wei (Glasgow): https://theses.gla.ac.uk/82986/1/2021WeiMingzhePhD.pdf
- JAF 2023: https://articlegateway.com/index.php/JAF/article/view/6453
- Liu & Tsyvinski: https://nber.org/papers/w24877
- Han, Kang & Ryu: https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
- De Nicola 2021: https://ledger.pitt.edu/ojs/ledger/article/view/213
- JAE 2022, shocks horarios: https://doaj.org/article/889af1e55ca44d83bcb079580903b1b0
- Caporale & Plastun: https://cesifo.org/en/publications/2019/working-paper/momentum-effects-cryptocurrency-market-after-one-day-abnormal
- Shen, Urquhart & Wang 2022: https://reading-9.eprints-hosting.org/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf
- Concretum, intradía: https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/
- Balcilar et al. 2017: https://repository.up.ac.za/handle/2263/60028
- Bouri et al. 2019: https://research.tees.ac.uk/en/publications/trading-volume-and-the-predictability-of-return-and-volatility-in/
- Fičura 2023: https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php
- Urquhart 2017, números redondos: https://ideas.repec.org/a/eee/ecolet/v159y2017icp145-148.html
- Barreras psicológicas: https://www.ceeol.com/search/article-detail?id=1043301
- Anclaje 52w (Quantpedia): https://vvv.quantpedia.com/?p=42289
- Hsu, Kuan & Shyu, Reality Check: https://ideas.repec.org/p/sin/wpaper/04-a003.html
- Campos de la kline de Binance: https://developers.binance.com/en/docs/products/connect-prime/open-apis/11.get-kline-data
- Survey de trading en cripto: https://arxiv.org/pdf/2003.11352
