"""Panko's store: the source of truth for every entry it manages.

SQLite file at data/panko.db (git-ignored, personal). Anki notes are rendered from
entries; Anki is never read back except for the user's own MyNotes field.

Tables
  entries    one row per word/phrase; structured content in `data` (JSON)
  sources    where material came from (a lesson, a teacher sheet, a book)
  sightings  an entry seen in a source: who said it, in what sentence, taught or corrected
  anki       the Anki note an entry is rendered to, plus a hash of what was last written
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from panko.config import ROOT
from panko.store.normalize import strip_article as key

DB_PATH = ROOT / "data" / "panko.db"

# What a person (or their chat assistant) may change on an entry; ids, status and checks stay Panko's.
EDITABLE = {"ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "present", "imperative", "literal",
            "usage", "notes", "related", "examples", "tags", "region", "cards", "extra",
            "picture_pref", "picture_request"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('word', 'phrase')),
  variety TEXT NOT NULL,              -- a variety from [learner] varieties (darija, fusha, spanish…)
  ar TEXT NOT NULL,                   -- headword / phrase as shown
  ar_key TEXT NOT NULL,               -- normalised, for "do we already have this?"
  status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'active', 'retired')),
  data TEXT NOT NULL,                 -- JSON: translit, gloss, examples, related, image...
  created TEXT NOT NULL,
  updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS entries_key ON entries (variety, ar_key);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,                -- e.g. lesson-2026-11-21
  kind TEXT NOT NULL,                 -- lesson | teacher-sheet | book | media | deck
  title TEXT NOT NULL,
  date TEXT,
  path TEXT,
  trust INTEGER NOT NULL DEFAULT 50   -- 0-100; lesson/teacher high, shared decks low
);

CREATE TABLE IF NOT EXISTS sightings (
  id INTEGER PRIMARY KEY,
  entry_id TEXT NOT NULL REFERENCES entries(id),
  source_id TEXT NOT NULL REFERENCES sources(id),
  role TEXT NOT NULL,                 -- taught | corrected | used | mentioned
  speaker TEXT,                       -- teacher | learner
  ar TEXT, tl TEXT, en TEXT,          -- the sentence it appeared in
  note TEXT,
  UNIQUE (entry_id, source_id, role, ar)
);

CREATE TABLE IF NOT EXISTS anki (
  entry_id TEXT PRIMARY KEY REFERENCES entries(id),
  note_id INTEGER NOT NULL,
  rendered_hash TEXT,
  synced TEXT
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- entries
    def put(self, entry: dict, status: str | None = None) -> str:
        """Insert or replace an entry (dict with id, kind, variety, ar + content)."""
        e = dict(entry)
        eid, kind, variety, ar = e.pop("id"), e.pop("kind"), e.pop("variety"), e.pop("ar")
        e.pop("status", None)  # status lives in its own column only
        old = self.get(eid)
        st = status or (old["status"] if old else "candidate")
        self.db.execute(
            "INSERT INTO entries (id, kind, variety, ar, ar_key, status, data, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, variety=excluded.variety, "
            "ar=excluded.ar, ar_key=excluded.ar_key, status=excluded.status, data=excluded.data, updated=excluded.updated",
            (eid, kind, variety, ar, key(ar), st, json.dumps(e, ensure_ascii=False), now(), now()))
        self.db.commit()
        return eid

    def get(self, eid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM entries WHERE id=?", (eid,)).fetchone()
        return self._row(r) if r else None

    def find(self, ar: str, variety: str, pos: str | None = None) -> dict | None:
        """The entry with this Arabic (normalised). With `pos`, homographs of another part of speech
        don't match, so دار "house" and دار "to do" stay separate entries."""
        rows = self.db.execute("SELECT * FROM entries WHERE variety=? AND ar_key=?", (variety, key(ar))).fetchall()
        from panko.dedupe import pos_compatible
        for r in map(self._row, rows):
            if pos_compatible(pos, r.get("pos")):
                return r
        return None

    def find_all(self, ar: str, variety: str) -> list[dict]:
        """Every entry (any status, any POS) with this normalised Arabic."""
        rows = self.db.execute("SELECT * FROM entries WHERE variety=? AND ar_key=? ORDER BY id", (variety, key(ar)))
        return [self._row(r) for r in rows]

    def entries(self, status: str | None = "active", variety: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM entries WHERE 1=1", []
        if status:
            q += " AND status=?"
            args.append(status)
        if variety:
            q += " AND variety=?"
            args.append(variety)
        return [self._row(r) for r in self.db.execute(q + " ORDER BY id", args)]

    def set_status(self, eid: str, status: str, why: str = ""):
        """`why` says why a card was retired ("rejected in the inbox", "dropped: …"); it goes when the card comes back."""
        self.db.execute("UPDATE entries SET status=?, updated=? WHERE id=?", (status, now(), eid))
        if why or status != "retired":
            e = self.get(eid)
            if e and (why or "retired_why" in e):
                data = {k: v for k, v in e.items() if k not in ("id", "kind", "variety", "ar", "status", "created", "updated")}
                if why:
                    data["retired_why"] = why
                else:
                    data.pop("retired_why", None)
                self.db.execute("UPDATE entries SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), eid))
        self.db.commit()

    def duplicates_of(self, eid: str) -> list[dict]:
        """Retired entries merged into this one (their `merged_into` reads "same as <id> …")."""
        rows = self.db.execute("SELECT id FROM entries WHERE status = 'retired' AND "
                               "json_extract(data, '$.merged_into') LIKE ?", (f"same as {eid} %",)).fetchall()
        return [self.get(r[0]) for r in rows]

    def next_id(self, kind: str, variety: str) -> str:
        prefix = f"{variety[0]}{kind[0]}-"  # dw- darija word, dp- darija phrase, fw- fusha word
        n = self.db.execute("SELECT COUNT(*) FROM entries WHERE id LIKE ?", (prefix + "%",)).fetchone()[0]
        while self.get(f"{prefix}{n + 1:05d}"):
            n += 1
        return f"{prefix}{n + 1:05d}"

    @staticmethod
    def _row(r) -> dict:
        data = {k: v for k, v in json.loads(r["data"]).items() if k != "status"}
        return {**data, "id": r["id"], "kind": r["kind"], "variety": r["variety"], "ar": r["ar"], "status": r["status"]}

    # ---- sources & sightings
    def add_source(self, sid: str, kind: str, title: str, date: str = "", path: str = "", trust: int = 50):
        self.db.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?)", (sid, kind, title, date, path, trust))
        self.db.commit()

    def source(self, sid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None

    def add_sighting(self, entry_id: str, source_id: str, role: str, speaker: str = "", ar: str = "", tl: str = "",
                     en: str = "", note: str = ""):
        self.db.execute("INSERT OR IGNORE INTO sightings (entry_id, source_id, role, speaker, ar, tl, en, note) "
                        "VALUES (?,?,?,?,?,?,?,?)", (entry_id, source_id, role, speaker, ar, tl, en, note))
        self.db.commit()

    def sightings(self, entry_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT s.*, src.title, src.trust, src.kind AS source_kind FROM sightings s JOIN sources src ON src.id = s.source_id "
            "WHERE entry_id=? ORDER BY src.trust DESC", (entry_id,))]

    # ---- anki links
    def link(self, entry_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM anki WHERE entry_id=?", (entry_id,)).fetchone()
        return dict(r) if r else None

    def set_link(self, entry_id: str, note_id: int, rendered_hash: str):
        self.db.execute("INSERT INTO anki VALUES (?,?,?,?) ON CONFLICT(entry_id) DO UPDATE SET note_id=excluded.note_id, "
                        "rendered_hash=excluded.rendered_hash, synced=excluded.synced", (entry_id, note_id, rendered_hash, now()))
        self.db.commit()
