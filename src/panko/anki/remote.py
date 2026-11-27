"""The server's side of the Anki add-on ("Panko sync", `src/panko/anki_addon/`): what it asks, what Panko answers.

The add-on can't decide anything about a card: Panko renders each note here (the same `cards.build` as `panko sync`)
and the add-on writes it through Anki's own library. One sync is a few rounds:

1. `pull(have)`: the add-on sends which Panko card each Anki note holds ({Panko id: note id}, read from its
   collection); Panko answers its note types (fields fixed, templates and styling from your card design) and up to
   `PAGE` notes that are new or changed since the add-on last wrote them (the store's `anki` table), with the media
   they use.
2. The add-on fetches the media it lacks (`media_file`), writes the notes, then `done(links)` records which note
   holds each card, so the next pull leaves them out.

The note types are this Panko's own ("Panko • Word (Iraqi Arabic)"), so two Pankos feeding one Anki never overwrite
each other's card design. Audio isn't made here (a pull costs nothing): clips not made yet are left out, and the
note is sent again once they exist.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from panko.cards import build as B
from panko.cards import note_types as T
from panko.store import Store

PAGE = 300                 # notes per round: the first sync of a big deck is many rounds, each one a small answer
ADDON_VERSION = 1          # the add-on sends its own; an older one than `ADDON_MIN` is asked to update
ADDON_MIN = 1
MEDIA_NAME = re.compile(r"_panko_[\w.-]+\.(?:mp3|jpg|jpeg|png|svg|webp)")
MEDIA_REF = re.compile(r'\[sound:([^\]]+)\]|src="([^"]+)"')


def model_names() -> dict[str, str]:
    """This Panko's own note types, named after what it teaches: {"word": …, "phrase": …}."""
    from panko.config import settings
    lang = str(settings().get("learner", {}).get("language") or "").strip() or "Panko"
    return {"word": f"Panko • Word ({lang})", "phrase": f"Panko • Phrase ({lang})"}


def models() -> list[dict]:
    """The note types the add-on keeps: fields in their fixed order, and the templates and styling of your design."""
    names = model_names()
    css = T.css()
    return [{"kind": kind, "name": names[kind], "fields": fields, "css": css,
             "templates": [{"name": t["Name"], "front": t["Front"], "back": t["Back"]} for t in tmpls]}
            for kind, fields, tmpls in (("word", T.WORD_FIELDS, T.word_templates()),
                                        ("phrase", T.PHRASE_FIELDS, T.phrase_templates()))]


def guid(eid: str) -> str:
    """The same guid as an .apkg from Panko gives the card, so a note imported from one is updated, not copied."""
    from panko.anki.apkg import _guid
    return _guid(eid)


def _narrator():
    from panko.anki.apkg import _Made
    return _Made(personal=True)        # audio already made only (yours, including clips from your recordings)


def pull(have: dict[str, int], store: Store | None = None, skip: list[str] | None = None, page: int = PAGE) -> dict:
    """What the add-on should write next: notes it doesn't hold, or that changed since it last wrote them."""
    store = store or Store()
    names = model_names()
    have = {str(k): int(v) for k, v in (have or {}).items() if str(v).lstrip("-").isdigit()}
    skip = set(skip or [])
    narrator = _narrator()
    out, unchanged, waiting = [], 0, 0
    for e in store.entries("active"):
        if e["id"] in skip:
            continue
        note = B.to_note(e, narrator)
        h = B.note_hash(note)
        link = store.link(e["id"])
        if e["id"] in have and link and link["note_id"] == have[e["id"]] and link["rendered_hash"] == h:
            unchanged += 1
            continue
        if len(out) >= page:
            waiting += 1
            continue
        out.append({"id": e["id"], "guid": guid(e["id"]), "model": names["word" if note["model"] == T.WORD_MODEL else "phrase"],
                    "deck": note["deck"], "fields": note["fields"], "tags": note["tags"], "hash": h})
    media = sorted({a or b for n in out for a, b in MEDIA_REF.findall(" ".join(n["fields"].values()))
                    if MEDIA_NAME.fullmatch(a or b)})
    return {"addon_min": ADDON_MIN, "models": models(), "notes": out, "media": media, "unchanged": unchanged,
            "more": waiting, "audio_not_made": narrator.missing}


def media_file(name: str) -> Path | None:
    """One of Panko's media files, by name (nothing else on the disk can be asked for)."""
    if not MEDIA_NAME.fullmatch(name or ""):
        return None
    from panko.anki.sync import MEDIA_DIRS
    from panko.media import audio, clips
    for d in (*MEDIA_DIRS, audio.MEDIA, clips._media()):
        p = d / name
        if p.is_file():
            return p
    return None


def done(links: dict[str, dict], store: Store | None = None) -> dict:
    """The add-on wrote these: {Panko id: {"nid": note id, "hash": the hash it was sent}}."""
    store = store or Store()
    kept = 0
    for eid, x in (links or {}).items():
        try:
            nid, h = int(x["nid"]), str(x["hash"])
        except (KeyError, TypeError, ValueError):
            continue
        if store.get(eid) and re.fullmatch(r"[0-9a-f]{40}", h):
            store.set_link(eid, nid, h)
            kept += 1
    _remember(kept)
    return {"kept": kept}


def _state_file() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "work" / "anki-addon.json"


def _remember(n: int) -> None:
    p = _state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        s = json.loads(p.read_text())
    except (OSError, ValueError):
        s = {}
    s = {"last": time.time(), "written": s.get("written", 0) + n if time.time() - s.get("last", 0) < 600 else n}
    p.write_text(json.dumps(s))


def last_sync() -> dict:
    """When the add-on last wrote to Anki, and how many notes in that sync ({} if it never has)."""
    try:
        return json.loads(_state_file().read_text())
    except (OSError, ValueError):
        return {}
