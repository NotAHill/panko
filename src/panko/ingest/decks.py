"""Read exported shared-deck notes (data/sources/decks/*.json) into rough (ar, en) rows.

Each deck has its own note type, so each gets a small parser. Rows are raw material for an
extraction, not entries: spelling, glosses and examples still go through extraction + checks.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

SOUND = re.compile(r"\[sound:[^\]]*\]")
TAG = re.compile(r"<[^>]+>")
IMG_ALT = re.compile(r'<img[^>]*alt="([^"]*)"', re.I)
IMG_SRC = re.compile(r'<img[^>]*src="([^"]*)"', re.I)
ARABIC = re.compile(r"[؀-ۿ]")


def text(s: str) -> str:
    s = SOUND.sub(" ", s or "")
    s = re.sub(r"<br\s*/?>|</div>|<div>", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s))).strip()


def picture_hint(s: str) -> str:
    """English meaning guessed from an image-only back: alt text or file name (city.jpg -> city)."""
    if m := IMG_ALT.search(s or ""):
        return m.group(1)
    if m := IMG_SRC.search(s or ""):
        stem = Path(m.group(1)).stem
        return "" if re.match(r"^(paste|images?)-", stem) else stem.replace("_", " ").replace("-", " ")
    return ""


def split_forms(ar: str) -> list[str]:
    return [p.strip() for p in re.split(r"[/،,]", ar) if p.strip()]


def row(deck, n, ar, en, tl="", hint=""):
    forms = split_forms(ar)
    return {"deck": deck, "nid": n["nid"], "studied": n["studied"], "ar": ar, "head": forms[0] if forms else ar,
            "forms": forms, "tl": tl, "en": en, "hint": hint}


def parse(deck: str, n: dict) -> dict | None:
    f = n["fields"]
    if deck == "darija":
        return row(deck, n, text(f.get("Front", "")), text(f.get("Back", "")), hint=picture_hint(f.get("Back", "")))
    if deck.startswith("darija-casablanca"):
        return row(deck, n, text(f.get("Front", "")), text(f.get("Back", "")), hint=picture_hint(f.get("Back", "")))
    if deck == "dave-s-darija":
        d = f.get("Darija (with audio)", "")
        ar, _, rest = d.partition("<br>")
        tl = text(re.search(r"<sub>(.*?)</sub>", d).group(1)) if "<sub>" in d else ""
        return row(deck, n, text(ar), text(f.get("English", "")), tl=tl)
    if deck == "peace-corps-darija-dictionary":
        ar = text(f.get("Front", ""))
        if m := re.match(r"^\((\S+) \((\S+)$", ar):   # "(غيب (غاب" is "غاب (غيب)" with the brackets flipped
            ar = f"{m.group(2)} / {m.group(1)}"
        return row(deck, n, ar, text(f.get("Back", "")))
    if deck == "most-used-moroccan":   # Arabizi only; Arabic is written at extraction
        vals = [text(v) for v in f.values() if v]
        front = text(f.get("Front") or f.get("Text") or f.get("- The full sentence (no words blanked out)", ""))
        front = re.sub(r"\{\{c\d+::(.*?)(::.*?)?\}\}", r"\1", front)
        en = text(f.get("Back") or f.get("Extra") or f.get("Front (Definitions, base word, etc.)", ""))
        return {"deck": deck, "nid": n["nid"], "studied": n["studied"], "ar": "", "head": "", "forms": [], "tl": front,
                "en": en, "hint": picture_hint(f.get("Back", "")), "all": vals}
    return generic(deck, n)


def generic(deck: str, n: dict) -> dict | None:
    """Any other note type: the first field with Arabic script is the word, the first field without it the meaning;
    no Arabic at all: the front is taken as romanisation (the model writes the Arabic). `fields` keeps the whole note."""
    vals = [(k, text(re.sub(r"\{\{c\d+::(.*?)(::.*?)?\}\}", r"\1", v))) for k, v in n["fields"].items() if text(v)]
    if not vals:
        return None
    ar = next((v for _, v in vals if ARABIC.search(v)), "")
    rest = [v for _, v in vals if not ARABIC.search(v)]     # the meaning: a field in the gloss language
    raw_back = next((v for v in n["fields"].values() if text(v) and text(v) != ar), "")
    whole = dict(vals)          # the reader sees the whole note too, since a guess can pick the wrong fields
    if ar:
        return {**row(deck, n, ar, rest[0] if rest else "", hint="" if rest else picture_hint(raw_back)),
                "fields": whole}
    return {"deck": deck, "nid": n["nid"], "studied": n.get("studied", False), "ar": "", "head": "", "forms": [],
            "tl": vals[0][1], "en": vals[1][1] if len(vals) > 1 else "", "hint": picture_hint(raw_back),
            "fields": whole}


def rows(path: Path) -> tuple[str, list[dict]]:
    """(deck title, rows) from an exported deck file {"deck", "notes": [{nid, fields, studied}]}."""
    import json
    d = json.loads(path.read_text())
    deck = path.stem
    return d.get("deck", deck), [r for n in d["notes"] if (r := parse(deck, {"studied": False, **n}))
                                 and (r["ar"] or r["tl"])]
