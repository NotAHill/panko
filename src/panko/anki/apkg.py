"""Your cards as an Anki package (.apkg), to share with a friend.

The package is built in a scratch collection with Anki's own library (`uv sync --extra apkg`), so your Anki and its
review history are never touched. It holds your active cards with Panko's note types, templates and styling, the
pictures and the audio already made (nothing new is paid for), and no scheduling: a friend starts from new cards.
MyNotes stays empty. Unless you choose `personal`, where each word came from is left out (source names can name your
teacher) and so are clips cut from your lesson recordings; photo credits always stay, because the licences need them.
Each note's id comes from its Panko id, so importing a newer package updates the friend's notes instead of adding
copies.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

from panko.anki.sync import MEDIA_DIRS, PREFIX
from panko.cards import build as B
from panko.cards import note_types as T
from panko.media import audio
from panko.store import Store

NATIVE = "_panko_native_"          # clips cut from your own recordings (panko.media.clips)
MEDIA_REF = re.compile(r'\[sound:([^\]]+)\]|src="([^"]+)"')


class _Made(audio.Narrator):
    """Audio already made: never generates (or pays for) a clip, and leaves your recordings out unless asked."""

    def __init__(self, personal: bool):
        super().__init__(prefix=PREFIX)
        self.personal, self.missing = personal, 0

    def say(self, text, variety, slot=0):
        v = audio.speak(text, variety, self.prefix, slot, dry=[])
        if not v or v.source == "not generated yet":
            self.missing += bool(v)
            return None
        if not self.personal and v.filename.startswith(NATIVE):
            return None
        return v


def _shared(e: dict, personal: bool) -> dict:
    """The entry as it goes in a package: without where it came from, unless that's wanted."""
    if personal:
        return e
    exs = [{**x, "source": "", "audio": "" if str(x.get("audio", "")).startswith(NATIVE) else x.get("audio", "")}
           for x in e.get("examples", [])]
    return {**e, "sources": [], "examples": exs, "review": False,
            "tags": [t for t in e.get("tags", []) if not t.startswith(("src::", "panko::"))]}


def _room(where: Path, files, tmp: Path) -> None:
    """Enough free space for the package (and a copy of the media when it can't be linked)? Say so before writing."""
    size = sum(f.stat().st_size for f in files)
    linkable = all(f.stat().st_dev == tmp.stat().st_dev for f in files)
    need = int(size * (1.1 if linkable else 2.1)) + 50_000_000
    free = shutil.disk_usage(where).free
    if free < need:
        raise RuntimeError(f"the package needs about {need // 1_000_000:,} MB free in {where}, and there's "
                           f"{free // 1_000_000:,} MB: set [export] dir in your config to a folder on a bigger disk")


def _guid(eid: str) -> str:
    return "panko-" + hashlib.sha1(eid.encode()).hexdigest()[:16]


def _model_id(name: str) -> int:
    return 1_700_000_000_000 + int(hashlib.sha1(name.encode()).hexdigest()[:8], 16) % 1_000_000_000


def export(out: Path, varieties: list[str] | None = None, personal: bool = False, store: Store | None = None) -> dict:
    try:
        from anki.collection import Collection, DeckIdLimit, ExportAnkiPackageOptions
    except ImportError as e:
        raise RuntimeError("making an .apkg needs Anki's library: run `uv sync --extra apkg`") from e
    store = store or Store()
    entries = [e for e in store.entries("active") if not varieties or e["variety"] in varieties]
    if not entries:
        raise ValueError("no active cards to put in it" + (f" for {', '.join(varieties)}" if varieties else ""))
    narrator = _Made(personal)
    notes = []
    for e in entries:
        n = B.to_note(_shared(e, personal), narrator)
        n["deck"] = f"Panko::{e['variety'].title()}"          # not your own deck names
        n["tags"] = [t for t in n["tags"] if personal or not t.startswith("panko::")]
        notes.append((e["id"], n))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".panko-apkg-", dir=out.parent))   # beside the package, not on the system disk
    try:
        col = Collection(str(tmp / "collection.anki2"))
        mm, models = col.models, {}
        for name, fields, tmpls in [(T.WORD_MODEL, T.WORD_FIELDS, T.word_templates()),
                                    (T.PHRASE_MODEL, T.PHRASE_FIELDS, T.phrase_templates())]:
            m = mm.new(name)
            for f in fields:
                mm.add_field(m, mm.new_field(f))
            for t in tmpls:
                tt = mm.new_template(t["Name"])
                tt["qfmt"], tt["afmt"] = t["Front"], t["Back"]
                mm.add_template(m, tt)
            m["css"] = T.css()
            new = mm.add_dict(m).id
            fixed = _model_id(name)        # the same on every export, so a newer package updates the old one
            for table, col_name in (("notetypes", "id"), ("fields", "ntid"), ("templates", "ntid")):
                col.db.execute(f"UPDATE {table} SET {col_name} = ? WHERE {col_name} = ?", fixed, new)
            models[name] = fixed
        col.models._clear_cache()
        used: set[str] = set()
        added, empty = 0, 0
        for eid, note in notes:
            n = col.new_note(mm.get(models[note["model"]]))
            for k, v in note["fields"].items():
                if k in n:
                    n[k] = v
            n.tags = note["tags"]
            n.guid = _guid(eid)
            try:
                col.add_note(n, col.decks.id(note["deck"]))
            except Exception:       # a note whose card switches make no card at all
                empty += 1
                continue
            added += 1
            used |= {a or b for a, b in MEDIA_REF.findall(" ".join(note["fields"].values()))}
        from panko.media import clips
        dirs = [*MEDIA_DIRS, audio.MEDIA, clips._media()]
        files = {f.name: f for d in dirs if d.exists() for f in d.iterdir() if f.name in used}
        _room(out.parent, files.values(), tmp)
        for f in files.values():
            try:
                os.link(f, Path(col.media.dir()) / f.name)       # no second copy when on the same disk
            except OSError:
                shutil.copy2(f, Path(col.media.dir()) / f.name)
        opts = ExportAnkiPackageOptions(with_scheduling=False, with_deck_configs=False, with_media=True, legacy=False)
        col.export_anki_package(out_path=str(out), options=opts, limit=DeckIdLimit(col.decks.id("Panko")))
        col.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"path": str(out), "notes": added, "skipped": empty, "media": len(files), "media_missing": len(used - set(files)),
            "audio_not_made": narrator.missing, "bytes": out.stat().st_size, "personal": personal}
