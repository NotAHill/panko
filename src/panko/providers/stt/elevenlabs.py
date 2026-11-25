"""Speech-to-text with ElevenLabs Scribe: words with start/end times (and speakers when diarized)."""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from panko.config import secret
from panko.providers import register
from panko.providers.base import STT


@register("stt", "elevenlabs")
class Scribe(STT):
    needs = ("ELEVENLABS_API_KEY",)

    def transcribe(self, path: Path, language: str = "", diarize: bool = True) -> dict:
        data = {"model_id": self.cfg.get("model", "scribe_v1"), "timestamps_granularity": "word",
                "diarize": str(diarize).lower(), "tag_audio_events": "false"}
        if language or self.cfg.get("language"):
            data["language_code"] = language or self.cfg["language"]   # auto-detect can mistake Darija for English
        for attempt in range(4):
            with open(path, "rb") as f:
                try:
                    r = httpx.post("https://api.elevenlabs.io/v1/speech-to-text", data=data,
                                   files={"file": (Path(path).name, f)},
                                   headers={"xi-api-key": secret("ELEVENLABS_API_KEY")}, timeout=900)
                except httpx.TransportError:
                    if attempt == 3:
                        raise
                    time.sleep(10 * (attempt + 1))
                    continue
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(10 * (attempt + 1))
        r.raise_for_status()
        out = r.json()
        return {"text": out.get("text", ""), "language_code": out.get("language_code", ""),
                "audio_duration_secs": out.get("audio_duration_secs"), "words": out.get("words", []),
                "engine": f"ElevenLabs {data['model_id']}"}
