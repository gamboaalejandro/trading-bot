# MetaTrader 5: puesta en marcha en tu PC Windows (demo)

Primer paso para operar con MetaTrader 5 (MT5): dejar el terminal y Python conectados y
comprobarlo **sin enviar ninguna orden**. El bot completo de day trading (motor, skills,
modo automático con límites) se construye después siguiendo las specs de `specs/`.

## Requisitos

- Windows 10/11 de 64 bits. El paquete oficial `MetaTrader5` de Python **solo existe para
  Windows** (wheels `win_amd64`, Python 3.6-3.14).
- MetaTrader 5 de 64 bits.
- Python 3.13 x64 (python.org).
- Una **cuenta demo**. Mientras eliges broker, sirve la demo que ofrece el propio terminal
  (servidor de MetaQuotes), aunque puede no traer los CFDs de índices o de acciones que
  usaremos. Para el bot conviene la demo de un broker con el CFD del Nasdaq-100 (US100,
  NAS100 o USTEC) y CFDs de acciones de EE. UU.

## Pasos

1. Instala MT5 (idealmente en `C:\MT5-bot\`), abre una cuenta demo desde el terminal y anota el
   **nombre exacto del servidor** que aparece en la ventana de inicio de sesión.
2. En **Herramientas → Opciones → Asesores Expertos**:
   - activa "Permitir trading algorítmico";
   - **desactiva** "Disable algorithmic trading via external Python API".
3. En **Herramientas → Opciones → Gráficos** sube "Max. bars in chart" (por ejemplo, ilimitado) y
   reinicia el terminal: limita cuánta historia puede leer Python.
4. Pon el botón **Algo Trading** en verde. **Ese botón es tu kill-switch manual**: apagado, ningún
   programa puede abrir órdenes (el terminal responde con el código 10027).
5. En la ventana Observación del Mercado pulsa Ctrl+U, busca los símbolos (US100/NAS100/USTEC,
   NVDA, AAPL…) y anota sus **nombres exactos**: cada broker los llama distinto.
6. Prepara Python en una carpeta del repo:

   ```bat
   py -3.13 -m venv .venv
   .venv\Scripts\pip install "MetaTrader5==5.0.6231" "numpy>=2"
   ```

   (Hace falta `MetaTrader5` 5.0.4682 o posterior para numpy 2.)
7. Ejecuta el diagnóstico, que es de solo lectura:

   ```bat
   set MT5_SYMBOLS=US100,NAS100,USTEC,NVDA,NVDA.US,#NVDA
   .venv\Scripts\python scripts\mt5_smoke_check.py
   ```

   Comprueba en la salida:
   - `demo True` (cuenta demo);
   - `connected True` y `algo trading button True`;
   - la especificación de cada símbolo que ofrece tu broker (tamaño de contrato, lote mínimo,
     paso de lote, modo de llenado, nivel de stops);
   - `server_offset` = 7200 s en invierno o 10800 s en verano **con el mercado abierto**: la
     mayoría de brokers usan la hora de "cierre de Nueva York" (NY+7), así que la apertura de
     EE. UU. (09:30 ET) cae a las 16:30 del servidor todo el año.
8. Mándame la salida (sin contraseñas: el script no las usa ni las imprime) y con eso fijamos los
   nombres de símbolos, costes y horarios reales de tu broker en la configuración.

## Ajustes del PC durante la sesión

- Desactiva la suspensión y fija las "horas activas" de Windows Update fuera de la sesión
  (09:30-16:00 Nueva York).
- Mantén activa la sincronización de hora de Windows.
- El terminal y el bot deben correr con el **mismo usuario de Windows** y la misma elevación.

## Seguridad

- El bot **no necesita tu contraseña**: se conecta al terminal que ya tiene la sesión abierta.
- Nunca guardes credenciales en el repositorio (constitución, principio VI).
- Si algún día usas Linux con Wine y el puente `mt5linux`, no expongas su puerto: solo `127.0.0.1`.

Fuente: `docs/daytrade/research/03_metatrader5.md` (investigación verificada contra el paquete
oficial 5.0.6231 y la documentación de MQL5).
