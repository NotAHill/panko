"""Phase 6: turn the old-deck notes you studied into Panko notes in place, so their review history stays.

Uses the official `anki` library (extra `migrate`, pinned to the desktop version) on the collection file, with Anki
closed: the MCP add-on can't change note types, and Change Note Type forces one full sync.

For each studied store entry (origin.notes[].nid), the old note:
- changes note type to Panko Word/Phrase; each old card keeps its id, reviews and schedule, mapped by direction:
  Arabic on the front → Recognition, English on the front → Production;
- keeps its old Front/Back verbatim in Spare3/Spare4 (hidden; nothing of yours is lost);
- gets the rendered Panko fields (never MyNotes), Panko tags on top of its own, and moves to Panko Sandbox;
- is linked in the store, so `panko sync` updates it in place from then on.
A note that fed two entries goes to the first; the second entry becomes a new note on the next `panko sync`.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from panko.anki.sync import MEDIA_DIRS, PREFIX
from panko.cards import build as B
from panko.cards import note_types as T

COLLECTION = Path.home() / "Library/Application Support/Anki2/User 1/collection.anki2"
KEEP = ("Spare3", "Spare4")   # old Front, old Back

# old note type → (old card ord → Panko card) by which side the old card shows first
CARD_MAP = {
    "Basic (and reversed card)++": {0: "recognition", 1: "production"},
    "Basic (and reversed card)+++": {0: "recognition", 1: "production"},
    "Darija Vocab": {0: "recognition", 1: "production"},
    "Basic++": {0: "recognition"},
    "Basic-64524": {0: "production"},   # front {{English}}
}
TEMPLATE_INDEX = {"recognition": 0, "production": 1}


def anki_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Anki"], capture_output=True).returncode == 0


def plan(store, col) -> list[dict]:
    """One row per old note to convert. Raises on an old note type with no card map."""
    rows, taken = [], set()
    for e in sorted(store.entries("candidate"), key=lambda x: x["id"]):
        olds = [n for n in (e.get("origin") or {}).get("notes", []) if n.get("studied") and n.get("nid")]
        if not olds:
            continue
        nid = olds[0]["nid"]
        if nid not in taken and col.get_note(nid).note_type()["name"] in (T.WORD_MODEL, T.PHRASE_MODEL):
            taken.add(nid)   # converted in an earlier run (e.g. the test batch) for the entry it fed first
        if nid in taken:
            rows.append({"eid": e["id"], "nid": None, "ar": e["ar"], "gloss": e.get("gloss", ""), "shared_with": nid})
            continue
        taken.add(nid)
        note = col.get_note(nid)
        old_model = note.note_type()["name"]
        if old_model not in CARD_MAP:
            raise ValueError(f"{e['id']}: no card map for note type {old_model!r}")
        cards = [{"cid": c.id, "ord": c.ord, "to": CARD_MAP[old_model][c.ord], "reps": c.reps,
                  "deck": col.decks.name(c.did)} for c in note.cards()]
        rows.append({"eid": e["id"], "nid": nid, "ar": e["ar"], "gloss": e.get("gloss", ""), "kind": e["kind"],
                     "old_model": old_model, "old_fields": dict(note.items()), "cards": cards})
    return rows


def _cards_for(entry: dict, row: dict) -> list[str]:
    """Panko's card switches, plus any card the old note already reviewed (its history must keep a front)."""
    want = list(entry.get("cards", B.DEFAULT_CARDS))
    for c in row["cards"]:
        if c["reps"] and c["to"] not in want:
            want.append(c["to"])
    return want


def _copy_media(note: dict, media_dir: Path) -> list[str]:
    import json
    used = set(re.findall(rf"({re.escape(PREFIX)}[\w.-]+?\.(?:mp3|jpg|jpeg|png|svg|webp))", json.dumps(note, ensure_ascii=False)))
    missing = []
    for name in sorted(used):
        src = next((d / name for d in MEDIA_DIRS if (d / name).exists()), None)
        if src is None:
            missing.append(name)
        elif not (media_dir / name).exists():
            shutil.copy2(src, media_dir / name)
    return missing


def convert(store, col, rows: list[dict], narrator=None) -> dict:
    """Change note type, fill fields, move cards, link in the store. `rows` from `plan` (a subset is fine)."""
    from anki.models import ChangeNotetypeRequest  # noqa: F401  (pylib present)

    todo = [r for r in rows if r.get("nid")]
    models = {"word": col.models.by_name(T.WORD_MODEL), "phrase": col.models.by_name(T.PHRASE_MODEL)}
    # 1. change note type, grouped by (old type, new type)
    groups: dict[tuple, list[dict]] = {}
    for r in todo:
        groups.setdefault((r["old_model"], r["kind"]), []).append(r)
    for (old_name, kind), rs in groups.items():
        old, new = col.models.by_name(old_name), models[kind]
        info = col.models.change_notetype_info(old_notetype_id=old["id"], new_notetype_id=new["id"])
        req = info.input
        n_old = len(old["flds"])   # old field i → KEEP[i] (Spare3 = old first field, Spare4 = old second)
        req.new_fields[:] = [KEEP.index(f["name"]) if f["name"] in KEEP and KEEP.index(f["name"]) < n_old else -1
                             for f in new["flds"]]
        tmpl = [-1] * len(new["tmpls"])
        for ord_, card in CARD_MAP[old_name].items():
            tmpl[TEMPLATE_INDEX[card]] = ord_
        req.new_templates[:] = tmpl
        req.note_ids[:] = [r["nid"] for r in rs]
        col.models.change_notetype_of_notes(req)
    # 2. fields, tags, media, deck, store link
    media_dir = Path(col.media.dir())
    missing = []
    for r in todo:
        e = store.get(r["eid"])
        e["cards"] = _cards_for(e, r)
        e["status"] = "active"
        rendered = B.to_note(e, narrator) if narrator else B.to_note(e)
        note = col.get_note(r["nid"])
        for k, v in rendered["fields"].items():
            if k not in KEEP:
                note[k] = v
        for t in rendered["tags"]:
            note.add_tag(t)
        col.update_note(note)
        unwanted = [c.id for c in note.cards() if c.ord not in {TEMPLATE_INDEX.get(x, -1) for x in e["cards"]}
                    and c.ord in TEMPLATE_INDEX.values() and c.reps == 0]   # never-reviewed old card for a card type that's off
        if unwanted:
            col.remove_cards_and_orphaned_notes(unwanted)
        missing += _copy_media(rendered, media_dir)
        did = col.decks.id(rendered["deck"])
        col.set_deck([c.id for c in note.cards()], did)
        store.put(e, "active")
        store.set_link(r["eid"], r["nid"], B.note_hash(rendered))
    # 3. the second entry of a shared note becomes a new note on the next sync
    for r in rows:
        if not r.get("nid") and r.get("shared_with"):
            store.set_status(r["eid"], "active")
    return {"converted": len(todo), "new_on_next_sync": sum(1 for r in rows if not r.get("nid")),
            "missing_media": sorted(set(missing))}


def report(rows: list[dict]) -> str:
    """The dry-run list, as Markdown."""
    name = {"recognition": "Recognition", "production": "Production"}
    out = ["| Entry | Word | Meaning | Old deck · note type | Cards (reviews) → Panko |", "|---|---|---|---|---|"]
    for r in rows:
        if not r.get("nid"):
            out.append(f"| {r['eid']} | {r['ar']} | {r['gloss']} | shares note {r['shared_with']} | new note on next sync |")
            continue
        cards = ", ".join(f"{c['ord'] + 1} ({c['reps']}) → {name[c['to']]}" for c in sorted(r["cards"], key=lambda c: c["ord"]))
        deck = r["cards"][0]["deck"] if r["cards"] else ""
        out.append(f"| {r['eid']} | {r['ar']} | {r['gloss']} | {deck} · {r['old_model']} | {cards} |")
    return "\n".join(out)


def run(dry_run: bool = True, ids: list[str] | None = None, collection: Path = COLLECTION,
        scratch: Path | None = None, store=None, narrator=None) -> dict:
    """Dry run: plan against a throwaway copy (safe with Anki open). Real run: Anki must be closed; backs up first."""
    import tempfile
    import time

    from anki.collection import Collection

    from panko.store import Store

    st = store or Store()
    base = scratch or (Path("/Volumes/external_ssd/panko-scratch") if Path("/Volumes/external_ssd").exists()
                       else Path(tempfile.gettempdir()))
    base.mkdir(parents=True, exist_ok=True)
    if dry_run:
        tmp = Path(tempfile.mkdtemp(dir=base))
        for suffix in ("", "-wal"):
            if Path(f"{collection}{suffix}").exists():
                shutil.copy2(f"{collection}{suffix}", tmp / f"collection.anki2{suffix}")
        path = tmp / "collection.anki2"
    else:
        if anki_running():
            raise SystemExit("Close Anki first (Change Note Type needs the collection to itself).")
        backup = base / f"collection-before-phase6-{time.strftime('%Y%m%d-%H%M%S')}.anki2"
        shutil.copy2(collection, backup)
        print("backup:", backup)
        path = collection
    col = Collection(str(path))
    try:
        rows = plan(st, col)
        if ids:
            rows = [r for r in rows if r["eid"] in ids]
        if dry_run:
            return {"rows": rows, "report": report(rows)}
        if narrator is None:
            from panko.media import audio
            narrator = audio.Narrator(prefix=PREFIX)
        return {"rows": rows, **convert(st, col, rows, narrator)}
    finally:
        col.close()
        if dry_run:
            shutil.rmtree(path.parent, ignore_errors=True)
