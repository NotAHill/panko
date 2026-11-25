"""Is this word already in Panko, under a slightly different spelling or as another word with the same letters?

Exact matching (`Store.find`) ignores harakat, so it misses near spellings (فالدار / ف الدار, بزّاف / بزاف ديال) and
it lumps together different words written with the same letters (ضحك d7ek "laugh" / ضحّك de77ek "make laugh").
This module adds the two checks Panko needs before a new item becomes a candidate:

- `same_word(item, entry)`: an exact key match is the same word only when the consonants of the transliterations
  agree; otherwise it's a homograph (a doubled verb, another word), kept apart and given a shadda when the
  transliteration doubles the middle consonant (`add_shadda`).
- `Index.near(item)`: fuzzy near-duplicates by Arabic, transliteration and gloss, for a person (or Claude) to decide.
"""
from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

from panko import lang

STOP = {"to", "the", "a", "an", "of", "for", "you", "i", "is", "it", "be", "in", "on", "and", "or", "please", "with",
        "me", "my", "your", "man", "woman", "do", "something", "someone", "one"}


def skel(tl: str) -> str:
    """Consonant skeleton of a transliteration, digraphs folded to one letter: de77ek -> d77k, chrab -> šrb."""
    t = (tl or "").lower().replace("sh", "š").replace("ch", "š").replace("kh", "x").replace("gh", "ġ")
    t = t.replace("q", "9").replace("ou", "u").replace("-", "").replace(" ", "")
    return re.sub(r"[aeiouəāīū'’?.,!()]", "", t)


def nar(ar: str) -> str:
    """The item's text folded for fuzzy matching (`panko.lang.fuzzy`: no marks or articles; for Arabic also ة=ه,
    ديال=د, one-letter prepositions glued on)."""
    return lang.fuzzy(ar)


def ntl(tl: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (tl or "").lower().replace("sh", "ch").replace("q", "9").replace("ou", "u"))


def gloss_words(g: str) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)*", (g or "").lower()) if w not in STOP and len(w) > 2}


FUNCTION_POS = {"adverb", "pronoun", "conjunction", "particle", "preposition", "interjection"}


def pos_compatible(a: str | None, b: str | None) -> bool:
    """Could two POS labels be the same word? Sources label function words loosely (شحال adverb or pronoun) and
    adjectives double as adverbs (مزيان), but a verb is never the noun with its letters (دار house / to do), nor is a
    noun a particle (ما water / not)."""
    a, b = (x if x != "phrase" else "" for x in (a, b))   # some entries carry the kind as their POS
    if not a or not b or a == b:
        return True
    if "verb" in (a, b):
        return False
    return {a, b} <= {"noun", "adjective", "number"} or {a, b} <= FUNCTION_POS | {"adjective"}


def _undouble(s: str) -> str:
    return re.sub(r"(.)\1+", r"\1", s)


def same_word(item: dict, entry: dict) -> bool:
    """Same letters and compatible POS: the same word, unless the transliterations differ only by a doubled
    consonant (ضحك d7ek / ضحّك de77ek, رجع rje3 / rejje3). Other differences are spelling noise (sh7al / chhal)."""
    if not pos_compatible(item.get("pos"), entry.get("pos")):
        return False
    a, b = skel(item.get("tl", "")), skel(entry.get("tl", ""))
    return not a or not b or a == b or _undouble(a) != _undouble(b)


def add_shadda(ar: str, tl: str) -> str:
    """A homograph told apart by a doubled consonant gets it marked, where the script marks doubling (Arabic: a shadda
    on the middle letter of a three-letter verb whose transliteration doubles it, de77ek, sekken)."""
    return lang.mark_doubling(ar, skel(tl))


class Index:
    """Near-duplicate search over store entries (any status but retired)."""

    def __init__(self, entries: list[dict]):
        self.entries = [e for e in entries if e.get("status") != "retired"]
        self.idx = defaultdict(list)
        for e in self.entries:
            self.add(e)

    @staticmethod
    def _keys(ar: str) -> list[tuple]:
        """Words, and for scripts that drop vowels their consonants, so علاحقاش finds علحقاش and فاين finds فين."""
        toks = nar(ar).split()
        return [("a", t) for t in toks] + [("c", c) for t in toks if len(c := lang.consonants(t)) >= 2]

    def add(self, e: dict):
        for k in self._keys(e["ar"]):
            self.idx[k].append(e)
        for w in gloss_words(e.get("gloss")):
            self.idx[("g", w)].append(e)

    def near(self, item: dict, limit: int = 3, skip: set[str] = frozenset()) -> list[dict]:
        a1, g1 = nar(item["ar"]), gloss_words(item.get("gloss"))
        keys = self._keys(item["ar"]) + [("g", w) for w in g1]
        cands = {e["id"]: e for k in keys for e in self.idx.get(k, []) if e["id"] not in skip}
        out = []
        for e in cands.values():
            a2, g2 = nar(e["ar"]), gloss_words(e.get("gloss"))
            ra = SequenceMatcher(None, a1, a2).ratio()
            rt = SequenceMatcher(None, ntl(item.get("tl")), ntl(e.get("tl"))).ratio() \
                if item.get("tl") and e.get("tl") else 0
            rg = len(g1 & g2) / max(1, min(len(g1), len(g2))) if g1 and g2 else 0
            same_kind = item.get("kind", "word") == e["kind"]
            if a1 == a2 or (ra >= 0.8 and rg >= 0.5) or ra >= 0.9 or (rg >= 0.99 and ra >= 0.6 and same_kind) \
                    or (rt >= 0.9 and rg >= 0.5):
                out.append({"id": e["id"], "status": e["status"], "ar": e["ar"], "tl": e.get("tl", ""),
                            "gloss": e.get("gloss", ""), "pos": e.get("pos", ""),
                            "score": round(max(ra, rt) * 0.7 + rg * 0.3, 2)})
        return sorted(out, key=lambda m: -m["score"])[:limit]

