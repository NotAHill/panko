"""Ingest an extraction (what a source taught) into the store.

An extraction is JSON:
  {"source": {"id", "kind", "title", "date", "path", "trust"},
   "items": [{"kind": "word"|"phrase", "variety", "ar", "tl", "tl_alt", "gloss", ...entry fields,
              "role": "taught"|"corrected"|"used", "said": {"ar", "tl", "en"}, "batch": 1}]}

Items Panko already has get a sighting (and the sentence as an extra example if it's new).
New items become candidates. `activate` promotes candidates to active so they sync to Anki.
Today the extraction is written by Claude in chat; an LLM provider can write the same file later.
"""
from __future__ import annotations

import json
from pathlib import Path

from panko.store import Store

ENTRY_KEYS = {"kind", "variety", "ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "root",
              "pattern", "form", "present", "imperative", "masdar", "examples", "related", "notes", "usage", "literal",
              "tags", "cards", "image", "ar_prompt", "ar_bare", "batch"}


def ingest(path: Path | str, store: Store | None = None) -> dict:
    store = store or Store()
    x = json.loads(Path(path).read_text())
    src = x["source"]
    store.add_source(src["id"], src["kind"], src["title"], src.get("date", ""), src.get("path", ""), src.get("trust", 50))
    new, known = [], []
    for it in x["items"]:
        said = it.get("said") or {}
        existing = store.find(it["ar"], it["variety"])
        if existing:
            eid = existing["id"]
            if said.get("ar") and all(e["ar"] != said["ar"] for e in existing.get("examples", [])):
                existing.setdefault("examples", []).append({**said, "source": src["title"]})
                store.put(existing)
            known.append(it["ar"])
        else:
            e = {k: v for k, v in it.items() if k in ENTRY_KEYS}
            e["id"] = store.next_id(it["kind"], it["variety"])
            e.setdefault("sources", [src["title"]])
            e.setdefault("tags", []).append(f"src::{src['kind']}::{src.get('date', '')}")
            if said.get("ar") and not e.get("examples"):
                e["examples"] = [{**said, "source": src["title"]}]
            eid = store.put(e, status="candidate")
            new.append(it["ar"])
        store.add_sighting(eid, src["id"], it.get("role", "taught"), it.get("speaker", "teacher"),
                           said.get("ar", ""), said.get("tl", ""), said.get("en", ""))
    return {"source": src["id"], "new": new, "known": known}


def activate(store: Store, ids: list[str] | None = None, batch: int | None = None) -> list[str]:
    done = []
    for e in store.entries("candidate"):
        if (ids and e["id"] in ids) or (batch is not None and e.get("batch") == batch):
            store.set_status(e["id"], "active")
            done.append(e["id"])
    return done
