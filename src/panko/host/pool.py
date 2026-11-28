"""The picture pool of a hosted Panko (stage 2 of picture reuse): pictures one person here found, offered to the
others for cards with the same meaning, so nobody searches the photo sites again for "bread".

- **What goes in**: pictures on people's cards whose licence lets anyone share them for any use (CC BY, CC BY-SA,
  CC0, public domain: not non-commercial or no-derivatives ones), and drawings only from people who choose to share theirs. Never a picture
  cut from someone's own sources (a teacher's sheet), from the web, or under a site licence that forbids passing
  the files on (Pexels, Pixabay). Each person decides in card design (`[images] share`, `share_drawings`).
- **How**: the front door looks through everyone's cards every hour (`fill`) and keeps one copy of each file
  (by its hash) in `<data>/pool/`, with the meanings it was chosen for. A card that loses its picture, or a person
  who stops sharing or leaves, takes their meanings out; a file nobody's meaning holds any more is deleted.
- **Who sees what**: a Panko asks with its front-door secret (`search`, `file`); others never see who shared a
  picture, which card it came from, or its gloss: only the picture, its credit and licence. Your own pictures
  never come back to you from here (your Panko offers them itself).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import tomllib
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pool_files (
    sha TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, provider TEXT NOT NULL DEFAULT '',
    license TEXT NOT NULL DEFAULT '', credit TEXT NOT NULL DEFAULT '', page TEXT NOT NULL DEFAULT '',
    bytes INTEGER NOT NULL DEFAULT 0, added REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pool_meanings (
    uid TEXT NOT NULL, eid TEXT NOT NULL, sha TEXT NOT NULL, key TEXT NOT NULL, full TEXT NOT NULL,
    pos TEXT NOT NULL DEFAULT '', PRIMARY KEY (uid, eid));
CREATE INDEX IF NOT EXISTS pool_meanings_key ON pool_meanings(key);
"""
MAX_BYTES = 3_000_000
NAME = re.compile(r"^[0-9a-f]{24}\.(jpg|png|webp)$")
# providers whose pictures are never shared: cut from your own sources, found on any web page, already from here,
# or your own picture reused (the card it came from is shared itself)
NEVER = {"source", "web", "pool", "yours"}
DRAWN = {"generate"}


def open_licence(lic: str) -> bool:
    """CC BY, CC BY-SA, CC0, public domain. Not non-commercial (some sites, like ARASAAC, mean personal use) nor
    no-derivatives (the pool keeps a resized copy)."""
    s = re.sub(r"[-_]+", " ", (lic or "").lower())
    if not s.strip():
        return False
    if "cc0" in s or "public domain" in s or re.search(r"\bpdm\b", s) or "no known copyright" in s:
        return True
    t = f" {s} "
    return "cc" in s and " by " in t and " nd " not in t and " nc " not in t


def kind_of(im: dict, share: bool, drawings: bool) -> str | None:
    """'photo', 'drawing', or None when this card's picture isn't shared."""
    if not isinstance(im, dict) or not im.get("file"):
        return None
    provider = im.get("provider", "")
    if provider in NEVER or im.get("reused_from"):
        return None
    if provider in DRAWN or im.get("prompt"):
        return "drawing" if drawings else None
    return "photo" if share and open_licence(im.get("license", "")) else None


def prefs(home: Path) -> dict:
    """Someone's choices for the pool, from their own config (the hub's choices over panko.toml). A config that
    can't be read shares nothing."""
    img: dict = {}
    for name in ("panko.toml", "hub.toml"):
        p = home / "config" / name
        if not p.exists():
            continue
        try:
            with open(p, "rb") as f:
                img.update(tomllib.load(f).get("images", {}) or {})
        except (OSError, tomllib.TOMLDecodeError):
            return {"use": True, "share": False, "share_drawings": False}
    return {"use": img.get("pool", True) is not False, "share": img.get("share", True) is not False,
            "share_drawings": img.get("share_drawings", False) is True}


class Pool:
    def __init__(self, data: Path):
        self.dir = Path(data) / "pool"
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        self.db = sqlite3.connect(Path(data) / "pool.db", check_same_thread=False, timeout=10)  # its own: the
        self.db.executescript(SCHEMA)                                                          # hourly fill runs in a thread
        self._lock = threading.RLock()
        self._hashes: dict[tuple, str] = {}       # (path, size, mtime) → sha, so an hourly fill hashes only new files
        self.skipped: dict[str, str] = {}         # user → why the last fill couldn't read their cards

    # ---- filling it from people's cards
    def _sha(self, p: Path) -> str | None:
        try:
            st = p.stat()
        except OSError:
            return None
        if st.st_size > MAX_BYTES:
            return None
        k = (str(p), st.st_size, st.st_mtime)
        if k not in self._hashes:
            self._hashes[k] = hashlib.sha256(p.read_bytes()).hexdigest()
        return self._hashes[k]

    BUSY_WAIT = 5      # seconds to wait for a store another process is writing

    def _cards(self, home: Path):
        db = home / "data" / "panko.db"
        if not db.exists():
            return
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=self.BUSY_WAIT)
        try:
            for eid, data in con.execute("SELECT id, data FROM entries WHERE status != 'retired'"):
                try:
                    yield eid, json.loads(data)
                except ValueError:
                    continue
        finally:
            con.close()

    def fill_user(self, uid: str, home: Path) -> int | None:
        """Bring the pool up to date with one person's cards; returns how many of their pictures it holds, or None
        when their store couldn't be read (busy or broken: nothing of theirs changes, `skipped` says why)."""
        self.skipped.pop(uid, None)
        from panko.media.reuse import _full, key, meaning_of
        p = prefs(home)
        rows: list[tuple] = []
        files: dict[str, tuple] = {}
        if p["share"] or p["share_drawings"]:
            try:
                for eid, e in self._cards(home):
                    im = e.get("image")
                    kind = kind_of(im, p["share"], p["share_drawings"])
                    if not kind:
                        continue
                    src = home / "data" / "media" / im["file"]
                    ext = src.suffix.lower().lstrip(".")
                    if ext == "jpeg":
                        ext = "jpg"
                    if ext not in ("jpg", "png", "webp"):
                        continue
                    sha = self._sha(src)
                    if not sha:
                        continue
                    m = meaning_of(e)
                    k = key(m["gloss"])
                    if not k:
                        continue
                    rows.append((uid, eid, sha, k, _full(m["gloss"]), m["pos"]))
                    files.setdefault(sha, (src, ext, kind, im))
            except sqlite3.Error as ex:
                self.skipped[uid] = str(ex)
                return None
        now = time.time()
        held = set()
        with self._lock, self.db:
            for sha, (src, ext, kind, im) in files.items():
                if self.db.execute("SELECT 1 FROM pool_files WHERE sha = ?", (sha,)).fetchone():
                    held.add(sha)
                    continue
                name = f"{sha[:24]}.{ext}"
                try:
                    shutil.copyfile(src, self.dir / name)
                except OSError:
                    continue
                self.db.execute("INSERT INTO pool_files (sha, name, kind, provider, license, credit, page, bytes, added) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (sha, name, kind, im.get("provider", ""), im.get("license", ""), im.get("credit", ""),
                                 im.get("page", ""), (self.dir / name).stat().st_size, now))
                held.add(sha)
            self.db.execute("DELETE FROM pool_meanings WHERE uid = ?", (uid,))
            self.db.executemany("INSERT OR REPLACE INTO pool_meanings (uid, eid, sha, key, full, pos) "
                                "VALUES (?, ?, ?, ?, ?, ?)", [r for r in rows if r[2] in held])
        self._sweep()
        return len(rows)

    def fill(self, users: list[tuple[str, Path]]) -> dict:
        """Everyone's cards: [(user id, their Panko folder)]. Someone not listed (disabled, deleted) is taken out."""
        self.skipped = {}
        out = {uid: self.fill_user(uid, home) for uid, home in users}
        listed = {uid for uid, _ in users}
        with self._lock, self.db:
            gone = [r[0] for r in self.db.execute("SELECT DISTINCT uid FROM pool_meanings") if r[0] not in listed]
            for uid in gone:
                self.db.execute("DELETE FROM pool_meanings WHERE uid = ?", (uid,))
        if gone:
            self._sweep()
        return out

    def forget(self, uid: str) -> None:
        """Someone leaves: their meanings go, and the files only they held."""
        with self._lock, self.db:
            self.db.execute("DELETE FROM pool_meanings WHERE uid = ?", (uid,))
        self._sweep()

    def _sweep(self) -> None:
        with self._lock, self.db:
            for sha, name in self.db.execute("SELECT sha, name FROM pool_files WHERE sha NOT IN "
                                             "(SELECT sha FROM pool_meanings)").fetchall():
                (self.dir / name).unlink(missing_ok=True)
                self.db.execute("DELETE FROM pool_files WHERE sha = ?", (sha,))

    # ---- what a Panko asks
    def search(self, query: str, uid: str, limit: int = 6) -> list[dict]:
        """Pictures for this search, never the asker's own: the same main sense first, then glosses holding every
        word searched. Only the picture, its credit and licence: not who shared it or their card."""
        from panko.media.reuse import key
        q = key(query)
        if not q:
            return []
        words = q.split()
        like = " AND ".join("instr(' ' || m.key || ' ', ?) > 0" for _ in words)
        with self._lock:
            mine = {r[0] for r in self.db.execute("SELECT sha FROM pool_meanings WHERE uid = ?", (uid,))}
            rows = self.db.execute(
                "SELECT f.sha, f.name, f.kind, f.license, f.credit, f.page, MAX(m.key = ?) AS same, "
                "COUNT(DISTINCT m.uid) AS n "
                f"FROM pool_meanings m JOIN pool_files f ON f.sha = m.sha WHERE m.uid != ? AND {like} "
                "GROUP BY f.sha ORDER BY same DESC, n DESC, f.added LIMIT ?",
                (q, uid, *[f" {w} " for w in words], limit + len(mine))).fetchall()
        return [{"name": r[1], "kind": r[2], "license": r[3], "credit": r[4], "page": r[5]}
                for r in rows if r[0] not in mine][:limit]

    def path(self, name: str) -> Path | None:
        if not NAME.match(name or ""):
            return None
        p = self.dir / name
        return p if p.exists() else None

    def stats(self) -> dict:
        with self._lock:
            return self._stats()

    def _stats(self) -> dict:
        r = self.db.execute("SELECT COUNT(*), COALESCE(SUM(bytes), 0), SUM(kind = 'drawing') FROM pool_files").fetchone()
        people = self.db.execute("SELECT COUNT(DISTINCT uid) FROM pool_meanings").fetchone()[0]
        return {"pictures": r[0], "bytes": r[1], "drawings": r[2] or 0, "people": people}
