"""Loads config/panko.toml and .env from the Panko folder.

The Panko folder holds a learner's config, data and cache: `PANKO_HOME` if set, else the nearest folder up from
where Panko runs that has `config/panko.toml`, else this source checkout when Panko runs from one, else the current
folder (where `panko init` then writes the config)."""
from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

CHECKOUT = Path(__file__).resolve().parents[2]
IS_CHECKOUT = (CHECKOUT / "pyproject.toml").exists() and (CHECKOUT / "src" / "panko").is_dir()


def find_root() -> Path:
    if os.environ.get("PANKO_HOME"):
        return Path(os.environ["PANKO_HOME"]).expanduser().resolve()
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if (d / "config" / "panko.toml").exists():
            return d
    return CHECKOUT if IS_CHECKOUT else cwd


ROOT = find_root()
CACHE = ROOT / "cache"


def choices_path() -> Path:
    """Choices made in the hub (card design, pictures, voices). They override config/panko.toml, which keeps your
    comments untouched; delete this file to go back to panko.toml alone."""
    return ROOT / "config" / "hub.toml"


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@cache
def settings() -> dict:
    load_dotenv(ROOT / ".env")
    path = ROOT / "config" / "panko.toml"
    if not path.exists():
        raise FileNotFoundError(f"no Panko config at {path}: run `panko init` in your Panko folder "
                                "(or set PANKO_HOME to it)")
    with open(path, "rb") as f:
        base = tomllib.load(f)
    over = choices_path()
    if over.exists():
        with open(over, "rb") as f:
            base = _merge(base, tomllib.load(f))
    return base


def choices() -> dict:
    p = choices_path()
    if not p.exists():
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


def save_choices(section: str, values: dict) -> Path:
    """Replace one dotted section of config/hub.toml (e.g. "cards", "audio.elevenlabs") with `values`, merged into
    what that section already holds there. None removes a key. Settings are read again afterwards."""
    data = choices()
    node = data
    for part in section.split("."):
        node = node.setdefault(part, {})
    for k, v in values.items():
        if v is None:
            node.pop(k, None)
        else:
            node[k] = v
    p = choices_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Choices made in the Panko hub. They override config/panko.toml; delete a section to undo it.\n\n"
                 + dump_toml(data))
    settings.cache_clear()
    return p


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        if "\n" in v:
            return '"""' + v.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '"""'
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{_toml_key(k)} = {_toml_value(x)}" for k, x in v.items()) + "}"
    raise TypeError(f"can't write {type(v).__name__} to TOML")


def _toml_key(k: str) -> str:
    import re
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else _toml_value(k)


def dump_toml(data: dict, prefix: str = "") -> str:
    """Enough TOML for hub choices: tables of strings, numbers, booleans, lists and inline tables."""
    tables = {k: v for k, v in data.items() if isinstance(v, dict) and v}
    out = "".join(f"{_toml_key(k)} = {_toml_value(v)}\n" for k, v in data.items() if k not in tables)
    for k, v in tables.items():
        name = f"{prefix}.{_toml_key(k)}" if prefix else _toml_key(k)
        out += f"\n[{name}]\n" + dump_toml(v, name)
    return out


def secret(name: str) -> str | None:
    settings()  # ensures .env is loaded
    return os.environ.get(name) or None


ANKI_DEFAULTS = {
    "url": "http://127.0.0.1:3141/",          # the Anki MCP Server add-on
    "profile": "User 1",                      # Anki profile whose collection migrations open
    "collection": "",                         # full path to collection.anki2, if not under the usual Anki folder
    "decks": {},                              # variety → deck; unnamed ones go to Panko::<Variety>
    "card_map": {},                           # old note type → Panko card per template ord (migrations)
}


def anki() -> dict:
    """`[anki]` from config over the defaults (decks merged, so a config can name one variety's deck)."""
    a = settings().get("anki", {})
    return {**ANKI_DEFAULTS, **a, "decks": {**ANKI_DEFAULTS["decks"], **a.get("decks", {})}}


def deck(variety: str) -> str:
    return anki()["decks"].get(variety) or f"Panko::{variety.capitalize()}"


def anki_folder() -> Path:
    """Where Anki keeps its profiles on this system."""
    import sys
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Anki2"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "Anki2"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "Anki2"


def collection_path() -> Path:
    a = anki()
    return Path(a["collection"]).expanduser() if a["collection"] else anki_folder() / a["profile"] / "collection.anki2"
