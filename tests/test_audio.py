from panko.media import audio
from panko.providers.base import Audio


class EmptyTTS:
    name, cfg = "fake", {}

    def voices(self, variety):
        return ["V"]

    def speak(self, text, variety, out, voice=None):
        out.write_bytes(b"")          # what ElevenLabs returns for a one-letter word
        return Audio(out, "V (fake)", False)


def test_empty_audio_counts_as_none(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "MEDIA", tmp_path)
    monkeypatch.setattr(audio.providers, "chain", lambda cap: [EmptyTTS()])
    assert audio.speak("ف", "darija") is None
    assert not list(tmp_path.iterdir())
