"""`panko init`: a starter config for a new learner, and a check of what's ready.

`write_config(answers)` fills templates/panko.example.toml with the learner's answers (language, varieties, decks, Anki
profile…) and writes config/panko.toml; `.env` is created from `.env.example` for the keys. `check()` reports what
works: config, keys and providers, Anki, reference data, chat mode.
"""
from __future__ import annotations

import json
import shutil
import tomllib
import urllib.request
from pathlib import Path

from panko.config import ROOT

TEMPLATES = Path(__file__).parent / "templates"      # shipped inside the package
TEMPLATE = TEMPLATES / "panko.example.toml"
CONFIG = ROOT / "config" / "panko.toml"

DEFAULTS = {"language": "Moroccan Darija", "gloss_language": "English", "varieties": ["darija"],
            "deck_root": "Panko", "profile": "User 1", "translit": "a learner-friendly romanisation",
            "wiktionary": "Moroccan Arabic"}


def _q(v) -> str:
    return json.dumps(v, ensure_ascii=False)   # a JSON string or list is a valid TOML value


def evidence_block(varieties: list[str], wiktionary: str) -> str:
    out = []
    if "darija" in varieties:
        out.append('''[[evidence.corpora]]
name = "Darija Open Dataset (DODa)"
path = "cache/refs/doda"
url = "https://github.com/darija-open-dataset/dataset"
include = ["semantic categories/", "syntactic categories/", "sentences/", "x-tra/"]
notes = "word lists and a sentence corpus, mostly mainstream (Casablanca/Rabat) Darija"''')
    if wiktionary:
        slug = wiktionary.replace(" ", "")
        out.append(f'''[[evidence.corpora]]
name = {_q(f"Wiktionary, {wiktionary} entries")}
path = {_q(f"cache/refs/wiktionary-{slug.lower()}.jsonl")}
url = {_q(f"https://kaikki.org/dictionary/{wiktionary.replace(' ', '%20')}/kaikki.org-dictionary-{slug}.jsonl")}
notes = "sense tags can mark regional words"''')
    out.append('''# A dictionary or course book you own, as plain text (never shipped, never downloaded):
# [[evidence.dictionaries]]
# name = "My dictionary"
# path = "cache/refs/my-dictionary.txt"
# notes = "which romanisation it uses"''')
    return "\n\n".join(out)


def render(answers: dict) -> str:
    a = {**DEFAULTS, **{k: v for k, v in answers.items() if v not in (None, "", [])}}
    vs = [v.strip().lower() for v in a["varieties"] if v.strip()]
    vals = {
        "voices": "\n".join(f"voices_{v} = []" for v in vs),
        "decks": "\n".join(f"{v} = {_q(a['deck_root'] + '::' + v.capitalize())}" for v in vs),
        "profile": _q(a["profile"]), "language": _q(a["language"]), "varieties": _q(vs),
        "learner": _q(f"a {a['gloss_language']}-speaking learner"), "gloss_language": _q(a["gloss_language"]),
        "translit": _q(a["translit"]), "evidence": evidence_block(vs, a["wiktionary"]),
    }
    text = TEMPLATE.read_text()
    for k, v in vals.items():
        text = text.replace("{{" + k + "}}", v)
    tomllib.loads(text)   # fails loudly rather than writing a broken config
    return text


def write_config(answers: dict, force: bool = False, path: Path = CONFIG) -> Path:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; use --force to replace it (a copy is kept as .bak)")
    if path.exists():
        shutil.copy2(path, path.with_suffix(".toml.bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(answers))
    env = path.parent.parent / ".env"
    if not env.exists():
        shutil.copy2(TEMPLATES / "env.example", env)
    return path


def anki_profiles() -> list[str]:
    from panko.config import anki_folder
    d = anki_folder()
    return sorted(p.name for p in d.iterdir() if (p / "collection.anki2").exists()) if d.exists() else []


def _anki_reachable(url: str) -> bool:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    try:
        urllib.request.urlopen(req, timeout=3)
        return True
    except urllib.error.HTTPError:
        return True        # something answered on that port
    except OSError:
        return False


def check() -> list[tuple[str, bool, str]]:
    """(what, ok, detail) for each part of a working setup."""
    from panko import providers
    from panko.config import anki, collection_path, settings
    from panko.evidence import references_status
    rows = []
    try:
        s = settings()
        rows.append(("config", True, str(CONFIG)))
    except FileNotFoundError:
        return [("config", False, "no config/panko.toml: run `panko init`")]
    for cap, what in (("llm", "API mode (language model)"), ("audio", "audio"), ("images", "pictures")):
        ready = [p.name for p in providers.chain(cap) if p.name not in ("native", "source")]   # need your own material
        rows.append((what, bool(ready), ", ".join(ready) or f"no {cap} provider has its key in .env"))
    for v in s.get("learner", {}).get("varieties", []):
        voices = s.get("audio", {}).get("elevenlabs", {}).get(f"voices_{v}", [])
        rows.append((f"voices for {v}", bool(voices), ", ".join(voices) or "none set: cards get no audio"))
    a = anki()
    rows.append(("Anki (open, MCP add-on)", _anki_reachable(a["url"]),
                 a["url"] if _anki_reachable(a["url"]) else f"nothing answers at {a['url']}: open Anki with the "
                 "Anki MCP Server add-on"))
    col = collection_path()
    rows.append(("Anki collection (migrations)", col.exists(), str(col)))
    for r in references_status():
        rows.append((r["name"], r["present"], r["path"] if r["present"] else
                     ("`panko refs --download`" if r["url"] else f"add the file at {r['path']}")))
    try:
        import mcp  # noqa: F401
        rows.append(("chat mode (panko mcp)", True, "`panko mcp --config` for the Claude snippet"))
    except ImportError:
        rows.append(("chat mode (panko mcp)", False, "uv sync --extra mcp"))
    return rows
