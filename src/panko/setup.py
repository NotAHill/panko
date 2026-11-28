"""`panko init`: a starter config for a new learner, and a check of what's ready.

`write_config(answers)` fills templates/panko.example.toml with the learner's answers (language, varieties, decks, Anki
profile…) and the preset for their language (templates/languages/*.toml: script, prompt wording, references,
speech-to-text language, voices), and writes config/panko.toml; `.env` is created from `.env.example` for the keys. `check()` reports what
works: config, keys and providers, Anki, reference data, chat mode.
"""
from __future__ import annotations

import json
import re
import shutil
import tomllib
import urllib.request
from pathlib import Path

from panko.config import ROOT

TEMPLATES = Path(__file__).parent / "templates"      # shipped inside the package
TEMPLATE = TEMPLATES / "panko.example.toml"
LANGUAGES = TEMPLATES / "languages"                 # presets: one TOML file per language
CONFIG = ROOT / "config" / "panko.toml"

DEFAULTS = {"language": "Moroccan Darija", "gloss_language": "English", "varieties": ["main"], "deck_root": "Panko",
            "profile": "User 1", "translit": "a learner-friendly romanisation", "wiktionary": "", "script": ""}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def presets() -> dict[str, Path]:
    """Language presets shipped with Panko, by slug ("moroccan-darija", "spanish")."""
    return {p.stem: p for p in sorted(LANGUAGES.glob("*.toml"))}


def preset(language: str) -> dict:
    """The preset for a language name or slug ({} when there is none: every setting then starts neutral)."""
    p = presets().get(_slug(language))
    return tomllib.loads(p.read_text(encoding="utf-8")) if p else {}


def defaults(language: str) -> dict:
    """What init offers for each question once the language is known."""
    language = language or DEFAULTS["language"]
    pre = preset(language)
    language = pre.get("answers", {}).get("language", language)     # "spanish" → "Spanish"
    d = {**DEFAULTS, "language": language, "wiktionary": language, "varieties": [_slug(language) or "main"],
         **pre.get("answers", {})}
    if pre:
        d["script"] = pre.get("learner", {}).get("script", "")
        d["translit"] = pre.get("learner", {}).get("translit", {}).get("main", d["translit"])
    return d


def _q(v) -> str:
    """A TOML value: JSON strings, lists, numbers and booleans are valid TOML; tables become inline tables."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k} = {_q(x)}" for k, x in v.items()) + "}"
    return json.dumps(v, ensure_ascii=False)


def _lines(d: dict) -> str:
    return "\n".join(f"{k} = {_q(v)}" for k, v in d.items())


def evidence_block(corpora: list[dict], wiktionary: str) -> str:
    out = [f"[[evidence.corpora]]\n{_lines(c)}" for c in corpora]
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


EXAMPLE_HINTS = """# verb = 'the dictionary form, e.g. the infinitive: comprar "to buy"'
# fixed_preposition = 'verbs that keep their preposition: acordarse de "to remember"'
# present = "the 1st-person singular present: compro"
# learner_note = "a regional note as it would read on a card"
# everyday_word = "The everyday word is …\""""


def render(answers: dict) -> str:
    """config/panko.toml text from the learner's answers and the preset for their language, if Panko has one."""
    given = {k: v for k, v in answers.items() if v not in (None, "", [])}
    a = {**defaults(given.get("language", "")), **{k: v for k, v in given.items() if k != "language"}}
    if "translit" in answers and answers["translit"] == "":
        a["translit"] = ""                       # an explicit "none"
    pre = preset(a["language"])
    L, audio = pre.get("learner", {}), pre.get("audio", {})
    tr = L.get("translit", {})
    vs = [v.strip().lower() for v in a["varieties"] if v.strip()]
    extra = {k: v for k, v in L.items() if k not in ("script", "mainstream", "regions", "examples", "translit")}
    vals = {
        "voices": "\n".join(f"voices_{v} = []" for v in vs),
        "audition": _lines({"library": audio.get("library", {}), "shortlist": audio.get("shortlist", []),
                            "audition": audio.get("audition", "")}),
        "stt_language": _q(pre.get("stt", {}).get("language", "")),
        "morph_dbs": _q({v: db for v, db in pre.get("morph", {}).get("dbs", {}).items() if v in vs}),
        "decks": "\n".join(f"{v} = {_q(a['deck_root'] + '::' + v.capitalize())}" for v in vs),
        "profile": _q(a["profile"]), "language": _q(a["language"]), "varieties": _q(vs),
        "script": _q(a["script"]),
        "learner": _q(f"{'an' if a['gloss_language'][:1].lower() in 'aeiou' else 'a'} {a['gloss_language']}-speaking "
                      "learner"), "gloss_language": _q(a["gloss_language"]),
        "learner_extra": _lines(extra),
        "mainstream": _q(L.get("mainstream", "")), "regions": _q(L.get("regions", [])),
        "examples": _lines(L.get("examples", {})) or EXAMPLE_HINTS,
        "translit": _q(a["translit"]), "translit_rules": _q(tr.get("main_rules", "")),
        "translit_alt": _q(tr.get("alt", "scholarly transliteration") if a["translit"] else ""),
        "none_for": _q([v for v in tr.get("none_for", []) if v in vs] or ([] if a["translit"] else vs)),
        "evidence": evidence_block(pre.get("evidence", {}).get("corpora", []), a["wiktionary"]),
    }
    text = TEMPLATE.read_text(encoding="utf-8")
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
    path.write_text(render(answers), encoding="utf-8")
    env = path.parent.parent / ".env"
    if not env.exists():
        shutil.copy2(TEMPLATES / "env.example", env)
    return path


# ---- keys (.env) -----------------------------------------------------------------------------------------------------
# Set from the hub's setup page as well as by editing .env. Only the names env.example lists; values are never sent
# back, only whether each is set. On the server the paths to local tools aren't the user's to set.

LOCAL_ONLY_KEYS = {"PANKO_CAMEL_PYTHON", "CAMELTOOLS_DATA"}
KEY_NAME = re.compile(r"^([A-Z][A-Z0-9_]*)=")


def keys() -> list[dict]:
    """[{name, note, set}] in env.example's order; `note` is the comment above each group."""
    import os

    from panko.config import hosted, settings
    try:
        settings()          # loads .env into the environment
    except FileNotFoundError:
        pass
    out, note = [], ""
    for line in (TEMPLATES / "env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            note = "" if line.startswith(("# Copy", "# Keep")) else line.lstrip("# ").strip()
            continue
        m = KEY_NAME.match(line)
        if m and not (hosted() and m[1] in LOCAL_ONLY_KEYS):
            out.append({"name": m[1], "note": note, "set": bool(os.environ.get(m[1])),
                        "server": bool(os.environ.get(f"PANKO_DEFAULT_{m[1]}"))})
        elif not line.strip():
            note = ""
    return out


def set_key(name: str, value: str, env: Path | None = None) -> Path:
    """Write NAME=value into the Panko folder's .env (readable by you only) and into this process, so the change works
    without a restart. An empty value removes it."""
    import os
    allowed = {k["name"] for k in keys()}
    if name not in allowed:
        raise ValueError(f"{name} isn't a key Panko uses here")
    value = (value or "").strip()
    if any(c in value for c in "\r\n\0") or len(value) > 4000:
        raise ValueError("that doesn't look like a key")
    env = env or ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    line = f"{name}={value}"
    for i, old in enumerate(lines):
        if old.startswith(f"{name}="):
            lines[i] = line
            break
    else:
        lines.append(line)
    env.parent.mkdir(parents=True, exist_ok=True)
    tmp = env.with_name(".env.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, env)
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)
    return env


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
    from panko.config import hosted
    keys_at = "under keys below" if hosted() else "in .env (or under keys in the hub's setup)"
    for cap, what in (("llm", "API mode (language model)"), ("audio", "audio"), ("images", "pictures")):
        ready = [p.name for p in providers.chain(cap) if p.name not in ("native", "source")]   # need your own material
        rows.append((what, bool(ready), ", ".join(ready) or f"no {cap} provider has its key yet: add one {keys_at}"))
    for v in s.get("learner", {}).get("varieties", []):
        voices = s.get("audio", {}).get("elevenlabs", {}).get(f"voices_{v}", [])
        rows.append((f"voices for {v}", bool(voices), ", ".join(voices) or "none set: cards get no audio"))
    if not hosted():         # on the server, cards reach Anki through the Panko add-on instead
        a = anki()
        rows.append(("Anki (open, MCP add-on)", _anki_reachable(a["url"]),
                     a["url"] if _anki_reachable(a["url"]) else f"nothing answers at {a['url']}: open Anki with the "
                     "Anki MCP Server add-on"))
        col = collection_path()
        rows.append(("Anki collection (migrations)", col.exists(), str(col)))
    for r in references_status():
        rows.append((r["name"], r["present"], r["path"] if r["present"] else
                     (("download it below" if hosted() else "`panko refs --download`") if r["url"]
                      else f"add the file at {r['path']}")))
    if hosted():             # connecting your Claude to the server comes with H4
        return rows
    try:
        import mcp  # noqa: F401
        rows.append(("chat mode (panko mcp)", True, "`panko mcp --config` for the Claude snippet"))
    except ImportError:
        rows.append(("chat mode (panko mcp)", False, "uv sync --extra mcp"))
    return rows
