"""Lesson recordings as sources: transcript → timed units, native clips cut at ingest and played as card audio."""
import json
import shutil
import subprocess

import pytest

from panko import work
from panko.cards import build
from panko.media import clips
from panko.media.audio import Narrator, Voiced
from panko.store import Store


def w(text, start, end, spk="speaker_0"):
    return {"text": text, "start": start, "end": end, "type": "word", "speaker_id": spk}


SCRIBE = {"language_code": "ara", "audio_duration_secs": 400.0, "words": [
    w("السلام", 0.5, 1.0), {"text": " ", "start": 1.0, "end": 1.1, "type": "spacing"}, w("عليكم", 1.1, 1.6),
    w("بغيت", 2.0, 2.4, "speaker_1"), w("نصيفط", 2.5, 3.0, "speaker_1"), w("البرية", 3.1, 3.6, "speaker_1"),
    w("بغيتي", 10.0, 10.5), w("تصيفط", 10.6, 11.0), w("لبرية", 11.1, 11.7),     # after a pause: a new line
    w("الطابع", 200.0, 200.6)]}


@pytest.fixture
def rec(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(work, "duration", lambda p: 400.0)
    monkeypatch.setattr(clips, "_media", lambda: tmp_path / "media")
    audio = tmp_path / "lesson.mp3"
    audio.write_bytes(b"not really audio")
    tr = tmp_path / "scribe.json"
    tr.write_text(json.dumps(SCRIBE, ensure_ascii=False))
    return tmp_path, audio, tr


def test_recording_becomes_timed_units(rec):
    _, audio, tr = rec
    s = work.add_source(str(audio), "lesson", "Post office", speakers=["teacher", "me"], learner="me",
                        transcript=str(tr))
    assert s["type"] == "audio" and s["units"] == ["a001", "a002", "a003"] and s["learner"] == "me"
    lines = work.page("post-office", "a001")["text"].splitlines()
    assert lines == ["[0:00] teacher: السلام عليكم", "[0:02] me: بغيت نصيفط البرية", "[0:10] teacher: بغيتي تصيفط لبرية"]
    assert work.page("post-office", "a002")["text"] == "[3:20] teacher: الطابع"
    assert work.page("post-office", "a003")["text"] == ""


def test_transcribe_with_a_provider(rec):
    _, audio, _ = rec
    s = work.add_source(str(audio), "lesson", "Post office")
    assert s["units"] == [] and work.pending("post-office")["transcribe_first"]
    with pytest.raises(ValueError, match="transcribe"):
        work.page("post-office", "a001")

    class FakeSTT:
        name = "fake"

        def transcribe(self, path, language="", diarize=True):
            assert diarize
            return {**SCRIBE, "engine": "fake stt"}

    s = work.transcribe("post-office", FakeSTT())
    assert s["units"] == ["a001", "a002", "a003"] and work.sources()["post-office"]["units"] == s["units"]
    assert work.transcript("post-office")["engine"] == "fake stt"


def test_find_skips_the_learner_and_matches_the_article():
    words = [{**x, "speaker": "me" if x["speaker_id"] == "speaker_1" else "teacher", "track": 0}
             for x in SCRIBE["words"] if x["type"] == "word"]
    hit = clips.find(words, "بغيت نصيفط البرية")
    assert hit["speaker"] == "me" and hit["start"] == 2.0          # only the learner said it: still found
    hit = clips.find(words, "تصيفط البرية", avoid="me")              # لبرية in the recording, البرية in the item
    assert (hit["start"], hit["end"], hit["speaker"]) == (10.6, 11.7, "teacher")
    assert clips.find(words, "الطابع")["start"] == 200.0
    assert clips.find(words, "كاس") is None


def test_ingest_cuts_clips_and_cards_play_them_once(rec, monkeypatch):
    tmp, audio, tr = rec
    cuts = []

    def fake_cut(src, start, end, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"clip")
        cuts.append((start, end))
        return out
    monkeypatch.setattr(clips, "cut", fake_cut)
    store = Store(tmp / "t.db")
    work.add_source(str(audio), "lesson", "Post office", speakers=["teacher", "me"], learner="me", transcript=str(tr))
    item = {"kind": "word", "ar": "الطابع", "tl": "t-tabe3", "gloss": "stamp", "pos": "noun",
            "examples": [{"ar": "بغيتي تصيفط لبرية", "en": "you want to send a letter", "source": "source"}],
            "verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}}
    ghost = {**item, "ar": "كاس", "tl": "kas", "gloss": "glass", "examples": []}
    assert work.submit("post-office", "a001", {"items": [item, ghost]})["ok"]
    rep = work.ingest_source("post-office", store)
    assert rep["clips"] == {"cut": 2, "kept": 0, "not_found": ["كاس"]}
    assert sorted(cuts) == [(10.0, 11.7), (200.0, 200.6)]
    hit = clips.lookup("الطابِع")                                   # harakat don't matter
    assert hit["source"] == "Post office, teacher, 3:20 (recording)"

    from panko.providers.tts.native import NativeAudio
    got = NativeAudio({}).speak("الطابع", "darija", tmp / "x.mp3")
    assert got.native and got.path == tmp / "media" / hit["file"]

    class TwoVoices(Narrator):     # what speak() gives when native comes first: the same clip for every slot
        def count(self, variety):
            return 2

        def say(self, text, variety, slot=0):
            h = clips.lookup(text)
            return Voiced(h["file"], h["source"]) if h else Voiced(f"tts{slot}.mp3", f"voice {slot}")

    entry = next(e for e in store.entries("candidate") if e["ar"] == "الطابع")
    note = build.to_note(entry, TwoVoices())
    assert note["fields"]["Audio"] == f"[sound:{hit['file']}]"
    ghost_note = build.to_note(next(e for e in store.entries("candidate") if e["ar"] == "كاس"), TwoVoices())
    assert ghost_note["fields"]["Audio"] == "[sound:tts0.mp3][sound:tts1.mp3]"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_cut_makes_a_short_clip(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(src)],
                   check=True)
    out = clips.cut(src, 1.0, 1.5, tmp_path / "c.mp3")
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(out)], capture_output=True, text=True).stdout)
    assert 0.8 < secs < 1.1
