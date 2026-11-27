"""The Panko sync add-on as a file to open in Anki: a zip of `src/panko/anki_addon`. Served by a Panko (its sync
page) and by the front door of a hosted one (the install page, for people without an account)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

NAME = "panko-sync.ankiaddon"


def addon_zip() -> bytes:
    src = Path(__file__).resolve().parent.parent / "anki_addon"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix in (".py", ".json", ".md"):
                z.write(f, f.relative_to(src).as_posix())
    return buf.getvalue()
