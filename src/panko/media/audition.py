"""Audition ElevenLabs Moroccan voices: each reads the same sentence, the audio is
transcribed back (Scribe) as an intelligibility check, and a local page lets you
listen side by side. Needs a paid ElevenLabs plan (library voices).

    uv run panko voices            # default shortlist
    uv run panko voices --all      # every Moroccan voice in the library
"""
from __future__ import annotations

import html
import json

import httpx

from panko.config import CACHE, secret

B = "https://api.elevenlabs.io/v1"
SENTENCE = "سلام، كنقلب على كنابي كبير. واش تقدر تدير ليا تخفيض؟ إلا ما عندكش، ماشي مشكل، نرجع غدا."
SHORTLIST = ["Badr", "Ghalia", "Loubna", "Houssam", "Mouhcine", "Saad"]
OUT = CACHE / "voices"


def _h():
    return {"xi-api-key": secret("ELEVENLABS_API_KEY")}


def tier() -> str:
    return httpx.get(f"{B}/user/subscription", headers=_h(), timeout=30).json()["tier"]


def moroccan_voices() -> list[dict]:
    r = httpx.get(f"{B}/shared-voices", headers=_h(), timeout=30,
                  params={"page_size": 100, "language": "ar", "accent": "moroccan"})
    r.raise_for_status()
    return r.json()["voices"]


def _ensure_in_library(v: dict, mine: dict) -> str:
    tag = f"panko-{v['name'].split()[0]}"
    if tag in mine:
        return mine[tag]
    r = httpx.post(f"{B}/voices/add/{v['public_owner_id']}/{v['voice_id']}", headers=_h(),
                   json={"new_name": tag}, timeout=30)
    r.raise_for_status()
    mine[tag] = r.json()["voice_id"]
    return mine[tag]


def run(all_voices: bool = False) -> None:
    if tier() == "free":
        print("ElevenLabs is still on the free plan; library voices need a paid plan.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    voices = moroccan_voices()
    if not all_voices:
        voices = [v for v in voices if v["name"].split()[0] in SHORTLIST]
    mine = {v["name"]: v["voice_id"] for v in httpx.get(f"{B}/voices", headers=_h(), timeout=30).json()["voices"]}
    rows = []
    for v in voices:
        name = v["name"].split()[0]
        try:
            vid = _ensure_in_library(v, mine)
            f = OUT / f"{name}.mp3"
            if not f.exists():
                r = httpx.post(f"{B}/text-to-speech/{vid}", headers=_h(), timeout=120,
                               params={"output_format": "mp3_44100_128"},
                               json={"text": SENTENCE, "model_id": "eleven_v3"})
                r.raise_for_status()
                f.write_bytes(r.content)
            r = httpx.post(f"{B}/speech-to-text", headers=_h(), timeout=120, data={"model_id": "scribe_v1"},
                           files={"file": (f.name, f.read_bytes(), "audio/mpeg")})
            heard = r.json().get("text", "") if r.is_success else f"(transcription failed: {r.status_code})"
            rows.append({"name": v["name"], "voice_id": vid, "gender": v.get("gender"), "age": v.get("age"),
                         "file": f.name, "heard": heard})
            print(f"{name:10} {heard}")
        except httpx.HTTPError as e:
            print(f"{name:10} failed: {e}")
    (OUT / "voices.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    cards = "".join(
        f"<section><h2>{html.escape(r['name'])}</h2><p class=meta>{r['gender']}, {r['age']} · <code>{r['voice_id']}</code></p>"
        f"<audio controls preload=none src='{r['file']}'></audio><p class=heard dir=rtl>{html.escape(r['heard'])}</p></section>"
        for r in rows)
    (OUT / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Darija voices</title><style>"
        "body{font:16px -apple-system,sans-serif;max-width:640px;margin:24px auto;padding:0 16px}"
        "section{border-top:1px solid #ddd;padding:12px 0}h2{margin:0;font-size:18px}.meta{color:#777;font-size:13px;margin:2px 0 8px}"
        ".heard{font-size:20px;font-family:'Geeza Pro',serif}.target{background:#f4f4f4;padding:10px;border-radius:6px}</style>"
        f"<h1>Darija voices</h1><p>Each voice reads:</p><p class='target heard' dir=rtl>{html.escape(SENTENCE)}</p>"
        f"<p>Under each player is what speech-to-text heard back.</p>{cards}")
    print(f"open {OUT / 'index.html'}")
