from __future__ import annotations

import time

import httpx

from panko.config import secret
from panko.providers import register
from panko.providers.base import TTS, Audio


@register("audio", "elevenlabs")
class ElevenLabs(TTS):
    needs = ("ELEVENLABS_API_KEY",)

    def voices(self, variety):
        return list(self.cfg.get(f"voices_{variety}", []))

    def speak(self, text, variety, out, voice=None) -> Audio | None:
        names = self.voices(variety)
        name = voice or (names[0] if names else None)
        vid = self.cfg.get("voice_ids", {}).get(name, name)
        if not vid:
            return None
        for attempt in range(5):  # ride out brief server errors and rate limits
            try:
                r = httpx.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                    params={"output_format": self.cfg.get("format", "mp3_44100_128")},
                    headers={"xi-api-key": secret("ELEVENLABS_API_KEY")},
                    json={"text": text, "model_id": self.cfg.get("model", "eleven_v3"), "language_code": "ar"},
                    timeout=60,
                )
            except httpx.TransportError:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        out.write_bytes(r.content)
        return Audio(path=out, source=f"{name} (ElevenLabs)", native=False)
