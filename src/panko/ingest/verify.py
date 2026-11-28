"""Apply verification verdicts (and hand-made overrides) to extraction items before ingest.

A verdict file is a list of records keyed like `item_key()`:
  {"key", "verdict": ok|regional|uncommon|fix|doubtful|drop, "region", "register", "usual_word",
   "learner_note", "fix": {field: value, "example_ar"|"example_tl"|"example_en": ...}, "evidence", "summary"}

- drop: the item is skipped.
- fix: fields are replaced (example_* fix the item's sentence).
- learner_note: appended to gloss_note (words) or usage (phrases); it shows on the card back.
- regional: tag region::<place>. doubtful: tag panko::doubtful.
- The verdict itself is kept on the entry as `check` (never rendered).

Overrides are {key: {field: value} | {"drop": true}}, applied last; used for merges and for
synonyms that get the recognition card only ({"cards": ["recognition"]}).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from panko.store.normalize import strip_article

FIXABLE = {"ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "present", "imperative",
           "literal", "usage", "notes", "related", "cards"}


def item_key(it: dict) -> str:
    return strip_article(it["ar"]) + "|" + (it.get("pos", "") if it["kind"] == "word" else "phrase")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def load_verdicts(paths) -> dict[str, dict]:
    out = {}
    for p in paths or []:
        for r in json.loads(Path(p).read_text(encoding="utf-8")):
            out[r["key"]] = r
    return out


def _fix_example(it: dict, ex: dict) -> None:
    if it.get("said"):
        it["said"] = {**it["said"], **ex}
    elif it.get("examples"):
        it["examples"] = [{**it["examples"][0], **ex}, *it["examples"][1:]]
    elif {"ar", "en"} <= ex.keys():
        it["examples"] = [{**ex, "source": "written by Panko, not yet checked"}]


def apply(items: list[dict], verdicts: dict[str, dict] | None = None,
          overrides: dict[str, dict] | None = None) -> list[dict]:
    verdicts, overrides = verdicts or {}, overrides or {}
    out = []
    for it in items:
        k = item_key(it)
        it = json.loads(json.dumps(it))
        v = verdicts.get(k)
        if v:
            if v.get("verdict") == "drop":
                continue
            fix = dict(v.get("fix") or {})
            ex = {f: fix.pop(f"example_{f}") for f in ("ar", "tl", "en") if f"example_{f}" in fix}
            if ex:
                _fix_example(it, ex)
            it.update({f: val for f, val in fix.items() if f in FIXABLE})
            note = (v.get("learner_note") or "").strip()
            if note:
                field = "gloss_note" if it["kind"] == "word" else "usage"
                it[field] = f"{it[field]}. {note}" if it.get(field) else note
            tags = it.setdefault("tags", [])
            if v.get("verdict") == "regional" and v.get("region"):
                tags.append(f"region::{slug(v['region'])}")
            if v.get("verdict") == "doubtful":
                tags.append("panko::doubtful")
            it["region"] = v.get("region", "")
            it["check"] = {f: v[f] for f in ("verdict", "register", "usual_word", "summary", "evidence") if v.get(f)}
        o = overrides.get(k)
        if o:
            if o.get("drop"):
                continue
            it.update({f: val for f, val in o.items() if f != "note"})
        out.append(it)
    return out
