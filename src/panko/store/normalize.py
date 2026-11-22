"""Arabic normalisation for matching ("is this word already in Panko?").
Display text is never normalised; only the lookup key is."""
from __future__ import annotations

import re

HARAKAT = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")  # vowels, shadda, tatweel
ALEF = re.compile(r"[آأإٱ]")  # آ أ إ ٱ -> ا


def bare(text: str) -> str:
    t = HARAKAT.sub("", text or "")
    t = ALEF.sub("ا", t)
    t = t.replace("ى", "ي")            # ى -> ي
    t = re.sub(r"[.,،؟?!؛:\"'«»]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def strip_article(text: str) -> str:
    """ال / ل- prefix off, for matching 'الكنابي' against 'كنابي'."""
    t = bare(text)
    return t[2:] if t.startswith("ال") and len(t) > 3 else t
