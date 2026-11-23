"""Export an Anki deck's notes (read-only) so its rows can be worked through as a source.

Writes {"deck", "notes": [{nid, model, tags, fields {name: html}, studied}]}: the shape `panko.ingest.decks` reads.
`studied` = any of the note's cards has been reviewed (Anki's `-is:new`), so Panko never adds those notes again;
`panko migrate` converts them in place with their history instead.
"""
from __future__ import annotations

import json
from pathlib import Path


def export_deck(name: str, path: Path) -> dict:
    from panko.anki import mcp_client as mcp
    from panko.anki.sync import tool
    mcp.init()
    q = 'deck:"' + name.replace('"', '\\"') + '"'
    ids = tool("find_notes", {"query": q}).get("noteIds", [])
    if not ids:
        raise ValueError(f"no notes in an Anki deck called {name!r}")
    studied = set(tool("find_notes", {"query": q + " -is:new"}).get("noteIds", []))
    notes = []
    for i in range(0, len(ids), 100):
        for n in tool("notes_info", {"notes": ids[i:i + 100]})["notes"]:
            fields = sorted(n["fields"].items(), key=lambda kv: kv[1].get("order", 0) if isinstance(kv[1], dict) else 0)
            notes.append({"nid": n["noteId"], "model": n.get("modelName", ""), "tags": n.get("tags", []),
                          "fields": {k: v["value"] if isinstance(v, dict) else v for k, v in fields},
                          "studied": n["noteId"] in studied})
    out = {"deck": name, "notes": notes}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False))
    return out
