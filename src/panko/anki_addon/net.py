"""Panko sync: talking to your Panko (Python's own urllib: nothing to install)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

VERSION = 2          # 2: a note whose picture or audio failed to download is fetched again next sync


LOCAL = ("localhost", "127.0.0.1", "[::1]")


class PankoError(Exception):
    """Your Panko said no, or couldn't be reached; the message is for you."""

    def __init__(self, text: str, unreachable: bool = False):
        super().__init__(text)
        self.unreachable = unreachable


class Panko:
    def __init__(self, server: str, code: str, timeout: float = 120):
        self.base = (server or "").strip().rstrip("/")
        if self.base and "://" not in self.base:     # a Panko on this computer (`panko hub`) has no https
            host = self.base.split("/")[0]
            host = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
            self.base = ("http://" if host in LOCAL else "https://") + self.base
        self.code, self.timeout = (code or "").strip(), timeout

    def _open(self, path: str, body: dict | None = None):
        req = urllib.request.Request(
            self.base + path, data=None if body is None else json.dumps(body).encode(),
            method="GET" if body is None else "POST",
            headers={"Authorization": f"Bearer {self.code}", "Content-Type": "application/json",
                     "User-Agent": f"panko-anki-addon/{VERSION}"})
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            try:
                why = json.loads(e.read().decode()).get("error", "")
            except Exception:  # noqa: BLE001
                why = ""
            if e.code == 401:
                why = ("the code isn't right, or was replaced: make a new one in Panko (on a server, your account "
                       "page; on your own computer, the sync page)")
            raise PankoError(why or f"Panko answered {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            local = any(f"//{h}" in self.base for h in LOCAL)
            raise PankoError(f"couldn't reach {self.base}: {getattr(e, 'reason', e)}"
                             + (". Is `panko hub` running?" if local else ""), unreachable=True) from None

    def call(self, path: str, body: dict) -> dict:
        with self._open(path, body) as r:
            return json.loads(r.read().decode())

    def media(self, name: str) -> bytes:
        from urllib.parse import quote
        with self._open("/anki/media/" + quote(name)) as r:
            return r.read()
