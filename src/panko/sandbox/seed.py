"""Seed content for the sandbox decks.

Darija items come from the 21 Nov 2026 lesson (Granola transcript) and the teacher's
Module 6 sheet; Fusha items mirror two existing cards. Transliterations and glosses
were written by hand and are NOT verified yet (tag panko::needs-review).

Audio comes from the audio provider chain (config/panko.toml) via `voice`, a
callable passed in by the builder. Tests pass no voice, so they stay offline.
"""
from __future__ import annotations

import json

from panko.cards import render as R
from panko.cards.render import Entry, Example, Related
from panko.config import ROOT
from panko.media.audio import Narrator, Silent

P = "_panko_proto_"
MEDIA = ROOT / "assets" / "sandbox" / "media"
LESSON = "Lesson with Oussama, 21 Nov 2026"
SHEET_M6 = "Teacher sheet: Module 6, Mol l-7anut"
SILENT = Silent()
_voice: Narrator = SILENT  # set per call by darija_words(voice=...) etc.


def img(slug: str, ext: str = "jpg") -> str:
    return f'<img src="{P}{slug}.{ext}">'


def _voice_all(f: dict, text_field: str, entry: Entry) -> None:
    """Fill headword + example audio from the provider chain, when one is ready."""
    variety = f.get("Register", "").lower()
    n = _voice.count(variety)
    # headword: every voice once (e.g. man then woman); examples: voices take turns
    said = [v for v in (_voice.say(f[text_field].rstrip(".؟?"), variety, slot) for slot in range(n)) if v]
    if said:
        f["Audio"] = "".join(f"[sound:{v.filename}]" for v in said)
        f["AudioSource"] = entry.audio_source = " + ".join(v.source for v in said)
    for i, e in enumerate(x for x in entry.examples if not x.cite):  # scripture: real recitation only
        ve = _voice.say(e.ar, variety, i % n) if n else None
        if ve:
            e.audio = ve.filename


def credit(slug: str) -> str:
    c = json.loads((MEDIA / "credits.json").read_text()).get(f"{P}{slug}.jpg", {})
    return f'<a href="{c.get("page", "")}">Wikimedia Commons</a> · {c.get("author", "")} · {c.get("license", "")}'


def word(fields: dict, entry: Entry, gram: dict | None = None, tags=()) -> dict:
    f = dict(fields)
    _voice_all(f, "Word", entry)
    f["ExamplesHTML"] = R.examples(entry.examples)
    f["LinksHTML"] = R.related(entry.related)
    f["SourcesHTML"] = R.sources(entry)
    f["MorphologyHTML"] = R.grammar(**(gram or {}))
    f["PankoData"] = json.dumps({"schema": "0.2-proto", "verification": "unverified"})
    return {"fields": f, "tags": list(tags)}


def phrase(fields: dict, entry: Entry, tags=()) -> dict:
    f = dict(fields)
    _voice_all(f, "Phrase", entry)
    f["KeyWordsHTML"] = R.related(entry.related)
    f["SourcesHTML"] = R.sources(entry)
    f["PankoData"] = json.dumps({"schema": "0.2-proto", "verification": "unverified"})
    return {"fields": f, "tags": list(tags)}


def darija_words(voice: Narrator = SILENT):
    global _voice
    _voice = voice
    return [
        word({"Word": "كنابي", "WordBare": "كنابي", "WordPrompt": "كنابي",
              "Translit": "kanapi", "TranslitAlt": "kanāpi", "Register": "Darija", "POS": "noun",
              "Gloss": "sofa, couch", "GlossNote": "from French canapé", "Gender": "masculine",
              "Image": img("sofa"), "ImageSource": credit("sofa"),
              "EnableProduction": "y", "PankoID": "proto-w-0001"},
             Entry(examples=[
                 Example("التلفاز قدام الكنابي.", "t-tilfaz 9eddam l-kanapi", "The TV is in front of the sofa.", source=LESSON),
                 Example("كنقلب على كنابي كبير.", "kan9elleb 3la kanapi kbir", "I'm looking for a big sofa.", source=LESSON)],
                 related=[Related("سداري", "traditional low bench-sofa", "sdari"),
                          Related("أَرِيكَة", "sofa (Fusha)", "arīka")],
                 word_sources=[LESSON], image_source=credit("sofa")),
             {"pos": "noun", "gender": "masculine"},
             ["pos::noun", "topic::furniture", "src::lesson::2026-11-21"]),

        word({"Word": "خزانة", "WordBare": "خزانة", "WordPrompt": "خزانة",
              "Translit": "khzana", "TranslitAlt": "xzāna", "Register": "Darija", "POS": "noun",
              "Gloss": "wardrobe, cupboard", "Gender": "feminine",
              "Image": img("wardrobe"), "ImageSource": credit("wardrobe"),
              "EnableProduction": "y", "PankoID": "proto-w-0002"},
             Entry(examples=[
                 Example("الخزانة ورا الباب.", "l-khzana wra l-bab", "The wardrobe is behind the door.", source=LESSON),
                 Example("الخزانة الكبيرة فين نحطها؟", "l-khzana l-kbira fin n7ettha?", "Where do I put the big wardrobe?", source=LESSON)],
                 related=[Related("مخزن", "storeroom (same root)", "makhzen"),
                          Related("خِزَانَة", "cupboard; library (Fusha)", "khizāna")],
                 word_sources=[LESSON], image_source=credit("wardrobe")),
             {"pos": "noun", "gender": "feminine", "root": "خ ز ن"},
             ["pos::noun", "topic::furniture", "src::lesson::2026-11-21"]),

        word({"Word": "تخفيض", "WordBare": "تخفيض", "WordPrompt": "تخفيض",
              "Translit": "takhfid", "TranslitAlt": "təxfīḍ", "Register": "Darija", "POS": "noun",
              "Gloss": "discount", "Image": img("discount"), "ImageSource": credit("discount"),
              "EnableProduction": "y", "PankoID": "proto-w-0003"},
             Entry(examples=[
                 Example("واش تقدر تدير ليا تخفيض؟", "wach t9der tdir liya takhfid?", "Can you give me a discount?", source=LESSON),
                 Example("غادي ندير ليك تخفيض ديال مية درهم.", "ghadi ndir lik takhfid dyal mya dirham",
                         "I'll give you a discount of 100 dirhams.", source=LESSON)],
                 related=[Related("نقص ليا شوية", "lower the price a bit for me", "n9es liya chwiya"),
                          Related("خَفَّضَ", "to lower (Fusha, same root)", "khaffaḍa")],
                 word_sources=[LESSON, "Teacher sheet: Bargaining in the Souk"], image_source=credit("discount")),
             {"pos": "noun", "root": "خ ف ض"},
             ["pos::noun", "topic::shopping", "src::lesson::2026-11-21"]),

        word({"Word": "حدا", "WordBare": "حدا", "WordPrompt": "حدا",
              "Translit": "7da", "TranslitAlt": "ḥda", "Register": "Darija", "POS": "preposition",
              "Gloss": "next to, beside", "Image": img("nextto", "svg"),
              "ImageSource": "Panko diagram", "EnableProduction": "y", "PankoID": "proto-w-0004"},
             Entry(examples=[
                 Example("حط الكرسي حدا الحيط.", "7ett l-korsi 7da l-7it", "Put the chair next to the wall.", source=LESSON)],
                 related=[Related("قدام", "in front of", "9eddam"), Related("ورا", "behind", "wra"),
                          Related("بين", "between", "bin"), Related("قبالة", "facing", "9bala"),
                          Related("بِجَانِبِ", "next to (Fusha)", "bi-jānibi")],
                 word_sources=[LESSON], image_source="Panko diagram"),
             {"pos": "preposition"},
             ["pos::preposition", "topic::position", "src::lesson::2026-11-21"]),
    ]


def darija_phrases(voice: Narrator = SILENT):
    global _voice
    _voice = voice
    return [
        phrase({"Phrase": "كنقلب على مراية لغرفة ديالي.", "PhrasePrompt": "كنقلب على مراية لغرفة ديالي.",
                "Translit": "kan9elleb 3la mraya l-ghorfa dyali", "TranslitAlt": "kanqəlləb ʿla mrāya l-ġorfa dyāli",
                "Register": "Darija", "Translation": "I'm looking for a mirror for my room.",
                "Literal": "I'm searching on a mirror for my room", "Image": img("mirror"), "ImageSource": credit("mirror"),
                "UsageHTML": "How to open a request in a shop.",
                "EnableProduction": "y", "PankoID": "proto-p-0001"},
               Entry(related=[Related("كنقلب على", "I'm looking for", "kan9elleb 3la"),
                              Related("مراية", "mirror", "mraya"), Related("غرفة", "room", "ghorfa")],
                     word_sources=[LESSON], image_source=credit("mirror")),
               ["topic::shopping", "src::lesson::2026-11-21"]),

        phrase({"Phrase": "واش نقدر نخلص بالكارت؟", "PhrasePrompt": "واش نقدر نخلص بالكارت؟",
                "Translit": "wach n9der nkhelless b l-kart?", "TranslitAlt": "wāš nqdər nxəlləṣ b-l-kārṭ?",
                "Register": "Darija", "Translation": "Can I pay by card?",
                "Literal": "can I pay with the card?", "Image": img("cardpay"), "ImageSource": credit("cardpay"),
                "UsageHTML": "واش turns a sentence into a yes/no question.",
                "EnableProduction": "y", "PankoID": "proto-p-0002"},
               Entry(related=[Related("نقدر", "I can", "n9der"), Related("نخلص", "I pay", "nkhelless"),
                              Related("الكارت", "card", "l-kart")],
                     word_sources=[LESSON], image_source=credit("cardpay")),
               ["topic::shopping", "src::lesson::2026-11-21"]),

        phrase({"Phrase": "كتبها عليا فالكارني.", "PhrasePrompt": "كتبها عليا فالكارني.",
                "Translit": "ktebha 3liya f l-karni", "TranslitAlt": "ktəbha ʿlīya f-l-karni",
                "Register": "Darija", "Translation": "Put it on my tab.", "Literal": "write it on me in the notebook",
                "UsageHTML": "At the corner shop when buying on credit. The karni is the shopkeeper's notebook of what "
                             "regulars owe; pay on the day you said you would.",
                "EnableProduction": "y", "PankoID": "proto-p-0003"},
               Entry(related=[Related("الكارني", "the shop's credit notebook", "l-karni")],
                     word_sources=[SHEET_M6 + ", §3"]),
               ["topic::shopping", "src::teacher::m06-hanout"]),
    ]


def fusha_words(voice: Narrator = SILENT):
    global _voice
    _voice = voice
    return [
        word({"Word": "مَثَّلَ", "WordBare": "مثل", "WordPartial": "مثّل", "WordPrompt": "مثّل",
              "Translit": "maththala", "Register": "Fusha", "POS": "verb",
              "Gloss": "to represent; to act (a role)",
              "Root": "م ث ل", "Pattern": "فَعَّلَ", "VerbForm": "II",
              "Present": "يُمَثِّلُ", "Imperative": "مَثِّلْ", "Masdar": "تَمْثِيل",
              "Image": img("actor"), "ImageSource": credit("actor"),
              "EnableVerbForms": "y", "EnableRoot": "y", "PankoID": "proto-w-0101"},
             Entry(examples=[
                 Example("يُمَثِّلُ الوَفْدُ بِلادَهُ في المُؤْتَمَرِ.", "yumaththilu l-wafdu bilādahu fī l-muʾtamar",
                         "The delegation represents its country at the conference.",
                         source="written by Panko, not yet checked"),
                 Example("ضَرَبَ اللَّهُ مَثَلًا", "ḍaraba llāhu mathalan", "Allah presents a parable.", cite="Quran 16:75 (An-Nahl)")],
                 related=[Related("مِثْل", "like, similar to", "mithl"), Related("مِثَال", "example", "mithāl"),
                          Related("مَثَل", "parable, proverb", "mathal"), Related("مُمَثِّل", "actor; representative", "mumaththil")],
                 word_sources=["Your iExplore card", '<a href="https://en.wiktionary.org/wiki/مثل">Wiktionary</a>'],
                 image_source=credit("actor")),
             {"pos": "verb", "form": "II", "root": "م ث ل", "present": "يُمَثِّلُ", "imperative": "مَثِّلْ", "masdar": "تَمْثِيل"},
             ["pos::verb", "root::م_ث_ل"]),

        word({"Word": "قِطْعَة", "WordBare": "قطعة", "WordPrompt": "قطعة",
              "Translit": "qiṭʿa", "Register": "Fusha", "POS": "noun",
              "Gloss": "piece", "Root": "ق ط ع", "Pattern": "فِعْلَة", "Gender": "feminine", "Plural": "قِطَع",
              "Image": img("piece"), "ImageSource": credit("piece"),
              "EnablePlural": "y", "PankoID": "proto-w-0102"},
             Entry(examples=[
                 Example("أَكَلْتُ قِطْعَةً مِنَ الخُبْزِ.", "akaltu qiṭʿatan mina l-khubz", "I ate a piece of bread.",
                         source="written by Panko, not yet checked")],
                 related=[Related("قَطَعَ", "to cut", "qaṭaʿa"), Related("قطعة", "piece (Darija, same word)", "9eT3a")],
                 word_sources=["Your iExplore card"], image_source=credit("piece")),
             {"pos": "noun", "gender": "feminine", "plural": "قِطَع", "root": "ق ط ع"},
             ["pos::noun", "root::ق_ط_ع"]),
    ]
