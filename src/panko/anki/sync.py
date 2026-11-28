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
    for name, fields, tmpls in [(T.WORD_MODEL, T.WORD_FIELDS, T.word_templates()),
                                (T.PHRASE_MODEL, T.PHRASE_FIELDS, T.phrase_templates())]:
        if name in existing:
            tool("update_model_templates", {"model_name": name,
                                            "templates": {t["Name"]: {"Front": t["Front"], "Back": t["Back"]} for t in tmpls}})
            tool("update_model_styling", {"model_name": name, "css": T.css()})
        else:
            tool("create_model", {"model_name": name, "in_order_fields": fields, "card_templates": tmpls, "css": T.css()})


def _media_names(notes: list[dict]) -> set[str]:
    return set(re.findall(rf"({re.escape(PREFIX)}[\w.-]+?\.(?:mp3|jpg|jpeg|png|svg|webp))",
                          json.dumps(notes, ensure_ascii=False)))


def push_media(notes: list[dict]) -> int:
    used = _media_names(notes)
    files = {f.name: f for d in MEDIA_DIRS if d.exists() for f in d.iterdir() if f.name in used}
    for name, f in sorted(files.items()):
        try:
            tool("store_media_file", {"filename": name, "path": str(f)})
        except RuntimeError:
            tool("store_media_file", {"filename": name, "data": base64.b64encode(f.read_bytes()).decode()})
    missing = used - set(files)
    if missing:
        print("missing media:", sorted(missing))
    return len(files)


def _media_in_collection() -> set[str]:
    """Panko media any note in the open collection uses: this Panko's and another's (the add-on writes a server
    Panko's cards with the same file names), so a sync never deletes a picture another Panko's card shows."""
    from panko.anki.export import _note_ids
    ids = _note_ids('"PankoID:_*"')
    used: set[str] = set()
    for i in range(0, len(ids), 200):
        used |= _media_names(tool("notes_info", {"notes": ids[i:i + 200]}).get("notes", []))
    return used


def clean_media(used: set[str]) -> int:
    """Delete Panko media no note uses any more (Anki keeps them in its media trash)."""
    keep = used | _media_in_collection()
    stale = [n for n in tool("get_media_files_names", {"pattern": f"{PREFIX}*"})["files"] if n not in keep]
    for n in stale:
        tool("delete_media_file", {"filename": n})
    return len(stale)


def _right_collection(store: Store, entries: list[dict], sample: int = 25) -> None:
    """Stop before touching Anki when the open profile isn't the one this Panko syncs to: none of the notes it
    linked are there (Anki opens on the last profile used, e.g. a test one)."""
    nids = [link["note_id"] for e in entries if (link := store.link(e["id"]))][:sample]
    if nids and not tool("notes_info", {"notes": nids}).get("notes"):
        raise RuntimeError("Anki has a profile open that doesn't hold your Panko cards (none of the notes Panko "
                           "synced before are in it). Switch to your own profile (File → Switch Profile) and sync "
                           "again. Nothing was changed.")


def plan(store: Store | None = None) -> dict:
    """What `sync` would do, without touching Anki or paying for audio: notes to add or update (by the stored hash
    of what was last written) and the audio clips still to generate."""
    store = store or Store()
    narrator = audio.DryRun(prefix=PREFIX)
    add, update, same = [], [], 0
    for e in store.entries("active"):
        note = B.to_note(e, narrator)
        link = store.link(e["id"])
        if not link:
            add.append(e["id"])
        elif link["rendered_hash"] != B.note_hash(note):
            update.append(e["id"])
        else:
            same += 1
    chars = {}
    for prov, text in narrator.todo:
        chars[prov] = chars.get(prov, 0) + len(text)
    return {"add": add, "update": update, "unchanged": same, "audio_clips": len(narrator.todo),
            "audio_chars": chars}


def sync(store: Store | None = None, narrator: audio.Narrator | None = None) -> dict:
    store = store or Store()
    narrator = narrator or audio.Narrator(prefix=PREFIX)
    entries = store.entries("active")
    notes = {e["id"]: B.to_note(e, narrator) for e in entries}   # audio generated here, before Anki is touched
    mcp.init()
    _right_collection(store, entries)
    push_models()
    from panko.config import deck
    for d in {deck(e["variety"]) for e in entries}:
        tool("create_deck", {"deck_name": d})
    stored = push_media(list(notes.values()))
    added = updated = same = 0
    gone: list[str] = []
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
        info = tool("notes_info", {"notes": [nid]}).get("notes") or []
        if not info:                  # deleted in Anki: listed, not added back behind your back
            gone.append(eid)
            continue
        fields = {k: v for k, v in note["fields"].items() if k not in ("Spare3", "Spare4")}  # old Front/Back of migrated notes
        tool("update_notes", {"notes": [{"id": nid, "fields": fields}]})
        tool("tag_add", {"note_ids": [nid], "tags": " ".join(note["tags"])})
        tool("card_change_deck", {"card_ids": info[0]["cards"], "deck": note["deck"]})
        store.set_link(eid, nid, h)
        updated += 1
    stale = clean_media(_media_names(list(notes.values())))
    res = {"added": added, "updated": updated, "unchanged": same, "media": stored, "stale_media_removed": stale}
    if gone:
        res["deleted_in_anki"] = gone
    print(res)
    return res
