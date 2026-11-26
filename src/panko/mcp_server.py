"""Panko as an MCP server (chat mode): the learner's own Claude does the reading and judging, Panko provides the tools.

Run with `panko mcp` (stdio). `panko mcp --config` prints the snippet for Claude Desktop / Claude Code.
Every tool is a thin wrapper over a plain module (panko.work, panko.evidence, panko.store, panko.anki.sync), so the
logic is tested without MCP. Panko never calls a language model here; paid services (audio on sync) need `confirm`.
"""
from __future__ import annotations

import contextlib
import functools
import json
import re
import sys
from pathlib import Path

from mcp.server.mcpserver import Audio, Image, MCPServer

from panko import prompts, work
from panko.store import EDITABLE, Store

INSTRUCTIONS = """Panko turns language-learning sources into checked Anki cards. Call `panko_guide` first: it explains
the workflow (units → prompts → evidence → submit → ingest) and when to ask the learner before acting."""


server = MCPServer("panko", instructions=INSTRUCTIONS)


def quiet(fn):
    """stdout is the MCP channel: anything a tool prints goes to stderr instead."""
    @functools.wraps(fn)
    def wrap(*a, **kw):
        with contextlib.redirect_stdout(sys.stderr):
            return fn(*a, **kw)
    return wrap


def tool(**kw):
    def deco(fn):
        return server.tool(**kw)(quiet(fn))
    return deco


def _brief(e: dict) -> dict:
    out = {k: e.get(k) for k in ("id", "status", "kind", "ar", "tl", "pos", "gloss") if e.get(k)}
    if (e.get("check") or {}).get("verdict") not in (None, "ok"):
        out["verdict"] = e["check"]["verdict"]
    return out


# ---- workflow & sources --------------------------------------------------------------------------------------------

@tool(structured_output=False)
def panko_guide() -> str:
    """How to run Panko in chat: the workflow, the result format for panko_submit, and what needs the learner's OK."""
    return prompts.render("chat") + "\n## Result schema for panko_submit\n```json\n" \
        + json.dumps(work.UNIT_SCHEMA, ensure_ascii=False) + "\n```\n"


@tool()
def panko_sources() -> dict:
    """Registered sources and their progress (units to do, submitted, held, ingested)."""
    out = {}
    for sid, s in work.sources().items():
        st = work.state(sid)
        out[sid] = {"title": s["title"], "kind": s["kind"], "type": s["type"], "units": len(st),
                    **{k: sum(1 for v in st.values() if v == k) for k in ("todo", "submitted", "held", "ingested")}}
    return out


@tool()
def panko_add_source(path: str, kind: str, title: str, id: str = "", date: str = "", trust: int = 70,
                     page_offset: int = 0, first_page: int = 1, last_page: int = 0, tracks: list[str] | None = None,
                     speakers: list[str] | None = None, learner: str = "", transcript: str = "") -> dict:
    """Register a PDF, a folder of page photos, a text transcript, an exported deck (.json) or a lesson recording
    (path absolute or relative to the Panko folder). kind: textbook | teacher-sheet | lesson | media | notes.
    trust 0-100 (teacher material high, shared decks low). PDFs: page_offset = PDF page number minus printed page
    number; first_page/last_page limit the range. Recordings: tracks = more files of the same session (one per mic),
    speakers = a name per track (or per speaker, for one track), learner = which name is the learner, transcript = a
    speech-to-text JSON already made. A recording without one needs `panko_transcribe` before its units exist."""
    s = work.add_source(path, kind, title, id, date, trust, page_offset=page_offset, first=first_page, last=last_page,
                        tracks=tracks or [], speakers=speakers or [], learner=learner, transcript=transcript)
    units = f"{len(s['units'])} ({s['units'][0]}…{s['units'][-1]})" if s["units"] else "none yet: transcribe it first"
    return {k: v for k, v in s.items() if k != "files"} | {"units": units}


@tool()
def panko_transcribe(source: str, confirm: bool = False) -> dict:
    """Speech-to-text for a recording source, with word times, so it splits into units and items get native clips.
    Paid (the [stt] chain, billed per minute of audio). Without confirm: how much audio would be sent. confirm=true
    only after the learner agrees."""
    s = work.source(source)
    if s["type"] != "audio":
        raise ValueError(f"{source} isn't a recording")
    mins = round(s["duration"] * len(s["tracks"]) / 60, 1)
    if not confirm:
        return {"source": source, "tracks": len(s["tracks"]), "minutes": mins, "note": "nothing sent; ask the learner"}
    s = work.transcribe(source)
    return {"source": source, "minutes": mins, "units": s["units"]}


@tool()
def panko_next_work(source: str, n: int = 5) -> dict:
    """The next n units nobody has submitted yet, so a source can be done across many chats."""
    return {"source": source, "next": work.next_work(source, n), **{k: v for k, v in work.pending(source).items()
                                                                     if k in ("units", "todo", "ingested")}}


@tool(structured_output=False)
def panko_page(source: str, unit: str) -> list:
    """A unit to read: the page image (the truth) and its text layer (handy for spelling, but columns interleave)."""
    p = work.page(source, unit)
    meta = json.dumps({"source": source, "unit": unit, "printed_page": p["page"], "text": p["text"]},
                      ensure_ascii=False)
    return [Image(path=p["image"]), meta] if p["image"] else [meta]


@tool()
def panko_prompt(name: str) -> dict:
    """A Panko prompt with the learner's settings filled in, and its answer schema. Names: extract, check,
    pictures-plan, pictures-pick, examples, deck. In chat, read extract, check and pictures-plan once per session."""
    if name not in prompts.PROMPTS:
        raise ValueError(f"no prompt {name!r}; choose from {', '.join(prompts.PROMPTS)}")
    return {"name": name, "prompt": prompts.render(name, web_search=False), "schema": prompts.schema(name)}


# ---- evidence, submit, ingest --------------------------------------------------------------------------------------

@tool()
def panko_evidence(words: list[dict], references: bool = True) -> list[dict]:
    """For each word ({ar, tl, tl_alt, pos}; only ar required): the learner's entry if they have it, entries sharing
    its letters, near-duplicates, and lines from the configured corpora and dictionaries. Free and local."""
    from panko import evidence
    return evidence.lookup(words, refs=references)


@tool()
def panko_submit(source: str, unit: str, result: dict) -> dict:
    """Store one unit's result: {"items": [...]} as panko_guide describes. Validated first; on errors nothing is
    stored and the errors come back to fix. Submitting a unit again replaces its earlier result."""
    return work.submit(source, unit, result)


@tool()
def panko_pending(source: str) -> dict:
    """Progress of a source: units to do, submitted (waiting for ingest), held (items to decide) and ingested."""
    return work.pending(source)


@tool()
def panko_ingest(source: str) -> dict:
    """Merge submitted units into the inbox as candidates (known words become sightings; near-duplicates are held
    for you to decide). Nothing becomes a card until activated and synced."""
    return work.ingest_source(source)


@tool()
def panko_decide(source: str, unit: str, ar: str, known_id: str = "", distinct: bool = False) -> dict:
    """Settle an item panko_ingest held: known_id = it's that entry (a sighting), distinct = a new word. Then call
    panko_ingest again."""
    return work.decide(source, unit, ar, known_id, distinct)


# ---- inbox & entries -----------------------------------------------------------------------------------------------

@tool()
def panko_inbox(tag: str = "", limit: int = 50, html: bool = False) -> dict:
    """Candidates waiting to become cards (optionally only those with a tag, e.g. src::textbook::my-book).
    html=true also writes a review page with keep/drop toggles and returns its path."""
    es = [e for e in Store().entries("candidate") if not tag or tag in e.get("tags", [])]
    out = {"candidates": len(es), "shown": [_brief(e) for e in es[:limit]]}
    if html:
        from panko import review
        out["page"] = str(review.write(es, work.plans(), title=f"Inbox review{' · ' + tag if tag else ''}"))
    return out


@tool()
def panko_entry(id: str) -> dict:
    """Everything about one entry: its fields, where it was seen, and whether it's in Anki."""
    s = Store()
    e = s.get(id)
    if not e:
        raise KeyError(f"no entry {id}")
    return {"entry": e, "sightings": s.sightings(id), "anki": s.link(id)}


@tool()
def panko_activate(ids: list[str]) -> dict:
    """Ask the learner first. Candidates become active, so the next sync adds them to Anki."""
    from panko.ingest import activate
    return {"activated": activate(Store(), ids=ids)}


@tool()
def panko_reject(ids: list[str]) -> dict:
    """Retire candidates the learner doesn't want (only candidates; cards already in Anki are never retired here)."""
    s = Store()
    done = [i for i in ids if (e := s.get(i)) and e["status"] == "candidate"]
    for i in done:
        s.set_status(i, "retired", why="rejected in chat")
    return {"retired": done, "skipped": [i for i in ids if i not in done]}


@tool()
def panko_edit(id: str, fields: dict) -> dict:
    """Correct an entry when the learner asks (fields: ar, tl, tl_alt, gloss, gloss_note, pos, plural, present,
    examples, related, usage, notes, tags...). The learner's own notes field is never written. The card changes on
    the next sync."""
    bad = sorted(set(fields) - EDITABLE)
    if bad:
        raise ValueError(f"can't edit {bad}; editable: {sorted(EDITABLE)}")
    s = Store()
    e = s.get(id)
    if not e:
        raise KeyError(f"no entry {id}")
    s.put({**e, **fields})
    return {"id": id, "changed": sorted(fields), "status": e["status"]}


# ---- pictures & audio ----------------------------------------------------------------------------------------------

@tool()
def panko_pictures_todo(status: str = "active", tag: str = "", limit: int = 24) -> dict:
    """Cards with no picture and no saved decision, with their saved picture plan if any (choice photo/draw/skip,
    query, prompt). Decide each as `panko_prompt("pictures-plan")` and `panko_prompt("pictures-pick")` say."""
    from panko.media import choose, pictures
    s, done = Store(), choose.load_decisions()
    plans = choose.known_plans()
    cards = [c for c in pictures.export(s, status=status) if c["id"] not in done
             and (not tag or tag in (s.get(c["id"]) or {}).get("tags", []))]
    return {"left": len(cards), "cards": [{**c, "plan": choose.plan_of(c, plans)} for c in cards[:limit]]}


@tool(structured_output=False)
def panko_photo_search(queries: dict) -> list:
    """Photo candidates from the free sites for up to 12 cards: {card id: plain English query}. Returns the contact
    sheets (one row per card, candidates numbered 0–9 in red, a grey tag names the site) and the folder to cite in
    a photo decision: {"photo": {"dir": folder, "index": n}}."""
    from panko.config import ROOT
    from panko.media import pictures
    if not 0 < len(queries) <= 12:
        raise ValueError("give 1 to 12 cards per search")
    base = ROOT / "cache" / "pictures" / "chat"
    out = base / f"run{len(list(base.glob('run*'))) + 1:03d}" if base.exists() else base / "run001"
    sheets = pictures.search(dict(queries), out)
    found = json.loads((out / "cands.json").read_text())
    ids = list(found)
    meta = json.dumps({"dir": str(out), "sheets": [ids[i:i + 6] for i in range(0, len(ids), 6)],
                       "candidates": {k: len(v) for k, v in found.items()}}, ensure_ascii=False)
    return [*(Image(path=p) for p in sheets), meta]


@tool()
def panko_pictures_save(decisions: dict) -> dict:
    """Save picture decisions {card id: {"photo": {"dir", "index"}} | {"prompt": drawing scene} | {"skip": reason}}.
    Checked before saving (the photo must exist in that search folder); `panko_pictures_apply` uses them."""
    from panko.media import choose
    return choose.save_decisions(decisions)


@tool()
def panko_pictures_apply() -> dict:
    """Download and credit the chosen photos (free) and set them on the cards; drawing prompts are kept in
    data/pictures/drawings.json for the learner to draw with `panko draw` (paid). Cards change on the next sync."""
    from panko.config import ROOT
    from panko.media import choose, pictures
    r = pictures.apply(choose.load_decisions())
    p = ROOT / "data" / "pictures" / "drawings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(p.read_text()) if p.exists() else {}
    p.write_text(json.dumps({**old, **r["prompts"]}, ensure_ascii=False, indent=1))
    return {"photos": r["photo"], "skips": r["skip"], "failed": r["failed"], "drawings_waiting": len({**old, **r["prompts"]}),
            "drawings_file": str(p), "note": "drawings cost money: the learner runs `panko draw` on that file"}


@tool(structured_output=False)
def panko_audio(id: str, confirm: bool = False) -> list:
    """An entry's audio (headword and examples, every voice). Without confirm: what would be generated (clips and
    characters, nothing spent). confirm=true after the learner agrees: generates it (paid, then cached, so the
    next sync reuses it) and returns the headword clips to listen to."""
    from panko.cards import build
    from panko.media import audio
    e = Store().get(id)
    if not e:
        raise KeyError(f"no entry {id}")
    dry = audio.DryRun()
    build.to_note(e, dry)
    if not confirm:
        return [json.dumps({"id": id, "clips_to_generate": len(dry.todo),
                            "characters": sum(len(t) for _, t in dry.todo), "note": "dry run"}, ensure_ascii=False)]
    note = build.to_note(e, audio.Narrator())
    files = re.findall(r"\[sound:([^\]]+)\]", note["fields"].get("Audio", ""))
    from panko.media import clips
    paths = [next((d / f for d in (audio.MEDIA, clips._media()) if (d / f).exists()), None) for f in files]
    return [*(Audio(path=p) for p in paths if p),
            json.dumps({"id": id, "generated": len(dry.todo), "headword_clips": files}, ensure_ascii=False)]


# ---- deterministic checks -----------------------------------------------------------------------------------------

@tool()
def panko_verify(ids: list[str] | None = None, status: str = "candidate", apply: bool = False) -> dict:
    """Check entries with tools, not judgement: for varieties with a morphological analyser ([morph]), headwords,
    forms, roots and example sentences against its readings; other varieties against the references (the ones none
    lists are for the teacher). Free. apply=true tags candidates with a spelling, marks or root problem `panko::doubtful` (kept out
    of Anki until cleared); fix them with `panko_edit` using the suggested reading, then `panko_activate` by id."""
    from panko import checks
    st = ("candidate", "active") if status == "all" else (status,)
    r = checks.run(Store(), st, ids=ids, apply=apply)
    return {**r, "doubtful": r["doubtful"][:40], "listed": r["listed"][:40], "ungrounded": r["ungrounded"][:60]}


# ---- gloss clashes ------------------------------------------------------------------------------------------------

@tool()
def panko_clashes(all: bool = False, limit: int = 30) -> dict:
    """Groups of production cards whose glosses share a sense, so their fronts would be ambiguous (by default only
    groups with a candidate). Decide as `panko_prompt("clashes")` says, then `panko_clashes_apply`."""
    from panko import clashes
    from panko.config import ROOT
    s, path = Store(), ROOT / "data" / "work" / "clashes.json"
    found = clashes.open_groups(clashes.find(s, None if all else [e["id"] for e in s.entries("candidate")]), path)
    groups = clashes.undecided(found, clashes.load(path))      # the learner settled the rest in the hub
    return {"groups": len(groups), "shown": groups[:limit]}


@tool()
def panko_clashes_apply(decisions: dict) -> dict:
    """Apply clash decisions {entry id: {"gloss": new} | {"cards": ["recognition"], "note": "The everyday word is …"}
    | {"drop": why, "same": id of the card it duplicates}}. A candidate with `same` becomes that card's duplicate,
    other dropped candidates are retired; a card already in Anki is never removed: it becomes recognition-only and is
    listed for the learner."""
    from panko import clashes
    return clashes.apply(Store(), decisions)


@tool()
def panko_sync(confirm: bool = False) -> dict:
    """Without confirm: a dry run (notes to add/update, audio clips still to pay for), touching neither Anki nor any
    paid service. confirm=true only after the learner agrees: generates the audio and pushes to Anki (Anki must be
    open with its MCP add-on)."""
    from panko.anki import sync
    if not confirm:
        p = sync.plan()
        return {**p, "add": len(p["add"]), "update": len(p["update"]), "add_ids": p["add"][:50],
                "update_ids": p["update"][:50], "note": "dry run; call again with confirm=true after the learner agrees"}
    return sync.sync()


def config_snippet() -> str:
    import shutil

    from panko.config import CHECKOUT, IS_CHECKOUT, ROOT
    if IS_CHECKOUT and ROOT == CHECKOUT:      # running from a source checkout
        uv = shutil.which("uv") or "uv"   # apps don't see the shell's PATH, so the full path
        cmd, args, env = uv, ["--directory", str(ROOT), "run", "--extra", "mcp", "panko", "mcp"], {}
    else:
        exe = Path(sys.executable).with_name("panko")     # the panko next to this Python (a venv's bin)
        cmd = str(exe) if exe.exists() else shutil.which("panko") or "panko"
        args, env = ["mcp"], {"PANKO_HOME": str(ROOT)}
    server = {"command": cmd, "args": args, **({"env": env} if env else {})}
    code = "claude mcp add panko" + "".join(f" -e {k}={v}" for k, v in env.items()) + " -- " + " ".join([cmd, *args])
    return ("Claude Desktop (Settings → Developer → Edit Config, claude_desktop_config.json):\n"
            + json.dumps({"mcpServers": {"panko": server}}, indent=2) + "\n\nClaude Code:\n  " + code + "\n")


def main():
    server.run("stdio")
