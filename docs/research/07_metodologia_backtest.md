# 07 — Metodología de backtesting robusta para el bot (spot + futuros USDT-M de Binance)

Fecha: 2026-10-15. Autor: subagente investigador cuantitativo (punto de vista: analítico/matemático, escéptico).

> **Nota metodológica (importante).** Desde este contenedor **WebFetch no pudo abrir ninguna fuente** (DNS: arxiv.org, ssrn, binance.com, wikipedia, carmamaths.org → `ENOTFOUND`). Las fuentes académicas se conocen por **resúmenes de WebSearch** (abstracts y fragmentos). Sí pude leer por `raw.githubusercontent.com` la **documentación oficial de la API spot de Binance** (`binance/binance-spot-api-docs`: `web-socket-streams.md`, `rest-api.md`), la licencia de `vectorbt` y `backtesting.py`, y consultar versiones en PyPI (`pip index versions`).
> - **[EVIDENCIA]** = respaldada por una fuente citada (aunque sea vía resumen).
> - **[DOC-BINANCE]** = leído directamente del repo oficial de docs de Binance en GitHub.
> - **[CÓDIGO]** = verificado leyendo el código del repo `/home/user/trading-bot`.
> - **[FÓRMULA – CONOCIMIENTO PREVIO, VERIFICAR]** = fórmula estándar de la literatura que reproduzco de memoria; no la pude cotejar con el PDF en esta sesión. Debe contrastarse con el paper o con una implementación de referencia antes de usarla para aceptar/rechazar.
> - **[OPINIÓN]** = juicio propio / decisión de diseño (incluidos todos los umbrales numéricos de aceptación).

---

## 1. Resumen ejecutivo

1. **[EVIDENCIA]** El sobreajuste de backtests es el riesgo nº1 en cualquier búsqueda de estrategias. Bailey, Borwein, López de Prado y Zhu muestran que tras probar solo **7 configuraciones** es esperable encontrar un backtest de 2 años con Sharpe anual > 1 aunque el Sharpe real fuera de muestra sea 0 ([Pseudo-Mathematics and Financial Charlatanism, Notices AMS 61(5) 2014](https://scholarworks.wmich.edu/math_pubs/40/), [charla IAQF](https://iaqf.org/event-813217), [Advisor Perspectives](https://www.advisorperspectives.com/articles/2013/10/22/how-many-monkeys-does-it-take-to-find-a-successful-strategy)). El rediseño que pide el usuario ("elegir la estrategia más adaptable entre muchas, sobre muchas monedas") es exactamente el escenario de **pruebas múltiples** donde esto explota.
2. **[EVIDENCIA]** Herramientas de corrección con respaldo académico:
   - **Deflated Sharpe Ratio (DSR)**: corrige por sesgo de selección (nº de pruebas) y no-normalidad ([Bailey & López de Prado, JPM 40(5) 2014, SSRN 2460551](https://papers.ssrn.com/abstract=2460551)).
   - **PBO vía CSCV** (Combinatorially Symmetric Cross-Validation): probabilidad de que la configuración elegida in-sample quede **por debajo de la mediana** fuera de muestra ([Bailey et al., J. Computational Finance 20(4), SSRN 2326253](https://papers.ssrn.com/abstract=2326253), [paquete R pbo](https://github.com/mrbcuda/pbo)).
   - **Umbral t > 3.0** para nuevos "factores" por pruebas múltiples ([Harvey, Liu & Zhu, RFS 29(1) 2016, NBER w20592](https://nber.org/papers/w20592)).
3. **[EVIDENCIA]** En cripto, los costos cambian el signo de muchos resultados: Han, Kang & Ryu reportan que, con costos y fluctuaciones diarias, muchas carteras de momentum con retornos "significativos" pasan a **insignificantes**; el momentum de serie temporal sobrevive mejor que el cross-sectional (resumen vía [AUT/ACFR PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)). AutoQuant (arXiv 2512.22476) en perps BTC/ETH/SOL/AVAX encuentra que backtests sin costos o solo con comisiones **sobrestiman** el retorno anual frente al escenario con funding+slippage, y su PBO indica **sobreajuste residual sustancial** ([arXiv 2512.22476](https://arxiv.org/abs/2512.22476v1)). Un estudio walk-forward de BTC usa 0.1% por transacción y reporta un **costo de break-even ≈0.4%** ([arXiv 2602.10785](https://arxiv.org/html/2602.10785v1)).
4. **[EVIDENCIA, ausencia]** No encontré **ningún estudio académico** que modele el slippage de altcoins en Binance a partir del libro de órdenes; solo material de proveedores ([Elliptic](https://www.elliptic.co/corpus/gen-3840/market-liquidity/order-book-depth-slippage-and-wash-trading-signals-in-crypto-markets.html), [Amberdata](https://amberdata.io/order-book)). → El modelo de slippage debe ser **conservador y por bucket de liquidez**, y calibrarse luego con fills reales del testnet/producción.
5. **[CÓDIGO]** El backtester actual (`apps/analytics/backtester.py`) **no es apto** para tomar decisiones: (a) **no descuenta comisiones, slippage ni funding**; (b) anualiza el Sharpe siempre con `sqrt(365*24)` aunque el timeframe no sea 1h; (c) "anualiza" el retorno como `total_return * (8760/limit)` (lineal, sin compounding, y asume barras de 1h); (d) `trades` cuenta barras con señal, no operaciones; (e) si falla la descarga **cae silenciosamente a datos simulados** (`_generate_mock_data`, random walk con seed 42) y devuelve métricas como si fueran reales. Además las estrategias en vivo leen `df['close'].iloc[-1]`, que puede ser la **vela no cerrada** (ver §2.3).
6. **[OPINIÓN]** Propuesta: un único motor de backtest **event-driven a nivel de barra cerrada**, con costos explícitos (comisión + slippage por bucket + funding real por símbolo/intervalo), **walk-forward anclado + holdout final intocable**, y un **gate de aceptación** que combine DSR, PBO, nº de trades, estabilidad entre monedas y estrés de costos ×2. Ninguna estrategia pasa a dinero real sin pasar el gate y 4+ semanas de paper/testnet con desvío de slippage medido.

---

## 2. Hallazgos con evidencia

### 2.1 Costos: comisiones [EVIDENCIA, verificar en vivo]

| Mercado | Maker | Taker | Fuente | Estado |
|---|---|---|---|---|
| Spot, usuario regular (VIP0) | 0.100% | 0.100% | [Binance.US anuncio](https://support.binance.us/en/articles/9843536-binance-us-launches-trading-fee-discount-and-vip-program-with-bnb); secundario para Binance global: [CryptoPotato](https://cryptopotato.com/binance-fees/) | La fuente oficial encontrada es **Binance.US**, no Binance global → verificar con `GET /api/v3/account/commission` |
| Spot pagando con BNB | 0.075% | 0.075% | idem (25% descuento) | idem |
| Futuros USDT-M VIP0 | 0.020% | 0.050% | [Finder](https://www.finder.com/cryptocurrency/trading/binance-futures-fees), [Bitsgap](https://bitsgap.com/blog/binance-trading-fees-explained-what-it-costs), ejemplo de Binance FAQ 360033544231 ([es](https://www.binance.com/es/support/articles/360033544231)) | verificar con `GET /fapi/v1/commissionRate` por símbolo |
| Futuros USDT-M con BNB | ≈0.018% | ≈0.045% | secundario (~10% descuento) | verificar |

**[OPINIÓN] Regla de implementación:** el backtest debe leer la comisión de un archivo de configuración que se rellena desde los endpoints de comisión de la cuenta real; por defecto usar **taker** en ambas patas (el bot actual usa órdenes de mercado). Costo de ida y vuelta mínimo: spot **0.20%**, futuros **0.10%** sin slippage.

### 2.2 Costos: funding y slippage

**Funding [EVIDENCIA]:** `F = P̄ + clamp(I − P̄, −0.05%, +0.05%)`, con `I = 0.01%` por intervalo de 8h por defecto; `P̄` = media ponderada temporalmente del premium index (muestreado cada 5 s); el pago = valor nocional de la posición × F, los largos pagan si F > 0 ([Binance FAQ](https://www.binance.com/en/support/faq/introduction-to-binance-futures-funding-rates-360033525031), vía resúmenes; [QuantJourney](https://quantjourney.substack.com/p/funding-rates-in-crypto-the-hidden), [Coinvado 2026](https://coinvado.com/en/posts/binance-futures-funding-rate-guide-2026/)). Los intervalos **no son siempre 8h**: desde 2025 hay cambios dinámicos a 4h/1h por símbolo ([Amberdata docs](https://docs.amberdata.io/docs/funding-rates-1), [Coincub](https://coincub.com/?p=14476)); ver también informe 04.

**[OPINIÓN] Regla de implementación (sin ambigüedad):**
- Cargar el histórico real de funding por símbolo (`GET /fapi/v1/fundingRate`, o ficheros mensuales `fundingRate` de [data.binance.vision / binance-public-data](https://github.com/binance/binance-public-data/)) con su `fundingTime` real.
- En cada `fundingTime` en que la posición esté abierta: `pnl -= signo_posicion × nocional_en_markPrice × fundingRate` (largo: signo = +1, corto: −1).
- Si no hay dato de funding para un símbolo/periodo, **el backtest falla** (no imputar 0).
- Spot: funding = 0.

**Slippage [EVIDENCIA débil → modelo OPINIÓN]:** la literatura disponible solo dice cualitativamente que el impacto crece en altcoins con libros finos y que los spreads se ensanchan con la volatilidad ([Elliptic](https://www.elliptic.co/corpus/gen-3795/intermarket-sweep-order/market-impact-and-slippage.html), [BIT Knowledge Hub](https://www.bit.com/knowledge-hub/slippage)). No hay una cifra académica para Binance. Modelo conservador propuesto:

```
slip_bps(símbolo, barra) = base_bps[bucket] * max(1, ATR%_actual / ATR%_mediana_90d)
bucket por volumen medio 30d en USDT (quote volume):
  A: > 500M/día   -> base 2 bps   (BTC, ETH)
  B: 50M–500M     -> base 5 bps
  C: 5M–50M       -> base 15 bps
  D: < 5M         -> excluir del universo
precio_fill_compra = open_siguiente * (1 + slip_bps/1e4); venta: (1 - slip_bps/1e4)
stops: fill = min(nivel_stop, open) en gap para largos (max para cortos) y luego slippage ×2
```
Los valores de `base_bps` son **[OPINIÓN]**: deben recalibrarse con fills reales (registrar `precio_señal` vs `avgPrice` de cada orden del testnet/producción). Adicionalmente: tamaño de orden ≤ 1% del volumen de la barra de ejecución, si no, reducir tamaño.

### 2.3 Look-ahead y vela no cerrada [DOC-BINANCE + CÓDIGO]

- **[DOC-BINANCE]** El stream WebSocket `<symbol>@kline_<interval>` envía actualizaciones cada **2000 ms** (1000 ms para `1s`) de la vela **en curso**, con el campo `"x": false` mientras no está cerrada ("Is this kline closed?") ([web-socket-streams.md](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)).
- **[DOC-BINANCE]** `GET /api/v3/klines`: "If startTime and endTime are not sent, the most recent klines are returned", máximo 1000 por llamada, intervalos en UTC salvo `timeZone` ([rest-api.md](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)). La doc **no dice explícitamente** que la última fila es la vela abierta, pero se deduce cuando su `closeTime` > hora del servidor → **[OPINIÓN] regla: descartar toda fila con `closeTime >= serverTime`.**
- **[CÓDIGO]** Las estrategias actuales (`mean_reversion_strategy.py:90-94`, `momentum_strategy.py:115-117`, `risk_manager.py:190-192, 254, 434`) usan `iloc[-1]`. Si el DataFrame incluye la vela abierta, las señales y el ATR "parpadean" dentro de la barra y **no son reproducibles en backtest** (el backtest solo ve la vela cerrada). Corrección: en vivo, solo procesar mensajes con `k.x == true`; en REST, eliminar la última fila si no está cerrada.
- Otras fuentes de look-ahead a prohibir **[OPINIÓN, práctica estándar]**:
  1. Ejecutar al `close` de la barra que generó la señal (el backtester actual hace `pct_change().shift(-1)` = entrar al close de la señal; aceptable solo si se añade slippage; preferible entrar al **open de la barra siguiente**).
  2. Indicadores con normalización sobre toda la muestra (z-score global, min-max global) → usar solo ventanas rodantes.
  3. Usar `high/low` de la barra para fijar un stop y también para salir en la misma barra sin regla de prioridad. Regla: si en una barra se tocan stop y TP, **asumir que se tocó el stop primero** (pesimista).
  4. **Sesgo de supervivencia**: el universo de monedas debe fijarse con lo que existía y era líquido **en cada fecha** (incluir pares deslistados de data.binance.vision); no usar "top 20 de hoy" para 2021.
  5. Datos de sentimiento (Fear & Greed, funding, OI) alineados por su **timestamp de publicación**, no por el día al que se refieren.
  6. Timeframes superiores: una vela de 4h solo existe tras su cierre; al combinar 1h con 4h usar `resample(...).last().shift(1)` o equivalente.

### 2.4 Validación: walk-forward, out-of-sample, CPCV

- **[EVIDENCIA]** Bailey et al. sostienen que los hold-out estándar son **poco fiables** en backtests de inversión porque el investigador reutiliza el OOS; proponen CSCV/PBO ([SSRN 2326253](https://papers.ssrn.com/abstract=2326253)). El estudio walk-forward de BTC (arXiv 2602.10785) señala que **reoptimizar repetidamente sobre el OOS** es un problema común y no reportado, y recomienda **un único test OOS final** ([arXiv 2602.10785](https://arxiv.org/html/2602.10785v1)).
- **[EVIDENCIA]** Purged/Combinatorial Purged CV (López de Prado, 2017/2018): purga observaciones cuyas etiquetas se solapan con el test y aplica un *embargo*; CPCV genera C(N,k) caminos de backtest (p. ej. N=6, k=2 → 15) frente al único camino del walk-forward ([Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation), [fynance docs](https://fynance.readthedocs.io/en/latest/generated/fynance.data.combinatorial_purged_cv.html)). No encontré un estudio independiente que compare CPCV vs walk-forward en cripto → **[EVIDENCIA débil]** sobre cuál es mejor en este dominio.
- **[EVIDENCIA]** Gort et al. (arXiv 2209.05559) aplican la estimación de probabilidad de sobreajuste a agentes de DRL en 10 criptos (mayo–junio 2022, con dos crashes): los agentes menos sobreajustados superan a los más sobreajustados, a equal-weight y al benchmark ([arXiv 2209.05559](https://arxiv.org/pdf/2209.05559)). Ventana de test **muy corta** (2 meses) → evidencia débil de generalidad, pero útil como ejemplo de uso de PBO como filtro.

**[OPINIÓN] Protocolo exacto propuesto para el harness:**
1. Datos: desde 2020-01-01 (o listado del par) hasta hoy, barras cerradas de 1h y 4h y 1d; funding real.
2. **Holdout final intocable**: los últimos **6 meses**. Solo se evalúa **una vez**, al final, con la configuración congelada. Se registra en un log de "intentos"; si se mira más de una vez, el holdout queda quemado y se documenta.
3. Sobre el resto: **walk-forward anclado** con ventana de entrenamiento mínima 12 meses, test de 3 meses, paso 3 meses (≈ 8–14 folds según el par). Optimización solo dentro del train; el test concatenado forma la curva OOS.
4. En paralelo, sobre la matriz de retornos de **todas** las configuraciones probadas (T × N), calcular **PBO con CSCV** (S = 16 bloques).
5. Calcular **DSR** de la configuración elegida con N = nº total de configuraciones probadas (contando todas las familias, no solo las de la familia ganadora).
6. Estrés de costos: repetir OOS con comisión y slippage **×2**; y con ejecución retrasada **1 barra**.
7. Robustez de parámetros: la métrica OOS en una vecindad ±20% de cada parámetro no debe caer más del 50% (meseta, no pico).

### 2.5 Fórmulas exactas

**Sharpe por barra y anualización** [FÓRMULA – estándar]:
`SR_barra = mean(r) / std(r, ddof=1)`, `SR_anual = SR_barra * sqrt(K)`, donde **K = barras por año en cripto 24/7**: 1m → 525 600; 5m → 105 120; 15m → 35 040; 1h → 8 760; 4h → 2 190; 1d → 365. Usar retornos **de la cartera por barra (incluyendo barras flat = 0)**, no por trade. **[EVIDENCIA]** Lo (2002) muestra que escalar por √K solo es válido sin autocorrelación; con autocorrelación positiva el Sharpe anualizado se sobrestima (hasta 65% en su ejemplo de hedge funds) ([CFA Institute FAJ 2002](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios), [MIT](https://alo.mit.edu/publications/page/18/)). → **[OPINIÓN]** calcular el Sharpe principal sobre **retornos diarios** (agregados desde las barras) y anualizar con √365; reportar el intradía solo como diagnóstico.

**Probabilistic Sharpe Ratio (PSR)** [FÓRMULA – CONOCIMIENTO PREVIO, VERIFICAR contra SSRN 2460551]:
```
PSR(SR*) = Φ( (SR_hat − SR*) * sqrt(T − 1) / sqrt(1 − γ3*SR_hat + ((γ4 − 1)/4)*SR_hat²) )
```
con `SR_hat` **no anualizado** (misma frecuencia que T), T = nº de observaciones, γ3 = asimetría, γ4 = curtosis (no exceso; normal = 3).

**Deflated Sharpe Ratio (DSR)** [FÓRMULA – CONOCIMIENTO PREVIO, VERIFICAR]:
```
SR0 = sqrt(Var[{SR_n}]) * ( (1 − γ) * Φ⁻¹(1 − 1/N) + γ * Φ⁻¹(1 − 1/(N·e)) )
DSR = PSR(SR0)
```
γ ≈ 0.5772 (Euler-Mascheroni), N = nº de pruebas independientes (si están correlacionadas, estimar N efectivo, p. ej. por clustering de las series de retornos), Var[{SR_n}] = varianza de los Sharpe (no anualizados) de todas las pruebas. Interpretación: probabilidad de que el Sharpe verdadero sea > 0 tras corregir por selección.

**Minimum Backtest Length** [FÓRMULA – CONOCIMIENTO PREVIO, VERIFICAR contra [backtest.pdf](https://carmamaths.org/jon/backtest.pdf)]: `MinBTL ≈ 2·ln(N) / E[max_N]²` (años), siendo E[max_N] el Sharpe anual máximo que se quiere "creer". Equivalente aproximado: con y años de datos y N intentos de Sharpe real 0, el máximo esperado es ≈ sqrt(2·ln N / y). Consistente con el ejemplo de los 7 intentos: con y = 2, sqrt(2·ln 7 / 2) ≈ 1.39 > 1; para no "creer" un SR = 1 espurio con N = 7 harían falta ≈ 2·ln 7 ≈ 3.9 años (aproximación asintótica; el paper da la versión exacta). **Uso práctico [OPINIÓN]:** si se prueban N = 200 configuraciones, para creer un Sharpe anual de 1 se necesitan ~2·ln(200) ≈ 10.6 años de datos → **imposible en cripto con datos de calidad** → hay que **reducir N** (pocas familias, pocos parámetros, rejillas gruesas) en lugar de buscar más.

**PBO por CSCV** [EVIDENCIA para la definición; algoritmo de memoria, VERIFICAR con [pbo R](https://github.com/mrbcuda/pbo) o `pypbo`]:
1. Matriz M (T × N) de retornos por barra/día de N configuraciones.
2. Partir las filas en S bloques contiguos de igual tamaño (S par, típico 16).
3. Para cada combinación C de S/2 bloques (C(16,8) = 12 870): IS = bloques en C, OOS = el resto.
4. n* = argmax de Sharpe en IS; ω = rango relativo de n* en OOS ∈ (0,1) (rango/(N+1)); λ = ln(ω/(1−ω)).
5. **PBO = fracción de combinaciones con λ ≤ 0** (n* por debajo de la mediana OOS).
6. Diagnósticos extra del paper: degradación (regresión SR_OOS vs SR_IS) y probabilidad de pérdida OOS ([resumen ResearchGate](https://www.researchgate.net/publication/318600389_The_probability_of_backtest_overfitting)).

**Métricas de trading** [FÓRMULA – estándar]:
- Sortino = mean(r) / sqrt(mean(min(r,0)²)) × √K (downside deviation sobre target 0, dividiendo por **todas** las observaciones).
- MaxDD = min_t (E_t / max_{s≤t} E_s − 1) sobre la curva de equity **marcada a mercado por barra** (no solo al cierre de trades).
- CAGR = (E_final/E_inicial)^(365/días) − 1 (compuesto; no el lineal del backtester actual).
- Calmar = CAGR / |MaxDD|.
- Profit factor = Σ ganancias netas / |Σ pérdidas netas| (por trade, **neto de costos**).
- Expectancy (en R) = mean(PnL_neto_trade / riesgo_inicial_trade); en %: win_rate × avg_win − (1 − win_rate) × avg_loss.
- nº trades = nº de **ciclos entrada-salida** (no barras con señal).
- Exposición = fracción de barras con posición abierta; turnover anual = Σ|Δposición nocional| / equity media.
- Costos totales / PnL bruto (si > 50%, la estrategia es frágil).

### 2.6 Librerías Python (pip) [verificado en PyPI 2026-10-15]

| Librería | Versión PyPI | Pros | Contras | Uso recomendado [OPINIÓN] |
|---|---|---|---|---|
| `vectorbt` | 1.1.2 | Vectorizado, muy rápido para barridos de parámetros, soporta fees/slippage, multi-activo | Licencia **Apache 2.0 + Commons Clause** (no se puede "vender" el software) [verificado en LICENSE.md](https://github.com/polakowo/vectorbt); funding y stops intrabar requieren trabajo manual | Barrido rápido de la rejilla para la matriz T×N de CSCV |
| `backtesting.py` (`backtesting`) | 0.6.6 | API simple, event-driven, comisiones, SL/TP | Licencia **AGPL-3.0** [verificado](https://github.com/kernc/backtesting.py); un activo por run; sin funding | Prototipos de una sola moneda / verificación cruzada |
| `quantstats` | 0.0.86 | Informes de métricas (Sharpe, Sortino, Calmar, DD) | Asume por defecto 252 días/año → **pasar `periods=365`** | Reportes |
| `empyrical-reloaded` | 0.5.12 | Métricas estándar | idem: fijar `annualization=365` | Métricas |
| `skfolio` | 1.8.6 | Incluye CombinatorialPurgedCV | orientado a carteras | CPCV si se usa |
| `freqtrade` | 2026.9 | Bot completo con backtesting, soporte futuros Binance, funding, `lookahead-analysis` | Framework grande, impone su arquitectura | Referencia / validación cruzada de resultados |
| `nautilus_trader` | 1.231.0 | Event-driven de alto realismo, Binance spot+futuros | Curva de aprendizaje alta | Si se necesita simulación tick/L2 |
| PBO | — | `pypbo` (GitHub [esvhd/pypbo](https://github.com/esvhd/pypbo), código accesible) o implementación propia (~60 líneas) | `pypbo` no está en PyPI (no lo encontré con `pip index`) | Implementar propio + test contra el ejemplo del paquete R |

**[OPINIÓN]** Recomendación: **motor propio mínimo y auditado** (event-driven por barra cerrada, ~300 líneas) para que costos/funding/stops sean exactamente los del bot en vivo (misma función de señales), + `vectorbt` solo para generar la matriz de configuraciones, + PBO/DSR propios con tests unitarios. Validación cruzada de 1–2 estrategias contra `freqtrade` para detectar errores del motor.

### 2.7 Qué sirve y qué no en cripto

**Sirve [EVIDENCIA/OPINIÓN]:**
- Estrategias de **trend/momentum de serie temporal** en marcos diarios/4h, que sobreviven mejor a costos que el cross-sectional (Han, Kang & Ryu, vía [ACFR](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf); [arXiv 2602.11708](https://arxiv.org/pdf/2602.11708) reporta TSMOM 1 mes Sharpe 0.65 y 3 meses 0.54 OOS 2022–2024 con 4 bps + slippage + funding — **columnas posiblemente desalineadas en el resumen, verificar**).
- Validación con DSR/PBO y holdout único.
- Datos oficiales y gratuitos de [data.binance.vision](https://github.com/binance/binance-public-data/) (klines spot/futuros, fundingRate, con `.CHECKSUM`).

**No sirve / sospechoso:**
- Backtests en **1m** con señales de indicadores clásicos y órdenes de mercado: con 0.2% de costo spot por ida y vuelta, el movimiento esperado por trade debe superar con holgura ese umbral; en 1m rara vez ocurre. **[OPINIÓN, coherente con la evidencia de costos]**.
- Papers que asumen costos nulos (p. ej. [arXiv 2009.12155](https://arxiv.org/pdf/2009.12155) asume comisiones, spread y slippage despreciables) → solo como evidencia de existencia de tendencia, no de rentabilidad neta.
- Sharpe anualizados con 252 días (cripto opera 365).
- Resultados de un solo par o de un solo periodo alcista (2020–2021) sin bajista (2022) ni lateral.
- **Sesgo de publicación [OPINIÓN fundada en Harvey-Liu-Zhu]:** blogs, posts de Binance Square, vendedores de bots y "estudios" con Sharpe > 2 sin código ni costos son casi seguramente sobreajustados; los papers académicos también tienen sesgo hacia resultados positivos (Harvey et al.: "la mayoría de hallazgos publicados en economía financiera probablemente son falsos").

---

## 3. Variables cuantitativas exactas (para el harness)

| Variable | Definición exacta | Fuente de datos |
|---|---|---|
| `r_t` | close_t/close_{t−1} − 1 de la barra **cerrada** | klines |
| `ATR_n` | media simple (o Wilder) de TR = max(h−l, |h−c_{t−1}|, |l−c_{t−1}|), n barras | klines |
| `ATR%` | ATR_n / close | klines |
| `quote_vol_30d` | mediana diaria de quote asset volume últimos 30 días | klines (campo 7) |
| `fee_maker/taker` | por símbolo y mercado | `/api/v3/account/commission`, `/fapi/v1/commissionRate` |
| `funding_rate`, `funding_time` | por evento | `/fapi/v1/fundingRate`, data.binance.vision |
| `funding_interval_h` | por símbolo | `/fapi/v1/fundingInfo` (ver informe 04) |
| `slip_bps` | modelo §2.2 | derivado |
| `SR_d`, `PSR`, `DSR`, `PBO` | §2.5 | derivado |
| `N_trials` | nº total de configuraciones evaluadas (log persistente) | log del harness |
| `T_obs` | nº de retornos diarios OOS | derivado |

---

## 4. Criterios de aceptación propuestos (gate) [OPINIÓN — umbrales a discutir por los agentes]

Una estrategia/configuración es **ACEPTADA para paper trading** solo si cumple **todas**:

1. **Costos**: OOS neto de comisión taker + slippage §2.2 + funding real.
2. **nº trades OOS ≥ 100** agregados en el universo y **≥ 30** en al menos 60% de las monedas donde se aplica (si no, la estadística es ruido).
3. **Sharpe OOS diario anualizado ≥ 1.0** (neto) y **DSR ≥ 0.95** con N = todas las pruebas registradas.
4. **PBO ≤ 0.30** (CSCV, S = 16).
5. **Profit factor OOS ≥ 1.3**; expectancy > 0 con IC 95% bootstrap (por bloques) que excluya 0.
6. **MaxDD OOS ≤ 25%** (spot) / **≤ 20%** (futuros, apalancamiento efectivo ≤ 2x); Calmar ≥ 0.75.
7. **Estrés ×2 costos**: Sharpe ≥ 0.5 y PF ≥ 1.1. **Retraso 1 barra**: Sharpe ≥ 50% del base.
8. **Estabilidad**: positiva en ≥ 60% de los folds walk-forward y en ≥ 2 de 3 regímenes (alcista, bajista, lateral, definidos ex-ante, p. ej. por la pendiente de la SMA200 diaria de BTC).
9. **Meseta de parámetros**: §2.4 punto 7.
10. **Holdout final** (una sola evaluación): Sharpe > 0 y DD dentro de 1.5× el MaxDD del walk-forward.
11. **Supera benchmarks** con el mismo riesgo: buy & hold BTC (spot) y "entrada aleatoria con mismas salidas/stops" (100 semillas; la estrategia debe estar por encima del percentil 95).

Tras aceptar: **paper/testnet ≥ 4 semanas**; descartar si el slippage medio real > 2× el modelado o si el Sharpe realizado cae fuera del intervalo de predicción del backtest.

---

## 5. Estrategias candidatas (para someter al gate)

> Ninguna está "validada" por este informe: son las candidatas con mejor relación evidencia/simplicidad para pasar por la metodología anterior. Todas: **solo barras cerradas**, ejecución al **open de la barra siguiente**, costos §2.

### C1. Trend following de serie temporal con volatility targeting (spot long-only y futuros long/short)
- **Reglas**: barra 1d (alternativa 4h). Señal = signo de r_L (retorno acumulado de L días) **y** close > SMA(L). Spot: largo si señal > 0, flat si no. Futuros: largo si r_L > 0 y close > SMA(L); corto si r_L < 0 y close < SMA(L); flat en otro caso. Rebalanceo diario.
- **Sizing**: peso_i = min(w_max, σ_target / σ_i,20d) / n_activos_con_señal, σ anualizada con √365; apalancamiento total ≤ 2x en futuros.
- **Stop**: trailing de k·ATR(20) desde el máximo (largos)/mínimo (cortos) posterior a la entrada; salida también por cambio de señal.
- **Filtros**: universo buckets A–B; excluir símbolos con < 365 días de historia; en futuros, no abrir largo si funding_8h equivalente > 0.05% (crowded long).
- **Parámetros**: L ∈ {20, 30, 60, 90}; σ_target ∈ {20%, 30%, 40%} anual; k ∈ {3, 4, 5}; w_max = 0.25. (≤ 36 configs → N pequeño, bueno para DSR.)
- **Evidencia**: TSMOM más robusto que XS tras costos (Han, Kang & Ryu vía [ACFR PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)); TSMOM Sharpe 0.54–0.65 OOS 2022–2024 con costos ([arXiv 2602.11708](https://arxiv.org/pdf/2602.11708), verificar). Sin costos: [arXiv 2009.12155](https://arxiv.org/pdf/2009.12155) (evidencia débil para neto).
- **Régimen**: funciona en tendencias largas (2020–21, 2023–24); falla en laterales con whipsaw y en reversiones en V (pierde el arranque).

### C2. Breakout de Donchian con stop ATR (rotacional, multi-moneda)
- **Reglas**: barra 1d. Entrada larga si close > max(high, N_in) de las N_in barras previas (excluyendo la actual). Salida si close < min(low, N_out) de las N_out previas, o stop. Futuros: simétrico para cortos (close < min(low,N_in)). Máx. P posiciones simultáneas; si hay más señales, priorizar por r_L / σ (momentum ajustado por volatilidad).
- **Stop**: inicial entry − m·ATR(20); riesgo por trade = 0.5–1% del equity → qty = riesgo / (m·ATR).
- **Parámetros**: N_in ∈ {20, 40, 55}; N_out ∈ {10, 20}; m ∈ {2, 3, 4}; P ∈ {5, 10}.
- **Evidencia**: Zarattini, Pagani & Barbon, *Catching Crypto Trends* (cartera rotacional top-20): Sharpe > 1.5 y alfa anual 10.8% vs BTC **neto de comisiones** ([abarbon.com](https://abarbon.com/papers/catching-crypto-trends)) — un solo estudio, autores con interés comercial en trend following → **evidencia moderada; replicar**.
- **Régimen**: idem C1; en altcoins el riesgo de gap/listing/delisting es alto → solo buckets A–B.

### C3. Momentum cross-sectional semanal long/short (solo futuros)
- **Reglas**: cada lunes 00:00 UTC (barra 1w cerrada), rankear el universo por retorno de 3 semanas (saltando la última semana opcional); largo el quintil superior, corto el inferior, pesos iguales por volatilidad, neto de mercado ≈ 0.
- **Stop**: ninguno por trade; stop de cartera −10% semanal → flat hasta el siguiente rebalanceo.
- **Parámetros**: lookback ∈ {1, 2, 3, 4} semanas; skip ∈ {0, 1}; universo ≥ 20 perps buckets A–B.
- **Evidencia**: factor momentum en cripto (Liu, Tsyvinski & Wu, *Common Risk Factors in Cryptocurrency*, JoF 2022, [SSRN 3379131](https://papers.ssrn.com/abstract=3379131), muestra 2014–2018 con >1000 monedas, la mayoría sin perps); **pero** con costos y liquidez real la evidencia XS es débil (Han, Kang & Ryu). Señales XS con funding+OHLCV en 10 perps de Binance dieron Sharpe neto negativo (informe 04, SSRN 6701738). → **candidata de baja prioridad, probable rechazo**; útil como control.
- **Régimen**: falla en "crashes de momentum" (rebotes bruscos tras caídas) y con universo pequeño.

### C4. Carry delta-neutral de funding (spot largo + perp corto) — condicional
- **Reglas**: evaluar cada fundingTime. Abrir si la media de los últimos 3 fundings (normalizada a 8h) > umbral_in y el funding previsto (`lastFundingRate` de premiumIndex) > 0. Posición: comprar Q en spot, vender Q en perp (mismo nocional). Cerrar si media de 3 fundings < umbral_out o basis perp-spot < −0.2%.
- **Costos**: 4 patas (2 spot + 2 perp) ≈ 0.2% + 0.1% + slippage; **break-even** en número de fundings = costo_total / funding_medio (debe ser ≤ 1/3 del holding esperado).
- **Parámetros**: umbral_in ∈ {0.03%, 0.05%, 0.08%} por 8h; umbral_out ∈ {0.01%, 0.02%}; apalancamiento perp ≤ 2x con margen suficiente para un +30% del subyacente sin liquidación.
- **Evidencia**: carry grande y variable explicado por demanda apalancada ([BIS WP 1087](https://www.bis.org/publ/work1087.htm)); pero oportunidades rentables tras costos en solo ~40% de casos ([MDPI Mathematics 14(2):346](https://www.mdpi.com/2227-7390/14/2/346)) y Sharpe negativo reportado en 2025 (informe 04). **Evidencia moderada, alfa decreciente.**
- **Régimen**: funciona en mercados alcistas apalancados (funding alto persistente); falla con funding ≈ 0.01% base (no cubre costos) y en caídas violentas (riesgo de liquidación de la pata corta si el precio sube, de ADL, de deslistado).

### C5. Benchmark nulo obligatorio (no es estrategia para operar)
- Buy & hold BTC/ETH (spot) y **entrada aleatoria** con las mismas reglas de salida/stop/sizing que la candidata (100 semillas). Toda candidata debe superarlas en Sharpe neto (percentil ≥ 95). Sin esto, no se puede distinguir habilidad de beta/suerte.

---

## 6. Cambios concretos recomendados al repo [OPINIÓN, basada en CÓDIGO]

1. `apps/analytics/backtester.py`: eliminar el fallback silencioso a mock (lanzar excepción); añadir costos (§2.1–2.2); anualización por timeframe (§2.5); CAGR compuesto; contar trades por ciclos; ejecución al open siguiente.
2. Feed/estrategias: procesar solo velas con `x == true`; en REST descartar filas con `closeTime >= serverTime`.
3. Registro persistente de **todas** las configuraciones probadas (N para DSR/PBO).
4. Holdout de 6 meses bloqueado por configuración (fecha de corte en config) y log de accesos.
5. Abandonar 1m como timeframe de señal; evaluar 1h/4h/1d.

---

## 7. Limitaciones de este informe
- No pude abrir PDFs; las fórmulas de PSR/DSR/MinBTL/CSCV son de conocimiento previo y deben cotejarse (p. ej. con el código de `pypbo` accesible en GitHub o con el paquete R `pbo`).
- Las comisiones de Binance global vienen de fuentes secundarias o de Binance.US; validar con la API de la cuenta.
- No existe evidencia académica de slippage para altcoins en Binance; el modelo §2.2 es una hipótesis conservadora.
- Los resultados de papers 2025–2026 de arXiv (2512.22476, 2602.10785, 2602.11708) son **preprints sin revisión por pares**.
