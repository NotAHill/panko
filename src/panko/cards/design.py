"""Card design: what the back of a card shows and in what order, what the fronts carry, sizes and fonts, and up to
four sections of your own. Chosen in the hub (Cards → design) or in `[cards]` in config.

Only template HTML and CSS change, never the field list or the card templates' names, so a new design reaches Anki
with a normal sync. Your own sections use the spare fields every Panko note already has (Spare1–4); what each card
says in them is the entry's `extra` (editable per card in the hub).

The defaults reproduce the built-in design exactly."""
from __future__ import annotations

import html
import re

WORD_BACK = ["picture", "word", "audio", "translit", "gloss", "grammar", "examples", "related", "notes", "mine",
             "sources"]
PHRASE_BACK = ["picture", "phrase", "audio", "translit", "translation", "usage", "words", "dialogue", "notes", "mine",
               "sources"]
REQUIRED = {"word", "gloss", "phrase", "translation"}           # the answer is always on the back
EXTRA_SLOTS = ["extra1", "extra2", "extra3", "extra4"]          # → Spare1–4
CARD_TYPES = ["recognition", "production", "listening", "picture", "plural", "verb-forms", "root", "typed"]
FONTS = {"system": '-apple-system, "Helvetica Neue", "Segoe UI", Roboto, sans-serif',
         "serif": 'Georgia, "Iowan Old Style", "Times New Roman", serif',
         "rounded": 'ui-rounded, "SF Pro Rounded", "Nunito", -apple-system, sans-serif',
         "mono": 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'}

DEFAULT = {
    "word_back": WORD_BACK, "phrase_back": PHRASE_BACK,
    "front_audio": True,          # recognition fronts play the word
    "production_picture": True,   # production fronts show the picture above the gloss
    "default_cards": ["recognition", "production"],
    "word_size": 48, "gloss_size": 24, "picture_height": 220,
    "align": "center",            # center | left
    "font": "system",             # a key of FONTS
    "extras": [],                 # [{"slot": "extra1", "label": "Mnemonic"}]
    "custom_css": "",
}

SECTION_NAMES = {
    "picture": "picture", "word": "word", "phrase": "phrase", "audio": "audio", "translit": "transliteration",
    "gloss": "gloss", "translation": "translation", "grammar": "grammar", "examples": "examples",
    "related": "related words", "usage": "usage", "words": "key words", "dialogue": "dialogue", "notes": "notes",
    "mine": "my notes", "sources": "sources",
}

_WORD = {
    "picture": '{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}',
    "word": '<div class="tgt word" dir="auto">{{Word}}</div>',
    "audio": '{{#Audio}}<div>{{Audio}}</div>{{/Audio}}',
    "translit": '<div class="tl">{{Translit}}{{#TranslitAlt}}<span class="tl2">{{TranslitAlt}}</span>{{/TranslitAlt}}</div>',
    "gloss": '<div class="gloss">{{Gloss}}</div>\n{{#GlossNote}}<div class="gnote">{{GlossNote}}</div>{{/GlossNote}}',
    "grammar": '{{#MorphologyHTML}}<div class="gram">{{MorphologyHTML}}</div>{{/MorphologyHTML}}',
    "examples": '{{#ExamplesHTML}}<div class="block">{{ExamplesHTML}}</div>{{/ExamplesHTML}}',
    "related": '{{#LinksHTML}}<div class="block"><div class="lbl">Related</div>{{LinksHTML}}</div>{{/LinksHTML}}',
    "notes": '{{#NotesHTML}}<div class="block notes">{{NotesHTML}}</div>{{/NotesHTML}}',
    "mine": '{{#MyNotes}}<div class="block mine">{{MyNotes}}</div>{{/MyNotes}}',
    "sources": '{{#SourcesHTML}}<div class="block"><details class="srcs"><summary>Sources</summary>{{SourcesHTML}}</details></div>{{/SourcesHTML}}',
}
_PHRASE = {
    "picture": _WORD["picture"],
    "phrase": '<div class="tgt phrase" dir="auto">{{#PhraseFull}}{{PhraseFull}}{{/PhraseFull}}{{^PhraseFull}}{{Phrase}}{{/PhraseFull}}</div>',
    "audio": _WORD["audio"], "translit": _WORD["translit"],
    "translation": '<div class="gloss">{{Translation}}</div>\n{{#Literal}}<div class="gnote">literally “{{Literal}}”</div>{{/Literal}}',
    "usage": '{{#UsageHTML}}<div class="block notes">{{UsageHTML}}</div>{{/UsageHTML}}',
    "words": '{{#KeyWordsHTML}}<div class="block"><div class="lbl">Words</div>{{KeyWordsHTML}}</div>{{/KeyWordsHTML}}',
    "dialogue": '{{#DialogueHTML}}<div class="block">{{DialogueHTML}}</div>{{/DialogueHTML}}',
    "notes": _WORD["notes"], "mine": _WORD["mine"], "sources": _WORD["sources"],
}


def spare(slot: str) -> str:
    return "Spare" + slot.removeprefix("extra")


def _label(text: str) -> str:
    """A section label is plain text: no template braces, escaped for HTML."""
    return html.escape(re.sub(r"[{}]", "", str(text)).strip()[:40])


def _int(v, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def normalise(d: dict | None) -> dict:
    """A design with every key present and every value in range. Unknown sections are dropped, required ones kept."""
    d = {**DEFAULT, **(d or {})}
    extras, seen = [], set()
    for x in d.get("extras") or []:
        slot, label = str(x.get("slot", "")), _label(x.get("label", ""))
        if slot in EXTRA_SLOTS and slot not in seen and label:
            seen.add(slot)
            extras.append({"slot": slot, "label": label})
    out = {
        "front_audio": bool(d["front_audio"]), "production_picture": bool(d["production_picture"]),
        "default_cards": ["recognition"] + [c for c in CARD_TYPES[1:] if c in (d.get("default_cards") or [])],
        "word_size": _int(d["word_size"], 24, 96, 48), "gloss_size": _int(d["gloss_size"], 14, 48, 24),
        "picture_height": _int(d["picture_height"], 80, 480, 220),
        "align": "left" if d.get("align") == "left" else "center",
        "font": d["font"] if d.get("font") in FONTS else "system",
        "extras": extras, "custom_css": str(d.get("custom_css") or "")[:8000],
    }
    slots = [x["slot"] for x in extras]
    for key, allowed in (("word_back", WORD_BACK), ("phrase_back", PHRASE_BACK)):
        want = [s for s in dict.fromkeys(d.get(key) or allowed) if s in allowed or s in slots]
        want += [s for s in allowed if s in REQUIRED and s not in want]
        out[key] = want
    return out


def load() -> dict:
    from panko.config import settings
    try:
        return normalise(settings().get("cards"))
    except FileNotFoundError:                   # no config yet (a fresh folder, the tests): the built-in design
        return normalise({})


def back(kind: str, design: dict) -> str:
    """The back of a card: the chosen sections in order, then the audio player script (added by note_types)."""
    parts = _WORD if kind == "word" else _PHRASE
    labels = {x["slot"]: x["label"] for x in design["extras"]}
    out = []
    for s in design["word_back" if kind == "word" else "phrase_back"]:
        if s in parts:
            out.append(parts[s])
        elif s in labels:
            f = spare(s)
            out.append(f'{{{{#{f}}}}}<div class="block"><div class="lbl">{labels[s]}</div>{{{{{f}}}}}</div>{{{{/{f}}}}}')
    return "\n" + "\n".join(out) + "\n"


def css(design: dict) -> str:
    """Design CSS added after the base card CSS (nothing when the design is the default)."""
    rules = []
    if design["font"] != "system":
        rules.append(f".card {{ font-family: {FONTS[design['font']]}; }}")
    if design["word_size"] != 48:
        rules.append(f".word {{ font-size: {design['word_size']}px; }}")
    if design["gloss_size"] != 24:
        rules.append(f".gloss {{ font-size: {design['gloss_size']}px; }}")
    if design["picture_height"] != 220:
        rules.append(f".pic img {{ max-height: {design['picture_height']}px; }}")
    if design["align"] == "left":
        rules.append(".card { text-align: left; } .block { margin-left: 0; }")
    if design["custom_css"].strip():
        rules.append("/* your CSS */\n" + design["custom_css"].replace("</", "<\\/"))
    return "\n".join(rules)
