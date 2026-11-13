# 03. MetaTrader 5 desde Python: paquete oficial, API de trading, entorno, seguridad y pruebas

Fecha: 2026-11-13.

**Ámbito.** Conector entre el bot (`/home/user/trading-bot`: Python 3.13, pandas 3, numpy 2) y MetaTrader 5 (MT5), para day trading de índices y acciones tecnológicas de EE. UU. mediante CFD.

**Decisiones vigentes del usuario** (`/home/user/harness/daytrade/USER_DECISIONS.md`):
- MT5 nativo y el paquete oficial de Python corren en un **PC Windows propio**.
- Todavía no tiene broker. Por ahora opera **solo en demo**.
- Las órdenes son automáticas, con un gate determinista y kill-switch.
- Apalancamiento máximo: 3x. Drawdown máximo: 20 % total y 5 % diario.

---

## 0. Método, etiquetas y limitaciones

### Fuentes primarias que se usaron

1. **Metadatos de PyPI** del paquete `MetaTrader5`, vía `https://pypi.org/pypi/MetaTrader5/json`: versiones, fechas y wheels publicados.
2. **Inspección del wheel oficial** `metatrader5-5.0.6231-cp313-cp313-win_amd64.whl`.
   - Su SHA-256 es `3a8c8349ce691a4ef05e314afc034ad82f4dbb19415efc7442af5ea075d5e797`, idéntico al que publica PyPI.
   - Se leyó `__init__.py` (constantes y funciones auxiliares) y las cadenas del binario `_core.cp313-win_amd64.pyd`: lista de funciones, firmas en docstring, nombres de campos y mensajes de error.
   - **No se ejecutó nada del wheel.**
   - Para comparar, se inspeccionaron también los wheels 5.0.45, 5.0.4288, 5.0.4424 y 5.0.4682.
3. **Texto oficial de la documentación Python de MQL5.**
   - `mql5.com` y `metatrader5.com` están bloqueados desde este contenedor (403 / ENOTFOUND).
   - El texto oficial se leyó por dos vías: fragmentos de WebSearch y el **espejo literal** que el proyecto `lucas-campagna/mt5linux` copia en sus docstrings (`mt5linux/metatrader5.py`, commit `7460cbc`, 2026-10-27).
   - Las citas "doc oficial" de este informe salen de ese espejo o de los fragmentos, y llevan la URL original.
4. **Repositorios de GitHub clonados**: mt5linux, gmag11/MetaTrader5-Docker-Image, pymt5linux, silicon-metatrader5, brokerclock, pdmt5, aiomql, MetaTrader5-stubs y rpyc.
5. **Foro MQL5, notas de versión de MT5 y webs de brokers y reguladores**, solo a través de los fragmentos de WebSearch.

### Limitaciones

- **El cupo de WebSearch se agotó** durante la investigación: 200 búsquedas por turno, compartidas por todos los agentes.
- Lo que quedó sin confirmar lleva **[VERIFICAR]**. Para cerrarlo hay que permitir `mql5.com`, `metatrader5.com` y las webs de los brokers en la red de la sesión, o hacerlo en otra sesión.

### Etiquetas

| etiqueta | significado |
|---|---|
| **[EVIDENCIA]** | Documento oficial de MetaQuotes o de un regulador, o inspección directa del paquete. |
| **[EVIDENCIA-FORO]** | Varios reportes coherentes de usuarios en el foro oficial MQL5, sin confirmación de MetaQuotes. |
| **[SECUNDARIA]** | Web de broker, prensa o terceros. |
| **[CÓDIGO-3º]** | Lectura del código o README de un proyecto de terceros. |
| **[CÁLCULO]** | Aritmética propia con supuestos explícitos. No es un dato de mercado. |
| **[OPINIÓN]** | Criterio propio. |
| **[VERIFICAR]** | No se pudo confirmar desde este contenedor. |

### Código de ejemplo

- Está en `/home/user/harness/daytrade/research/03_mt5/`:
  - `mt5_gateway.py`: conector de ejemplo.
  - `fake_mt5.py`: módulo `MetaTrader5` falso.
  - `smoke_check.py`: diagnóstico de solo lectura.
  - `test_mt5_gateway.py`: tests.
  - `fetch_official_wheel.sh`: descarga el wheel oficial y verifica su SHA-256.
- **21 tests pasan en Linux** (`python3 -m pytest -q test_mt5_gateway.py`).
- Dos de esos tests comparan las constantes del módulo falso y la tabla de retcodes con las del paquete oficial. El paquete se **parsea con `ast`; nunca se importa**.
- **No se probó contra un terminal real.** En el contenedor no hay Windows ni broker. Probar en demo es obligatorio antes de usarlo.

---

## 1. Resumen ejecutivo

1. **Paquete** [EVIDENCIA]
   - `MetaTrader5` **5.0.6231** (27-sep-2026) es la última versión en PyPI.
   - Solo publica wheels **`win_amd64`**:
     - CPython 3.6 a 3.14.
     - 3.13 desde 5.0.4682 (20-nov-2024).
     - 3.14 desde 5.0.5488 (05-ene-2026).
   - Licencia MIT.
   - **No existe wheel para Linux ni macOS.** El paquete solo funciona en Windows de 64 bits, o en Python para Windows dentro de Wine.
2. **numpy 2** [EVIDENCIA: inspección binaria]
   - Hasta 5.0.4424 (jun-2024), el binario se compiló contra NumPy 1.x: solo importa `numpy.core._multiarray_umath`.
   - Desde 5.0.4682 se compiló con cabeceras NumPy 2: importa `numpy._core` con respaldo a `numpy.core`, y la API C mínima es la de **NumPy 1.20**.
   - El proyecto usa numpy 2.5 y pandas 3, así que **necesita ≥ 5.0.4682**.
   - El metadato `Requires-Dist: numpy>=1.7` está desactualizado.
3. **API** [EVIDENCIA]
   - Tiene 32 funciones **síncronas**, sin callbacks ni eventos (no hay `OnTick` ni `OnTradeTransaction`). Por eso **hay que consultar en bucle** (polling).
   - **No expone**:
     - el horario de sesiones (no hay equivalente a `SymbolInfoSessionTrade`);
     - la apertura de cuentas;
     - el login con OTP o certificado.
4. **Horas** [EVIDENCIA-FORO + SECUNDARIA; la doc oficial se contradice]
   - La doc oficial dice que los tiempos están en UTC. En la práctica, barras, ticks y deals llegan con el **reloj del servidor del broker escrito como epoch**.
   - La convención mayoritaria es "New York close": GMT+2 en invierno y GMT+3 en verano, cambiando con el horario de **EE. UU.** Equivale a hora de Nueva York + 7 h.
   - Consecuencia: la apertura de contado de las 09:30 ET cae **a las 16:30 del servidor todo el año**.
5. **Ejecución** [EVIDENCIA; la doc se contradice en un punto]
   - En símbolos con ejecución "Market", la orden de mercado **no lleva precio** y `deviation` **no limita el deslizamiento**: solo actúa en los modos Instant y Request.
   - `ORDER_FILLING_RETURN` no se admite en órdenes de mercado en modo Market según la referencia de propiedades de órdenes. Otra página de la doc dice lo contrario.
   - Método robusto:
     - elegir el modo de llenado con los bits de `filling_mode`;
     - pasar a la siguiente opción si la respuesta es **10030 (INVALID_FILL)**, porque ese rechazo no ejecuta nada.
6. **Retcodes** [EVIDENCIA]
   - `order_check` devuelve `retcode=0` y `comment='Done'` si la comprobación pasa.
   - `order_send` devuelve **10009 (DONE)** si se ejecutó y **10008 (PLACED)** si quedó colocada una pendiente.
   - **`None` significa que falló la llamada IPC y el estado de la orden es desconocido.** Antes de reenviar hay que reconciliar con posiciones, órdenes y deals.
   - El paquete exporta 40 retcodes (10004–10045). Le falta **10046 (HEDGE_PROHIBITED)**.
7. **Seguridad y kill-switch humano** [EVIDENCIA + EVIDENCIA-FORO]
   - Bloquean las órdenes de Python con 10027:
     - el botón **Algo Trading** del terminal;
     - la opción "Disable algorithmic trading via external Python API".
   - Con la **contraseña de inversor** no se puede operar.
   - Las cuentas con **OTP** fallan en `initialize`/`login` con `"Unsupported authorization mode, OTP or certificate password needed"`.
   - Recomendación: **iniciar sesión a mano en el terminal y que el bot se adjunte sin contraseña.**
8. **Linux/macOS** [EVIDENCIA + CÓDIGO-3º]
   - Las vías posibles son:
     - Wine, con el terminal y un Python para Windows dentro;
     - un puente RPyC (mt5linux y sus forks);
     - una VM o VPS con Windows.
   - Los puentes RPyC usan el modo *classic*. La documentación de RPyC lo declara **"intentionally insecure"**: permite ejecutar código arbitrario en remoto. **El puerto no debe quedar expuesto nunca.**
   - Como el usuario eligió Windows, esto queda como plan B.
9. **Fallos abiertos** [EVIDENCIA-FORO]
   - Hay reportes recientes de `initialize()` → `(-10005, 'IPC timeout')` con el terminal build 6230/6231 y el paquete 5.0.6231, sin solución confirmada.
   - Hace falta un *watchdog* y fijar las versiones probadas en demo.
10. **Apalancamiento regulado** [EVIDENCIA]
    - ESMA, FCA y ASIC limitan a 1:20 los índices mayores (el Nasdaq-100 está en la lista) y a 1:5 las acciones.
    - Los brokers offshore ofrecen más apalancamiento.
    - El tope del usuario, **3x efectivo**, es más estricto. El bot debe aplicarlo calculando el **nocional**, no el margen.
11. **Cuenta de 100 USD** [CÁLCULO]
    - Supuestos: US100 ≈ 28.2 mil (estimación) y 1 USD por punto y lote.
    - Con lote mínimo 0.1 hacen falta ≈ 940 USD de equity para una sola posición dentro de 3x.
    - Con 100 USD solo caben 0.01 lotes (si el broker los permite) o 1 acción CFD.
    - Con una cuenta así, el riesgo por operación casi nunca baja del 0.5 %.
12. **Pruebas sin terminal** [CÓDIGO-3º]
    - El paquete no se instala en un CI Linux.
    - Se prueba con un módulo falso inyectado, que es el patrón de `pdmt5`.
    - Se completa con tests de contrato *opt-in* contra la demo, que es el patrón de mt5linux: `MT5_E2E_ALLOW_ORDER_SEND=1`.

---

## 2. El paquete oficial `MetaTrader5`

### 2.1 Versiones y Python soportado [EVIDENCIA: PyPI JSON]

| versión | fecha de subida | wheels (todos `win_amd64`) | nota |
|---|---|---|---|
| 5.0.36 | 2021-10-23 | cp36–cp310 | versión que fija la imagen Docker de gmag11 |
| 5.0.44 | 2023-02-15 | + cp311 | |
| 5.0.47 | 2024-02-02 | + cp312 | |
| 5.0.4424 | 2024-06-28 | cp36–cp312 | último binario compilado contra NumPy 1.x |
| **5.0.4682** | 2024-11-20 | + **cp313** | primero compilado con cabeceras NumPy 2 |
| 5.0.5200 | 2025-08-01 | cp36–cp313 | versión que fija `mt5-remote` |
| **5.0.5488** | 2026-01-05 | + **cp314** | |
| 5.0.6090 | 2026-08-01 | cp36–cp314 | |
| **5.0.6231** | 2026-09-27 | cp36–cp314 | **última versión**; el foro la empareja con el terminal build 6230 |

- **[Inferencia]** Desde 2024 el número de versión parece seguir al build del terminal (5.0.4200 → build 4200). Hay pistas: el foro empareja el build 6230 con el paquete 5.0.6231, y `version()` devolvió `(500, 4120, '22 Dec 2023')` con el terminal build 4120 (README de gmag11). MetaQuotes no lo documenta.
- El binario contiene el error `"Terminal: Incompatible versions, please install the latest version of Terminal and Python module"`. **Terminal y paquete se deben actualizar juntos.** [EVIDENCIA: cadenas del binario]
- **Solo 64 bits.** No hay wheel `win32`, así que Python de 32 bits no sirve.
- El foro documenta el error `-10003 'IPC initialize failed, MetaTrader 5 x64 not found'` cuando no se encuentra un terminal de 64 bits. [EVIDENCIA + EVIDENCIA-FORO]
- **Recomendación para este proyecto** [OPINIÓN]:
  - Python 3.13 x64 en el PC Windows.
  - `MetaTrader5==5.0.6231` fijado en un `requirements-windows.txt` con el marcador `; sys_platform == "win32"`, como hace `pdmt5` (`metatrader5>=5.0.5735; sys_platform == "win32"`).
  - Subir de versión solo después de probar en demo cada actualización del terminal.

### 2.2 Superficie de la API [EVIDENCIA: docstrings compilados en `_core` 5.0.6231 y doc oficial]

| grupo | función y firma (texto del binario) | devuelve |
|---|---|---|
| sesión | `initialize([path],[server="SERVER"],[login=LOGIN],[password="PASSWORD"])` + `timeout=60000`, `portable=False` (doc) | `True`/`False` |
| | `login(login,[server="SERVER"],[password="PASSWORD"])` + `timeout` | `True`/`False` |
| | `shutdown()`, `version()`, `last_error()` | `None`; `(versión, build, fecha)`; `(código, texto)` |
| estado | `account_info()`, `terminal_info()` | `AccountInfo` / `TerminalInfo` o `None` |
| símbolos | `symbols_total()`, `symbols_get([group="GROUP"])`, `symbol_info(symbol)`, `symbol_info_tick(symbol)`, `symbol_select(symbol,[enable])` | tupla / `SymbolInfo` / `Tick` / `bool` |
| profundidad | `market_book_add/get/release(symbol)` | `BookInfo` |
| datos | `copy_rates_from(symbol, timeframe, date_from, count)`, `copy_rates_from_pos(symbol, timeframe, start_pos, count)`, `copy_rates_range(symbol, timeframe, date_from, date_to)` | array estructurado de numpy (`time, open, high, low, close, tick_volume, spread, real_volume`) |
| | `copy_ticks_from(symbol, date_from, count, flags)`, `copy_ticks_range(symbol, date_from, date_to, flags)` | array de numpy (`time, bid, ask, last, volume, time_msc, flags, volume_real`) |
| trading | `order_calc_margin(action, symbol, volume, price)`, `order_calc_profit(action, symbol, volume, price_open, price_close)` | `float` o `None` |
| | `order_check(request)`, `order_send(request)` | `OrderCheckResult` / `OrderSendResult` o `None` |
| cartera | `orders_total()`, `orders_get([symbol],[ticket],[group])`, `positions_total()`, `positions_get([symbol],[ticket],[group])` | tuplas de `TradeOrder` / `TradePosition` |
| historial | `history_orders_total(date_from, date_to)`, `history_orders_get([date_from, date_to,[group]],[position],[ticket])`, `history_deals_total(...)`, `history_deals_get(...)` | tuplas de `TradeOrder` / `TradeDeal` |

Puntos que importan para el diseño:

- **No hay** funciones de horario de sesión, ni eventos o callbacks, ni apertura de cuentas, ni historial de posiciones. `history_positions_get` **no existe** en el binario aunque algún wrapper de terceros la mencione. [EVIDENCIA]
- `order_calc_margin` estima el margen "sin considerar las órdenes pendientes ni las posiciones abiertas actuales" (doc oficial). Con esa función no se puede controlar el apalancamiento total de la cartera. [EVIDENCIA]
- `order_check`: según la doc oficial, que el envío sea correcto "no implica que la operación se vaya a ejecutar". En los ejemplos documentados el éxito se ve como `retcode=0, comment='Done'`. [EVIDENCIA]
- Los tipos de resultado (`SymbolInfo`, `Tick`, `AccountInfo`, `TerminalInfo`, `OrderSendResult`, `OrderCheckResult`, `TradePosition`, `TradeOrder`, `TradeDeal`, `BookInfo`, `TradeRequest`) son tuplas con nombre implementadas en C.
  - Tienen `_asdict()`, que viene compilado con el docstring "Convert named tuple object to dictionary".
  - Se pueden importar desde `MetaTrader5`, como hace `aiomql`.
  - No se pueden serializar con `pickle` (mt5linux, issue #57).
  - **Los campos se deben leer siempre por nombre**, nunca por posición. [EVIDENCIA + CÓDIGO-3º]
- **Constantes que el paquete NO exporta**, comprobado en `__init__.py` 5.0.6231. Hay que definirlas en el código:
  - `SYMBOL_FILLING_FOK=1`, `SYMBOL_FILLING_IOC=2`;
  - `SYMBOL_EXPIRATION_GTC/DAY/SPECIFIED/SPECIFIED_DAY = 1/2/4/8`;
  - `SYMBOL_ORDER_MARKET/LIMIT/STOP/STOP_LIMIT/SL/TP/CLOSEBY = 1/2/4/8/16/32/64`;
  - `TRADE_RETCODE_HEDGE_PROHIBITED=10046`.
  - Los valores salen de la doc MQL5 de propiedades de símbolo y de retcodes. [EVIDENCIA]
- **Funciones auxiliares sin documentar** en `__init__.py`: `Buy()`, `Sell()` y `Close()`.
  - Usan `deviation=10`.
  - No fijan `type_filling`, `magic` ni SL.
  - Reintentan hasta 10 veces ante REQUOTE o PRICE_OFF.
  - `Close()` devuelve `True`, `"Partially"`, `False` o `None`.
  - **No conviene usarlas en el bot**: no adjuntan stop ni se identifican. [EVIDENCIA: código; OPINIÓN: recomendación]
- La tabla de `last_error()` de la doc oficial pone `RES_E_INTERNAL_FAIL_CONNECT = -10003`, mientras que el paquete define **-10004**. Manda el valor del paquete. [EVIDENCIA]

### 2.3 Códigos de `last_error()` [EVIDENCIA: `__init__.py`]

| código | constante | significado y acción [OPINIÓN] |
|---|---|---|
| 1 | `RES_S_OK` | OK |
| -1 | `RES_E_FAIL` | fallo genérico: reintentar una vez y alertar |
| -2 | `RES_E_INVALID_PARAMS` | bug en los parámetros: no reintentar |
| -4 | `RES_E_NOT_FOUND` | "no history": puede que la historia aún no se haya sincronizado; reintentar con espera |
| -5 | `RES_E_INVALID_VERSION` | versión de terminal o paquete incompatible: **HALT** |
| -6 | `RES_E_AUTH_FAILED` | autorización fallida: **HALT** |
| -7 | `RES_E_UNSUPPORTED` | p. ej. login con OTP o certificado: **HALT** |
| -8 | `RES_E_AUTO_TRADING_DISABLED` | algotrading deshabilitado: **HALT** de nuevas órdenes |
| -10000 a -10005 | `RES_E_INTERNAL_FAIL*` (send, recv, init, connect, timeout) | el IPC con el terminal se cayó: re-`initialize` con backoff y luego **reconciliar** |

---

## 3. Conexión: `initialize`, `login`, `shutdown`

### 3.1 Semántica oficial [EVIDENCIA: doc oficial, espejo en mt5linux]

- `initialize()` se puede llamar de tres formas:
  - sin argumentos: busca el terminal automáticamente;
  - con `path` (`terminal64.exe`);
  - con `path` más `login`, `password`, `server`, `timeout` y `portable`.
- Sin `login` usa **la última cuenta**. Sin `password` ni `server` usa **los guardados en la base del terminal**.
- `timeout` vale por defecto 60 000 ms. `portable` vale `False` por defecto.
- *"If required, the MetaTrader 5 terminal is launched to establish connection"*: el terminal se abre solo si hace falta.
- `login(login, password=..., server=..., timeout=...)` cambia de cuenta dentro de una conexión ya abierta. Si se agota el `timeout`, "la llamada se termina forzosamente y se genera la excepción".

### 3.2 Patrón recomendado: adjuntarse a un terminal ya logueado [OPINIÓN, basado en la doc]

1. Instalar el terminal **en una carpeta dedicada al bot** y arrancarlo en modo portable (p. ej. `C:\MT5-bot\terminal64.exe /portable`). Así los datos no se mezclan con otros terminales y `path` siempre apunta a ese.
2. Abrir la cuenta demo **desde el terminal** (Archivo → Abrir cuenta). La API no puede crear cuentas.
3. Iniciar sesión a mano, con OTP o passkey si el broker lo exige, y marcar "Guardar contraseña" si se desea.
4. El bot llama a `mt5.initialize(path)` **sin credenciales**.
5. El bot verifica:
   - que `account_info().login` y `.server` coincidan con `MT5_EXPECTED_LOGIN` y `MT5_EXPECTED_SERVER`;
   - que `trade_mode == ACCOUNT_TRADE_MODE_DEMO`, salvo que haya opt-in explícito para real.
6. Si algo no coincide: `shutdown()` y **no operar**.

Ventajas:
- El bot no guarda la contraseña maestra.
- Las cuentas con OTP, que la API no puede autenticar, siguen funcionando.

Este patrón está implementado en `Mt5Gateway.connect()` (§13).

### 3.3 Problemas conocidos de conexión

- **`(-10005, 'IPC timeout')` en `initialize()`** [EVIDENCIA-FORO]. Reportes con el terminal build 6230/6231 y los paquetes 5.0.6180 y 5.0.6231:
  - en Windows Server 2019;
  - con `portable=True`;
  - con `timeout=120000`.
  - Los hilos son 517169, 517620, 517401 y 519788.
  - Causas propuestas en el foro, **ninguna confirmada**:
    - terminal recién instalado sin ninguna cuenta autenticada (se arregló iniciando sesión a mano en una demo);
    - casilla "Disable algorithmic trading via external Python API" marcada;
    - ruta mal escapada;
    - **Python y el terminal con distinta elevación** (uno como administrador y el otro no).
  - mt5linux (issue #55) observa el mismo síntoma con un fallo a los ~60 s exactos.
- **Build 6266**: un usuario reporta que la casilla de restricción de la API de Python aparece **gris** mientras Algo Trading está apagado (foro 518568). [EVIDENCIA-FORO]
- **Passkey** (build 6060, 23-jul-2026): MT5 añadió passkey como segundo factor al iniciar sesión. **[VERIFICAR]** cómo afecta a `login()` desde Python. Mitigación: el patrón de §3.2, con login manual.
- **Checklist de arranque** [OPINIÓN]:
  1. Abrir el terminal a mano y comprobar que está conectado (indicador de conexión).
  2. Botón Algo Trading en verde.
  3. Python y el terminal con el mismo usuario de Windows y sin "Ejecutar como administrador" en ninguno.
  4. `initialize(path)` con la ruta absoluta en un raw string (`r"C:\MT5-bot\terminal64.exe"`).
  5. Si falla con -10005: cerrar el terminal, reabrirlo, iniciar sesión y reintentar con backoff (5, 10, 20 y 40 s).
  6. Si sigue fallando: **no operar** y alertar.

### 3.4 Un terminal por proceso [OPINIÓN / VERIFICAR]

- La API conecta **un proceso Python con un terminal**. Para varias cuentas se usan varias instalaciones portables, cada una con su proceso.
- No encontré documentación oficial sobre la seguridad de la API entre hilos.
- `aiomql` envuelve cada llamada con `asyncio.to_thread` y además serializa con un `asyncio.Lock`. [CÓDIGO-3º]
- Recomendación: **un único hilo dueño de la conexión**. El resto del bot le pasa peticiones por una cola.

---

## 4. Gate de cuenta y terminal (antes de cada sesión y cada 60 s)

Campos verificados en el binario 5.0.6231 y en la doc. El "uso" es **[OPINIÓN]**.

| campo | significado | regla del bot |
|---|---|---|
| `AccountInfo.trade_mode` | 0 demo, 1 concurso, 2 real (`ACCOUNT_TRADE_MODE_*`) | ≠ 0 → no operar, salvo `TRADING_MODE=live` **y** `MT5_ALLOW_REAL` con la frase exacta |
| `AccountInfo.login`, `.server` | cuenta y servidor | deben coincidir con lo configurado |
| `AccountInfo.margin_mode` | 0 netting retail, 1 exchange, 2 hedging retail | registrarlo; en hedging, cerrar siempre con `position=ticket` |
| `AccountInfo.trade_allowed` | la cuenta permite operar | `False` → no operar (p. ej. sesión iniciada con contraseña de inversor) |
| `AccountInfo.trade_expert` | la cuenta permite trading automatizado | `False` → no operar |
| `AccountInfo.limit_orders` | máximo de órdenes pendientes | tope duro del bot por debajo de este valor |
| `AccountInfo.fifo_close` | cierre obligatorio en orden FIFO | si es `True`, cerrar en orden FIFO (hay que confirmarlo con el broker) |
| `AccountInfo.leverage`, `.currency`, `.equity`, `.margin_free`, `.margin_level` | apalancamiento del broker, divisa y estado | sizing y kill-switch; `currency` ≠ USD → conversiones |
| `TerminalInfo.connected` | conexión con el servidor de trading | `False` → no enviar nada |
| `TerminalInfo.trade_allowed` | **botón Algo Trading** (mt5linux #51: `False` → `order_send` da 10027) | `False` → HALT de entradas |
| `TerminalInfo.tradeapi_disabled` | campo del binario, probablemente la casilla "Disable algorithmic trading via external Python API" **[VERIFICAR la correspondencia exacta]** | `True` → HALT |
| `TerminalInfo.maxbars` | "Max. bars in chart" | debe ser ≥ las barras que pide el calentamiento de indicadores |
| `TerminalInfo.build`, `version()` | build del terminal | registrar; comparar con la versión probada |
| `TerminalInfo.ping_last` | último ping al servidor (en MQL5, `TERMINAL_PING_LAST` va en microsegundos **[VERIFICAR]**) | registrar; alertar si sube mucho |
| `TerminalInfo.data_path` | carpeta de datos (logs del terminal) | adjuntar los logs a la auditoría |

---

## 5. Símbolos

### 5.1 Nombres según el broker

Lo que se encontró, con nivel de evidencia:

| broker / entidad | índice Nasdaq-100 | acciones de EE. UU. | fuente |
|---|---|---|---|
| Pepperstone | `NAS100` | `AAPL.US` (horario de contado) y `AAPL.US-24` (24 h, con sufijo `-24`) | pepperstone.com, página "24-hour share CFDs" [SECUNDARIA] |
| IC Markets | `USTEC` [VERIFICAR] | `NVDA.NAS`, `AIG.NYSE` (ticker + bolsa) | icmarkets.eu: aviso del *split* de NVDA.NAS y lista de acciones [SECUNDARIA] |
| Admirals (Trade.MT5) | **`US100`** desde el 01-nov-2025 (antes `[NQ100]`); `US100-Z` en Zero.MT5 | prefijo `#` (p. ej. `#ADM`, `#TDIV`) | admiralmarkets.com, avisos de cambio de nombre [SECUNDARIA] |
| FTMO (prop firm) | `US100.cash`; contrato rolling `US100.sim` | — | ftmo.com, trading updates [SECUNDARIA] |
| XM | `US100Cash` | — | artículo promocional de xm.com [SECUNDARIA, VERIFICAR] |
| Exness | `USTEC` | — | reseñas de terceros [VERIFICAR] |
| FxPro | `US100_U26` es un **futuro con vencimiento**, no contado | — | fxpro.com [SECUNDARIA] |

**Regla de resolución** [OPINIÓN, implementable]:

1. **Índice.** Llamar a `symbols_get(group="*NAS*,*US100*,*USTEC*,*NDX*,*TEC*")`. La sintaxis de grupos es oficial: `*` como comodín, `!` para excluir, condiciones aplicadas en orden.
   - Quedarse con los símbolos que cumplan:
     - `trade_calc_mode ∈ {CFD, CFDINDEX, CFDLEVERAGE}`;
     - `description` contiene "Nasdaq" o "100";
     - `currency_profit == "USD"`;
     - el nombre **no** termina en un código de vencimiento (`_U26`, `_Z26`…).
   - Si queda más de uno: **no elegir automáticamente**. Lo fija el usuario en la configuración.
2. **Acciones.** Para cada ticker canónico (NVDA, MSFT, AAPL, AMZN, GOOGL, META, AVGO, TSLA, AMD, NFLX…), probar en orden `T`, `T.US`, `T.NAS`, `T.NYSE`, `#T`, `T.OQ`.
   - Aceptar el primero cuyo `symbol_info` exista y cuya `description` contenga el nombre de la empresa.
   - Si el broker rellena `isin`, validar por ISIN.
   - Guardar el mapeo **en la configuración** (p. ej. `config/mt5_symbols.yml`) y no volver a resolverlo en cada arranque. Los nombres cambian: Admirals renombró `[NQ100]` en 2025.
3. Llamar a `symbol_select(name, True)` antes de pedir ticks o datos.
   - La doc oficial lo usa así en el ejemplo de `order_send`.
   - Un símbolo no se puede quitar de Market Watch mientras tenga gráficos abiertos o posiciones.

### 5.2 Campos de `symbol_info` que usa el bot [EVIDENCIA: nombres en el binario; la regla de uso es OPINIÓN]

| campo | uso |
|---|---|
| `trade_mode` | `SYMBOL_TRADE_MODE_FULL=4` para operar; `LONGONLY=1`, `SHORTONLY=2`, `CLOSEONLY=3` y `DISABLED=0` bloquean |
| `trade_exemode` | `REQUEST=0`, `INSTANT=1`, `MARKET=2`, `EXCHANGE=3`. Decide si hace falta `price`, si actúa `deviation` y qué llenados se aceptan |
| `filling_mode` | bits FOK=1 / IOC=2 |
| `order_mode` | bits MARKET=1, LIMIT=2, STOP=4, STOP_LIMIT=8, SL=16, TP=32, CLOSEBY=64. Sin `MARKET\|SL` no hay entradas a mercado con stop |
| `expiration_mode` | bits GTC=1, DAY=2, SPECIFIED=4, SPECIFIED_DAY=8. Una pendiente con expiración exacta requiere el bit 4 |
| `order_gtc_mode` | `SYMBOL_ORDERS_GTC=0`, `DAILY=1`, `DAILY_NO_STOPS=2`. Indica si las pendientes y los SL/TP sobreviven al cambio de día |
| `volume_min`, `volume_step`, `volume_max`, `volume_limit` | redondeo del volumen **hacia abajo** al múltiplo de `volume_step`; `volume_limit` (0 = sin límite) acota el volumen total por símbolo |
| `trade_contract_size` | unidades por lote (p. ej. 1 acción, o 1 USD por punto) |
| `trade_tick_size`, `trade_tick_value`, `trade_tick_value_profit`, `trade_tick_value_loss` | valor del tick en la **divisa de la cuenta**: `valor por 1.0 de precio y lote = tick_value / tick_size`. Para riesgo se usa `_loss` |
| `point`, `digits` | los precios se redondean a `trade_tick_size` (que puede ser 0.25, 0.1…), **no solo** a `digits` |
| `trade_stops_level` | distancia mínima en **puntos** entre el SL/TP y el precio. Si vale 0, el símbolo no declara mínimo fijo (el broker puede tener uno flotante); usar un colchón ≥ 2 spreads [OPINIÓN] |
| `trade_freeze_level` | distancia en puntos dentro de la cual no se pueden modificar ni cerrar órdenes o posiciones (respuesta 10029 FROZEN) |
| `trade_calc_mode` | `CFD=2`, `CFDINDEX=3`, `CFDLEVERAGE=4`, `EXCH_STOCKS=32`… Describe cómo se calculan margen y beneficio |
| `spread`, `spread_float`, `bid`, `ask` | spread actual en puntos; si `spread_float` es `True`, es variable |
| `currency_profit`, `currency_margin` | divisas de P&L y de margen |
| `swap_long`, `swap_short`, `swap_rollover3days` | coste nocturno. En day trading no debería aplicarse: hay que cerrar antes |
| `session_open`, `session_close`, `session_deals`… | **estadísticas** de la sesión (precios y conteos), **no horarios** |
| `start_time`, `expiration_time` | inicio y fin de vida del instrumento (futuros), no horario diario |
| `isin`, `description`, `exchange`, `path` | identificación |

### 5.3 Horarios de sesión (la API de Python no los da) [EVIDENCIA + OPINIÓN]

- No hay función de sesiones en el binario. Las alternativas son:
  1. **Calendario NYSE** (`exchange_calendars`, calendario `XNYS`) en UTC, convertido al reloj del servidor con el modelo de §6.3. Es la fuente de verdad para el RTH y los cierres anticipados.
  2. **Horario de la ficha de especificación** del broker, copiado a la configuración por el usuario y cotejado con 1.
  3. *[OPINIÓN]* Un script MQL5 pequeño que exporte `SymbolInfoSessionTrade` a un JSON en la carpeta común, para que Python lo lea. Añade un segundo lenguaje: solo merece la pena si 1 y 2 discrepan.
- **Validación en vivo**: si llega `10018 MARKET_CLOSED` o el último tick es viejo, el símbolo queda bloqueado esa sesión.

---

## 6. Datos: barras, ticks y el reloj del servidor

### 6.1 Barras y ticks

- `copy_rates_from_pos(symbol, tf, start_pos, count)`: según la doc oficial, la barra **0 es la actual**.
  - El array viene del más antiguo al más reciente.
  - En `copy_rates_from_pos(..., 0, n)` **el último elemento es la barra que todavía se está formando**.
  - **Regla**: para señales, usar `start_pos=1` o descartar la última fila. Así lo hace SiliconMetaTrader5 ("position 1 skips the bar that is still forming"). [EVIDENCIA + CÓDIGO-3º]
- **Límite "Max. bars in chart"** [EVIDENCIA + EVIDENCIA-FORO]
  - Doc oficial: *"MetaTrader 5 terminal provides bars only within a history available to a user on charts. The number of bars available to users is set in the 'Max. bars in chart' parameter"*.
  - Se cambia en Herramientas → Opciones → Gráficos y **hace falta reiniciar el terminal** (foro).
- **Ticks**: `copy_ticks_range(symbol, from, to, flags)` acepta tres flags:
  - `COPY_TICKS_INFO`: ticks con cambio de bid o ask;
  - `COPY_TICKS_TRADE`: ticks con cambio de last o volumen;
  - `COPY_TICKS_ALL`: todos.
  - Las definiciones de los flags son [EVIDENCIA]. **[OPINIÓN]** En CFD lo útil es `COPY_TICKS_INFO`, porque no hay operaciones de bolsa.
- **Volumen**:
  - `tick_volume` cuenta cambios de precio, no volumen negociado.
  - `real_volume` solo tiene sentido en instrumentos de bolsa. En CFD OTC cabe esperar 0 **[VERIFICAR en demo]**.
  - Los filtros de "volumen relativo" deben calcularse con datos de la bolsa (p. ej. QQQ/NVDA SIP en `/home/user/harness/data/intraday`), no con el CFD. [OPINIÓN]
- **Columna `spread` de las barras** (en puntos): la doc no precisa si es el mínimo o el último de la barra **[VERIFICAR]**.
  - Para medir costes de verdad: `copy_ticks_range(..., COPY_TICKS_INFO)` y `ask − bid` por minuto del día.

### 6.2 Contradicción sobre la zona horaria

- **Doc oficial** [EVIDENCIA]:
  - *"MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift). Therefore, 'datetime' should be created in UTC time… Data received from the MetaTrader 5 terminal has UTC time."*
  - Los ejemplos crean `datetime(..., tzinfo=pytz.timezone("Etc/UTC"))`.
- **Práctica** [EVIDENCIA-FORO + CÓDIGO-3º]: ticks, barras y deals vienen con **el reloj del servidor del broker** escrito como epoch.
  - En MetaQuotes-Demo (builds 6182 a 6259) los ticks van ≈ 3 h por delante de UTC en verano. Hilos 515951, 517653, 518574, 497637 y 375461.
  - El moderador Alain Verleyen (hilo 518574, 2026-10-15) dice: *"MT5 returns data in broker server time"*. Las diferencias que ve la gente vienen de que el `datetime` que se pide "is interpreted as UTC" por las APIs.
  - Lo mismo afirman `brokerclock` (*"MT5 does not give you UTC… server clock written as epoch seconds"*) y SiliconMetaTrader5 (*"Bar times are on the broker's clock"*).
- **Cómo cuadra todo**:
  - Para pedir datos, pasar un `datetime` *aware* en UTC cuyos **números de reloj** sean los del servidor, o directamente epoch en reloj de servidor.
  - Un `datetime` *naive* se convierte con la zona horaria del PC y desplaza la ventana.
  - Al recibir datos, interpretar `time` como reloj de servidor.
  - Lo mismo vale para `expiration` de las pendientes (`brokerclock`). **[VERIFICAR en demo]**

### 6.3 Modelo "New York close" y detección del desfase

- **Pepperstone** [SECUNDARIA]: servidor en GMT+3 durante el horario de verano de EE. UU. y GMT+2 el resto del año, "para que la vela diaria cierre con el día de Nueva York". El contado de EE. UU. va de **16:30 a 23:00** (GMT+3). En los símbolos `-24`: pre-market de 11:00 a 16:30 y after-hours de 23:00 a 03:00.
- **IC Markets** [SECUNDARIA]: el servidor se basa en "5 pm New York" y pasa de GMT+2 a GMT+3 cuando cambia la hora en EE. UU.
- **brokerclock** [CÓDIGO-3º]: "la mayoría" de brokers usa GMT+2/+3 con el cambio de EE. UU. Otros usan la regla europea, GMT+1/+2 o un desfase fijo.
- **Consecuencia** [CÁLCULO]: servidor = hora de NY + 7 h, así que **09:30–16:00 ET = 16:30–23:00 de servidor todo el año**.
  - Cuadra con el aviso de FTMO: cierre anticipado de índices de EE. UU. a las 20:00 de plataforma = 13:00 ET.
  - En brokers con regla **europea**, la apertura cae a las 15:30 de servidor durante ≈ 3 semanas de marzo y ≈ 1 semana de octubre/noviembre.
- **Vela D1**: empieza a medianoche del servidor = 17:00 ET. **El "máximo/mínimo del día previo" de una D1 de US100 incluye la sesión nocturna.**
  - Para el máximo y mínimo de la sesión regular (RTH), usar barras M1/M5 entre 16:30 y 23:00 de servidor. [CÁLCULO + OPINIÓN]
- **Pre-market del índice** (04:00–09:30 ET = 11:00–16:30 de servidor): se puede sacar del CFD del índice si cotiza casi 23 h.
  - Ejemplos: XM `US100Cash` 01:05–23:15 GMT+2 y Admirals 01:00–23:59, ambos [SECUNDARIA/VERIFICAR].
  - En CFD de **acciones** normales no hay pre-market. Solo existe si el broker ofrece símbolos ampliados, como el `-24` de Pepperstone.
- **Detección en vivo** (implementada en `measure_server_offset`):
  - Con un tick fresco: `offset = round((tick.time_msc/1000 − time.time()) / 900) × 900`.
  - Si el redondeo se aleja más de 60 s del valor bruto, el tick es viejo y no se mide.
  - Comparar con el modelo NY+7. Si no coincide → **HALT** ("reloj incoherente").
  - El reloj del PC debe estar sincronizado (servicio de hora de Windows).

---

## 7. Órdenes

### 7.1 `MqlTradeRequest`: campos y uso por acción [EVIDENCIA: doc oficial de `order_send`; las reglas de uso son OPINIÓN]

Campos oficiales: `action, magic, order, symbol, volume, price, stoplimit, sl, tp, deviation, type, type_filling, type_time, expiration, comment, position, position_by`.

- `price`: *"is not set in case of market orders for instruments of the 'Market Execution' (SYMBOL_TRADE_EXECUTION_MARKET) type having the TRADE_ACTION_DEAL type"*.
- `position`: *"Fill it when changing and closing a position… Usually, it is the same as the ticket of the order that opened the position."*

| acción (valor) | uso en el bot | campos |
|---|---|---|
| `TRADE_ACTION_DEAL` (1) | entrar o salir a mercado | `symbol, volume, type=BUY/SELL, price` (se ignora en Market), `sl`, `tp`, `deviation`, `magic`, `comment`, `type_time`, `type_filling`; para cerrar, además `position=ticket` |
| `TRADE_ACTION_PENDING` (5) | stop o limit de ruptura (ORB) | `type=BUY_STOP/SELL_STOP/…`, `price`, `sl`, `tp`, `type_time=SPECIFIED` + `expiration` (reloj de servidor), `type_filling=RETURN` |
| `TRADE_ACTION_SLTP` (6) | mover SL (breakeven, trailing) o TP | `symbol, position, sl, tp` |
| `TRADE_ACTION_MODIFY` (7) | mover una pendiente | `order, price, sl, tp, type_time, expiration` |
| `TRADE_ACTION_REMOVE` (8) | cancelar una pendiente (OCO manual) | `order` |
| `TRADE_ACTION_CLOSE_BY` (10) | cerrar contra la opuesta (solo hedging) | `position, position_by` |

- `ORDER_TYPE_*`: `BUY=0`, `SELL=1`, `BUY_LIMIT=2`, `SELL_LIMIT=3`, `BUY_STOP=4`, `SELL_STOP=5`, `BUY_STOP_LIMIT=6`, `SELL_STOP_LIMIT=7`, `CLOSE_BY=8`.
  - **No hay tipo OCO.** Una ruptura en las dos direcciones exige cancelar la otra pendiente cuando una se ejecuta, consultando en bucle. [EVIDENCIA: enumeración]
- `ORDER_TIME_*`:
  - `GTC=0`;
  - `DAY=1`: válida durante el día de trading en curso;
  - `SPECIFIED=2`;
  - `SPECIFIED_DAY=3`: hasta las 23:59:59 del día indicado.
- **`deviation`**:
  - Doc oficial: "maximum acceptable deviation from the requested price, specified in points".
  - Libro MQL5: **solo actúa en los modos Instant y Request**. En Market no limita el slippage. [EVIDENCIA]
  - Consecuencia: el bot debe medir el slippage después de la ejecución (`result.price` contra el precio de la señal) y **dejar de operar** el símbolo si supera el presupuesto. [OPINIÓN]
- **SL y TP en la misma orden de mercado**:
  - El ejemplo oficial de `order_send` los pone en la orden `DEAL`.
  - En el foro hay quien los envía después con `SLTP`.
  - **Regla** [OPINIÓN]: enviar el SL **dentro** de la orden de entrada. Si el broker responde 10016 (INVALID_STOPS) a un SL válido, **no abrir sin stop**: no operar ese símbolo hasta revisarlo en demo.
- **`comment`**: no hay límite oficial publicado. En el foro se observa ≈ 31 caracteres y que el servidor puede sobrescribir el final (p. ej. con `[sl]`).
  - Regla: ≤ 25 caracteres y sin información crítica. Para identificar, usar `magic`. [EVIDENCIA-FORO + OPINIÓN]
- **Dónde viven los stops** [VERIFICAR]: los SL/TP normales se guardan en el servidor del broker y siguen activos aunque el PC se apague. El *trailing stop* de la interfaz del terminal funciona del lado del cliente.
  - Implicación: el bot **siempre** envía el SL en la entrada. El trailing lo hace el bot con `TRADE_ACTION_SLTP`.

### 7.2 Modo de llenado [EVIDENCIA, con contradicción]

- **Definiciones oficiales**:
  - **FOK**: todo o nada.
  - **IOC**: llena lo disponible y cancela el resto.
  - **RETURN**: "only for market, limit and stop limit orders and only for the symbols with Market or Exchange execution modes; if filled partially… the remaining volume is not canceled".
  - **BOC** (Book-or-Cancel, desde el build 3800, jun-2023): solo para limit y stop-limit pasivas.
- **Contradicción**:
  - La referencia de propiedades de órdenes y el libro MQL5 dicen que *"Return orders are not allowed in the Market Execution mode"*.
  - Un texto de la página de propiedades de símbolo, citado en el foro, dice que en Market y Exchange "Return is always allowed".
  - Un blog de MQL5 llama a RETURN en Market "the classic trap", que acaba en **10030**.
- **Pendientes**: el libro MQL5 indica `ORDER_FILLING_RETURN` sea cual sea el modo de ejecución.
- **Algoritmo implementado** (`candidate_fillings` + `_send_with_filling`) [OPINIÓN, probado con el módulo falso]:
  1. Pendiente → `[RETURN]`.
  2. Mercado → FOK si el bit 1 está activo, después IOC si el bit 2 lo está. RETURN solo como último recurso cuando el símbolo **no** está en modo Market o no declara ningún bit.
  3. Para cada candidato: `order_check`. Si da 10030, siguiente; si da otro código ≠ 0, abortar sin enviar.
  4. Si pasa, `order_send`. Si responde 10030, siguiente: el rechazo no ejecutó nada.
  5. **[VERIFICAR]** si `order_check` valida el modo de llenado. Por eso se maneja 10030 en los dos pasos.
- **FOK antes que IOC** [OPINIÓN]: en day trading con stop calculado conviene todo o nada. Con IOC puede quedar un parcial (10010) cuyo tamaño no encaja con el plan.

### 7.3 Margen, beneficio y comisiones

- `order_calc_profit(ORDER_TYPE_BUY, sym, 1.0, entry, stop)` devuelve, para un lote y en la divisa de la cuenta, la pérdida en el stop, con conversión de divisas. Se usa como **verificación cruzada** del cálculo por `tick_value`. Si difieren más de un 2 %, no se opera. [EVIDENCIA: semántica de la doc; OPINIÓN: umbral]
- `order_calc_margin(...)` sirve para comprobar que hay margen libre, **no** para el tope de 3x (§9).
- Las comisiones aparecen en `TradeDeal.commission` y `TradeDeal.fee` en `history_deals_get(position=…)`.
  - **[VERIFICAR]** que `order_calc_profit` no incluye comisión. Asumir que no y sumar aparte el coste de ida y vuelta: `2 × comisión_por_lado + spread × valor_por_unidad`.
- Dividendos y *splits* sobre CFD de acciones aparecen como deals de tipo `DEAL_DIVIDEND=15` y `DEAL_DIVIDEND_FRANKED=16`, y con `DEAL_REASON_SPLIT=9`. [EVIDENCIA: constantes]

---

## 8. Retcodes y política de manejo

- Los códigos y nombres salen del paquete; las descripciones, de la doc oficial (página "Trade Server Return Codes"). [EVIDENCIA]
- La columna "acción" es **[OPINIÓN]** y está implementada en `RETCODE_ACTION` del ejemplo.
- Un test comprueba que la tabla cubre los 40 retcodes del paquete más el 10046.

| código | nombre | descripción oficial (resumida) | acción del bot |
|---|---|---|---|
| 10004 | REQUOTE | recotización | reintentar con tick nuevo (máx. 2) si el slippage sigue dentro del presupuesto |
| 10006 | REJECT | solicitud rechazada | no reenviar; registrar |
| 10007 | CANCEL | cancelada por el trader | no reenviar |
| 10008 | PLACED | orden colocada | OK (pendiente) |
| 10009 | DONE | solicitud completada | OK; verificar la posición |
| 10010 | DONE_PARTIAL | solo una parte completada | tratar como parcial: recalcular el riesgo y no completar a ciegas |
| 10011 | ERROR | error de procesamiento | **reconciliar** |
| 10012 | TIMEOUT | cancelada por timeout | **reconciliar** antes de cualquier reintento |
| 10013 | INVALID | solicitud inválida | bug: no reintentar; bloquear el setup |
| 10014 | INVALID_VOLUME | volumen inválido | bug de normalización |
| 10015 | INVALID_PRICE | precio inválido | bug de redondeo al tick |
| 10016 | INVALID_STOPS | stops inválidos | no abrir sin stop; revisar stops/freeze level |
| 10017 | TRADE_DISABLED | trading deshabilitado | bloquear el símbolo |
| 10018 | MARKET_CLOSED | mercado cerrado | bloquear el símbolo esa sesión |
| 10019 | NO_MONEY | fondos insuficientes | bloquear entradas y alertar |
| 10020 | PRICE_CHANGED | el precio cambió | como REQUOTE |
| 10021 | PRICE_OFF | sin cotizaciones | como REQUOTE; si se repite, bloquear el símbolo |
| 10022 | INVALID_EXPIRATION | expiración inválida | bug (revisar el bit de `expiration_mode`) |
| 10023 | ORDER_CHANGED | cambió el estado de la orden | reconciliar |
| 10024 | TOO_MANY_REQUESTS | demasiadas solicitudes | esperar con backoff |
| 10025 | NO_CHANGES | sin cambios | no-op (modificación redundante) |
| 10026 | SERVER_DISABLES_AT | autotrading deshabilitado por el servidor | **HALT** |
| 10027 | CLIENT_DISABLES_AT | autotrading deshabilitado por el terminal | **HALT** (kill-switch humano) |
| 10028 | LOCKED | solicitud bloqueada en proceso | backoff y reconciliar |
| 10029 | FROZEN | orden o posición congelada (freeze level) | esperar; no modificar dentro del freeze level |
| 10030 | INVALID_FILL | tipo de llenado inválido | probar el siguiente modo permitido |
| 10031 | CONNECTION | sin conexión con el servidor | **reconciliar** al reconectar |
| 10032 | ONLY_REAL | solo para cuentas reales | HALT (configuración) |
| 10033 | LIMIT_ORDERS | límite de pendientes | bloquear entradas |
| 10034 | LIMIT_VOLUME | límite de volumen del símbolo | bloquear entradas |
| 10035 | INVALID_ORDER | tipo de orden incorrecto o prohibido | bug (`order_mode`) |
| 10036 | POSITION_CLOSED | la posición ya estaba cerrada | darlo por hecho y reconciliar |
| 10038 | INVALID_CLOSE_VOLUME | volumen de cierre mayor que la posición | reconciliar el volumen |
| 10039 | CLOSE_ORDER_EXIST | ya existe una orden de cierre | reconciliar |
| 10040 | LIMIT_POSITIONS | límite de posiciones | bloquear entradas |
| 10041 | REJECT_CANCEL | activación de pendiente rechazada; orden cancelada | reconciliar |
| 10042–10044 | LONG_ONLY / SHORT_ONLY / CLOSE_ONLY | restricción del símbolo | bloquear el símbolo (o el lado) |
| 10045 | FIFO_CLOSE | cierre solo por FIFO | bloquear y cerrar en orden FIFO |
| 10046 | HEDGE_PROHIBITED (**no** exportado) | posiciones opuestas prohibidas | bloquear |
| otro | — | — | **HALT** (fallar cerrado) |
| `None` | (la llamada falló) | ver `last_error()` | −8 → HALT; si no → **reconciliar** |

### Reconciliación (idempotencia) [OPINIÓN, implementable]

- Cada entrada lleva un **`magic` fijo del bot** y un `comment` corto con el id de la señal (≤ 25 caracteres).
- Ante `None`, 10011, 10012, 10023, 10031, 10039 o 10041, **no se reenvía**. Se consultan:
  - `positions_get(symbol=…)` filtrando por `magic`;
  - `orders_get(symbol=…)`;
  - `history_deals_get(date_from, date_to, group=symbol)` de los últimos minutos (las fechas en reloj de servidor), o `history_deals_get(ticket=order)` si se conoce el ticket.
- Si aparece un deal o una posición con ese `magic` y ese `comment`, la entrada **existe**: registrarla y gestionarla.
- Si no aparece, esperar 5 s y consultar otra vez. Solo después de 2 consultas vacías se considera "no ejecutada".
- **Reenviar está prohibido** si ya pasó la ventana de la señal.
- En hedging, el ticket de la posición suele coincidir con el de la orden que la abrió (doc oficial).

---

## 9. Sizing, apalancamiento y regulación

### 9.1 Fórmulas implementadas (`size_position`) [CÁLCULO + OPINIÓN]

```
valor_por_unidad_loss   = trade_tick_value_loss   / trade_tick_size   # divisa cuenta, por 1.0 de precio y lote
valor_por_unidad_profit = trade_tick_value_profit / trade_tick_size
pérdida_por_lote = |entrada − stop| × valor_por_unidad_loss          # cruzado con −order_calc_profit(...)
nocional_por_lote = entrada × valor_por_unidad_profit
lotes_riesgo = equity × riesgo_frac / pérdida_por_lote
lotes_apalanc = (3.0 × equity − nocional_abierto) / nocional_por_lote
lotes = floor_step(min(lotes_riesgo, lotes_apalanc));  si lotes < volume_min → NO OPERAR (nunca redondear hacia arriba)
equity_mínima_símbolo = max(volume_min × pérdida_por_lote / riesgo_frac,  volume_min × nocional_por_lote / 3.0)
```

### 9.2 Regulación [EVIDENCIA, salvo donde se indica]

- **ESMA**, medidas de intervención sobre CFD de 2018, para clientes minoristas. Aplican desde el 01-ago-2018 y ESMA las renovó varias veces. Después, cada autoridad nacional las adoptó como medida propia **[VERIFICAR la vigencia exacta en el país del usuario]**. Contenido:
  - 30:1 en pares de divisas principales;
  - **20:1** en pares no principales, oro e **índices bursátiles principales**;
  - 10:1 en materias primas distintas del oro e índices no principales;
  - **5:1 en acciones individuales**;
  - 2:1 en cripto;
  - cierre de posiciones cuando el margen cae al **50 %** del mínimo;
  - protección de saldo negativo por cuenta.
  - El aviso de renovación de ESMA y la definición de "major stock market index" del FCA Handbook incluyen el **NASDAQ 100**.
- **ASIC** (Australia, orden en vigor desde el 29-mar-2021): índices principales 20:1 y acciones 5:1, con el mismo esquema. [EVIDENCIA vía prensa sectorial]
- **FCA** (Reino Unido): conserva límites por subyacente, cierre al 50 % y protección de saldo negativo. [SECUNDARIA]
- **Offshore** (Vanuatu, Seychelles, Belice…): apalancamientos de 1:100 a 1:500+ sin protecciones de minorista. [SECUNDARIA]
- **Residentes en EE. UU.**: no pueden operar CFD minoristas. Fuentes secundarias coherentes; falta confirmarlo con SEC/CFTC **[VERIFICAR]**.
- **[OPINIÓN]** El tope del usuario (3x efectivo sobre el nocional) es mucho más estricto que el regulatorio, así que **lo que limita el tamaño es el bot**.
  - El apalancamiento que muestra el broker (`AccountInfo.leverage`) solo dice cuánto margen se bloquea.
  - Con margen de 1:20 se podría abrir 20x el equity: el bot **no** debe usar el margen como freno.

### 9.3 Ejemplos con cuentas pequeñas [CÁLCULO; precios aproximados, no de broker]

- **Supuesto US100** ≈ 28 200:
  - QQQ cerró en 688.17 el 2026-11-12 (dataset local `equities_daily/QQQ_1d.csv`).
  - Ratio NDX/QQQ ≈ 41.0, medido en 2023 entre el CFD de Dukascopy US100 y QQQ (`intraday/cfd_dukascopy/US100_15m.csv`).
  - Es una estimación.
- **Supuesto de contrato**: 1 USD por punto y lote. **Cada broker define el suyo [VERIFICAR].**
- **Nocional por posición y equity mínima para respetar 3x**:

| tamaño | nocional | equity mínima a 3x | margen ESMA 1:20 |
|---|---|---|---|
| 1.0 lote | ≈ 28 200 USD | ≈ 9 400 USD | ≈ 1 410 USD |
| 0.1 lote | ≈ 2 820 USD | ≈ **940 USD** | ≈ 141 USD |
| 0.01 lote | ≈ 282 USD | ≈ 94 USD | — |

- **Riesgo con un stop de 40 puntos** (≈ 0.14 %):

| tamaño | pérdida en el stop | con equity de 100 USD |
|---|---|---|
| 0.1 lote | 4 USD | 4 % del equity |
| 0.01 lote | 0.40 USD | 0.4 % |

  - **Con 100 USD reales** solo sirve un broker con lote mínimo 0.01 en el índice. Si no, cada operación pesa ≥ 4 % y basta un stop para chocar con el límite diario del 5 %.
- **CFD de NVDA** a 166.19 (cierre del 2026-11-12, dataset local), con 1 acción por lote:
  - 1 acción = 166 USD de nocional, 1.66x sobre 100 USD (cabe en 3x); 2 acciones ya serían 3.3x.
  - Un stop del 1 % (1.66 USD) = **1.66 %** del equity. Para bajar de ahí hacen falta fracciones de acción (`volume_min` < 1) **[VERIFICAR por broker]**.
- **[OPINIÓN]**
  - Con 100 USD reales no se puede respetar "0.25–0.5 % por operación" y a la vez el lote mínimo.
  - Esos 100 USD sirven para probar la operativa real (ejecución, slippage, comisiones), **no** para medir la estrategia.
  - Para que el riesgo por operación sea ≤ 0.5 % con 0.1 lote de US100 y stop de 40 puntos, hacen falta ≥ 800 USD; y ≥ 940 USD para el tope de 3x.

---

## 10. CFD de índices y de acciones de EE. UU.: especificaciones y sesiones

| aspecto | índice (US100 / NAS100 / USTEC) | acción (NVDA y similares) |
|---|---|---|
| `trade_calc_mode` | `CFDINDEX` o `CFD` [VERIFICAR por broker] | `CFD` o `CFDLEVERAGE` [VERIFICAR] |
| contrato | normalmente 1 unidad de cuenta por punto y lote; algunos brokers usan otro valor [VERIFICAR] | 1 acción por lote |
| volumen mínimo | 0.01–1 según el broker (Admirals avisó de bajar NQ100 a 0.02 lotes con paso 0.01, fecha sin confirmar [SECUNDARIA]) | 1 acción o fracción [VERIFICAR] (una reseña de IC Markets dice mínimo 0.1 [SECUNDARIA]) |
| comisión | habitualmente solo spread (Pepperstone "zero commission on index CFDs"; FTMO no cobra comisión en índices rolling) [SECUNDARIA] | por acción y por lado (≈ 0.02 USD/acción en reseñas de IC Markets) [SECUNDARIA, VERIFICAR] |
| horario (servidor NY+7) | casi 23 h; ejemplos: XM 01:05–23:15, Admirals 01:00–23:59 [SECUNDARIA] | **16:30–23:00** (RTH); 24 h solo con símbolos especiales (Pepperstone `-24`) |
| apalancamiento minorista UE/UK/AU | 1:20 | 1:5 |
| eventos corporativos | — | dividendos como deals `DEAL_DIVIDEND`; *splits* con `DEAL_REASON_SPLIT` [EVIDENCIA] |
| precio fuera del horario de contado | el CFD de contado suele derivarse del futuro con ajuste de base [VERIFICAR por broker] | sin cotización |

**[OPINIÓN]** Reglas operativas derivadas:

1. **No entrar en los primeros 60 s** tras las 16:30 de servidor. Pedir además `spread ≤ 2 ×` la mediana del spread de ese minuto del día, medida en los logs de demo.
2. **Cierre forzado a las 22:55 de servidor** (15:55 ET). Así se evitan el cierre del CFD de acciones a las 23:00, los swaps y el gap nocturno.
3. **Calendario XNYS** para festivos y cierres anticipados (13:00 ET = 20:00 de servidor). Ejemplo: el aviso de FTMO de cierre a las 20:00 en un festivo de EE. UU.

---

## 11. Entorno de ejecución

### 11.1 Windows nativo (decisión del usuario): pasos

1. Instalar MT5 de 64 bits, preferiblemente desde el broker elegido, en `C:\MT5-bot\`. Arrancarlo en modo portable (`terminal64.exe /portable`) **[VERIFICAR la sintaxis del modificador en la ayuda del terminal]**.
2. Abrir una **cuenta demo** desde el terminal y anotar el **nombre exacto del servidor**, tal como aparece en la ventana de login.
3. En Herramientas → Opciones → **Asesores Expertos**:
   - marcar "Permitir trading algorítmico";
   - **desmarcar** "Disable algorithmic trading via external Python API";
   - **[OPINIÓN]** marcar "Deshabilitar el trading algorítmico al cambiar de cuenta" **[VERIFICAR el nombre exacto]**.
4. En Herramientas → Opciones → **Gráficos**: subir "Max. bars in chart" (p. ej. a ilimitado) y **reiniciar el terminal**.
5. Botón **Algo Trading** en verde. En Market Watch, Ctrl+U: buscar los símbolos y apuntar los nombres exactos. Clic derecho → Especificación para guardar la ficha.
6. Instalar **Python 3.13 x64** (python.org), crear un venv y ejecutar `pip install MetaTrader5==5.0.6231` junto con las dependencias del bot.
7. Variables de entorno, siguiendo el patrón de `core/secrets.py`, nunca en el repo:
   - `MT5_TERMINAL_PATH`, `MT5_EXPECTED_LOGIN`, `MT5_EXPECTED_SERVER`;
   - `TRADING_MODE=demo`;
   - `MT5_LOGIN`, `MT5_PASSWORD` y `MT5_SERVER` solo si el usuario elige que el bot inicie sesión (no recomendado).
8. Ejecutar `python smoke_check.py`, que es de solo lectura: versión, cuenta, flags, especificaciones y desfase del reloj.
9. Hacer una prueba de orden **opt-in** en demo con el volumen mínimo, cerrarla enseguida y comprobar retcodes, slippage, comisiones y log.
10. Ajustes del PC:
    - desactivar la suspensión;
    - fijar las "horas activas" de Windows Update fuera de la sesión;
    - mantener la sincronización horaria activa;
    - considerar un SAI;
    - el bot y el terminal con el **mismo usuario y la misma elevación**.
11. El terminal se actualiza (LiveUpdate) y puede reiniciarse. Hace falta un watchdog que, ante -10001…-10005, haga `shutdown()`, espere, vuelva a `initialize()` y **reconcilie** antes de seguir. [OPINIÓN]

### 11.2 Linux y macOS (plan B)

| opción | cómo funciona | estado (nov-2026) | riesgos |
|---|---|---|---|
| **Wine a mano** | terminal y Python para Windows en el mismo prefijo de Wine; el bot corre en ese Python | MetaQuotes añadió la integración Python en Wine en el build 2085 (nota "Integration with Python… in Wine (Linux/macOS)") y tiene una guía oficial de instalación en Linux [EVIDENCIA] | las dependencias del bot se instalan en el Python de Windows dentro de Wine |
| **mt5linux** (lucas-campagna) | Python Windows en Wine + servidor **RPyC classic** (puerto 18812); el cliente Linux replica la API | v1.1.1 (PyPI, 2026-08-04); último commit 2026-10-27 [CÓDIGO-3º] | issues abiertos: #50 (la v1.1.1 exige Docker/udocker), #51 (en Docker, `common.ini` deja `[Experts] Enabled=0` → **10027**), #55 (IPC timeout a ~60 s), #57 (`PicklingError` con `TerminalInfo` y otros) |
| **pymt5linux** | fork para Python 3.13 | v1.0 (2025-04-14), último commit 2025-06-21 | poco mantenido |
| **mt5-remote** | cliente/servidor RPyC | v1.0.5 (2025-08-31); fija `metatrader5==5.0.5200`, `numpy==2.3.2`, `rpyc==6.0.2` | versiones fijadas viejas |
| **gmag11/MetaTrader5-Docker-Image** | KasmVNC (web en :3000) + MT5 en Wine + mt5linux en **:8001** escuchando en `0.0.0.0` | último commit 2025-12-20; **fija `MetaTrader5==5.0.36` (2021) y Python 3.9 en Wine**; solo amd64 [CÓDIGO-3º] | paquete viejo (sin numpy 2); puerto RPyC sin autenticación |
| **SiliconMetaTrader5** | app + runtime: Wine 11 + Rosetta 2 en Mac, nativo o Docker en Linux, VPS por SSH; puertos solo en 127.0.0.1 | v1.3.0 (PyPI, 2026-11-05) [CÓDIGO-3º] | **licencia PolyForm Noncommercial**: el uso comercial requiere licencia |
| **VM o VPS Windows** | MT5 y Python nativos | — | coste y administración; es la opción con soporte oficial completo |
| **APIs en la nube** (MetaApi, MetaRPC/mrpc.pro) | terminal gestionado por un tercero | comerciales y de pago [CÓDIGO-3º] | las credenciales salen de tu máquina; dependencia de un tercero |

- **Seguridad de RPyC** [EVIDENCIA: `rpyc/docs/docs/security.rst`]: *"The classic mode (SlaveService) is intentionally insecure… exposes everything to the client… Only ever use a classic mode server over secure local networks."*
  - Cualquiera que llegue al puerto puede ejecutar código y **operar la cuenta**.
  - Regla: escuchar solo en `127.0.0.1`, o usar un túnel SSH. Nunca `0.0.0.0` en un VPS.
- **VPS integrado de MQL5** (Virtual Hosting): migra programas MQL5 del terminal. **No ejecuta procesos Python externos** [VERIFICAR; es lo que entiendo de su diseño]. Para Python 24/5 hace falta un VPS Windows propio.

---

## 12. Seguridad

1. **Contraseñas** [EVIDENCIA-FORO + EVIDENCIA]:
   - La **maestra** opera; la de **inversor** es de solo lectura.
   - Un usuario recibía 10017/10027 porque había iniciado sesión con la de inversor (foro 483129).
   - Según la ayuda de MT5, con la contraseña de inversor **no se pide OTP**: es la credencial adecuada para paneles y auditoría de solo lectura (p. ej. una skill de auditoría en otra máquina).
2. **OTP y passkey** [EVIDENCIA]:
   - El binario contiene `"Unsupported authorization mode, OTP or certificate password needed"`, y el foro 459777 lo reporta como error `-7` en `login()`.
   - El build 6060 añadió **passkey** como segundo factor.
   - Mitigación: iniciar sesión a mano en el terminal y que el bot se adjunte (§3.2).
3. **Guardar credenciales**:
   - **Opción A, recomendada** [OPINIÓN]: no guardar nada en el bot; el terminal ya tiene la sesión iniciada.
   - **Opción B**: variables de entorno del servicio, o Windows Credential Manager vía `keyring` [OPINIÓN]. Nunca en el repo, ni en logs, ni en `comment`.
4. **Gate de identidad** (implementado): `login` y `server` esperados, y `trade_mode == DEMO`, salvo `TRADING_MODE=live` **y** `MT5_ALLOW_REAL` con la frase exacta (§14, R1).
5. **Kill-switch humano** [EVIDENCIA + VERIFICAR]:
   - Apagar el botón **Algo Trading** hace que `terminal_info().trade_allowed` pase a `False` y que `order_send` devuelva 10027.
   - La casilla de Python API bloquea **solo Python** (los EAs siguen) y también devuelve 10027 (ayuda de MT5).
   - **[VERIFICAR]** que apagar Algo Trading **no cierra** posiciones: los SL/TP del servidor siguen activos.
   - El bot debe detectarlo (`trading_permitted()`), dejar de abrir y avisar.
   - **[OPINIÓN]** Decidir con el usuario si en ese estado el bot puede cerrar posiciones. Con 10027 no podría.
6. **Aislamiento** [OPINIÓN]:
   - instalación portable dedicada;
   - `magic` exclusivo;
   - **no operar a mano en la misma cuenta**: confunde la reconciliación y el P&L diario del kill-switch;
   - si se opera a mano, que sea en otra cuenta.
7. **Red** [EVIDENCIA]: los puentes RPyC classic no deben quedar expuestos (§11.2).

---

## 13. Probar sin terminal

### 13.1 Estrategia

1. **Inyección de dependencias** [OPINIÓN + CÓDIGO-3º]:
   - El conector recibe el módulo `mt5` por constructor (`Mt5Gateway(mt5, cfg)`) y nunca hace `import MetaTrader5` al cargar el módulo.
   - En los tests se pasa `fake_mt5`, o se hace `monkeypatch.setitem(sys.modules, "MetaTrader5", fake)` para scripts que importan el paquete (así se prueba `smoke_check.py`).
   - `pdmt5` hace lo mismo con un `ModuleType` + `MagicMock` (`tests/helpers.py::create_mock_mt5_module`).
2. **Constantes verificadas**: un test parsea con `ast` el `__init__.py` del wheel oficial (descargado por `fetch_official_wheel.sh` con su SHA-256) y exige que coincidan:
   - las constantes del módulo falso;
   - los retcodes de la tabla de política.
3. **Escenarios guionizados** en el módulo falso:
   - cola de retcodes para `order_send` (REQUOTE seguido de DONE);
   - `None` con `last_error` (-10005 o -8);
   - símbolos con distintos bits de `filling_mode`, `order_mode` y `expiration_mode`;
   - Algo Trading apagado;
   - cuenta real;
   - login inesperado.
4. **Tests de contrato contra la demo**, *opt-in* [CÓDIGO-3º: mt5linux usa los markers `e2e` y `trading` y `MT5_E2E_ALLOW_ORDER_SEND=1`]:
   - en el PC Windows, `pytest -m mt5_demo` con `MT5_DEMO_ALLOW_ORDER_SEND=1`;
   - orden de volumen mínimo, cierre inmediato, y comprobación de retcode, `magic` y deals.
5. **Grabar y reproducir** [OPINIÓN]: guardar los `_asdict()` reales de la demo en JSON (spec de símbolos, ticks, resultados) y reproducirlos en el módulo falso. Así los tests usan datos reales del broker elegido.
6. **El Strategy Tester de MT5 ejecuta EAs MQL5, no scripts Python** [VERIFICAR]. Existen simuladores comunitarios en Python (artículos MQL5 20455 y 20782). El backtest del bot sigue en Python con los datos del harness.

### 13.2 Resultado de los tests del ejemplo [EVIDENCIA: ejecutado en este contenedor]

```
$ cd /home/user/harness/daytrade/research/03_mt5 && ./fetch_official_wheel.sh && python3 -m pytest -q test_mt5_gateway.py
/tmp/.../metatrader5-5.0.6231-cp313-cp313-win_amd64.whl: OK
.....................                                                    [100%]
21 passed
```

Qué cubren:
- constantes falsas = oficiales;
- la tabla de retcodes cubre todos los oficiales (+10046);
- volumen redondeado hacia abajo (incluida la trampa `0.3/0.1`);
- precio redondeado al tick (0.25);
- validación de SL/TP por lado;
- candidatos de llenado;
- clasificación de retcodes;
- sizing con doble tope y negativa por debajo de `volume_min`;
- verificación cruzada con `order_calc_profit`;
- desfase NY+7 en invierno, en verano y en la semana de desajuste de marzo;
- rechazo de ticks viejos;
- ventana 16:30–16:45 = 09:30 ET y rango de apertura (`None` si falta un minuto);
- gate de cuenta real y de login;
- IOC elegido en un símbolo solo-IOC;
- REQUOTE reintentado;
- `None` → reconciliar sin reenviar;
- Algo Trading apagado → no se envía nada;
- API de Python deshabilitada (-8) → HALT;
- pendiente sin el bit SPECIFIED → error;
- `smoke_check` no envía ninguna orden.

### 13.3 Fragmentos clave del ejemplo

El código completo está en `03_mt5/mt5_gateway.py`.

```python
SYMBOL_FILLING_FOK = 1   # el paquete no exporta estas constantes (verificado en 5.0.6231)
SYMBOL_FILLING_IOC = 2

def candidate_fillings(sym, mt5, pending: bool) -> list[int]:
    if pending:
        return [mt5.ORDER_FILLING_RETURN]
    out = []
    if sym.filling_mode & SYMBOL_FILLING_FOK:
        out.append(mt5.ORDER_FILLING_FOK)
    if sym.filling_mode & SYMBOL_FILLING_IOC:
        out.append(mt5.ORDER_FILLING_IOC)
    if sym.trade_exemode != mt5.SYMBOL_TRADE_EXECUTION_MARKET or not out:
        out.append(mt5.ORDER_FILLING_RETURN)
    return out

def normalize_volume(volume, volume_min, volume_max, volume_step) -> float:
    """Redondea HACIA ABAJO al múltiplo de volume_step; 0.0 si queda bajo volume_min."""
    if volume <= 0 or volume_step <= 0:
        return 0.0
    v = min(Decimal(repr(volume)), Decimal(repr(volume_max)))
    step = Decimal(repr(volume_step))
    out = (v / step).to_integral_value(rounding=ROUND_FLOOR) * step
    return 0.0 if out < Decimal(repr(volume_min)) else float(out)

def measure_server_offset(tick_time_msc: int, now_utc: float | None = None, max_age_s=60.0) -> int:
    now_utc = time.time() if now_utc is None else now_utc
    raw = tick_time_msc / 1000.0 - now_utc          # desfase + antigüedad del tick
    off = round(raw / 900.0) * 900                  # múltiplos de 15 min
    if abs(raw - off) > max_age_s:
        raise GatewayError("tick no fresco: no se mide el desfase")
    return int(off)
```

```python
class Mt5Gateway:
    def connect(self) -> None:
        m = self.mt5
        ok = m.initialize(self.cfg.path) if self.cfg.path else m.initialize()   # sin contraseña
        if not ok:
            raise GatewayError(f"initialize() failed: {m.last_error()}")
        acc, term = m.account_info(), m.terminal_info()
        if acc is None or term is None:
            m.shutdown(); raise GatewayError(f"no account/terminal info: {m.last_error()}")
        if acc.login != self.cfg.expected_login or acc.server != self.cfg.expected_server:
            m.shutdown(); raise GatewayError(f"unexpected account {acc.login}@{acc.server}")
        if acc.trade_mode != m.ACCOUNT_TRADE_MODE_DEMO and not self.cfg.allow_real:
            m.shutdown(); raise GatewayError("account is not DEMO and allow_real is False")

    def _send_with_filling(self, request: dict, fillings) -> Any:
        m, rejected = self.mt5, None
        for filling in fillings:
            req = dict(request, type_filling=filling)
            chk = m.order_check(req)
            if chk is None:
                raise GatewayError(f"order_check() failed: {m.last_error()}")
            if chk.retcode == m.TRADE_RETCODE_INVALID_FILL:
                continue
            if chk.retcode != 0:                     # 0 = OK en order_check
                raise GatewayError(f"order_check retcode={chk.retcode} {chk.comment}")
            res = m.order_send(req)
            if res is not None and res.retcode == m.TRADE_RETCODE_INVALID_FILL:
                rejected = res; continue             # 10030 no ejecuta nada: probar el siguiente
            return res
        if rejected is not None:
            return rejected
        raise GatewayError("no filling mode accepted by order_check()")

    def _classify(self, res) -> Action:
        if res is None:                              # falló el IPC: estado desconocido
            code, _ = self.mt5.last_error()
            return Action.HALT if code == -8 else Action.RECONCILE
        return classify_retcode(res.retcode)
```

---

## 14. Reglas implementables del conector

**Variables por defecto.** Las marcadas *usuario* las fija el usuario; el resto son **[OPINIÓN]** y se calibran en demo.

| variable | valor | origen |
|---|---|---|
| `MAX_LEVERAGE_EFFECTIVE` | 3.0 (nocional / equity) | usuario |
| `RISK_PER_TRADE` | 0.25 % (máx. 0.5 %) | *usuario: pendiente de confirmar*; 0.25 % es el valor de `max_risk_per_trade_alt` en `risk_limits.yml` |
| `DAILY_BLOCK` / `DAILY_FLATTEN` | −2 % / −5 % de la equity al inicio de la sesión | `risk_limits.yml` (usuario: 5 % diario) |
| `DD_HALF_RISK` / `DD_HALT` | 10 % / 20 % desde el máximo | `risk_limits.yml` (usuario: 20 %) |
| `TICK_MAX_AGE` | 5 s para operar; 60 s para medir el desfase | OPINIÓN |
| `OFFSET_ROUND` | 900 s | OPINIÓN (brokerclock usa pasos de 15 min) |
| `ENTRY_BLACKOUT_OPEN` | 60 s tras las 16:30 de servidor | OPINIÓN |
| `LAST_ENTRY` | 22:30 de servidor (15:30 ET) | OPINIÓN |
| `FORCED_FLAT` | 22:55 de servidor (15:55 ET); en días con cierre anticipado, cierre − 5 min | OPINIÓN |
| `MAX_SPREAD` | ≤ 2 × mediana del spread de ese minuto del día (logs de demo) | OPINIÓN |
| `MAX_SLIPPAGE` | ≤ 0.25 × distancia al stop | OPINIÓN |
| `PRICE_RETRIES` | 2 (solo 10004/10020/10021) | OPINIÓN |
| `DEVIATION_POINTS` | 20 (solo actúa en Instant/Request) | EVIDENCIA + OPINIÓN |
| `COMMENT_MAX` | 25 caracteres | EVIDENCIA-FORO + OPINIÓN |
| `RECONCILE_WAIT` | 5 s × 2 consultas | OPINIÓN |
| `POLL_INTERVAL` | 0.5–1 s (barras M1/M5) | OPINIÓN |
| `RECONNECT_BACKOFF` | 5, 10, 20, 40, 60 s | OPINIÓN |
| `LOSS_CROSSCHECK_TOL` | 2 % (tick_value frente a `order_calc_profit`) | OPINIÓN |

### R1. Gate de entorno (al arrancar, 30 min antes de la apertura y cada 60 s)

Se opera solo si se cumplen **todas**:
1. `initialize(path)` → `True`.
2. `login`/`server` esperados.
3. `trade_mode == DEMO`, o bien `TRADING_MODE=live` y `MT5_ALLOW_REAL="si-entiendo-el-riesgo"`.
4. `terminal.connected`, `terminal.trade_allowed`, `not terminal.tradeapi_disabled`, `account.trade_allowed` y `account.trade_expert` son todos verdaderos.
5. `__version__` igual a la versión fijada y ≥ 5.0.4682.
6. El desfase medido coincide con el modelo del broker (NY+7 por defecto).
7. `maxbars` ≥ las barras necesarias.
8. Cada símbolo resuelto, en Market Watch, con `trade_mode=FULL`, `order_mode ⊇ {MARKET, SL}` y al menos un modo de llenado candidato.

Si algo falla, no se opera y se avisa.

### R2. NO entrar si (cualquiera)

- Kill-switch: P&L diario ≤ −2 %, o DD ≥ 20 %.
- Fuera de la ventana [16:31, 22:30] de servidor.
- Día festivo o fuera del horario según XNYS.
- Tick con más de 5 s.
- Spread > `MAX_SPREAD`.
- `size_position` devuelve 0, que incluye estar por debajo de `volume_min`.
- `order_check` ≠ 0.
- El apalancamiento efectivo superaría 3x.
- Hay una reconciliación pendiente en el símbolo.
- El símbolo quedó bloqueado hoy por un retcode de tipo BLOCK.
- Ya hay una posición del bot en el símbolo [OPINIÓN: sin piramidar].
- Se superó el número máximo de operaciones del día (*usuario*).

### R3. Entrada a mercado

1. `DEAL` con `sl` obligatorio (y `tp` si la estrategia lo define), `magic` fijo y `comment` = id de la señal.
2. Modo de llenado según R-filling (§7.2).
3. Reintentar solo ante 10004/10020/10021, con tick nuevo, como mucho 2 veces y solo si el slippage sigue ≤ `MAX_SLIPPAGE`.
4. Tras 10009: confirmar la posición con `positions_get` + `magic`. Registrar:
   - precio de ejecución;
   - slippage;
   - spread;
   - latencia (`perf_counter` antes y después de `order_send`);
   - `retcode_external`.

### R4. Entrada por pendiente (ruptura de rango de apertura)

1. `BUY_STOP` en el máximo del rango + *buffer*; `SELL_STOP` en el mínimo − *buffer*.
2. `type_time=SPECIFIED` con `expiration` en reloj de servidor (requiere el bit 4 de `expiration_mode`) y `RETURN`.
3. Cuando una se ejecuta, `REMOVE` de la otra (no existe OCO nativo).
4. Si `expiration_mode` no admite SPECIFIED: usar `ORDER_TIME_DAY` y cancelar a mano a la hora límite.

### R5. Salidas

1. SL/TP en el servidor desde la entrada.
2. Breakeven o trailing con `SLTP`, solo si la distancia es > `trade_stops_level` y > `trade_freeze_level`, y como máximo una modificación cada 5 s [OPINIÓN].
3. A las 22:55 de servidor: `REMOVE` de todas las pendientes del bot y cierre de sus posiciones. Verificar que no queda nada. Si alguna no cierra, alerta inmediata.
4. Con el kill-switch en −5 %: cerrar todo y bloquear el día.
5. Si se pierde la conexión: no enviar nada; reconectar con backoff; **reconciliar** antes de cualquier acción nueva.

### R6. Sizing

Las fórmulas de §9.1, con las tres condiciones:
- doble tope (riesgo y 3x);
- verificación cruzada con `order_calc_profit`;
- nunca redondear hacia arriba.

### R7. Datos

1. Barras con `copy_rates_from_pos(sym, tf, 1, n)`, sin la barra en formación.
2. Tiempos convertidos con el desfase medido.
3. Ventanas de sesión en reloj de servidor (16:30–23:00).
4. El máximo y mínimo previos se toman del RTH en M1, no de D1.
5. El rango de apertura de 16:30 a 16:45 se calcula solo si **están los 15 minutos**; si falta alguno, ese día no se opera ORB.

### R8. Auditoría

Cada petición y cada respuesta se escriben en JSONL con estos campos:
- `ts_utc`, `ts_server`, `rule_id`, `signal_id`, `request._asdict()`, `result._asdict()`;
- `last_error`, `action`;
- `bid`, `ask` y `spread` al enviar; `latency_ms`;
- equity antes y después.

Ese log es lo que debe revisar la skill de auditoría:
- que todas las entradas lleven SL;
- que el riesgo esté dentro del presupuesto;
- que no haya entradas fuera de la ventana;
- que la cuenta quede plana al cierre;
- la distribución de retcodes, el slippage y el spread.

---

## 15. Qué tiene evidencia sólida y qué es folklore

| afirmación | veredicto |
|---|---|
| "El paquete MetaTrader5 funciona en Linux/Mac" | **Falso**. Solo hay wheels `win_amd64`; fuera de Windows hace falta Wine o un puente [EVIDENCIA] |
| "Cualquier versión sirve con numpy 2" | **Falso**. Hace falta ≥ 5.0.4682 [EVIDENCIA binaria] |
| "Los tiempos de MT5 están en UTC" | **Lo dice la doc oficial, pero la práctica lo contradice**: reloj de servidor [EVIDENCIA-FORO + CÓDIGO-3º] |
| "`deviation` me protege del slippage" | **Falso en ejecución Market**: solo actúa en Instant y Request [EVIDENCIA] |
| "Usa siempre ORDER_FILLING_RETURN" | **Folklore**. En Market da 10030; hay que elegir por bits [EVIDENCIA] |
| "Si `order_check` pasa, la orden se ejecuta" | **Falso** según la doc oficial |
| "`order_send` siempre devuelve un resultado" | **Falso**. Puede devolver `None` (el propio `Close()` del paquete lo contempla) [EVIDENCIA] |
| "Si hay timeout, reenvía" | **Peligroso**: puede duplicar la posición. Hay que reconciliar primero [OPINIÓN fundada en la semántica de 10012/`None`] |
| "El apalancamiento del broker es mi apalancamiento" | **Falso**: el efectivo es nocional / equity. El margen 1:20 permite hasta 20x [CÁLCULO] |
| "El volumen de MT5 es volumen real" | **Falso en CFD**: `tick_volume` cuenta cambios de precio [EVIDENCIA de campos + VERIFICAR `real_volume`] |
| "El VPS de MQL5 corre mi bot Python" | **No** [VERIFICAR] |
| "RPyC/mt5linux es seguro de exponer" | **Falso**: el modo classic es inseguro por diseño [EVIDENCIA] |
| "La demo representa la ejecución real" | **No demostrado**. Slippage, recotizaciones y parciales pueden diferir; medir con los 100 USD reales [OPINIÓN] |

---

## 16. Riesgos

1. **Operativos** (PC propio): apagón, suspensión, Windows Update, actualización del terminal o caída de la red.
   - Mitigación: SL en el servidor siempre; watchdog; reconciliación; aviso de "bot caído"; cierre forzado al final de la sesión.
   - Posiciones sin SL = riesgo inaceptable.
2. **Versiones**: terminal y paquete acoplados (error de versiones incompatibles) y reportes abiertos de -10005 en 6230/6231.
   - Mitigación: fijar versiones; probar en demo tras cada actualización; poder volver a la versión anterior del paquete.
3. **Reloj**: un desfase mal aplicado desplaza todas las ventanas (rango de apertura, máximo y mínimo previos, cierre forzado).
   - Mitigación: medir en vivo y comparar con el modelo (R1).
4. **Broker**:
   - nombres y especificaciones cambian sin aviso (renombre de Admirals en 2025);
   - spreads amplios en la apertura y en noticias;
   - cierres anticipados;
   - mantenimiento de fin de semana;
   - posibles diferencias entre demo y real.
5. **Regulación y jurisdicción**: el país de residencia decide si hay CFD, qué apalancamiento y qué protección. Residentes en EE. UU.: CFD no disponibles [SECUNDARIA].
6. **Seguridad**: credenciales en texto plano, puentes expuestos, operativa manual mezclada en la cuenta.
7. **Modelo**: el CFD de índice no es el índice (base respecto al futuro, horario), y el CFD de acciones no tiene pre-market (salvo los símbolos `-24`). Las estrategias diseñadas con datos de QQQ/NVDA SIP deben revalidarse con los precios del CFD del broker antes de pasar a real.
8. **Cuenta pequeña**: con 100 USD los mínimos de volumen obligan a riesgos por operación superiores al 0.5 % (§9.3).

---

## 17. Preguntas que solo puede responder el usuario

1. **País de residencia fiscal y legal.** Decide si puede operar CFD, qué entidad del broker le toca (UE/UK/AU con 1:20 y 1:5, u offshore) y la protección de saldo negativo.
2. **Broker preferido** o lista corta (Pepperstone, IC Markets, Admirals, XM, Exness…). ¿Cuenta "standard" (solo spread) o "raw/ECN" (comisión)? ¿Hedging o netting?
3. **Divisa de la cuenta** (USD, EUR u otra). Afecta a conversiones y a costes.
4. **Nombres exactos de los símbolos** en su Market Watch: índice Nasdaq-100 y cada acción tecnológica de la lista. Y una captura o copia de la **Especificación** de cada uno: contrato, volumen mínimo y paso, tamaño y valor del tick, stops level, freeze level, modo de llenado, modo de ejecución, horario de sesiones y comisión.
5. **Zona horaria del servidor**: ¿la hora del Market Watch es GMT+2 ahora (noviembre)? Sirve para confirmar el modelo NY+7.
6. **Disponibilidad horaria**: ¿en qué zona vive? ¿Puede tener el PC encendido de 16:30 a 23:00 de servidor (09:30–16:00 ET) y supervisar la apertura? ¿Y los festivos de EE. UU.?
7. **Inicio de sesión**: ¿deja el terminal con la sesión iniciada a mano (recomendado) o quiere que el bot inicie sesión con credenciales? ¿Usa OTP o passkey?
8. **Real**: ¿qué frase o variable exacta quiere como confirmación para pasar a cuenta real? ¿Cuántos días o operaciones de demo exige antes de arrancar? Sugerencia [OPINIÓN]: ≥ 20 sesiones y ≥ 50 operaciones sin incidencias del conector.
9. **Riesgo**:
   - riesgo por operación (0.25 %, 0.5 % o 1 %);
   - máximo de operaciones por día;
   - máximo de posiciones simultáneas;
   - ¿se mantienen −2 % (bloquear) y −5 % (cerrar todo) diarios?
10. **Capital real inicial**: ¿acepta que con 100 USD el riesgo por operación será > 0.5 %, o que solo sirve como prueba de ejecución? ¿Podría empezar con ≥ 1 000 USD si la demo sale bien?
11. **Overnight**: confirmar que el day trading significa **sin posiciones abiertas tras las 22:55 de servidor** (sin swaps ni gaps).
12. **Kill-switch humano**: si apaga Algo Trading, ¿el bot debe intentar cerrar posiciones (lo que exige tenerlo encendido), o basta con que no abra nada y los SL del servidor protejan?
13. **Avisos**: ¿por qué canal quiere las alertas (Telegram, email, notificación push de MT5)?
14. **PC**: ¿Windows 10 u 11? ¿Tiene permisos de administrador para instalar? ¿Puede desactivar la suspensión y programar las actualizaciones fuera de la sesión?
15. **Datos**: ¿acepta usar la historia del broker en MT5 (M1 del CFD) como fuente para revalidar las estrategias, además del SIP de QQQ/NVDA? ¿Cuántos años ofrece su broker?
16. **Pre-market y 24 h**: si el broker ofrece CFD de acciones en 24 h, ¿quiere usarlos (más horas, spreads mayores) o solo el horario de contado?

---

## 18. Fuentes

**Paquete y documentación oficial**
- PyPI, paquete MetaTrader5 (versiones y wheels): https://pypi.org/project/MetaTrader5/ — JSON: https://pypi.org/pypi/MetaTrader5/json
- Documentación Python de MQL5 (índice): https://www.mql5.com/en/docs/python_metatrader5
  - initialize: https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py
  - login: https://www.mql5.com/en/docs/python_metatrader5/mt5login_py
  - order_send: https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
  - order_check: https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py
  - copy_rates_from: https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py
  - copy_rates_range: https://mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
  - copy_ticks_range: https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py
  - positions_get: https://www.mql5.com/en/docs/python_metatrader5/mt5positionsget_py
  - history_deals_get: https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py
- Espejo literal de la doc en docstrings: https://github.com/lucas-campagna/mt5linux/blob/master/mt5linux/metatrader5.py
- Trade Server Return Codes: https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes
- Order Properties (filling, RETURN y Market, BOC): https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties
- Symbol Properties: https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants
- Estructura MqlTradeRequest: https://www.mql5.com/en/docs/constants/structures/mqltraderequest
- Libro MQL5:
  - modos de llenado: https://www.mql5.com/en/book/automation/experts/experts_execution_filling
  - condiciones del símbolo: https://www.mql5.com/en/book/automation/symbols/symbols_execution_filling
  - compra y venta (deviation): https://www.mql5.com/en/book/automation/experts/experts_market_buy_sell
  - MqlTradeRequest: https://www.mql5.com/en/book/automation/experts/experts_mqltraderequest
  - order_check/order_send en Python: https://www.mql5.com/en/book/advanced/python/python_ordercheck_ordersend
  - lectura de barras: https://www.mql5.com/en/book/advanced/python/python_copyrates
  - inicialización: https://mql5.com/ko/book/advanced/python/python_init
  - resumen de funciones: https://www.mql5.com/en/book/advanced/python/python_funcs_overview
  - historial de deals: https://www.mql5.com/en/book/advanced/python/python_history_deals
- Blog MQL5, trampa de RETURN en Market: https://www.mql5.com/en/blogs/post/779012
- Notas de versión de MT5:
  - build 3800 (BOC): https://www.metatrader5.com/en/releasenotes/terminal/2286
  - build 6060 (Passkey): https://www.metatrader5.com/en/releasenotes/terminal/2447
  - Python en Wine (build 2085): https://www.metatrader5.com/en/news/2086
- Ayuda de MT5:
  - Expert Advisors (opción de Python API): https://www.metatrader5.com/en/terminal/help/algotrading/trade_robots_indicators
  - OTP: https://www.metatrader5.com/en/terminal/help/start_advanced/otp
  - instalación en Linux: https://www.metatrader5.com/en/terminal/help/start_advanced/install_linux

**Foro MQL5** [EVIDENCIA-FORO]
- Reloj del servidor:
  - https://www.mql5.com/en/forum/517653
  - https://www.mql5.com/en/forum/515951
  - https://www.mql5.com/en/forum/518574
  - https://www.mql5.com/en/forum/497637
  - https://www.mql5.com/en/forum/375461
  - https://www.mql5.com/en/forum/485630
- IPC timeout:
  - https://www.mql5.com/en/forum/517169
  - https://www.mql5.com/en/forum/517620
  - https://www.mql5.com/en/forum/517401
  - https://www.mql5.com/en/forum/519788
  - https://www.mql5.com/en/forum/455101 (x64 not found)
- Casilla de Python API en gris (build 6266): https://www.mql5.com/en/forum/518568
- Contraseña de inversor y 10017/10027: https://www.mql5.com/en/forum/483129
- OTP no soportado: https://www.mql5.com/en/forum/459777
- Max bars:
  - https://www.mql5.com/en/forum/490426
  - https://mql5.com/en/forum/393357/29251432
- Longitud de `comment`: https://www.mql5.com/en/forum/464340
- 10027: https://www.mql5.com/en/forum/376255

**Proyectos y código** [CÓDIGO-3º]
- mt5linux, commit 7460cbc (2026-10-27), con docs/issues #50, #51, #55 y #57: https://github.com/lucas-campagna/mt5linux
- gmag11/MetaTrader5-Docker-Image, commit 2a3fe40 (2025-12-20): https://github.com/gmag11/MetaTrader5-Docker-Image
- pymt5linux: https://github.com/hpdeandrade/pymt5linux
- mt5-remote: https://pypi.org/project/mt5-remote/
- SiliconMetaTrader5: https://github.com/bahadirumutiscimen/silicon-metatrader5
- brokerclock: https://github.com/raiez-alshamaly/brokerclock
- pdmt5 (mock en `tests/helpers.py`): https://github.com/dceoy/pdmt5
- aiomql: https://github.com/Ichinga-Samuel/aiomql
- MetaTrader5-stubs: https://github.com/heunle23/MetaTrader5-stubs
- RPyC, seguridad del modo classic: https://github.com/tomerfiliba-org/rpyc/blob/master/docs/docs/security.rst
- MetaRPC PyMT5 (servicio comercial): https://github.com/MetaRPC/PyMT5

**Brokers** [SECUNDARIA]
- Pepperstone:
  - CFD de acciones 24 h y horarios: https://pepperstone.com/en/markets/shares/24-hour-trading
  - horarios de trading: https://pepperstone.com/en/ways-to-trade/trading-hours
- IC Markets:
  - horario de verano de EE. UU.: https://www.icmarkets.com/blog/us-daylight-savings-updated-trading-schedule-2023
  - split de NVDA.NAS: https://icmarkets.eu/blog/trading-schedule/nvidia-nvda-nas-stock-split/
- Admirals:
  - renombre de símbolos Nasdaq: https://admiralmarkets.com/about-us/news/nasdaq-symbols-renaming-on-mt4-mt5-accounts
  - tamaños mínimos menores: https://admiralmarkets.com/about-us/news/lower-minimum-trade-sizes-for-cfds-on-major-indices
- FTMO, trading update: https://ftmo.com/en/blog/trading-updates/trading-update-9-jan-2025/
- XM, US100Cash: https://xm.com/tag/us100cash
- FxPro, US100_U26: https://www.fxpro.com/trading/futures/us100_u26

**Regulación**
- ESMA, medidas finales sobre CFD: https://www.esma.europa.eu/press-news/esma-news/esma-adopts-final-product-intervention-measures-cfds-and-binary-options
- ESMA, aviso de renovación (lista de índices): https://www.esma.europa.eu/sites/default/files/library/2018-esma35-43-1397_cfd_renewal_decision_notice_et.pdf
- FCA Handbook, "major stock market index": https://www.handbook.fca.org.uk/handbook/glossary/G3597m.html
- ASIC 20-254MR: https://asic.gov.au/about-asic/news-centre/find-a-media-release/2020-releases/20-254mr-asic-product-intervention-order-strengthens-cfd-protections/
- CFD en EE. UU. (secundaria): https://www.daytrading.com/cfd/usa

**Datos locales usados para los cálculos**
- `/home/user/harness/data/equities_daily/QQQ_1d.csv`, `NVDA_1d.csv`: cierres del 2026-11-12.
- `/home/user/harness/data/intraday/cfd_dukascopy/US100_15m.csv`: ratio NDX/QQQ de 2023.

---

## Anexo A. Borrador para el README: "Entorno MetaTrader 5"

> **Requisitos**
> - Windows 10/11 de 64 bits.
> - MetaTrader 5 de 64 bits del broker.
> - Python 3.13 x64.
> - `MetaTrader5==5.0.6231` (mínimo 5.0.4682 por numpy 2).
> - Cuenta **demo**.
>
> **Pasos**
> 1. Instala MT5 en `C:\MT5-bot\`, inicia sesión en la cuenta demo y anota el servidor exacto.
> 2. En Herramientas → Opciones → Asesores Expertos:
>    - activa "Permitir trading algorítmico";
>    - desactiva "Disable algorithmic trading via external Python API".
> 3. En Herramientas → Opciones → Gráficos, sube "Max. bars in chart" y reinicia MT5.
> 4. Pon el botón **Algo Trading** en verde. **Ese botón es tu kill-switch manual**: apagado, el bot no puede abrir órdenes.
> 5. Prepara Python: `py -3.13 -m venv .venv && .venv\Scripts\pip install -r requirements-windows.txt`.
> 6. Define las variables:
>    - `MT5_TERMINAL_PATH=C:\MT5-bot\terminal64.exe`
>    - `MT5_EXPECTED_LOGIN=<tu login demo>`
>    - `MT5_EXPECTED_SERVER=<servidor>`
>    - `TRADING_MODE=demo`
>    - El bot **no necesita tu contraseña**: se adjunta al terminal ya conectado.
> 7. Diagnóstico sin órdenes: `python smoke_check.py`. Revisa:
>    - `demo True`;
>    - `algo trading button True`;
>    - especificaciones de los símbolos;
>    - `server_offset` = 7200 s en invierno o 10800 s en verano, con el mercado abierto.
> 8. Prueba de orden mínima en demo (opt-in): `MT5_DEMO_ALLOW_ORDER_SEND=1 pytest -m mt5_demo`.
> 9. Mantén el PC encendido y sin suspensión durante la sesión: 16:30–23:00 hora del servidor (09:30–16:00 Nueva York).
>
> **Linux/macOS**: no está soportado de forma nativa. Usa una VM o VPS Windows, o Wine. Si usas un puente RPyC (mt5linux), **nunca expongas su puerto**: solo `127.0.0.1` o un túnel SSH.

## Anexo B. Archivos entregados

- `03_mt5/mt5_gateway.py`:
  - política de retcodes;
  - normalización de volumen y precio;
  - stops;
  - modo de llenado;
  - sizing con doble tope y equity mínima por símbolo;
  - reloj del servidor (medición, modelo NY+7, ventanas, rango de apertura);
  - `Mt5Gateway` (connect, gate, entrada a mercado, cierre, SLTP, pendiente con expiración, cancelación, posiciones y órdenes del bot).
- `03_mt5/fake_mt5.py`: módulo falso guionizable.
- `03_mt5/test_mt5_gateway.py`: 21 tests.
- `03_mt5/smoke_check.py`: diagnóstico de solo lectura para el PC Windows.
- `03_mt5/fetch_official_wheel.sh`: descarga el wheel oficial, verifica el SHA-256 y extrae las constantes. El binario `.pyd` se borró; quedan `__init__.py`, METADATA y la licencia MIT en `03_mt5/_official/`.
