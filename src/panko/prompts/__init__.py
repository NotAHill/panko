"""Packaged prompts for Panko's language-model steps, filled in from the learner's config.

A prompt is a Markdown file in this folder. `{{name}}` is replaced by a value; `{{#name}}…{{/name}}` is kept only
when the value is truthy; `{{> part}}` includes `_part.md`. Values come from `[learner]` and `[evidence]` in
config/panko.toml (see `context()`), plus anything the caller passes for the whole run. Everything that changes
per item goes in the request itself, not here, so the rendered prompt is identical across a run and is cached.
"""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from panko import lang
from panko.prompts.schemas import SCHEMAS

DIR = Path(__file__).parent
PROMPTS = ("extract", "deck", "check", "examples", "pictures-plan", "pictures-pick", "clashes")


def _bullets(items) -> str:
    return "\n".join(f"- {x}" for x in items)


def context() -> dict:
    """Prompt values from config. Missing settings fall back to neutral wording."""
    from panko.config import settings
    s = settings()
    L, ev = s.get("learner", {}), s.get("evidence", {})
    tr, pics, ex = L.get("translit", {}), L.get("pictures", {}), L.get("examples", {})
    dicts = ev.get("dictionaries", [])
    return {
        "language": L.get("language", "the target language"),
        "script": lang.label(),
        "rtl": lang.is_rtl(),
        "spelling": L.get("spelling", ""),
        "standard": L.get("standard", ""),
        "loans": L.get("loans", ""),
        "ex_verb": ex.get("verb", ""),
        "ex_fixed_prep": ex.get("fixed_preposition", ""),
        "ex_present": ex.get("present", ""),
        "ex_learner_note": ex.get("learner_note", "Mainly in the north; elsewhere people say …"),
        "ex_everyday": ex.get("everyday_word", "The everyday word is …"),
        "learner": L.get("learner", "a learner"),
        "gloss_language": L.get("gloss_language", "English"),
        "varieties": ", ".join(f"`{v}`" for v in L.get("varieties", [])),
        "mainstream": L.get("mainstream", ""),
        "regions": ", ".join(f"`{r}`" for r in L.get("regions", [])),
        "topics": ", ".join(L.get("topics", [])),
        "keep": L.get("keep", ""),
        "drop": L.get("drop", ""),
        "tl_main": tr.get("main", "a learner-friendly romanisation") or "\"\" (no romanisation: the script is enough)",
        "tl_main_rules": tr.get("main_rules", ""),
        "tl_alt": tr.get("alt", "a scholarly transliteration") or "\"\"",
        "picture_rules": _bullets(pics.get("rules", [])),
        "picture_skip": pics.get("skip", "words a picture can't show"),
        "sources": _bullets([*(f"{c['name']}" + (f": {c['notes']}" if c.get("notes") else "") for c in ev.get("corpora", [])),
                             *(f"{d['name']}" + (f" ({d['notes']})" if d.get("notes") else "") for d in dicts)])
        or "- (none configured: rely on the web and your knowledge, and say so)",
        "web_search": bool(ev.get("web_search")),
        "web_searches": ev.get("web_searches_per_item", 2),
    }


@cache
def _raw(name: str) -> str:
    return (DIR / f"{name}.md").read_text()


def render(name: str, **extra) -> str:
    """The prompt `name` with config values (and `extra`, which win) filled in."""
    vals = {**context(), **extra}
    text = re.sub(r"\{\{>\s*(\w[\w-]*)\s*\}\}", lambda m: _raw(f"_{m.group(1)}"), _raw(name))

    def section(m):
        return m.group(2) if vals.get(m.group(1)) else ""

    while True:   # innermost sections first, so they can nest
        new = re.sub(r"\{\{#(\w+)\}\}((?:(?!\{\{#).)*?)\{\{/\1\}\}", section, text, flags=re.S)
        if new == text:
            break
        text = new
    missing = set(re.findall(r"\{\{(\w+)\}\}", text)) - set(vals)
    if missing:
        raise KeyError(f"prompt {name}: no value for {sorted(missing)}")
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals[m.group(1)]), text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def schema(name: str) -> dict:
    return SCHEMAS[name]


def ask(name: str, id: str, parts: list, run: dict | None = None, **kw):
    """An `Ask` for prompt `name`: rendered prompt (with run-wide values `run`) as the cached system prompt, the
    prompt's answer schema, and this item's `parts`. Extra keywords go to `Ask` (max_tokens, effort)."""
    from panko.providers.base import Ask
    return Ask(id=id, system=render(name, **(run or {})), parts=parts, schema=schema(name), **kw)
