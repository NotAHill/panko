"""Choosing the voices that read your cards (ElevenLabs), for the hub's voice picker.

Browsing is free: your own ElevenLabs voices and the shared library, filtered for each variety by language and
accent (`library` in [audio.elevenlabs], e.g. {language = "ar", accent = "moroccan", fusha = {accent = "modern
standard"}}: a table named after a variety overrides the rest for it), by man or woman, each with its sample clip. Choosing a library voice adds it to your ElevenLabs
voices (needed before it can speak; library voices need a paid plan) and saves the pick in config/hub.toml as
`voices_<variety>` and `voice_ids`. A new voice means new audio for every card of that variety on the next sync,
which `panko sync --dry-run` (or the hub's sync plan) prices first.
"""
from __future__ import annotations

import re

import httpx

from panko.config import save_choices, secret, settings

B = "https://api.elevenlabs.io/v1"
GENDERS = {"male", "female", "neutral"}


def _cfg() -> dict:
    return settings().get("audio", {}).get("elevenlabs", {})


def _h() -> dict:
    key = secret("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("no ElevenLabs key: add ELEVENLABS_API_KEY to .env")
    return {"xi-api-key": key}


def _check(r: httpx.Response) -> dict:
    if r.is_error:
        try:
            msg = r.json().get("detail", {})
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f"ElevenLabs said {r.status_code}: {msg}")
    return r.json()


def _get(path: str, params: dict | None = None) -> dict:
    try:
        return _check(httpx.get(f"{B}{path}", headers=_h(), params=params or {}, timeout=30))
    except httpx.TransportError as e:
        raise RuntimeError(f"couldn't reach ElevenLabs: {e}") from e


def _post(path: str, body: dict) -> dict:
    try:
        return _check(httpx.post(f"{B}{path}", headers=_h(), json=body, timeout=30))
    except httpx.TransportError as e:
        raise RuntimeError(f"couldn't reach ElevenLabs: {e}") from e


def ready() -> bool:
    return bool(secret("ELEVENLABS_API_KEY"))


def _row(v: dict, mine: bool) -> dict:
    labels = v.get("labels") or {}
    return {"name": v.get("name", ""), "voice_id": v.get("voice_id", ""), "owner": v.get("public_owner_id", ""),
            "gender": v.get("gender") or labels.get("gender", ""), "age": v.get("age") or labels.get("age", ""),
            "accent": v.get("accent") or labels.get("accent", ""), "language": v.get("language", ""),
            "use": v.get("use_case") or labels.get("use_case", ""),
            "about": (v.get("description") or labels.get("description") or "")[:240],
            "sample": v.get("preview_url", ""), "mine": mine, "users": v.get("cloned_by_count", 0)}


def mine() -> list[dict]:
    """Voices already in your ElevenLabs account (built-in ones included)."""
    return [_row(v, True) for v in _get("/voices").get("voices", [])]


def filters(variety: str = "") -> dict:
    """{language, accent} the voices for a variety should have: `library` in config, with the variety's own table
    (if any) laid over it."""
    lib = _cfg().get("library", {})
    if not lib:          # nothing in config: from the language (an Iraqi Arabic learner gets Iraqi voices)
        from panko import lang
        return lang.voice_filter(variety)
    out = {k: v for k, v in lib.items() if not isinstance(v, dict)}
    return {**out, **(lib.get(variety) if isinstance(lib.get(variety), dict) else {})}


def _matches(v: dict, want: dict) -> bool:
    if want.get("accent"):
        return v["accent"].lower() == want["accent"].lower()
    return not want.get("language") or not v["language"] or v["language"] == want["language"]


def yours(variety: str = "", gender: str = "", search: str = "", any_accent: bool = False) -> list[dict]:
    """Your own voices that suit a variety (its accent, or its language), the ones Panko added first."""
    want = {} if any_accent else filters(variety)
    q = search.strip().lower()
    out = [v for v in mine() if _matches(v, want) and (gender not in GENDERS or v["gender"] == gender)
           and (not q or q in (v["name"] + " " + v["about"]).lower())]
    return sorted(out, key=lambda v: not v["name"].startswith("panko-"))


def library(gender: str = "", search: str = "", language: str = "", accent: str = "", page: int = 0,
            variety: str = "") -> dict:
    """The shared library, filtered by the variety's language and accent from config unless given."""
    lib = filters(variety)
    accent = "" if accent == "any" else (accent or lib.get("accent", ""))      # "any" lifts the config's accent
    params = {"page_size": 30, "page": max(0, int(page)), "language": language or lib.get("language", ""),
              "accent": accent}
    if gender in GENDERS:
        params["gender"] = gender
    if search.strip():
        params["search"] = search.strip()[:80]
    d = _get("/shared-voices", {k: v for k, v in params.items() if v not in ("", None)})
    return {"voices": [_row(v, False) for v in d.get("voices", [])], "more": bool(d.get("has_more"))}


def chosen(varieties: list[str]) -> dict:
    """Per variety, the voices that read its cards now, in order, with what's known about each."""
    cfg, ids = _cfg(), _cfg().get("voice_ids", {})
    known = {}
    if ready():
        try:
            known = {v["voice_id"]: v for v in mine()}
        except RuntimeError:
            known = {}
    out = {}
    for var in varieties:
        rows = []
        for name in cfg.get(f"voices_{var}", []):
            vid = ids.get(name, name)
            rows.append({**known.get(vid, {}), "name": name, "voice_id": vid})
        out[var] = rows
    return out


def _tag(name: str, vid: str, ids: dict) -> str:
    base = re.sub(r"[^\w-]+", "", (name.split() or ["voice"])[0]) or "voice"
    tag, n = base, 2
    while tag in ids and ids[tag] != vid:
        tag, n = f"{base}{n}", n + 1
    return tag


def choose(variety: str, picks: list[dict]) -> dict:
    """Save the voices for a variety, in order (e.g. a man then a woman: every word is read by each). A library
    voice is first added to your ElevenLabs voices. Returns {variety, voices: [names]}."""
    if variety not in settings().get("learner", {}).get("varieties", []):
        raise ValueError(f"no variety {variety!r} in [learner]")
    if not picks or len(picks) > 4:
        raise ValueError("pick one to four voices")
    ids = dict(_cfg().get("voice_ids", {}))
    names = []
    have = None
    for p in picks:
        vid = str(p.get("voice_id", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9]{8,64}", vid):
            raise ValueError(f"not a voice id: {vid!r}")
        if p.get("owner"):                      # from the shared library: add it to your voices first
            have = have if have is not None else {v["name"]: v["voice_id"] for v in mine()}
            base = _tag(str(p.get("name", "")), "", {})
            if have.get(f"panko-{base}"):           # added before (by the hub or `panko voices`)
                tag, vid = base, have[f"panko-{base}"]
            else:
                tag = _tag(base, "", ids)                # a different voice may already be called that
                vid = _post(f"/voices/add/{p['owner']}/{p['voice_id']}", {"new_name": f"panko-{tag}"})["voice_id"]
        else:
            tag = _tag(str(p.get("name", "")), vid, ids)
        ids[tag] = vid
        names.append(tag)
    save_choices("audio.elevenlabs", {f"voices_{variety}": names, "voice_ids": ids})
    return {"variety": variety, "voices": names}
