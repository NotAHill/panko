"""Free, local evidence for words: does the learner already have it, and what do the reference sources say?

`lookup(words)` takes `[{ar, tl, tl_alt, pos, gloss, variety}]` (only `ar` is required) and returns, per word:
- `panko`: the entry the learner already has (same letters, compatible POS and transliteration), or null;
- `same_letters`: entries with the same letters that are another word (other POS, or the consonants of the
  transliteration differ: ضحك d7ek / ضحّك de77ek), so a new item there is a homograph, not a duplicate;
- `near`: near-duplicates by spelling, transliteration and gloss (فالدار / ف الدار), to look at before adding;
- `hits`: lines from the corpora and dictionaries in `[evidence]` (config/panko.toml).

Reference files are read by shape, so another learner points config at their own:
- a folder of CSVs (one column of Arabic, one of English; a file named *sentences* is a sentence corpus);
- a JSON-lines dictionary (`word` plus `senses[].glosses`, as Wiktionary extracts are);
- a plain-text dictionary, searched for the scholarly transliteration (and the Arabic).
"""
from __future__ import annotations

import csv
import json
import re
from functools import cache
from pathlib import Path

from panko.config import ROOT, settings
from panko.dedupe import Index, same_word
from panko.store import Store
from panko.store.normalize import strip_article

POS_ALIASES = {"n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb", "prep": "preposition",
               "pron": "pronoun", "conj": "conjunction", "interj": "interjection", "num": "number",
               "part": "particle", "phrase": ""}
ARABIC = re.compile(r"[؀-ۿ]")
MAX_HITS = 4


def norm_pos(pos: str | None) -> str:
    p = (pos or "").strip().lower().rstrip(".")
    return POS_ALIASES.get(p, p)


def variants(ar: str) -> list[str]:
    """Spellings to try: گ/ڭ for g written as ك or ق, and a final ا/ى/ي."""
    out = [ar]
    for g in "گڭ":
        if g in ar:
            out += [ar.replace(g, "ك"), ar.replace(g, "ق")]
    if ar.endswith("ا"):
        out.append(ar[:-1] + "ى")
    elif ar.endswith(("ى", "ي")):
        out.append(ar[:-1] + "ا")
    return list(dict.fromkeys(out))


def _tokens(s: str) -> set[str]:
    s = re.sub(r"[\u200e\u200f\u202a-\u202e.؟?!:;\"«»]", " ", s or "")
    return {strip_article(t) for t in re.split(r"[\s,،/()]+", s) if t}


def _path(p: str) -> Path:
    return Path(p) if Path(p).is_absolute() else ROOT / p


@cache
def _references() -> list[dict]:
    """Each configured corpus/dictionary loaded once: {name, kind: rows|sentences|jsonl|text, data}."""
    ev = settings().get("evidence", {})
    refs = []
    for c in [*ev.get("corpora", []), *ev.get("dictionaries", [])]:
        p = _path(c.get("path", ""))
        if p.is_dir():
            for f in sorted(p.glob("*.csv")):
                rows = list(csv.DictReader(open(f, encoding="utf-8")))
                if not rows:
                    continue
                cols = list(rows[0])
                ar = next((k for k in cols if any(ARABIC.search(r.get(k) or "") for r in rows[:20])), None)
                en = next((k for k in cols if k.lower() in ("eng", "en", "english", "gloss", "meaning")), None)
                if ar:
                    kind = "sentences" if "sentence" in f.stem else "rows"
                    refs.append({"name": f"{c['name']} ({f.stem})", "kind": kind,
                                 "data": [(r[ar], r.get(en, "") if en else "") for r in rows if r.get(ar)]})
        elif p.suffix == ".jsonl" and p.exists():
            d = {}
            for line in open(p, encoding="utf-8"):
                x = json.loads(line)
                gl = "; ".join(g for s in x.get("senses", []) for g in s.get("glosses", [])[:1])[:160]
                d.setdefault(x.get("word", ""), []).append(f"{x.get('pos', '')}: {gl}" if x.get("pos") else gl)
            refs.append({"name": c["name"], "kind": "jsonl", "data": d})
        elif p.exists():
            refs.append({"name": c["name"], "kind": "text", "data": p.read_text(encoding="utf-8").splitlines()})
    return refs


def _hits(ar: str, tl_alt: str) -> list[str]:
    from panko.store.normalize import bare
    b = strip_article(ar)
    one_word = " " not in b
    out, rows = [], {}
    for ref in _references():
        if ref["kind"] == "rows":
            for a, en in ref["data"]:
                if b == strip_article(a) or (one_word and b in _tokens(a)):
                    rows.setdefault((a, en.strip().lower()), ref["name"])
        elif ref["kind"] == "sentences" and one_word:
            ss = [(a, en) for a, en in ref["data"] if b in _tokens(a)]
            if ss:
                out.append(f"{ref['name']}: {len(ss)} sentences, e.g. {ss[0][0]} '{ss[0][1]}'")
        elif ref["kind"] == "jsonl":
            for w in dict.fromkeys((b, bare(ar), ar)):
                if w in ref["data"]:
                    out.append(f"{ref['name']} {w}: {' | '.join(ref['data'][w][:2])}")
                    break
        elif ref["kind"] == "text":
            k = (tl_alt or "").lower().replace("ʿ", "ɛ").replace("ḥ", "ħ")
            pat = re.compile(rf"(?<![\wɛħ]){re.escape(k)}(?![\wɛħ])") if len(k) >= 3 else None
            out += [f"{ref['name']} l.{i + 1}: {line.strip()[:140]}" for i, line in enumerate(ref["data"])
                    if (pat and pat.search(line.lower())) or (one_word and len(b) >= 3 and b in _tokens(line))][:2]
    rows_out = [f"{name}: {a} '{en}'" for (a, en), name in rows.items()][:MAX_HITS]
    return rows_out + out


def _short(e: dict) -> dict:
    return {k: e.get(k, "") for k in ("id", "status", "ar", "tl", "pos", "gloss")}


def lookup(words: list[dict], store: Store | None = None, refs: bool = True) -> list[dict]:
    store = store or Store()
    default_variety = (settings().get("learner", {}).get("varieties") or ["darija"])[0]
    index = Index(store.entries(None))
    out = []
    for w in words:
        ar, pos, variety = w["ar"].strip(), norm_pos(w.get("pos")), w.get("variety") or default_variety
        item = {**w, "ar": ar, "pos": pos}
        panko, same = None, []
        for v in variants(ar):
            for e in store.find_all(v, variety):
                if e["status"] == "retired" or e["id"] in {x["id"] for x in same} or (panko and e["id"] == panko["id"]):
                    continue
                if panko is None and same_word(item, e):
                    panko = e
                else:
                    same.append(_short(e))
        skip = {panko["id"]} if panko else set()
        skip |= {x["id"] for x in same}
        out.append({"ar": ar, "panko": _short(panko) if panko else None, "same_letters": same,
                    "near": [] if panko else index.near(item, skip=skip),
                    "hits": _hits(ar, w.get("tl_alt", "")) if refs else []})
    return out
