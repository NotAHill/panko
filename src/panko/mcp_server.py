"""Panko as an MCP server (chat mode): the learner's own Claude does the reading and judging, Panko provides the tools.

Run with `panko mcp` (stdio). `panko mcp --config` prints the snippet for Claude Desktop / Claude Code.
Every tool is a thin wrapper over a plain module (panko.work, panko.evidence, panko.store, panko.anki.sync), so the
logic is tested without MCP. Panko never calls a language model here; paid services (audio on sync) need `confirm`.
"""
from __future__ import annotations

import contextlib
import functools
import json
import sys
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer

from panko import prompts, work
from panko.store import Store

INSTRUCTIONS = """Panko turns language-learning sources into checked Anki cards. Call `panko_guide` first: it explains
the workflow (units → prompts → evidence → submit → ingest) and when to ask the learner before acting."""

EDITABLE = {"ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "present", "imperative", "literal",
            "usage", "notes", "related", "examples", "tags", "region", "cards"}

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
                     page_offset: int = 0, first_page: int = 1, last_page: int = 0) -> dict:
    """Register a PDF, a folder of page photos or a text transcript (path absolute or relative to the Panko folder).
    kind: textbook | teacher-sheet | lesson | media | notes. trust 0-100 (teacher material high, shared decks low).
    PDFs: page_offset = PDF page number minus printed page number; first_page/last_page limit the range."""
    s = work.add_source(path, kind, title, id, date, trust, page_offset=page_offset, first=first_page, last=last_page)
    return {k: v for k, v in s.items() if k != "files"} | {"units": f"{len(s['units'])} ({s['units'][0]}…{s['units'][-1]})"}


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
        s.set_status(i, "retired")
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
