"""Interfaces every provider implements. Keep these small: Panko's pipeline only
talks to these, never to a vendor SDK directly."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class Provider:
    name = "?"
    needs: tuple[str, ...] = ()  # env vars that must be set

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def ready(self) -> bool:
        from panko.config import secret
        return all(secret(n) for n in self.needs)


@dataclass
class Audio:
    path: Path
    source: str          # human-readable, shown in the card's Sources section
    native: bool         # True = real human recording


@dataclass
class Image:
    path: Path
    source: str          # e.g. "Wikimedia Commons · Jane Doe · CC BY-SA 4.0"
    generated: bool = False
    meta: dict = field(default_factory=dict)


class TTS(Provider):
    def voices(self, variety: str) -> list[str]:
        """Voice names for a variety, in order (headword uses all, examples rotate)."""
        v = self.cfg.get(f"voice_{variety}")
        return [v] if v else []

    def speak(self, text: str, variety: str, out: Path, voice: str | None = None) -> Audio | None:
        raise NotImplementedError


class ImageSearch(Provider):
    def search(self, query: str, limit: int = 6) -> list[dict]:
        """Return candidates: {url, thumb, title, author, license, page}."""
        raise NotImplementedError


class ImageGen(Provider):
    def generate(self, prompt: str, out: Path) -> Image | None:
        raise NotImplementedError
