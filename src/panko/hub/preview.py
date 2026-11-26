"""A card as Anki would show it: Panko's own templates and CSS filled with the entry's fields.

Covers what the Panko templates use: `{{Field}}`, `{{#Field}}…{{/Field}}`, `{{^Field}}…{{/Field}}`, `{{type:Field}}`
and `[sound:file]`. A card exists only when its front isn't empty, as in Anki, so optional cards that are off don't
show. Audio comes from the cache only: nothing is generated or paid for here.
"""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

from panko.anki.sync import PREFIX
from panko.cards import build
from panko.cards import note_types as T

SECTION = re.compile(r"\{\{([#^])([^}]+)\}\}(.*?)\{\{/\2\}\}", re.S)
FIELD = re.compile(r"\{\{([^#^/}][^}]*)\}\}")
SOUND = re.compile(r"\[sound:([^\]]+)\]")


PLAY = ('<button class="pk-play" aria-label="play" onclick="var a=this.nextElementSibling;a.currentTime=0;a.play()">'
        '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M7 4.5v15l12-7.5z" fill="currentColor"/></svg>'
        '</button><audio preload="none" src="{src}"></audio>')
LATER = '<span class="pk-later" title="made on the next sync">♪ audio on sync</span>'


def _sound(name: str, have) -> str:
    if have is not None and not have(name):
        return LATER
    return PLAY.format(src=html.escape(name))


def fill(template: str, fields: dict, have=None) -> str:
    """The template filled as Anki would. `have(file)` says whether a media file exists; sounds that don't yet are
    shown as made-on-sync instead of a player that can't play."""
    t = template
    while True:
        new = SECTION.sub(lambda m: m.group(3) if bool(fields.get(m.group(2).strip())) == (m.group(1) == "#") else "", t)
        if new == t:
            break
        t = new

    def field(m):
        name = m.group(1).strip()
        if name.startswith("type:"):
            return '<input class="typeans" placeholder="type the answer" disabled>'
        return fields.get(name.split(":")[-1], "")
    out = SOUND.sub(lambda m: _sound(m.group(1), have), FIELD.sub(field, t))
    return re.sub(f"(?:{re.escape(LATER)})+", LATER, out)


IMG = re.compile(r'(<(?:img|audio)\b[^>]*?\bsrc=")([^"/:]+)(")', re.I)
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
        ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".wav": "audio/wav"}


def inline_images(body: str, dirs, limit: int = 3_000_000) -> str:
    """Card pictures and audio as data URIs, so the sandboxed preview makes no requests of its own."""
    def sub(m):
        name = html.unescape(m.group(2))
        mime = MIME.get(Path(name).suffix.lower())
        for d in dirs if mime else ():
            p = Path(d) / name
            if p.is_file() and p.stat().st_size <= limit:
                return f"{m.group(1)}data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}{m.group(3)}"
        return m.group(0)
    return _no_dead_audio(IMG.sub(sub, body))


DEAD = re.compile(r'(<button class="pk-play"(?:(?!</button>).)*</button>)?<audio\b[^>]*\bsrc="(?!data:)[^"]*"[^>]*></audio>', re.I | re.S)
SAY_EMPTY = re.compile(r'<span class="say"[^>]*>\s*</span>')


def _no_dead_audio(body: str) -> str:
    """Audio not made yet (or too big to inline) can't load in the sandbox, and the browser reports each one as an
    error. A player with none left becomes the made-on-sync badge, as headword sounds do."""
    body = DEAD.sub(lambda m: LATER if m.group(1) else "", body)
    return SAY_EMPTY.sub(LATER, body)


def _empty(front: str) -> bool:
    return not re.sub(r"<script.*?</script>|<[^>]+>|\s", "", front, flags=re.S) and "<img" not in front \
        and "<audio" not in front


def cards(entry: dict, narrator=None, have=None, design: dict | None = None) -> dict:
    """{model, deck, tags, css, cards: [{name, front, back}]} for the cards Anki would make from this entry, with the
    configured card design or a draft one."""
    from panko.media import audio
    note = build.to_note(entry, narrator or audio.DryRun(prefix=PREFIX), design=design)
    tmpls = (T.word_templates(design) if note["model"] == T.WORD_MODEL else T.phrase_templates(design))
    out = []
    for t in tmpls:
        if _empty(fill(t["Front"], note["fields"])):
            continue
        out.append({"name": re.sub(r"^\d+ ", "", t["Name"]), "front": fill(t["Front"], note["fields"], have),
                    "back": fill(t["Back"], note["fields"], have)})
    return {"model": note["model"], "deck": note["deck"], "tags": note["tags"], "css": T.css(design), "cards": out}


DARK = ".card{background:#2f2f31;color:#eee}"
LIGHT = ".card{background:#fff;color:#1b1b1b}"


# The card's own script and styles run; nothing loads from anywhere (media come inline), so a card from a shared deck
# can't call out, not even with an image. The iframe's sandbox keeps it away from the hub's page and cookie.
CSP = ("default-src 'none'; img-src data:; media-src data:; font-src data:; style-src 'unsafe-inline'; "
       "script-src 'unsafe-inline'")


def page(css: str, body: str, theme: str = "") -> str:
    """A standalone document for a sandboxed iframe. `theme` "dark" or "light" pins the look (as Anki's night mode
    would); otherwise it follows the system."""
    look = {"dark": DARK, "light": LIGHT}.get(theme, f"{LIGHT}@media (prefers-color-scheme: dark){{{DARK}}}")
    night = " nightMode night_mode" if theme == "dark" else ""
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f"<style>{css}\nbody{{margin:0}} .card{{min-height:100vh;box-sizing:border-box}}"
            ".typeans{font:inherit;padding:6px 10px;margin-top:12px;border-radius:6px;border:1px solid #bbb}"
            ".pk-play{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;"
            "border-radius:50%;border:1px solid rgba(128,128,128,.45);background:transparent;color:inherit;"
            "cursor:pointer;margin:6px 3px;padding:0 0 0 2px;vertical-align:middle}"
            ".pk-play:hover{background:rgba(128,128,128,.15)}"
            ".pk-later{display:inline-block;font:12px ui-monospace,Menlo,monospace;opacity:.5;margin:8px 0}"
            f"{look}</style></head>"
            f'<body class="{night.strip()}"><div class="card{night}">{body}</div>{FIT}</body></html>')


# Tells the hub how tall the card is, so the preview frame fits it (the card fills at least the frame, so its own
# height can't be read: the bottom of its last child can). A click on the card flips it, and keys go to the hub, so
# space flips the card and j/k move through the list while the preview has focus.
FIT = ("<script>(function(){var c=document.querySelector('.card');function f(){var b=0;"
       "for(var i=0;i<c.children.length;i++){var r=c.children[i].getBoundingClientRect();if(r.height)b=Math.max(b,r.bottom)}"
       "parent.postMessage({pankoHeight:Math.ceil(b+window.scrollY+parseFloat(getComputedStyle(c).paddingBottom||0))},'*')}"
       "addEventListener('load',f);document.addEventListener('toggle',f,true);"
       "if(window.ResizeObserver)new ResizeObserver(f).observe(c);setTimeout(f,60);"
       "document.addEventListener('click',function(e){if(e.target.closest('button,a,summary,details,audio,input,.say'))return;"
       "parent.postMessage({pankoFlip:1},'*')});"
       "document.addEventListener('keydown',function(e){if(e.target.closest('input')||e.metaKey||e.ctrlKey||e.altKey)return;"
       "if(e.key===' ')e.preventDefault();parent.postMessage({pankoKey:e.key},'*')});"
       "['play','error'].forEach(function(t){document.addEventListener(t,function(e){"
       "parent.postMessage({pankoAudio:t,detail:e.target.error?e.target.error.message||String(e.target.error.code):''},'*')},true)});"
       "document.addEventListener('click',function(e){var b=e.target.closest('.pk-play');if(!b)return;"
       "var a=b.nextElementSibling;a.play().catch(function(x){parent.postMessage({pankoAudio:'blocked',detail:x.name+': '+x.message},'*')})},true)"
       "})()</script>")
