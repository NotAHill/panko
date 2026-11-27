"""Panko sync: talking to your Panko (Python's own urllib: nothing to install)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

VERSION = 1


class PankoError(Exception):
    """Your Panko said no, or couldn't be reached; the message is for you."""


class Panko:
    def __init__(self, server: str, code: str, timeout: float = 120):
        self.base = (server or "").strip().rstrip("/")
        if self.base and "://" not in self.base:
            self.base = "https://" + self.base
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
                why = "the device code isn't right, or was ended: make a new one in Panko (your account page)"
            raise PankoError(why or f"Panko answered {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise PankoError(f"couldn't reach {self.base}: {getattr(e, 'reason', e)}") from None

    def call(self, path: str, body: dict) -> dict:
        with self._open(path, body) as r:
            return json.loads(r.read().decode())

    def media(self, name: str) -> bytes:
        from urllib.parse import quote
        with self._open("/anki/media/" + quote(name)) as r:
            return r.read()
