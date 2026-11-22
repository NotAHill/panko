"""Get audio for a piece of text by walking the audio provider chain.

Results are cached by (provider, voice, text) so re-running never pays twice.
Cached files live in cache/media/ (git-ignored, re-creatable)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from panko import providers
from panko.config import CACHE

MEDIA = CACHE / "media"


@dataclass
class Voiced:
    filename: str
    source: str


def speak(text: str, variety: str, prefix: str = "_panko_") -> Voiced | None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    for p in providers.chain("audio"):
        voice = p.cfg.get(f"voice_{variety}", "")
        key = hashlib.sha1(f"{p.name}|{voice}|{p.cfg.get('model', '')}|{text}".encode()).hexdigest()[:12]
        out = MEDIA / f"{prefix}{p.name}_{key}.mp3"
        meta = out.with_suffix(".txt")
        if out.exists() and meta.exists():
            return Voiced(out.name, meta.read_text())
        got = p.speak(text, variety, out)
        if got:
            meta.write_text(got.source)
            return Voiced(out.name, got.source)
    return None


def no_voice(text: str, variety: str) -> Voiced | None:
    return None
