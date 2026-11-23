"""Push active store entries to Anki, updating notes in place (history kept).

- New entry -> add a note and remember its note ID.
- Changed entry -> update fields (never MyNotes), add tags, move cards to the right deck.
- Unchanged -> skip (hash of the rendered note).
Media referenced by the notes is stored first; sandbox media no longer used is removed.
"""
from __future__ import annotations

import base64
import json
import re

from panko.anki import mcp_client as mcp
from panko.cards import build as B
from panko.cards import note_types as T
from panko.config import ROOT
from panko.media import audio
from panko.store import Store

PREFIX = "_panko_proto_"
MEDIA_DIRS = [ROOT / "assets" / "sandbox" / "media", ROOT / "data" / "media", audio.MEDIA]


def tool(name, args):
    r = mcp.call(name, args)
    res = r.get("result", {})
    if res.get("isError"):
        raise RuntimeError(f"{name}: {res['content'][0]['text'][:500]}")
    return res.get("structuredContent") or json.loads(res["content"][0]["text"])


def push_models():
    existing = set(tool("model_names", {})["modelNames"])
    for name, fields, tmpls in [(T.WORD_MODEL, T.WORD_FIELDS, T.WORD_TEMPLATES),
                                (T.PHRASE_MODEL, T.PHRASE_FIELDS, T.PHRASE_TEMPLATES)]:
        if name in existing:
            tool("update_model_templates", {"model_name": name,
                                            "templates": {t["Name"]: {"Front": t["Front"], "Back": t["Back"]} for t in tmpls}})
            tool("update_model_styling", {"model_name": name, "css": T.CSS})
        else:
            tool("create_model", {"model_name": name, "in_order_fields": fields, "card_templates": tmpls, "css": T.CSS})


def push_media(notes: list[dict]) -> tuple[int, int]:
    blob = json.dumps(notes, ensure_ascii=False)
    used = set(re.findall(rf"({re.escape(PREFIX)}[\w.-]+?\.(?:mp3|jpg|jpeg|png|svg|webp))", blob))
    files = {f.name: f for d in MEDIA_DIRS if d.exists() for f in d.iterdir() if f.name in used}
    for name, f in sorted(files.items()):
        try:
            tool("store_media_file", {"filename": name, "path": str(f)})
        except RuntimeError:
            tool("store_media_file", {"filename": name, "data": base64.b64encode(f.read_bytes()).decode()})
    stale = [n for n in tool("get_media_files_names", {"pattern": f"{PREFIX}*"})["files"] if n not in used]
    for n in stale:
        tool("delete_media_file", {"filename": n})
    missing = used - set(files)
    if missing:
        print("missing media:", sorted(missing))
    return len(files), len(stale)


def sync(store: Store | None = None, narrator: audio.Narrator | None = None) -> dict:
    store = store or Store()
    narrator = narrator or audio.Narrator(prefix=PREFIX)
    entries = store.entries("active")
    notes = {e["id"]: B.to_note(e, narrator) for e in entries}   # audio generated here, before Anki is touched
    mcp.init()
    push_models()
    for d in set(B.DECKS.values()):
        tool("create_deck", {"deck_name": d})
    stored, stale = push_media(list(notes.values()))
    added = updated = same = 0
    for eid, note in notes.items():
        h = B.note_hash(note)
        link = store.link(eid)
        nid = link["note_id"] if link else None
        if nid is None:
            found = tool("find_notes", {"query": f'"PankoID:{eid}"'})["noteIds"]
            nid = found[0] if found else None
        if nid is None:
            tool("add_note", {"deck_name": note["deck"], "model_name": note["model"],
                              "fields": {**note["fields"], "MyNotes": ""}, "tags": note["tags"],
                              "allow_duplicate": True})  # homographs (دار house / to do / to turn); PankoID is the key
            nid = tool("find_notes", {"query": f'"PankoID:{eid}"'})["noteIds"][0]
            store.set_link(eid, nid, h)
            added += 1
            continue
        if link and link["rendered_hash"] == h:
            same += 1
            continue
        fields = {k: v for k, v in note["fields"].items() if k not in ("Spare3", "Spare4")}  # old Front/Back of migrated notes
        tool("update_notes", {"notes": [{"id": nid, "fields": fields}]})
        tool("tag_add", {"note_ids": [nid], "tags": " ".join(note["tags"])})
        cards = tool("notes_info", {"notes": [nid]})["notes"][0]["cards"]
        tool("card_change_deck", {"card_ids": cards, "deck": note["deck"]})
        store.set_link(eid, nid, h)
        updated += 1
    res = {"added": added, "updated": updated, "unchanged": same, "media": stored, "stale_media_removed": stale}
    print(res)
    return res
