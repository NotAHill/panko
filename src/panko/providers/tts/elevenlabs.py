from __future__ import annotations

import httpx

from panko.config import secret
from panko.providers import register
from panko.providers.base import TTS, Audio


@register("audio", "elevenlabs")
class ElevenLabs(TTS):
    needs = ("ELEVENLABS_API_KEY",)

    def speak(self, text, variety, out) -> Audio | None:
        voice = self.cfg.get(f"voice_{variety}")
        if not voice:
            return None
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            params={"output_format": self.cfg.get("format", "mp3_44100_128")},
            headers={"xi-api-key": secret("ELEVENLABS_API_KEY")},
            json={"text": text, "model_id": self.cfg.get("model", "eleven_v3"), "language_code": "ar"},
            timeout=60,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return Audio(path=out, source=f"ElevenLabs {self.cfg.get('model')} (synthetic)", native=False)
