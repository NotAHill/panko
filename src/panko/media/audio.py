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


def voice_count(variety: str) -> int:
    """How many voices the first ready provider has for this variety."""
    for p in providers.chain("audio"):
        if p.voices(variety):
            return len(p.voices(variety))
    return 0


def speak(text: str, variety: str, prefix: str = "_panko_", slot: int = 0, dry: list | None = None) -> Voiced | None:
    """slot picks the voice: 0 = first voice listed, 1 = second... (wraps around).
    `dry`: a list; nothing is generated, and the text of each clip that would be paid for is appended to it."""
    MEDIA.mkdir(parents=True, exist_ok=True)
    for p in providers.chain("audio"):
        names = p.voices(variety)
        if not names and p.name != "native":
            continue
        voice = names[slot % len(names)] if names else None
        key = hashlib.sha1(f"{p.name}|{voice}|{p.cfg.get('model', '')}|{text}".encode()).hexdigest()[:12]
        out = MEDIA / f"{prefix}{p.name}_{key}.mp3"
        meta = out.with_suffix(".txt")
        if out.exists() and meta.exists() and out.stat().st_size:
            return Voiced(out.name, meta.read_text())
        if dry is not None and p.name != "native":
            dry.append((p.name, text))
            return Voiced(out.name, "not generated yet")
        got = p.speak(text, variety, out, voice=voice)
        if got and not got.native and (not out.exists() or not out.stat().st_size):
            out.unlink(missing_ok=True)   # e.g. a one-letter word comes back as empty audio
            meta.unlink(missing_ok=True)
            continue
        if got and got.native:
            return Voiced(got.path.name, got.source)
        if got:
            meta.write_text(got.source)
            return Voiced(out.name, got.source)
    return None


class Narrator:
    """What card builders use: how many voices a variety has, and audio per slot."""

    def __init__(self, prefix: str = "_panko_"):
        self.prefix = prefix

    def count(self, variety: str) -> int:
        return voice_count(variety)

    def say(self, text: str, variety: str, slot: int = 0) -> Voiced | None:
        return speak(text, variety, self.prefix, slot)


class DryRun(Narrator):
    """Uses cached audio and records what would be generated (`self.todo`: [(provider, text)]), spending nothing."""

    def __init__(self, prefix: str = "_panko_"):
        super().__init__(prefix)
        self.todo: list[tuple[str, str]] = []

    def say(self, text, variety, slot=0):
        return speak(text, variety, self.prefix, slot, dry=self.todo)


class Silent(Narrator):
    """No audio (tests, or no provider configured)."""

    def count(self, variety):
        return 0

    def say(self, text, variety, slot=0):
        return None
