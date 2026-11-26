"""The hub's JSON API: thin routes over Panko's modules (panko.work, store, checks, pipeline, anki.sync…), the same
logic the commands and chat tools use. Steps that take a while or cost money run as jobs (`panko.hub.jobs`); paid
ones answer with an estimate unless the request says `confirm: true`, and they honour a budget.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from panko.anki.sync import PREFIX
from panko.examples import needs_example
from panko.hub.jobs import Job, Jobs

ROUTES: list[Route] = []
JOBS: Jobs | None = None
EXPECTED = (ValueError, KeyError, FileNotFoundError, FileExistsError, PermissionError, RuntimeError)


class Req:
    def __init__(self, request: Request, body: dict):
        self.path = request.path_params
        self.query = dict(request.query_params)
        self.body = body
        self.base = str(request.base_url)


def _json(data, status: int = 200) -> Response:
    return Response(json.dumps(data, ensure_ascii=False, default=str), status_code=status,
                    media_type="application/json")


def api(method: str, path: str):
    """Register `fn(req)` (run in a worker thread) under /api`path`."""
    def deco(fn):
        async def endpoint(request: Request):
            body = {}
            if request.method in ("POST", "PATCH", "PUT", "DELETE"):
                raw = await request.body()
                try:
                    body = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return _json({"error": "the request body isn't JSON"}, 400)
            try:
                res = await run_in_threadpool(fn, Req(request, body))
            except KeyError as e:
                return _json({"error": str(e.args[0]) if e.args else "not found"}, 404)
            except EXPECTED as e:
                return _json({"error": str(e)}, 400)
            return res if isinstance(res, Response) else _json(res)
        ROUTES.append(Route("/api" + path, endpoint, methods=[method]))
        return fn
    return deco


def _jobs() -> Jobs:
    assert JOBS is not None
    return JOBS


def _start(kind: str, title: str, fn, paid: bool = False) -> dict:
    return {"job": _jobs().submit(kind, title, fn, paid).view()}


def _store():
    from panko.store import Store
    return Store()


def _config_ready() -> bool:
    from panko import setup
    return setup.CONFIG.exists()


def _reload():
    """After the config changed: settings and everything read from them are read again."""
    from panko import config, evidence
    config.settings.cache_clear()
    evidence._references.cache_clear()
    evidence._INDEX.clear()


def _confirmed(req: Req) -> bool:
    return req.body.get("confirm") is True


def _budget(req: Req) -> float | None:
    b = req.body.get("budget")
    return float(b) if b not in (None, "") else None


# ---- meta, overview, readiness -------------------------------------------------------------------------------------

def _presets() -> list[dict]:
    from panko import setup
    out = []
    for slug in setup.presets():
        d = setup.defaults(slug)
        out.append({"slug": slug, "language": d["language"], "script": d["script"], "varieties": d["varieties"],
                    "translit": d["translit"], "wiktionary": d["wiktionary"]})
    return out


@api("GET", "/meta")
def meta(req: Req):
    from panko import lang, setup
    from panko.config import ROOT
    if not _config_ready():
        return {"config": False, "root": str(ROOT), "presets": _presets(), "defaults": setup.DEFAULTS,
                "profiles": setup.anki_profiles()}
    from panko.cards import build
    from panko.config import deck, settings
    s = settings()
    L = s.get("learner", {})
    morph = {}
    try:
        from panko import providers
        morph = {v: p.name for p in providers.chain("morph") for v in p.dbs()}
    except Exception:  # an analyser that can't load must not stop the hub
        pass
    return {"config": True, "root": str(ROOT), "config_path": str(setup.CONFIG), "language": L.get("language", ""),
            "gloss_language": L.get("gloss_language", "English"), "romanised": lang.romanised(),
            "regions": L.get("regions", []), "topics": L.get("topics", []),
            "varieties": [{"name": v, "title": v.title(), "script": lang.label(v), "rtl": lang.is_rtl(v),
                           "font": lang.font(v)[0], "deck": deck(v), "translit": build.shows_translit(v),
                           "analyser": morph.get(v, "")} for v in L.get("varieties", [])],
            "budget": s.get("llm", {}).get("budget_usd", 5)}


@api("GET", "/overview")
def overview(req: Req):
    from panko import llm, work
    st = _store()
    counts: dict[str, dict] = {}
    for e in st.entries(None):
        c = counts.setdefault(e["variety"], {"candidate": 0, "active": 0, "retired": 0, "duplicate": 0, "rejected": 0,
                                             "doubtful": 0, "in_anki": 0, "no_picture": 0, "no_example": 0})
        c[e["status"]] += 1
        if e["status"] == "retired":
            c[_shown_status(e)] += 1
        if e["status"] == "candidate" and "panko::doubtful" in e.get("tags", []):
            c["doubtful"] += 1
        if e["status"] == "active" and not e.get("image") and e.get("picture_pref") != "none":
            c["no_picture"] += 1
        if e["status"] != "retired" and needs_example(e) and not e.get("examples"):
            c["no_example"] += 1
    linked = dict(st.db.execute("SELECT e.variety, COUNT(*) FROM anki a JOIN entries e ON e.id = a.entry_id "
                                "GROUP BY e.variety").fetchall())
    for v, n in linked.items():
        counts.setdefault(v, {}).update(in_anki=n)
    srcs = _sources()
    month = dt.date.today().replace(day=1).isoformat()
    steps = []
    for sid, s in srcs.items():
        if s["submitted"]:
            steps.append({"text": f"{s['submitted']} unit{'s' if s['submitted'] != 1 else ''} of {s['title']} ready to ingest", "go": f"#/sources/{sid}"})
        if s["held"]:
            steps.append({"text": f"{s['title']}: {s['held']} unit{'s' if s['held'] != 1 else ''} with items to decide", "go": f"#/sources/{sid}"})
    cand = sum(c.get("candidate", 0) for c in counts.values())
    if cand:
        steps.append({"text": f"{cand} candidate{'s' if cand != 1 else ''} waiting in the inbox",
                      "go": "#/cards?status=candidate"})
    since = (dt.date.today() - dt.timedelta(days=13)).isoformat()
    added = dict(st.db.execute("SELECT substr(created, 1, 10) d, COUNT(*) FROM entries WHERE created >= ? GROUP BY d",
                               (since,)).fetchall())
    days = [(dt.date.today() - dt.timedelta(days=13 - i)).isoformat() for i in range(14)]
    return {"counts": counts, "sources": srcs, "spend": {"all": llm.usage()["usd"], "month": llm.usage(month)["usd"]},
            "added": [{"day": d, "n": added.get(d, 0)} for d in days], "steps": steps, "jobs": [j.view(tail=3) for j in _jobs().busy()],
            "batches": len(json.loads(llm._batches_file().read_text())) if llm._batches_file().exists() else 0,
            "work_dir": str(work.WORK)}


@api("GET", "/readiness")
def readiness(req: Req):
    from panko import setup
    return {"rows": [{"what": w, "ok": ok, "detail": d} for w, ok, d in setup.check()]}


@api("GET", "/usage")
def usage(req: Req):
    from panko import llm
    month = dt.date.today().replace(day=1).isoformat()
    f = llm._usage_file()
    days: dict[str, float] = {}
    recent = []
    if f.exists():
        for line in f.read_text().splitlines():
            r = json.loads(line)
            days[r["at"][:10]] = days.get(r["at"][:10], 0) + r["cost"]
            recent.append(r)
    return {"all": llm.usage(), "month": llm.usage(month), "days": [{"day": d, "usd": round(v, 4)}
                                                                    for d, v in sorted(days.items())[-60:]],
            "recent": [{k: r.get(k) for k in ("at", "task", "model", "cost", "batch", "id")} for r in recent[-40:][::-1]],
            "budget": llm.budget_default()}


# ---- jobs ----------------------------------------------------------------------------------------------------------

@api("GET", "/jobs")
def jobs(req: Req):
    return {"jobs": [j.view(tail=1) for j in _jobs().all()[:60]]}


@api("GET", "/jobs/{jid}")
def job(req: Req):
    j = _jobs().get(req.path["jid"])
    if not j:
        raise KeyError(f"no job {req.path['jid']}")
    return j.view(tail=int(req.query.get("tail", 600)))


@api("POST", "/jobs/{jid}/cancel")
def cancel(req: Req):
    return {"cancelled": _jobs().cancel(req.path["jid"])}


# ---- sources -------------------------------------------------------------------------------------------------------

def _sources() -> dict:
    from panko import work
    out = {}
    for sid, s in work.sources().items():
        st = work.state(sid)
        out[sid] = {"id": sid, "title": s["title"], "kind": s["kind"], "type": s["type"], "date": s.get("date", ""),
                    "units": len(st), "added": s.get("added", ""),
                    **{k: sum(1 for v in st.values() if v == k) for k in ("todo", "submitted", "held", "ingested")},
                    "transcribe_first": s["type"] == "audio" and not s["units"]}
    return out


@api("GET", "/sources")
def sources(req: Req):
    """Sources in the queue (units to read), and the ones already in the store from before the queue existed."""
    queued = _sources()
    rows = _store().db.execute(
        "SELECT s.id, s.kind, s.title, s.date, s.trust, COUNT(DISTINCT g.entry_id) FROM sources s "
        "LEFT JOIN sightings g ON g.source_id = s.id GROUP BY s.id ORDER BY s.trust DESC, s.title").fetchall()
    known = [{"id": r[0], "kind": r[1], "title": r[2], "date": r[3] or "", "trust": r[4], "entries": r[5],
              "queued": r[0] in queued} for r in rows]
    return {"sources": list(queued.values()), "known": known}


@api("GET", "/sources/{sid}")
def source(req: Req):
    from panko import work
    sid = req.path["sid"]
    s = work.source(sid)
    st = work.state(sid)
    units = []
    for u, v in st.items():
        r = work.result(sid, u) or {}
        units.append({"unit": u, "state": v, "items": len(r.get("items", [])),
                      "page": work.book_page(s, u) if s["type"] in ("pdf", "images") else None})
    info = {k: v for k, v in s.items() if k not in ("files",)}
    if s["type"] == "audio":
        info["minutes"] = round(s.get("duration", 0) * len(s.get("tracks", [])) / 60, 1)
    try:
        from panko import providers
        llm_ready = bool(providers.chain("llm"))
    except Exception:      # a provider that can't load means no API mode, not a broken page
        llm_ready = False
    return {"source": info, "units": units, "pending": work.pending(sid), "llm_ready": llm_ready}


@api("GET", "/sources/{sid}/units/{unit}")
def unit(req: Req):
    from panko import work
    sid, u = req.path["sid"], req.path["unit"]
    p = work.page(sid, u)
    r = work.result(sid, u) or {}
    return {"unit": u, "state": work.state(sid).get(u), "page": p.get("page"), "text": p.get("text", ""),
            "rows": p.get("rows"), "image": f"/api/sources/{sid}/units/{u}/image" if p.get("image") else "",
            "items": r.get("items", []), "held": r.get("held", []), "dropped": r.get("dropped", [])}


@api("GET", "/sources/{sid}/units/{unit}/image")
def unit_image(req: Req):
    from panko import work
    p = work.page(req.path["sid"], req.path["unit"])
    if not p.get("image"):
        raise KeyError("this unit has no image")
    return FileResponse(p["image"])


@api("POST", "/sources")
def add_source(req: Req):
    """Register a source by path (`path`), or export an Anki deck (`deck`, a job: Anki must be open)."""
    from panko import work
    b = req.body
    kind, title = b.get("kind") or "notes", (b.get("title") or "").strip()
    if not title:
        raise ValueError("give the source a title")
    sid = b.get("id", "")
    if not sid:     # a second source with the same title gets its own id instead of replacing the first
        taken, base = work.sources(), work.slug(title)
        sid = next(c for c in [base, *(f"{base}-{i}" for i in range(2, 1000))] if c not in taken)
    opts = dict(sid=sid, date=b.get("date", ""), trust=int(b.get("trust") or 70))
    extra = dict(page_offset=int(b.get("page_offset") or 0), first=int(b.get("first_page") or 1),
                 last=int(b.get("last_page") or 0), tracks=[t for t in b.get("tracks", []) if t],
                 speakers=[x.strip() for x in (b.get("speakers") or "").split(",") if x.strip()],
                 learner=b.get("learner", ""), transcript=b.get("transcript", ""))
    if b.get("deck"):
        def run(job: Job):
            from panko.anki.export import export_deck
            path = work.WORK / "decks" / f"{work.slug(b['deck'])}.json"
            d = export_deck(b["deck"], path)
            job.say(f"exported {len(d['notes'])} notes ({sum(n['studied'] for n in d['notes'])} studied)")
            s = work.add_source(str(path), kind or "deck", title, opts["sid"], opts["date"], opts["trust"])
            return {"id": s["id"], "units": len(s["units"])}
        return _start("add-deck", f"Export deck {b['deck']}", run)
    if not b.get("path"):
        raise ValueError("give a file or folder")
    try:
        s = work.add_source(str(Path(b["path"].strip()).expanduser()), kind, title, opts["sid"], opts["date"],
                            opts["trust"], **extra)
    except FileNotFoundError as e:   # a tool Panko runs, rather than the file, can be what's missing
        tool = {"pdfinfo": "poppler (brew install poppler)", "ffprobe": "ffmpeg (brew install ffmpeg)"}.get(e.filename or "")
        raise ValueError(f"reading this needs {tool}" if tool else str(e)) from e
    return {"id": s["id"], "units": len(s["units"]), "type": s["type"]}


@api("POST", "/sources/{sid}/estimate")
def run_estimate(req: Req):
    from panko import pipeline
    return pipeline.estimate(req.path["sid"], req.body.get("units") or None, int(req.body.get("n") or 5))


@api("POST", "/sources/{sid}/run")
def run_source(req: Req):
    """API mode on the next units (paid): estimate unless `confirm`."""
    from panko import pipeline
    sid, units, n = req.path["sid"], req.body.get("units") or None, int(req.body.get("n") or 5)
    if not _confirmed(req):
        return {"estimate": pipeline.estimate(sid, units, n)}
    batch, budget = bool(req.body.get("batch")), _budget(req)

    def run(job: Job):
        r = pipeline.run(sid, units, n, batch=batch, budget=budget, store=_store())
        job.say(f"done {len(r['done'])}, waiting {len(r['waiting'])}, failed {len(r['failed'])}; spent ${r['spent']:.2f}")
        return r
    return _start("run", f"Run {n if not units else len(units)} unit(s) of {sid}", run, paid=True)


@api("POST", "/sources/{sid}/transcribe")
def transcribe(req: Req):
    from panko import work
    sid = req.path["sid"]
    s = work.source(sid)
    if s["type"] != "audio":
        raise ValueError(f"{sid} isn't a recording")
    mins = round(s["duration"] * len(s["tracks"]) / 60, 1)
    if not _confirmed(req):
        return {"estimate": {"tracks": len(s["tracks"]), "minutes": mins}}
    return _start("transcribe", f"Transcribe {s['title']}", lambda job: {"units": work.transcribe(sid)["units"]},
                  paid=True)


@api("POST", "/sources/{sid}/ingest")
def ingest(req: Req):
    from panko import work
    sid = req.path["sid"]

    def run(job: Job):
        r = work.ingest_source(sid, _store())
        job.say(f"{r['new']} new candidates, {r['known']} known, {r['dropped']} dropped, {r['merged']} merged, "
                f"{len(r['homographs'])} homographs, {len(r['held'])} held"
                + (f", {len(r['rejected_again'])} you'd rejected kept out" if r.get("rejected_again") else ""))
        return r
    return _start("ingest", f"Ingest {sid}", run)


@api("POST", "/sources/{sid}/decide")
def decide(req: Req):
    from panko import work
    b = req.body
    return work.decide(req.path["sid"], b["unit"], b["ar"], b.get("known_id", ""), bool(b.get("distinct")))


# ---- entries -------------------------------------------------------------------------------------------------------

SET_ASIDE = ("duplicate", "rejected")


def _shown_status(e: dict) -> str:
    """In the store a card set aside is "retired"; the hub says which kind: a duplicate, or a word you rejected."""
    if e["status"] != "retired":
        return e["status"]
    return "duplicate" if e.get("merged_into") else "rejected"


def _flags(e: dict, linked: set) -> list[str]:
    if e["status"] == "retired":      # the tab already says why it's there
        return []
    f = []
    if "panko::doubtful" in e.get("tags", []):
        f.append("doubtful")
    v = (e.get("check") or {}).get("verdict")
    if v and v not in ("ok", "fix", "doubtful"):
        f.append(v)
    if (e.get("check") or {}).get("morph"):
        f.append("check")
    if not e.get("image") and e.get("picture_pref") != "none":
        f.append("no-picture")
    if needs_example(e) and not e.get("examples"):
        f.append("no-example")
    if e["id"] in linked:
        f.append("in-anki")
    return f


def _match(e: dict, q: str) -> bool:
    from panko import lang
    key = lang.bare(q)
    hay = " ".join([lang.bare(e["ar"]), (e.get("tl") or "").lower(), (e.get("gloss") or "").lower(), e["id"],
                    " ".join(e.get("tags", [])).lower()])
    return all(w in hay for w in key.split()) or q.lower() in hay


@api("GET", "/entries")
def entries(req: Req):
    q = req.query
    st = _store()
    status = q.get("status", "candidate")
    status = "rejected" if status == "retired" else status          # old links
    es = st.entries(None if status == "all" else "retired" if status in SET_ASIDE else status, q.get("variety") or None)
    if status in SET_ASIDE:
        es = [e for e in es if _shown_status(e) == status]
    linked = {r[0] for r in st.db.execute("SELECT entry_id FROM anki")}
    flag, tag, text = q.get("flag", ""), q.get("tag", ""), q.get("q", "").strip()
    if q.get("source"):
        seen = {r[0] for r in st.db.execute("SELECT entry_id FROM sightings WHERE source_id = ?", (q["source"],))}
        es = [e for e in es if e["id"] in seen]
    if q.get("kind") in ("word", "phrase"):
        es = [e for e in es if e["kind"] == q["kind"]]
    rows, flag_counts = [], {}
    for e in es:
        fl = _flags(e, linked)
        for f in fl:
            flag_counts[f] = flag_counts.get(f, 0) + 1
        if flag and flag not in fl:
            continue
        if tag and not any(t.startswith(tag) for t in e.get("tags", [])):
            continue
        if text and not _match(e, text):
            continue
        rows.append({"id": e["id"], "status": _shown_status(e), "variety": e["variety"], "kind": e["kind"], "ar": e["ar"],
                     "tl": e.get("tl", ""), "gloss": e.get("gloss", ""), "pos": e.get("pos", ""), "flags": fl,
                     "updated": e.get("updated", ""), "image": (e.get("image") or {}).get("file", "")})
    sort = q.get("sort", "id")
    if sort == "word":
        rows.sort(key=lambda r: r["ar"])
    elif sort == "gloss":
        rows.sort(key=lambda r: r["gloss"].lower())
    elif sort == "recent":
        rows.sort(key=lambda r: r["updated"], reverse=True)
    off, lim = int(q.get("offset", 0)), min(int(q.get("limit", 100)), 500)
    tags: dict[str, int] = {}
    for e in es:
        for t in e.get("tags", []):
            tags[t] = tags.get(t, 0) + 1
    return {"total": len(rows), "offset": off, "rows": rows[off:off + lim], "flags": flag_counts,
            "tags": sorted(tags.items(), key=lambda x: (-x[1], x[0]))[:200]}


@api("GET", "/entries/{eid}")
def entry(req: Req):
    from panko.store import EDITABLE
    st = _store()
    e = st.get(req.path["eid"])
    if not e:
        raise KeyError(f"no entry {req.path['eid']}")
    same = re.match(r"same as (\S+)", e.get("merged_into") or "")
    kept = st.get(same.group(1)) if same else None
    dups = st.duplicates_of(e["id"])
    seen = st.sightings(e["id"]) + [x for d in dups for x in st.sightings(d["id"])]   # its copies' sources count too
    return {"entry": e, "sightings": seen, "anki": st.link(e["id"]), "editable": sorted(EDITABLE),
            "kept": _brief(kept) if kept else None, "duplicates": [_brief(x) for x in dups],
            "also": [_brief(x) for i in e.get("merged_also", []) if (x := st.get(i))]}


def _brief(x: dict) -> dict:
    return {"id": x["id"], "ar": x["ar"], "tl": x.get("tl", ""), "gloss": x.get("gloss", ""), "status": x["status"]}


@api("PATCH", "/entries/{eid}")
def edit(req: Req):
    from panko.store import EDITABLE
    fields = req.body.get("fields", {})
    bad = sorted(set(fields) - EDITABLE)
    if bad:
        raise ValueError(f"can't edit {bad}")
    st = _store()
    e = st.get(req.path["eid"])
    if not e:
        raise KeyError(f"no entry {req.path['eid']}")
    st.put({**e, **fields})
    return {"id": e["id"], "changed": sorted(fields), "entry": st.get(e["id"])}


@api("POST", "/entries/activate")
def activate(req: Req):
    from panko.ingest import activate as act
    return {"activated": act(_store(), ids=list(req.body.get("ids", [])))}


@api("POST", "/entries/reject")
def reject(req: Req):
    st = _store()
    ids = list(req.body.get("ids", []))
    done = [i for i in ids if (e := st.get(i)) and e["status"] == "candidate"]
    for i in done:
        st.set_status(i, "retired", why="rejected in the inbox")
    return {"retired": done, "skipped": [i for i in ids if i not in done]}


@api("POST", "/entries/restore")
def restore(req: Req):
    """A rejected word back to the inbox (set-aside entries never reached Anki)."""
    st = _store()
    done = [i for i in req.body.get("ids", []) if (e := st.get(i)) and e["status"] == "retired" and not st.link(i)
            and not e.get("merged_into")]       # a duplicate belongs to the card that was kept
    for i in done:
        st.set_status(i, "candidate")
    return {"restored": done}


@api("GET", "/entries/{eid}/preview")
def preview(req: Req):
    from panko.hub import preview as P
    e = _store().get(req.path["eid"])
    if not e:
        raise KeyError(f"no entry {req.path['eid']}")
    side = req.query.get("side")
    dirs = media_dirs()
    c = P.cards(e, have=lambda name: any((d / name).is_file() for d in dirs))
    if side:        # one side as a document, for an iframe
        i = int(req.query.get("card", 0))
        card = c["cards"][min(i, len(c["cards"]) - 1)] if c["cards"] else {"front": "", "back": ""}
        body = P.inline_images(card[side], dirs)
        return Response(P.page(c["css"], body, req.query.get("theme", "")), media_type="text/html",
                        headers={"Cache-Control": "no-store", "Content-Security-Policy": f"sandbox allow-scripts; {P.CSP}"})
    return {**{k: v for k, v in c.items() if k != "css"}, "cards": [{"name": x["name"]} for x in c["cards"]]}


@api("GET", "/entries/{eid}/evidence")
def entry_evidence(req: Req):
    from panko import evidence
    e = _store().get(req.path["eid"])
    if not e:
        raise KeyError(f"no entry {req.path['eid']}")
    [r] = evidence.lookup([{"ar": e["ar"], "tl": e.get("tl", ""), "tl_alt": e.get("tl_alt", ""), "pos": e.get("pos", ""),
                            "gloss": e.get("gloss", ""), "variety": e["variety"]}])
    r["near"] = [n for n in r["near"] if n["id"] != e["id"]]
    r["same_letters"] = [n for n in r["same_letters"] if n["id"] != e["id"]]
    if r.get("panko") and r["panko"]["id"] == e["id"]:
        r["panko"] = None
    return r


@api("POST", "/entries/{eid}/audio")
def entry_audio(req: Req):
    """The entry's audio: what's missing (free) or, with confirm, generate it (paid, then cached for sync)."""
    from panko.cards import build
    from panko.media import audio
    e = _store().get(req.path["eid"])
    if not e:
        raise KeyError(f"no entry {req.path['eid']}")
    dry = audio.DryRun(prefix=PREFIX)
    build.to_note(e, dry)
    est = {"clips": len(dry.todo), "characters": sum(len(t) for _, t in dry.todo)}
    if not _confirmed(req) or not dry.todo:
        return {"estimate": est}
    return _start("audio", f"Audio for {e['ar']}", lambda job: (build.to_note(e, audio.Narrator(prefix=PREFIX)),
                                                               est)[1], paid=True)


# ---- checks, examples, clashes -------------------------------------------------------------------------------------

@api("POST", "/verify")
def verify(req: Req):
    from panko import checks
    status, apply = req.body.get("status", "candidate"), bool(req.body.get("apply"))
    st = ("candidate", "active") if status == "all" else (status,)

    def run(job: Job):
        m = {v: p.name for p in __import__("panko.providers", fromlist=["chain"]).chain("morph") for v in p.dbs()}
        job.say("analysers: " + (", ".join(f"{v} ({n})" for v, n in m.items()) or "none ready"))
        r = checks.run(_store(), st, apply=apply)
        job.say(f"checked {r['checked']}: {r['fine']} fine, {len(r['doubtful'])} doubtful, {len(r['listed'])} listed; "
                f"{len(r['ungrounded'])} words in no reference" + (f"; tagged {r['tagged']}" if apply else ""))
        return {**r, "analysers": m, "applied": apply}
    return _start("verify", "Check with tools" + (" and tag" if apply else ""), run)


@api("POST", "/examples")
def examples(req: Req):
    from panko import examples as ex
    st = _store()
    status, want = req.body.get("status", "candidate"), int(req.body.get("want") or 1)
    es = ex.todo(st, status, req.body.get("ids") or None, req.body.get("tag", ""), want)
    if not _confirmed(req):
        return {"estimate": ex.estimate(es, st, want) if es else {"entries": 0, "usd": 0, "usd_batch": 0}}
    batch, budget = bool(req.body.get("batch")), _budget(req)

    def run(job: Job):
        r = ex.run(es, _store(), want, batch=batch, budget=budget)
        job.say(f"{r['added']} examples on {r['entries']} of {len(es)} entries; none for {len(r['skipped'])}")
        return r
    return _start("examples", f"Examples for {len(es)} {status} entries", run, paid=True)


def _clash_path() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "work" / "clashes.json"


def _clash_groups(every: bool) -> list[dict]:
    """Clash groups (touching the inbox unless `every`), less the ones you called fine."""
    from panko import clashes
    st = _store()
    groups = clashes.find(st, None if every else [e["id"] for e in st.entries("candidate")])
    return clashes.open_groups(groups, _clash_path())


@api("GET", "/clashes")
def clashes_list(req: Req):
    from panko import clashes
    groups = _clash_groups(bool(req.query.get("all")))
    saved = clashes.load(_clash_path())
    for g in groups:
        g["key"] = clashes.key(g)
    return {"groups": groups[:200], "total": len(groups), "decisions": saved,
            "undecided": len(clashes.undecided(groups, saved)), "fine": len(clashes.fine(_clash_path()))}


CHOICES = ("keep", "gloss", "recognition", "same")


@api("POST", "/clashes/choose")
def clashes_choose(req: Req):
    """Your choice for one card: {"id", "choice": keep | gloss (with "gloss") | recognition | same (with "same"), or
    "" to clear it}. Saved with the model's decisions, marked as yours, so the model leaves it alone."""
    from panko import clashes
    eid, choice = str(req.body.get("id") or ""), req.body.get("choice") or ""
    st = _store()
    if not st.get(eid):
        raise KeyError(f"no entry {eid}")
    saved = clashes.load(_clash_path())
    if not choice:
        saved.pop(eid, None)
    elif choice not in CHOICES:
        raise ValueError(f"choose one of {', '.join(CHOICES)}")
    elif choice == "gloss":
        gloss = str(req.body.get("gloss") or "").strip()
        if not gloss:
            raise ValueError("what should the new gloss be?")
        saved[eid] = {"gloss": gloss, "by": "you"}
    elif choice == "same":
        other = str(req.body.get("same") or "")
        if not st.get(other) or other == eid:
            raise ValueError("the same word as which card?")
        saved[eid] = {"same": other, "drop": f"the same word as {other}", "by": "you"}
    else:
        saved[eid] = {"keep": True, "by": "you"} if choice == "keep" else {"cards": ["recognition"], "note": "", "by": "you"}
    clashes.save(saved, _clash_path())
    return {"decision": saved.get(eid)}


@api("POST", "/clashes/fine")
def clashes_fine(req: Req):
    """A group you're happy with as it is ({"key"}, or with "undo"). Its cards' saved decisions go, so nothing is applied
    to them; the group comes back if a new card joins it."""
    from panko import clashes
    k = str(req.body.get("key") or "")
    if not k:
        raise ValueError("which group?")
    clashes.mark_fine(_clash_path(), k, undo=bool(req.body.get("undo")))
    if not req.body.get("undo"):
        saved = clashes.load(_clash_path())
        clashes.save({i: d for i, d in saved.items() if i not in k.split("|")}, _clash_path())
    return {"fine": len(clashes.fine(_clash_path()))}


@api("POST", "/clashes/decide")
def clashes_decide(req: Req):
    from panko import clashes
    groups = clashes.undecided(_clash_groups(bool(req.body.get("all"))), clashes.load(_clash_path()))
    if not _confirmed(req):
        return {"estimate": clashes.estimate(groups) if groups else {"groups": 0, "usd": 0, "usd_batch": 0}}
    budget = _budget(req)

    def run(job: Job):
        d = clashes.decide(groups, budget=budget)
        clashes.save(clashes.merge(clashes.load(_clash_path()), d), _clash_path())
        job.say(f"{len(groups)} groups decided; look them over, then apply")
        return {"decisions": d}
    return _start("clashes", f"Decide {len(groups)} gloss clashes", run, paid=True)


@api("POST", "/clashes/apply")
def clashes_apply(req: Req):
    """Apply the saved decisions; the ones applied leave the file (choices to keep a card stay)."""
    from panko import clashes
    if req.body.get("decisions"):
        return clashes.apply(_store(), req.body["decisions"])
    saved = clashes.load(_clash_path())
    rep = clashes.apply(_store(), saved)
    clashes.save({i: d for i, d in saved.items() if d.get("keep")}, _clash_path())
    return rep


# ---- pictures ------------------------------------------------------------------------------------------------------

def _picture_cards(status: str, tag: str = "") -> list[dict]:
    from panko.media import choose, pictures
    st, done = _store(), choose.load_decisions()
    return [c for c in pictures.export(st, status=status) if c["id"] not in done
            and (not tag or tag in (st.get(c["id"]) or {}).get("tags", []))]


@api("GET", "/pictures")
def pictures_state(req: Req):
    from panko.config import ROOT
    from panko.media import choose
    status = req.query.get("status", "active")
    cards = _picture_cards(status, req.query.get("tag", ""))
    decisions = choose.load_decisions()
    draws = ROOT / "data" / "pictures" / "drawings.json"
    st = _store()
    pending = [{"id": k, **v, "ar": (st.get(k) or {}).get("ar", ""), "gloss": (st.get(k) or {}).get("gloss", ""),
                "applied": bool((st.get(k) or {}).get("image"))} for k, v in list(decisions.items())[-300:]]
    tags: dict[str, int] = {}
    for c in _picture_cards(status):
        for t in (st.get(c["id"]) or {}).get("tags", []):
            tags[t] = tags.get(t, 0) + 1
    none = sum(1 for e in st.entries(status) if e.get("picture_pref") == "none" and not e.get("image"))
    return {"todo": len(cards), "cards": cards[:60], "ids": [c["id"] for c in cards], "decisions": pending[::-1],
            "tags": sorted(tags.items(), key=lambda x: (-x[1], x[0]))[:80], "none": none,
            "drawings_waiting": len(json.loads(draws.read_text())) if draws.exists() else 0}


@api("POST", "/pictures/none")
def pictures_none(req: Req):
    """Cards that should have no picture (or, with `undo`, go back to Panko deciding). They leave the picture queue."""
    st = _store()
    ids = [str(i) for i in req.body.get("ids") or []][:2000]
    done = []
    for i in ids:
        e = st.get(i)
        if not e:
            continue
        if req.body.get("undo"):
            e.pop("picture_pref", None)
        else:
            e["picture_pref"] = "none"
        st.put(e)
        done.append(i)
    return {"changed": done}


@api("POST", "/pictures/decide")
def pictures_decide(req: Req):
    from panko.media import choose
    status = req.body.get("status", "active")
    cards = _picture_cards(status, req.body.get("tag", ""))
    lim = int(req.body.get("limit") or 0)
    cards = cards[:lim] if lim else cards
    if not _confirmed(req):
        return {"estimate": choose.estimate(cards) if cards else {"cards": 0, "usd": 0, "usd_batch": 0}}
    budget = _budget(req)

    def run(job: Job):
        r = choose.decide(cards, budget=budget)
        s = choose.save_decisions(r["decisions"])
        job.say(f"{len(cards)} cards: {r['counts']}; {s.get('total')} decisions saved")
        w = r["waiting"]
        return {"counts": r["counts"], "waiting": w if isinstance(w, int) else len(w)}
    return _start("pictures", f"Choose pictures for {len(cards)} cards", run, paid=True)


@api("POST", "/pictures/apply")
def pictures_apply(req: Req):
    def run(job: Job):
        from panko.config import ROOT
        from panko.media import choose, pictures
        r = pictures.apply(choose.load_decisions(), store=_store())
        p = ROOT / "data" / "pictures" / "drawings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps({**old, **r["prompts"]}, ensure_ascii=False, indent=1))
        job.say(f"photos {r['photo']}, skips {r['skip']}, drawings waiting {len({**old, **r['prompts']})}, "
                f"failed {len(r['failed'])}")
        return {"photos": r["photo"], "skips": r["skip"], "failed": r["failed"]}
    return _start("pictures-apply", "Download chosen photos", run)


# ---- card design ---------------------------------------------------------------------------------------------------

@api("GET", "/design")
def design_state(req: Req):
    from panko.cards import design as D
    return {"design": D.load(), "default": D.normalise({}), "word": D.WORD_BACK, "phrase": D.PHRASE_BACK,
            "names": D.SECTION_NAMES, "required": sorted(D.REQUIRED), "card_types": D.CARD_TYPES,
            "fonts": list(D.FONTS), "slots": D.EXTRA_SLOTS}


def _sample(eid: str, kind: str):
    st = _store()
    e = st.get(eid) if eid else None
    if not e:
        e = next((x for x in st.entries("active") if x["kind"] == kind and x.get("examples")), None) \
            or next((x for x in st.entries("all") if x["kind"] == kind), None)
    if not e:
        raise KeyError("no card to preview yet: add a source first")
    return e


@api("POST", "/design/preview")
def design_preview(req: Req):
    """A card with a draft design, as a document for the preview frame (nothing is saved)."""
    from panko.cards import design as D
    from panko.hub import preview as P
    draft = D.normalise(req.body.get("design"))
    e = dict(_sample(str(req.body.get("id") or ""), req.body.get("kind") or "word"))
    e["extra"] = {**{x["slot"]: f"Your {x['label'].lower()} for this card." for x in draft["extras"]},
                  **(e.get("extra") or {})}
    dirs = media_dirs()
    c = P.cards(e, have=lambda name: any((d / name).is_file() for d in dirs), design=draft)
    names = [x["name"] for x in c["cards"]]
    i = min(int(req.body.get("card", 0)), max(len(c["cards"]) - 1, 0))
    card = c["cards"][i] if c["cards"] else {"front": "", "back": ""}
    side = "front" if req.body.get("side") == "front" else "back"
    body = P.inline_images(card[side], dirs)
    return Response(P.page(c["css"], body, req.body.get("theme", "")), media_type="text/html",
                    headers={"Cache-Control": "no-store", "X-Panko-Cards": ",".join(names), "X-Panko-Entry": e["id"],
                             "Content-Security-Policy": f"sandbox allow-scripts; {P.CSP}"})


@api("POST", "/design")
def design_save(req: Req):
    """Save the card design to config/hub.toml. It reaches Anki on the next sync (templates and CSS only, so never a
    full sync)."""
    from panko.cards import design as D
    from panko.config import save_choices
    if req.body.get("reset"):
        path = save_choices("cards", {k: None for k in D.DEFAULT})
    else:
        path = save_choices("cards", D.normalise(req.body.get("design")))
    _reload()
    return {"design": D.load(), "path": str(path)}


# ---- picture choices -----------------------------------------------------------------------------------------------

IMAGE_ABOUT = {
    "source": "cropped from the page the word came from", "wikidata": "the Wikidata item's own picture",
    "commons": "Wikimedia Commons", "openverse": "Openverse (open-licence photos)", "pexels": "Pexels (free key)",
    "pixabay": "Pixabay (free key)", "inaturalist": "iNaturalist (animals and plants)",
    "arasaac": "ARASAAC pictograms (personal use only)", "generate": "drawn by an image model when no photo fits (paid)",
}


@api("GET", "/pictures/prefs")
def picture_prefs(req: Req):
    from panko import providers
    from panko.config import settings
    s = settings()
    img, gen = s.get("images", {}), s.get("images", {}).get("generate", {})
    chain = img.get("chain", [])
    rows = []
    for name in chain + [n for n in providers.available("images") if n not in chain]:
        p = providers.get("images", name)
        rows.append({"name": name, "on": name in chain, "ready": bool(p and p.ready()), "about": IMAGE_ABOUT.get(name, ""),
                     "needs": list(getattr(p, "needs", ()) or ())})
    pics = s.get("learner", {}).get("pictures", {})
    return {"providers": rows, "drawings": "generate" in chain, "style": gen.get("style", ""),
            "quality": gen.get("quality", "low"), "model": gen.get("model", ""), "rules": pics.get("rules", []),
            "skip": pics.get("skip", "")}


@api("POST", "/pictures/prefs")
def picture_prefs_save(req: Req):
    from panko import providers
    from panko.config import save_choices
    b = req.body
    known = set(providers.available("images"))
    if "chain" in b:
        chain = [n for n in dict.fromkeys(b["chain"]) if n in known]
        if not chain:
            raise ValueError("keep at least one picture source")
        save_choices("images", {"chain": chain})
    gen = {k: str(b[k]) for k in ("style", "quality") if k in b}
    if gen.get("quality") and gen["quality"] not in ("low", "medium", "high"):
        raise ValueError("quality is low, medium or high")
    if gen:
        save_choices("images.generate", gen)
    pics = {}
    if "rules" in b:
        pics["rules"] = [str(r).strip() for r in b["rules"] if str(r).strip()][:30]
    if "skip" in b:
        pics["skip"] = str(b["skip"]).strip()
    if pics:
        save_choices("learner.pictures", pics)
    _reload()
    return picture_prefs(req)


# ---- voices --------------------------------------------------------------------------------------------------------

@api("GET", "/voices")
def voices_state(req: Req):
    from panko.config import settings
    from panko.media import voices
    s = settings()
    varieties = s.get("learner", {}).get("varieties", [])
    q = req.query
    variety = q.get("variety") if q.get("variety") in varieties else (varieties[0] if varieties else "")
    out = {"ready": voices.ready(), "varieties": varieties, "variety": variety, "filter": voices.filters(variety),
           "in_chain": "elevenlabs" in s.get("audio", {}).get("chain", [])}
    if not out["ready"]:
        return {**out, "chosen": {v: [] for v in varieties}, "voices": [], "more": False}
    if q.get("only") != "list":
        out["chosen"] = voices.chosen(varieties)
    if q.get("source") == "library":
        found = voices.library(gender=q.get("gender", ""), search=q.get("q", ""), accent=q.get("accent", ""),
                               page=int(q.get("page", 0) or 0), variety=variety)
    else:
        found = {"voices": voices.yours(variety, q.get("gender", ""), q.get("q", ""), q.get("accent") == "any"),
                 "more": False}
    return {**out, **found}


@api("POST", "/voices/choose")
def voices_choose(req: Req):
    from panko.media import voices
    r = voices.choose(str(req.body.get("variety", "")), list(req.body.get("picks") or []))
    _reload()
    return r


# ---- sync ----------------------------------------------------------------------------------------------------------

@api("POST", "/sync/plan")
def sync_plan(req: Req):
    def run(job: Job):
        from panko.anki import sync
        p = sync.plan(_store())
        job.say(f"add {len(p['add'])}, update {len(p['update'])}, unchanged {p['unchanged']}; "
                f"{p['audio_clips']} audio clips to generate")
        st = _store()

        def rows(ids):
            return [{"id": i, "ar": e["ar"], "gloss": e.get("gloss", ""), "variety": e["variety"]}
                    for i in ids[:300] if (e := st.get(i))]
        return {**p, "add_count": len(p["add"]), "update_count": len(p["update"]), "add": rows(p["add"]),
                "update": rows(p["update"]), "audio_total": sum(p["audio_chars"].values())}
    return _start("sync-plan", "What a sync would do", run)


@api("POST", "/sync")
def sync_now(req: Req):
    if not _confirmed(req):
        raise ValueError("a sync needs confirm: true (check what it would do first)")

    def run(job: Job):
        from panko.anki import sync
        return sync.sync(_store())
    return _start("sync", "Sync to Anki", run, paid=True)


def exports_dir() -> Path:
    """`[export] dir` in your config, else cache/exports in the Panko folder (packages can be hundreds of MB)."""
    from panko.config import CACHE, settings
    d = settings().get("export", {}).get("dir")
    return Path(d).expanduser() if d else CACHE / "exports"


@api("POST", "/export/apkg")
def export_apkg(req: Req):
    """Active cards as an .apkg to share (a job); the file is then downloaded from /export/file/<name>."""
    from panko.config import settings
    known = settings().get("learner", {}).get("varieties", [])
    varieties = [v for v in req.body.get("varieties") or [] if v in known] or known
    personal = bool(req.body.get("personal"))

    def run(job: Job):
        from panko.anki import apkg
        name = f"panko-{'-'.join(varieties)}-{dt.date.today().isoformat()}.apkg"
        r = apkg.export(exports_dir() / name, varieties, personal, _store())
        job.say(f"{r['notes']} cards, {r['media']} media files, {r['bytes'] / 1e6:.0f} MB"
                + (f"; {r['audio_not_made']} audio clips not made yet were left out" if r["audio_not_made"] else ""))
        return {**r, "name": name}
    return _start("export", "Make an Anki package", run)


async def export_file(request: Request):
    """A package made by /export/apkg, as a download."""
    name = request.path_params["name"]
    p = exports_dir() / name
    if not re.fullmatch(r"panko-[\w-]+\.apkg", name) or not p.is_file():
        return JSONResponse({"error": "no such package"}, 404)
    return FileResponse(p, filename=name, media_type="application/octet-stream")


@api("POST", "/llm/collect")
def llm_collect(req: Req):
    def run(job: Job):
        from panko import llm
        done = llm.collect()
        job.say(f"collected {len(done)} batch answer(s)")
        return {"collected": len(done)}
    return _start("collect", "Collect finished batches", run)


# ---- setup ---------------------------------------------------------------------------------------------------------

@api("GET", "/setup")
def setup_state(req: Req):
    from panko import evidence, setup
    out = {"config": _config_ready(), "presets": _presets(), "profiles": setup.anki_profiles(),
           "defaults": setup.DEFAULTS, "path": str(setup.CONFIG)}
    if out["config"]:
        out["references"] = evidence.references_status()
        out["text"] = setup.CONFIG.read_text()
        try:
            from panko.mcp_server import config_snippet
            out["chat"] = config_snippet()
        except ImportError:
            out["chat"] = ""
    return out


@api("POST", "/setup/preview")
def setup_preview(req: Req):
    from panko import setup
    return {"text": setup.render(req.body.get("answers", {}))}


@api("POST", "/setup")
def setup_write(req: Req):
    from panko import setup
    answers = req.body.get("answers", {})
    if not str(answers.get("language") or "").strip():
        raise ValueError("which language are you learning?")
    p = setup.write_config(answers, force=bool(req.body.get("force")))
    _reload()
    return {"path": str(p)}


@api("POST", "/refs/download")
def refs_download(req: Req):
    def run(job: Job):
        from panko import evidence
        r = evidence.download(force=bool(req.body.get("force")), say=job.say)
        _reload()
        return {"references": r}
    return _start("refs", "Download reference data", run)


@api("POST", "/open")
def open_path(req: Req):
    """Open the config file or the Panko folder in this computer's own app (local hub only)."""
    from panko import setup
    from panko.config import ROOT
    what = {"config": setup.CONFIG, "folder": ROOT}.get(req.body.get("what", ""))
    if not what or not what.exists():
        raise ValueError("nothing to open")
    cmd = ["open", str(what)] if sys.platform == "darwin" else ["xdg-open", str(what)] \
        if sys.platform.startswith("linux") else ["cmd", "/c", "start", "", str(what)]
    subprocess.Popen(cmd)
    return {"opened": str(what)}


# ---- media ---------------------------------------------------------------------------------------------------------

SAFE = re.compile(r"^[\w.\- ]+$")


def media_dirs() -> list[Path]:
    from panko.anki.sync import MEDIA_DIRS
    from panko.config import CACHE, ROOT
    from panko.media import audio, clips
    return list(dict.fromkeys([*MEDIA_DIRS, clips._media(), audio.MEDIA, ROOT / "data" / "media", CACHE / "media"]))


async def media(request: Request):
    """A card's picture or audio by file name, from Panko's media folders only."""
    name = request.path_params["name"]
    if not SAFE.match(name) or name.startswith("."):
        return JSONResponse({"error": "bad name"}, 400)
    for d in media_dirs():
        p = d / name
        if p.is_file():
            return FileResponse(p)
    return JSONResponse({"error": "not found"}, 404)
