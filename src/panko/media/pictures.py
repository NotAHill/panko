"""Find candidate pictures for a word and lay them out on a numbered contact sheet
so a human (or a vision model) can pick one. Usage:
    uv run python -m panko.media.pictures "sofa living room" out_dir
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx

from panko import providers
from panko.providers.images.commons import UA


def candidates(query: str, per_provider: int = 6) -> list[dict]:
    out = []
    for p in providers.chain("images"):
        if not hasattr(p, "search"):
            continue
        try:
            for c in p.search(query, per_provider):
                out.append({**c, "provider": p.name})
        except httpx.HTTPError as e:
            print(f"  {p.name}: {e}", file=sys.stderr)
    return [c for c in out if c.get("thumb")]


def contact_sheet(cands: list[dict], out: Path, cell: int = 300) -> Path:
    from PIL import Image, ImageDraw

    cols = 4
    rows = (len(cands) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    for i, c in enumerate(cands):
        try:
            img = Image.open(io.BytesIO(httpx.get(c["thumb"], headers=UA, timeout=30, follow_redirects=True).content))
            img.thumbnail((cell - 8, cell - 28))
            sheet.paste(img.convert("RGB"), ((i % cols) * cell + 4, (i // cols) * cell + 24))
        except Exception as e:  # noqa: BLE001
            c["error"] = str(e)
        draw.rectangle([(i % cols) * cell, (i // cols) * cell, (i % cols) * cell + 60, (i // cols) * cell + 20], fill="black")
        draw.text(((i % cols) * cell + 4, (i // cols) * cell + 4), f"{i} {c['provider'][:2]}", fill="white")
    sheet.save(out)
    return out


if __name__ == "__main__":
    q, d = sys.argv[1], Path(sys.argv[2])
    d.mkdir(parents=True, exist_ok=True)
    slug = q.replace(" ", "_")
    cs = candidates(q)
    (d / f"{slug}.json").write_text(json.dumps(cs, indent=1, ensure_ascii=False))
    print(contact_sheet(cs, d / f"{slug}.jpg"), len(cs))
