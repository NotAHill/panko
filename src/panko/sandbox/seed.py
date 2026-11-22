"""The hand-written sandbox entries, as store data. `panko seed` loads them into the
store (status active). IDs match the notes already in Anki, so syncing updates
those notes in place.

Transliterations and glosses were written by hand and are not verified yet.
"""
from __future__ import annotations

import json

from panko.config import ROOT

P = "_panko_proto_"
MEDIA = ROOT / "assets" / "sandbox" / "media"
LESSON = "Lesson with Oussama, 21 Nov 2026"
SHEET_M6 = "Teacher sheet: Module 6, Mol l-7anut"
GEN = "written by Panko, not yet checked"


def image(slug: str, ext: str = "jpg", credit: str | None = None) -> dict:
    name = f"{P}{slug}.{ext}"
    if credit is None:
        c = json.loads((MEDIA / "credits.json").read_text()).get(name, {})
        credit = f'<a href="{c.get("page", "")}">Wikimedia Commons</a> · {c.get("author", "")} · {c.get("license", "")}'
    return {"file": name, "credit": credit}


def ex(ar, tl, en, source=LESSON, cite=""):
    return {"ar": ar, "tl": tl, "en": en, "source": source, "cite": cite}


def rel(ar, meaning, tl=""):
    return {"ar": ar, "meaning": meaning, "tl": tl}


def entries() -> list[dict]:
    d = "darija"
    return [
        {"id": "proto-w-0001", "kind": "word", "variety": d, "ar": "كنابي", "tl": "kanapi", "tl_alt": "kanāpi",
         "gloss": "sofa, couch", "gloss_note": "from French canapé", "pos": "noun", "gender": "masculine",
         "image": image("sofa"), "sources": [LESSON], "tags": ["topic::furniture", "src::lesson::2026-11-21"],
         "examples": [ex("التلفاز قدام الكنابي.", "t-tilfaz 9eddam l-kanapi", "The TV is in front of the sofa."),
                      ex("كنقلب على كنابي كبير.", "kan9elleb 3la kanapi kbir", "I'm looking for a big sofa.")],
         "related": [rel("سداري", "traditional low bench-sofa", "sdari"), rel("أَرِيكَة", "sofa (Fusha)", "arīka")]},
        {"id": "proto-w-0002", "kind": "word", "variety": d, "ar": "خزانة", "tl": "khzana", "tl_alt": "xzāna",
         "gloss": "wardrobe, cupboard", "pos": "noun", "gender": "feminine", "root": "خ ز ن",
         "image": image("wardrobe"), "sources": [LESSON], "tags": ["topic::furniture", "src::lesson::2026-11-21"],
         "examples": [ex("الخزانة ورا الباب.", "l-khzana wra l-bab", "The wardrobe is behind the door."),
                      ex("الخزانة الكبيرة فين نحطها؟", "l-khzana l-kbira fin n7ettha?", "Where do I put the big wardrobe?")],
         "related": [rel("مخزن", "storeroom (same root)", "makhzen"), rel("خِزَانَة", "cupboard; library (Fusha)", "khizāna")]},
        {"id": "proto-w-0003", "kind": "word", "variety": d, "ar": "تخفيض", "tl": "takhfid", "tl_alt": "təxfīḍ",
         "gloss": "discount", "pos": "noun", "root": "خ ف ض", "image": image("discount"),
         "sources": [LESSON, "Teacher sheet: Bargaining in the Souk"], "tags": ["topic::shopping", "src::lesson::2026-11-21"],
         "examples": [ex("واش تقدر تدير ليا تخفيض؟", "wach t9der tdir liya takhfid?", "Can you give me a discount?"),
                      ex("غادي ندير ليك تخفيض ديال مية درهم.", "ghadi ndir lik takhfid dyal mya dirham",
                         "I'll give you a discount of 100 dirhams.")],
         "related": [rel("نقص ليا شوية", "lower the price a bit for me", "n9es liya chwiya"),
                     rel("خَفَّضَ", "to lower (Fusha, same root)", "khaffaḍa")]},
        {"id": "proto-w-0004", "kind": "word", "variety": d, "ar": "حدا", "tl": "7da", "tl_alt": "ḥda",
         "gloss": "next to, beside", "pos": "preposition", "image": image("nextto", "svg", "Panko diagram"),
         "sources": [LESSON], "tags": ["topic::position", "src::lesson::2026-11-21"],
         "examples": [ex("حط الكرسي حدا الحيط.", "7ett l-korsi 7da l-7it", "Put the chair next to the wall.")],
         "related": [rel("قدام", "in front of", "9eddam"), rel("ورا", "behind", "wra"), rel("بين", "between", "bin"),
                     rel("قبالة", "facing", "9bala"), rel("بِجَانِبِ", "next to (Fusha)", "bi-jānibi")]},
        {"id": "proto-p-0001", "kind": "phrase", "variety": d, "ar": "كنقلب على مراية لغرفة ديالي.",
         "tl": "kan9elleb 3la mraya l-ghorfa dyali", "tl_alt": "kanqəlləb ʿla mrāya l-ġorfa dyāli",
         "gloss": "I'm looking for a mirror for my room.", "literal": "I'm searching on a mirror for my room",
         "usage": "How to open a request in a shop.", "image": image("mirror"), "sources": [LESSON],
         "tags": ["topic::shopping", "src::lesson::2026-11-21"],
         "related": [rel("كنقلب على", "I'm looking for", "kan9elleb 3la"), rel("مراية", "mirror", "mraya"),
                     rel("غرفة", "room", "ghorfa")]},
        {"id": "proto-p-0002", "kind": "phrase", "variety": d, "ar": "واش نقدر نخلص بالكارت؟",
         "tl": "wach n9der nkhelless b l-kart?", "tl_alt": "wāš nqdər nxəlləṣ b-l-kārṭ?", "gloss": "Can I pay by card?",
         "literal": "can I pay with the card?", "usage": "واش turns a sentence into a yes/no question.",
         "image": image("cardpay"), "sources": [LESSON], "tags": ["topic::shopping", "src::lesson::2026-11-21"],
         "related": [rel("نقدر", "I can", "n9der"), rel("نخلص", "I pay", "nkhelless"), rel("الكارت", "card", "l-kart")]},
        {"id": "proto-p-0003", "kind": "phrase", "variety": d, "ar": "كتبها عليا فالكارني.",
         "tl": "ktebha 3liya f l-karni", "tl_alt": "ktəbha ʿlīya f-l-karni", "gloss": "Put it on my tab.",
         "literal": "write it on me in the notebook",
         "usage": "At the corner shop when buying on credit. The karni is the shopkeeper's notebook of what "
                  "regulars owe; pay on the day you said you would.",
         "sources": [SHEET_M6 + ", §3"], "tags": ["topic::shopping", "src::teacher::m06-hanout"],
         "related": [rel("الكارني", "the shop's credit notebook", "l-karni")]},
        {"id": "proto-w-0101", "kind": "word", "variety": "fusha", "ar": "مَثَّلَ", "ar_bare": "مثل", "ar_partial": "مثّل",
         "ar_prompt": "مثّل", "tl": "maththala", "gloss": "to represent; to act (a role)", "pos": "verb",
         "root": "م ث ل", "pattern": "فَعَّلَ", "form": "II", "present": "يُمَثِّلُ", "imperative": "مَثِّلْ", "masdar": "تَمْثِيل",
         "image": image("actor"), "review": False, "tags": ["pos::verb", "root::م_ث_ل"],
         "sources": ["Your iExplore card", '<a href="https://en.wiktionary.org/wiki/مثل">Wiktionary</a>'],
         "examples": [ex("يُمَثِّلُ الوَفْدُ بِلادَهُ في المُؤْتَمَرِ.", "yumaththilu l-wafdu bilādahu fī l-muʾtamar",
                         "The delegation represents its country at the conference.", GEN),
                      ex("ضَرَبَ اللَّهُ مَثَلًا", "ḍaraba llāhu mathalan", "Allah presents a parable.", "", "Quran 16:75 (An-Nahl)")],
         "related": [rel("مِثْل", "like, similar to", "mithl"), rel("مِثَال", "example", "mithāl"),
                     rel("مَثَل", "parable, proverb", "mathal"), rel("مُمَثِّل", "actor; representative", "mumaththil")]},
        {"id": "proto-w-0102", "kind": "word", "variety": "fusha", "ar": "قِطْعَة", "ar_bare": "قطعة", "ar_prompt": "قطعة",
         "tl": "qiṭʿa", "gloss": "piece", "pos": "noun", "gender": "feminine", "plural": "قِطَع", "root": "ق ط ع",
         "pattern": "فِعْلَة", "image": image("piece"), "review": False, "tags": ["pos::noun", "root::ق_ط_ع"],
         "sources": ["Your iExplore card"],
         "examples": [ex("أَكَلْتُ قِطْعَةً مِنَ الخُبْزِ.", "akaltu qiṭʿatan mina l-khubz", "I ate a piece of bread.", GEN)],
         "related": [rel("قَطَعَ", "to cut", "qaṭaʿa"), rel("قطعة", "piece (Darija, same word)", "9eT3a")]},
    ]


def load(store) -> int:
    for e in entries():
        store.put(e, status="active")
    return len(entries())
