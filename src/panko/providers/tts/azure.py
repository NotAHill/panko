from __future__ import annotations

from xml.sax.saxutils import escape

import httpx

from panko.config import secret
from panko.providers import register
from panko.providers.base import TTS, Audio


@register("audio", "azure")
class AzureTTS(TTS):
    needs = ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")

    def speak(self, text, variety, out) -> Audio | None:
        voice = self.cfg.get(f"voice_{variety}")
        if not voice:
            return None
        lang = "-".join(voice.split("-")[:2])
        ssml = f"<speak version='1.0' xml:lang='{lang}'><voice name='{voice}'>{escape(text)}</voice></speak>"
        r = httpx.post(
            f"https://{secret('AZURE_SPEECH_REGION')}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={"Ocp-Apim-Subscription-Key": secret("AZURE_SPEECH_KEY"),
                     "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3"},
            content=ssml.encode(), timeout=60,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return Audio(path=out, source=f"Azure {voice} (synthetic)", native=False)
