"""Real human audio we already hold (teacher clips cut from lesson recordings,
Peace Corps recordings). Lookup is by exact text; the index is filled by the
ingestion pipeline (Phase 2), so for now this finds nothing."""
from __future__ import annotations

from pathlib import Path

from panko.providers import register
from panko.providers.base import TTS, Audio


@register("audio", "native")
class NativeAudio(TTS):
    index: dict[str, tuple[Path, str]] = {}

    def speak(self, text, variety, out) -> Audio | None:
        hit = self.index.get(text)
        return Audio(path=hit[0], source=hit[1], native=True) if hit else None
