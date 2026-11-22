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
