"""Chat mode as a one-click Claude Desktop extension (`panko.mcpb`, track D4).

An extension is a zip that Claude's desktop app opens: a manifest, an icon, and here a `pyproject.toml` naming this
release of Panko on PyPI (`pankohub`). It's a "uv" extension (manifest 0.4): Claude installs Python and Panko itself,
so nothing needs installing first, and the bundle stays small. The only setting is the Panko folder (`~/Panko` by
default, the same folder `panko hub` uses), passed as `PANKO_HOME`.

Built on demand: by `panko mcp --bundle FILE`, the hub's setup page, and the front door's install page.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

NAME = "panko.mcpb"
ICON = Path(__file__).with_name("icon.png")
SERVER = '''"""Panko's chat mode, as Claude's desktop app starts it (see manifest.json)."""
from panko.cli import main

main(["mcp"])
'''


def _version() -> str:
    from panko import version
    return version() or "0.1.0"


def _tools() -> list[dict]:
    """The tools Claude gets, for the install dialog: each one's first sentence."""
    import asyncio

    from panko.mcp_server import server
    out = []
    for t in asyncio.run(server.list_tools()):
        first = re.split(r"(?<=\.)\s", " ".join((t.description or "").split()), maxsplit=1)[0].rstrip(".:;")
        out.append({"name": t.name, "description": first[:200]})
    return out


def manifest(version: str | None = None, folder: str | Path | None = None) -> dict:
    """`folder`: the Panko folder offered by default (a local hub offers its own; otherwise ~/Panko)."""
    from panko import SOURCE
    v = version or _version()
    return {
        "manifest_version": "0.4",
        "name": "panko",
        "display_name": "Panko",
        "version": v,
        "description": "Turn language-learning sources into checked Anki cards, with Claude doing the reading.",
        "long_description": (
            "Panko reads your lessons, teacher sheets, transcripts and old decks with you: Claude reads each page, "
            "Panko checks every word against dictionaries and your sources, finds pictures and example sentences, "
            "and keeps the cards in your Panko folder until you send them to Anki. Chat mode costs nothing beyond "
            "your Claude plan.\n\nRun `panko hub` (from `uv tool install pankohub`) for the dashboard and the Anki "
            "add-on; this extension uses the same folder."),
        "author": {"name": "Panko", "url": SOURCE},
        "repository": {"type": "git", "url": SOURCE},
        "homepage": SOURCE,
        "support": f"{SOURCE}/issues",
        "icon": "icon.png",
        "license": "AGPL-3.0-or-later",
        "keywords": ["anki", "flashcards", "language learning", "vocabulary", "arabic"],
        "server": {
            "type": "uv",
            "entry_point": "src/server.py",
            "mcp_config": {
                "command": "uv",
                "args": ["run", "--directory", "${__dirname}", "src/server.py"],
                "env": {"PANKO_HOME": "${user_config.folder}"},
            },
        },
        "user_config": {
            "folder": {
                "type": "directory",
                "title": "Panko folder",
                "description": "Where your cards, sources and settings live: the folder `panko hub` uses "
                               "(Panko in your home folder unless you chose another).",
                "default": str(folder) if folder else "${HOME}/Panko",
                "required": True,
            },
        },
        "tools": _tools(),
        "compatibility": {"platforms": ["darwin", "win32", "linux"], "runtimes": {"python": ">=3.12"}},
    }


def pyproject(version: str | None = None) -> str:
    v = version or _version()
    return (f'[project]\nname = "panko-claude-extension"\nversion = "{v}"\nrequires-python = ">=3.12"\n'
            f'dependencies = ["pankohub=={v}"]\n')


def bundle(version: str | None = None, folder: str | Path | None = None) -> bytes:
    """The extension as bytes: manifest.json at the root, the icon, pyproject.toml and src/server.py."""
    v = version or _version()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest(v, folder), indent=2, ensure_ascii=False) + "\n")
        z.writestr("pyproject.toml", pyproject(v))
        z.writestr("src/server.py", SERVER)
        z.write(ICON, "icon.png")
    return buf.getvalue()


def write(path: str | Path, folder: str | Path | None = None) -> Path:
    p = Path(path).expanduser()
    if p.is_dir():
        p = p / NAME
    p.write_bytes(bundle(folder=folder))
    return p
