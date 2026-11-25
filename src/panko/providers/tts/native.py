"""Real human audio we hold: clips cut from lesson recordings and other audio sources (panko.media.clips), looked
up by their text (harakat and punctuation ignored). First in the [audio] chain, so a card plays the real speaker."""
from __future__ import annotations

from panko.providers import register
from panko.providers.base import TTS, Audio


@register("audio", "native")
class NativeAudio(TTS):
    def speak(self, text, variety, out, voice=None) -> Audio | None:
        from panko.media import clips
        hit = clips.lookup(text)
        if not hit:
            return None
        return Audio(path=clips._media() / hit["file"], source=hit["source"], native=True)
