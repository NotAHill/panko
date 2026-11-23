"""Entry (from the store) -> Anki note: model, deck, fields, tags.

Everything visual comes from render.py + note_types.py, so a design change is a
re-render. Audio is fetched through the audio provider chain (cached)."""
from __future__ import annotations

import hashlib
import json

from panko.cards import note_types as T
from panko.cards import render as R
from panko.config import deck, settings
from panko.media.audio import Narrator, Silent

CARD_SWITCH = {"production": "EnableProduction", "listening": "EnableListening", "picture": "EnablePicture",
               "plural": "EnablePlural", "verb-forms": "EnableVerbForms", "root": "EnableRoot", "typed": "EnableTyped"}
DEFAULT_CARDS = ["recognition", "production"]   # recognition is always on


def shows_translit(variety: str) -> bool:
    """[learner.translit] none_for lists varieties whose cards show only the script (Fusha, by the learner's choice)."""
    return variety not in settings().get("learner", {}).get("translit", {}).get("none_for", [])


def _examples(entry) -> list[R.Example]:
    tl = shows_translit(entry["variety"])
    return [R.Example(x["ar"], x.get("tl", "") if tl else "", x.get("en", ""), x.get("audio", ""), x.get("source", ""),
                      x.get("cite", "")) for x in entry.get("examples", [])]


def _voice(entry, exs: list[R.Example], narrator: Narrator) -> tuple[str, str]:
    """Headword and every example are read by every voice (man, then woman). Scripture is never voiced."""
    variety = entry["variety"]
    n = narrator.count(variety)
    said = [v for v in (narrator.say(entry["ar"].rstrip(".؟?"), variety, s) for s in range(n)) if v]
    for e in (x for x in exs if not x.cite and not x.audio):
        e.audio = [v.filename for v in (narrator.say(e.ar, variety, s) for s in range(n)) if v]
    return "".join(f"[sound:{v.filename}]" for v in said), " + ".join(v.source for v in said)


def to_note(entry: dict, narrator: Narrator | None = None) -> dict:
    narrator = narrator or Silent()
    exs = _examples(entry)
    audio, audio_src = _voice(entry, exs, narrator)
    img = entry.get("image") or {}
    tl = shows_translit(entry["variety"])
    info = R.Entry(examples=exs, related=[R.Related(r["ar"], r.get("meaning", ""), r.get("tl", "") if tl else "")
                                          for r in entry.get("related", [])],
                   word_sources=entry.get("sources", []), audio_source=audio_src, image_source=img.get("credit", ""))
    common = {
        "Translit": entry.get("tl", "") if tl else "", "TranslitAlt": entry.get("tl_alt", "") if tl else "",
        "Register": entry["variety"].title(),
        "Audio": audio, "AudioSource": audio_src,
        "Image": f'<img src="{img["file"]}">' if img.get("file") else "", "ImageSource": img.get("credit", ""),
        "NotesHTML": entry.get("notes", ""), "SourcesHTML": R.sources(info), "PankoID": entry["id"],
        "PankoData": json.dumps({"schema": "0.3", "status": entry.get("status")}),
    }
    for card in entry.get("cards", DEFAULT_CARDS):
        if card in CARD_SWITCH:
            common[CARD_SWITCH[card]] = "y"
    if entry["kind"] == "word":
        model, all_fields = T.WORD_MODEL, T.WORD_FIELDS
        f = {**common, "Word": entry["ar"], "WordBare": entry.get("ar_bare") or entry["ar"],
             "WordPartial": entry.get("ar_partial", ""), "WordPrompt": entry.get("ar_prompt") or entry["ar"],
             "POS": entry.get("pos", ""), "Gloss": entry.get("gloss", ""), "GlossNote": entry.get("gloss_note", ""),
             "Root": entry.get("root", ""), "Pattern": entry.get("pattern", ""), "VerbForm": entry.get("form", ""),
             "Present": entry.get("present", ""), "Imperative": entry.get("imperative", ""), "Masdar": entry.get("masdar", ""),
             "Gender": entry.get("gender", ""), "Plural": entry.get("plural", ""),
             "ExamplesHTML": R.examples(exs), "LinksHTML": R.related(info.related),
             "MorphologyHTML": R.grammar(pos=entry.get("pos", ""), gender=entry.get("gender", ""), plural=entry.get("plural", ""),
                                         root=entry.get("root", ""), form=entry.get("form", ""), present=entry.get("present", ""),
                                         imperative=entry.get("imperative", ""), masdar=entry.get("masdar", ""))}
    else:
        model, all_fields = T.PHRASE_MODEL, T.PHRASE_FIELDS
        f = {**common, "Phrase": entry["ar"], "PhrasePrompt": entry.get("ar_prompt") or entry["ar"],
             "Translation": entry.get("gloss", ""), "Literal": entry.get("literal", ""), "UsageHTML": entry.get("usage", ""),
             "KeyWordsHTML": R.related(info.related), "DialogueHTML": R.examples(exs)}
    tags = sorted({f"register::{entry['variety']}", f"kind::{entry['kind']}", "panko::prototype", *entry.get("tags", [])}
                  | ({"panko::needs-review"} if entry.get("review", True) else set()))
    fields = {k: f.get(k, "") for k in all_fields if k != "MyNotes"}   # MyNotes is the user's, never written
    return {"model": model, "deck": deck(entry["variety"]), "fields": fields, "tags": tags}


def note_hash(note: dict) -> str:
    return hashlib.sha1(json.dumps(note, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
