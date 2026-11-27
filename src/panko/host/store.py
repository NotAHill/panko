"""The front door's own records (`<data>/host.db`): users, invites and sign-in sessions. No learner data lives here:
each user's cards, sources and keys are in their own Panko folder.

Invite, session and OAuth tokens (host/oauth.py) are stored only as SHA-256 hashes, so a copy of this file can't sign anyone in. Passwords
are argon2 hashes."""
from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0,
    disabled INTEGER NOT NULL DEFAULT 0, quota_gb REAL, created REAL NOT NULL, last_seen REAL);
CREATE TABLE IF NOT EXISTS invites (
    token TEXT PRIMARY KEY, admin INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', created_by TEXT,
    created REAL NOT NULL, expires REAL NOT NULL, used_by TEXT, used REAL);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created REAL NOT NULL,
    expires REAL NOT NULL, agent TEXT NOT NULL DEFAULT '');
"""

NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
MIN_PASSWORD = 10
SESSION_DAYS = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hasher():
    from argon2 import PasswordHasher
    return PasswordHasher()


class HostStore:
    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        from panko.host.oauth import SCHEMA as OAUTH
        self.db.executescript(OAUTH)

    # ---- users
    def users(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM users ORDER BY created")]

    def user(self, uid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        return dict(r) if r else None

    def by_name(self, name: str) -> dict | None:
        r = self.db.execute("SELECT * FROM users WHERE name = ?", ((name or "").strip().lower(),)).fetchone()
        return dict(r) if r else None

    def add_user(self, name: str, password: str, admin: bool = False) -> dict:
        name = (name or "").strip().lower()
        if not NAME.match(name):
            raise ValueError("a name is 2 to 32 letters, digits, - or _, starting with a letter or digit")
        check_password(password, name)
        if self.by_name(name):
            raise ValueError("that name is taken")
        uid = "u" + secrets.token_hex(5)
        with self.db:
            self.db.execute("INSERT INTO users (id, name, pw, admin, created) VALUES (?, ?, ?, ?, ?)",
                            (uid, name, _hasher().hash(password), int(admin), time.time()))
        return self.user(uid)

    def check(self, name: str, password: str) -> dict | None:
        """The user if the name and password match and they aren't disabled. Takes about as long either way."""
        from argon2.exceptions import InvalidHashError, VerificationError
        u = self.by_name(name)
        ph = _hasher()
        try:
            ph.verify(u["pw"] if u else _DUMMY(), password or "")
        except (VerificationError, InvalidHashError):
            return None
        if not u or u["disabled"]:
            return None
        if ph.check_needs_rehash(u["pw"]):
            with self.db:
                self.db.execute("UPDATE users SET pw = ? WHERE id = ?", (ph.hash(password), u["id"]))
        return u

    def set_password(self, uid: str, password: str) -> None:
        u = self.user(uid)
        check_password(password, u["name"] if u else "")
        with self.db:
            self.db.execute("UPDATE users SET pw = ? WHERE id = ?", (_hasher().hash(password), uid))
            self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))     # signed out everywhere
            self.db.execute("DELETE FROM oauth_grants WHERE user_id = ?", (uid,))  # and Claude must connect again

    def update(self, uid: str, **fields) -> None:
        allowed = {"admin", "disabled", "quota_gb"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        with self.db:
            self.db.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",
                            (*sets.values(), uid))
            if sets.get("disabled"):
                self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
                self.db.execute("DELETE FROM oauth_grants WHERE user_id = ?", (uid,))

    def seen(self, uid: str) -> None:
        with self.db:
            self.db.execute("UPDATE users SET last_seen = ? WHERE id = ?", (time.time(), uid))

    def remove_user(self, uid: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
            self.db.execute("DELETE FROM users WHERE id = ?", (uid,))

    # ---- invites
    def invite(self, *, admin: bool = False, days: float = 7, note: str = "", by: str | None = None) -> str:
        token = secrets.token_urlsafe(24)
        now = time.time()
        with self.db:
            self.db.execute("INSERT INTO invites (token, admin, note, created_by, created, expires) VALUES "
                            "(?, ?, ?, ?, ?, ?)", (_hash(token), int(admin), note[:200], by, now, now + days * 86400))
        return token

    def invite_ok(self, token: str) -> dict | None:
        r = self.db.execute("SELECT * FROM invites WHERE token = ? AND used_by IS NULL AND expires > ?",
                            (_hash(token or ""), time.time())).fetchone()
        return dict(r) if r else None

    def invites(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT rowid AS n, admin, note, created, expires, used_by, used FROM invites ORDER BY created DESC")]

    def withdraw(self, n: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM invites WHERE rowid = ? AND used_by IS NULL", (n,))

    def accept(self, token: str, name: str, password: str) -> dict:
        """Use an invite: make the account. An invite works once."""
        inv = self.invite_ok(token)
        if not inv:
            raise ValueError("this invite has expired or was used already: ask for a new one")
        u = self.add_user(name, password, admin=bool(inv["admin"]))
        with self.db:
            cur = self.db.execute("UPDATE invites SET used_by = ?, used = ? WHERE token = ? AND used_by IS NULL",
                                  (u["id"], time.time(), inv["token"]))
            if cur.rowcount != 1:            # used by someone else in the same instant
                self.db.execute("DELETE FROM users WHERE id = ?", (u["id"],))
                raise ValueError("this invite was just used: ask for a new one")
        return u

    # ---- sessions
    def start_session(self, uid: str, agent: str = "") -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            self.db.execute("INSERT INTO sessions (token, user_id, created, expires, agent) VALUES (?, ?, ?, ?, ?)",
                            (_hash(token), uid, now, now + SESSION_DAYS * 86400, agent[:200]))
        return token

    def session_user(self, token: str) -> dict | None:
        if not token:
            return None
        r = self.db.execute("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND "
                            "s.expires > ? AND u.disabled = 0", (_hash(token), time.time())).fetchone()
        return dict(r) if r else None

    def end_session(self, token: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE token = ?", (_hash(token or ""),))


def check_password(password: str, name: str = "") -> None:
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"a password needs at least {MIN_PASSWORD} characters")
    if name and name.lower() in password.lower():
        raise ValueError("the password can't contain your name")


_DUMMY_HASH: list[str] = []


def _DUMMY() -> str:      # noqa: N802  a hash to verify against when the name doesn't exist (same timing)
    if not _DUMMY_HASH:
        _DUMMY_HASH.append(_hasher().hash(secrets.token_urlsafe(16)))
    return _DUMMY_HASH[0]
