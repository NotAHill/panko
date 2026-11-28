"""Panko sync: the part that writes to your collection. Only Anki's own library (no Qt), so it can be tried on a
scratch collection outside Anki.

The rules (docs/SPEC-hosted.md, "The Anki add-on"):
- only Panko's own note types and the notes that hold a Panko card are touched;
- MyNotes is yours and never written; nothing is deleted; scheduling and review history are never changed;
- a note type whose fields or card types differ from Panko's is refused, never changed (that would force a full
  sync); templates and styling are updated in place (a normal sync);
- a note that already holds a Panko card is updated where it is (its deck too: moving it is yours to do);
- the whole sync is one step in Edit → Undo.
"""
from __future__ import annotations

NEVER = {"MyNotes"}                 # yours
KEEP_IF_SET = {"Spare3", "Spare4"}  # notes converted from an old deck keep their old Front/Back here
ID = "PankoID"


class Refused(Exception):
    """Something the add-on won't do to your collection; the message says what and why."""


def _field_names(m: dict) -> list[str]:
    return [f["name"] for f in m["flds"]]


def ensure_models(col, specs: list[dict]) -> dict[str, dict]:
    """Panko's note types as the server describes them: made if missing, templates and styling brought up to date
    if not, refused if their fields or card types differ. {name: note type}."""
    mm, out = col.models, {}
    for s in specs:
        m = mm.by_name(s["name"])
        if m is None:
            m = mm.new(s["name"])
            for f in s["fields"]:
                mm.add_field(m, mm.new_field(f))
            for t in s["templates"]:
                tt = mm.new_template(t["name"])
                tt["qfmt"], tt["afmt"] = t["front"], t["back"]
                mm.add_template(m, tt)
            m["css"] = s["css"]
            mm.add_dict(m)
            out[s["name"]] = mm.by_name(s["name"])
            continue
        if _field_names(m) != list(s["fields"]):
            raise Refused(f"the note type “{s['name']}” in your Anki has other fields than Panko's. Changing them "
                          "would force a full sync, so nothing was written. Rename that note type in Anki "
                          "(Tools → Manage Note Types) and sync again: Panko then makes its own.")
        if [t["name"] for t in m["tmpls"]] != [t["name"] for t in s["templates"]]:
            raise Refused(f"the note type “{s['name']}” in your Anki has other card types than Panko's. Changing "
                          "them would force a full sync, so nothing was written. Rename that note type in Anki "
                          "and sync again.")
        changed = m["css"] != s["css"]
        m["css"] = s["css"]
        for t, want in zip(m["tmpls"], s["templates"]):  # noqa: B905  same length, checked above (and Anki 2.1.5x has Python 3.9)
            if t["qfmt"] != want["front"] or t["afmt"] != want["back"]:
                t["qfmt"], t["afmt"] = want["front"], want["back"]
                changed = True
        if changed:
            mm.update_dict(m)
            m = mm.by_name(s["name"])
        out[s["name"]] = m
    return out


def held(col, model_names: list[str]) -> dict[str, int]:
    """{Panko id: note id} for the notes in your collection that hold a Panko card: those of these note types, and
    notes imported from a Panko .apkg (their guid starts with "panko-")."""
    out: dict[str, int] = {}
    fields: dict[int, int | None] = {}

    def at(mid: int) -> int | None:
        if mid not in fields:
            m = col.models.get(mid)
            names = _field_names(m) if m else []
            fields[mid] = names.index(ID) if ID in names else None
        return fields[mid]

    mids = [m["id"] for name in model_names if (m := col.models.by_name(name))]
    rows = []
    if mids:
        rows += col.db.all(f"select id, mid, flds from notes where mid in ({','.join(str(int(x)) for x in mids)})")
    rows += col.db.all("select id, mid, flds from notes where guid like 'panko-%'")
    for nid, mid, flds in rows:
        i = at(mid)
        if i is None:
            continue
        parts = flds.split("\x1f")
        pid = parts[i].strip() if i < len(parts) else ""
        if pid:
            out.setdefault(pid, nid)
    return out


def write(col, notes: list[dict], models: dict[str, dict], have: dict[str, int]) -> dict:
    """Write these rendered notes: update the note that holds each card, or add one in its deck. Returns what
    happened and {Panko id: {"nid", "hash"}} for the server."""
    links, added, updated, same, failed = {}, 0, 0, 0, []
    changed_notes = []
    for n in notes:
        note = None
        if n["id"] in have:
            try:
                note = col.get_note(have[n["id"]])
            except Exception:  # noqa: BLE001  deleted since it was read: add it again
                note = None
        if note is not None:
            dirty = False
            for k, v in n["fields"].items():
                if k in NEVER or k not in note:
                    continue
                if k in KEEP_IF_SET and note[k] and not v:
                    continue
                if note[k] != v:
                    note[k] = v
                    dirty = True
            for t in n["tags"]:                 # tags are only added: one you removed in Anki may come back,
                if not note.has_tag(t):         # one you added stays
                    note.add_tag(t)
                    dirty = True
            if dirty:
                changed_notes.append(note)
                updated += 1
            else:
                same += 1
            links[n["id"]] = {"nid": note.id, "hash": n["hash"]}
            continue
        m = models.get(n["model"])
        if m is None:
            failed.append(n["id"])
            continue
        note = col.new_note(m)
        for k, v in n["fields"].items():
            if k in note and k not in NEVER:
                note[k] = v
        note.tags = list(n["tags"])
        if n.get("guid"):
            note.guid = n["guid"]
        try:
            col.add_note(note, col.decks.id(n["deck"]))
        except Exception:  # noqa: BLE001  e.g. its card switches make no card at all
            failed.append(n["id"])
            continue
        added += 1
        links[n["id"]] = {"nid": note.id, "hash": n["hash"]}
    if changed_notes:
        col.update_notes(changed_notes)
    return {"added": added, "updated": updated, "unchanged": same, "failed": failed, "links": links}


def run(col, panko, say=lambda text: None, version: int = 1, rounds: int = 200) -> dict:
    """One whole sync with your Panko (`panko`: `call(path, body)` and `media(name)`, net.Panko in Anki): note
    types, then rounds of notes until nothing is left, media first. One undo step."""
    pos = col.add_custom_undo_entry("Panko sync")
    first = panko.call("/anki/pull", {"addon": version, "page": 0, "have": {}})
    models = ensure_models(col, first["models"])
    names = [m["name"] for m in first["models"]]
    total = {"added": 0, "updated": 0, "unchanged": 0, "failed": [], "media": 0, "media_missing": 0,
             "audio_not_made": 0}
    skip: list[str] = []
    for _ in range(rounds):
        have = held(col, names)
        r = panko.call("/anki/pull", {"addon": version, "have": have, "skip": skip})
        total["audio_not_made"] = r.get("audio_not_made", 0)
        if not r["notes"]:
            total["unchanged"] += r.get("unchanged", 0) if not (total["added"] or total["updated"]) else 0
            break
        missing = set()
        for name in r["media"]:
            if col.media.have(name):
                continue
            try:
                col.media.write_data(name, panko.media(name))
                total["media"] += 1
            except Exception:  # noqa: BLE001  one missing file doesn't stop the sync; the card shows without it
                missing.add(name)
                total["media_missing"] += 1
        w = write(col, r["notes"], models, have)
        # a note whose file didn't come isn't reported as done, so the next sync sends it (and asks for it) again
        short = {n["id"] for n in r["notes"] if any(m in v for m in missing for v in n["fields"].values())}
        panko.call("/anki/done", {"links": {k: v for k, v in w["links"].items() if k not in short}})
        skip += w["failed"] + sorted(short)
        for k in ("added", "updated"):
            total[k] += w[k]
        total["failed"] += w["failed"]
        say(f"{total['added']} added, {total['updated']} updated" + (f", {r['more']} to go" if r.get("more") else ""))
        if not r.get("more"):
            break
    total["changes"] = col.merge_undo_entries(pos)
    return total
