# Informe final (E10): investigación de estrategias spot + futuros USDT-M

Generado el 2026-10-16 en la rama `feature/experiments`. Especificación: `docs/research/PLAN.md`.

Todas las cifras están copiadas de los informes ya commiteados (`E0/`, `E1/`, `E2/`, `E5/`, `E6/`, `verdicts.json`) o de los diagnósticos de solo lectura (`diagnostics/`, scripts en `scripts/research_diag/`). No se ha calculado nada a mano para este informe. Las cuentas de minNotional de la §7 son aritmética sobre los límites del plan, no resultados de backtest, y van marcadas como estimaciones.

## 0. Conclusión en una línea

**Ninguna estrategia pasa el gate §5.6. Las cinco combinaciones motor-mercado están en nivel C.** No hay finalistas, así que **el holdout (E9) no se ha abierto**. Por §5.6 la recomendación es cash, o B&H/DCA de BTC con tamaño acotado, y la decisión es del usuario. El gate no se relaja. La operación en testnet/demo y con 100 USD reales se plantea **solo como validación de la ejecución**, no como apuesta a un edge.

## 1. Protocolo y presupuesto de ensayos

- OOS: walk-forward anclado de 17 folds trimestrales, de 2022-01-01 a 2026-03-09 (1529 días; CARRY 1528). La selección por fold usa solo el entrenamiento.
- IC95 del Sharpe: bootstrap estacionario con bloque medio de 20 días.
- TrialsLog (`data/trials/trials.jsonl`): 54 registros (21 trials y 33 registros de métricas). SHA-256 `1b83570a487c4caf…`, sin cambios en E9/E10. En esta fase no se ha ejecutado ningún trial.

| familia | trials usados | cuota | estado |
|---|---|---|---|
| DEBATE (exploratorios precargados, sin métricas) | 8 | 8 | cerrada |
| TREND T1-T5 (E2) | 5 | 5 | agotada, nivel C |
| E3 REGIME | 0 | 3 | cerrada por el panel (2/5), cuota conservada |
| E3 FVETO | 0 | 3 | cerrada por el panel (1/5), aplazada hasta verificar el funding |
| E4 SHORT | 0 | 2 | cerrada por el panel (2/5), cuota conservada |
| E5 BRK4H B1-B5 | 5 | 5 | agotada, nivel C |
| E6 CARRY K1-K3 | 3 | 3 | agotada, nivel C, solo paper |
| E7 PULLBACK / SHOCK | 0 | — | cerradas por el panel (0/5 y 2/5) |
| E8 SELECTOR | 0 | — | cerrada: necesita ≥ 2 motores en A/B y no hay ninguno |
| **N total** | **21** | ≤ 40 | quedan 19 de presupuesto global |

**Advertencias que afectan a todos los resultados:**
- **Sesgo de supervivencia.** Todos los símbolos del universo siguen listados en 2026; faltan LUNA, FTT, SRM, etc. Los resultados con alts son optimistas en una magnitud desconocida.
- **Funding no verificado** contra `/fapi/v1/fundingRate` ni `/fapi/v1/fundingInfo`. El funding local se muestreó a las 00/08/16 UTC, así que los intervalos de 4h/1h quedan infracontados. El funding de BNBUSDT está excluido.
- **Costes** según §5.4 (spot 0.10% por lado; futuros 0.05% taker; slippage por tramos). Están sin verificar en vivo.

## 2. Tabla de todas las estrategias probadas (OOS walk-forward)

### 2.1 Resultados de familia (selección por fold) y referencia T3

| motor | mercado | selección | CAGR | MaxDD | Sharpe OOS [IC95] | PSR(0) | DSR | PBO | entradas aleatorias (pctl) | coste ×2 Sharpe | A_k | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TREND T1-T5 (E2) | spot | T1 en 17/17 | 3.65% | 16.21% | 0.436 [-0.826, 1.698] | 0.814 | 0.581 (N=13) | 0.375 | 92 | 0.329 | -0.905 | **C** |
| TREND T1-T5 (E2) | perp (L=1) | T2 f0-7, T4 f8-16 | 3.98% | 19.08% | 0.424 [-0.872, 1.658] | 0.807 | 0.543 (N=13) | 0.137 | 97 | 0.144 | -0.388 | **C** |
| T3 MIX sola (referencia, sin trial nuevo) | spot | — | 3.62% | 18.22% | 0.411 [-0.876, 1.673] | 0.800 | 0.372 (N=21) | — | — | — | -1.291 | (familia C) |
| T3 MIX sola (referencia, sin trial nuevo) | perp | — | 3.31% | 17.59% | 0.377 [-0.869, 1.598] | 0.780 | 0.345 (N=21) | — | — | — | -0.342 | (familia C) |
| BRK4H B1-B5 (E5) | spot | B5/B2/B3 | 2.22% | 8.87% | 0.368 [-0.600, 1.169] | 0.780 | 0.336 (N=21, V final)¹ | 0.088 | 99 | -0.061 | -0.866 | **C** |
| BRK4H B1-B5 (E5) | perp | B3/B1/B4 | 1.76% | 16.44% | 0.206 [-0.596, 0.941] | 0.665 | 0.225 (N=21) | 0.332 | 94 | -0.129 | -0.206 | **C** |
| CARRY K1-K3 (E6) | perp (paper) | K3 en 14/17 | 0.16% | 2.27% | 0.145 [-0.534, 3.600] | 0.603 | 0.221 (N=21, V final)² | 1.000 | 78 | — | +1.647 (3 celdas) | **C**, solo paper |

¹ El informe commiteado `E5/brk4h_spot.md` dice DSR 0.241 porque se calculó con V[SR] = 3.68e-4, cuando el log tenía menos métricas. **El valor válido es 0.336**, calculado con el log final (N=21, V[SR]=2.42e-4/día), igual en los dos lados de la regla pre-registrada 2.
² El informe `E6/` dice 0.210 (V[SR] = 2.58e-4). El valor con V final es 0.221. La conclusión no cambia en ningún caso.

Los DSR de TREND con N=13 son los de su informe (E2). Con N=21 solo se recalculó T3 (0.372 en spot y 0.345 en perp). Benchmarks (E1): B&H BTC spot con Sharpe 0.440 [-0.538, 1.486] y MaxDD 66.93%; cesta EW con Sharpe 0.173 y MaxDD 77.24%.

**Todos los IC95 del Sharpe OOS incluyen el 0**, y el mejor DSR (0.372) está muy lejos del 0.95 que exige el nivel A. Los valores de t van de 0.30 (CARRY) a 0.89 (TREND spot).

### 2.2 Configuraciones individuales (OOS, solo informativo, no seleccionables a posteriori)

| config | spot Sharpe / MaxDD | perp Sharpe / MaxDD |
|---|---|---|
| T1 DON | 0.436 / 16.21% | 0.391 / 15.85% |
| T2 TSM | 0.034 / 19.08% | -0.019 / 18.18% |
| T3 MIX (primaria) | 0.411 / 18.22% | 0.377 / 17.59% |
| T4 MIX σ 20% | 0.551 / 19.92% | 0.564 / 19.08% |
| T5 MIX b 0.10 | 0.434 / 17.71% | 0.420 / 17.69% |
| B1 | 0.252 / 10.55% | 0.142 / 14.87% |
| B2 | -0.205 / 11.40% | 0.013 / 16.52% |
| B3 | 0.674 / 9.71% | 0.338 / 14.99% |
| B4 | -0.323 / 9.99% | 0.074 / 16.92% |
| B5 | 0.357 / 6.81% | 0.042 / 14.73% |
| K1 / K2 / K3 (perp, paper) | — | 0.563 / 2.27%; 0.251 / 2.44%; 1.053 / 0.57% |

### 2.3 Estabilidad temporal (regla 4 pre-registrada)

| serie | folds 0-7 (2022-2023) Sharpe / MaxDD | folds 8-16 (2024-2026Q1) Sharpe / MaxDD |
|---|---|---|
| T3 spot | 0.981 / 12.2% | **-0.054** / 18.2% |
| T3 perp | 0.919 / 12.0% | **-0.073** / 17.6% |
| BRK4H spot | -0.091 / 6.7% | 0.596 / 8.9% |
| BRK4H perp | 0.015 / 15.3% | 0.343 / 11.3% |

TREND por año (spot, familia): 2022 -8.03%, 2023 +26.85%, 2024 +12.51%, 2025 -8.69%, 2026 (hasta el 03-09) -3.03%. La ventaja de tendencia se concentra en 2022-23 y en el tramo reciente es plana o negativa.

### 2.4 Por qué cada motor falla el nivel B (de `verdicts.json`)

| motor:mercado | criterios B que fallan | criterios A que fallan |
|---|---|---|
| TREND:spot | pbo, random_entries, psr, adaptability | dsr, pbo, random_entries, vs_bh, no_catastrophe, holdout, significance |
| TREND:futures | frozen_spot (T4 SR -0.196 en 2017-2020), psr, adaptability | dsr, vs_bh, no_catastrophe, cost_stress, frozen_spot, holdout, significance |
| BRK4H:spot | cost_stress, psr, adaptability | dsr, vs_bh, no_catastrophe (2023-24 dSR -2.19 vs BTC), cost_stress, holdout, significance |
| BRK4H:futures | pbo, random_entries, cost_stress, psr, adaptability | dsr, pbo, random_entries, vs_bh, no_catastrophe, cost_stress, holdout, significance |
| CARRY:futures | pbo, random_entries, psr | dsr, pbo, random_entries, vs_bh, no_catastrophe, cost_stress, delay_stress, holdout, significance |

Otros hallazgos de E5:
- BRK4H **no supera a T3 en DSR** en ningún mercado (spot 0.336 frente a 0.372; perp 0.225 frente a 0.345).
- Ablaciones: el filtro ADX no aporta (en spot y en perp, quitarlo fue mejor). El filtro de funding solo aporta en spot por la regla pre-registrada (p 0.030; tras Holm 0.091, no significativo), y además depende de un funding no verificado. El filtro de volumen no aporta.
- Stress de stop al peor precio de la barra: dispara el kill-switch (DD ≥ 20%) en 2/5 configuraciones de spot y en 5/5 de perp.
- CARRY: con funding ×0.5 el Sharpe es -0.274 y con ×2 es 0.950.

## 3. Holdout (E9)

**No se ha abierto.** La regla era abrirlo una sola vez con `HoldoutLock`, y solo para los finalistas con mayoría del panel (≥ 3/5). Ninguna de las 5 perspectivas propuso finalistas (0/5 para todos los motores). `data/trials/holdout.lock` no existe, así que la apertura sigue disponible para un ciclo futuro con candidatos en nivel A o B. Para TREND, el holdout ya estaba parcialmente contaminado (PLAN §1.4).

| motor | votos a finalista | holdout |
|---|---|---|
| TREND spot / perp | 0/5 | no abierto |
| BRK4H spot / perp | 0/5 | no abierto |
| CARRY | 0/5 | no abierto |

## 4. Votos del panel (revisión final)

| perspectiva | finalistas | más adaptable spot | más adaptable futuros | ¿abrir holdout? | recomendación en vivo (resumen) |
|---|---|---|---|---|---|
| Pesimista | ninguno | ninguna (todas las A_k de spot < 0) | ninguna (CARRY +1.647 sin valor: 3 celdas, PBO 1.0) | no | Cash o DCA de BTC acotado. Testnet 4 semanas como prueba de infraestructura (fills, stops F03, velas cerradas F01, kill-switch, reconexión). 100 USD solo BTC/ETH sin apalancamiento. Futuros solo en testnet. |
| Optimista | ninguno | ninguna | ninguna | no | T3 congelada en testnet con la capa D completa. 100 USD solo BTC/ETH con órdenes mínimas, tope de pérdida de 20 USD y apagado a -5 USD en el día. Verificar el funding en paralelo. |
| Realista | ninguno | ninguna | ninguna | no | Executor diario en testnet con T3 en sombra. Medir los deltas descartados por minNotional. 100 USD: DCA de BTC acotado a través del bot, o T3 restringida a BTC/ETH. No usar 10 monedas con 100 USD. |
| Analítico | ninguno | ninguna | ninguna | no | Testnet solo para validar la ejecución (sin potencia estadística). 100 USD en BTC/ETH con órdenes de 5-10 USD, sin apalancamiento. No escalar sin un nivel B en un ciclo nuevo y ≥ 3 meses de paper. |
| Matemático | ninguno | ninguna | ninguna | no | Kelly ≤ 0 en el límite inferior del IC, así que la fracción defendible es 0. Los 100 USD se tratan como coste de ingeniería. 4 semanas de demo dan t ≈ 0.11 y no sirven para promover ni descartar nada. |

**Resultado: 0/5 votos a finalista para todos los motores. Hay unanimidad en no abrir el holdout, en que no existe un motor "más adaptable" y en que la operación real es solo de ejecución.**

Preocupaciones comunes (citadas por ≥ 3 perspectivas):
1. Decaimiento de T3 en los folds 8-16 (Sharpe -0.05 en spot y -0.07 en perp).
2. Funding no verificado y sesgo de supervivencia.
3. Fragilidad de BRK4H ante costes ×2 y riesgo de cola (stress de peor barra).
4. DSR de los informes calculados con V[SR] antiguos. La versión válida es la de la tabla 2.1.
5. Los A_k no son comparables entre motores. TREND usa celdas moneda × régimen con contribuciones aproximadas, cuya suma da Sharpe 0.61 frente a 0.41 real. BRK4H y CARRY usan 3-6 celdas de cartera. La A_k de T3 viene de un script de diagnóstico (`scripts/research_diag/t3_adaptability.py`), no de `run.py`.
6. 4 semanas de demo no tienen potencia estadística. Su P&L no debe usarse para decidir.

## 5. Estrategia más adaptable

- **Spot: ninguna.** PLAN §3.3.5 dice que la más adaptable es la de mayor A_k entre las que pasan el gate, y ninguna lo pasa. Como dato informativo, todas las A_k de spot son negativas: BRK4H -0.866, TREND -0.905 y T3 sola -1.291.
- **Futuros: ninguna.** El único A_k positivo es el de CARRY (+1.647), que sale de 3 celdas, con PBO 1.000, funding sin verificar y nivel C. BRK4H perp tiene -0.206 y TREND perp -0.388.

## 6. Configuración recomendada para `apps/live`

**No se crea `config/live_strategy.yml`.** Ese archivo solo se genera si hay una estrategia aceptada (A) o candidata a paper (B), y no la hay. CARRY tiene destino "solo paper" por excepción del panel, pero condicionado a verificar antes el funding. Además, el executor actual no implementa CARRY. Crear el archivo ahora daría la impresión falsa de que existe una estrategia aprobada.

Configuración operativa que se recomienda, **solo para validar la ejecución** (no es una asignación de capital a un edge):

| parámetro | valor |
|---|---|
| motor | T3 (TREND-03, especificación congelada, sin retoques), como referencia en sombra/testnet. BRK4H no supera a T3 y CARRY no está implementado en el executor. |
| pesos | 100% T3 en testnet. Con capital real: **0% en estrategia**; solo órdenes mínimas de validación o DCA de BTC acotado. |
| `TRADING_MODE` | `dry_run` por defecto; `spot_demo` / `futures_testnet` en la fase (a). `live` solo en la fase (b) con `LIVE_TRADING_CONFIRM=I_UNDERSTAND`. |
| kill-switch (`config/risk_limits.yml`, confirmado por el usuario) | -2% diario: sin entradas nuevas; **-5% diario**: cerrar lo apalancado y bloquear; DD 10%: mitad de riesgo; **DD 20%: parada total** y revisión humana. |
| exposición | bruto largo ≤ 1x; bruto corto ≤ 0.5x (sin motor de cortos activo); BTC/ETH ≤ 35% por moneda; alts ≤ 20% por moneda y ≤ 60% en total; riesgo por trade ≤ 0.5% (BTC/ETH) y ≤ 0.25% (alts). |
| apalancamiento | margen aislado, one-way. Alts 1x y BTC/ETH ≤ 1.5x efectivo (el executor solo acepta `futures_leverage=1`). El techo de 3x del usuario nunca se usa. |
| capital | tope de 10 000 USDT depositados (`max_capital_usdt`). Fase (b): 100 USD. |
| universo | testnet: universo spot del plan (10 monedas). Real con 100 USD: **solo BTCUSDT y ETHUSDT** (ver la §7(b)). |

Pendiente de código, que no se ha hecho en esta fase: `ExecutorConfig.spot_symbols` toma por defecto el universo de 10 monedas y la CLI de `apps/live/portfolio_executor.py` no permite restringirlo. Para la fase (b) hace falta un cambio pequeño y revisado (por ejemplo, un argumento `--symbols`) en su propia rama `feature/`, con tests.

## 7. Plan concreto para el usuario

### (a) Testnet / demo: 4 semanas, validación de INFRAESTRUCTURA

1. Claves de **Spot Demo** (demo.binance.com) y de **Futures Testnet**, sin permiso de retiro y con whitelist de IP, exportadas como variables de entorno (ver (d)).
2. `python scripts/check_connection.py` debe salir con código 0. Solo usa endpoints GET.
3. `TRADING_MODE=spot_demo python -m apps.live.portfolio_executor --engine T3` (programado a las 00:05 UTC; `--once` para una sola ejecución). Después, una ejecución paralela con `TRADING_MODE=futures_testnet`.
4. Qué se mide cada día (desde el journal JSONL y el estado):
   - fills frente al precio del modelo (open t+1): slippage real en pb frente a los tramos de §5.4;
   - comisiones reales frente a 0.10% spot y 0.05% taker en futuros;
   - deltas descartados por MIN_NOTIONAL/LOT_SIZE (número y valor nocional);
   - stop de catástrofe presente en el exchange tras cada fill. Una posición sin stop cuenta como incidencia grave;
   - reconciliación al arrancar y cada 5 minutos sin divergencias;
   - kill-switch: un disparo forzado en testnet (-2% / -5% / 20%) debe bloquear y cerrar como se espera;
   - recuperación tras reinicio: no hay órdenes duplicadas (IDs deterministas `{fecha}-{motor}-{símbolo}-{seq}`);
   - solo se usan velas cerradas (`closeTime < serverTime`).
5. Criterio de éxito: **4 semanas con cero incidencias de ejecución** y desviación fill-modelo dentro de 2σ. **El P&L de testnet no es criterio**: con Sharpe ~0.4, 4 semanas dan t ≈ 0.11.
6. En paralelo, sin operar: descargar `/fapi/v1/fundingRate`, `/fapi/v1/fundingInfo` y `exchangeInfo` (spot y futuros) para verificar el funding y los minNotional reales (`scripts/fetch_official_audit_data.py`).

### (b) 100 USD reales en spot: validación de EJECUCIÓN

- **Monedas que caben.** Con minNotional spot ~5 USD [VERIFICAR con exchangeInfo]: **solo BTCUSDT y ETHUSDT** (BTC prioritario, ETH opcional). Esto es una estimación aritmética, no un resultado. T3 discretiza la exposición en pasos de 0.25. Con 10 monedas y ~10% de NAV cada una, un paso son ~2.5 USD, por debajo del mínimo, así que el executor descartaría casi todos los deltas. Para que un paso supere 5 USD hace falta un NAV ≥ ~200 USD (0.025·NAV ≥ 5). Con vol targeting, topes y LOT_SIZE, la cifra realista es del orden de 500-1000 USD, también pendiente de verificar.
- Órdenes de 10-20 USD como mínimo, para pasar minNotional con margen tras el redondeo. **Sin apalancamiento, sin futuros reales**: el minNotional del perp BTCUSDT es ~100 USD, así que con 100 USD sería toda la cuenta en una posición.
- Opciones, las dos dentro de §5.6 nivel C (la elección es del usuario):
  1. **DCA/B&H de BTC acotado a través del propio bot**: valida órdenes, comisiones y contabilidad sin añadir riesgo de estrategia.
  2. **T3 restringida a BTC/ETH**, aceptando que es una prueba de ejecución y que no reproduce el backtest de 10 monedas.
- Límites: kill-switch de `risk_limits.yml`, es decir, -5% diario (≈ 5 USD) y DD 20% (≈ 20 USD) con parada y revisión humana. Los 100 USD se tratan como coste de ingeniería, no como inversión.
- `TRADING_MODE=live` exige `LIVE_TRADING_CONFIRM=I_UNDERSTAND` y `user_confirmed: true` en `config/risk_limits.yml`. Hay que usar claves de producción separadas y con tope de depósito.

### (c) Criterios de evaluación mensuales: ejecución frente a backtest, **nunca ajustar por P&L**

Cada mes se revisan:
1. Slippage medio y p95 por símbolo frente al modelo de §5.4. Si se supera en > 2σ, se revisa el modelo de costes, **no la estrategia**.
2. Comisión efectiva frente a la modelada (0.10% spot; 0.075% con BNB si se confirma).
3. Tracking error entre el P&L en vivo y el P&L en sombra (`dry_run` sobre los mismos datos) dentro de 2σ. Una desviación se explica por fills, redondeo o deltas descartados, nunca por "mala racha".
4. Incidencias: posición sin stop, órdenes duplicadas, divergencias de reconciliación, kill-switch inesperado, velas no cerradas. **Objetivo: 0**.
5. Deltas descartados por minNotional (porcentaje del nocional objetivo).

Reglas que no se negocian:
- **No se cambia ningún parámetro por el P&L del mes.** Cualquier variante nueva va como familia pre-registrada, se vota en el panel y se ejecuta vía `python -m apps.research.run` (TrialsLog, N ≤ 40, quedan 19).
- **No se escala más allá de 100 USD** hasta que un motor llegue al nivel B en un ciclo nuevo (y después ≥ 3 meses de paper con tracking error dentro de 2σ) o al nivel A (y después ≥ 4 semanas de demo sin incidencias).
- Antes de cualquier ciclo nuevo: verificar el funding, corregir el sesgo de supervivencia (incluir delistados) y correr el spot 2017-2020 congelado para los motores que falten.
- El holdout se reserva para ese ciclo, con una sola apertura.

### (d) Cómo activar

1. Variables de entorno (nombres en `.env.example`, **nunca valores en git**). Se exportan en la máquina o en un `.env` ignorado (`set -a; source .env; set +a`):
   - spot demo: `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_API_SECRET` (opcional `BINANCE_SPOT_BASE_URL`, por defecto `https://demo-api.binance.com`);
   - futures testnet: `BINANCE_FUTURES_TESTNET_API_KEY`, `BINANCE_FUTURES_TESTNET_API_SECRET` (opcional `BINANCE_FUTURES_BASE_URL`, por defecto `https://testnet.binancefuture.com`);
   - producción (solo en la fase (b)): `BINANCE_API_KEY`, `BINANCE_API_SECRET` (y `BINANCE_SECRET` con el mismo valor para el código legado), `LIVE_TRADING_CONFIRM=I_UNDERSTAND`;
   - modo: `TRADING_MODE` ∈ {`dry_run` (por defecto), `spot_demo`, `futures_testnet`, `live`}.
2. Comprobar la conexión: `python scripts/check_connection.py` (o `--only futures`). Es de solo lectura y no imprime secretos.
3. Ejecutar: `TRADING_MODE=dry_run python -m apps.live.portfolio_executor --engine T3 --once`, luego `spot_demo` / `futures_testnet` y, solo al final, `live`.
4. Los límites de riesgo se leen de `config/risk_limits.yml`. Sin un archivo válido y confirmado, el bot no arranca en `live`.
5. El bot de 1m y el `multi_symbol_engine` legado quedan forzados a `dry_run` (`ALLOW_1M_LIVE=false`).

## 8. Archivos de referencia

- `docs/research/PLAN.md` (§3.3, §5.6, §7)
- `docs/research/results/verdicts.json`
- `docs/research/results/E0_E2_summary.md`, `E3_E8_summary.md`, `E3_E8_panel_decisions.md`
- `docs/research/results/E2/`, `E5/`, `E6/`, `diagnostics/`
- `config/risk_limits.yml`, `.env.example`, `scripts/check_connection.py`, `apps/live/portfolio_executor.py`
