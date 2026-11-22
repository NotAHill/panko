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


GEN_PREFIX = "_panko_proto_gen_"


def draw(prompts: dict[str, str], force: bool = False, workers: int = 6, store=None, out: Path | None = None,
         gen=None) -> dict[str, str]:
    """Generate a memorable illustration for each entry id in `prompts` ({id: what to draw}) and set it as the
    entry's picture. Entries that already have a picture are skipped unless `force`. Returns {id: file | error}."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    from panko.config import ROOT, settings
    from panko.providers.imagegen import Generate
    from panko.store import Store

    st = store or Store()
    out = out or ROOT / "data" / "media"
    model = settings()["images"]["generate"].get("model", "")
    gen = gen or Generate({})
    todo = {i: p for i, p in prompts.items() if p and (force or not (st.get(i) or {}).get("image"))}

    def one(item):
        eid, prompt = item
        name = f"{GEN_PREFIX}{eid}.jpg"
        png = out / f"{GEN_PREFIX}{eid}.png"
        try:
            gen.generate(prompt, png)
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", "640",
                            str(png), "--out", str(out / name)], check=True, capture_output=True)
            png.unlink()
            return eid, name, prompt
        except Exception as e:  # noqa: BLE001
            return eid, None, f"error: {e}"

    res = {}
    with ThreadPoolExecutor(workers) as ex:
        for eid, name, info in ex.map(one, todo.items()):
            if name:
                e = st.get(eid)
                e["image"] = {"file": name, "credit": f"Illustration generated ({model})", "prompt": info}
                st.put(e)
            res[eid] = name or info
            print(eid, res[eid], flush=True)
    return res
