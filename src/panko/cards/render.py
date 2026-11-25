"""Turns structured entry data into the HTML that goes into the panel fields
(ExamplesHTML, LinksHTML, ...). All card markup lives here and in note_types.py,
so the look can change in one place and be re-rendered for every note."""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape


@dataclass
class Example:
    ar: str
    tl: str            # main transliteration (teacher's Arabizi for Darija)
    en: str
    audio: str | list[str] = ""   # media filename(s) (.mp3), played in turn with one tap, never autoplayed
    source: str = ""   # shown only in the Sources section
    cite: str = ""     # shown under the example (scripture references, e.g. "Quran 16:75")


@dataclass
class Related:
    ar: str
    meaning: str
    tl: str = ""


@dataclass
class Entry:
    examples: list[Example] = field(default_factory=list)
    related: list[Related] = field(default_factory=list)
    word_sources: list[str] = field(default_factory=list)
    audio_source: str = ""
    image_source: str = ""


def say_button(audio: str | list[str]) -> str:
    """One play button; with several files (one per voice) a tap plays them one after another."""
    files = [audio] if isinstance(audio, str) else list(audio)
    files = [f for f in files if f]
    if not files:
        return ""
    return ('<span class="say" role="button" aria-label="play">'
            + "".join(f'<audio preload="none" src="{escape(f)}"></audio>' for f in files) + "</span>")


def examples(exs: list[Example]) -> str:
    return "".join(
        f'<div class="ex"><div class="tgt ex-tgt" dir="auto">{escape(e.ar)}{say_button(e.audio)}</div>'
        f'<div class="ex-tl">{escape(e.tl)}</div><div class="ex-en">{escape(e.en)}</div>'
        + (f'<div class="cite">{escape(e.cite)}</div>' if e.cite else "") + '</div>'
        for e in exs
    )


def related(items: list[Related]) -> str:
    rows = "".join(
        f'<tr><td class="tgt" dir="auto">{escape(r.ar)}</td>'
        f'<td>{escape(r.tl) + " · " if r.tl else ""}{escape(r.meaning)}</td></tr>'
        for r in items
    )
    return f'<table class="rel">{rows}</table>' if rows else ""


def grammar(pos: str = "", gender: str = "", plural: str = "", root: str = "", form: str = "",
            present: str = "", imperative: str = "", masdar: str = "") -> str:
    """One or two short lines, e.g. 'noun, masculine' / 'verb, form II · root م ث ل'."""
    first = ", ".join(x for x in [pos, gender, f"form {form}" if form else ""] if x)
    bits = [escape(first)] if first else []
    if plural:
        bits.append(f'plural <span class="tgt" dir="auto">{escape(plural)}</span>')
    if root:
        bits.append(f'root <span class="tgt" dir="auto">{escape(root)}</span>')
    line1 = " · ".join(bits)
    conj = [(lbl, v) for lbl, v in [("present", present), ("imperative", imperative), ("masdar", masdar)] if v]
    line2 = " · ".join(f'{lbl} <span class="tgt" dir="auto">{escape(v)}</span>' for lbl, v in conj)
    return "".join(f"<div>{x}</div>" for x in [line1, line2] if x)


def sources(entry: Entry) -> str:
    items = list(entry.word_sources)
    for i, e in enumerate(entry.examples, 1):
        if e.source or e.cite:
            items.append(f"Example {i}: {e.source or e.cite}")
    if entry.audio_source:
        items.append(f"Audio: {entry.audio_source}")
    if entry.image_source:
        items.append(f"Picture: {entry.image_source}")
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else ""
