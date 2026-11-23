"""Ingest an extraction (what a source taught) into the store.

An extraction is JSON:
  {"source": {"id", "kind", "title", "date", "path", "trust"},
   "items": [{"kind": "word"|"phrase", "variety", "ar", "tl", "tl_alt", "gloss", ...entry fields,
              "role": "taught"|"corrected"|"used", "said": {"ar", "tl", "en"}, "batch": 1}]}

Items Panko already has get a sighting (and the sentence as an extra example if it's new).
New items become candidates. `activate` promotes candidates to active so they sync to Anki.
An item from an old Anki deck carries `origin` {"deck", "nid", "studied"}; studied ones are never
activated, because Phase 6 converts the old note in place so its review history survives.
Today the extraction is written by Claude in chat; an LLM provider can write the same file later.
"""
from __future__ import annotations

import json
from pathlib import Path

from panko.store import Store
from panko.store.normalize import bare

ENTRY_KEYS = {"kind", "variety", "ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "root",
              "pattern", "form", "present", "imperative", "masdar", "examples", "related", "notes", "usage", "literal",
              "tags", "cards", "image", "ar_prompt", "ar_bare", "batch", "region", "check", "origin"}


def ingest(path: Path | str | dict, store: Store | None = None, verdicts: dict | None = None,
           overrides: dict | None = None) -> dict:
    """`path`: an extraction file, or the extraction itself. `verdicts`/`overrides`: see panko.ingest.verify; they're
    applied to the items first. An item with `entry_id` is a sighting of that entry (no lookup)."""
    from panko.ingest.verify import apply

    store = store or Store()
    x = json.loads(json.dumps(path)) if isinstance(path, dict) else json.loads(Path(path).read_text())
    x["items"] = apply(x["items"], verdicts, overrides)
    src = x["source"]
    store.add_source(src["id"], src["kind"], src["title"], src.get("date", ""), src.get("path", ""), src.get("trust", 50))
    new, known = [], []
    for it in x["items"]:
        said = it.get("said") or {}
        # `homograph`: same bare letters and POS as another entry but a different word (وصل wSel / وصّل weSSel)
        if it.get("entry_id"):
            existing = store.get(it["entry_id"])
        else:
            existing = None if it.get("homograph") else store.find(it["ar"], it["variety"], it.get("pos"))
        if existing:
            eid = existing["id"]
            have = {bare(e["ar"]) for e in existing.get("examples", [])}   # same sentence, harakat aside
            extra = [{**said, "source": src["title"]}] if said.get("ar") else []
            extra += [{**ex, "source": ex.get("source") or src["title"]} for ex in it.get("examples", [])
                      if "written by Panko" not in (ex.get("source") or "")]   # a known card gets only real sentences
            extra = [ex for ex in extra if ex.get("ar") and bare(ex["ar"]) not in have and not have.add(bare(ex["ar"]))]
            if extra:
                existing.setdefault("examples", []).extend(extra)
                store.put(existing)
            known.append(it["ar"])
        else:
            e = {k: v for k, v in it.items() if k in ENTRY_KEYS}
            e["id"] = store.next_id(it["kind"], it["variety"])
            e.setdefault("sources", [src["title"]])
            e.setdefault("tags", []).append(f"src::{src['kind']}::{src.get('tag') or src.get('date', '')}")
            if said.get("ar") and not e.get("examples"):
                e["examples"] = [{**said, "source": src["title"]}]
            eid = store.put(e, status="candidate")
            new.append(it["ar"])
        store.add_sighting(eid, src["id"], it.get("role", "taught"), it.get("speaker", "teacher"),
                           said.get("ar", ""), said.get("tl", ""), said.get("en", ""),
                           json.dumps(it["origin"]) if it.get("origin") else "")
    return {"source": src["id"], "new": new, "known": known}


def activate(store: Store, ids: list[str] | None = None, batch: int | None = None) -> list[str]:
    """Candidates → active (cards on the next sync), by id or batch. Doubtful ones stay in the store until cleared:
    a batch skips them, and naming one by id is the learner clearing it."""
    done = []
    for e in store.entries("candidate"):
        if (e.get("origin") or {}).get("studied"):
            continue  # studied old-deck notes are migrated with their history (Phase 6), not re-added
        if "panko::doubtful" in e.get("tags", []) and not (ids and e["id"] in ids):
            continue
        if (ids and e["id"] in ids) or (batch is not None and e.get("batch") == batch):
            if "panko::doubtful" in e.get("tags", []):    # cleared by the learner
                store.put({**e, "tags": [t for t in e["tags"] if t != "panko::doubtful"]})
            store.set_status(e["id"], "active")
            done.append(e["id"])
    return done
