# 06 — Detección de régimen y gestión de riesgo (spot + futuros USDT-M)

> Autor: agente investigador (cuant). Fecha: 2026-10-15.
> **Limitación metodológica importante:** en este contenedor `WebFetch` falló por DNS para todos los dominios probados (arxiv.org, export.arxiv.org, binance.com, concretumgroup.com, cxoadvisory.com). Toda la evidencia de abajo proviene de **resúmenes y extractos devueltos por WebSearch** (abstracts, resúmenes secundarios). No he leído los PDF completos. Las cifras numéricas se marcan con su fuente y su nivel de confianza. Nada de este informe es un resultado de backtest propio.
>
> Convención: **[EVIDENCIA]** = afirmación respaldada por fuente citada; **[SECUNDARIA]** = cifra vista en un resumen de terceros, no verificada contra el paper; **[OPINIÓN]** = juicio del autor / práctica habitual sin estudio que lo respalde.

---

## 1. Resumen ejecutivo

1. **La pieza con mejor evidencia en cripto no es un "detector de régimen" sofisticado, sino tendencia (time-series momentum) en marco diario + dimensionamiento por volatilidad objetivo.** Liu & Tsyvinski (RFS 2021) documentan momentum de series temporales fuerte en BTC/ETH/XRP a frecuencia diaria y semanal; Detzel et al. (Financial Management 2021) muestran que el ratio precio/media móvil predice retornos diarios de BTC dentro y fuera de muestra; Zarattini, Pagani & Barbon (SFI 2025) reportan Sharpe > 1.5 neto de comisiones con un ensemble de Donchian + vol target del 25 %.
2. **El volatility targeting mejora sobre todo las colas (drawdowns), y el Sharpe solo en "activos de riesgo" con efecto apalancamiento** (Harvey et al. 2018). En momentum cripto, el escalado por volatilidad es lo que convierte una estrategia con crashes en una rentable (Grobys et al. 2025). Pero hay críticas serias out-of-sample en acciones (Cederburg et al. 2020).
3. **HMM, Hurst y ADX como selectores de régimen: evidencia débil en cripto.** No encontré ningún estudio revisado por pares con backtest out-of-sample, con costes, que muestre que cambiar entre tendencia y reversión según ADX/Hurst/HMM supere a una estrategia de tendencia simple en cripto. Los HMM tienen un riesgo de look-ahead muy documentado (probabilidades suavizadas vs filtradas).
4. **Las reglas técnicas en cripto sufren data-snooping y decaimiento:** Hudson & Urquhart encontraron predictibilidad con ~15 000 reglas, pero **BTC no mostró predictibilidad en el periodo fuera de muestra**; un estudio de 2023 sobre BTC/ETH 2022-23 no encontró estrategias rentables tras el ajuste por data-snooping.
5. **Correlación:** las altcoins se vuelven más correlacionadas con BTC en estrés (contagio). Diversificar entre 20 alts no es diversificar 20 veces; hay que limitar la exposición agregada como si fuera una sola apuesta beta-BTC.
6. **Recomendación central [OPINIÓN fundamentada]:** abandonar 1m como timeframe de señal. Usar 4h/1d para la señal de régimen y tendencia, sizing por riesgo (ATR) acotado por vol target de cartera, Kelly ≤ 0.25, kill-switch diario, límite de beta-BTC agregado, y una meta-estrategia **conservadora** (régimen → "permitir/bloquear" familias de estrategias, no optimizar cambios finos).

---

## 2. Hallazgos con evidencia

### 2.1 Tendencia / momentum de series temporales (base del filtro de régimen)

| Fuente | Qué encontró | Confianza |
|---|---|---|
| Liu & Tsyvinski, *Risks and Returns of Cryptocurrency*, RFS 34(6) 2021. NBER w24877: https://www.nber.org/system/files/working_papers/w24877/w24877.pdf · SSRN: https://papers.ssrn.com/abstract=3226806 | "Strong time-series momentum effect" en BTC, XRP, ETH; significativo a frecuencias diaria y semanal; más débil en ETH. Cripto sin exposición a factores tradicionales. | [EVIDENCIA] (abstract). Cifras de quintiles (11.2 % vs 2.6 % semanal) solo vistas en resumen de CXO: https://www.cxoadvisory.com/currency-trading/crypto-asset-risks-and-returns/ → [SECUNDARIA] |
| Detzel, Liu, Strauss, Zhou, Zhu, *Learning and predictability via technical analysis*, Financial Management 50(1) 2021. https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html | Ratio precio/MA (5,10,20,50,100 días) predice retornos diarios de BTC in- y out-of-sample; estrategia "long si precio > SMA, si no cash" genera alpha y mejora de Sharpe vs buy&hold. | [EVIDENCIA] |
| Zarattini, Pagani, Barbon, *Catching Crypto Trends*, SFI RP 25-80 (2025). https://ideas.repec.org/p/chf/rpseri/rp2580.html · https://concretumgroup.substack.com/p/catching-crypto-trends | Ensemble de canales Donchian con 9 lookbacks, sizing por vol objetivo 25 % anual, exposición ≤ 200 %, top-20 monedas más líquidas. Sharpe > 1.5 neto, alpha anual 10.8 % vs BTC. | [EVIDENCIA] (abstract). Cifras por activo (BTC CAGR 30 %, Sharpe 1.56, MDD 19 %; ETH 27 %/1.51/15 %; BNB 17 %/1.06/17 %; cartera MDD 11 %) → [SECUNDARIA] vía https://github.com/alfred1123/Quant_Strategies/pull/61 y https://www.quantifiedstrategies.com/crypto-trend-trading-strategy-for-bitcoin/ |
| Replicación independiente (proyecto personal) https://gurufinanceinsights.substack.com/p/the-simplest-trend-following-system / issue https://github.com/zebadee2kk/DeFi-TraderStack-Agent/issues/137 | Réplica BTC diario long-only 2018-2026: ~16 % CAGR, MDD ~-20 %; con 0.15 %/lado CAGR ~15.6 %. **Muy por debajo del buy&hold (37 % CAGR, MDD -77 %) en retorno, pero con 1/4 del drawdown.** | [SECUNDARIA], útil como contrapeso: la cifra del paper (30 %) no se reprodujo en este periodo. |
| Borgards, *Dynamic time series momentum of cryptocurrencies*, NAJEF 57 (2021). https://econpapers.repec.org/RePEc:eee:ecofin:v:57:y:2021:i:c:s1062940821000590 | Periodos de momentum en 20 criptos más largos y grandes que en acciones US. | [EVIDENCIA] (abstract) |
| Grobys et al., *Cryptocurrency momentum has (not) its moments*, FMPM 2025. https://link.springer.com/article/10.1007/s11408-025-00474-9 · https://osuva.uwasa.fi/handle/10024/20018 | Momentum cripto (cross-sectional) sufre crashes severos; **una sola moneda puede anular la significancia**; el escalado por volatilidad lo corrige con ganancias sustanciales; fenómeno de large caps. | [EVIDENCIA] (abstract) |

**Lectura crítica:** la evidencia de tendencia es la más robusta del área, pero (a) proviene casi toda de datos diarios, no intradía; (b) los papers recientes de la misma familia (Zarattini) son working papers de un grupo que también vende investigación (Concretum) — posible sesgo; (c) la réplica independiente muestra resultados bastante peores en 2018-2026.

### 2.2 Volatility targeting / volatility-managed

| Fuente | Hallazgo | Confianza |
|---|---|---|
| Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert, *The Impact of Volatility Targeting*, JPM 45(1) 2018. https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf · https://www.man.com/insights/the-impact-of-volatility-targeting | >60 activos desde 1926. Mejora Sharpe solo en activos de riesgo (acciones, crédito) por el efecto apalancamiento (correlación negativa retorno-volatilidad); **reduce colas extremas en todas las clases**. El escalado introduce algo de momentum. | [EVIDENCIA] |
| Cederburg, O'Doherty, Wang, Yan (crítica), https://www.lehigh.edu/~xuy219/research/COWY.pdf | En 103 estrategias de acciones, las carteras vol-managed **no** superan sistemáticamente a las no gestionadas out-of-sample; las alphas de spanning no son implementables en tiempo real; inestabilidad estructural. | [EVIDENCIA] |
| DeMiguel, Martín-Utrera, Uppal, JF 2024. https://lbsresearch.london.edu/id/eprint/3716 | Versión multifactor condicional sí supera out-of-sample neta de costes. | [EVIDENCIA] |
| Vol targeting en cripto específico | **No encontré un estudio revisado por pares que aísle el efecto del vol targeting sobre el Sharpe de BTC**. Solo Grobys (momentum) y Zarattini (tendencia) lo usan como componente. Un preprint arXiv (https://arxiv.org/pdf/2603.23480) lo usa como envoltorio en una cartera con señales de stablecoins. | Brecha de evidencia |

**Implicación:** usar vol targeting como **control de riesgo** (cortar colas, normalizar exposición entre monedas con volatilidades muy distintas), no como fuente de alpha. En cripto la relación retorno-volatilidad no es claramente negativa (a veces las subidas son de alta volatilidad), así que el beneficio en Sharpe no está garantizado [OPINIÓN].

### 2.3 Estimación de volatilidad
- Bitcoin presenta clustering y memoria larga en volatilidad (Bariviera, https://arxiv.org/abs/1709.08090: "volatility shows long memory throughout"). [EVIDENCIA]
- Modelos HAR-RV con saltos (HARQ-F-J) dan el mejor pronóstico a 1 día de la volatilidad de BTC entre 18 variantes; saltos y rupturas estructurales importan. https://eu.vlex.com/vid/forecasting-the-volatility-of-1049450990 [EVIDENCIA, abstract]
- **Práctica recomendada [OPINIÓN]:** EWMA de retornos (half-life 10-30 días en diario, o realized vol de barras 1h agregada) es suficiente para sizing; HAR es mejora marginal. Usar max(vol_corta, vol_larga) para ser conservador al subir la vol.

### 2.4 Detección de régimen

**ADX / EMA200 / filtros de volatilidad**
- Detzel et al. respaldan indirectamente el filtro "precio vs MA" en BTC. [EVIDENCIA]
- Umbrales ADX (<20 rango, >25 tendencia, 20-25 zona de transición donde ambas fallan) son **convención de practicantes**, sin estudio cripto out-of-sample: https://nexusfi.com/a/risk-management/regime-adaptive-risk-management · https://www.luxalgo.com/library/concept/volatility-regime-switches.md → [OPINIÓN de practicantes]
- Un resumen de un estudio de 2026 (no localizado) con ~2 700 backtests sobre SPY/QQQ/BTC afirma que los filtros de tendencia "cuestan" 2-4 puntos de retorno anual a cambio de protección: https://aiintrading.substack.com/p/claude-code-backtest → [SECUNDARIA no verificada]

**HMM**
- Bayesian NH-HMM de 4 estados para BTC/ETH/XRP mejor pronóstico a un paso entre los modelos probados (https://arxiv.org/pdf/2011.03741). [EVIDENCIA, pronóstico, no trading]
- HMM gaussiano de 3 estados en BTC (Computational Economics 2026): 3 estados mejor balance (BIC/out-of-sample); backtest de 6 meses Sharpe ~1.01 — no consta si incluye costes, y 6 meses es irrelevante estadísticamente. https://link.springer.com/article/10.1007/s10614-026-11338-3 [EVIDENCIA débil]
- **Riesgo de look-ahead:** misma estrategia en SPY con HMM 2 estados: Sharpe 0.78 con probabilidades filtradas (causales) vs 1.74 con suavizadas. https://github.com/dmitridefreitas-dev/regime-detection [EVIDENCIA — código reproducible, no paper]. Cualquier HMM que use `predict()` de hmmlearn (Viterbi sobre toda la serie) **filtra el futuro**.
- Paper HAL sobre HMM bayesiano advierte de falsas señales → muchas operaciones → costes. https://ideas.repec.org/p/hal/wpaper/hal-04608937.html

**Hurst**
- La eficiencia de BTC varía en el tiempo: persistente en los primeros años, más eficiente desde 2014 (DFA). R/S tiende a sobreestimar memoria larga. https://arxiv.org/abs/1709.08090 [EVIDENCIA]
- Las conclusiones dependen fuertemente del estimador, periodo y fuente de datos (tabla resumen: https://jfin-swufe.springeropen.com/articles/10.1186/s40854-025-00773-0/tables/3). [EVIDENCIA]
- Uso de Hurst local para pares en cripto: los spreads con H anti-persistente revierten significativamente más rápido (Grande et al., Mathematics 2024: https://ideas.repec.org/a/gam/jmathe/v12y2024i18p2911-d1480990.html). [EVIDENCIA] — aplicable a stat-arb, no a direccional.
- Hurst + Q-learning para cambiar momentum/reversión: informe estudiantil (https://arxiv.org/pdf/2205.11122): más retorno, pero más riesgo. [EVIDENCIA débil]
- **Problema práctico [OPINIÓN]:** Hurst en ventanas cortas (<250 obs) tiene un sesgo y varianza enormes; con 100 barras el intervalo de confianza de H suele abarcar 0.4-0.6, por lo que no discrimina régimen. Útil solo como feature secundaria con ventanas largas.

**Selección dinámica de estrategia (meta-estrategia)**
- No encontré ningún paper revisado por pares, con backtest out-of-sample y costes, que demuestre que cambiar entre trend y mean-reversion por régimen supere a trend-only en cripto. Lo publicado es de blogs/practicantes. [Brecha de evidencia]
- Advertencia razonable de practicantes: un sistema conmutado debe batir out-of-sample a cada componente sin conmutar antes de confiar en los parámetros extra; un flag de régimen que "repinta" intrabar corrompe todo lo que depende de él. https://www.luxalgo.com/library/concept/volatility-regime-switches.md [OPINIÓN de practicantes, pero metodológicamente correcta]
- Reversión a la media en BTC horario: tesis que encontró comportamiento mean-reverting en datos horarios y que Bollinger tuvo mejor ratio ajustado al riesgo en 2020-2025 (https://www.theseus.fi/handle/10024/902903). [EVIDENCIA débil — tesis de grado]. Esto es coherente con la idea "tendencia en diario, reversión en intradía", pero no es concluyente.

### 2.5 Data-snooping y decaimiento
- Hudson & Urquhart (Annals of OR): ~15 000 reglas, 5 clases; predictibilidad sobrevive a tests de hipótesis múltiples, **pero BTC sin predictibilidad out-of-sample** (las alts sí). https://hull-repository.worktribe.com/output/2328042 · https://link.springer.com/article/10.1007/s10479-019-03357-1 [EVIDENCIA]
- Estudio 2023 (BTC/USDT, ETH/USDT 2022-2023): ninguna de 4 estrategias técnicas rentable tras ajuste por data-snooping. https://articlegateway.com/index.php/JAF/article/download/6453/6095 [EVIDENCIA]
- Paper 2025 que revisita TA+ML en BTC: solo el ratio log-MA de corto plazo y el índice de hashrate muestran rentabilidad genuina in/out-of-sample. https://arxiv.org/html/2511.00665v1 [EVIDENCIA, abstract]
- ML en BTC con costes y walk-forward: estrategias "naive" por signo colapsan tras costes por exceso de rotación; un filtro consciente de costes reduce la rotación. https://arxiv.org/html/2606.00060 [EVIDENCIA, abstract]

**Implicación directa para el bot actual:** operar en 1m con Bollinger+RSI es exactamente el caso donde los costes (0.1 % spot taker por lado; ~0.04-0.05 % futuros taker) destruyen la ventaja. [OPINIÓN fundamentada en lo anterior]

### 2.6 Stops (ATR)
- Kaminski & Lo, *When do stop-loss rules stop losses?*, J. Financial Markets 18 (2014): bajo paseo aleatorio un stop 0/1 **siempre reduce** el retorno esperado; con momentum (autocorrelación positiva) puede añadir valor. https://dspace.mit.edu/handle/1721.1/114876 [EVIDENCIA]
- Lo & Remorov (2017): con autocorrelación y costes, el stop supera a buy&hold solo si hay suficiente autocorrelación; costes altos lo revierten (resumen en búsqueda). [EVIDENCIA, secundaria]
- **Implicación:** los stops (y trailing stops) tienen sentido teórico **en estrategias de tendencia**; en reversión a la media un stop ajustado corta justo cuando la tesis es más atractiva → usar stops de catástrofe amplios + salida por tiempo. [Inferencia]

### 2.7 Kelly fraccional
- Kelly completo produce drawdowns enormes; colas pesadas y parámetros inestables reducen el apalancamiento óptimo (estudio Monte Carlo sobre dependencia de trayectoria: https://pmc.ncbi.nlm.nih.gov/articles/PMC9955835 ; limitaciones: https://www.arxiv-vanity.com/papers/1710.01787/). [EVIDENCIA, general no cripto]
- Tablas "full Kelly MDD 50-80 %, quarter Kelly 12-20 %" circulan en webs de practicantes sin estudio citado → [OPINIÓN].
- **Conclusión:** en cripto el edge estimado de un backtest está sesgado al alza (data-snooping), así que Kelly sobre ese edge sobredimensiona. Usar Kelly solo como **techo**, con fracción ≤ 0.25 y edge descontado ("haircut" del 50 %). [OPINIÓN]

### 2.8 Correlación y exposición de cartera
- Contagio de BTC hacia las demás criptos tras el crash de 2017-18 (Ferreira & Pereira, DCCA). https://ideas.repec.org/a/gam/jjrfmx/v12y2019i3p115-d247119.html [EVIDENCIA]
- Conectividad alta en periodos de alta incertidumbre; BTC es el principal transmisor (Antonakakis et al. 2019) y contagio de BTC en casi todas de 50 criptos líquidas (Silva et al. 2019) — citados en el mismo resultado. [EVIDENCIA, resumen]
- Alts más afectadas que BTC en COVID; alta correlación hace fallar coberturas cruzadas. https://african-review.com/journal/online-first/AREF%20article%20Abraham%20final.pdf [EVIDENCIA]
- Oct-2025: correlación BTC-ETH 0.69 → 0.73 tras el crash del 10-oct (CoinMetrics vía Cointelegraph) https://cointelegraph.com/news/without-bitcoin-what-happens-to-ether-and-xrp [SECUNDARIA, prensa]

### 2.9 Futuros USDT-M: márgenes y funding (documentación oficial, leída solo vía extractos)
- Margen de mantenimiento = nocional × tasa MMR del tramo − importe de mantenimiento del tramo; el apalancamiento máximo baja al aumentar la posición; Binance puede cambiar tasas < 0.5 % sin anuncio; desde 12-ago-2025 sub-cuentas de usuarios normales limitadas a 5x. https://www.binance.com/en/support/faq/360033162192 [EVIDENCIA — FAQ oficial, extracto vía búsqueda; usar endpoint `GET /fapi/v1/leverageBracket` como fuente de verdad]
- Funding = interés + media ponderada del Premium Index (8 h); interés por defecto 0.03 %/día (0.01 % por intervalo); liquidación a 00:00/08:00/16:00 UTC (algunos contratos tienen intervalos distintos). Fuente secundaria que cita FAQ 360033525031: https://www.tradingview.com/script/BKa9AHJx-Binance-Funding-Rates-vichtoreb [SECUNDARIA de documentación oficial]
- He, Manela, Ross, von Wachter, *Fundamentals of Perpetual Futures* (arXiv 2212.06888): desviaciones de perps respecto a no-arbitraje mayores que en divisas, co-mueven entre criptos y **disminuyen con el tiempo**; estrategia simple con Sharpe alto incluso con las comisiones más altas de Binance (versión v2). https://arxiv.org/abs/2212.06888v6 [EVIDENCIA, abstract; la ventaja se erosiona]
- Funding extremo como predictor de correcciones: **no encontré estudio académico**; solo afirmaciones de practicantes. [OPINIÓN]

---

## 3. Qué sirve y qué no en cripto (síntesis crítica)

| Herramienta | Veredicto | Motivo |
|---|---|---|
| Tendencia diaria (precio vs SMA, Donchian, TSMOM) | **Sirve** (la mejor evidencia) | Liu-Tsyvinski, Detzel, Zarattini, Borgards. Cuidado: decaimiento en BTC (Hudson-Urquhart OOS). |
| Vol targeting / risk parity entre monedas | **Sirve como control de riesgo** | Reduce colas (Harvey); rescata momentum (Grobys). No asumir alpha. |
| Filtro EMA200 / SMA(100-200) diario como "risk-on/off" | **Sirve como filtro grueso** | Coherente con Detzel; cuesta retorno en mercados alcistas fuertes. |
| ADX umbrales fijos | **Débil** | Convención; no hay evidencia cripto OOS. Usar solo como confirmación, con histéresis. |
| HMM | **Débil / peligroso** | Look-ahead fácil; sobreajuste; muchas transiciones → costes. Solo con probabilidades filtradas y walk-forward. |
| Hurst rolling | **Débil para direccional** | Estimador ruidoso en ventanas cortas; resultados dependen del método. Algo útil en pares. |
| Mean reversion intradía | **Incierto** | Alguna evidencia en BTC horario (tesis); muy sensible a costes. No en 1m. |
| Stops ATR | **Sirve en tendencia**, cuestionable en reversión | Kaminski-Lo. |
| Kelly completo | **No** | Edge sobreestimado + colas pesadas. Fracción ≤ 0.25 como techo. |
| Límites de pérdida diaria / kill-switch | **Sin evidencia académica, pero imprescindible operativamente** | Protege contra bugs, gaps, cascadas de liquidación. [OPINIÓN] |
| Límite de correlación / beta-BTC agregada | **Sirve** | Contagio documentado; diversificación entre alts colapsa en estrés. |
| Funding como señal direccional | **No probado** | Solo practicantes. Útil como filtro de coste/crowding y para no pagar carry. |

---

## 4. Variables cuantitativas exactas (definiciones para implementar)

Todas calculadas **sólo con barras cerradas** (sin repintado). `t` = barra cerrada actual.

- `r_t = ln(C_t / C_{t-1})`
- `ATR_n` = media de Wilder del True Range, `TR_t = max(H_t−L_t, |H_t−C_{t−1}|, |L_t−C_{t−1}|)`; n = 14 (4h/1d) o 20.
- `ATRp_t = ATR_n / C_t` (ATR porcentual).
- `σ_ewma,t` (anualizada) = sqrt(EWMA(r², λ) × B), λ = 1 − 2/(N+1), N = 20-60 barras; B = barras/año (cripto 24/7: 1d → 365; 4h → 2190; 1h → 8760).
- `σ_est = max(σ_ewma(N=20), σ_ewma(N=60))` (conservador).
- `VolPct_t` = percentil de `ATRp_t` en ventana de 365 días (o 2190 barras 4h).
- `TrendScore_t` (ensemble Donchian, inspirado en Zarattini; valores exactos del paper no verificados): para cada L ∈ {20, 30, 60, 90, 150, 250, 360} días: `s_L = +1` si `C_t ≥ max(H_{t−L..t−1})` (ruptura) y se mantiene +1 mientras `C_t > trailing_L`; `−1` simétrico (solo futuros); `0` en otro caso. `TrendScore = mean(s_L)` ∈ [−1, 1].
- `MAratio_t = C_t / SMA_n(C)_t − 1`, n ∈ {20, 50, 100, 200} (Detzel).
- `ADX_14` (Wilder) con histéresis: entrar en "tendencia" si ADX > 25, salir si ADX < 20.
- `ER_n` (Kaufman Efficiency Ratio) = |C_t − C_{t−n}| / Σ|C_i − C_{i−1}|, n = 20-30. Alternativa más estable que ADX [OPINIÓN].
- `H_t` (Hurst por DFA) en ventana ≥ 500 barras; usar solo como feature, no como gatillo.
- `P(state | info_t)` HMM: **probabilidad filtrada** (forward algorithm), re-entrenado walk-forward; nunca Viterbi/smoothed.
- `ρ_ij` = correlación de retornos diarios en 30-90 días; `β_i` = beta de la moneda i vs BTC (90 días).
- `Funding_t` (último y media 3 días = 9 liquidaciones), anualizado = funding × (3 × 365).
- `Basis_t = (MarkPrice_perp − IndexPrice)/IndexPrice`.
- `ADV30` = mediana del volumen en USDT de 30 días (filtro de liquidez; Zarattini usa ≥ 2 M USD/día y ≥ 1 año listado [SECUNDARIA]).
- Costes: spot taker 0.10 %, futuros taker ~0.05 % / maker ~0.02 % (verificar con `GET /api/v3/account/commission` y `/fapi/v1/commissionRate`) + slippage estimado ≥ 0.05 % por lado en alts. [Comisiones exactas: verificar en la cuenta; no comprobado aquí]

---

## 5. Estrategias candidatas (reglas implementables)

### Candidata A — Tendencia ensemble Donchian con vol targeting (núcleo, spot y futuros)

- **Familia:** time-series momentum / trend following.
- **Mercado:** spot (solo largos) y futuros USDT-M (largos y cortos; la pata corta tiene menos evidencia — tratarla como experimental).
- **Timeframe:** señal en **1d** (cierre 00:00 UTC). Variante 4h para test, esperando más rotación.
- **Universo:** top-20 por ADV30 de pares USDT con ≥ 365 días de historial y ADV30 ≥ 5 M USDT (spot) / ≥ 20 M USDT (futuros). Excluir stablecoins y tokens apalancados. Recalcular semanalmente.
- **Señal por moneda:** `TrendScore` con lookbacks L ∈ {20, 30, 60, 90, 150, 250, 360}.
  - Para cada L: entrada larga si `C_t > max(H_{t−L..t−1})`. Stop trailing de esa sub-señal: `trail_L = max(trail_L previo, C_t − k·ATR_20)`, k = 2.5-4 (o el mínimo de L/2 barras; elegir uno y fijarlo). **El trailing nunca baja.** Sub-señal sale (=0) cuando `C_t < trail_L`.
  - Futuros: simétrico para cortos (`C_t < min(L_{t−L..t−1})`).
- **Peso objetivo:** `w_i = TrendScore_i × (σ_target_asset / σ_est,i)`, con `σ_target_asset = 25 %/√N_activos_activos` *o* más simple: vol target por activo 25-40 % anual y luego escalar la cartera (ver Candidata D). Tope por activo `|w_i| ≤ 1.0` en spot (sin apalancamiento), ≤ 2.0 en futuros.
- **Rebalanceo:** diario; solo operar si `|w_i_nuevo − w_i_actual| > 20 %` del objetivo (banda anti-rotación).
- **Stop de catástrofe (orden en exchange):** `C_entry − 4·ATR_20` (spot: orden STOP_LOSS_LIMIT/OCO; futuros: STOP_MARKET reduceOnly con `workingType=MARK_PRICE`).
- **Salida:** cuando TrendScore llega a 0 o cambia de signo; o stop de catástrofe.
- **Filtros:** no abrir largos si `Funding_3d anualizado > 50 %` en futuros (coste de carry/crowding) [OPINIÓN]; no abrir si ADV cae bajo el umbral.
- **Parámetros y rangos:** lookbacks fijos (no optimizar individualmente); k ∈ [2.5, 4]; vol target por activo ∈ [20 %, 40 %]; banda rebalanceo ∈ [10 %, 30 %].
- **Datos:** OHLCV 1d (spot y perp), ADV, funding (futuros), leverage brackets.
- **Régimen:** funciona en tendencias persistentes (2017, 2020-21, 2023-24). Falla en rangos con roturas falsas (whipsaw, 2019, 2022 H2 lateral) y en V-reversals violentos; rinde menos que buy&hold en mercados alcistas continuos.
- **Evidencia:** Zarattini et al. 2025; Liu & Tsyvinski 2021; Detzel et al. 2021; réplica independiente con resultados más modestos. Riesgo de decaimiento (Hudson-Urquhart OOS en BTC).

### Candidata B — Filtro de régimen "risk-on/off" de mercado (meta-capa) + sizing por riesgo

- **Familia:** regime filter / meta-estrategia conservadora.
- **Mercado:** ambos. Es una capa que **habilita o bloquea** las demás estrategias.
- **Timeframe:** 1d para el régimen; las estrategias hijas pueden ir en 4h/1h.
- **Definición de régimen (BTC como proxy de mercado, por el contagio documentado):**
  - `Trend_BTC = +1` si `C_BTC > SMA200_BTC` **y** `SMA50 > SMA200`; `−1` si ambas condiciones invertidas; `0` si mixto.
  - `Vol_regime`: `VolPct_BTC` (percentil de ATRp 365d): bajo < 30, medio 30-80, alto > 80.
  - `Direccionalidad`: `ER_30(BTC)` > 0.35 → tendencial; < 0.20 → rango (con histéresis: cambiar solo si la condición se mantiene 3 cierres seguidos).
- **Tabla de habilitación:**
  | Trend_BTC | Vol | ER | Permitido |
  |---|---|---|---|
  | +1 | bajo/medio | tendencial | Tendencia larga (A), exposición 100 % del presupuesto |
  | +1 | alto | cualquiera | Tendencia larga con 50 % del presupuesto |
  | 0 | bajo/medio | rango | Reversión (C) con 50 %; tendencia sin nuevas entradas |
  | −1 | cualquiera | cualquiera | Spot: solo cash/stable (o 25 %). Futuros: cortos de A con 50 %; reversión larga **bloqueada** |
  | cualquiera | > percentil 95 | — | Sin nuevas entradas 24 h (shock) |
- **Sizing por operación (todas las hijas):** `qty = (Equity × riesgo_por_trade) / (k × ATR_n)`, riesgo_por_trade ∈ [0.25 %, 1 %]; luego `notional ≤ min(cap_activo, vol-target cap)`.
- **Parámetros:** SMA 50/200; ER umbrales 0.20/0.35; percentiles 30/80/95; confirmación 2-5 cierres.
- **Datos:** OHLCV 1d de BTC (y opcionalmente ETH), ATR.
- **Régimen:** reduce drawdowns en bear markets prolongados (2018, 2022). Falla en giros rápidos (entra tarde en recuperaciones en V; cuesta retorno, ~2-4 pts/año según resumen no verificado).
- **Evidencia:** Detzel (precio vs MA), contagio BTC (Ferreira-Pereira; Antonakakis); Harvey (reducir exposición en alta vol corta colas). **La tabla de habilitación es [OPINIÓN]** — debe validarse walk-forward contra "A sola" y "C sola".

### Candidata C — Reversión a la media intradía condicionada a régimen de rango

- **Familia:** mean reversion.
- **Mercado:** spot (largos) y futuros (largos/cortos). Solo top-10 por liquidez (coste).
- **Timeframe:** 1h (no 1m). Contexto en 1d (Candidata B debe marcar "rango").
- **Entrada larga:** régimen B = rango **y** `C_1h < SMA20_1h − 2.0·σ20_1h` (Bollinger 20,2) **y** `RSI2 < 10` **y** `C_1h > SMA200_1d × 0.9` (no "cuchillo cayendo" muy por debajo de tendencia). Corto simétrico en futuros solo si `Funding_3d > 0` (los largos pagan) [OPINIÓN].
- **Salida:** `C ≥ SMA20_1h` (vuelta a la media) o tras 24 barras (salida por tiempo).
- **Stop:** catástrofe a `entry − 3·ATR14_1h` (amplio, por Kaminski-Lo: stops ajustados destruyen reversión).
- **Sizing:** riesgo 0.25-0.5 % por trade según distancia al stop; máx. 3 posiciones de reversión simultáneas.
- **Filtro de costes:** solo operar si `(SMA20 − C)/C > 3 × coste_ida_vuelta` (p. ej. > 0.6 % en spot).
- **Parámetros:** Bollinger 20 × [1.8, 2.5]; RSI2 [5, 15]; tiempo máx. [12, 48] barras.
- **Datos:** OHLCV 1h y 1d; funding.
- **Régimen:** funciona en rangos de baja/media volatilidad. **Falla gravemente** en tendencias bajistas y cascadas de liquidación.
- **Evidencia:** débil (tesis BTC horario https://www.theseus.fi/handle/10024/902903); Hudson-Urquhart muestran que muchas reglas no sobreviven OOS en BTC; estudio 2022-23 sin estrategias rentables tras snooping. **Marcar como experimental; solo pasa a real si supera walk-forward con costes.**

### Candidata D — Capa de riesgo de cartera (obligatoria, envuelve A/B/C)

- **Familia:** risk management / volatility targeting de cartera.
- **Mercado:** ambos (cuenta spot y cuenta futuros se agregan en una sola visión de riesgo).
- **Reglas:**
  1. **Vol target de cartera:** estimar `σ_p = sqrt(wᵀ Σ w)` con Σ = covarianza EWMA de retornos diarios (half-life 30 d). Escalar todos los pesos por `min(1, σ_target / σ_p)`, σ_target ∈ [15 %, 30 %] anual. Nunca escalar por encima de 1 en spot; en futuros cap de apalancamiento bruto total ≤ 2x.
  2. **Beta-BTC agregada:** `Σ_i w_i·β_i ∈ [−1.0, +1.0]` (spot: [0, 1]). Si se excede, recortar proporcionalmente las posiciones de mayor β.
  3. **Clusters de correlación:** si `ρ_ij > 0.8` (90 d) tratar i y j como un solo activo para el límite por activo (máx. 25 % del riesgo total por cluster).
  4. **Límite de pérdida diaria:** si `PnL_día (realizado + no realizado, mark price) ≤ −2 %` del equity al inicio del día UTC → cerrar nuevas entradas hasta 00:00 UTC; si `≤ −4 %` → cerrar todo y pausar 24 h. [OPINIÓN, rango 1.5-3 % / 3-6 %]
  5. **Drawdown circuit breaker:** si DD desde máximo > 15 % → reducir riesgo a la mitad; > 25 % → pausa y revisión humana.
  6. **Kelly como techo:** `f* = μ/σ²` estimado walk-forward, con μ descontado 50 %; riesgo efectivo ≤ 0.25·f*. Si `f*` ≤ 0 en la ventana reciente de la estrategia → desactivarla (meta-selección por desempeño, ventana ≥ 100 trades).
  7. **Futuros — distancia a liquidación:** usar margen aislado; exigir `|precio_liq − entry| ≥ 3 × distancia_stop`; apalancamiento por posición = el mínimo que satisface el nocional (normalmente 2-3x), nunca el máximo del bracket. Consultar `leverageBracket` antes de cada orden.
  8. **Funding:** incluir el funding esperado en el coste; cerrar/no abrir si el funding acumulado previsto en el horizonte medio de holding > 30 % del beneficio esperado.
- **Datos:** retornos diarios de todas las posiciones, betas, equity en tiempo real, mark price, brackets, funding.
- **Régimen:** siempre activa. Falla (parcialmente) en gaps instantáneos/cascadas donde los stops se ejecutan con slippage grande — mitigado por apalancamiento bajo.
- **Evidencia:** Harvey et al. 2018 (colas); Grobys 2025 (vol scaling en crypto momentum); contagio (Ferreira-Pereira 2019); Kelly con colas pesadas (PMC9955835). Los umbrales numéricos de pérdida diaria/DD son **[OPINIÓN]**.

### Candidata E (experimental, solo investigación) — Régimen por HMM filtrado

- **Familia:** regime detection estadística.
- **Mercado:** ambos como sustituto de la tabla de B.
- **Reglas:** HMM gaussiano de 2-3 estados sobre features diarias `[r_t, ln σ_ewma20, MAratio_50]` de BTC; ajuste en ventana expanding con re-entrenamiento mensual (walk-forward); usar **solo probabilidad filtrada** `P(estado_bajista | datos ≤ t)`; reducir exposición al 50 % si > 0.6 y a 0 % si > 0.8; histéresis de 3 días; ordenar estados por media de retorno en cada re-entrenamiento (para evitar label switching).
- **Parámetros:** n_estados ∈ {2, 3}; umbrales 0.6/0.8; ventana mínima 3 años.
- **Datos:** OHLCV 1d BTC.
- **Régimen:** útil en transiciones prolongadas de volatilidad. Falla por label switching, inestabilidad de parámetros y retraso.
- **Evidencia:** débil (Springer 2026 con backtest de 6 meses; repo que muestra Sharpe 0.78 vs 1.74 por look-ahead). **Solo adoptar si en walk-forward bate a B (SMA200+ER), que es más simple.**

---

## 6. Protocolo de validación recomendado (para el harness de implementación)

1. **Datos:** OHLCV diario/4h/1h de spot y perps (descarga vía data.binance.vision desde una máquina con acceso; este contenedor no lo tiene). Funding histórico (`/fapi/v1/fundingRate`).
2. **Walk-forward** con re-optimización mínima; parámetros fijos de la literatura primero.
3. **Costes realistas:** 0.10 %/lado spot, 0.05 %/lado futuros + 0.05 % slippage; test de sensibilidad a 2× costes.
4. **Corrección por múltiples pruebas:** registrar cuántas variantes se prueban; usar Deflated Sharpe Ratio (Bailey & López de Prado) o White Reality Check / SPA. [Metodología citada en https://www.fmg.ac.uk/publications/discussion-papers/data-snooping-technical-trading-rule-performance-and-bootstrap]
5. **Benchmarks obligatorios:** buy&hold BTC, cartera equiponderada top-10, A sin capa de régimen. La meta-estrategia solo se acepta si bate a **cada** componente sin conmutar out-of-sample.
6. **Sesgo de supervivencia:** incluir monedas deslistadas en el universo histórico.
7. **Periodos de estrés a reportar por separado:** mar-2020, may-2021, may-2022 (LUNA), nov-2022 (FTX), 10-oct-2025.

---

## 7. Advertencias sobre la calidad de la evidencia

- Ninguna fuente fue leída íntegramente (WebFetch bloqueado). Cifras de rendimiento de Zarattini et al. y Liu-Tsyvinski por quintiles son **secundarias**.
- Sesgo de publicación: los resultados negativos de reglas técnicas en cripto se publican menos; los positivos vienen a menudo de grupos con interés comercial (Concretum, vendors).
- Casi no existe evidencia académica sobre: selección dinámica de estrategia en cripto, funding como señal direccional, límites de pérdida diaria, ADX en cripto. Todo eso en este informe es **[OPINIÓN]** y debe tratarse como hipótesis a validar.
- La predictibilidad de BTC parece haber disminuido con el tiempo (Bariviera; Hudson-Urquhart OOS; He et al. sobre perps). Esperar resultados futuros inferiores a los backtests históricos.
