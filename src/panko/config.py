"""Loads config/panko.toml and .env from the repo root."""
from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache"


@cache
def settings() -> dict:
    load_dotenv(ROOT / ".env")
    with open(ROOT / "config" / "panko.toml", "rb") as f:
        return tomllib.load(f)


def secret(name: str) -> str | None:
    settings()  # ensures .env is loaded
    return os.environ.get(name) or None


ANKI_DEFAULTS = {
    "url": "http://127.0.0.1:3141/",          # the Anki MCP Server add-on
    "profile": "User 1",                      # Anki profile whose collection migrations open
    "collection": "",                         # full path to collection.anki2, if not under the usual Anki folder
    "decks": {"darija": "Panko Sandbox::Darija", "fusha": "Panko Sandbox::Fusha"},
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
