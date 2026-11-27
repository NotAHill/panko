"""What Panko knows about the language being learned, from config: its script, how to match its words, how to show
them. Nothing else in Panko assumes a language.

Config (`[learner]` in config/panko.toml):
- `script`: the script cards are written in, a Unicode script name ("Arabic", "Latin", "Cyrillic", "Devanagari"…),
  or a list (Japanese: ["Han", "Hiragana", "Katakana"]). `[learner.scripts]` names another for one variety.
  Items whose text isn't in it are refused at submit.
- `articles`: articles left off when matching ("el", "la", "l'"…), so "la casa" finds "casa". Arabic's ال is built in.
- `fold_marks`: true to match words without their accents or vowel marks (Arabic harakat always are).
- `font`: a CSS font stack for the cards, when the default for the script isn't right.

Matching keys (`bare`, `strip_article`) are case-folded and NFC-normalised for every language; text in Arabic script
also gets the Arabic rules in `panko.lang.arabic` (they touch Arabic letters only, so mixed text is safe).
"""
from __future__ import annotations

import re
import unicodedata

from panko.lang import arabic

RTL = {"Arabic", "Hebrew", "Syriac", "Thaana", "Nko", "Samaritan", "Mandaic", "Adlam"}
FONTS = {
    "Arabic": ('"Noto Naskh Arabic", "Geeza Pro", "Al Nile", "Traditional Arabic", serif', 2.0),
    "Hebrew": ('"Noto Serif Hebrew", "Arial Hebrew", "David", serif', 1.6),
    "Japanese": ('"Hiragino Mincho ProN", "Noto Serif CJK JP", "Yu Mincho", serif', 1.6),
    "Han": ('"Songti SC", "Noto Serif CJK SC", "SimSun", serif', 1.6),
    "Hangul": ('"Apple SD Gothic Neo", "Noto Sans CJK KR", "Malgun Gothic", sans-serif', 1.6),
    "Devanagari": ('"Kohinoor Devanagari", "Noto Serif Devanagari", "Mangal", serif', 1.8),
    "Thai": ('"Thonburi", "Noto Sans Thai", "Leelawadee UI", sans-serif', 1.8),
}
DEFAULT_FONT = ('"Iowan Old Style", Georgia, "Noto Serif", serif', 1.45)
PUNCT = re.compile(r"[.,،؟?!؛:\"'«»¿¡]")
_NAMES = {"CJK": "Han", "NKO": "Nko"}


def _learner() -> dict:
    from panko import config
    try:
        return config.settings().get("learner", {})
    except FileNotFoundError:
        return {}


def script_of(ch: str) -> str:
    """The Unicode script of a letter ("Latin", "Arabic", "Han"…), "" for anything else (marks, digits, spaces)."""
    if not ch.isalpha():
        return ""
    first = unicodedata.name(ch, "").split(" ")[0]
    return _NAMES.get(first, first.title())


def scripts(text: str) -> set[str]:
    return {s for ch in text or "" if (s := script_of(ch))}


def target(variety: str | None = None) -> list[str]:
    """The configured script(s) for a variety (all varieties when none is given); [] when not configured."""
    L = _learner()
    per = L.get("scripts", {})
    vals = [per[variety]] if variety and variety in per else [L.get("script", [])] + (
        [] if variety else list(per.values()))
    out = []
    for v in vals:
        out += [v] if isinstance(v, str) else list(v)
    return [s.strip().title() for s in dict.fromkeys(out) if s.strip()]


def label(variety: str | None = None) -> str:
    """'Arabic script', 'Han, Hiragana or Katakana script'; 'the target language's script' when not configured."""
    t = target(variety)
    if not t:
        return "the target language's script"
    return (", ".join(t[:-1]) + " or " + t[-1] if len(t) > 1 else t[0]) + " script"


def in_target(text: str, variety: str | None = None) -> bool:
    """Is any of `text` in the variety's script? Any letters count when no script is configured."""
    t = set(target(variety))
    found = scripts(text)
    return bool(found & t) if t else bool(found)


# a PDF's text layer --------------------------------------------------------------------------------------------------
# A page's embedded text can help with spelling, or mislead: OCR over a scan is usually fine for Latin and poor for
# other scripts, and some PDFs store shaped glyphs (Arabic presentation forms, often in reverse order). The page image
# is always what's read; a layer that fails these checks isn't given to the model at all.

LAYER_NOTES = {
    "none": "this page has no text layer",
    "ocr": "the scan's own OCR, unreliable for {script}: the page image is what's read",
    "shaped": "stored as shaped glyphs, so its {script} is scrambled: the page image is what's read",
    "garbled": "garbled (mixed scripts and stray symbols inside words): the page image is what's read",
    "ok": "the PDF's own text, given to the model as a spelling aid; the page image is what's read",
}
_JUNK = set("$<>{}|\\^~@#_=")


def _broken(tok: str) -> bool | None:
    """True for a word OCR or a bad encoding broke: letters of two scripts in one word, a symbol inside it, or digits
    glued to letters of a script that doesn't write numbers in them (Arabizi's 3/7/9 in Latin words are fine)."""
    found = scripts(tok)
    if not found:
        return None
    return len(found) > 1 or any(c in _JUNK for c in tok) or (
        found != {"Latin"} and any(c.isdigit() for c in tok if c.isascii()))


def text_layer(text: str, *, ocr: bool = False, variety: str | None = None) -> str:
    """How far to trust a page's embedded text: "none", "ocr", "shaped", "garbled" or "ok" (see LAYER_NOTES)."""
    text = text or ""
    found = scripts(text)
    if not text.strip() or not found:
        return "none"
    wanted = set(target(variety)) or (found - {"Latin"})
    if ocr and wanted - {"Latin"}:
        return "ocr"
    letters = [c for c in text if c.isalpha()]
    shaped = sum(1 for c in letters if unicodedata.normalize("NFKC", c) != c and script_of(c) != "Latin")
    if letters and shaped / len(letters) > 0.02:
        return "shaped"
    marks = [b for t in text.split() if (b := _broken(t)) is not None]
    if marks and sum(marks) / len(marks) > 0.08:
        return "garbled"
    return "ok"


def layer_note(state: str, variety: str | None = None) -> str:
    t = target(variety)
    return LAYER_NOTES.get(state, "").format(script=t[0] if len(t) == 1 else "the target script")


def romanised() -> bool:
    """Does the learner want a romanisation (`tl`)? Not when `[learner.translit] main` is set to "" (a language
    written in Latin letters already)."""
    return _learner().get("translit", {}).get("main", "x") != ""


def default_variety() -> str:
    return (_learner().get("varieties") or ["main"])[0]


# matching ----------------------------------------------------------------------------------------------------------

def _marks_off(t: str) -> str:
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", t)
                                                if not unicodedata.combining(c)))


def bare(text: str) -> str:
    """The matching key ("is this word already in Panko?"): Arabic folded, case folded, NFC, no punctuation, single
    spaces; accents and vowel marks off too with `fold_marks`. Display text is never changed, only the key."""
    t = unicodedata.normalize("NFC", arabic.fold(text or "")).casefold()
    if _learner().get("fold_marks"):
        t = _marks_off(t)
    t = PUNCT.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


def articles() -> list[str]:
    return [a.casefold() for a in _learner().get("articles", [])]


def strip_article(text: str) -> str:
    """The key without a leading article: configured ones ("la casa" → casa, "l'eau" → eau) and Arabic ال."""
    t = unicodedata.normalize("NFC", arabic.fold(text or "")).casefold().strip()
    for a in sorted(articles(), key=len, reverse=True):
        if a.endswith(("'", "’")) and t.startswith(a) and len(t) > len(a):
            t = t[len(a):]
            break
        if t.startswith(a + " ") and len(t) > len(a) + 1:
            t = t[len(a) + 1:]
            break
    return arabic.strip_article(bare(t))


def fuzzy(text: str) -> str:
    """Folded further for near-duplicates: the key with every word's article off (and Arabic's own folding)."""
    arts = set(articles())
    toks = [w for w in bare(text).replace("…", " ").replace("...", " ").split() if w not in arts]
    return arabic.fuzzy(" ".join(toks))


def consonants(tok: str) -> str:
    """A rougher key for one word, for scripts that often leave vowels out (Arabic); the word itself otherwise."""
    return arabic.consonants(tok) if "Arabic" in scripts(tok) else tok


def split_list(text: str) -> list[str]:
    """Several forms in one field ("libros, libritos", "كتب، كتوب", "x or y") as separate forms."""
    return [w.strip() for w in re.split(r"[,،、/;]| or |" + arabic.OR, text or "") if w.strip()]


def variants(text: str) -> list[str]:
    """Spellings worth looking up in references besides the given one."""
    return list(dict.fromkeys(arabic.variants(text)))


def mark_doubling(text: str, skel: str) -> str:
    """Mark a doubled consonant the script writes with a sign (Arabic shadda); other scripts already show it."""
    return arabic.add_shadda(text, skel) if "Arabic" in scripts(text) else text


def bare_noun(text: str) -> str:
    """A word as speech-to-text may write it: without its article."""
    return arabic.bare_noun(strip_article(text))


# comparing a written form with an analyser's reading (panko.checks) ------------------------------------------------

def same_letters(mine: str, reading: str) -> bool:
    if "Arabic" in scripts(mine):
        return arabic.same_letters(mine, reading)
    return _marks_off(mine).casefold() == _marks_off(reading).casefold()


def consistent(mine: str, reading: str) -> bool:
    """`mine` fits the reading: for Arabic, every haraka written is in it; elsewhere, the same text (case aside)."""
    if "Arabic" in scripts(mine):
        return arabic.consistent(mine, reading)
    return unicodedata.normalize("NFC", mine).casefold() == unicodedata.normalize("NFC", reading).casefold()


def root_letters(r: str) -> list[str]:
    if "Arabic" in scripts(r):
        return arabic.root_letters(r)
    return [c for c in r if c.isalpha() or c == "#"]


def _in_word(ch: str) -> bool:
    return ch.isalpha() or unicodedata.category(ch) in ("Mn", "Mc")


def tokens(text: str, apostrophes: bool = False) -> list[str]:
    """Words of `text` in any script, marks kept with their letters (and apostrophes inside a word, if asked)."""
    out, cur = [], ""
    for ch in text or "":
        if _in_word(ch) or (apostrophes and ch in "'\u2019" and cur):
            cur += ch
        else:
            if cur:
                out.append(cur.rstrip("'\u2019"))
            cur = ""
    if cur:
        out.append(cur.rstrip("'\u2019"))
    return [t for t in out if t]


# showing -----------------------------------------------------------------------------------------------------------

def _font_key(ts: list[str]) -> str:
    if {"Hiragana", "Katakana"} & set(ts):
        return "Japanese"
    return next((t for t in ts if t in FONTS), ts[0] if ts else "")


def is_rtl(variety: str | None = None) -> bool:
    return bool(set(target(variety)) & RTL)


def font(variety: str | None = None) -> tuple[str, float]:
    """(CSS font stack, line height) for the variety's script; `[learner] font` overrides the stack."""
    stack, lh = FONTS.get(_font_key(target(variety)), DEFAULT_FONT)
    return _learner().get("font") or stack, lh


def card_css() -> str:
    """CSS for `.tgt` text on cards: the main script's font, line height and direction, then a rule per variety whose
    script differs (cards carry `data-v="{{Register}}"`, the variety's name capitalised)."""
    def rule(sel: str, v: str | None, lh: bool) -> str:
        stack, height = font(v)
        return (f"{sel} {{ font-family: {stack};{f' line-height: {height};' if lh else ''} "
                f"direction: {'rtl' if is_rtl(v) else 'ltr'}; }}")
    vs = _learner().get("varieties", [])
    main = vs[0] if vs else None
    out = [rule(".tgt", main, True)]
    for v in vs[1:]:
        if target(v) != target(main) or font(v) != font(main):
            out.append(rule(f'[data-v="{v.title()}"] .tgt, .tgt[data-v="{v.title()}"]', v, False))
    return "\n".join(out)
