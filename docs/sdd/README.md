# Spec-Driven Development (SDD) en este proyecto

El proyecto se desarrolla con **Spec-Driven Development** usando **GitHub Spec Kit v1.4.0**.
La idea: primero se escribe *qué* debe hacer el sistema y *por qué* (la spec), se resuelven las
dudas con preguntas al usuario, y solo después se planifica, se divide en tareas y se implementa.
Antes de implementar, un análisis cruzado detecta contradicciones entre la constitución, la spec,
el plan, las tareas y el código.

## Piezas instaladas

| ruta | qué es |
|---|---|
| `.specify/memory/constitution.md` | La **constitución**: principios innegociables (evidencia antes que dinero, datos reales, riesgo en código determinista, auditabilidad, una sola fuente de verdad, credenciales fuera del código, calidad, simplicidad). |
| `.specify/templates/` | Plantillas de spec, plan, tareas, checklist y constitución. |
| `.specify/scripts/bash/` | Scripts que resuelven rutas de la feature activa (no usan red ni git). |
| `.claude/skills/speckit-*/SKILL.md` | Los comandos de Spec Kit como skills de Claude Code. |
| `specs/NNN-nombre/` | Una carpeta por funcionalidad: `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/`, `checklists/`. Índice en `specs/README.md`. |

## Flujo

| paso | comando | resultado |
|---|---|---|
| 1 | `/speckit-constitution` | Crea o enmienda la constitución (versión semántica). |
| 2 | `/speckit-specify <descripción>` | Crea `specs/NNN-nombre/spec.md`: historias de usuario, requisitos funcionales, criterios de éxito medibles. |
| 3 | `/speckit-clarify` | **Te hace hasta 5 preguntas** sobre lo que la spec deja ambiguo y guarda las respuestas en la spec. |
| 4 | `/speckit-plan` | Plan técnico (`plan.md`, `research.md`, `data-model.md`, `contracts/`) con "Constitution Check". |
| 5 | `/speckit-tasks` | `tasks.md`: tareas ordenadas por dependencias, con tests. |
| 6 | `/speckit-analyze` | **Detecta inconsistencias**, duplicados, ambigüedades y violaciones de la constitución entre spec, plan y tareas. Solo lectura. |
| 7 | `/speckit-implement` | Ejecuta las tareas. |
| 8 | `/speckit-converge` | Compara el código con spec/plan/tareas y añade como tareas nuevas lo que falte. |
| — | `/speckit-checklist <dominio>` | Checklists de calidad de requisitos (p. ej. "riesgo", "MT5", "seguridad"). |

## Integración con gitflow

Spec Kit 1.4 localiza la feature activa con `.specify/feature.json` (o la variable
`SPECIFY_FEATURE_DIRECTORY`), no por el nombre de la rama. Por eso convive con gitflow:

1. `git checkout develop && git checkout -b feature/NNN-nombre`
2. `/speckit-specify …` (crea `specs/NNN-nombre/`) → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze`
3. `/speckit-implement`, tests en verde, `/speckit-converge`
4. merge `--no-ff` a `develop`; las versiones salen por `release/x.y.z` → `main`.

No se instaló la extensión `git` de Spec Kit (crearía ramas `NNN-nombre` fuera de gitflow).

## En Windows

Claude Code en Windows usa Git Bash para ejecutar comandos, así que los scripts `bash` funcionan
tal cual. Requisitos: Git for Windows y Python en el PATH.

## Cómo se instaló y cómo actualizarlo

En la sesión en la nube el instalador oficial no podía descargarse ni ejecutarse, así que los
archivos se generaron con `tools/sdd/gen_speckit_claude.py` a partir del repositorio de Spec Kit
(tag v1.4.0), aplicando la misma transformación que `specify init --here --integration claude
--script sh`. Para actualizar a una versión nueva en tu PC puedes usar el instalador oficial:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.4.0
specify init --here --integration claude --script sh --force
```

o regenerar con el script del repo:

```bash
git clone --depth 1 --branch v1.4.0 https://github.com/github/spec-kit /tmp/spec-kit
python tools/sdd/gen_speckit_claude.py /tmp/spec-kit .
```

Revisa el diff antes de commitear: la constitución (`.specify/memory/constitution.md`) no se
sobrescribe si ya existe.

Licencia y atribución: `THIRD_PARTY_NOTICES.md`.
