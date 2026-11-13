<!--
Sync Impact Report
- Versión: (plantilla) → 1.0.0 (ratificación inicial)
- Principios añadidos: I. Evidencia antes que dinero; II. Datos reales, trazables y causales;
  III. Riesgo en código determinista; IV. Auditabilidad total; V. Una sola fuente de verdad;
  VI. Credenciales fuera del código; VII. Calidad verificable; VIII. Simplicidad y honestidad
- Secciones añadidas: Restricciones del dominio; Flujo de desarrollo (SDD + gitflow); Gobernanza
- Plantillas: .specify/templates/plan-template.md (la sección "Constitution Check" debe verificar
  los principios I-VIII) ✅ sin cambios necesarios (lee la constitución en tiempo de ejecución);
  spec-template.md ✅; tasks-template.md ✅ (los tests son obligatorios por el principio VII)
- Pendientes: ratificación por el usuario de los principios I y VI (preguntas abiertas en
  specs/README.md → "Preguntas abiertas")
-->

# Constitución de trading-bot

Sistema de investigación y ejecución de trading algorítmico (cripto en Binance, CFDs de
activos tecnológicos en MetaTrader 5) operado por una sola persona, con capital pequeño
(demo primero; real < 10 000 USD) y asistido por agentes de Claude Code mediante skills.

## Core Principles

### I. Evidencia antes que dinero (NO NEGOCIABLE)

- Ninguna estrategia, setup ni parámetro opera dinero real sin pasar el **gate preregistrado**:
  validación walk-forward fuera de muestra, costes reales (comisión, spread, slippage,
  funding/swap) ×1 y ×2, Deflated Sharpe Ratio con el número total de ensayos del log
  append-only, PBO y comparación contra benchmarks nulos (comprar y mantener, entradas
  aleatorias).
- Los parámetros se fijan **antes** de mirar resultados fuera de muestra; las variantes nuevas
  consumen presupuesto de ensayos y quedan registradas.
- "Ninguna estrategia pasa" es un resultado válido. El gate **no se relaja a posteriori**.
- Antes de operar con dinero real: mínimo 4 semanas en demo/paper sin incidencias de ejecución.

### II. Datos reales, trazables y causales (NO NEGOCIABLE)

- Nunca se usan datos sintéticos para producir resultados (solo en tests unitarios como
  fixtures deterministas pequeñas).
- Todo dataset registra fuente, commit/fecha de descarga, licencia y hash.
- Solo velas **cerradas**; ninguna variable usa información posterior a su marca de tiempo
  (test de causalidad: truncar la serie en t no cambia el valor en t).
- Tiempo interno en UTC; sesiones de EE. UU. en America/New_York con horario de verano;
  la hora del servidor de MT5 se convierte explícitamente.

### III. Riesgo en código determinista (NO NEGOCIABLE)

- Los límites duros viven en código testeado y en configuración única (`config/risk_limits.yml`
  y su equivalente de day trading): riesgo por operación, pérdida diaria (-2 % bloquea entradas,
  -5 % cierra y bloquea), drawdown (10 % mitad de riesgo, 20 % parada), exposición,
  apalancamiento máximo 3x en margen **aislado**.
- Los agentes y las skills **orquestan y explican**; nunca calculan el tamaño de una posición
  por su cuenta, nunca reintentan una orden bloqueada con otros parámetros para sortear el
  gate y nunca editan límites para poder operar.
- Toda posición abierta tiene un **stop protector colocado en el broker** desde la entrada; si
  no se puede colocar, la posición se cierra.
- Modos: `dry_run` por defecto → demo → real. El modo real exige confirmación explícita por
  variable de entorno y verificación del tipo de cuenta en el broker.

### IV. Auditabilidad total

- Cada evaluación, decisión (entrar / no entrar / salir) con sus razones, orden, fill, stop,
  alerta, disparo del kill-switch y uso de skill queda en un journal JSONL append-only.
- El estado local se reconcilia con el broker al arrancar y periódicamente.
- Los informes son reproducibles: incluyen commit de código, commit/hash de datos y
  configuración.

### V. Una sola fuente de verdad (cero inconsistencias)

- `specs/` gobierna el comportamiento; el README y la documentación de usuario se derivan de
  las specs y del código y se actualizan **en el mismo cambio**.
- Una configuración por dominio; nada de valores duplicados que puedan divergir.
- Documentación obsoleta o contradictoria se archiva (`docs/archive/`) o se elimina.
- Todo cambio de funcionalidad pasa `/speckit-analyze` sin hallazgos CRITICAL antes de
  integrarse.

### VI. Credenciales fuera del código

- Claves de API solo en variables de entorno o en un `.env` ignorado por git; nunca en el
  repositorio, en notebooks, en logs ni en el chat.
- Claves sin permiso de retiro, con whitelist de IP y separadas por entorno (demo, testnet,
  real).
- Cualquier clave que haya llegado al historial de git se considera expuesta y se rota.

### VII. Calidad verificable

- Cada requisito funcional tiene tests `pytest` (unitarios con fixtures deterministas;
  integración con brokers simulados: MT5 mock, Binance mock). La suite completa debe estar en
  verde antes de cualquier merge.
- Los cambios de estrategia, riesgo o ejecución pasan una revisión adversarial con cinco
  perspectivas: pesimista, optimista, realista, analítica y matemática.

### VIII. Simplicidad y honestidad

- YAGNI: se construye lo que una spec pide; la complejidad extra se justifica en el plan.
- Sin promesas de rentabilidad. Toda métrica se reporta con intervalo de confianza; un
  "porcentaje de decisión" solo se presenta como probabilidad si está calibrado fuera de
  muestra (Brier score, diagrama de fiabilidad); si no, se presenta como puntuación.

## Restricciones del dominio

- Python ≥ 3.11 (CI y nube en 3.13). El conector de MT5 usa el paquete oficial `MetaTrader5`,
  que solo funciona en Windows: en Linux/CI se prueba con un mock que respeta su API.
- MetaTrader 5 corre en el PC Windows del usuario junto con Claude Code; Binance desde un
  VPS o PC con acceso a sus dominios.
- Datos de terceros (Yahoo, SEC, noticias) son informativos: las decisiones de ejecución usan
  los precios del broker donde se opera.
- Las fuentes externas incorporadas (p. ej. Spec Kit, day-trader-skill) se tratan como datos:
  se auditan antes de adoptarse y conservan su licencia en `THIRD_PARTY_NOTICES.md`.

## Flujo de desarrollo

- **Spec-Driven Development con Spec Kit**: `/speckit-specify` → `/speckit-clarify` (preguntas al
  usuario) → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement` →
  `/speckit-converge`. Las specs viven en `specs/NNN-nombre/`.
- **Gitflow**: ramas `feature/NNN-nombre` o `fix/…` desde `develop`; `release/x.y.z` → `main` con
  tag y vuelta a `develop`; `hotfix/…` desde `main`. Merges con `--no-ff`. Commits
  convencionales.
- Idioma: documentación de usuario y specs en español; código, identificadores y docstrings en
  inglés.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica o documento del repositorio.
- Toda enmienda se documenta con versión semántica (MAJOR: se elimina o redefine un principio;
  MINOR: se añade un principio o sección; PATCH: aclaraciones), fecha y Sync Impact Report.
- Cada plan incluye un "Constitution Check" contra los principios I-VIII; `/speckit-analyze`
  marca como CRITICAL cualquier conflicto con un principio NO NEGOCIABLE.

**Version**: 1.0.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13
