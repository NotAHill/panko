from panko.media import audio
from panko.providers.base import Audio


class EmptyTTS:
    name, cfg = "fake", {}

    def voices(self, variety):
        return ["V"]

    def speak(self, text, variety, out, voice=None):
        out.write_bytes(b"")          # what ElevenLabs returns for a one-letter word
        return Audio(out, "V (fake)", False)


def test_empty_audio_counts_as_none_and_is_not_asked_again(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "MEDIA", tmp_path)
    tts = EmptyTTS()
    asked = []
    real = tts.speak
    tts.speak = lambda *a, **k: asked.append(a[0]) or real(*a, **k)
    monkeypatch.setattr(audio.providers, "chain", lambda cap: [tts])
    assert audio.speak("ف", "darija") is None
    assert not list(tmp_path.glob("*.mp3"))
    # remembered: not "still to make" in a dry run (the add-on and the sync page stop offering it), not asked again
    todo = []
    assert audio.speak("ف", "darija", dry=todo) is None and todo == []
    assert audio.speak("ف", "darija") is None and asked == ["ف"]
