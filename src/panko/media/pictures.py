"""Pictures for cards: real photos first, generated drawings as the fallback.

The flow (`panko pictures …`, see data/sources/decks/PICTURE-BRIEF.md):
1. export   cards without a picture → a JSON list for whoever decides (Claude, following PICTURE-BRIEF).
2. search   English queries → candidates from the free sites in the [images] chain (Wikidata, Commons, Openverse,
            Pexels, Pixabay…), taken in turn from each, + numbered contact sheets.
3. apply    decisions {id: {"photo": {dir, index}} | {"prompt": …} | {"skip": …}}: downloads and credits the
            chosen photos, then draws the prompts now (`draw`) or as an OpenAI batch (`draw_batch` + `collect`).
"""
from __future__ import annotations

import io
import itertools
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from panko import providers
from panko.config import inside
from panko.providers.images.web import UA

GEN_PREFIX = "_panko_proto_gen_"
PHOTO_PREFIX = "_panko_proto_"


def _media() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "media"


def _batches_file() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "draw-batches.json"


# 1. export ------------------------------------------------------------------------------------------------------

def export(store, status: str = "active", batch: int | None = None, ids: list[str] | None = None) -> list[dict]:
    """Cards without a picture, with what a decider needs to judge them."""
    rows = []
    for e in store.entries(status):
        if e.get("image") or (batch is not None and e.get("batch") != batch) or (ids and e["id"] not in ids):
            continue
        if e.get("picture_pref") == "none":
            continue
        ex = next((x.get("en") for x in e.get("examples", []) if x.get("en")), "")
        row = {"id": e["id"], "ar": e["ar"], "tl": e.get("tl", ""), "pos": e.get("pos", ""), "kind": e["kind"],
               "gloss": e.get("gloss", ""), "note": e.get("gloss_note", "") or e.get("usage", ""), "example_en": ex}
        wish = request(e)
        if wish:
            row["request"] = wish
        rows.append(row)
    return rows


PREFS = {"photo": "a real photo", "drawing": "a drawing"}


def request(entry: dict) -> str:
    """The learner's wish for this card's picture, in words the planner reads ("" when there is none)."""
    pref, text = PREFS.get(entry.get("picture_pref", "")), str(entry.get("picture_request") or "").strip()
    return "; ".join(x for x in (pref and f"wants {pref}", text) if x)


def drawings_allowed() -> bool:
    """Drawings are made only while `generate` is in the [images] chain (the hub's "drawn pictures" switch)."""
    from panko.config import settings
    return "generate" in settings().get("images", {}).get("chain", [])


# 2. search ------------------------------------------------------------------------------------------------------

def _searchers(names: list[str] | None = None) -> list:
    """The photo sites in the [images] chain, after your own pictures (unless `[images] reuse = false`)."""
    from panko.config import settings
    found = [p for p in providers.chain("images", names) if hasattr(p, "search")]
    if names is None and settings().get("images", {}).get("reuse", True) and not any(p.name == "yours" for p in found):
        mine = providers.get("images", "yours")
        if mine is not None:
            found.insert(0, mine)
    return found


def candidates(query: str, per_provider: int = 6, names: list[str] | None = None,
               errors: dict | None = None) -> list[dict]:
    """Candidates from each search provider, taken in turn (1st of each, then 2nd of each…) so every site shows up
    on a sheet and the most precise one (first in the chain) leads. A site that fails is skipped (and named in
    `errors`, {site: reason}, when given)."""
    found = []
    for p in _searchers(names):
        try:
            found.append([{**c, "provider": p.name} for c in p.search(query, per_provider) if c.get("thumb")])
        except httpx.HTTPError as e:
            print(f"  {p.name}: {e}", file=sys.stderr)
            if errors is not None:
                errors[p.name] = str(e)
    return [c for rnd in itertools.zip_longest(*found) for c in rnd if c]


def _on_white(im):
    """RGB, with any transparency (pictograms) on white instead of black."""
    from PIL import Image
    if im.mode in ("RGBA", "LA", "P", "PA"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.getchannel("A"))
        return bg
    return im.convert("RGB")



def _to_jpeg(src: Path | bytes, dst: Path, longest: int, quality: int) -> None:
    """Any image → RGB JPEG whose longest side is at most `longest` px (never enlarged)."""
    from PIL import Image
    with Image.open(io.BytesIO(src) if isinstance(src, bytes) else src) as im:
        im.load()
        out = _on_white(im)
    out.thumbnail((longest, longest), Image.LANCZOS)
    out.save(dst, "JPEG", quality=quality, optimize=True)

def _fetch(c: dict):
    from PIL import Image
    if c.get("file"):                                  # one of your own pictures: already here
        try:
            with Image.open(_media() / c["file"]) as im:
                im.load()
                return _on_white(im)
        except OSError:
            return None
    for attempt in range(2):                          # image hosts throttle bursts of parallel fetches
        try:
            r = httpx.get(c["thumb"], headers=UA, timeout=30, follow_redirects=True)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content))
            im.load()
            return _on_white(im)
        except Exception:  # noqa: BLE001
            if attempt == 0:
                time.sleep(2)
    return None


# provider → short tag printed next to each candidate's number on a sheet
TAGS = {"yours": "yo", "wikidata": "wd", "commons": "cm", "openverse": "ov", "pexels": "px", "pixabay": "pb", "inaturalist": "in",
        "arasaac": "as", "source": "src"}


def search(queries: dict[str, str], outdir: Path, per_slug: int = 10, names: list[str] | None = None,
           fetch=_fetch) -> list[Path]:
    """{slug: English query} → outdir/cands.json and contact sheets (one row per slug, candidates numbered 0–9,
    each tagged with its site). `names` swaps the configured chain for these providers."""
    from PIL import Image, ImageDraw

    outdir.mkdir(parents=True, exist_ok=True)
    each = -(-per_slug // max(1, len(_searchers(names)))) + 1   # enough from each site to fill a row if one fails
    with ThreadPoolExecutor(6) as ex:
        found = dict(zip(queries, ex.map(lambda q: candidates(q, each, names)[:per_slug], queries.values()),
                         strict=True))
    (outdir / "cands.json").write_text(json.dumps(found, ensure_ascii=False, indent=1))
    cell, slugs, sheets = 170, list(queries), []
    for part in range(0, len(slugs), 6):
        rows = slugs[part:part + 6]
        sheet = Image.new("RGB", (per_slug * cell + 90, len(rows) * cell), "white")
        d = ImageDraw.Draw(sheet)
        for r, slug in enumerate(rows):
            d.text((4, r * cell + cell // 2), slug[:12], fill="black")
            with ThreadPoolExecutor(7) as ex:
                ims = list(ex.map(fetch, found[slug]))
            for i, im in enumerate(ims):
                if im is None:
                    continue
                im.thumbnail((cell - 6, cell - 18))
                x, y = 90 + i * cell, r * cell
                sheet.paste(im.convert("RGB"), (x + 3, y + 15))
                d.text((x + 3, y + 2), str(i), fill="red")
                d.text((x + 24, y + 2), TAGS.get(found[slug][i].get("provider"), ""), fill="gray")
        p = outdir / f"sheet{part // 6}.jpg"
        sheet.save(p)
        sheets.append(p)
    return sheets


# 3. apply -------------------------------------------------------------------------------------------------------

def _credit(c: dict) -> str:
    if c.get("file"):                                  # your own picture keeps the credit it came with
        return c.get("credit", "")
    p = providers.get("images", c.get("provider", ""))
    site = getattr(p, "label", "") or "Openverse"     # older cands.json files: anything not Commons was Openverse
    return f'<a href="{c.get("page", "")}">{site}</a>, {c.get("author", "")}, {c.get("license", "")}'


def _download(c: dict, path: Path):
    p = providers.get("images", c.get("provider", ""))
    if p is not None and hasattr(p, "fresh"):
        c = p.fresh(c)                                 # some sites' links expire (Pixabay: 24 h)
    r = httpx.get(c["thumb"], headers=UA, follow_redirects=True, timeout=60)
    r.raise_for_status()
    _to_jpeg(r.content, path, 800, 85)                  # pictograms are transparent PNGs: flattened onto white


def _record(c: dict, entry: dict, name: str) -> dict:
    """The card's picture, with where it came from and the meaning it was chosen for (so it can be reused)."""
    im = {"file": name, "credit": _credit(c), "provider": c.get("provider", ""),
          "meaning": {"gloss": entry.get("gloss", ""), "pos": entry.get("pos", "")}}
    for k, out in (("page", "page"), ("license", "license"), ("item", "item"), ("source_id", "reused_from")):
        if c.get(k):
            im[out] = c[k]
    return im


def _place(c: dict, eid: str, out: Path, name: str, download) -> str:
    """The file for this candidate: your own picture is shared as it is (Anki stores it once); a site's is fetched."""
    if c.get("file"):
        if not (out / c["file"]).exists():
            raise FileNotFoundError(c["file"])
        return c["file"]
    download(c, out / name)
    return name


def apply(decisions: dict[str, dict], store=None, out: Path | None = None, download=_download) -> dict:
    """Download and credit chosen photos; return {"photo": n, "skip": n, "failed": [ids], "prompts": {id: prompt}}.
    A photo that can't be fetched is reported in "failed" (give it a prompt and re-apply)."""
    from panko.store import Store

    st = store or Store()
    out = out or _media()
    cp = out / "credits.json"
    credits = json.loads(cp.read_text()) if cp.exists() else {}
    res = {"photo": 0, "skip": 0, "failed": [], "prompts": {}}
    draw = drawings_allowed()
    for eid, d in decisions.items():
        if "prompt" in d:
            if draw:
                res["prompts"][eid] = d["prompt"]
            else:
                res["skip"] += 1          # drawn pictures are switched off
            continue
        if "photo" not in d:
            res["skip"] += 1
            continue
        e = st.get(eid)
        if not e or e.get("image"):
            continue
        try:
            c = json.loads((inside(d["photo"]["dir"]) / "cands.json").read_text())[eid][d["photo"]["index"]]
            name = _place(c, eid, out, f"{PHOTO_PREFIX}{eid}.jpg", download)
        except Exception as ex:  # noqa: BLE001
            print("photo failed", eid, ex, file=sys.stderr)
            res["failed"].append(eid)
            continue
        if not c.get("file"):
            credits[name] = {k: c.get(k, "") for k in ("provider", "title", "author", "license", "page")}
        e["image"] = _record(c, e, name)
        st.put(e)
        res["photo"] += 1
    cp.write_text(json.dumps(credits, indent=1, ensure_ascii=False))
    return res


def use(eid: str, c: dict, store=None, out: Path | None = None, download=None) -> dict:
    """Put this candidate on the card now (your own choice), replacing any picture it has. The file gets a new name
    when it replaces one, because Anki keeps a file it already has under the same name."""
    import hashlib

    from panko.store import Store
    st = store or Store()
    out = out or _media()
    e = st.get(eid)
    if not e:
        raise KeyError(eid)
    name = f"{PHOTO_PREFIX}{eid}.jpg"
    if e.get("image") or (out / name).exists():
        name = f"{PHOTO_PREFIX}{eid}-{hashlib.sha1(c['thumb'].encode()).hexdigest()[:8]}.jpg"
    name = _place(c, eid, out, name, download or _download)
    if not c.get("file"):
        cp = out / "credits.json"
        credits = json.loads(cp.read_text()) if cp.exists() else {}
        credits[name] = {k: c.get(k, "") for k in ("provider", "title", "author", "license", "page")}
        cp.write_text(json.dumps(credits, indent=1, ensure_ascii=False))
    e["image"] = _record(c, e, name)
    if e.get("picture_pref") == "none":       # you chose one after all
        e.pop("picture_pref")
    st.put(e)
    return e["image"]


def query_for(entry: dict) -> str:
    """A first search for a card: its gloss without notes in brackets, up to the first ; or ,."""
    import re
    g = re.sub(r"\([^)]*\)", "", entry.get("gloss") or "").strip()
    g = re.split(r"[;,/]", g)[0].strip()
    return re.sub(r"^to ", "", g) or entry.get("tl", "")


# drawings -------------------------------------------------------------------------------------------------------

def _model() -> str:
    from panko.config import settings
    return settings()["images"]["generate"].get("model", "")


def _save_drawing(st, out: Path, eid: str, png: Path, prompt: str, model: str) -> str:
    """PNG → small JPEG in the media folder, set as the entry's picture."""
    name = f"{GEN_PREFIX}{eid}.jpg"
    _to_jpeg(png, out / name, 640, 80)
    png.unlink()
    e = st.get(eid)
    e["image"] = {"file": name, "credit": f"Illustration generated ({model})", "prompt": prompt, "provider": "generate",
                  "meaning": {"gloss": e.get("gloss", ""), "pos": e.get("pos", "")}}
    st.put(e)
    return name


def _todo(st, prompts: dict[str, str], force: bool) -> dict[str, str]:
    return {i: p for i, p in prompts.items() if p and st.get(i) and (force or not st.get(i).get("image"))}


def draw(prompts: dict[str, str], force: bool = False, workers: int = 6, store=None, out: Path | None = None,
         gen=None) -> dict[str, str]:
    """Draw each {entry id: scene} now and set it as the entry's picture. Entries that already have a picture are
    skipped unless `force`. Stops early when the account is out of credits. Returns {id: file | error}."""
    from panko.providers.imagegen import Generate, OutOfCredits
    from panko.store import Store

    st = store or Store()
    out = out or _media()
    model, gen, stop = _model(), gen or Generate({}), []

    def one(item):
        eid, prompt = item
        if stop:
            return eid, None, "error: skipped (out of credits)"
        png = out / f"{GEN_PREFIX}{eid}.png"
        try:
            gen.generate(prompt, png)
            return eid, png, prompt
        except OutOfCredits as e:
            stop.append(1)
            return eid, None, f"error: {e}"
        except Exception as e:  # noqa: BLE001
            return eid, None, f"error: {e}"

    res = {}
    with ThreadPoolExecutor(workers) as ex:
        for eid, png, info in ex.map(one, _todo(st, prompts, force).items()):
            res[eid] = _save_drawing(st, out, eid, png, info, model) if png else info
            print(eid, res[eid], flush=True)
    return res


def draw_batch(prompts: dict[str, str], force: bool = False, store=None, gen=None) -> str | None:
    """Submit the drawings as one OpenAI batch (half price, done within 24 h). `collect` saves them later."""
    from panko.providers.imagegen import Generate
    from panko.store import Store

    st = store or Store()
    todo = _todo(st, prompts, force)
    if not todo:
        return None
    bid = (gen or Generate({})).batch_submit(todo)
    f = _batches_file()
    rec = json.loads(f.read_text()) if f.exists() else {}
    rec[bid] = {"prompts": todo, "model": _model(), "submitted": time.strftime("%Y-%m-%d %H:%M"), "done": False}
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return bid


def collect(store=None, out: Path | None = None, gen=None, batches: Path | None = None) -> dict[str, dict]:
    """Save the drawings of every finished batch; report the status of the rest. Returns {batch id: summary}."""
    from panko.providers.imagegen import Generate
    from panko.store import Store

    st, out, gen = store or Store(), out or _media(), gen or Generate({})
    f = batches or _batches_file()
    rec = json.loads(f.read_text()) if f.exists() else {}
    report = {}
    for bid, r in rec.items():
        if r.get("done"):
            continue
        b = gen.batch_status(bid)
        report[bid] = {"status": b.get("status"), "counts": b.get("request_counts")}
        if b.get("status") not in ("completed", "expired", "cancelled", "failed"):
            continue
        saved, errors = 0, {}
        for eid, got in gen.batch_results(b).items():
            if isinstance(got, bytes):
                png = out / f"{GEN_PREFIX}{eid}.png"
                png.write_bytes(got)
                _save_drawing(st, out, eid, png, r["prompts"].get(eid, ""), r.get("model", ""))
                saved += 1
            else:
                errors[eid] = got
        r.update(done=True, saved=saved, errors=errors)
        report[bid].update(saved=saved, errors=len(errors))
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return report
