"""Integrity of the Spec Kit (SDD) installation: skills, scripts and constitution."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted((ROOT / ".claude" / "skills").glob("speckit-*/SKILL.md"))
CORE = {"analyze", "checklist", "clarify", "constitution", "converge", "implement", "plan", "specify", "tasks"}


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_all_core_commands_installed():
    assert {p.parent.name.removeprefix("speckit-") for p in SKILLS} == CORE


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter_and_script_paths(skill):
    fm = frontmatter(skill)
    assert fm["name"] == skill.parent.name
    assert fm["description"]
    assert fm["user-invocable"] is True
    body = skill.read_text(encoding="utf-8")
    # every script the skill tells Claude to run must exist in the repo
    for rel in set(re.findall(r"\.specify/scripts/bash/[\w-]+\.sh", body)):
        assert (ROOT / rel).is_file(), rel
    # no unresolved template placeholders
    assert "{SCRIPT}" not in body and "__AGENT__" not in body and "__SPECKIT_COMMAND_" not in body


def test_constitution_is_ratified():
    text = (ROOT / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    assert not re.findall(r"\[[A-Z_0-9]{3,}\]", body), "unfilled [PLACEHOLDER] in constitution"
    assert re.search(r"\*\*Version\*\*: \d+\.\d+\.\d+", body)
    assert body.count("NO NEGOCIABLE") >= 3


def test_feature_pointer_is_not_versioned():
    assert "feature.json" in (ROOT / ".specify" / ".gitignore").read_text(encoding="utf-8")
