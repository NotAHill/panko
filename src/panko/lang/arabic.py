"""Rules for text in Arabic script (Darija, Fusha, any Arabic): matching keys, near-duplicate folding, spelling
variants, and how a written form compares with an analyser's reading. Every function here changes Arabic letters
only, so it is safe to run on any text; `panko.lang` calls it for every language.
"""
from __future__ import annotations

import re

HARAKAT = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")  # vowels, shadda, tatweel
ALEF = re.compile(r"[\u0622\u0623\u0625\u0671]")  # آ أ إ ٱ -> ا
SHADDA = "\u0651"
OR = " \u0623\u0648 "                # أو, "or" between two forms


# ElevenLabs' accent labels for Arabic voices, by a word in the dialect's name (only labels its library uses)
ACCENTS = {"iraqi": "iraqi", "baghdadi": "iraqi", "gulf": "gulf", "khaleeji": "gulf", "levantine": "levantine",
           "shami": "levantine", "egyptian": "egyptian", "masri": "egyptian", "moroccan": "moroccan",
           "darija": "moroccan", "fusha": "modern standard", "msa": "modern standard", "quranic": "modern standard",
           "standard": "modern standard"}


def voice_filter(name: str) -> dict:
    """{language, accent} for ElevenLabs' shared library from a dialect's name ("Iraqi Arabic" → iraqi); Arabic voices
    of any accent when the name doesn't say."""
    for w in re.findall(r"[a-z]+", (name or "").lower()):
        if w in ACCENTS:
            return {"language": "ar", "accent": ACCENTS[w]}
    return {"language": "ar"}


def fold(text: str) -> str:
    """The matching key's Arabic part: no harakat, one alef, ى as ي."""
    t = HARAKAT.sub("", text)
    t = ALEF.sub("ا", t)
    return t.replace("ى", "ي")


def strip_article(t: str) -> str:
    """ال off ('الكنابي' matches 'كنابي'); `t` is already folded."""
    return t[2:] if t.startswith("ال") and len(t) > 3 else t


def fuzzy(t: str) -> str:
    """Folded further for near-duplicates (`t` is already a matching key): ة=ه, hamza seats gone, ديال=د, the article
    off, one-letter prepositions glued on (فالدار = ف+دار)."""
    t = t.replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    t = re.sub(r"(^|\s)ديال(\s|$)", r"\1د\2", t)
    toks = [x[2:] if x.startswith("ال") and len(x) > 3 else x for x in t.split()]
    out, i = [], 0
    while i < len(toks):
        if toks[i] in ("ف", "ب", "ل", "د", "و") and i + 1 < len(toks):
            out.append(toks[i] + toks[i + 1])
            i += 2
        else:
            out.append(toks[i])
            i += 1
    return " ".join(re.sub(r"^([فبلدو])ال(?=..)", r"\1", t) for t in out)


def consonants(tok: str) -> str:
    """Without long vowels, so علاحقاش finds علحقاش and فاين finds فين."""
    return re.sub("[اوي]", "", tok)


def variants(ar: str) -> list[str]:
    """Spellings to look up: گ/ڭ for g written as ك or ق, and a final ا/ى/ي."""
    out = [ar]
    for g in "گڭ":
        if g in ar:
            out += [ar.replace(g, "ك"), ar.replace(g, "ق")]
    if ar.endswith("ا"):
        out.append(ar[:-1] + "ى")
    elif ar.endswith(("ى", "ي")):
        out.append(ar[:-1] + "ا")
    return out


def add_shadda(ar: str, skel: str) -> str:
    """Shadda on the middle letter of a three-letter word whose transliteration skeleton doubles it (d77k)."""
    if SHADDA in ar or len(ar) != 3 or len(skel) < 4 or skel[1] != skel[2]:
        return ar
    return ar[:2] + SHADDA + ar[2:]


def bare_noun(t: str) -> str:
    """A key with ال already off, also without the lone ل speech-to-text writes for it (لبرية for البرية)."""
    return t[1:] if t.startswith("ل") and len(t) > 3 else t


# A written form against an analyser's reading (panko.checks) -------------------------------------------------------

MARKS = set("\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670")
FATHA, SUKUN, SHADDA, DAGGER, TANWEEN_FATH = "َ", "ْ", "ّ", "ٰ", "ً"
CASE = {"ً": "َ", "ٌ": "ُ", "ٍ": "ِ"}
HAMZA = str.maketrans("\u0623\u0625\u0622\u0624\u0626\u0671", "\u0621\u0621\u0621\u0621\u0621\u0627")


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


def root_letters(r: str) -> list[str]:
    """A root's radicals, hamza forms as one and `#` (CAMeL's weak radical) kept as a wildcard."""
    return [c for c in r.translate(HAMZA) if c == "#" or "ء" <= c <= "ي"]
