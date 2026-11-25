"""Deterministic checks of entries (`panko verify`, and at ingest): facts come from tools, not from the model.

Any variety with a morphology database in [morph] (Fusha with CAMeL Tools, here):
- the headword, its plural, present, imperative and masdar must each be one of the analyser's readings: the same
  letters, and every mark written must be in that reading (for Arabic: harakat left out are fine, see
  `panko.lang.arabic.consistent`);
- the root written on the card must be the root of one of those readings, and the part of speech must fit;
- every word of a written example sentence must have such a reading too (scripture quotes are verbatim, never
  checked).
Spelling, marks (wrong vowel marks) and root problems are hard: a candidate with one is tagged `panko::doubtful` (kept out of Anki until
cleared). Part of speech, unknown words and example problems are listed for you, without a tag.

Varieties without a database (most dialects; an analyser for the standard language would "correct" good dialect):
grounded when a reference in [evidence] lists the word; the ones none lists are listed for your teacher, never
tagged.
"""
from __future__ import annotations

from panko import lang, providers

HARD = {"spelling", "marks", "root"}
FIELDS = ("plural", "present", "imperative", "masdar")
TAG = "panko::doubtful"


def morph_for(variety: str):
    """The first ready morphology provider with a database for this variety, or None."""
    return next((p for p in providers.chain("morph") if variety in p.dbs()), None)


consistent, same_letters = lang.consistent, lang.same_letters


def same_root(mine: str, theirs: str) -> bool:
    a, b = lang.root_letters(mine), lang.root_letters(theirs)
    return len(a) == len(b) and all(x == y or "#" in (x, y) for x, y in zip(a, b, strict=True))


POS_FAMILY = {"noun": "noun", "adj": "noun", "verb": "verb", "adv": "adverb", "pron": "pronoun", "prep": "particle",
              "conj": "particle", "part": "particle", "interj": "particle", "digit": "noun", "abbrev": "noun"}
ENTRY_FAMILY = {"noun": "noun", "adjective": "noun", "number": "noun", "verb": "verb", "adverb": "adverb",
                "pronoun": "pronoun", "preposition": "particle", "conjunction": "particle", "particle": "particle",
                "interjection": "particle"}


def _family(camel_pos: str) -> str:
    return POS_FAMILY.get(camel_pos.split("_")[0], camel_pos)


def check_word(text: str, readings: list[dict], root: str = "", pos: str = "", field: str = "ar") -> list[dict]:
    """Problems with one word against its readings: [] when fine."""
    if not readings:
        return [{"field": field, "text": text, "problem": "unknown", "detail": "the analyser has no reading of it"}]
    if field == "imperative":       # CAMeL knows few imperatives (ساعِدْ, not سافِرْ or مَثِّلْ): judge only by those
        readings = [r for r in readings if r.get("asp") == "c"]
        if not readings:
            return [{"field": field, "text": text, "problem": "unknown",
                     "detail": "the analyser has no imperative of this verb"}]
    spelled = [r for r in readings if lang.same_letters(text, r["diac"])]
    if not spelled:
        return [{"field": field, "text": text, "problem": "spelling", "suggest": readings[0]["diac"],
                 "detail": "written with other letters in every reading"}]
    fits = [r for r in spelled if lang.consistent(text, r["diac"])]
    if not fits:
        return [{"field": field, "text": text, "problem": "marks",
                 "suggest": " / ".join(dict.fromkeys(r["diac"] for r in spelled[:4])),
                 "detail": "no reading has these marks"}]
    out = []
    if root and any(r.get("root") for r in fits) and not any(same_root(root, r.get("root", "")) for r in fits):
        out.append({"field": "root", "text": root, "problem": "root",
                    "suggest": " / ".join(dict.fromkeys(r["root"] for r in fits if r.get("root"))),
                    "detail": f"not the root of {text} in any reading"})
    want = ENTRY_FAMILY.get((pos or "").lower())
    if want and not any(_family(r.get("pos", "")) == want for r in fits):
        out.append({"field": "pos", "text": pos, "problem": "pos",
                    "suggest": " / ".join(dict.fromkeys(r.get("pos", "") for r in fits)),
                    "detail": f"no reading of {text} is a {pos}"})
    return out


def _forms(e: dict) -> list[tuple[str, str]]:
    """(field, word) for the headword's other forms: plurals may list several."""
    out = []
    for f in FIELDS:
        for w in lang.split_list(e.get(f) or ""):
            if len(lang.tokens(w)) == 1 and lang.tokens(w)[0] == w.strip():
                out.append((f, w.strip()))
    return out


def _sentence_words(e: dict) -> list[str]:
    return [t for x in e.get("examples", []) if not x.get("cite") for t in lang.tokens(x.get("ar", ""))]


def check_entries(entries: list[dict], morph=None) -> dict[str, list[dict]]:
    """{entry id: problems} for the entries a morphology database covers (others are left out)."""
    by_var: dict[str, list[dict]] = {}
    for e in entries:
        by_var.setdefault(e["variety"], []).append(e)
    out = {}
    for variety, es in by_var.items():
        m = morph or morph_for(variety)
        if not m or variety not in m.dbs():
            continue
        words = set()
        for e in es:
            words |= set(lang.tokens(e["ar"])) | {w for _, w in _forms(e)} | set(_sentence_words(e))
        an = m.analyse(sorted(words), variety)
        for e in es:
            probs = []
            heads = lang.tokens(e["ar"])
            if e["kind"] == "word" and len(heads) == 1:
                probs += check_word(heads[0], an.get(heads[0], []), e.get("root", ""), e.get("pos", ""))
            else:
                for w in heads:
                    probs += [p for p in check_word(w, an.get(w, [])) if p["problem"] != "unknown"]
            for f, w in _forms(e):
                probs += [p for p in check_word(w, an.get(w, []), e.get("root", ""), field=f)
                          if p["problem"] not in ("pos",)]
            seen = set()
            for w in _sentence_words(e):
                if w in seen:
                    continue
                seen.add(w)
                probs += [{**p, "field": "example", "problem": f"example {p['problem']}"}
                          for p in check_word(w, an.get(w, [])) if p["problem"] in ("spelling", "marks")]
            out[e["id"]] = probs
    return out


def hard(problems: list[dict]) -> list[dict]:
    return [p for p in problems if p["problem"] in HARD]


def flag(items: list[dict], morph=None) -> int:
    """At ingest: new items with a hard problem get `panko::doubtful` and the problems in `check.morph`. Returns how
    many were flagged."""
    keyed = [{**it, "id": f"_{i}"} for i, it in enumerate(items)]
    res = check_entries(keyed, morph)
    n = 0
    for i, it in enumerate(items):
        probs = res.get(f"_{i}", [])
        if probs:
            it["check"] = {**it.get("check", {}), "morph": probs}
        if hard(probs):
            it["tags"] = [*it.get("tags", []), *([TAG] if TAG not in it.get("tags", []) else [])]
            n += 1
    return n


def ungrounded(entries: list[dict]) -> list[dict]:
    """Dialect entries that no reference in [evidence] lists (the ones to ask your teacher about)."""
    from panko import evidence
    es = [e for e in entries if not morph_for(e["variety"]) and e["kind"] == "word"]
    if not es:
        return []
    return [{"id": e["id"], "ar": e["ar"], "tl": e.get("tl", ""), "gloss": e.get("gloss", "")} for e in es
            if not any(evidence._hits(v, e.get("tl_alt", "")) for v in evidence.variants(e["ar"]))]


def run(store, statuses=("candidate",), ids: list[str] | None = None, apply: bool = False, tag_active: bool = False,
        morph=None, grounding: bool = True) -> dict:
    """Check entries. With `apply`, candidates with a hard problem get `panko::doubtful` and the problems in
    `check.morph` (active ones too with `tag_active`: they stay in Anki, tagged). Returns a report."""
    es = [store.get(i) for i in ids] if ids else [e for st in statuses for e in store.entries(st)]
    es = [e for e in es if e]
    res = check_entries(es, morph)
    by_id = {e["id"]: e for e in es}
    rep = {"checked": len(res), "fine": 0, "doubtful": [], "listed": [], "tagged": 0, "ungrounded": []}
    for eid, probs in res.items():
        e = by_id[eid]
        row = {"id": eid, "ar": e["ar"], "status": e["status"], "problems": probs}
        if hard(probs):
            rep["doubtful"].append(row)
        elif probs:
            rep["listed"].append(row)
        else:
            rep["fine"] += 1
        if apply and (probs or e.get("check", {}).get("morph")):
            e["check"] = {**e.get("check", {}), "morph": probs}
            if hard(probs) and TAG not in e.get("tags", []) and (e["status"] == "candidate" or tag_active):
                e["tags"] = [*e.get("tags", []), TAG]
                rep["tagged"] += 1
            store.put(e)
    if grounding:
        rep["ungrounded"] = ungrounded([e for e in es if e["id"] not in res])
    return rep
