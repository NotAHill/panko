"""Deterministic checks of entries (`panko verify`, and at ingest): facts come from tools, not from the model.

Standard Arabic (any variety with a database in [morph], Fusha here):
- the headword, its plural, present, imperative and masdar must each be one of the analyser's readings: same
  letters (hamza seats included), and every haraka written must be in that reading (harakat left out are fine);
- the root written on the card must be the root of one of those readings, and the part of speech must fit;
- every word of a written example sentence must have such a reading too (Quran quotes are verbatim, never checked).
Spelling, harakat and root problems are hard: a candidate with one is tagged `panko::doubtful` (kept out of Anki
until cleared). Part of speech, unknown words and example problems are listed for you, without a tag.

Dialects (no open database, and an MSA analyser would "correct" good dialect): grounded when a reference in
[evidence] lists the word; the ones none lists are listed for your teacher, never tagged.
"""
from __future__ import annotations

import re

from panko import providers

MARKS = set("ًٌٍَُِّْٰ")
FATHA, SUKUN, SHADDA, DAGGER, TANWEEN_FATH = "َ", "ْ", "ّ", "ٰ", "ً"
CASE = {"ً": "َ", "ٌ": "ُ", "ٍ": "ِ"}
HARD = {"spelling", "harakat", "root"}
TOKEN = re.compile(r"[ء-يٱً-ْٰ]+")
HAMZA = str.maketrans("أإآؤئٱ", "ءءءءءا")
FIELDS = ("plural", "present", "imperative", "masdar")
TAG = "panko::doubtful"


def morph_for(variety: str):
    """The first ready morphology provider with a database for this variety, or None."""
    return next((p for p in providers.chain("morph") if variety in p.dbs()), None)


# harakat ------------------------------------------------------------------------------------------------------------

def letters(text: str) -> list[tuple[str, frozenset]]:
    """(letter, its marks) for each letter, with spelling conventions evened out so they don't count as differences
    (CAMeL writes the second form of each): sukun is ignored; a dagger alif counts as a fatha (هَٰذَا, هٰذا); a fatha
    before alif is dropped; a tanween on alif or alif maqsura belongs to the letter before it (كتابًا, كتاباً); the
    shadda of a sun letter after the article is dropped (الرَّحْمٰن, الرَحْمٰن)."""
    groups: list[list] = []
    for ch in text.replace("ٱ", "ا").replace("ـ", ""):
        if ch in MARKS:
            if groups and ch != SUKUN:
                groups[-1][1].add(FATHA if ch == DAGGER else ch)
        elif "ء" <= ch <= "ي":
            groups.append([ch, set()])
    for i, g in enumerate(groups):
        if g[0] in "اى" and TANWEEN_FATH in g[1] and i:
            g[1].discard(TANWEEN_FATH)
            groups[i - 1][1].add(TANWEEN_FATH)
        if i + 1 < len(groups) and groups[i + 1][0] == "ا":
            g[1].discard(FATHA)
        if i >= 2 and groups[i - 1][0] == "ل" and not groups[i - 1][1] and groups[i - 2][0] == "ا" and \
                (i == 2 or groups[i - 3][0] in "وفبك"):
            g[1].discard(SHADDA)
    return [(c, frozenset(m)) for c, m in groups]


def _ending(ls: list) -> int:
    """Where the case or mood ending sits: the last letter, or the one before a final alif or alif maqsura."""
    return len(ls) - 2 if len(ls) > 1 and ls[-1][0] in "اى" else len(ls) - 1


def consistent(mine: str, reading: str) -> bool:
    """Every haraka written is in the reading. The ending is looser, since a headword's case is arbitrary and CAMeL
    often leaves it off: anything goes when the reading has none, and tanween counts as its short vowel."""
    a, b = letters(mine), letters(reading)
    if len(a) != len(b) or any(x[0] != y[0] for x, y in zip(a, b, strict=True)):
        return False
    end = _ending(a)
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        mx, my = set(x[1]), set(y[1])
        if i == end:
            mx, my = {CASE.get(m, m) for m in mx}, {CASE.get(m, m) for m in my}
            if not my - {SHADDA}:
                mx &= {SHADDA}
        if not mx <= my:
            return False
    return True


def same_letters(mine: str, reading: str) -> bool:
    return [c for c, _ in letters(mine)] == [c for c, _ in letters(reading)]


def _root(r: str) -> list[str]:
    return [c for c in r.translate(HAMZA) if c == "#" or "ء" <= c <= "ي"]


def same_root(mine: str, theirs: str) -> bool:
    a, b = _root(mine), _root(theirs)
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
    spelled = [r for r in readings if same_letters(text, r["diac"])]
    if not spelled:
        return [{"field": field, "text": text, "problem": "spelling", "suggest": readings[0]["diac"],
                 "detail": "written with other letters (hamza seat, alif, ta marbuta?) in every reading"}]
    fits = [r for r in spelled if consistent(text, r["diac"])]
    if not fits:
        return [{"field": field, "text": text, "problem": "harakat",
                 "suggest": " / ".join(dict.fromkeys(r["diac"] for r in spelled[:4])),
                 "detail": "no reading has these harakat"}]
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
        for w in re.split(r"[،,/;]| or | أو ", e.get(f) or ""):
            if TOKEN.fullmatch(w.strip()):
                out.append((f, w.strip()))
    return out


def _sentence_words(e: dict) -> list[str]:
    return [t for x in e.get("examples", []) if not x.get("cite") for t in TOKEN.findall(x.get("ar", ""))]


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
            words |= set(TOKEN.findall(e["ar"])) | {w for _, w in _forms(e)} | set(_sentence_words(e))
        an = m.analyse(sorted(words), variety)
        for e in es:
            probs = []
            heads = TOKEN.findall(e["ar"])
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
                          for p in check_word(w, an.get(w, [])) if p["problem"] in ("spelling", "harakat")]
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
