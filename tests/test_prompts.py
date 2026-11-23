"""The packaged prompts render, their schemas are strict, and they hold no personal choices."""

import re
from pathlib import Path

import pytest

from panko import prompts

PROMPT_DIR = Path(prompts.__file__).parent


@pytest.mark.parametrize("name", prompts.PROMPTS)
def test_every_prompt_renders(name):
    text = prompts.render(name)
    assert "{{" not in text and "}}" not in text
    assert len(text.split()) > 100


@pytest.mark.parametrize("name", prompts.PROMPTS)
def test_every_schema_is_strict(name):
    def walk(node, path):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            props = node.get("properties", {})
            assert node.get("additionalProperties") is False, path
            assert sorted(node.get("required", [])) == sorted(props), path
            for k, v in props.items():
                walk(v, f"{path}.{k}")
        if node.get("type") == "array":
            walk(node.get("items"), f"{path}[]")

    walk(prompts.schema(name), name)


def test_prompt_files_hold_no_personal_choices():
    personal = ["oussama", "hijab", "casablanca", "rabat", "routledge", "fez", "doda", "peace corps"]
    for f in PROMPT_DIR.glob("*.md"):
        text = f.read_text().lower()
        for word in personal:
            assert not re.search(rf"\b{word}\b", text), f"{f.name} mentions {word!r}"


def test_config_reaches_the_prompts():
    text = prompts.render("pictures-plan")
    rules = prompts.context()["picture_rules"]
    assert rules and rules in text


def test_sections_and_missing_vars():
    assert "About this source: from page 3" in prompts.render("extract", source_note="from page 3")
    assert "About this source" not in prompts.render("extract")


def test_ask_builds_a_request():
    a = prompts.ask("check", "x1", ["items here"], effort="high")
    assert a.id == "x1" and a.parts == ["items here"] and a.effort == "high"
    assert a.schema == prompts.schema("check") and a.system == prompts.render("check")
