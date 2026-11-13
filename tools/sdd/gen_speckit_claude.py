"""
Generate the Spec Kit (github/spec-kit v1.4.0) scaffolding for the Claude Code
integration WITHOUT running the Specify CLI: reads the release's command
templates, shared templates and bash scripts as data and writes them in the
layout `specify init --here --integration claude --script sh` produces
(src/specify_cli/integrations/base.py: process_template + SkillsIntegration.setup;
integrations/claude: post_process_skill_content; shared_infra.install_shared_infra).

Usage: python3 gen_speckit_claude.py <spec-kit-src> <dest-project-root>
"""
import json
import re
import shutil
import stat
import sys
from pathlib import Path

import yaml

ARGUMENT_HINTS = {
    "specify": "Describe the feature you want to specify",
    "plan": "Optional guidance for the planning phase",
    "tasks": "Optional task generation constraints",
    "implement": "Optional implementation guidance or task filter",
    "analyze": "Optional focus areas for analysis",
    "clarify": "Optional areas to clarify in the spec",
    "constitution": "Principles or values for the project constitution",
    "checklist": "Domain or focus area for the checklist",
}
HOOK_NOTE = ("- When constructing command invocations from hook command names, "
             "replace dots (`.`) with hyphens (`-`). "
             "For example, `speckit.git.commit` → `/speckit-git-commit`.")
SPECIFY_GITIGNORE = """\
# Machine-local Spec Kit state — not meant to be shared.
# Managed by the Specify CLI; safe to edit (your changes are preserved on refresh).

# Local pointer to the current feature directory. Rewritten every time you
# switch features, so it is per-checkout state rather than something to share.
feature.json

# Per-machine extension config overrides.
extensions/*/local-config.yml

# Executable adapter packages and their per-checkout provenance registry.
# Execution consent is stored separately in the user's local trust registry.
integrations/packages/
integrations/packages.json
"""
PATH_RE = re.compile(
    r"""(?:(?<![.\w])(?P<parent>(?:\.\./){2,})|(?P<boundary>^|[\s`"'(\[{<=])(?P<rel>\.specify/|(?:\.?/))?)(?P<target>scripts|memory|templates)/"""
)


def rewrite_paths(text: str) -> str:
    def repl(m: re.Match) -> str:
        target = m.group("target")
        if m.group("parent"):
            return f".specify/{target}/"
        if m.group("rel") == ".specify/":
            return m.group(0)
        return f"{m.group('boundary')}.specify/{target}/"
    return PATH_RE.sub(repl, text)


def resolve_command_refs(content: str, separator: str = "-", prefix: str = "/") -> str:
    return re.sub(r"__SPECKIT_COMMAND_([A-Z][A-Z0-9_-]*)__",
                  lambda m: prefix + "speckit" + separator + m.group(1).lower().replace("_", separator),
                  content)


def split_frontmatter(text: str):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return {}, text
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if close is None:
        return {}, text
    fm = yaml.safe_load("".join(lines[1:close])) or {}
    return fm, lines[close][3:] + "".join(lines[close + 1:])


def process_template(raw: str) -> str:
    scripts, in_fm, in_scripts = {}, False, False
    for line in raw.splitlines():
        if line == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if not in_fm:
            continue
        if line == "scripts:":
            in_scripts = True
            continue
        if in_scripts and line and not line[0].isspace():
            break
        if in_scripts:
            m = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.+)$", line)
            if m:
                scripts[m.group(1)] = m.group(2).strip()
    content = raw.replace("{SCRIPT}", scripts["sh"]) if "sh" in scripts else raw
    out, dash, in_fm, skip = [], 0, False, False
    for line in content.splitlines(keepends=True):
        s = line.rstrip("\n\r")
        if s == "---":
            dash += 1
            in_fm = dash == 1
            skip = False
            out.append(line)
            continue
        if in_fm:
            if s == "scripts:":
                skip = True
                continue
            if skip:
                if line[:1].isspace():
                    continue
                skip = False
        out.append(line)
    content = "".join(out).replace("{ARGS}", "$ARGUMENTS").replace("__AGENT__", "claude")
    return resolve_command_refs(rewrite_paths(content))


def inject_hook_note(content: str) -> str:
    def repl(m: re.Match) -> str:
        indent, instr, eol = m.group(1), m.group(2), m.group(3) or "\n"
        prev = content[:m.start()].splitlines()
        if prev and prev[-1] == indent + HOOK_NOTE:
            return m.group(0)
        return indent + HOOK_NOTE + eol + indent + instr + eol
    return re.sub(r"(?m)^([ \t]*)(- For each executable hook, output the following[^\r\n]*)(\r\n|\n|$)", repl, content)


def build_skill(stem: str, description: str, body: str, source: str) -> str:
    q = json.dumps  # JSON strings are valid YAML double-quoted scalars
    fm = [
        "---",
        f"name: {q('speckit-' + stem)}",
        f"description: {q(description or f'Spec Kit: {stem} workflow')}",
    ]
    if ARGUMENT_HINTS.get(stem):
        fm.append(f"argument-hint: {q(ARGUMENT_HINTS[stem])}")
    fm += [
        f"compatibility: {q('Requires spec-kit project structure with .specify/ directory')}",
        "metadata:",
        f"  author: {q('github-spec-kit')}",
        f"  source: {q('templates/commands/' + source)}",
        "user-invocable: true",
        "disable-model-invocation: false",
        "---",
    ]
    return inject_hook_note("\n".join(fm) + "\n" + body)


def main(src: Path, dest: Path) -> None:
    created = []
    for tpl in sorted((src / "templates" / "commands").glob("*.md")):
        raw = tpl.read_text(encoding="utf-8")
        fm, _ = split_frontmatter(raw)
        _, body = split_frontmatter(process_template(raw))
        out = dest / ".claude" / "skills" / f"speckit-{tpl.stem}" / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_skill(tpl.stem, fm.get("description", ""), body, tpl.name), encoding="utf-8")
        created.append(out)
    tdest = dest / ".specify" / "templates"
    tdest.mkdir(parents=True, exist_ok=True)
    for t in sorted((src / "templates").glob("*.md")):
        (tdest / t.name).write_text(resolve_command_refs(t.read_text(encoding="utf-8")), encoding="utf-8")
        created.append(tdest / t.name)
    sdest = dest / ".specify" / "scripts" / "bash"
    sdest.mkdir(parents=True, exist_ok=True)
    for s in sorted((src / "scripts" / "bash").glob("*.sh")):
        shutil.copyfile(s, sdest / s.name)
        (sdest / s.name).chmod((sdest / s.name).stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        created.append(sdest / s.name)
    mem = dest / ".specify" / "memory" / "constitution.md"
    if not mem.exists():
        mem.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / "templates" / "constitution-template.md", mem)
        created.append(mem)
    (dest / ".specify" / ".gitignore").write_text(SPECIFY_GITIGNORE, encoding="utf-8")
    (dest / ".specify" / "integration.json").write_text(json.dumps({
        "integration": "claude",
        "default_integration": "claude",
        "script_type": "sh",
        "speckit_version": "1.4.0",
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }, indent=2) + "\n", encoding="utf-8")
    for p in created:
        print(p.relative_to(dest))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
