# 01 — Trend-following y momentum en cripto (spot y futuros USDT-M)

Fecha: 2026-10-15. Autor: subagente investigador cuantitativo (punto de vista: analítico/crítico).

> **Nota metodológica (importante).** Desde este contenedor WebFetch/curl **no pudo** abrir ninguna fuente (DNS/proxy bloqueado para SSRN, arXiv, concretumgroup, cxoadvisory, etc.). Todo lo citado proviene de **resúmenes de resultados de WebSearch** (abstracts, fichas RePEc/SSRN, resúmenes secundarios). Por tanto: las cifras se citan como "reportadas por la fuente X"; **no he verificado tablas completas**. Los parámetros marcados con [VERIFICAR-PDF] deben confirmarse leyendo el PDF original antes de tomarlos como exactos. Distingo:
> - **[EVIDENCIA]** = afirmación respaldada por una fuente citada.
> - **[OPINIÓN]** = juicio propio / inferencia de diseño.

---

## 1. Resumen ejecutivo

1. **[EVIDENCIA]** El trend-following / time-series momentum (TSMOM) en horizontes **diarios a semanales** es el patrón técnico con mejor respaldo en cripto. Han, Kang & Ryu concluyen que, con costes y fluctuaciones diarias realistas, la evidencia de **TSMOM es fuerte** y la de **momentum cross-sectional es débil** ([ACFR PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)).
2. **[EVIDENCIA]** El trabajo práctico más completo y reciente es Zarattini, Pagani & Barbon (2025), *Catching Crypto Trends* (SFI RP 25-80): ensemble de canales Donchian con varias ventanas + sizing por volatilidad objetivo; en cartera rotatoria del top-20 líquido reportan **Sharpe > 1.5 neto de comisiones** y alfa anual 10.8% vs BTC, con universo libre de sesgo de supervivencia ([SSRN 5209907](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907), [RePEc](https://ideas.repec.org/p/chf/rpseri/rp2580.html), [Concretum](https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/)).
3. **[EVIDENCIA]** Reglas de medias móviles simples (precio vs SMA, cruces) predicen retornos diarios de BTC dentro y fuera de muestra (Detzel et al., *Financial Management* 2021, [RePEc](https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html)). Rozario et al. (arXiv 2009.12155) hallan SMAs ~10 y ~40 días robustas con Sharpe 0.5–1.5 y **ausencia de estrategias de tendencia intradía rentables en BTCUSD spot** ([arXiv](https://arxiv.org/pdf/2009.12155)).
4. **[EVIDENCIA]** La evidencia **no es uniforme**: Li, Wang, Wang & Yang (2023) no encuentran reglas técnicas rentables en BTC/USDT y ETH/USDT 2022–2023 tras ajustar por data snooping ([articlegateway](https://articlegateway.com/index.php/JAF/article/view/6453)); Hudson & Urquhart (2019/2021) encuentran predictibilidad en ~15.000 reglas, pero **sin predictibilidad fuera de muestra para BTC** y con costes de break-even superiores a los típicos según el resumen ([Springer](https://link.springer.com/article/10.1007/s10479-019-03357-1)).
5. **[EVIDENCIA]** Para **Supertrend, ADX y MACD** no encontré **ningún estudio académico** sólido en cripto con costes; solo scripts de TradingView y un preprint (arXiv 2511.00665) que evalúa MACD+ADX **sin costes ni stops** y donde no supera al LSTM ni (tras fees) al buy&hold ([arXiv](https://arxiv.org/html/2511.00665v1)).
6. **[OPINIÓN, fundada en lo anterior]** El bot actual (mean reversion BB+RSI y cruces EMA en **velas de 1m**, long-only spot) está en la zona de **peor evidencia**: horizonte intradía muy corto, donde costes (0.1% spot taker por lado; 0.05% taker futuros, ver §6) se comen cualquier borde, y sin filtro de régimen. La recomendación es mover el núcleo de tendencia a **4h–1D**, con sizing por volatilidad, y usar timeframes cortos solo para ejecución.

---

## 2. Hallazgos con evidencia

### 2.1 Time-series momentum (TSMOM)
| Estudio | Qué encuentra | Calidad / sesgos |
|---|---|---|
| Han, Kang & Ryu, "TS and CS momentum in crypto under realistic assumptions" ([PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)) | Con costes y swings diarios, muchas carteras se liquidan; TSMOM robusto, CSMOM débil; el momentum se concentra en grandes ganadores y los perdedores rebotan (castigando cortos). | Working paper; precisamente diseñado para corregir sobreestimaciones previas → alta relevancia. |
| Borgards (2021), *NAJEF*, "Dynamic time series momentum of cryptocurrencies" ([EconPapers](https://econpapers.repec.org/RePEc:eee:ecofin:v:57:y:2021:i:c:s1062940821000590)) | 20 criptos: periodos de momentum largos y frecuentes. | Peer-reviewed; muestra pequeña de monedas. |
| Shen, Urquhart & Wang (2022), *Financial Review*, "Bitcoin intraday TSMOM" ([Birmingham](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/), [Reading PDF](https://reading-9.eprints-hosting.org/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf)) | El primer half-hour (definido por volumen) predice el último half-hour; más fuerte en sesiones de alto volumen/volatilidad y en caídas. | Peer-reviewed, pero efecto intradía pequeño; viabilidad neta de costes no confirmada en lo leído. |
| Wisselink (tesis EUR 2018) ([PDF](https://thesis.eur.nl/pub/44390/Wisselink-NJ-483391-BA-thesis.pdf)) | TSMOM/filtros: exceso de retorno significativo en la mayoría de carteras **long-only**, **ninguna** long-short. | Tesis de grado; muestra 2014–2018 alcista. Evidencia débil pero coherente con "cortos difíciles". |

### 2.2 Breakouts Donchian / Turtle
- **[EVIDENCIA]** Zarattini, Pagani & Barbon (2025). Según el resumen de CXO Advisory recogido en la búsqueda ([CXO](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/)) [VERIFICAR-PDF]:
  - Ventanas: máximos/mínimos de **cierres** de 5, 10, 20, 30, 60, 90, 150, 250, 360 días.
  - Entrada: cierre diario > máximo del canal de esa ventana.
  - Salida: trailing stop diario = max(stop de ayer, punto medio (max+min)/2 de esa ventana); salida si cierre < stop.
  - Sizing: cada posición se reescala a diario a **25% vol anualizada** objetivo, vol = desviación estándar de 90 días; apalancamiento máximo 200%; ensemble equiponderado rebalanceado diario.
  - Universo: monedas con ≥1 año listadas y volumen diario mediano ≥ 2 M USD (30d previos), top-20 más líquidas; principalmente **long-only**.
  - Resultado reportado: Sharpe > 1.5 neto, alfa 10.8%/año vs BTC ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907)).
- **[EVIDENCIA]** Mismo grupo (Concretum) sobre tendencia intradía en BTC: ensemble long-short de modelos de alta frecuencia 2018–2025, **Sharpe bruto ~1.6** vs ~0.8 de long-only con vol objetivo 20% ([Concretum](https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/)). **Bruto de comisiones**, hecho por la propia firma.
- **[EVIDENCIA, débil]** Gerritsen et al. (2020), según resumen de TradingView: reglas trading-range-breakout con Sharpe ~0.08 frente a buy&hold en BTC ([TradingView](https://my.tradingview.com/chart/BTCUSD/tK5t6vU6-The-profitability-of-TA-trading-rules-in-the-Bitcoin-market)). Fuente secundaria.
- **[OPINIÓN]** El valor de Donchian aparece en **ensembles multi-ventana + vol targeting**, no en un único "20/55 turtle" optimizado. Una sola ventana optimizada es la receta clásica de sobreajuste.

### 2.3 Medias móviles / cruces EMA
- **[EVIDENCIA]** Detzel, Liu, Strauss, Zhou & Zhu (2021) ([RePEc](https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html)): ratios precio/MA predicen retornos diarios de BTC in/out-of-sample; versión 2018 usaba SMA 5,10,20,50,100 días con regla "BTC si P>SMA, si no cash" ([CXO](https://www.cxoadvisory.com/currency-trading/timing-bitcoin-with-smas/)).
- **[EVIDENCIA]** Rozario et al. (arXiv 2009.12155, [ar5iv](https://ar5iv.labs.arxiv.org/html/2009.12155)): SMA ~10 y ~40 días consistentemente buenas con ligera caída reciente; Sharpe 0.5–1.5; EMA ~1.35 en el mejor caso; "ausencia notable de estrategias de tendencia intradía rentables" en BTCUSD spot. Ojo: el "255% anual walk-forward" depende de 2011–2019 (fase hiper-alcista); no extrapolable.
- **[EVIDENCIA]** Corbet, Eraslan, Lucey & Şensoy (2019), *FRL* ([RePEc](https://ideas.repec.org/a/eee/finlet/v31y2019icp32-37.html)): en datos de alta frecuencia de BTC, soporte significativo a MA; la variable-length MA es la mejor; las señales de compra rinden más que las de venta.
- **[EVIDENCIA]** Svogun & Bazán-Palomino (2022), *JIFMIM* 79 ([UP](https://faculty.up.edu.pe/es/publications/technical-analysis-in-cryptocurrency-markets-do-transaction-costs/)): 69 reglas MA/breakout en datos diarios y de 1 minuto, 2016–2021; resultados mixtos por moneda y régimen burbuja.
- **[EVIDENCIA]** Le & Ruthbah (2024): SMA 20/65/150/200 días en BTC, ETH e índice S&P Crypto LargeCap con fricciones 0.1–0.5% (método confirmado; resultados no verificados por mí) ([CXO](https://cxoadvisory.com/technical-trading/applying-simple-trend-following-rules-to-cryptocurrencies)).
- **[EVIDENCIA, contraria]** Li et al. 2023 ([articlegateway](https://articlegateway.com/index.php/JAF/article/view/6453)): sin reglas rentables en BTC/USDT, ETH/USDT 2022–2023 tras data snooping. Bakker (tesis 2017, 5m BTC): reglas significativas tras snooping y costes pero **inestables y decrecientes** ([PDF](https://thesis.eur.nl/pub/41546/Bakker.pdf)).

### 2.4 Supertrend, ADX, MACD
- **[EVIDENCIA de ausencia]** No hallé papers peer-reviewed que validen Supertrend en cripto con costes. Todo lo encontrado son scripts TradingView con claims no verificados (ej. [Supertrend+MACD](https://kr.tradingview.com/script/YZNZihaG-Supertrend-MACD-Crossover)).
- **[EVIDENCIA]** arXiv 2511.00665 (2025): MACD+ADX>25 con parámetros elegidos por grid search del máximo retorno histórico, **sin costes ni stops**; test 2024; el LSTM gana y con fee 0.1% "solo el LSTM supera buy&hold" ([arXiv](https://arxiv.org/html/2511.00665v1)). Evidencia **débil y sesgada** (selección por máximo retorno in-sample).
- **[OPINIÓN]** Supertrend ≈ trailing stop ATR; MACD ≈ diferencia de EMAs (es un cruce EMA suavizado); ADX ≈ filtro de fuerza de tendencia. Matemáticamente son variaciones de las mismas señales de tendencia. Se pueden usar como **componentes** (ATR trailing, filtro ADX) pero no hay justificación empírica para preferirlas sobre Donchian/SMA. ADX como filtro de régimen es razonable para **evitar operar tendencia en rango**, pero el umbral (20/25) es convención, no evidencia.

### 2.5 Momentum cross-sectional (rotación entre monedas)
- **[EVIDENCIA]** Liu, Tsyvinski & Wu (2022, *J. Finance*): mercado, tamaño y **momentum** son los 3 factores que explican la sección cruzada ([SSRN](https://papers.ssrn.com/abstract=3379131), [NBER](https://www.nber.org/papers/w25882.pdf)) — sorts semanales.
- **[EVIDENCIA]** Dobrynskaya: momentum a 1–2 semanas, reversión desde ~4–6 semanas; Fičura (2023): la reversión semanal es solo de monedas pequeñas/ilíquidas; las grandes muestran momentum semanal ([VSE](https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php), [HSE](https://finance.hse.ru/en/news/559533243.html)).
- **[EVIDENCIA]** Momentum cripto sufre **crashes severos**; la gestión por volatilidad los mitiga ("Cryptocurrency momentum has (not) its moments", [Springer](https://link.springer.com/article/10.1007/s11408-025-00474-9), [Vaasa](https://osuva.uwasa.fi/handle/10024/20018)).
- **[EVIDENCIA]** Han, Kang & Ryu: CSMOM débil tras costes; perdedores rebotan → los cortos del lado "loser" son peligrosos.

### 2.6 Futuros perpetuos: funding / carry como variable de contexto
- **[EVIDENCIA]** Schmeling, Schrimpf & Todorov, "Crypto Carry" (BIS WP 1087; *Management Science*): carry (futuro−spot) llega hasta 60% anual, media ~7–8%; lo impulsan inversores minoristas persiguiendo tendencia con apalancamiento; **carry alto predice crashes** ([BIS](https://www.bis.org/publ/work1087.htm), [VoxEU](https://cepr.org/voxeu/columns/crypto-carry-market-segmentation-and-price-distortions-digital-asset-markets)).
- **[EVIDENCIA]** Survey arXiv 2510.14435: carry (short perp + long spot) Sharpe 6.45 en 2020–2025 pero cae a 4.06 desde 2024 y **negativo en 2025** ([arXiv](https://arxiv.org/pdf/2510.14435)).
- **[OPINIÓN]** Implicación para tendencia en futuros: un long de tendencia paga funding cuando el mercado está "caliente"; funding extremo positivo = señal de riesgo de crash → reducir tamaño de longs. No encontré paper que combine explícitamente trend + filtro de funding; es una hipótesis a testear, no evidencia.

### 2.7 Long vs short
- **[EVIDENCIA]** Señales de compra > señales de venta (Corbet et al.); long-only significativo y long-short no (Wisselink); perdedores rebotan (Han et al.). Contra: Concretum intradía long-short Sharpe bruto 1.6 > long-only 0.8.
- **[OPINIÓN]** En futuros, el lado corto debe tener **exigencias mayores** (ventanas más largas, tamaño reducido, filtro de régimen bajista confirmado). En spot, la "pata corta" es simplemente ir a cash/USDT.

### 2.8 Otras nuevas fuentes (débiles)
- arXiv 2602.11708 (Bui & Nguyen, 2026, "AdaptiveTrend"): tendencia en 6h, trailing stop por vol intradía, selección por Sharpe rolling, 70/30 long/short; Sharpe 2.41, MDD −12.7% en 150+ pares 2022–2024 ([arXiv](https://arxiv.org/html/2602.11708v1)). **Preprint v1 de una firma pequeña, no revisado; cifras sospechosamente altas → tratar como hipótesis.**

---

## 3. Qué sirve y qué no (síntesis crítica)

| Sirve (evidencia moderada-fuerte) | No sirve / dudoso |
|---|---|
| TSMOM / tendencia en **1D** (y plausiblemente 4h–12h) | Tendencia en **1m–15m** con fees taker (evidencia: Rozario "sin intradía rentable"; Bakker inestable) |
| **Ensembles** multi-ventana (Donchian 5–360d, SMA 10–200d) | Una sola combinación optimizada (alto riesgo de data snooping; Li et al. 2023) |
| **Sizing por volatilidad objetivo** (reduce crashes) | Sizing fijo por % del capital sin ajuste por vol |
| Long > short; corto con más filtro | Shorts simétricos sobre "perdedores" (rebotes) |
| Universo de monedas líquidas (vol ≥ 2M USD/día) | Altcoins ilíquidas (reversión, spreads) |
| Funding/carry como **riesgo** (indicador de euforia) | Supertrend/MACD/ADX "porque sí": sin validación académica independiente |

**Sesgos a vigilar [OPINIÓN]:** (a) sesgo de publicación — los blogs/TradingView solo publican lo que funciona; (b) dependencia de muestra 2013–2021 hiper-alcista; (c) muchos resultados son brutos de costes o sin slippage; (d) autores con interés comercial (Concretum, Talyxion); (e) supervivencia: universos de "top coins actuales" inflan resultados (Zarattini sí lo corrige, según el abstract).

---

## 4. Variables cuantitativas exactas (definiciones para implementar)

Sea `C_t` cierre de la vela t, `H_t`, `L_t` máximo/mínimo, `r_t = ln(C_t/C_{t-1})`.

- **Donchian sobre cierres (Zarattini):** `UP_n(t) = max(C_{t-n..t-1})`, `DN_n(t) = min(C_{t-n..t-1})`, `MID_n(t) = (UP_n+DN_n)/2`. (Turtle clásico usa H/L en vez de C.)
- **TSMOM:** `sig_n(t) = sign( C_t / C_{t-n} - 1 )` (o `sign(sum r)` sobre n).
- **Ratio MA (Detzel):** `MAR_n(t) = C_t / SMA_n(t)`; long si `MAR_n > 1`.
- **EMA:** `EMA_t = α C_t + (1-α) EMA_{t-1}`, `α = 2/(n+1)`.
- **MACD:** `EMA_12 − EMA_26`, señal `EMA_9(MACD)`.
- **ATR (Wilder):** `TR_t = max(H−L, |H−C_{t-1}|, |L−C_{t-1}|)`, `ATR_n = RMA_n(TR)`.
- **Supertrend(n, m):** bandas `HL2 ± m·ATR_n` con lógica de arrastre (equivale a trailing ATR).
- **ADX(14)** de Wilder: `+DI, −DI` sobre `RMA_14`, `ADX = RMA_14(|+DI−−DI|/(+DI+−DI)·100)`.
- **Vol realizada anualizada:** `σ_t = std(r_{t-k..t}) · sqrt(P)`, con P = 365 (diario) o 365·6 (4h). Zarattini: k = 90 días.
- **Peso por vol objetivo:** `w_t = min( σ* / σ_t , Lmax )`, σ* = 25%/año (Zarattini), Lmax = 2.0 en futuros, 1.0 en spot.
- **Filtro de liquidez:** mediana de volumen en USDT de 30 días ≥ 2 M (Zarattini); [OPINIÓN] para Binance usar ≥ 10–20 M para evitar slippage con órdenes de mercado.
- **Funding:** `f_t` (tasa por intervalo, típicamente 8h; anualizada ≈ `f·3·365`). **Basis:** `(F−S)/S`.
- **Coste por round-trip [EVIDENCIA, fuentes secundarias]:** futuros USDT-M VIP0 ≈ 0.02% maker / 0.05% taker por lado ([Finder](https://www.finder.com/cryptocurrency/trading/binance-futures-fees), [Binance support](https://www.binance.com/es/support/articles/360033544231)); spot VIP0 habitual 0.1% por lado ([CryptoPotato](https://cryptopotato.com/binance-fees/)). Verificar en el endpoint de comisiones de la cuenta (no accesible desde aquí).

---

## 5. Estrategias candidatas (reglas sin ambigüedad)

Convenciones comunes: señales calculadas **al cierre de vela confirmada**; ejecución en la apertura de la siguiente vela (o limit en el mid con timeout → market). Coste modelado mínimo: 0.05%/lado futuros, 0.1%/lado spot + slippage 0.02–0.05%. Una posición por símbolo y por estrategia.

### C1. Ensemble Donchian multi-ventana con vol targeting (basada en Zarattini et al. 2025)
- **Mercado:** spot (long-only, w≤1) y futuros (long; corto opcional C1-S).
- **Timeframe:** 1D (principal). Variante 4h con ventanas ×6 (equivalentes en barras) — no validada académicamente.
- **Universo:** USDT pairs con ≥ 365 días de historia y mediana 30d de volumen ≥ 2 M USD (paper) / ≥ 10 M (recomendado); top-20 por volumen, re-seleccionado mensualmente.
- **Sub-modelos:** N = {5, 10, 20, 30, 60, 90, 150, 250, 360} días [VERIFICAR-PDF].
- **Entrada (sub-modelo n):** si plano y `C_t > UP_n(t)` → long. Stop inicial `S_n = MID_n(t)`.
- **Trailing:** cada día `S_n(t) = max(S_n(t-1), MID_n(t))`.
- **Salida:** `C_t < S_n(t)` → cerrar sub-posición n.
- **Señal agregada:** `E_t = (1/|N|) Σ_n pos_n` ∈ [0,1].
- **Sizing:** `w_t = E_t · min(σ*/σ_90(t), Lmax)`; σ* = 25% (rango 15–40%); Lmax 1.0 spot, 1.5–2.0 futuros (aislado). Rebalancear solo si |Δw| > 10–20% del objetivo (reduce costes; [OPINIÓN]).
- **Cartera:** equiponderar riesgo entre monedas activas; tope por moneda 20% del NAV; exposición bruta ≤ 2× en futuros.
- **Stop de emergencia (futuros) [OPINIÓN]:** stop-market en el exchange a `entry − 3·ATR_14(1D)` para evitar liquidación por gap; precio de liquidación debe estar al menos 2× más lejos que este stop.
- **Corto (C1-S, solo futuros, [OPINIÓN]):** espejo con `C_t < DN_n` y `S_n = MID_n` decreciente, solo ventanas ≥ 20d, peso 0.5× del long, y solo si BTC `C < SMA_200`.
- **Variables:** OHLCV 1D, volumen USDT, (futuros: mark price, funding).
- **Régimen:** funciona en tendencias persistentes (2017, 2020–21, 2023–24); falla en rangos laterales con falsas rupturas (2018 H2–2019, 2022 H2 lateral) y en reversiones en V; costes de rebalanceo diario si σ* bajo.

### C2. TSMOM / filtro de media (Detzel, Rozario) — núcleo simple y robusto
- **Mercado:** spot y futuros. **Timeframe:** 1D.
- **Señal:** ensemble de K reglas `s_k = 1{C_t > SMA_{n_k}(t)}`, n ∈ {10, 20, 40, 50, 100, 200} (rango probado en la literatura 5–200). `E_t = media(s_k)`.
- **Entrada/salida:** posición objetivo `w_t = E_t · min(σ*/σ_60, Lmax)`; se ajusta diariamente con banda de no-trade 15%.
- **Stop:** implícito (cuando E→0 la posición se cierra); stop de emergencia exchange `entry − 3·ATR_14`.
- **Variante cruce EMA:** long si `EMA_fast > EMA_slow` con pares (10,40), (20,100), (50,200); ensemble de los tres.
- **Corto (futuros, opcional):** `w_t = −0.5·(1−E_t)·…` solo si `E_t = 0` y `C < SMA_200` de BTC.
- **Variables:** OHLCV 1D.
- **Régimen:** igual que C1; más lenta en giros (SMA 200 entra tarde: [Motley Fool / reference](https://therighttrader.com/bitcoin-charts/golden-death-cross) señala que el cruce 50/200 llega tarde). Falla en mercados laterales con whipsaw alrededor de la SMA.

### C3. Breakout 4h con filtro de régimen diario y trailing ATR (táctica, futuros)
- **Estado de la evidencia:** **[OPINIÓN / hipótesis]**: combina piezas con evidencia (tendencia diaria como filtro, Donchian, ATR trailing, vol targeting) pero **no existe paper que valide esta combinación exacta en 4h**. AdaptiveTrend (6h) es indicio débil.
- **Mercado:** futuros USDT-M (long y short), spot solo long.
- **Filtro de régimen (1D):** long permitido si `C_1D > SMA_100_1D` y `ADX_14_1D ≥ 20`; short permitido si `C_1D < SMA_100_1D`, `ADX_14_1D ≥ 20` y BTC `C < SMA_200`.
- **Entrada (4h):** long si `C_4h > max(H_{t-20..t-1})` (Donchian 20 barras = 3.3 días); short simétrico con `min(L)`.
- **Stop inicial:** `entry − 2.5·ATR_14(4h)` (rango 2–3.5).
- **Trailing:** Chandelier `max(H desde entrada) − 3·ATR_14(4h)` (≈ Supertrend(14,3)); solo se mueve a favor.
- **Salida adicional:** cierre 4h por debajo de `MID` del Donchian 20, o el filtro diario se invierte.
- **Sizing:** riesgo fijo por trade `R = 0.5%` NAV → `qty = 0.005·NAV / (entry − stop)`; cap por vol: nocional ≤ `σ*/σ_4h_anual`·NAV; apalancamiento efectivo ≤ 3×.
- **Filtro funding [OPINIÓN, hipótesis basada en Schmeling et al.]:** no abrir long si funding anualizado > 50% (≈ 0.0457%/8h) o en el percentil > 95 de los últimos 90 días; no abrir short si funding < −30% anual.
- **Parámetros a barrer:** Donchian 10–55; ATR mult 2–4; filtro SMA 50–200; ADX 15–25.
- **Variables:** OHLCV 4h y 1D, funding rate histórico, mark price, open interest (opcional).
- **Régimen:** funciona en tendencias con volatilidad expandiéndose; falla en rangos (ADX bajo, mitigado por filtro) y en squeeze de liquidaciones con mechas que tocan stops.

### C4. Momentum cross-sectional semanal con vol targeting (rotación entre altcoins líquidas)
- **Evidencia:** LTW (2022) a favor; Han et al. dicen que tras costes es débil → **prioridad baja**, solo como capa de selección del universo para C1/C2.
- **Mercado:** spot long-only (top-k) o futuros market-neutral (no recomendado por rebote de perdedores).
- **Timeframe:** rebalanceo semanal (lunes 00:00 UTC) o cada 2 semanas (Dobrynskaya: máximo efecto a 2 semanas).
- **Regla:** universo top-30 por volumen 30d; ranking por retorno 14d (rango 7–28d) excluyendo el último día; comprar top-5 equiponderado por riesgo (`w_i ∝ 1/σ_i`); **solo si** BTC `C > SMA_50` (filtro de tendencia del mercado); si no, cash.
- **Stop:** por cartera, si drawdown semanal > 10% → cash hasta próximo rebalanceo.
- **Variables:** OHLCV 1D de todo el universo, volumen USD.
- **Régimen:** funciona en "altseasons" y tendencias amplias; falla en crashes de momentum (reversiones bruscas) y mercados liderados solo por BTC.

### C5 (descartada como núcleo). Tendencia en 1m–15m (EMA cross / Supertrend / MACD)
- **[EVIDENCIA]** Rozario et al.: no hay tendencia intradía rentable en BTCUSD spot; Bakker: inestable y decreciente; Shen et al.: efecto pequeño limitado a sesiones de alto volumen. **[OPINIÓN]** Con 0.1% spot por lado, un cruce de EMAs en 1m necesita >0.2% de movimiento medio favorable por trade solo para empatar. Se recomienda usar timeframes cortos solo para **timing de ejecución** de señales 4h/1D, no para generar señales.

---

## 6. Datos requeridos (resumen)
- OHLCV 1D y 4h (velas cerradas) de todos los símbolos USDT spot y perps; historia ≥ 400 días para la ventana de 360d.
- Volumen en USDT (quote volume) para filtros de liquidez.
- Futuros: funding rate histórico (8h), mark price, open interest (opcional), exchangeInfo (tick/step/minNotional), brackets de apalancamiento y comisiones reales de la cuenta.
- Lista de deslistados (para backtest sin sesgo de supervivencia). **Nota:** este contenedor no accede a Binance; los datos deben descargarse en la máquina del usuario o desde un mirror (p. ej. data.binance.vision) cuando haya acceso.

## 7. Plan de validación sugerido (para el harness) [OPINIÓN]
1. Walk-forward anclado (entrenar ≤ año N, probar año N+1), 2019–2026.
2. Costes conservadores (taker siempre) + slippage; funding aplicado en futuros.
3. Deflated Sharpe / White Reality Check o SPA para corregir por número de variantes probadas (lección de Li et al. 2023 y Hudson & Urquhart).
4. Reportar por régimen: tendencia alcista, bajista, lateral (clasificado ex-ante por SMA200 y ADX) y por grupo de monedas (BTC/ETH vs top-20 vs resto).
5. Comparar contra benchmarks: buy&hold BTC, buy&hold vol-targeted, y la estrategia actual del bot.

## 8. Fuentes (todas leídas solo vía resúmenes de búsqueda)
- Zarattini, Pagani, Barbon (2025) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 ; https://ideas.repec.org/p/chf/rpseri/rp2580.html ; https://concretumgroup.substack.com/p/catching-crypto-trends ; https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/
- Concretum, intradía BTC — https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/
- Han, Kang, Ryu — https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
- Borgards (2021) — https://econpapers.repec.org/RePEc:eee:ecofin:v:57:y:2021:i:c:s1062940821000590
- Shen, Urquhart, Wang (2022) — https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/
- Rozario et al. — https://arxiv.org/pdf/2009.12155
- Detzel et al. (2021) — https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html ; https://www.cxoadvisory.com/currency-trading/timing-bitcoin-with-smas/
- Hudson & Urquhart — https://link.springer.com/article/10.1007/s10479-019-03357-1
- Corbet et al. (2019) — https://ideas.repec.org/a/eee/finlet/v31y2019icp32-37.html
- Li, Wang, Wang, Yang (2023) — https://articlegateway.com/index.php/JAF/article/view/6453
- Bakker (2017) — https://thesis.eur.nl/pub/41546/Bakker.pdf ; Wisselink (2018) — https://thesis.eur.nl/pub/44390/Wisselink-NJ-483391-BA-thesis.pdf
- Svogun & Bazán-Palomino (2022) — https://faculty.up.edu.pe/es/publications/technical-analysis-in-cryptocurrency-markets-do-transaction-costs/
- Le & Ruthbah (2024) — https://cxoadvisory.com/technical-trading/applying-simple-trend-following-rules-to-cryptocurrencies
- Liu, Tsyvinski, Wu — https://papers.ssrn.com/abstract=3379131
- Fičura (2023) — https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php ; Dobrynskaya — https://finance.hse.ru/en/news/559533243.html
- Momentum crashes cripto — https://link.springer.com/article/10.1007/s11408-025-00474-9
- Schmeling, Schrimpf, Todorov — https://www.bis.org/publ/work1087.htm ; https://cepr.org/voxeu/columns/crypto-carry-market-segmentation-and-price-distortions-digital-asset-markets
- Survey cripto (carry) — https://arxiv.org/pdf/2510.14435
- AdaptiveTrend — https://arxiv.org/html/2602.11708v1
- MACD+ADX vs ML — https://arxiv.org/html/2511.00665v1
- Comisiones Binance — https://www.binance.com/es/support/articles/360033544231 ; https://www.finder.com/cryptocurrency/trading/binance-futures-fees ; https://cryptopotato.com/binance-fees/
