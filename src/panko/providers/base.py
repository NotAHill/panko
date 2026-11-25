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
    label = "?"          # the site named in a card's picture credit

    def search(self, query: str, limit: int = 6) -> list[dict]:
        """Return candidates: {url, thumb, title, author, license, page}. `thumb` (about 800 px) is what the
        contact sheet shows and what gets downloaded for the card."""
        raise NotImplementedError

    def fresh(self, c: dict) -> dict:
        """The candidate with download links that still work (some sites' links expire)."""
        return c


class STT(Provider):
    def transcribe(self, path: Path, language: str = "", diarize: bool = True) -> dict:
        """{"text", "language_code", "audio_duration_secs", "engine", "words": [{text, start, end, type
        ("word" | "spacing"), speaker_id?}]}: the transcript with word times (seconds)."""
        raise NotImplementedError


class Morph(Provider):
    """Morphological analysis for the varieties it has a database for ([morph.<name>] dbs = {variety = db})."""

    def dbs(self) -> dict[str, str]:
        return dict(self.cfg.get("dbs", {}))

    def analyse(self, words: list[str], variety: str) -> dict[str, list[dict]]:
        """{word: [reading]}, each reading {"diac", "lex", "root" (letters joined by "."), "pos", "pattern", "asp",
        "num", "gen", ...}; an empty list = no reading (a typo, a rare or a foreign word)."""
        raise NotImplementedError


class ImageGen(Provider):
    def generate(self, prompt: str, out: Path) -> Image | None:
        raise NotImplementedError


@dataclass
class Ask:
    """One request to a language model. `system` is the stable task prompt (cached across requests); `parts` is
    this item's input: strings, or {"image": path} / {"pdf": path}. With `schema`, the reply is JSON that fits it."""
    id: str
    system: str
    parts: list
    schema: dict | None = None
    max_tokens: int = 16000
    effort: str | None = None      # low | medium | high | xhigh | max (provider default when None)


@dataclass
class Answer:
    id: str
    data: object = None            # parsed JSON (with a schema) or text
    error: str = ""                # empty when it worked
    model: str = ""
    usage: dict = field(default_factory=dict)   # input, output, cache_read, cache_write (tokens)
    cost: float = 0.0              # USD, from the price table; 0 when the price is unknown
    batch: bool = False


class LLM(Provider):
    model = ""

    def ask(self, a: Ask) -> Answer:
        raise NotImplementedError

    def count_tokens(self, a: Ask) -> int | None:
        """Input tokens for one request, or None when the provider can't count."""
        return None

    # batch APIs (half price, results within 24 h)
    def batch_submit(self, asks: list[Ask]) -> str:
        raise NotImplementedError(f"{self.name}: batches not wired yet")

    def batch_status(self, batch_id: str) -> dict:
        raise NotImplementedError

    def batch_results(self, batch_id: str) -> list[Answer]:
        raise NotImplementedError
