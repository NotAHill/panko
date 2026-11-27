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


# ---- hosted mode ---------------------------------------------------------------------------------------------------
# On the server (docs/SPEC-hosted.md) each user's Panko runs with PANKO_HOSTED=1 behind the front door. Its limits
# come from the environment the front door sets, never from the user's own config, which they can edit.

def hosted() -> bool:
    """True when this Panko runs on the server for one user, rather than on the learner's own computer."""
    return os.environ.get("PANKO_HOSTED", "").strip().lower() not in ("", "0", "false", "no")


def host_limits() -> dict:
    """Upload size (MB, per request) and disk quota (GB, the whole Panko folder) on the server."""
    def num(name, default):
        try:
            return float(os.environ.get(name) or default)
        except ValueError:
            return float(default)
    return {"upload_mb": num("PANKO_UPLOAD_MB", 500), "quota_gb": num("PANKO_QUOTA_GB", 5)}


def folder_size(path) -> int:
    total = 0
    for d, _, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return total


_USE: list = [0.0, 0]          # [when measured, bytes]: walking a big folder takes a moment, so it's reused briefly
USE_FOR = 30                   # seconds


def disk_use(fresh: bool = True) -> int:
    """Bytes the Panko folder holds (what the quota counts). `fresh=False` may answer from the last half minute."""
    import time
    if fresh or time.time() - _USE[0] > USE_FOR:
        _USE[:] = [time.time(), folder_size(ROOT)]
    return _USE[1]


QUOTA_NEAR = 0.8               # a warning from here; at 1.0 steps that add data stop


def quota_state(fresh: bool = False) -> dict | None:
    """On the server: {used, quota (bytes), pct, level: ok | near | full}; None on your own computer."""
    if not hosted():
        return None
    quota = host_limits()["quota_gb"] * 1e9
    used = disk_use(fresh)
    frac = used / quota if quota else 1
    return {"used": used, "quota": quota, "pct": round(100 * frac, 1),
            "level": "full" if frac >= 1 else "near" if frac >= QUOTA_NEAR else "ok"}


def room_for(n: int) -> None:
    """On the server, refuse to add `n` bytes that would take the Panko folder over its quota."""
    if not hosted():
        return
    quota = host_limits()["quota_gb"] * 1e9
    used = disk_use()
    if used + n > quota:
        raise ValueError(f"that needs {n / 1e6:,.0f} MB and your Panko has {max(quota - used, 0) / 1e6:,.0f} MB left "
                         f"of {quota / 1e9:g} GB: see what takes room in setup, or remove a source")


def not_full() -> None:
    """On the server, refuse a step that adds data when the Panko folder is already at its quota."""
    q = quota_state(fresh=True)
    if q and q["level"] == "full":
        raise ValueError(f"your Panko is full ({q['used'] / 1e9:.2f} of {q['quota'] / 1e9:g} GB), so this step would "
                         "go over: free up room first (setup → disk shows what takes room)")


def public_url(u: str) -> str:
    """On the server, a URL from the user's config (a reference, a library index) must be https to a public name, so
    it can't be used to reach the server's own or its network's services."""
    if not hosted():
        return u
    import ipaddress
    from urllib.parse import urlsplit
    host = (urlsplit(u).hostname or "").lower()
    bad = not u.startswith("https://") or not host or host == "localhost" or host.endswith((".local", ".internal"))
    try:
        ip = ipaddress.ip_address(host)
        bad = bad or not ip.is_global
    except ValueError:
        pass
    if bad:
        raise ValueError(f"on the server, downloads must be https from a public site: {u}")
    return u


def inside(p: str | Path) -> Path:
    """A path the learner gave or a source stored, relative to the Panko folder unless absolute. On the server it must
    be inside their own folder (files come in by upload), so no one reads another user's files or the server's."""
    q = Path(p).expanduser()
    q = q if q.is_absolute() else ROOT / q
    if hosted() and not q.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("on the server, files come in by upload: this path is outside your Panko folder")
    return q


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
    """A key from the environment or .env. On the server, the front door may give every Panko a shared key as
    PANKO_DEFAULT_<NAME> (the free photo sites): the user's own key wins when they've added one."""
    settings()  # ensures .env is loaded
    return os.environ.get(name) or os.environ.get(f"PANKO_DEFAULT_{name}") or None


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
