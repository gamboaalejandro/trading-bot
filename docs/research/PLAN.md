# PLAN — Rediseño de estrategias spot + futuros USDT-M (especificación para el harness de implementación)

Fecha: 2026-10-15. Autor: moderador y arquitecto principal (síntesis de los informes `research/01-07`, del informe de datos `data/README.md` y de dos rondas de debate con cinco perspectivas: pesimista, optimista, realista, analítica y matemática).

**Convenciones**
- **[EVIDENCIA]**: dato con fuente citada (URL en los informes 01-07) o cálculo propio reproducible sobre `/home/user/harness/data`.
- **[OPINIÓN]**: decisión de diseño o umbral fijado a priori. No se optimiza.
- **[VERIFICAR]**: dato que no se pudo confirmar desde este contenedor (Binance, SSRN y arXiv devuelven 403 o fallan por DNS). Hay que comprobarlo antes de usarlo en real.
- Ninguna cifra publicada (por ejemplo, el "Sharpe > 1.5" de Zarattini 2025) es un objetivo. Solo cuentan los números fuera de muestra (OOS) que produzca este harness, con su script y el commit de los datos.
- Repo de trabajo: `/home/user/trading-bot`, rama `develop`, commit `86c3d5a` (merge de `release/1.1.0`). El debate revisó `4f5dea0`.

---

## 1. Resumen ejecutivo

### 1.1 Conclusión del debate

1. **No existe hoy ninguna estrategia validada.** Lo único que tiene evidencia externa razonable y una ratio coste/edge aceptable es la familia **TENDENCIA DIARIA**: un ensemble de canales Donchian más TSMOM/precio>SMA, con volatilidad objetivo. Evidencia: Zarattini-Pagani-Barbon 2025 (SSRN 5209907), Detzel et al. 2021 (Financial Management), Liu-Tsyvinski 2021 (RFS) y Han-Kang-Ryu. Las cinco perspectivas la ponen como núcleo.
2. **La prueba local del optimista es exploratoria e in-sample.** [EVIDENCIA, cálculo propio]
   - Resultado: Sharpe 0.64-0.75 y MaxDD de -32% a -37%, frente a B&H de BTC con Sharpe 0.45 y MaxDD -77%. Aguanta costes ×2.
   - No es significativa: t ≈ 1.5 e IC95 del Sharpe ≈ [-0.3, 1.7].
   - Pierde en 2022 (-15/-17%) y 2025 (-16%). El único tramo fuera de muestra respecto al paper (2025-04 en adelante) sale negativo.
   - Cambiar la regla de salida movió el CAGR del 17% al 12.9%: la varianza de implementación es alta.
3. **No hace falta apalancamiento en la pata larga.** [EVIDENCIA, cálculo del matemático]
   - Para una vol de cartera del 17% basta una exposición bruta de 0.27x en un largo equiponderado de 18 perps (vol de la cesta 0.64) o de 0.37x en BTC.
   - Las mechas del 2025-10-10 (SUI -79/-83%, AVAX -63/-70%, DOGE -58/-66%) liquidan a 2x casi todas las altcoins.
   - **Decisión:** exposición bruta larga ≤ 1x. Los largos van en **spot** siempre que exista el par, porque un largo en perp paga funding: ≈11-14% APR medio en BTC y ETH en la muestra, y 28-48% en 2021.
   - Los futuros se justifican solo por (a) la pata corta condicionada, (b) los símbolos sin spot y (c) el carry futuro.
4. **El carry de funding es episódico y hoy está apagado.** [EVIDENCIA, cálculo propio]
   - Días con APR de 3 días ≥ 25%: 28-50% en 2021, 7-18% en 2024 y 0% en 2022, 2025 y 2026.
   - Va como módulo latente y **solo en paper trading**.
5. **Sentimiento, OI, ratio long/short y liquidaciones no tienen histórico fiable en local.**
   - El OI de 2022 viene imputado (86% de las barras en BTC). No hay Fear & Greed, el LSR solo cubre 30 días y el stream de liquidaciones infracuenta.
   - Lo único utilizable es el **funding** (17 símbolos; BNB queda excluido, ver §5.2) como overlay que solo puede reducir riesgo.
6. **"La estrategia más adaptable según el contexto" no es un meta-selector optimizado.**
   - Por defecto se asigna **paridad de riesgo fija** entre los motores aceptados, que se autorregulan: la tendencia se queda plana en rango, el corto solo actúa con BTC < SMA200 y el carry solo con funding alto.
   - Un selector régimen→estrategia es **una estrategia más**, con su DSR y su PBO. Solo sustituye a la paridad si gana con p < 0.05 en un bootstrap de la diferencia.
   - La adaptabilidad se mide con el **Q20 encogido** de los Sharpe OOS por celda (moneda × régimen ex-ante). Nunca con la media ni con el mejor caso.
7. **El bot actual (1m, BB+RSI y MA+RSI, TP 3R) se apaga en real.** Hay unanimidad.
   - El coste de ida y vuelta en spot (0.20%) supera el rango típico de una vela de 1m y equivale al 65% del ATR de 15m de BTC.
   - Las señales usan `iloc[-1]`, que puede ser la vela no cerrada.
   - El backtester actual (`apps/analytics/backtester.py`) no descuenta costes y cae en silencio a datos simulados: **no sirve para decidir**.
8. **Resultado probable y honesto.**
   - Con 6 años de datos, un Sharpe verdadero de 1 da t ≈ 2.45 < 3, y N_eff de monedas ≈ 1.6-2.4.
   - Es probable que **ninguna** estrategia alcance el nivel A del gate (§5.6) y que lo mejor quede en nivel B, es decir, paper prolongado.
   - El harness debe aceptar "ninguna pasa" como resultado válido y no relajar el gate a posteriori.

### 1.2 Tabla de puntuaciones (ronda 2, final; 0-10)

| Candidata | Pes. | Opt. | Real. | Anal. | Mat. | Media | Decisión |
|---|---|---|---|---|---|---|---|
| Benchmark nulo (B&H con vol igualada + entradas aleatorias) | 10 | 10 | 10 | 9.5 | 10 | 9.9 | Implementar (juez) |
| Capa de riesgo D (vol target, beta-BTC, clusters, kill-switch, liquidación) | 9.5 | 9 | 9 | 8.5 | 9.5 | 9.1 | Implementar (fija a priori) |
| Tendencia diaria: ensemble Donchian + TSMOM, vol target | 6.5 | 9 | 9 / 7.5 | 8 | 8.5 | ≈8.1 | Implementar y probar (núcleo) |
| Ejecución en perps (algoOrder, aislado, one-way) | 4–9* | 8 | 7 | (en tendencia) | 7.5 | ≈7 | Implementar (infraestructura) |
| Filtro de régimen BTC (SMA200/SMA50), solo como reductor | 5 | 5 | 6.5 | 5.5 | 5.5 | 5.5 | Probar (A/B) |
| Overlay de crowding solo con funding (sin BNB) | 4 | 6 | 5.5 | 5 | 5 | 5.1 | Probar (A/B) |
| Pata corta condicionada en perps (BTC<SMA200, peso ≤0.5) | 2.5 | 7 | 5.5 | — | 5 | 5.0 | Probar (A/B, aparte) |
| Carry de funding delta-neutral condicional | 3.5 | 5 | 4 | 4.5 | 4 | 4.2 | Probar; solo paper |
| Breakout 4h + régimen diario (01-C3; 03-C2 como ablación) | 3.5 | 4 | 4.5 | 4 | 4 | 4.0 | Probar (debe batir a la tendencia diaria) |
| Pullback 1h / RSI(2) como overlay de entrada | 2.5 | 3 | 3.5 | 3.5 | 4 | 3.3 | Probar, prioridad baja |
| Reversión tras shock 1h (sin OI) | 1.5 | 3 | 2.5 | 3 | 3.5 | 2.7 | Probar; solo paper |
| Meta-selector régimen→estrategia | — | (paridad) | (paridad) | (como estrategia) | 3 | — | Compite contra la paridad |
| MR-Range Bollinger 1h | 1 | — | 2 | 2 | 2.5 | 1.9 | Descartar |
| Cross-sectional (momentum top-k, 52 semanas, XS L/S, XS-rev) | 1.5 | 2 | 2.5 | 1.5 | 2 | 1.9 | Descartar |
| Pares cointegrados en perps | 1.5 | 1 | 1.5 | 2 | 2 | 1.6 | Descartar |
| Funding contrario, S2, LSR, cascadas, F&G, HMM | 1 | 1–2 | 1–2 | 1.5 | 1.5 | ≈1.4 | Descartar; solo recolección o paper |
| Bot actual 1m / tendencia intradía 1m-15m | 0 | 0 | 0 | 0 | 0.5 | 0.1 | Apagar |

\* El pesimista da 9 a la higiene de ejecución y 4 a usar perps en largos de altcoins.

### 1.3 Consensos

- Benchmark nulo obligatorio y log append-only de **todas** las configuraciones probadas. El DSR usa ese N y el presupuesto total es **N ≤ 40** en todo el proyecto.
- Donchian, TSMOM y SMA son **una sola hipótesis**, con una especificación fijada a priori y la sensibilidad reportada como meseta.
- Higiene del backtest:
  - solo velas cerradas y fill en la apertura t+1;
  - costes reales y costes ×2;
  - funding en cada settlement;
  - filtrar `volume == 0`;
  - nunca datos simulados: si falta un dato, el proceso falla.
- Futuros:
  - margen aislado y modo one-way;
  - distancia a liquidación ≥ max(3× la distancia al stop, peor mecha histórica);
  - stops STOP_MARKET reduceOnly con MARK_PRICE vía `POST /fapi/v1/algoOrder`. Desde el 2025-12-09, `/fapi/v1/order` devuelve -4120 para órdenes stop según el changelog oficial que citó el realista: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Algo-Order [VERIFICAR los parámetros exactos].
- Al menos 4 semanas de demo/testnet antes de usar capital real. dry-run por defecto.
- Claves API **fuera de git aunque el repo sea privado**, sin permiso de retiro y con whitelist de IP.

### 1.4 Disensos y cómo se resuelven

| Tema | Posiciones | Resolución (OPINIÓN del moderador) |
|---|---|---|
| Gate por año | El pesimista exige ganar al B&H en 2022, 2023-24 y 2025-26 por separado. El matemático calcula que ese gate tiene ≈29% de potencia ante un edge real de ΔSR = 0.3. | Test conjunto de la diferencia (bootstrap estacionario) más una condición de **no catástrofe** por subperiodo: Δ̂SR > -1·SE y MaxDD ≤ el del B&H con vol igualada. Siempre se reporta por año. |
| Precio de ejecución del stop | El pesimista pide el peor precio de la barra; el analítico, gap-aware. | **Caso base** gap-aware: fill = min(stop, open) en largos, más slippage. **Estrés obligatorio**: peor precio de la barra con costes ×2. Se reportan los dos. |
| Exposición bruta >1 con vol target de cartera | El optimista lo propuso; los otros cuatro lo refutaron. | Exposición bruta larga ≤ 1x. Correlación de estrés (§2.0). L por posición ≤ 1x en altcoins y ≤ 1.5x en BTC/ETH. |
| Kill-switch -4% | El pesimista quiere cerrar todo; el realista, cerrar solo lo apalancado. | -2% diario: sin nuevas entradas. -4%: cerrar las posiciones con L > 1 y la pata corta, y bloquear spot 1x con alerta. **Los umbrales los fija el usuario.** |
| Carry | Puntuaciones de 3.5 a 5. | Backtest con N ≤ 3 y solo en paper, con funding contrastado contra el endpoint oficial. Se construye después del cliente de futuros. |
| Kelly | El matemático corrigió su propio doble descuento. | vol_obj_cartera = 0.5·SR_aj, con SR_aj = SR_OOS·(1-haircut) y haircut = 50% por defecto. Con SR de 0.6-0.8 da ≈15-20%. Mientras no haya SR OOS se usa **σ_p* = 15%** como valor prudente. |
| Holdout | Se pensó en 2026-03-10 a 2026-09-10 (futuros). | **Ya está contaminado en parte** para la familia de tendencia, porque el optimista reportó "2026 YTD". Queda como **control de sanidad**. Los OOS limpios son el **spot 2017-08 a 2020-08 con parámetros congelados** (nadie lo ha mirado con estrategias) y el **paper trading futuro**. |

---

## 2. Estrategias a implementar y probar

### 2.0 Definiciones comunes (todas causales)

- Las barras son UTC y cerradas. La barra 1d de t cierra a las 00:00 UTC de t+1. **Señal al cierre de t y fill en `open[t+1]`.**
- `r_t = C_t/C_{t-1} − 1`. `σ_n(t)` = desviación típica de los log-retornos diarios de las últimas n barras, ×√365.
- `ATR14` de Wilder. `ATR% = ATR14/C`.
- `SMA_n`, `EMA_n` estándar. Donchian sobre **cierres**:
  - `UP_n(t) = max(C_{t-n..t-1})`
  - `DN_n(t) = min(C_{t-n..t-1})`
  - `MID_n = (UP_n + DN_n)/2`
- Funding:
  - `F̄_3d` = media de los últimos 9 settlements (8h);
  - `APR(F) = F·3·365` (fracción);
  - `fund_pct` = percentil de `F̄_3d` en una ventana móvil de 365 días con mínimo de 180 días.
- **Discretización de la señal:** `E_q = round(4·E)/4` ∈ {0, .25, .5, .75, 1}. Reduce grados de libertad y respeta el minNotional.
- **Construcción de cartera común** (capa D, fija, consume 0 configuraciones):
  1. Peso bruto por moneda: `u_i = E_q,i / σ_90,i`.
  2. Covarianza de estrés: `Σ_s = D·R_s·D`, con `R_s,ij = max(ρ̂_ij^EWMA(λ=0.97), 0.75)` [OPINIÓN: suelo alto de correlación porque la diversificación desaparece en los crashes].
  3. Escala: `w = u · σ_p* / sqrt(uᵀ Σ_s u)`.
  4. Topes, en este orden: |w_i| ≤ 0.20 en altcoins y ≤ 0.35 en BTC/ETH; Σ alts largo ≤ 0.60; **bruto largo ≤ 1.0**; bruto corto ≤ 0.5; y w_i nunca mayor que el peso sin escalar que daría `E_q,i·min(σ*_coin/σ_90,i, 1)` con σ*_coin = 25%.
  5. **Banda de no-trade:** se rebalancea el símbolo i solo si `|w_i,new − w_i,held| > b·max(|w_i,held|, |w_i,new|)`, o si `E_q` pasa a 0 o sale de 0. Por defecto b = 0.20.
  6. Rebalanceo diario a las 00:00 UTC más 5 minutos (en vivo).
- **Stop de catástrofe** (todas las posiciones de tendencia, también en el backtest): `stop(t) = max(stop(t−1), C_t − 3·ATR14_1d(t))` para largos (simétrico para cortos). Se mueve como mucho una vez al día, tras el cierre. Se coloca en el exchange desde la entrada.
- **Universo de backtest:**
  - Símbolos con ≥ 365 días de historia (esto excluye de paso las dos semanas posteriores a un listado) y una mediana de volumen en USDT a 30 días ≥ 5M.
  - Futuros: 18 perps. **BNB queda fuera de todo P&L de perps** porque su funding es anómalo (§5.2).
  - Spot: 10 monedas.
  - Comparación spot frente a perp: las 9 monedas comunes sin BNB.

### 2.1 Tabla resumen y presupuesto de ensayos (N ≤ 40)

Ya consumidos: **8 ensayos exploratorios del debate**. Son 2 de la ronda 1 del optimista (Donchian con Lmax 1 y 2) y 6 de la ronda 2 (4 de tendencia, 1 de corto con vol de cartera y 1 de carry). Se registran en el log con la etiqueta `debate-exploratorio`.

| ID | Estrategia | Mercado | TF | Cuota N | Destino si pasa |
|---|---|---|---|---|---|
| BENCH | B&H con vol igualada + entradas aleatorias (100 semillas) | ambos | 1d / según la candidata | 0 (no es un ensayo) | juez |
| TREND | Ensemble Donchian / TSMOM / MIX | spot (largo), perp (comparación) | 1d | 5 | núcleo |
| SHORT | Pata corta condicionada | perp | 1d | 2 | A/B sobre TREND |
| REGIME | Filtro BTC, solo reductor | ambos | 1d | 3 | A/B sobre TREND |
| FVETO | Veto o reducción por crowding de funding | ambos (dato de perp) | 1d | 3 | A/B sobre TREND |
| BRK4H | Breakout 4h + régimen diario | perp (largo y corto), spot (largo) | 4h | 5 | debe batir a TREND |
| CARRY | Carry delta-neutral condicional | spot + perp | settlement 8h | 3 | solo paper |
| PULLBACK | Overlay de entrada 1h | ambos | 1h | 3 | mejora de ejecución |
| SHOCK | Reversión tras shock 1h | perp / spot | 1h | 3 | solo paper |
| SELECTOR | Meta-selector frente a paridad | — | — | 3 | sustituye a la paridad solo con p < 0.05 |
| Reserva | — | — | — | 2 | — |
| **Total** | | | | **8 + 32 = 40** | |

**Qué cuenta como ensayo:** toda configuración con reglas o parámetros distintos que llegue a calcular métricas sobre datos de 2022 o posteriores. **No cuentan** las pruebas de robustez de la misma configuración (costes ×2, retraso de 1 barra, funding ×0.5/×2, stop al peor precio), el benchmark ni los tests unitarios. Si una familia agota su cuota sin pasar el gate, se cierra y su N se conserva.

### 2.2 TREND — familia de tendencia diaria (5 configuraciones)

**TREND-DON (01-C1 / 03-C1 / 06-A).**
- Ventanas `N = {5, 10, 20, 30, 60, 90, 150, 250, 360}` [VERIFICAR-PDF contra Zarattini 2025].
- Para cada sub-modelo n:
  - si está plano y `C_t > UP_n(t)`, pasa a `pos_n = 1` con `S_n = MID_n(t)`;
  - cada día, `S_n(t) = max(S_n(t−1), MID_n(t))`;
  - si `C_t < S_n(t)`, pasa a `pos_n = 0`.
- `E_t = media_n(pos_n)`.

**TREND-TSM (01-C2 / 07-C1).**
- `s_k = 1{C_t > SMA_{n_k}(t)}`, con `n ∈ {10, 20, 40, 50, 100, 200}`.
- `E_t = media(s_k)`.

**TREND-MIX.** `E_t = 0.5·E_DON + 0.5·E_TSM`.

**Sizing.** Construcción común de §2.0, con σ_90 en la familia.

Las 5 configuraciones (se fijan todas antes de ver resultados):

| Config | Señal | σ_p* | banda b |
|---|---|---|---|
| T1 | DON | 15% | 0.20 |
| T2 | TSM | 15% | 0.20 |
| T3 | MIX (**configuración primaria preregistrada**) | 15% | 0.20 |
| T4 | MIX | 20% | 0.20 |
| T5 | MIX | 15% | 0.10 |

- **Mercado:**
  - La pata larga se ejecuta en spot. El mismo backtest corre en perp con L = 1 para reportar el coste de funding, pero **eso no es un ensayo nuevo**.
  - Regla preregistrada: la pata larga va en spot salvo que el perp gane con p < 0.05 en el bootstrap de la diferencia.
- **Variables:** OHLCV 1d, volumen en USDT y, en perp, funding.

### 2.3 SHORT — pata corta condicionada (perps; 2 configuraciones)

- Se activa solo si BTC cumple `C_1d < SMA200_1d`.
- Sub-modelos Donchian espejo con ventanas `{20, 30, 60, 90, 150, 250, 360}`:
  - entrada si `C_t < DN_n`, con `S_n = MID_n`;
  - trailing con `S_n(t) = min(S_n(t−1), MID_n(t))`;
  - salida si `C_t > S_n`.
- `E_s = media`, discretizada en cuartos. `w_short = −k·E_s,q / σ_90`, escalado con la misma Σ_s. Tope de bruto corto 0.5.
- **Veto:** no abrir cortos si `APR(F̄_3d) < −25%` (pagarían más de un 25% anual).
- Margen de la pata corta: L ≤ 1. El chequeo de liquidación usa la peor mecha **alcista** histórica, causal.
- Configuraciones:
  - S1: k = 0.5 sobre T3.
  - S2: k = 0.25 sobre T3.
- El A/B se hace frente a T3 largo solo.

### 2.4 REGIME — filtro de régimen BTC, solo reductor (3 configuraciones)

Es un multiplicador `m_t ∈ (0, 1]` sobre la exposición larga de TREND en **altcoins y BTC**. Nunca aumenta la exposición.

| Config | Regla |
|---|---|
| R1 | `m = 1` si `C_BTC > SMA200`; si no, `m = 0.5` |
| R2 | `m = 1` si `C>SMA200` y `SMA50>SMA200`; `m = 0.5` si se cumple solo una; `m = 0.25` si no se cumple ninguna |
| R3 | R2 × (0.5 si el percentil expanding (≥365 d) de `ATR%_BTC` es > 80; si no, 1) |

### 2.5 FVETO — overlay de crowding por funding (3 configuraciones)

Se aplica por símbolo y excluye BNB. Usa el funding conocido en t, es decir, settlements con timestamp ≤ cierre de t.

| Config | Regla |
|---|---|
| F1 | Si `fund_pct ≥ 95` o `APR(F̄_3d) > 50%`: **sin nuevas entradas largas** (E_q no puede subir); las posiciones abiertas se mantienen |
| F2 | Mismo disparador: `w_i ← 0.5·w_i` |
| F3 | Disparador `fund_pct ≥ 90`: `w_i ← 0.5·w_i` |

Criterio de aceptación: reducir el CVaR95 o el MaxDD sin empeorar el Sharpe de forma significativa (§5.6).

### 2.6 BRK4H — breakout 4h con régimen diario (01-C3 / 03-C2; 5 configuraciones)

- **Régimen** (vela 1d cerrada, unida con `merge_asof` en dirección backward):
  - largo permitido si `C_1d > SMA100_1d` y `ADX14_1d ≥ 20`;
  - corto (solo perp) si `C_1d < SMA100_1d`, `ADX14_1d ≥ 20` y BTC `C < SMA200`.
- **Entrada:** largo si `C_4h > max(H_{t−n..t−1})`, con n en barras de 4h. Corto simétrico con `min(L)`.
- **Stop inicial:** `entry − 2.5·ATR14_4h` (va en el exchange).
- **Trailing chandelier:** `max(H desde entrada) − 3·ATR14_4h`, solo a favor.
- **Salida adicional:** `C_4h < MID_n`, o el régimen diario se invierte.
- **Sizing:** riesgo 0.5% del NAV por trade en BTC/ETH y 0.25% en altcoins: `qty = R·NAV/(entry − stop)`. Topes de §2.0 y apalancamiento efectivo ≤ 1x en altcoins y ≤ 1.5x en BTC/ETH.
- **Filtro de funding:** no abrir largo si `APR(F̄_3d) > 50%` o `fund_pct > 95`; no abrir corto si `APR < −30%`.
- Configuraciones:
  - B1: n = 20, todos los filtros.
  - B2: n = 55, todos los filtros.
  - B3: B1 sin ADX (ablación).
  - B4: B1 sin filtro de funding (ablación).
  - B5: B1 más el filtro de 03-C2: `rvol = V/mediana(V,20) ≥ 1.5` y `close_loc = (C−L)/(H−L) ≥ 0.7`.
- Solo pasa si supera a T3 en DSR con el N global y la ablación demuestra que cada filtro aporta.

### 2.7 CARRY — carry delta-neutral condicional (solo paper; 3 configuraciones)

- **Universo:** BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, LINK y DOT (spot y perp, sin BNB).
- **Datos:** spot 4h y perp 4h. Los cierres de 4h coinciden con los settlements de las 00, 08 y 16 UTC. Basis = `C_perp/C_spot − 1`.
- **Evaluación** en cada settlement.
- **Entrada:** `APR(F̄_3d) ≥ θ_in` y el último funding > 0 → compra spot Q y vende perp Q (mismo nocional). La pata corta en aislado con margen suficiente para una subida de +100% sin liquidación (L ≤ 1).
- **Salida:** `APR(F̄_3d) < θ_out` o `basis < −0.2%`.
- **Tamaño:** ≤ 20% del NAV por símbolo, ≤ 5 símbolos y ≤ 70% del NAV en total.
- **Coste por ciclo:** 2×0.10% (spot) + 2×0.05% (perp) + slippage. Se suma el drift real del basis.
- Configuraciones `(θ_in, θ_out)` en APR:
  - K1: (25%, 8%).
  - K2: (20%, 5%).
  - K3: (35%, 10%).
- **Condición previa para creer el P&L:** contrastar el funding con `/fapi/v1/fundingRate` y `/fapi/v1/fundingInfo` desde la máquina del usuario (§8). Mientras tanto, el informe lo marca como "P&L no verificado".

### 2.8 PULLBACK — overlay de entrada en 1h para TREND (3 configuraciones)

- Solo se aplica cuando `E_q,i` **sube**. En lugar de comprar en `open[t+1]`, se espera hasta 24h (en barras de 1h cerradas) a una de estas condiciones:
  - P1: `RSI2_1h < 10`;
  - P2: `C_1h ≤ C_1d,t − 0.5·ATR14_1d`;
  - P3: P1 o P2.
- Si no se da en 24h, se compra a mercado en la apertura de la barra 25.
- Las bajadas de E se ejecutan siempre en t+1, sin esperar.
- **Métrica:** retorno neto incremental por unidad de turnover frente a T3. Spot 1h desde 2022 y futuros 1h desde 2020.

### 2.9 SHOCK — reversión tras shock en 1h (solo paper; 3 configuraciones)

- `z_t = r_1h,t / σ_1h(720 barras)`.
- **Señal larga:** `z_t ≤ −3`, con la condición sistémica `r_1h,BTC,t > −2·σ_1h,BTC` (el shock debe ser idiosincrático) y BTC 1d por encima de su SMA200.
- **Entrada** en `open[t+1]`. Stop `entry − 2·ATR14_1h`. Riesgo 0.25% del NAV.
- **Salida** por tiempo:
  - H1: 4h;
  - H2: 12h;
  - H3: 24h.
- Se reporta aparte la pérdida condicional en 2021-05-19, 2022-11-09 y 2025-10-10.

### 2.10 SELECTOR — meta-estrategia frente a paridad (3 configuraciones)

- M1, el **baseline**: paridad de riesgo fija entre los motores aceptados (nivel A o B), con pesos ∝ 1/σ_motor sobre una ventana de 365 días.
- M2: tabla régimen→pesos. En cada fold de walk-forward, y solo con el entrenamiento, el peso de cada motor por celda (§3.3) es ∝ max(0, SR̃_celda) (encogido por empirical Bayes). La celda de cada día se determina ex-ante.
- M3: M2 con pesos mezclados al 50% con M1.
- M2 y M3 solo se adoptan si superan a M1 con p < 0.05 en un bootstrap estacionario de la diferencia y con PBO ≤ 0.3.

### 2.11 BENCH — benchmark nulo (obligatorio)

- **B&H con vol igualada:** BTC y la cesta equiponderada del mismo universo, escaladas por un multiplicador constante para igualar la vol realizada OOS de la candidata.
- **Entradas aleatorias (100 semillas):**
  - En estrategias de pesos objetivo (TREND y overlays): por símbolo, se permutan aleatoriamente los inicios de los episodios de exposición, conservando su duración y su peso, sin solaparlos y dentro del periodo de vida del símbolo.
  - En estrategias con stops (BRK4H, SHOCK): entradas en instantes aleatorios con la misma frecuencia por símbolo y las mismas reglas de salida y sizing.
- La candidata debe quedar **por encima del percentil 95** de los Sharpe netos aleatorios.

### 2.12 Descartadas (sin implementación de señal)

- MR-Range Bollinger 1h, cross-sectional (momentum, 52 semanas, XS L/S, XS-reversal), pares cointegrados, funding negativo contrario (4 episodios en BTC), funding extremo con OI, LSR, cascadas de liquidación, HMM, throttle de F&G y patrones de velas como disparador.
- Sobre los patrones de velas: según el informe 03, IEEE BigData 2021 analizó 68 patrones en 23 criptos y los encontró "de poca utilidad".
- Lo que sí se hace: los recolectores en vivo de OI, LSR, `!forceOrder` y premiumIndex (§4.6) **graban datos** para una revisión dentro de 6-12 meses.

---

## 3. Capa de contexto y régimen

### 3.1 Features (módulo `apps/research/features/`; todas causales, rolling o expanding)

| Grupo | Feature | Definición | TF | Uso |
|---|---|---|---|---|
| Velas | `body_atr` | `(C−O)/ATR14` | 1h/4h/1d | diagnóstico y meta-etiquetado futuro |
| Velas | `upper_wick_atr`, `lower_wick_atr` | `(H−max(O,C))/ATR14`, `(min(O,C)−L)/ATR14` | idem | diagnóstico; peor mecha para liquidación |
| Velas | `range_atr` | `(H−L)/ATR14` | idem | detección de shock |
| Velas | `close_loc` | `(C−L)/(H−L)` | 4h | BRK4H-B5 |
| Velas | `rvol` | `V/mediana(V,20)` | 4h/1d | BRK4H-B5 y diagnóstico |
| Velas | `gap` | `O_t/C_{t−1} − 1` | 1h/4h | validación de datos y fills |
| Chart | `donchian_pos_n` | `(C−DN_n)/(UP_n−DN_n)` | 1d | diagnóstico |
| Chart | `dist_52w_high` | `C/max(H,365d) − 1` | 1d | diagnóstico (no se opera) |
| Chart | `dd_365` | drawdown desde el máximo de 365 días | 1d | régimen y riesgo |
| Tendencia | `sma_ratio_n` | `C/SMA_n − 1`, n ∈ {50, 100, 200} | 1d | TREND, REGIME |
| Tendencia | `sma50_gt_sma200`, `slope_sma50` | pendiente de 20 días | 1d | REGIME |
| Tendencia | `adx14` | Wilder | 1d/4h | BRK4H |
| Tendencia | `er30` | Kaufman: `|C_t−C_{t−30}| / Σ|ΔC|` | 1d | diagnóstico de celdas |
| Volatilidad | `sigma_30`, `sigma_90` | anualizadas | 1d | sizing |
| Volatilidad | `atr_pct`, `atr_pct_pctl` | percentil expanding (≥365 d) | 1d | REGIME-R3 y celdas |
| Volatilidad | `ewma_corr` | λ = 0.97 | 1d | Σ_s y clusters |
| Funding | `f_bar_3d`, `apr_3d`, `fund_pct` | §2.0 (sin BNB) | 8h→1d | FVETO, CARRY, SHORT |
| Basis | `basis` | `C_perp/C_spot − 1` | 4h/1h | CARRY y diagnóstico |
| Sentimiento | `fng`, `fng_pctl` | **solo si el usuario aporta el CSV de alternative.me**; el loader falla si falta | 1d | solo diagnóstico o paper (multiplicador ≤ 1); no consume N salvo que se pruebe |
| OI/LSR/liquidaciones | — | no hay histórico fiable | — | solo recolección en vivo |

**Regla de causalidad:** el valor de cualquier feature en t usa datos con timestamp ≤ cierre de t. Esto se comprueba con un test que trunca la serie en t y verifica que el valor no cambia (§6).

### 3.2 Etiquetas de régimen ex-ante (máximo 6 celdas)

- `trend_BTC ∈ {up: C_BTC > SMA200_BTC, down}`.
- `vol_tercile ∈ {low, mid, high}` según el percentil expanding de `atr_pct` de BTC (cortes en 33 y 67).
- Celda = `trend_BTC × vol_tercile`, 6 en total. La celda se calcula con la vela 1d cerrada de t y se aplica a los retornos de t+1.

### 3.3 Score de adaptabilidad A_k (por motor k, solo OOS walk-forward)

1. Celdas `(moneda i, régimen j)`. En cada una se calculan el Sharpe neto diario anualizado `SR̂_ij`, sus `T_ij` días y su error estándar `se_ij = sqrt((1 − γ3·SR + (γ4−1)/4·SR²)/T_ij)` (SR por periodo).
2. Encogimiento de empirical Bayes hacia la media del motor: `SR̃_ij = SR̄ + (1−B_ij)(SR̂_ij − SR̄)`, con `B_ij = se_ij²/(se_ij² + τ̂²)` y τ̂² estimado por momentos (truncado en 0).
3. `A_k = Q20_ponderado(SR̃_ij) − λ·p_k/√T_años`. Pesos ∝ `T_ij/(1+(n_cluster−1)·ρ̄)`, p_k = número de parámetros libres y **λ = 0.1** [OPINIÓN, fijo].
4. Se reportan aparte: la fracción de celdas con SR̃ > 0, el CVaR95 diario del peor régimen y el DSR global.
5. **"La más adaptable" es la de mayor A_k entre las que pasan el gate.** Un motor que gana en un régimen y pierde en el resto solo se usa condicionado a ese régimen si M2/M3 vencen a M1.

### 3.4 Meta-estrategia en vivo

- El bot en vivo **no optimiza nada**. Ejecuta los pesos por motor que dejó el informe final del harness: M1 por defecto, o M2/M3 si ganaron.
- Cada motor genera sus pesos objetivo y la capa D los agrega con los topes de §2.0 y §7.
- Las etiquetas de régimen en vivo se calculan con exactamente el mismo código que en el backtest.

---

## 4. Arquitectura de código (dentro de `/home/user/trading-bot`)

### 4.1 Árbol propuesto

```
apps/research/                      # NUEVO. Investigación y backtest (sin red; lee CSV locales)
  __init__.py
  config.py                         # carga config/research.yml (costes, splits, presupuesto, rutas)
  data/
    loader.py                       # load_ohlcv, load_funding, load_fng; validación estricta
    manifest.py                     # commits de las fuentes, hashes de archivos
  features/
    candles.py  trend.py  volatility.py  funding.py  regime.py
  strategies/
    base.py                         # protocolos TargetWeightStrategy / EventStrategy
    trend.py                        # DON, TSM, MIX (+ SHORT)
    overlays.py                     # REGIME, FVETO
    breakout4h.py  carry.py  pullback.py  shock.py
    benchmarks.py                   # B&H con vol igualada, entradas aleatorias
  portfolio/
    sizing.py                       # discretización, vol target con Σ_s, topes, banda
    risk.py                         # kill-switch simulado, chequeo de liquidación, peor mecha
  engine/
    costs.py                        # comisiones, slippage por tramos, funding por settlement
    fills.py                        # open t+1, stops gap-aware o peor de la barra
    liquidation.py                  # LP aislado, MMR por tramo (por defecto conservador)
    portfolio_bt.py                 # motor diario de pesos objetivo (multi-símbolo)
    event_bt.py                     # motor por eventos (stops/TP, 4h/1h)
  validation/
    trials_log.py                   # log append-only (JSONL + hash encadenado)
    stats.py                        # PSR, DSR, MinBTL, SE del Sharpe, bootstrap estacionario, Holm
    pbo.py                          # CSCV S=16
    walkforward.py                  # WF anclado + selección por fold
    holdout.py                      # candado del holdout (una sola apertura, registrada)
    adaptability.py                 # celdas, EB shrinkage, A_k, N_eff
    gate.py                         # niveles A/B/C (§5.6)
  reports/
    report.py                       # markdown/HTML por año, símbolo, régimen; IC
  run.py                            # CLI: python -m apps.research.run <experimento>
apps/live/                          # NUEVO. Ejecución diaria compartiendo el código de estrategias
  portfolio_executor.py             # job diario: datos cerrados → pesos → órdenes
  reconciliation.py                 # estado local frente al exchange
  kill_switch.py                    # umbrales desde config del usuario
  recorders.py                      # OI, LSR, forceOrder, premiumIndex (fase F4)
core/
  binance_client.py                 # spot (existente): + cancelReplace, + klines cerradas
  binance_futures_client.py         # NUEVO: /fapi
  secrets.py                        # NUEVO: lectura de variables de entorno, nunca de archivos versionados
config/
  research.yml                      # NUEVO: costes, splits, presupuesto N, rutas de datos
  risk_limits.yml                   # NUEVO: umbrales que fija el usuario (sin valores por defecto agresivos)
.env.example                        # NUEVO: nombres de variables, sin valores
scripts/
  check_connection.py               # NUEVO: pruebas de conexión de solo lectura (spot demo, futures testnet)
  fetch_official_audit_data.py      # NUEVO: para ejecutar en la máquina del usuario (§8)
tests/research/ , tests/live/       # pytest
```

### 4.2 Interfaces principales (firmas)

```python
# apps/research/data/loader.py
class DataError(Exception): ...
def load_ohlcv(symbol: str, market: Literal["spot","futures"], tf: Literal["15m","1h","4h","1d"],
               start: str | None = None, end: str | None = None, root: Path = DATA_ROOT) -> pd.DataFrame:
    """Índice UTC (DatetimeIndex, apertura de barra), columnas open/high/low/close/volume, quote_volume≈volume*close.
    Filtra volume==0 (marca NaN, sin forward-fill). Lanza DataError si falta el archivo o el rango pedido,
    si hay OHLC inválido o duplicados. Nunca genera datos."""
def load_funding(symbol: str, root: Path = DATA_ROOT, allow_bnb: bool = False) -> pd.Series:
    """funding_rate en FRACCIÓN (0.0001 = 0.01 %), índice = settlement time. BNBUSDT → DataError salvo allow_bnb."""
def load_fng(path: Path) -> pd.Series: ...            # DataError si no existe
def load_panel(symbols, market, tf, start, end) -> dict[str, pd.DataFrame]: ...

# apps/research/strategies/base.py
class TargetWeightStrategy(Protocol):
    name: str; params: dict; n_free_params: int
    def signal(self, panel: dict[str, pd.DataFrame], ctx: "Context") -> pd.DataFrame:
        """E por símbolo y fecha (índice = cierre de t), en [-1,1], usando solo datos ≤ t."""
class EventStrategy(Protocol):
    def on_bar(self, t, bars: dict[str, pd.Series], ctx: "Context") -> list["OrderIntent"]: ...
@dataclass(frozen=True)
class OrderIntent: symbol: str; side: Literal["BUY","SELL"]; qty: float | None; target_weight: float | None
                   order_type: Literal["MARKET","LIMIT"]; stop_price: float | None; reduce_only: bool; tag: str

# apps/research/portfolio/sizing.py
def discretize(E: pd.DataFrame, step: float = 0.25) -> pd.DataFrame: ...
def stress_cov(returns: pd.DataFrame, t, lam: float = 0.97, rho_floor: float = 0.75, vol_window: int = 90) -> np.ndarray: ...
def target_weights(E_q: pd.Series, sigma: pd.Series, cov_s: np.ndarray, cfg: "SizingConfig") -> pd.Series: ...
def apply_band(w_new: pd.Series, w_held: pd.Series, band: float) -> pd.Series: ...

# apps/research/engine/costs.py
@dataclass(frozen=True)
class CostModel: spot_fee: float = 0.0010; fut_taker: float = 0.0005; fut_maker: float = 0.0002
                 slip_bps: dict = {"A":2,"B":5,"C":15}; cost_mult: float = 1.0; funding_mult: float = 1.0
def slippage_bps(symbol, t, quote_vol_30d, atr_pct, atr_pct_med90, cm: CostModel) -> float: ...
def funding_cashflow(position_notional: pd.Series, funding: pd.Series, side: pd.Series, mult: float) -> pd.Series:
    """Para cada settlement τ: −side(τ⁻)·notional(τ⁻)·F(τ)·mult. La posición en τ⁻ es la vigente justo ANTES del rebalanceo de las 00:00."""

# apps/research/engine/portfolio_bt.py
@dataclass
class BTResult: equity: pd.Series; returns: pd.Series; weights: pd.DataFrame; trades: pd.DataFrame
                costs: pd.DataFrame  # comisión, slippage y funding por día y símbolo
                meta: dict           # config, commits de datos, hash del trial
def run_portfolio_bt(strategy: TargetWeightStrategy, panel, market: Literal["spot","futures"],
                     cost: CostModel, sizing: "SizingConfig", risk: "RiskConfig",
                     start, end, stop_fill: Literal["gap_aware","worst_bar"] = "gap_aware",
                     delay_bars: int = 1) -> BTResult: ...

# apps/research/engine/liquidation.py
def liq_price(entry: float, lev: float, side: int, mmr: float = 0.01) -> float:
    """Largo: EP·(1−1/L)/(1−MMR); corto: EP·(1+1/L)/(1+MMR). Simplificación [VERIFICAR con leverageBracket]."""
def worst_wick(df_1d: pd.DataFrame, side: int) -> pd.Series:   # expanding, causal
def liq_ok(entry, stop, lev, side, worst_wick_t, mmr) -> bool:  # dist_liq ≥ max(3·dist_stop, worst_wick)

# apps/research/validation
class TrialsLog:   # data/trials/trials.jsonl; cada línea: id, ts, agente, familia, params, data_commit, git_sha, métricas, prev_hash
    def register(self, family: str, params: dict, agent: str, tag: str = "") -> str: ...
    def n_total(self) -> int: ...
    def remaining(self, family: str) -> int: ...   # lanza BudgetExceeded al superar la cuota
def psr(sr: float, T: int, skew: float, kurt: float, sr_star: float = 0.0) -> float: ...
def dsr(sr: float, T: int, skew: float, kurt: float, sr_trials_var: float, n_trials: int) -> float: ...
def min_btl(n_trials: int, target_sr: float) -> float: ...
def stationary_bootstrap(x: np.ndarray, stat: Callable, block_mean: int = 20, reps: int = 10_000, seed: int = 0) -> np.ndarray: ...
def pbo_cscv(M: pd.DataFrame, S: int = 16) -> float: ...
def walk_forward(family_configs: list, panel, folds: list[tuple], select: Callable) -> "WFResult": ...
class HoldoutLock:  # data/trials/holdout.lock; open() solo una vez, registra quién y cuándo; segunda llamada → HoldoutAlreadyOpened
def adaptability_score(oos_returns: pd.DataFrame, cells: pd.DataFrame, n_free: int, lam: float = 0.1) -> dict: ...
def evaluate_gate(result, bench, trials: TrialsLog) -> Literal["A","B","C"]: ...
```

### 4.3 Reutilización en el bot en vivo

- `apps/research/strategies/*`, `features/*` y `portfolio/sizing.py` son **el mismo código** en backtest y en vivo, sin duplicar lógica.
- `apps/live/portfolio_executor.py`:
  1. Se ejecuta a las 00:05 UTC.
  2. Descarga klines 1d por REST y **descarta toda fila con `closeTime ≥ serverTime`**.
  3. Construye el panel y llama a `strategy.signal` → `target_weights`, y aplica la capa D y el kill-switch.
  4. Calcula los deltas respecto a las posiciones reales y los redondea a LOT_SIZE y PRICE_FILTER. Los deltas por debajo de MIN_NOTIONAL o NOTIONAL se ignoran y quedan registrados.
  5. Envía las órdenes con `newClientOrderId` determinista (`{fecha}-{motor}-{símbolo}-{seq}`, idempotente).
  6. Coloca o mueve el stop de catástrofe y registra en log cada input y decisión.
- WebSocket: solo el user data stream (y ALGO_UPDATE en futuros) y el monitoreo. Las klines por WebSocket, si se usan, solo con `x == true`.
- Modos de ejecución: `TRADING_MODE ∈ {dry_run (por defecto), spot_demo, futures_testnet, live}`. `live` exige además `LIVE_TRADING_CONFIRM=I_UNDERSTAND`.

### 4.4 Conector de futuros `core/binance_futures_client.py`

- **Bases:** producción `https://fapi.binance.com`. Testnet o demo de futuros: [VERIFICAR la URL vigente: históricamente `https://testnet.binancefuture.com`; el repo usa `demo-api.binance.com` para spot].

```python
class BinanceFuturesClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str, recv_window: int = 5000): ...
    # públicos
    def exchange_info(self) -> dict: ...                          # GET /fapi/v1/exchangeInfo (filtros por símbolo)
    def klines(self, symbol, interval, limit=1500, closed_only=True) -> pd.DataFrame: ...
    def mark_price_klines(self, symbol, interval, ...) -> pd.DataFrame: ...
    def funding_rate(self, symbol, start_ms=None, end_ms=None) -> pd.DataFrame: ...   # GET /fapi/v1/fundingRate
    def funding_info(self) -> list[dict]: ...                     # GET /fapi/v1/fundingInfo (intervalos 4h/1h)
    def premium_index(self, symbol=None) -> dict: ...
    # cuenta (firmados)
    def commission_rate(self, symbol) -> dict: ...                # GET /fapi/v1/commissionRate
    def leverage_bracket(self, symbol) -> list[dict]: ...
    def position_risk(self, symbol=None) -> list[dict]: ...
    def account(self) -> dict: ...
    def set_one_way_mode(self) -> None: ...                       # POST /fapi/v1/positionSide/dual dualSidePosition=false
    def set_margin_type(self, symbol, margin_type="ISOLATED") -> None: ...   # idempotente (ignora "No need to change")
    def set_leverage(self, symbol, leverage: int) -> None: ...
    def new_order(self, symbol, side, type_, quantity, client_order_id, reduce_only=False, price=None, tif=None) -> dict: ...
    def new_stop_market_algo(self, symbol, side, quantity, trigger_price, client_algo_id,
                             reduce_only=True, working_type="MARK_PRICE") -> dict: ...
        # POST /fapi/v1/algoOrder [VERIFICAR nombres exactos de los parámetros en
        # https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Algo-Order]
    def cancel_algo_order(self, symbol, algo_id) -> dict: ...
    def open_algo_orders(self, symbol=None) -> list[dict]: ...
    def start_user_stream(self) -> str: ...  def keepalive_user_stream(self, listen_key) -> None: ...
```

**Secuencia de apertura en futuros:**
1. `set_one_way_mode`.
2. `set_margin_type(ISOLATED)` y `set_leverage(L)`, con L = 1 en altcoins y ≤ 2 (efectivo ≤ 1.5) en BTC/ETH.
3. Comprobar `leverage_bracket` → MMR, y calcular `liq_ok`. Si falla, no se opera.
4. Orden MARKET.
5. **Inmediatamente**, `new_stop_market_algo` con reduceOnly y MARK_PRICE.
6. Si el stop falla, cerrar la posición a mercado, alertar y activar el kill-switch del símbolo.

### 4.5 Cambios en el bot existente

- `apps/executor/strategies/*`: no usar `iloc[-1]` sin verificar que la vela está cerrada. Hay que usar la última vela con `closeTime < now`.
- `apps/analytics/backtester.py`: se elimina `_generate_mock_data` y el fallback (ahora lanza una excepción), y se marca DEPRECATED a favor de `apps/research`.
- `multi_symbol_engine._move_exchange_stop`: usar `POST /api/v3/order/cancelReplace` con `cancelReplaceMode=STOP_ON_FAILURE` [VERIFICAR en la documentación de spot], o reintentos con alerta si la posición queda sin stop.
- Perfiles de 1m: pasan a `dry_run` forzado. Activarlos en real exige un flag explícito.

### 4.6 Recolectores (fase F4, opcional)

`apps/live/recorders.py` graba en parquet diario, con reconexión y sin afectar al trading:
- `openInterest` cada 5 minutos;
- `globalLongShortAccountRatio` cada 5 minutos;
- `!forceOrder@arr`;
- `premiumIndex` cada minuto.

---

## 5. Protocolo experimental

### 5.1 Universo

- **Futuros:** BTC, ETH, BNB*, XRP, DOGE, ADA, LINK, DOT, TRX, LTC, BCH, SOL, AVAX, NEAR, OP, APT, ARB y SUI. (*BNB solo OHLCV, sin P&L de perp.)
- **Spot:** BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK y DOT.
- **Sesgo de supervivencia (se declara en cada informe):** todas son monedas listadas en 2026; faltan LUNA, FTT, SRM y otras. Las conclusiones se centran en BTC/ETH, y las de cesta llevan la advertencia.
- **N_eff:** se reporta el participation ratio de los autovalores de la correlación (≈2.4 medido) y `n/(1+(n−1)ρ̄)` (≈1.6).

### 5.2 Datos: reglas obligatorias

1. `funding_rate` está en **fracción**. La columna se llama `funding_rate`, no `funding_rate_pct`.
2. **Funding de BNBUSDT excluido** [EVIDENCIA]: el 50% de sus registros vale 0.0 exacto, ninguno vale 0.0001 y las sumas anuales de 2022-2025 son negativas. Solo vuelve si se re-descarga desde `/fapi/v1/fundingRate`.
3. El funding local está muestreado a las 00, 08 y 16 UTC y puede ser el **predicho**, no el liquidado. Si algún símbolo pasó a intervalos de 4h o 1h, el coste queda infracontado. Por eso es obligatorio el análisis de sensibilidad ×0.5 y ×2, y el informe marca "funding no verificado".
4. Filtrar `volume == 0` en futuros (≈6 velas por símbolo). Los huecos de spot (2017-2019 en 4h y un hueco de 2h en 1h) quedan como NaN, sin forward-fill de retornos.
5. No hay mark price: la liquidación se calcula sobre last price (conservador) y se declara así.
6. El intradía spot anterior a 2022 (1h) y a 2024-12-30 (15m) no existe. Si se usa el OHLC de futuros como proxy (basis mediano ≈ -5 pb), se marca `proxy=True`.
7. Cada resultado guarda el `data_commit` de las fuentes (kbsingh1399 `735eb87…` y finom `4d33a56…`) y el hash de los CSV (`apps/research/data/manifest.py`).

### 5.3 Partición temporal

| Tramo | Fechas | Uso |
|---|---|---|
| Depuración | 2020-09-01 a 2021-12-31 (futuros) y datos de fixture | Desarrollo de código, gráficos y debug. Libre. |
| Walk-forward OOS | Tests trimestrales del 2022-01-01 al 2026-03-09 (17 folds), con entrenamiento anclado desde el inicio de los datos | Solo a través de `run.py` con un trial registrado. Prohibido mirarlo a mano. |
| Holdout de sanidad | 2026-03-10 a 2026-09-10 (futuros); spot hasta 2026-10-15 | Una sola apertura con `HoldoutLock`, al final, para los finalistas. **Ya está parcialmente contaminado para TREND** (el debate vio "2026 YTD"), así que solo sirve como control de sanidad. |
| OOS congelado independiente | Spot 1d del 2017-08-17 al 2020-08-31 (BTC, ETH y luego BNB, XRP, ADA, LINK y DOGE según su listado; warmup de 360 días) | Familias diarias (TREND y sus overlays) con parámetros **congelados**. **Gate eliminatorio.** Incluye el bear de 2018-19. |
| OOS vivo | Paper o testnet desde el despliegue | Holdout real, a 4 semanas como mínimo. |

- **Walk-forward con selección:** en cada fold se elige, entre las configuraciones de la familia, la de mejor Sharpe neto en el tramo de entrenamiento (anclado). El OOS concatenado de esa elección es el resultado de la familia. Cada configuración también se reporta por separado.
- En estrategias con umbrales relativos (percentiles), estos son siempre expanding o rolling, nunca de muestra completa.

### 5.4 Costes [EVIDENCIA, informe 07; VERIFICAR en vivo con `/api/v3/account/commission` y `/fapi/v1/commissionRate`]

- **Spot:** 0.10% por lado (VIP0). Con BNB, 0.075% si el usuario lo confirma.
- **Futuros:** 0.05% taker y 0.02% maker. El caso base usa **taker** en todas las patas.
- **Slippage por tramo de volumen en USDT a 30 días:** A > 500M → 2 pb; B entre 50M y 500M → 5 pb; C entre 5M y 50M → 15 pb; < 5M → excluido. Se multiplica por `max(1, ATR%/mediana_90d(ATR%))`.
- **Funding:** en cada settlement con la posición vigente justo antes del settlement.
- **Estrés obligatorio** (no son ensayos nuevos): costes ×2; retraso de 1 barra adicional (fill en t+2); stop al peor precio de la barra; funding ×0.5 y ×2.
- **Eventos de cola** (reporte obligatorio): 2021-05-19, 2022-11-09 y 2025-10-10. Para cada uno, P&L, liquidaciones simuladas y slippage del stop.

### 5.5 Métricas reportadas

- Por estrategia, año, símbolo y celda de régimen: CAGR, vol, Sharpe con IC95 (bootstrap estacionario con bloque medio de 20 días), Sortino, MaxDD, MAR, CVaR95 diario, turnover, exposición bruta media, número de trades, profit factor, expectancy en múltiplos de ATR, y costes desglosados (comisión, slippage y funding).
- A nivel global: PSR(0), DSR (con N = `TrialsLog.n_total()` y la varianza de los SR de todos los ensayos), MinBTL, PBO (CSCV, S = 16, sobre la matriz T×N de la familia y también global), percentil frente a las entradas aleatorias, test de la diferencia frente al B&H con vol igualada y A_k.
- Fórmulas de PSR, DSR, MinBTL y PBO: según el informe 07 §2.5 (marcadas [FÓRMULA, VERIFICAR]). Hay que **contrastarlas en los tests** con una implementación de referencia (paquete `pypbo` o valores publicados en los ejemplos de Bailey y López de Prado) antes de usarlas para decidir.

### 5.6 Gate de aceptación (dos niveles)

**Nivel A — "aceptada"** (capital real tras ≥ 4 semanas de demo sin incidencias). Debe cumplir **todo** lo siguiente:
1. DSR ≥ 0.95, con el N del log.
2. PBO ≤ 0.30.
3. Sharpe neto OOS > percentil 95 de las entradas aleatorias.
4. Bootstrap de la diferencia de retornos diarios frente al B&H con vol igualada (BTC y cesta): p < 0.05 (una cola).
5. No catástrofe en cada subperiodo (2022, 2023-24, 2025-26): Δ̂SR > −1·SE y MaxDD ≤ MaxDD del B&H con vol igualada.
6. Costes ×2: Sharpe > 0 y ≥ 50% del base. Con retraso de +1 barra: Sharpe ≥ 50% del base.
7. Spot 2017-2020 congelado: Sharpe > 0 y MaxDD ≤ el del B&H con vol igualada.
8. MaxDD OOS ≤ 25% en spot y ≤ 20% en futuros.
9. Holdout: el retorno de 6 meses está por encima del percentil 5 de la distribución bootstrap de ventanas de 6 meses del WF, y el DD ≤ 1.5× el MaxDD del WF.
10. Significancia: t ≥ 3, o el número de trades OOS cumple `n ≥ (3/SR_t)²·(1 − γ3·SR_t + (γ4−1)/4·SR_t²)` en estrategias de trades discretos.

**Nivel B — "candidata a paper":** PSR(0) ≥ 0.90; por encima del percentil 95 aleatorio; PBO ≤ 0.30; A_k > 0; costes ×2 con Sharpe > 0; y spot 2017-2020 sin catástrofe. Pasa a capital real solo tras ≥ 3 meses de paper con un tracking error dentro de 2σ de lo esperado.

**Overlays** (SHORT, REGIME, FVETO, PULLBACK): se evalúan como **incremento** sobre T3 (o sobre la TREND aceptada). Se aceptan si reducen el CVaR95 o el MaxDD, o mejoran el MAR, con p < 0.05 en el bootstrap de la diferencia, sin empeorar el Sharpe más de 1 SE, y con el PBO de la familia ≤ 0.3.

**Nivel C:** se rechaza. Si **nada** llega a A o B, el informe final recomienda **cash o B&H/DCA de BTC con tamaño acotado** (decisión del usuario) y no se relaja el gate.

---

## 6. Plan de tareas para el harness de implementación

### 6.1 Reglas generales

- **Gitflow básico:** se parte de `develop`. Cada tarea va en su rama: `feature/<id>-<nombre>`, `fix/<id>-<nombre>` o `hotfix/...` si afecta a lo que corre en real desde `main`. Entra por PR a `develop` con los tests en verde. Al final se abre `release/2.0.0` → `main` con su tag.
- Commits con la atribución que indique el harness.
- Tests con `pytest` en `tests/research/` y `tests/live/`. En los tests unitarios se pueden usar **fixtures deterministas pequeñas**: OHLC construido a mano para comprobar fórmulas. La prohibición de datos simulados aplica a los resultados de backtest, no a los tests. Las pruebas de integración leen `/home/user/harness/data` y hacen `skip` si no existe.
- Ningún agente ejecuta backtests sobre 2022 o fechas posteriores fuera de `run.py`, que registra el trial **antes** de calcular.
- Dependencias nuevas permitidas (PyPI): `pyarrow`, `scipy`, `statsmodels` (opcional) y `responses` (mock HTTP en tests). Se fijan las versiones en `requirements-research.txt`.

### 6.2 Tareas

| ID | Rama | Archivos | Depende de | Tests requeridos (pytest) |
|---|---|---|---|---|
| H0 | `hotfix/1.1.1-disable-1m-live` | `apps/executor/profiles.py`, `run_*.sh`, `config` | — | Arrancar sin flag deja `dry_run`; los perfiles de 1m rechazan el modo live |
| F01 | `fix/closed-candles` | `apps/executor/strategies/*.py`, `core/binance_websocket.py`, `core/binance_client.py` (`closed_only`) | — | Una vela con `closeTime ≥ now` nunca se usa; con WS `x=false` no hay señal |
| F02 | `fix/legacy-backtester-no-mock` | `apps/analytics/backtester.py` | — | Un fallo de descarga lanza excepción; ya no existe `_generate_mock_data` |
| F03 | `fix/spot-stop-cancel-replace` | `apps/executor/multi_symbol_engine.py`, `core/binance_client.py` | F01 | Con `responses`: la cadena cancelReplace y STOP_ON_FAILURE; si falla, reintenta y alerta; la posición nunca queda sin stop más de X segundos en la simulación |
| R00 | `feature/research-scaffold` | `apps/research/__init__.py`, `config.py`, `config/research.yml`, `requirements-research.txt`, `validation/trials_log.py` | — | Log append-only: el hash encadenado detecta ediciones; `BudgetExceeded` salta al superar la cuota; los 8 ensayos del debate quedan precargados |
| R01 | `feature/research-data-loader` | `data/loader.py`, `data/manifest.py` | R00 | DataError si falta un archivo o un rango; filtro de volume==0; BNB funding → DataError; huecos como NaN; funding en fracción (BTC con mediana ≈ 1e-4) |
| R02 | `feature/research-costs` | `engine/costs.py`, `engine/fills.py` | R00 | Comisión exacta; tramos de slippage; funding con el signo correcto (largo paga si F > 0) y la posición τ⁻; stop gap-aware frente al peor de la barra; fill en open t+1 |
| R03 | `feature/research-stats` | `validation/stats.py`, `validation/pbo.py` | R00 | PSR/DSR contra valores de referencia; E[max Z] ≈ 1.57 (N=10), 2.15 (36), 2.53 (100); el bootstrap reproduce la media; PBO ≈ 0.5 con configuraciones de ruido puro y ≈ 0 con una dominante |
| R04 | `feature/research-features` | `features/*.py` | R01 | **Test de causalidad**: truncar en t no cambia el valor en t; ATR de Wilder frente a un cálculo a mano; Donchian sobre cierres; celdas de régimen ex-ante |
| R05 | `feature/research-sizing` | `portfolio/sizing.py`, `portfolio/risk.py`, `engine/liquidation.py` | R04 | Discretización en cuartos; topes en orden; bruto largo ≤ 1; Σ_s con suelo de ρ; banda; LP aislado (L=2 → ≈ -50%); `liq_ok` con la peor mecha causal; kill-switch simulado |
| R06 | `feature/research-portfolio-engine` | `engine/portfolio_bt.py` | R02, R05 | Contabilidad: equity = Σ P&L − costes; retraso de 1 barra; funding solo en perps; caso trivial con E=1 en spot igual a B&H menos costes |
| R07 | `feature/research-event-engine` | `engine/event_bt.py` | R02, R05 | Si stop y TP caen en la misma barra, cuenta el stop; trailing solo a favor; merge_asof de la vela 1d cerrada |
| R08 | `feature/research-trend` | `strategies/base.py`, `strategies/trend.py` | R04 | DON: entrada, trailing y salida en una serie hecha a mano; TSM; MIX; espejo SHORT con veto de funding; señal invariante al truncar |
| R09 | `feature/research-overlays` | `strategies/overlays.py` | R04 | REGIME m ∈ (0,1]; FVETO con BNB excluido; nunca aumentan la exposición |
| R10 | `feature/research-breakout4h` | `strategies/breakout4h.py` | R04, R07 | Reglas B1-B5; régimen con la vela diaria cerrada |
| R11 | `feature/research-carry` | `strategies/carry.py` | R01, R02 | Alineación con los settlements de 4h; 4 patas de coste; drift del basis; sin BNB |
| R12 | `feature/research-pullback-shock` | `strategies/pullback.py`, `strategies/shock.py` | R04, R07 | Timeout de 24h; z sobre una ventana rolling; filtro sistémico de BTC |
| R13 | `feature/research-benchmarks` | `strategies/benchmarks.py` | R06, R07 | La permutación conserva duraciones y pesos; semillas reproducibles; la vol igualada se cumple |
| R14 | `feature/research-walkforward` | `validation/walkforward.py`, `validation/holdout.py`, `validation/gate.py` | R03, R06 | 17 folds sin solape; selección por fold solo con el entrenamiento; HoldoutLock abre una vez; gate A/B/C sobre resultados de juguete |
| R15 | `feature/research-adaptability` | `validation/adaptability.py` | R03, R04 | EB shrinkage (B → 1 cuando se → ∞); Q20 ponderado; N_eff |
| R16 | `feature/research-reports` | `reports/report.py`, `run.py` | R14, R15 | El informe incluye por año, símbolo y régimen, la advertencia de supervivencia, el aviso de funding no verificado y el commit de los datos |
| L01 | `feature/futures-client` | `core/binance_futures_client.py`, `core/secrets.py` | — | Con `responses`: firma HMAC; idempotencia de margin type; `new_stop_market_algo` envía reduceOnly y MARK_PRICE al endpoint algoOrder; el error -4120 se reconoce |
| L02 | `feature/live-reconciliation` | `apps/live/reconciliation.py` | L01, F03 | Posición sin stop → coloca el stop; stop huérfano → lo cancela; divergencia → alerta |
| L03 | `feature/live-kill-switch` | `apps/live/kill_switch.py`, `config/risk_limits.yml` | — | -2% bloquea entradas; -4% cierra las posiciones con L > 1 y bloquea spot; DD de 15% → mitad de riesgo; 25% → parada; sin config del usuario → no arranca en live |
| L04 | `feature/live-portfolio-executor` | `apps/live/portfolio_executor.py` | R08, R05, L01, L02, L03 | Dry-run de punta a punta con un exchange mock: redondeo a filtros, minNotional, IDs deterministas, stop inmediatamente tras el fill y cierre si falla |
| L05 | `feature/secrets-and-connection-check` | `.env.example`, `.gitignore`, `scripts/check_connection.py`, `scripts/fetch_official_audit_data.py` | L01 | Ningún secreto en el repo (test que busca patrones de clave); `check_connection` solo usa endpoints de lectura |
| L06 | `feature/live-recorders` (F4) | `apps/live/recorders.py` | L01 | Reconexión y rotación de archivos |

**Paralelismo:**
- Ola 1: H0, F01, F02, R00, R03, L01 y L03.
- Ola 2: R01, R02, F03 y L05.
- Ola 3: R04 y R05.
- Ola 4: R06 y R07.
- Ola 5: R08 a R13, en paralelo.
- Ola 6: R14, R15 y L02.
- Ola 7: R16 y L04.

### 6.3 Secuencia de experimentos (después del código, vía `run.py`)

| Experimento | Contenido | Revisión |
|---|---|---|
| E0 | Auditoría de datos (cobertura, BNB, intervalos de funding, volume==0) | Informe |
| E1 | Benchmarks | — |
| E2 | TREND T1-T5: WF en futuros y en spot (9 monedas comunes), comparación spot frente a perp y **spot 2017-2020 congelado** | Revisión de las 5 perspectivas |
| E3 | Overlays REGIME y FVETO sobre T3 o la TREND ganadora | — |
| E4 | SHORT | — |
| E5 | BRK4H | — |
| E6 | CARRY | Informe "no verificado" |
| E7 | PULLBACK y SHOCK | — |
| E8 | SELECTOR frente a paridad | — |
| E9 | Holdout (una vez, solo los finalistas) | — |
| E10 | Informe final | — |

En cada revisión, agentes con las cinco perspectivas leen el informe y votan si se continúa. **No pueden pedir variantes fuera de la cuota.**

### 6.4 Fases operativas

| Fase | Contenido |
|---|---|
| F0 | Harness completo y E0-E2 |
| F1 | Núcleo aceptado (A o B) en spot demo, durante ≥ 4 semanas |
| F2 | Cliente /fapi en testnet: pata corta si pasó, y largos de símbolos sin spot |
| F3 | A/B de overlays y 4h en paper |
| F4 | Carry, shock y recolectores en paper |

---

## 7. Gestión de riesgo innegociable en operación real

1. **Bot de 1m apagado en real** y velas no cerradas corregidas antes de reutilizar cualquier código.
2. **Ninguna estrategia va a real sin gate** (A, o B más ≥ 3 meses de paper) y sin ≥ 4 semanas de demo o testnet sin incidencias de ejecución, con desviación entre fills y backtest dentro de 2σ. Después se arranca con capital pequeño y se escala de forma gradual.
3. **Exposición:**
   - bruto largo ≤ 1x;
   - bruto corto ≤ 0.5x;
   - tope por moneda de 20% en altcoins y 35% en BTC/ETH;
   - suma de altcoins ≤ 60%, tratadas como un solo cluster (ρ > 0.8);
   - límite de beta agregada a BTC ≤ 1;
   - riesgo por trade ≤ 0.5% del NAV (0.25% en altcoins y en motores tácticos);
   - **nunca promediar a la baja**;
   - Kelly solo como techo: vol de cartera ≤ 0.5·SR_aj (§1.4).
4. **Futuros:**
   - modo one-way y margen **aislado**;
   - L = 1 en altcoins y ≤ 1.5x efectivo en BTC/ETH;
   - `dist_liq ≥ max(3·dist_stop, peor mecha histórica del símbolo)` comprobado con `leverageBracket` antes de cada orden;
   - stop de catástrofe **STOP_MARKET reduceOnly con workingType=MARK_PRICE vía `/fapi/v1/algoOrder`**, colocado al entrar. Si no se puede colocar, se cierra la posición.
5. **Spot:** stop de catástrofe STOP_LOSS en el exchange. Se mueve con cancelReplace STOP_ON_FAILURE o con reintentos y alerta.
6. **Kill-switch** (los valores los fija el usuario en `config/risk_limits.yml`; propuesta: -2%, -4%, 15% y 25%):
   - pérdida diaria ≤ -2%: sin entradas nuevas;
   - pérdida diaria ≤ -4%: cerrar las posiciones con L > 1 y los cortos, bloquear todo y alertar;
   - DD > 15%: riesgo a la mitad;
   - DD > 25%: parada total y revisión humana.
   - Los umbrales no se optimizan. Se implementan y se prueban antes de operar en real.
7. **Reconciliación** al arrancar y cada 5 minutos entre el estado local y las posiciones y órdenes del exchange. Alertas (Telegram o email) ante fallos de orden, desconexión, kill-switch o divergencias. Heartbeat.
8. **Operativa:**
   - dry-run por defecto y flag explícito para real;
   - IDs de orden idempotentes;
   - respeto de los rate limits leyendo las cabeceras `X-MBX-USED-WEIGHT`;
   - universo solo líquido (tramos A-C) y sin operar en las 2 semanas siguientes a un listado.
9. **Claves:**
   - sin permiso de retiro y con whitelist de IP;
   - separadas para spot demo, futures testnet y producción;
   - en variables de entorno de la máquina o en un `.env` ignorado por git. **Nunca en git, aunque el repo sea privado**: un repo privado no protege de forks, de colaboradores, de copias en CI ni de filtraciones. Si alguna vez se suben por error, se rotan.
   - Tope de capital depositado en el exchange.
10. **Riesgos no modelables que se declaran:** ADL, caídas de la API en los crashes, cambios del cap o del intervalo de funding, delistings y custodia en Binance.

---

## 8. Preguntas abiertas para el usuario (deduplicadas y en orden de prioridad)

1. **Capital y jurisdicción.**
   - ¿Cuántos USDT piensas destinar en total, y cuántos a spot y a futuros?
   - ¿Cuánto aceptas tener depositado en Binance?
   - ¿En qué país está la cuenta y tiene acceso a futuros USDT-M?
   - ¿En qué nivel VIP estás y pagas comisiones con BNB?
   - El capital decide cuántas monedas caben por encima del minNotional: ~5 USDT en spot y ~100 USDT en el perp de BTCUSDT [VERIFICAR con exchangeInfo].
2. **Límites de riesgo.**
   - ¿Confirmas la pérdida diaria de -2% (bloquear entradas) y -4% (cerrar lo apalancado)?
   - ¿Y el DD de 15% (mitad de riesgo) y 25% (parada)? ¿O prefieres otros valores?
   - ¿Riesgo por trade ≤ 0.5%, L ≤ 1x en altcoins y ≤ 1.5x en BTC/ETH?
   - No se optimizarán.
3. **Si nada pasa el gate**, ¿aceptas quedarte en cash o en B&H/DCA de BTC con tamaño acotado, y aceptas el gate en dos niveles sabiendo que lo más probable es "paper prolongado"?
4. **Diseño de mercado.** ¿Aceptas que los largos vayan en spot y los futuros se usen solo para cortos condicionados (BTC < SMA200), símbolos sin spot y, más adelante, carry? ¿Quieres operar en corto?
5. **Claves y entorno.**
   - ¿Prefieres configurar tú las claves en variables de entorno de la máquina (recomendado; nombres en `.env.example`) o pasármelas para hacer las pruebas de conexión?
   - En cualquier caso: claves de **Spot Demo** y **Futures Testnet**, sin permiso de retiro y con whitelist de IP.
   - ¿Desde qué máquina o IP correrá el bot 24/7, y qué canal de alertas prefieres (Telegram o email)?
6. **Datos de auditoría** (este contenedor recibe 403 de Binance). ¿Puedes ejecutar en tu máquina `scripts/fetch_official_audit_data.py`? Descarga lo siguiente:
   - `/fapi/v1/fundingRate` y `/fapi/v1/fundingInfo` (sobre todo de BNB, BTC y SOL);
   - `markPriceKlines` 1d de los 18 perps;
   - `exchangeInfo` (minNotional);
   - `commissionRate`.
   - Y, si es posible, el **CSV histórico de Fear & Greed** de alternative.me.
7. **Carry.** ¿Quieres que exista aunque hoy esté apagado? Exige saldo en spot y en futuros a la vez y transferencias entre cuentas. ¿Qué rendimiento te da hoy tener los USDT parados (Earn)? Es el coste de oportunidad que fija su umbral.
8. **Presupuesto de pruebas.** ¿Aceptas un máximo de 40 configuraciones probadas en todo el proyecto? Implica no explorar la mayoría de las ideas de sentimiento e intradía.
9. **Git.** Confirma que el repo remoto es privado. Aun así, las claves no se suben, por los motivos de §7.9.
