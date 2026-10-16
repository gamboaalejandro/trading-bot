# 02 — Mean reversion y stat-arb en cripto (spot + futuros USDT-M Binance)

> Informe del investigador cuantitativo. Fecha: 2026-10-15.
> **Convención:** `[EVIDENCIA]` = afirmado por una fuente citada (paper, documentación o backtest publicado). `[OPINIÓN]` = juicio propio del autor de este informe, sin respaldo empírico directo. `[NO VERIFICADO]` = cifra que aparece en resúmenes o buscadores pero cuyo texto completo no se pudo leer.
>
> **Limitación metodológica importante:** en este contenedor WebFetch no resolvía DNS (arxiv.org, quantpedia.com y ledger.pitt.edu daban `ENOTFOUND`, y curl recibía 403 del proxy). Todas las cifras proceden de **resúmenes, abstracts y fichas bibliográficas obtenidos con WebSearch**, no de la lectura completa de los PDF. Los parámetros exactos de los papers (umbrales de z, ventanas) que no aparecían en esos resúmenes **no se han inventado**: se indica "no disponible". Antes de producción conviene que alguien lea los PDF completos.

---

## 1. Resumen ejecutivo

1. **Existe evidencia de reversión a la media intradía en BTC, en horizontes de 1h a 4h** (autocorrelación negativa de primer orden en retornos de 1h, 2h y 4h; los movimientos más grandes revierten más, en %). El autor lo atribuye a sobrerreacción, exceso de volatilidad y liquidaciones en cascada por apalancamiento. `[EVIDENCIA]` De Nicola (2021), *Ledger* 6, 58–80. El proceso de revisión fue polémico (el archivo de revisión abierta lo muestra) y hay trabajos que concluyen lo contrario para intradía (Resta et al., 2020: el buy & hold supera a las alternativas intradía examinadas).
2. **A horizontes diarios/semanales en las monedas grandes predomina el momentum, no la reversión.** La reversión de corto plazo en el corte transversal se concentra en monedas **pequeñas e ilíquidas** (Zaremba et al.), y por encima de 1 mes aparece reversión (Dobrynskaya). `[EVIDENCIA]` La literatura es contradictoria (Liu–Tsyvinski encuentran momentum semanal de ≈3%/semana en long-short; Grobys & Sapkota encuentran reversión).
3. **Bollinger/RSI en cripto:** casi toda la "evidencia" favorable son tesis de grado/máster, scripts de TradingView o papers con backtests cortos dentro de la muestra. Ninguno que haya encontrado aporta validación fuera de muestra con costes realistas. `[EVIDENCIA de la ausencia, OPINIÓN sobre la calidad]`
4. **Pairs trading / cointegración:** es la familia con mejor literatura académica, pero el resultado **depende críticamente de los costes y de la ejecución**. Fil & Kristoufek (2020, 26 monedas de Binance) señalan que la rentabilidad es muy sensible a costes y ventanas de ejecución, que la frecuencia alta (5m) rinde mucho más que la diaria en bruto, y que la versión realista queda en ≈+3%/mes (distancia) o en una ligera pérdida (cointegración). Un paper de 2026 (Pindza & Mba, *QFE*) encuentra **retornos netos negativos** en pairs con cópulas una vez descontados los costes. `[EVIDENCIA]`
5. **La mean reversion arruina la cuenta en tendencia**, porque promedia contra un movimiento persistente. La literatura sobre el exponente de Hurst en BTC muestra que el régimen cambia con el tiempo (persistente en algunos periodos y cercano a eficiente en otros), así que **no se puede usar una estrategia de reversión sin un filtro de régimen**. `[EVIDENCIA]` Bariviera (2017); `[OPINIÓN]` sobre la necesidad del filtro.
6. **Implicación directa para el bot actual (velas de 1m, BB+RSI long-only, stop ATR×3.5, TP 3R):** `[OPINIÓN fundada]` en 1m, el movimiento esperado por operación es del mismo orden que el coste de ida y vuelta en spot (≈0,20% taker/taker, ≈0,15% con BNB). Además, un TP de 3R es incoherente con una lógica de reversión, cuyo objetivo natural es la media (aprox. 1R o menos) y que gana por tasa de acierto, no por ratio. Recomendación: subir a 15m–4h y salir en la media.

---

## 2. Hallazgos con evidencia

### 2.1 Autocorrelación y reversión intradía en BTC
| Fuente | Qué dice | Calidad |
|---|---|---|
| De Nicola, G. (2021) "On the Intraday Behavior of Bitcoin", *Ledger* vol. 6, pp. 58–80, DOI 10.5195/LEDGER.2021.213 — https://ledger.pitt.edu/ojs/ledger/article/view/213 · https://epub.ub.uni-muenchen.de/97651/ | Autocorrelación negativa de primer orden en retornos de 1h, 2h y 4h. Los movimientos mayores producen reversiones mayores (en %). Aplica retroactivamente una estrategia algorítmica simple. Lo atribuye a sobrerreacción y liquidaciones en cascada. | Revista con revisión abierta, y la revisión fue controvertida. Las magnitudes exactas no aparecían en los resúmenes `[NO VERIFICADO]`. |
| Resta et al. (2020), citado en los mismos resultados | Operar con datos diarios fue más rentable que el intradía, y el buy & hold superó a las alternativas intradía. | Contraevidencia. Resumen secundario. |
| Tesis Theseus (2020–2025) — https://www.theseus.fi/handle/10024/902903 | BTC muestra reversión en datos horarios; la estrategia basada en Bollinger batió al momentum y al B&H. La efectividad depende mucho de si se usan datos horarios o diarios. | Tesis de grado. Evidencia débil. |

### 2.2 Bollinger / RSI
| Fuente | Qué dice | Calidad |
|---|---|---|
| LUT University (2024) — https://lutpub.lut.fi/handle/10024/168985 | Entre BB, SMA, EMA, estocástico y RSI sobre BTC (ene-2022 a ene-2024), BB obtuvo el mejor resultado neto. | Tesis, 2 años, un solo activo y sin fuera de muestra. Débil. |
| Applied Economics Letters 30(11):1437-1443 (2023) — https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html | Comprar en ruptura de la banda inferior y vender en la superior en futuros de BTC: retorno medio por operación (holding period return) >20%. | `[NO VERIFICADO]`: no pude confirmar autores ni metodología. Un retorno medio por operación >20% en futuros apalancados no dice nada sobre el drawdown. |
| Ni et al., *Applied Sciences* (dic-2023) — https://doaj.org/article/117023aaddcf4d15a0da82358f10e0b6 | Variante de BB con matriz de parámetros ("heatmap") en BTC/ETH spot, con retornos "múltiplemente superiores" al diseño convencional. | Muy probable sobreajuste por barrido de parámetros dentro de la muestra `[OPINIÓN]`. |
| Poznań (Sensors 2023) — https://kie.ue.poznan.pl/en/?p=289 | El sistema automático con RSI mostró rentabilidad superior al B&H. | Resumen sin detalle de costes. |
| Connors RSI(2): regla original (Connors & Alvarez, 2008) — https://www.luxalgo.com/library/concept/rsi-2/ ; prueba en Nasdaq-100 — https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100 | Regla: RSI(2)<5–10 con precio > SMA200, salida al cerrar por encima de la SMA5. En el Nasdaq-100 (2016–2026): +26,9% frente a +528% del B&H, con DD de −25% frente a −35,7%. | **No encontré ningún backtest publicado de RSI(2) en cripto.** En M30 el resultado es "la mayor parte del tiempo no rentable" (ProRealCode). |

**Conclusión 2.2** `[OPINIÓN]`: el uso de BB/RSI como señal de reversión en cripto carece de evidencia sólida fuera de muestra. Merece probarse solo si se combina con (a) un filtro de régimen, (b) un timeframe ≥15m y (c) la salida en la media.

### 2.3 Pairs trading y cointegración
| Fuente | Qué dice | Calidad |
|---|---|---|
| Fil, M. & Kristoufek, L. (2020) "Pairs Trading in Cryptocurrency Markets", *IEEE Access*, DOI 10.1109/ACCESS.2020.3024619 — https://ieeexplore.ieee.org/document/9200323 · https://dspace.cuni.cz/handle/20.500.11956/109634 | Prueban los métodos de distancia y de cointegración sobre 26 monedas líquidas **de Binance** a 5m, 1h y 1d. La frecuencia alta rinde mucho más: distancia diaria −0,07%/mes frente a 11,61%/mes a 5m (bruto, idealizado). Con supuestos realistas: distancia ≈+3%/mes y cointegración con ligera pérdida. Muy sensible a costes y ejecución. | Revista revisada por pares. La mejor referencia para Binance. Cifras procedentes de resúmenes. |
| Tadi, M. & Kortchemski, I. (2021) "Evaluation of Dynamic Cointegration-Based Pairs Trading Strategy in the Cryptocurrency Market", *Studies in Economics and Finance*; arXiv 2109.10662 — https://arxiv.org/abs/2109.10662v1 · https://www.researchgate.net/publication/354776945 | Usan Engle-Granger, KSS y Johansen, y fijan la ventana con el **half-life de Ornstein-Uhlenbeck**. Las señales salen de barras de 1 minuto y la ejecución se simula con bid/ask y trades reales (BitMEX). Superan al B&H, pero el Sharpe varía enormemente por par (ETH futuro vs perp 0,29; ADA–TRX >20). Formar el spread con varias monedas mejora el ratio riesgo-retorno. | Un Sharpe >20 es una señal roja de capacidad mínima o de artefacto `[OPINIÓN]`. El umbral de entrada no estaba en los resúmenes. |
| Tadi & Witzany (2023/2025) "Copula-based trading of cointegrated cryptocurrency pairs", *Financial Innovation* — https://link.springer.com/article/10.1186/s40854-024-00702-7 · arXiv 2305.06961 | Superan al B&H en bruto, pero los costes reducen sustancialmente el resultado. La variante agresiva acaba con grandes pérdidas netas. El Sharpe cae de 0,93 a 0,16 al subir el umbral de 0,10 a 0,20. | Revisado por pares. Muestra explícitamente la erosión por costes. |
| Pindza, E. & Mba, J.C. (2026) "Adaptive copula-based pairs trading with market overlay", *QFE* 10(2):378–404 — https://www.aimspress.com/article/doi/10.3934/QFE.2026016 | **Retornos netos negativos** tras costes. Solo la variante con exposición direccional se acercó al B&H. | Revisado. Evidencia en contra. |
| Leung, T. & Nguyen, H. (2019) "Constructing cointegrated cryptocurrency portfolios for statistical arbitrage", *SEF* 36(4):581–599 — https://ideas.repec.org/a/eme/sefpps/sef-08-2018-0264.html | Cesta BTC–ETH–BCH–LTC mediante Johansen y Engle-Granger. La variante **sin stop-loss** obtuvo el mayor beneficio pero también los mayores drawdowns. | Muestra pequeña (2018). |
| Dann & Kotsireas (2024), capítulo de Springer — https://econpapers.repec.org/bookchap/sprlnopch/978-3-031-68974-1_5f16.htm | Reexamina Leung-Nguyen: 100% de acierto en backtest y 79–100% en vivo. | Un 100% de acierto en backtest suele indicar muestra minúscula o sesgo `[OPINIÓN]`. |
| Tesis Turku — https://www.utupub.fi/handle/11111/24573 | La distancia fue el peor método (con pérdidas) y la cópula el mejor. | **Contradice** a Fil & Kristoufek sobre qué método funciona mejor. |
| Palazzi, R.B. (2025) *J. Futures Markets* 45(11):1911-1933 — https://ideas.repec.org/a/wly/jfutmk/v45y2025i11p1911-1933.html | 10 monedas, 2019–2024: los pares superan al pairs convencional y a la estrategia pasiva, con baja exposición al mercado. | El abstract no menciona costes. |

### 2.4 Stat-arb transversal (cesta de monedas)
| Fuente | Qué dice |
|---|---|
| Fischer, Krauss & Deinert (2019) "Statistical Arbitrage in Cryptocurrency Markets", *JRFM* 12(1):31 — https://ideas.repec.org/a/gam/jjrfmx/v12y2019i1p31-d205554.html | Random forest sobre retornos rezagados de 40 monedas (barras de 1m). Compra las 3 con mejor predicción, vende en corto las 3 peores y cierra a los 120 minutos. Fuera de muestra (jun–sep 2018, >100.000 trades): **7,1 pb/día netos con 15 pb por media vuelta**. Los propios autores advierten de límites de volumen. Periodo corto, en 2018. |
| Zaremba et al. "Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets", *IRFA* 2021 — https://www.sciencedirect.com/science/article/pii/S1057521921002349 | Reversión diaria, semanal y mensual en 200 monedas, explicada por **iliquidez**. Otro trabajo: la reversión semanal solo aparece en monedas pequeñas e ilíquidas. |
| Liu, Tsyvinski & Wu, NBER w25882 — https://www.nber.org/system/files/working_papers/w25882/w25882.pdf | Momentum semanal: long-short de ≈3%/semana de exceso de retorno. |
| Dobrynskaya, "Cryptocurrency Momentum and Reversal", *J. Alternative Investments* 26(1) — https://www.pm-research.com/content/iijaltinv/26/1/65 | Momentum hasta 2–4 semanas y reversión a partir de 1 mes (2.000 monedas, 2014–2020). |
| Epstein, Wang, Choi & Pelger (2025) "Attention Factors for Statistical Arbitrage" — https://arxiv.org/html/2510.11616v1 | **Acciones de EE. UU., no cripto.** Residuos PCA: Sharpe bruto 2,79 y neto 1,57. El benchmark OU paramétrico queda con **Sharpe neto negativo por exceso de rotación**. Lección trasladable: la rotación mata la estrategia de residuos. |

### 2.5 Régimen: cuándo la reversión destruye la cuenta
- Bariviera (2017) "The inefficiency of Bitcoin revisited: a dynamic approach" — https://arxiv.org/pdf/1709.08090 : el Hurst de BTC **varía con el tiempo**; DFA es preferible a R/S, que detecta memoria larga espuria. `[EVIDENCIA]`
- arXiv 1809.08403 "Chaos and Order in the Bitcoin Market" — https://arxiv.org/abs/1809.08403 : el Hurst generalizado detecta cambios de régimen que coinciden con eventos de mercado. `[EVIDENCIA]`
- Harbourfront Quant — https://harbourfrontquant.substack.com/p/detecting-trends-and-risks-in-crypto : DFA móvil con H>0,5 = tendencia y H<0,5 = reversión. `[OPINIÓN de practicante]`
- Quantpedia — https://quantpedia.com/trend-following-and-mean-reversion-in-bitcoin/ : cuando BTC está en un máximo local de 10–50 días tiende a **seguir** subiendo (tendencia), no a revertir. `[EVIDENCIA secundaria]`
- Trend following en cripto ("A Decade of Evidence of Trend Following Investing in Cryptocurrencies", arXiv 2009.12155 — https://paperswithcode.com/paper/a-decade-of-evidence-of-trend-following ; Zarattini et al., 2025) : el trend following funciona en BTC con horizontes diarios. `[EVIDENCIA]` con posible sesgo de autor/patrocinio.
- Liquidaciones, funding y OI: **no encontré ningún estudio académico** sobre rebotes tras cascadas. Solo hay comentarios de exchanges y blogs (Galaxy — https://www.galaxy.com/insights/perspectives/price-action-triggers-liquidation-cascade-slashing-funding-rates-and-wiping ; Blockworks — https://www.blockworks.com/news/crypto-sell-off-open-interest-funding ; Bitsgap — https://bitsgap.com/blog/liquidation-cascades-explained). `[ANECDÓTICO]`

**Mecanismo de ruina** `[OPINIÓN, consenso de practicantes]`: la reversión tiene una distribución de pagos de cola izquierda (muchas ganancias pequeñas y pérdidas grandes ocasionales). En tendencia el z-score puede quedarse por debajo de −2 durante días. Sin stop o sin filtro de régimen, una sola tendencia borra decenas de operaciones ganadoras (Leung-Nguyen: la variante sin stop tuvo el mayor beneficio y el mayor DD). Con apalancamiento en futuros, esa cola se convierte en liquidación.

### 2.6 VWAP reversion
No encontré ningún estudio publicado ni backtest verificable de reversión a VWAP intradía en cripto. Solo hay scripts de TradingView (uno diseñado para FX en 5m) y descripciones de indicadores (https://tr.tradingview.com/script/oSV81CXs-VWAP-SD2-Reversion-Long/ , https://veksi.com/docs/strategies_popular_vwap_reversion.php). En cripto el ancla diaria es arbitraria (00:00 UTC). **Veredicto:** no lo incluyo como estrategia candidata independiente. Como mucho sirve de objetivo de salida o de filtro `[OPINIÓN]`.

### 2.7 Costes en Binance (variable crítica)
- Spot VIP0: 0,10% maker y 0,10% taker; 0,075% pagando con BNB (descuento del 25%, sujeto a cambios). `[EVIDENCIA secundaria]` https://cryptopotato.com/binance-fees/ , https://support.binance.us/en/articles/9843536 (este último es de Binance.US, no de Binance global).
- Futuros USDT-M VIP0: 0,02% maker y 0,05% taker; 10% de descuento con BNB. Funding cada 8h por defecto (algunos símbolos tienen intervalos distintos). `[EVIDENCIA]` https://www.binance.com/es/support/articles/360033544231 y fuentes secundarias. **Hay que verificar la tabla vigente vía API** (`/fapi/v1/commissionRate`, `/fapi/v1/fundingInfo`) cuando haya acceso.
- Ida y vuelta: spot taker ≈0,20% (0,15% con BNB); futuros taker ≈0,10% y maker ≈0,04%. Hay que sumar el slippage (estimado en 0,02–0,10% según liquidez) `[OPINIÓN]`.
- **Regla de viabilidad** `[OPINIÓN]`: la distancia a la media en la entrada (|close − SMA| / close) debe ser ≥ 3× el coste de ida y vuelta. En spot eso es ≥0,6%; en futuros taker, ≥0,3%. En velas de 1m esto rara vez se cumple en las monedas grandes.

---

## 3. Qué sirve y qué no en cripto

| Sirve (con condiciones) | No sirve / evidencia en contra |
|---|---|
| Reversión de 1h–4h tras movimientos grandes (De Nicola), con filtro de régimen | BB/RSI en 1m sin filtro de régimen (el bot actual): el coste se come el edge `[OPINIÓN]` |
| Pairs/cestas cointegradas en **perps USDT-M** (permiten el corto barato), con reselección periódica | Pairs en spot: no se puede vender en corto sin margen. Inviable en el spot long-only actual |
| Salir en la media (z=0 / SMA), con time stop | TP fijo de 3R en reversión: contradice la lógica de la estrategia |
| Filtro de régimen (ADX, Efficiency Ratio, Hurst-DFA, pendiente de la EMA200) | Promediar a la baja sin stop (aumenta el beneficio en backtest y explota en vivo) |
| Reversión transversal **solo** en el universo líquido, y con cautela | Reversión semanal en altcoins ilíquidas: el edge existe en papel, pero es iliquidez no capturable |
| RSI(2) estilo Connors **a favor de la tendencia mayor** (comprar retrocesos en tendencia alcista) | RSI(2) contra la tendencia mayor |

---

## 4. Variables cuantitativas (definiciones exactas)

Notación: `C_t` = cierre, `H_t`, `L_t`, `V_t`; todo calculado **solo con velas cerradas** (sin look-ahead).

- **z-score de precio:** `z_t = (C_t − SMA_n(C)_t) / STD_n(C)_t`, n=20 (rango 14–50). La STD es la desviación estándar poblacional (ddof=0), igual que en Bollinger.
- **Bollinger:** `BB_up/lo = SMA_n ± k·STD_n`, n=20, k=2 (rango 1,5–2,5). `%B = (C − BB_lo)/(BB_up − BB_lo)`. `BBW = (BB_up − BB_lo)/SMA_n`; `BBW_pct` = percentil de BBW en los últimos 180 periodos.
- **RSI(p) de Wilder:** p=2 (Connors) o 14. Suavizado RMA (α=1/p).
- **ATR(14) de Wilder**, usado para stops y sizing.
- **ADX(14) de Wilder.** Rango (régimen apto para reversión) si ADX < 20–25.
- **Efficiency Ratio de Kaufman:** `ER_n = |C_t − C_{t−n}| / Σ_{i=1..n} |C_{t−i+1} − C_{t−i}|`, n=20–30. ER < 0,3 indica rango/ruido y ER > 0,5 tendencia (umbrales `[OPINIÓN]`, a calibrar).
- **Hurst por DFA** sobre log-retornos, ventana móvil de 500–1000 barras. H < 0,45 = antipersistente, H > 0,55 = persistente (umbrales `[OPINIÓN]`).
- **Variance ratio de Lo-MacKinlay:** `VR(q) = Var(r_t^{(q)}) / (q·Var(r_t))`. VR < 1 indica reversión. Sirve como confirmación (q=4, 8).
- **Pendiente de tendencia:** `slope = (EMA200_t / EMA200_{t−20}) − 1` en el TF superior.
- **Shock de retorno:** `s_t = r_t / σ_t`, con `r_t = ln(C_t/C_{t−1})` y `σ_t` = desviación estándar de r en las últimas 168 barras (1 semana en 1h).
- **Pairs:** hedge ratio β por OLS de `ln P_A` sobre `ln P_B` (o por filtro de Kalman). Spread `S_t = ln P_A − β·ln P_B − α`. Test ADF/Engle-Granger con p < 0,05. **Half-life OU:** se ajusta `ΔS_t = λ·S_{t−1} + ε`, y `HL = −ln(2)/λ` (λ<0). `z_S = (S_t − mean_w(S))/std_w(S)`, con w ≈ 3·HL acotado a [24, 720] barras.
- **Derivados (solo futuros):** funding rate (último y predicho), open interest (variación % en 1h/4h), basis perp–spot, ratio long/short. Fuente: endpoints `/fapi/v1/fundingRate`, `/fapi/v1/openInterest` y `/futures/data/openInterestHist` de Binance.
- **Liquidez:** volumen en USDT de 24h y spread bid/ask (`/api/v3/ticker/bookTicker`). Filtro de universo: volumen 24h ≥ 20 M USDT `[OPINIÓN]`.

---

## 5. Estrategias candidatas (reglas implementables)

Reglas comunes a todas `[OPINIÓN de diseño]`:
- Las señales se evalúan **al cierre de la vela** y se ejecutan en la apertura de la siguiente (o con orden límite post-only al precio de cierre ± 1 tick, cancelable tras 1 vela).
- Sizing por riesgo: `qty = (equity · risk_pct) / |entry − stop|`, con `risk_pct` del 0,25–0,5% por operación, un máximo de 3–5 posiciones de reversión simultáneas y una exposición bruta ≤ 1× equity en futuros (apalancamiento de margen ≤ 3x, en aislado).
- Kill-switch: si el DD de la familia de reversión supera el 8% en 30 días, se pausa la familia.
- Costes en el backtest: taker de 0,10% en spot o 0,05% en futuros por lado, + 0,03% de slippage por lado y + funding real en futuros.

### C1. Bollinger z-score fade con filtro de régimen de rango ("MR-Range")
- **Mercado:** spot (solo long) y futuros (long y short).
- **TF de señal:** 1h (alternativas: 15m y 4h). **TF de régimen:** 4h.
- **Filtro de régimen (todas las condiciones):** ADX(14) en 4h < 22; ER(20) en 1h < 0,30; |slope EMA200 en 4h| < 2% en 20 velas; BBW_pct(1h) entre 20 y 80 (ni compresión extrema, que precede a rupturas, ni expansión extrema).
- **Entrada long:** z(20) ≤ −2,0 **y** RSI(14) ≤ 30 **y** la vela de señal cierra por encima de su apertura o el siguiente cierre es > el cierre de la señal (confirmación de giro; parámetro `confirm` = on/off).
- **Entrada short (solo futuros):** el espejo de lo anterior (z ≥ +2,0, RSI ≥ 70). Además, funding ≥ 0 (no pagar funding por estar corto contra un mercado que ya está corto).
- **Salida:** cerrar cuando z cruce 0 (SMA20). Salida parcial opcional del 50% en z = −1.
- **Stop:** `entry − 2,0·ATR(14)` (long), o cierre con z ≤ −3,5, lo que ocurra primero.
- **Time stop:** 24 velas (1 día en 1h).
- **Invalidez de régimen:** si con la posición abierta ADX(4h) sube por encima de 30, se cierra en la siguiente vela.
- **Parámetros/rangos:** n ∈ {14, 20, 30}; k/z_in ∈ [1,8; 2,5]; z_stop ∈ [3,0; 4,0]; ADX_max ∈ [18; 25]; ER_max ∈ [0,25; 0,40]; ATR_mult_stop ∈ [1,5; 3,0]; time_stop ∈ [12; 48] velas.
- **Datos:** OHLCV de 1h y 4h; funding en futuros.
- **Régimen:** funciona en rango lateral con volatilidad media. Falla en tendencia sostenida (sobre todo en caídas con capitulación) y en rupturas tras compresión.
- **Evidencia:** débil en cripto (tesis LUT y Theseus, AEL 2023 sin verificar). La autocorrelación negativa en 1–4h (De Nicola) da una base mecánica. Es la versión corregida de la estrategia actual del bot.

### C2. RSI(2) de pullback a favor de la tendencia mayor ("MR-Pullback", estilo Connors)
- **Mercado:** spot (long). En futuros también short en tendencia bajista.
- **TF:** señal en 1h o 4h; tendencia en 1d (o 4h si la señal está en 1h).
- **Filtro:** long solo si C(1d) > SMA200(1d) **y** slope EMA50(1d) > 0. Short (futuros) solo si C(1d) < SMA200(1d) y slope < 0.
- **Entrada long:** RSI(2) ≤ 10 (estricto: ≤ 5) en el TF de señal **y** C > SMA200 del mismo TF ×0,97 (que no esté rompiendo la estructura).
- **Salida:** C > SMA(5) del TF de señal, o RSI(2) ≥ 70.
- **Stop:** `entry − 2,5·ATR(14)`. Time stop de 10 velas.
- **Sin promediar** (Connors sí escala en algunas variantes; aquí se prohíbe por el riesgo de cola en cripto `[OPINIÓN]`).
- **Parámetros/rangos:** RSI_len ∈ {2, 3}; umbral_in ∈ [3; 15]; exit_SMA ∈ {3, 5, 10}; ATR_mult ∈ [2; 3,5]; trend_SMA ∈ {100, 150, 200}.
- **Datos:** OHLCV de 1h, 4h y 1d.
- **Régimen:** funciona en tendencia alcista con correcciones cortas. Falla en los cambios de tendencia (el filtro SMA200 llega tarde) y en mercados bajistas, donde solo puede operar en corto en futuros.
- **Evidencia:** las reglas tienen evidencia en acciones (Connors). En el Nasdaq-100 2016–2026 rindió muy por debajo del B&H pero con menor DD. **No hay backtest publicado en cripto**: hipótesis por validar. Compatible con la evidencia de momentum diario en BTC (opera a favor de la tendencia).

### C3. Reversión tras shock de 1h ("MR-Shock / liquidation flush")
- **Mercado:** futuros USDT-M (long y short). En spot, solo long.
- **TF:** 1h (alternativas: 15m y 4h).
- **Entrada long:** `s_t ≤ −3,0` (retorno de 1h ≤ −3σ semanal) **y** la caída total de las últimas 3 velas es ≥ 2,5·ATR(14) **y** (solo futuros) la variación de OI en 1h ≤ −3% (desapalancamiento) **y** el funding actual ≤ +0,01% por 8h (sin euforia long residual). Se entra con límite en `C_t − 0,25·ATR` (válida 2 velas) o a mercado en la apertura siguiente (`exec_mode`).
- **Entrada short:** el espejo (`s_t ≥ +3,0`, OI cae ≥3%, que indica squeeze de cortos, y funding ≥ −0,01%).
- **Salida:** al recuperar el 50% del movimiento del shock (de `C_{t−3}` a `C_t`), o un time stop de 12 velas.
- **Stop:** `low del shock − 1,0·ATR(14)` (long).
- **Filtro adicional:** no operar si BTC hace un shock simultáneo ≤ −4σ en 1h y en ese momento se está evaluando una altcoin (riesgo sistémico). Opcionalmente, solo se opera BTC/ETH en ese caso.
- **Parámetros/rangos:** σ_thr ∈ [2,5; 4,0]; OI_drop ∈ [2%; 6%]; retrace_target ∈ [0,382; 0,618]; time_stop ∈ [6; 24].
- **Datos:** OHLCV de 1h, open interest histórico (5m/1h), funding.
- **Régimen:** funciona en sobrerreacciones aisladas por liquidaciones, en cualquier régimen. Falla en las cascadas en varias olas (el OI se reconstruye sin recuperar el precio) y ante noticias fundamentales (hacks, delistings, regulación).
- **Evidencia:** De Nicola ("los movimientos grandes revierten más" en 1–4h) es evidencia directa del núcleo de la regla. Los filtros de OI y funding son **anecdóticos** (Galaxy, Blockworks): hay que probarlos con y sin ellos.

### C4. Pairs cointegrados en perps USDT-M ("StatArb-Pairs")
- **Mercado:** solo futuros (necesita el corto). Market-neutral en dólares beta-ajustados.
- **TF:** 1h (Fil & Kristoufek: la frecuencia alta rinde más en bruto pero es más sensible a costes; 1h es el compromiso `[OPINIÓN]`). Alternativa: 15m.
- **Universo:** top 30–40 perps por volumen, idealmente agrupados por sector (L1, L2, DeFi, memes, exchange tokens) para reducir pares espurios.
- **Formación** (cada 7 días, ventana de 30 días = 720 velas de 1h):
  1. Correlación de log-retornos ≥ 0,7 como prefiltro.
  2. Test de Engle-Granger (ADF sobre el spread) con p < 0,05 en **ambas** direcciones, o Johansen con rango ≥ 1.
  3. Half-life entre 4 y 72 velas.
  4. Corrección por comparaciones múltiples: Benjamini-Hochberg sobre todos los pares probados (con 40 monedas hay 780 pares y unas 39 falsas cointegraciones esperables con p<0,05) `[OPINIÓN, imprescindible]`.
  5. Se quedan los K=5–10 pares con menor half-life y spread con mayor σ (más edge por operación).
- **Señal:** `z_S` con ventana w = clip(3·HL, 24, 720).
- **Entrada:** si z_S ≥ +2,0, short A y long B·β. Si z_S ≤ −2,0, al revés. Notional por pata: `N_A = N`, `N_B = β·N·(P_A/P_B)` expresado en USDT.
- **Salida:** |z_S| ≤ 0,25.
- **Stop:** |z_S| ≥ 3,5, o duración > 3·HL, o el par deja de ser cointegrado (p > 0,10 en el re-test diario de la ventana móvil). **Siempre con stop** (lección de Leung-Nguyen).
- **Costes:** se exige `2·σ_S·z_in ≥ 4×` el coste de ida y vuelta de las 2 patas. Se prefieren órdenes límite (maker de 0,02%). Se descuenta el diferencial de funding entre las patas.
- **Parámetros/rangos:** formación ∈ [14; 60] días; z_in ∈ [1,5; 2,5]; z_out ∈ [0; 0,5]; z_stop ∈ [3; 4]; HL ∈ [4; 72]h; p_max ∈ [0,01; 0,05]; K ∈ [3; 15].
- **Datos:** OHLCV de 1h de todos los perps, funding por símbolo, comisiones y tamaños mínimos (`exchangeInfo`: stepSize y minNotional).
- **Régimen:** funciona con dispersión normal entre monedas de un mismo sector. Falla ante rupturas idiosincráticas (listings, hacks, unlocks de tokens, delistings), por la ruptura de la cointegración (frecuente en cripto) y en los crashes de correlación 1.
- **Evidencia:** la más académica de la familia (Fil & Kristoufek con datos de Binance; Tadi & Kortchemski; Leung & Nguyen). **Pero** los resultados netos realistas van de ligeramente negativos a ≈+3%/mes, y la evidencia de 2026 (Pindza & Mba) es negativa tras costes. Riesgo de sesgo de publicación alto `[OPINIÓN]`.

### C5 (experimental, prioridad baja). Reversión transversal de corto plazo en una cesta de perps líquidos ("XS-Reversal")
- **Mercado:** futuros. Long-short neutral en dólares.
- **TF:** rebalanceo cada 4h (alternativas: 2h y 8h). Medida: retorno de las últimas 4h residualizado contra BTC (`r_i − β_i·r_BTC`, con β a 30 días).
- **Regla:** se ordenan las ~30 monedas más líquidas. Long las 3–5 con peor residual y short las 3–5 con mejor residual. Pesos iguales, ajustados por volatilidad inversa (σ a 7 días). Se mantiene una ventana y luego se rebalancea.
- **Stop:** por pata a 3·ATR(14) en 1h. Stop de cartera: −2% del equity por día.
- **Filtro de régimen:** solo si la dispersión transversal de retornos de 4h está por encima de su mediana de 30 días, y no hay un shock de BTC > 3σ.
- **Parámetros:** lookback ∈ {1h, 2h, 4h, 8h}; N por lado ∈ [3; 8]; holding ∈ [lookback; 2·lookback].
- **Datos:** OHLCV de 1h de la cesta, funding.
- **Régimen y evidencia:** Fischer-Krauss-Deinert (7,1 pb/día netos, horizonte de 120 min, 2018, muestra corta) apoya la previsibilidad transversal intradía. Pero a horizonte semanal la evidencia en monedas grandes es de **momentum** (Liu-Tsyvinski) y la reversión se concentra en las ilíquidas (Zaremba). **Riesgo alto de que no sobreviva a los costes con 0,05% taker.** Se incluye solo como experimento de investigación.

---

## 6. Selector de régimen propuesto (para elegir entre familias)
`[OPINIÓN de diseño]`, a validar en el backtest del harness:

| Estado (en el TF superior del activo) | Familia de reversión permitida |
|---|---|
| ADX < 20, ER < 0,3, Hurst-DFA < 0,5 | C1 (fade de rango) a tamaño completo; C4 activo |
| ADX > 25 y C > SMA200 (tendencia alcista) | Solo C2 long. C1 desactivado |
| ADX > 25 y C < SMA200 (tendencia bajista) | Solo C2 short (futuros). En spot, nada de reversión |
| Shock ≥ 3σ en 1h | C3 (con filtros OI/funding en futuros) |
| BBW_pct < 10 (compresión) | Ninguna reversión (pasar a la familia breakout/trend, informe 01) |

Validación mínima exigida a cada candidata `[OPINIÓN]`: walk-forward (entrenar 6 meses / probar 1 mes, desplazando), al menos 3 años de datos que incluyan 2022 (bajista), 2023 (rango) y 2024 (alcista), más de 200 operaciones fuera de muestra, costes completos y funding, un test de permutación o White's Reality Check / Deflated Sharpe para descontar el número de combinaciones probadas, y robustez de ±20% en cada parámetro.

---

## 7. Sesgos y debilidades de la evidencia
1. **Sesgo de publicación:** las tesis y los papers con resultados positivos dominan las búsquedas. Los resultados negativos (Pindza & Mba 2026, Resta 2020, Fil & Kristoufek en versión realista) son minoría pero más creíbles.
2. **Periodos cortos y antiguos:** Fischer et al. cubren 3 meses de 2018; la tesis de Erasmus, 16 semanas. Los regímenes de 2017–2018 (spreads amplios, menos HFT) ya no existen.
3. **Sharpe absurdos** (>20 en Tadi & Kortchemski, 100% de acierto en Dann & Kotsireas): indican capacidad nula, errores de ejecución simulada o sobreajuste.
4. **Barrido de parámetros dentro de la muestra** (Ni et al. 2023): resultados inflados.
5. **Comparaciones múltiples en pairs:** con N monedas hay N(N−1)/2 pares, y sin corrección aparecen cointegraciones espurias.
6. **No se pudieron leer los PDF completos** (limitación de red de este contenedor). Los umbrales exactos de z de los papers de pairs y las magnitudes de De Nicola siguen `[NO VERIFICADO]`.

---

## 8. Fuentes
- De Nicola (2021) Ledger: https://ledger.pitt.edu/ojs/ledger/article/view/213 ; https://epub.ub.uni-muenchen.de/97651/
- Fil & Kristoufek (2020) IEEE Access: https://ieeexplore.ieee.org/document/9200323 ; https://dspace.cuni.cz/handle/20.500.11956/109634
- Tadi & Kortchemski (2021): https://arxiv.org/abs/2109.10662v1 ; https://www.researchgate.net/publication/354776945_Evaluation_of_Dynamic_Cointegration-Based_Pairs_Trading_Strategy_in_the_Cryptocurrency_Market
- Tadi & Witzany (2025) Financial Innovation: https://link.springer.com/article/10.1186/s40854-024-00702-7 ; https://arxiv.org/pdf/2305.06961
- Pindza & Mba (2026) QFE: https://www.aimspress.com/article/doi/10.3934/QFE.2026016
- Leung & Nguyen (2019): https://ideas.repec.org/a/eme/sefpps/sef-08-2018-0264.html ; https://towardsdatascience.com/constructing-cointegrated-cryptocurrency-portfolios-d0a27922891e/
- Dann & Kotsireas (2024): https://econpapers.repec.org/bookchap/sprlnopch/978-3-031-68974-1_5f16.htm
- Palazzi (2025) JFM: https://ideas.repec.org/a/wly/jfutmk/v45y2025i11p1911-1933.html
- Tesis Turku: https://www.utupub.fi/handle/11111/24573
- Fischer, Krauss & Deinert (2019): https://ideas.repec.org/a/gam/jjrfmx/v12y2019i1p31-d205554.html
- Zaremba et al. (2021): https://www.sciencedirect.com/science/article/pii/S1057521921002349
- Liu, Tsyvinski & Wu (NBER): https://www.nber.org/system/files/working_papers/w25882/w25882.pdf
- Dobrynskaya: https://www.pm-research.com/content/iijaltinv/26/1/65
- Epstein et al. (2025): https://arxiv.org/html/2510.11616v1
- Bariviera (2017): https://arxiv.org/pdf/1709.08090 ; arXiv 1809.08403: https://arxiv.org/abs/1809.08403
- Harbourfront Quant (Hurst): https://harbourfrontquant.substack.com/p/detecting-trends-and-risks-in-crypto
- Quantpedia: https://quantpedia.com/trend-following-and-mean-reversion-in-bitcoin/
- Trend following en cripto: https://paperswithcode.com/paper/a-decade-of-evidence-of-trend-following
- Theseus: https://www.theseus.fi/handle/10024/902903 ; LUT: https://lutpub.lut.fi/handle/10024/168985
- AEL 2023: https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html ; Ni et al. 2023: https://doaj.org/article/117023aaddcf4d15a0da82358f10e0b6 ; Poznań: https://kie.ue.poznan.pl/en/?p=289
- Connors RSI(2): https://www.luxalgo.com/library/concept/rsi-2/ ; https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100 ; https://www.prorealcode.com/prorealtime-trading-strategies/rsi-2p-larry-connors/
- VWAP (sin evidencia): https://tr.tradingview.com/script/oSV81CXs-VWAP-SD2-Reversion-Long/ ; https://veksi.com/docs/strategies_popular_vwap_reversion.php
- Liquidaciones (anecdótico): https://www.galaxy.com/insights/perspectives/price-action-triggers-liquidation-cascade-slashing-funding-rates-and-wiping ; https://www.blockworks.com/news/crypto-sell-off-open-interest-funding ; https://bitsgap.com/blog/liquidation-cascades-explained ; https://www.luxalgo.com/library/concept/liquidation-clusters/
- Comisiones Binance: https://www.binance.com/es/support/articles/360033544231 ; https://cryptopotato.com/binance-fees/ ; https://support.binance.us/en/articles/9843536-binance-us-launches-trading-fee-discount-and-vip-program-with-bnb
