"""Native clips: the moment a recording says a word or phrase, cut out and used as the card's audio.

A transcript with word times (from speech-to-text, panko.providers.stt) is enough to find where an item is said.
`find` looks for the item's words in order, `cut` saves that stretch (ffmpeg) to data/media, and `register` adds it
to the native index (data/media/native.json), which the "native" audio provider reads. Native audio comes first in
the [audio] chain, so the card plays the real speaker instead of a synthetic voice.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from panko import lang
from panko.store.normalize import bare

PREFIX = "_panko_native_"
PAD_BEFORE, PAD_AFTER = 0.12, 0.3


def _media() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "media"


def index_path() -> Path:
    return _media() / "native.json"


def key(text: str) -> str:
    return bare(text).strip()


def load_index() -> dict:
    p = index_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def lookup(text: str) -> dict | None:
    """{"file", "source"} of a native clip of exactly this text (harakat and punctuation ignored)."""
    return load_index().get(key(text))


def register(text: str, file: str, source: str) -> None:
    idx = load_index()
    idx[key(text)] = {"file": file, "source": source}
    index_path().parent.mkdir(parents=True, exist_ok=True)
    index_path().write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


def _norm(tok: str) -> str:
    return bare(tok).lower()


def _bare_noun(t: str) -> str:
    """Without the article, as speech-to-text may write it (Arabic: ال or a lone ل, لبرية for البرية)."""
    return lang.bare_noun(t)


def _same(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) > 2 and _bare_noun(a) == _bare_noun(b))


def find(words: list[dict], text: str, avoid: str = "") -> dict | None:
    """Where `text` is said: {start, end, speaker, track} of the first run of transcript words matching its words in
    order, preferring a speaker other than `avoid` (the learner)."""
    want = [_norm(t) for t in lang.tokens(text, apostrophes=True)]
    ws = [w for w in words if w.get("type", "word") == "word" and lang.tokens(w["text"], apostrophes=True)]
    toks = [_norm(lang.tokens(w["text"], apostrophes=True)[0]) for w in ws]
    if not want:
        return None
    hits = []
    for i in range(len(toks) - len(want) + 1):
        if all(_same(toks[i + k], want[k]) for k in range(len(want))) \
                and len({ws[i + k].get("track", 0) for k in range(len(want))}) == 1:
            w0, w1 = ws[i], ws[i + len(want) - 1]
            hits.append({"start": w0["start"], "end": w1["end"], "speaker": w0.get("speaker", ""),
                         "track": w0.get("track", 0)})
    good = [h for h in hits if not avoid or h["speaker"] != avoid]
    return (good or hits or [None])[0]


def cut(src: Path, start: float, end: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    s = max(0.0, start - PAD_BEFORE)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{s:.2f}", "-to", f"{end + PAD_AFTER:.2f}", "-i",
                    str(src), "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "96k", str(out)], check=True)
    return out


def clip(text: str, words: list[dict], tracks: list[dict], title: str, avoid: str = "") -> dict | None:
    """Find, cut and register a clip of `text`; None when the recording doesn't say it. Existing clips are kept."""
    if lookup(text):
        return lookup(text)
    h = find(words, text, avoid)
    if not h:
        return None
    tr = tracks[h["track"]]
    name = PREFIX + hashlib.sha1(f"{tr['path']}|{h['start']}|{text}".encode()).hexdigest()[:12] + ".mp3"
    cut(Path(tr["path"]), h["start"], h["end"], _media() / name)
    m, s = divmod(int(h["start"]), 60)
    who = h["speaker"] or tr.get("speaker", "")
    source = f"{title}{f', {who}' if who else ''}, {m}:{s:02d} (recording)"
    register(text, name, source)
    return {"file": name, "source": source}
