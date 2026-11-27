"""Looking after a hosted Panko: what `/host/health` answers, and what the admin page and alerts tell you.

- **Health** (`checks`): the disk under the data folder and the front door's database. `/host/health` answers 503
  when one fails, so an outside check (the `uptime` GitHub workflow) notices a full disk as well as a dead server.
- **Events** (`Watch.note`): the front door starting, a user's Panko stopping by itself or failing to start, the
  disk getting low and recovering. Kept in host.db, shown on the admin page.
- **Alerts**: with `PANKO_ALERT_URL` set (an ntfy.sh topic, or any address that takes a POST with a text body), each
  event worth knowing about is sent there too, at most once per kind and user every few hours. Alert texts never
  carry a user's content, only what happened.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    n INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, user_id TEXT, text TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '');
"""
KEPT_EVENTS = 500
DISK_LOW_PCT = 90           # used: above this the disk is "low" (PANKO_DISK_LOW_PCT)
DISK_LOW_GB = 1             # or less than this free
ALERT_EVERY = 6 * 3600      # the same kind of alert, for the same user, at most this often
WATCH_EVERY = 300           # seconds between disk checks


def disk(path: Path) -> dict:
    u = shutil.disk_usage(path)
    used_pct = round(100 * (u.total - u.free) / u.total, 1) if u.total else 0
    low_pct = float(os.environ.get("PANKO_DISK_LOW_PCT") or DISK_LOW_PCT)
    return {"free_gb": round(u.free / 1e9, 1), "total_gb": round(u.total / 1e9, 1), "used_pct": used_pct,
            "low": used_pct >= low_pct or u.free < DISK_LOW_GB * 1e9}


def checks(data: Path, db) -> dict:
    """{"disk": {...}, "db": True/False, "ok": all fine}."""
    try:
        d = disk(data)
    except OSError:
        d = {"low": True, "error": True}
    try:
        db.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:  # noqa: BLE001  any failure here is the answer
        db_ok = False
    return {"disk": d, "db": db_ok, "ok": db_ok and not d.get("low")}


class Watch:
    def __init__(self, data: Path, db):
        self.data, self.db = Path(data), db
        self.db.executescript(SCHEMA)
        self.alert_url = os.environ.get("PANKO_ALERT_URL", "").strip()
        self.started = time.time()
        self._sent: dict[tuple, float] = {}
        self._disk_low = False
        self._lock = threading.Lock()
        self._spawn = lambda fn, *a: threading.Thread(target=fn, args=a, daemon=True).start()   # tests: run inline

    def note(self, kind: str, text: str, uid: str | None = None, detail: str = "", alert: bool = True) -> None:
        """Record an event; with alerts on, send `text` too (not `detail`, which may hold a log's lines)."""
        with self._lock, self.db:
            self.db.execute("INSERT INTO events (at, kind, user_id, text, detail) VALUES (?, ?, ?, ?, ?)",
                            (time.time(), kind, uid, text, detail[-4000:]))
            self.db.execute("DELETE FROM events WHERE n <= (SELECT MAX(n) FROM events) - ?", (KEPT_EVENTS,))
        if alert:
            self.alert(kind, text, uid)

    def events(self, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY n DESC LIMIT ?", (limit,))]

    def alert(self, kind: str, text: str, uid: str | None = None) -> bool:
        if not self.alert_url:
            return False
        key, now = (kind, uid), time.time()
        if now - self._sent.get(key, 0) < ALERT_EVERY:
            return False
        self._sent[key] = now
        self._spawn(self._post, text)
        return True

    def _post(self, text: str) -> None:
        import httpx
        try:
            httpx.post(self.alert_url, content=text.encode(), timeout=15,
                       headers={"Title": "Panko", "Tags": "warning", "Content-Type": "text/plain; charset=utf-8"})
        except Exception as e:  # noqa: BLE001  an alert that can't be sent is noted in the log, nothing more
            print(f"alert not sent: {e}", file=sys.stderr)

    def check_disk(self) -> dict:
        c = checks(self.data, self.db)
        low = bool(c["disk"].get("low"))
        if low and not self._disk_low:
            d = c["disk"]
            self.note("disk", f"the server's disk is nearly full: {d.get('free_gb', '?')} GB free "
                              f"({d.get('used_pct', '?')}% used)")
        elif self._disk_low and not low:
            self.note("disk-ok", f"the server's disk has room again: {c['disk']['free_gb']} GB free")
        self._disk_low = low
        return c

    def failed_jobs(self, uids: list[str], since: float) -> dict[str, int]:
        """{user id: jobs that failed since `since`}, from each Panko's jobs file."""
        out = {}
        for uid in uids:
            try:
                rows = json.loads((self.data / "users" / uid / "data" / "work" / "jobs.json").read_text())
            except (OSError, ValueError):
                continue
            k = sum(1 for j in rows if isinstance(j, dict) and j.get("status") == "failed"
                    and (j.get("finished") or 0) >= since)
            if k:
                out[uid] = k
        return out


def log_tail(path: Path, lines: int = 12) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8000))
            return "\n".join(f.read().decode(errors="replace").splitlines()[-lines:])
    except OSError:
        return ""
