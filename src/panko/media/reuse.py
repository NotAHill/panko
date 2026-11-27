"""Pictures you already have, for cards that need one: a picture belongs to a meaning, so a card whose gloss means the
same as a card with a picture (in another variety, or another language in this folder) can use that picture.

- `search(query)`: your pictures whose meaning matches a search, as candidates like any site's (the `yours`
  provider, first in every photo search): you or the model still confirm each one, since "glass" can be a cup or
  the material.
- `matches(store, cards)`: for the pictures page's reuse list, each waiting card with the pictures from *other*
  varieties that match it (two words of one variety with one meaning are synonyms: the same picture would make their
  cards look alike); `sure` when there is one picture, for the same gloss and part of speech.
- `use(store, eid, source)`: put a source card's picture on a card. The file itself is shared (Anki stores it once).

A picture records what it was chosen for (`meaning`: gloss and part of speech) and where it came from, so later
matching doesn't depend on the card's gloss staying the same.
"""
from __future__ import annotations

import re
from pathlib import Path

PROVIDER = "yours"
_PAREN = re.compile(r"\([^)]*\)")
_LEAD = re.compile(r"^(to|a|an|the)\s+")


def key(gloss: str) -> str:
    """The main sense of a gloss, for matching: "a glass (for tea); cup" → "glass". A slash stays ("yes/no
    question particle" isn't "yes")."""
    g = _PAREN.sub("", (gloss or "").lower())
    g = re.split(r"[;,]", g)[0]
    g = re.sub(r"[^\w\s'-]", " ", g)
    return _LEAD.sub("", " ".join(g.split()))


def _full(gloss: str) -> str:
    return " ".join(re.sub(r"[^\w\s'()-]", " ", (gloss or "").lower()).split())


def meaning_of(e: dict) -> dict:
    """What a card's picture shows: the meaning it was chosen for, else the card's own gloss."""
    im = e.get("image") if isinstance(e.get("image"), dict) else {}
    m = im.get("meaning") or {}
    return {"gloss": m.get("gloss") or e.get("gloss", ""), "pos": (m.get("pos") or e.get("pos") or "").lower()}


def _media() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "media"


def pictured(store) -> list[dict]:
    """Every card with a picture whose file is here, as a source: {id, variety, ar, gloss, pos, key, file, credit}."""
    media, out = _media(), []
    for e in store.entries(None):
        im = e.get("image") if isinstance(e.get("image"), dict) else None
        if not im or not im.get("file") or not (media / im["file"]).exists():
            continue
        m = meaning_of(e)
        out.append({"id": e["id"], "variety": e["variety"], "ar": e["ar"], "gloss": m["gloss"], "pos": m["pos"],
                    "key": key(m["gloss"]), "full": _full(m["gloss"]), "file": im["file"],
                    "credit": im.get("credit", ""), "drawn": bool(im.get("prompt"))})
    return out


def candidate(src: dict) -> dict:
    """A source as a photo candidate: shown like any site's, but already here (`file`), so nothing is downloaded."""
    return {"thumb": f"/media/{src['file']}", "file": src["file"], "provider": PROVIDER, "source_id": src["id"],
            "title": f"{src['ar']} · {src['gloss']}", "author": src["variety"].title(),
            "license": "drawn" if src["drawn"] else "", "credit": src["credit"], "page": ""}


def search(query: str, limit: int = 6, store=None) -> list[dict]:
    """Your pictures for this search: the same main sense first, then glosses that contain every word searched."""
    from panko.store import DB_PATH, Store
    if store is None:
        if not Path(DB_PATH).exists():
            return []
        store = Store()
    q = key(query)
    if not q:
        return []
    words = set(q.split())
    same, near, seen = [], [], set()
    for s in pictured(store):
        if s["file"] in seen:
            continue
        if s["key"] == q:
            same.append(s)
            seen.add(s["file"])
        elif words <= set(s["key"].split()):
            near.append(s)
            seen.add(s["file"])
    return [candidate(s) for s in (same + near)[:limit]]


def matches(store, cards: list[dict]) -> list[dict]:
    """Each card waiting for a picture that has a match: {id, ar, gloss, variety, sources: [...], sure}."""
    by_key: dict[str, list[dict]] = {}
    shown_in: dict[str, set] = {}           # file → the varieties whose cards already show it
    for s in pictured(store):
        by_key.setdefault(s["key"], []).append(s)
        shown_in.setdefault(s["file"], set()).add(s["variety"])
    out = []
    for c in cards:
        e = store.get(c["id"]) or {}
        k = key(c.get("gloss", ""))
        files, sources = set(), []
        for s in by_key.get(k, []):
            if s["id"] != c["id"] and e.get("variety") not in shown_in[s["file"]] and s["file"] not in files:
                files.add(s["file"])
                sources.append(s)
        if not sources:
            continue
        pos = (c.get("pos") or "").lower()
        s0 = sources[0]
        sure = (len(sources) == 1 and (not pos or not s0["pos"] or pos == s0["pos"])
                and _full(c.get("gloss", "")) == s0["full"])
        out.append({"id": c["id"], "ar": c.get("ar", ""), "gloss": c.get("gloss", ""), "pos": pos,
                    "variety": e.get("variety", ""), "sure": sure,
                    "sources": [{k2: s[k2] for k2 in ("id", "variety", "ar", "gloss", "pos", "file", "drawn")}
                                for s in sources[:6]]})
    return out


def use(store, eid: str, source_id: str) -> dict:
    """Put the source card's picture on this card: the same file and credit, and the meaning it shows."""
    e, src = store.get(eid), store.get(source_id)
    if not e:
        raise KeyError(f"no card {eid}")
    im = (src or {}).get("image") if isinstance((src or {}).get("image"), dict) else None
    if not im or not im.get("file") or not (_media() / im["file"]).exists():
        raise ValueError(f"card {source_id} has no picture to share")
    e["image"] = {**{k: v for k, v in im.items() if k != "reused_from"}, "meaning": meaning_of(src),
                  "reused_from": source_id}
    if e.get("picture_pref") == "none":
        e.pop("picture_pref")
    store.put(e)
    return e["image"]
