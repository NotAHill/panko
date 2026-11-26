"""Work through a source in units, whoever does the reading: the learner's Claude in chat (MCP) or, later, API mode.

A source (a PDF, a folder of page photos, a transcript, an exported deck, a lesson recording) is registered once and
split into units: PDF pages, image files, transcript chunks, deck rows or stretches of a recording. A recording is
transcribed first (speech-to-text with word times, `transcribe`); at ingest each item the recording says gets a
native clip (panko.media.clips) that the card plays instead of a synthetic voice. For each unit the reader submits one result, the unit's items, each already checked
and given a picture plan (the `extract`, `check` and `pictures-plan` prompts in one pass). Results wait in
`data/work/<source>/units/<unit>.json` until `ingest_source` merges them into the store, so a book can be done over
many chats and nothing reaches the store before it has been validated and checked for duplicates.

Ingest, per item:
- `known` items (or ones whose letters, POS and transliteration match an entry) become sightings of that entry, and
  the source's sentences are added to it;
- a new item with the same letters as an entry but other consonants is a homograph (gets a shadda where the
  transliteration doubles the middle consonant) and becomes its own candidate;
- a new item close to an existing entry (near spelling, same gloss) is held back with the matches, unless it says
  `distinct: true` or names the entry with `known_id`; the reader resubmits held items once decided;
- everything else becomes a candidate in the inbox, with the verdict applied (panko.ingest.verify).
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from panko import lang
from panko.config import ROOT
from panko.prompts.schemas import CONFIDENCE, ITEM_FIELDS, VERDICT

WORK = ROOT / "data" / "work"
PAGES = ROOT / "cache" / "pages"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}
TEXT_EXT = {".txt", ".md", ".srt", ".vtt"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".oga", ".opus", ".flac", ".aac", ".mp4", ".mov", ".webm", ".mkv"}
CHUNK_SECS = 180        # seconds of a recording per unit
PAUSE = 1.5             # a silence this long starts a new transcript line
CHUNK_LINES = 60
DECK_ROWS = 25          # rows of an old deck per unit (one `deck` answer, well under the output limit)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "source"


def _abs(p: str | Path) -> Path:
    from panko.config import inside
    return inside(p)


# ---- sources -----------------------------------------------------------------------------------------------------

def _reg_path() -> Path:
    return WORK / "sources.json"


def sources() -> dict[str, dict]:
    p = _reg_path()
    return json.loads(p.read_text()) if p.exists() else {}


def _save_sources(reg: dict):
    _reg_path().parent.mkdir(parents=True, exist_ok=True)
    _reg_path().write_text(json.dumps(reg, ensure_ascii=False, indent=1))


def source(sid: str) -> dict:
    reg = sources()
    if sid not in reg:
        raise KeyError(f"no source {sid!r}; registered: {', '.join(reg) or 'none'} (add one with add_source)")
    return reg[sid]


def add_source(path: str, kind: str, title: str, sid: str = "", date: str = "", trust: int = 70, tag: str = "",
               page_offset: int = 0, first: int = 1, last: int = 0, tracks: list[str] = (), speakers: list[str] = (),
               learner: str = "", transcript: str = "") -> dict:
    """Register a source. `kind`: textbook | teacher-sheet | lesson | media | notes (free text, stored on sightings).
    PDFs: `page_offset` = PDF page − printed page; `first`/`last` limit the PDF pages worked on.
    Recordings: `tracks` = more files of the same session recorded separately (each mic its own file), `speakers` =
    a name per track, or per diarized speaker when there's one track; `learner` = the name that is the learner, whose
    voice is never used for a clip; `transcript` = a speech-to-text JSON you already have (ElevenLabs format), so
    nothing is paid for. Without one, run `transcribe` before working through it."""
    p = _abs(path)
    if not p.exists():
        raise FileNotFoundError(f"{p} does not exist")
    sid = sid or slug(title)
    s = {"id": sid, "kind": kind, "title": title, "date": date, "trust": trust, "tag": tag or sid,
         "path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), "added": _now()}
    if p.suffix.lower() == ".pdf":
        info = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, check=True).stdout
        n = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
        last = min(last or n, n)
        s |= {"type": "pdf", "page_offset": page_offset, "units": [f"p{i:03d}" for i in range(first, last + 1)]}
    elif p.is_dir():
        files = sorted(f.name for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT)
        if not files:
            raise ValueError(f"{p} has no images: a folder is read as photos of pages (jpg, png…). For one file, "
                             "give the file itself")
        s |= {"type": "images", "files": files, "units": [f"i{i:03d}" for i in range(1, len(files) + 1)]}
    elif p.suffix.lower() == ".json":
        from panko.ingest.decks import rows
        title, rs = rows(p)
        if not rs:
            raise ValueError(f"{p} has no deck rows (expected an exported deck: {{\"deck\", \"notes\"}})")
        rp = WORK / sid / "rows.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(rs, ensure_ascii=False))
        s |= {"type": "deck", "deck": title, "rows": len(rs),
              "units": [f"d{i:03d}" for i in range(1, (len(rs) - 1) // DECK_ROWS + 2)]}
    elif p.suffix.lower() in AUDIO_EXT:
        paths = [p, *(_abs(t) for t in tracks)]
        for t in paths:
            if not t.exists():
                raise FileNotFoundError(f"{t} does not exist")
        names = list(speakers)
        s |= {"type": "audio", "learner": learner, "units": [],
              "tracks": [{"path": str(t), "speaker": names[i] if len(paths) > 1 and i < len(names) else ""}
                         for i, t in enumerate(paths)],
              "speakers": names if len(paths) == 1 else [], "duration": round(sum(duration(t) for t in paths)
                                                                              / len(paths), 1)}
        if transcript:
            if len(paths) > 1:
                raise ValueError("a ready transcript works for a single recording; transcribe several tracks instead")
            _save_transcript(sid, s, [json.loads(_abs(transcript).read_text())], engine="given")
    elif p.suffix.lower() in TEXT_EXT:
        n = len(p.read_text(encoding="utf-8").splitlines())
        s |= {"type": "text", "units": [f"c{i:03d}" for i in range(1, n // CHUNK_LINES + 2)]}
    else:
        raise ValueError(f"can't split {p.suffix} files yet: use a PDF, a folder of images, a text transcript, an "
                         "exported deck (.json) or a recording")
    reg = sources()
    reg[sid] = s
    _save_sources(reg)
    return s


# ---- recordings ----------------------------------------------------------------------------------------------------

def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip() or 0)


def _transcript_path(sid: str) -> Path:
    return WORK / sid / "transcript.json"


def transcript(sid: str) -> dict:
    p = _transcript_path(sid)
    if not p.exists():
        raise ValueError(f"{sid} isn't transcribed yet: run `panko work transcribe {sid}` (paid speech-to-text)")
    return json.loads(p.read_text())


def _save_transcript(sid: str, s: dict, outs: list[dict], engine: str) -> None:
    """Speech-to-text answers (one per track) → WORK/<sid>/transcript.json: every word with its time, speaker and
    track, in time order; the source gets one unit per CHUNK_SECS."""
    words, dur = [], s.get("duration") or 0
    for t, out in enumerate(outs):
        for w in out.get("words", []):
            if w.get("type", "word") != "word" or w.get("start") is None:
                continue
            spk = s["tracks"][t]["speaker"] if len(outs) > 1 else w.get("speaker_id", "")
            if len(outs) == 1 and s.get("speakers") and re.fullmatch(r"speaker_\d+", spk or ""):
                i = int(spk.split("_")[1])
                spk = s["speakers"][i] if i < len(s["speakers"]) else spk
            words.append({"text": w["text"], "start": w["start"], "end": w.get("end", w["start"]), "speaker": spk or "",
                          "track": t})
        dur = max(dur, out.get("audio_duration_secs") or 0)
    words.sort(key=lambda w: (w["start"], w["track"]))
    dur = max(dur, words[-1]["end"] if words else 0)
    _transcript_path(sid).parent.mkdir(parents=True, exist_ok=True)
    _transcript_path(sid).write_text(json.dumps({"engine": engine or outs[0].get("engine", ""), "duration": dur,
                                                 "language": outs[0].get("language_code", ""), "words": words},
                                                ensure_ascii=False))
    s["duration"] = round(dur, 1)
    s["units"] = [f"a{i:03d}" for i in range(1, int(dur // CHUNK_SECS) + 2)] if words else []


def transcribe(sid: str, stt=None) -> dict:
    """Speech-to-text for a recording (paid: the first ready provider in the [stt] chain). Returns the source."""
    from panko import providers
    reg = sources()
    s = source(sid)
    if s["type"] != "audio":
        raise ValueError(f"{sid} isn't a recording")
    stt = stt or next((p for p in providers.chain("stt") if p.ready()), None)
    if stt is None:
        raise RuntimeError("no speech-to-text provider is ready: add ELEVENLABS_API_KEY to .env (see [stt] in config)")
    outs = [stt.transcribe(Path(t["path"]), diarize=len(s["tracks"]) == 1) for t in s["tracks"]]
    _save_transcript(sid, s, outs, engine=outs[0].get("engine", stt.name))
    reg[sid] = s
    _save_sources(reg)
    return s


def _clock(t: float) -> str:
    m, sec = divmod(int(t), 60)
    return f"{m}:{sec:02d}"


def transcript_lines(words: list[dict]) -> list[str]:
    """Words → lines "[m:ss] speaker: text", a new line when the speaker changes or after a pause."""
    lines, cur, last = [], None, None
    for w in words:
        if cur is None or w["speaker"] != cur["speaker"] or w["start"] - last > PAUSE:
            if cur:
                lines.append(cur)
            cur = {"start": w["start"], "speaker": w["speaker"], "words": []}
        cur["words"].append(w["text"])
        last = w["end"]
    if cur:
        lines.append(cur)
    return [f"[{_clock(c['start'])}] " + (f"{c['speaker']}: " if c["speaker"] else "") + " ".join(c["words"])
            for c in lines]


def book_page(s: dict, unit: str) -> int | None:
    if s["type"] != "pdf":
        return None
    return int(unit[1:]) - s.get("page_offset", 0)


def page(sid: str, unit: str, dpi: int = 110) -> dict:
    """One unit to read: {unit, page (printed page number), image (path or None), text}."""
    s = source(sid)
    if not s["units"]:
        raise ValueError(f"{sid} has no units yet: transcribe it first (`panko work transcribe {sid}`)")
    if unit not in s["units"]:
        raise KeyError(f"{sid} has no unit {unit!r} (units run {s['units'][0]}…{s['units'][-1]})")
    p = _abs(s["path"])
    image, text = None, ""
    if s["type"] == "audio":
        i = int(unit[1:]) - 1
        lo, hi = i * CHUNK_SECS, (i + 1) * CHUNK_SECS
        ws = [w for w in transcript(sid)["words"] if lo <= w["start"] < hi]
        return {"source": sid, "unit": unit, "page": None, "image": None, "text": "\n".join(transcript_lines(ws)),
                "start": lo, "end": hi}
    if s["type"] == "pdf":
        n = int(unit[1:])
        out = PAGES / sid / f"{unit}.png"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(n), "-l", str(n), "-png", "-singlefile", str(p),
                            str(out.with_suffix(""))], check=True)
        image = out
        text = subprocess.run(["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(p), "-"],
                              capture_output=True, text=True).stdout
    elif s["type"] == "images":
        image = p / s["files"][int(unit[1:]) - 1]
    elif s["type"] == "pack":          # cards from a Panko pack (panko.library): already submitted, shown as they are
        r = result(sid, unit) or {"items": []}
        text = "\n".join(json.dumps({k: it.get(k, "") for k in ("ar", "tl", "gloss")}, ensure_ascii=False)
                         for it in r["items"])
        return {"source": sid, "unit": unit, "page": None, "image": None, "text": text}
    elif s["type"] == "deck":
        i = (int(unit[1:]) - 1) * DECK_ROWS
        rs = json.loads((WORK / sid / "rows.json").read_text())[i:i + DECK_ROWS]
        text = "\n".join(json.dumps(deck_row(r), ensure_ascii=False) for r in rs)
        return {"source": sid, "unit": unit, "page": None, "image": None, "text": text, "rows": rs}
    else:
        lines = p.read_text(encoding="utf-8").splitlines()
        i = (int(unit[1:]) - 1) * CHUNK_LINES
        text = "\n".join(lines[i:i + CHUNK_LINES])
    return {"source": sid, "unit": unit, "page": book_page(s, unit), "image": image, "text": text.strip()}


def deck_row(r: dict) -> dict:
    """A deck row as the `deck` prompt reads it."""
    out = {"id": str(r["nid"]), "ar": r["ar"], "tl": r["tl"], "en": r["en"], "picture_hint": r["hint"],
           "studied": r["studied"]}
    return out | ({"fields": r["fields"]} if r.get("fields") else {})


# ---- results -----------------------------------------------------------------------------------------------------

def _unit_path(sid: str, unit: str) -> Path:
    return WORK / sid / "units" / f"{unit}.json"


def result(sid: str, unit: str) -> dict | None:
    p = _unit_path(sid, unit)
    return json.loads(p.read_text()) if p.exists() else None


def _save_result(sid: str, unit: str, r: dict):
    p = _unit_path(sid, unit)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(r, ensure_ascii=False, indent=1))


def state(sid: str) -> dict[str, str]:
    """unit -> todo | submitted | held | ingested."""
    out = {}
    for u in source(sid)["units"]:
        r = result(sid, u)
        out[u] = r["status"] if r else "todo"
    return out


def next_work(sid: str, n: int = 5) -> list[str]:
    return [u for u, st in state(sid).items() if st == "todo"][:n]


def pending(sid: str) -> dict:
    st = state(sid)
    counts = {k: sum(1 for v in st.values() if v == k) for k in ("todo", "submitted", "held", "ingested")}
    held = []
    for u, v in st.items():
        if v == "held":
            held += [{"unit": u, **h} for h in result(sid, u).get("held", [])]
    s = source(sid)
    extra = {"transcribe_first": True} if s["type"] == "audio" and not s["units"] else {}
    return {"source": sid, "units": len(st), **counts, **extra,
            "to_ingest": [u for u, v in st.items() if v == "submitted"], "held": held,
            "next": [u for u, v in st.items() if v == "todo"][:5]}


# ---- the submission schema -----------------------------------------------------------------------------------------

def _loose(node: dict, required: list[str]) -> dict:
    return {**node, "required": required}


EXAMPLE = {"type": "object", "properties": {k: {"type": "string"} for k in ("ar", "tl", "en", "source")},
           "required": ["ar", "en"], "additionalProperties": False}
RELATED = {"type": "object", "properties": {k: {"type": "string"} for k in ("ar", "tl", "meaning")},
           "required": ["ar", "meaning"], "additionalProperties": False}
_VERDICT_PROPS = {**VERDICT["properties"], "fix": {"type": "object", "additionalProperties": {"type": "string"}}}
PICTURE = {"type": "object", "properties": {"choice": {"type": "string", "enum": ["photo", "draw", "skip"]},
                                            "query": {"type": "string"}, "prompt": {"type": "string"},
                                            "reason": {"type": "string"}},
           "required": ["choice"], "additionalProperties": False}
ITEM = {"type": "object", "additionalProperties": False, "required": ["kind", "ar", "gloss"],
        "properties": {**ITEM_FIELDS, "examples": {"type": "array", "items": EXAMPLE},
                       "related": {"type": "array", "items": RELATED},
                       "check": _loose(CONFIDENCE, []),
                       "page": {"type": ["integer", "string"]}, "known": {"type": "boolean"},
                       "region": {"type": "string"},
                       "cards": {"type": "array", "items": {"type": "string", "enum": ["recognition", "production"]}},
                       "origin": {"type": "object"},
                       "known_id": {"type": "string"}, "distinct": {"type": "boolean"},
                       "verdict": {"type": "object", "properties": _VERDICT_PROPS, "required": ["verdict"],
                                   "additionalProperties": False},
                       "picture": PICTURE}}
UNIT_SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": ITEM}}, "required": ["items"],
               "additionalProperties": False}


def validate(data: dict) -> list[str]:
    """Errors that would stop a unit result from being stored ([] when it's fine)."""
    from jsonschema import Draft202012Validator
    errs = [f"{'.'.join(map(str, e.absolute_path)) or 'result'}: {e.message}"
            for e in Draft202012Validator(UNIT_SCHEMA).iter_errors(data)]
    if errs:
        return errs[:25]
    for i, it in enumerate(data["items"]):
        where = f"items.{i} ({it['ar']})"
        if not lang.in_target(it["ar"], it.get("variety")):
            errs.append(f"{where}: `ar` must be in {lang.label(it.get('variety'))}")
        if it.get("known") or it.get("known_id"):
            continue
        if not it.get("tl") and lang.romanised():
            errs.append(f"{where}: a new item needs `tl`")
        if "verdict" not in it:
            errs.append(f"{where}: a new item needs a `verdict` (the check step); known items set `known: true`")
        elif it["verdict"]["verdict"] == "fix" and not it["verdict"].get("fix"):
            errs.append(f"{where}: verdict `fix` needs `fix`: {{field: corrected value}}")
        if it.get("verdict", {}).get("verdict") not in ("drop", None) and "picture" not in it:
            errs.append(f"{where}: a new item needs a `picture` plan (choice skip is fine)")
    return errs


def _normalise(data: dict) -> dict:
    from panko.evidence import norm_pos
    for it in data.get("items", []):
        if isinstance(it, dict) and "pos" in it:
            it["pos"] = norm_pos(it["pos"])
    return data


def submit(sid: str, unit: str, data: dict | str) -> dict:
    """Validate and store one unit's result (replacing an earlier one). Bounced with the errors if invalid."""
    s = source(sid)
    if unit not in s["units"]:
        raise KeyError(f"{sid} has no unit {unit!r}")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return {"ok": False, "errors": [f"not valid JSON: {e}"]}
    data = _normalise(data)
    errs = validate(data)
    if errs:
        return {"ok": False, "errors": errs, "hint": "fix these and submit the whole unit again"}
    _save_result(sid, unit, {"unit": unit, "status": "submitted", "submitted": _now(), "items": data["items"]})
    items = data["items"]
    known = sum(1 for i in items if i.get("known") or i.get("known_id"))
    return {"ok": True, "unit": unit, "items": len(items), "known": known, "new": len(items) - known,
            "next": next_work(sid, 3)}


# ---- ingest --------------------------------------------------------------------------------------------------------

def _verdict_record(it: dict) -> dict:
    from panko.ingest.verify import item_key
    v = it.get("verdict") or {}
    return {"key": item_key(it), **{k: v.get(k, "") for k in ("verdict", "region", "register", "usual_word",
                                                             "learner_note", "summary", "confidence")},
            "evidence": v.get("evidence", []), "fix": v.get("fix") or {}}


def _group(it: dict) -> tuple:
    from panko.dedupe import skel
    from panko.store.normalize import strip_article
    k = strip_article(it["ar"])
    return (it["variety"], k, "phrase") if it["kind"] == "phrase" else (it["variety"], k, it.get("pos", ""),
                                                                       skel(it.get("tl")))


def _add_examples(dst: dict, src: dict):
    from panko.store.normalize import bare
    for ex in src.get("examples", []):
        if all(bare(ex.get("ar", "")) != bare(y.get("ar", "")) for y in dst.get("examples", [])):
            dst.setdefault("examples", []).append(ex)


def _set_aside(store, it: dict, unit: str, rep: dict, pos_compatible, same_word) -> dict | None:
    """A word you already set aside, seen again: a duplicate's sighting goes to the card that was kept, and a word you
    rejected stays rejected (it gets the sighting, and doesn't come back to the inbox). None when it's neither."""
    gone = next((e for e in store.find_all(it["ar"], it["variety"]) if e["status"] == "retired"
                 and pos_compatible(it.get("pos"), e.get("pos")) and same_word(it, e)), None)
    if not gone:
        return None
    m = re.match(r"same as (\S+)", gone.get("merged_into") or "")
    if m:
        kept = store.get(m.group(1))
        return kept if kept and kept["status"] != "retired" else None
    rep["rejected_again"].append({"unit": unit, "id": gone["id"], "ar": gone["ar"], "gloss": gone.get("gloss", "")})
    return gone


def ingest_source(sid: str, store=None, units: list[str] | None = None) -> dict:
    """Merge submitted unit results into the store (see the module docstring). Returns what happened."""
    from panko.dedupe import Index, add_shadda, pos_compatible, same_word
    from panko.ingest import ingest
    from panko.ingest.verify import apply
    from panko.store import Store

    store = store or Store()
    s = source(sid)
    variety0 = lang.default_variety()
    todo = [u for u, st in state(sid).items() if st in ("submitted", "held") and (not units or u in units)]
    index = Index(store.entries(None))
    rep = {"source": sid, "units": todo, "new": 0, "known": 0, "dropped": 0, "merged": 0, "homographs": [],
           "held": [], "unresolved_known": [], "rejected_again": []}
    known, new, groups, held_by_unit, plans = {}, [], {}, {u: [] for u in todo}, {}
    for u in todo:
        bp = book_page(s, u)
        for raw in result(sid, u)["items"]:
            it = {**raw, "variety": raw.get("variety") or variety0}
            if it.get("page") in (None, "") and bp is not None:
                it["page"] = bp
            if it.get("page") not in (None, ""):
                it["tags"] = [*it.get("tags", []), f"{s['tag']}::page-{it['page']}"]
            ex_src = f"{s['title']}" + (f" p. {it['page']}" if it.get("page") not in (None, "") else "")
            # the prompts mark a sentence taken from the source as "source": name it (title, page)
            it["examples"] = [{**ex, "source": ex_src if ex.get("source", "") in ("", "source") else ex["source"]}
                              for ex in it.get("examples", [])]
            # known: a sighting of the entry it names (or the one with its letters, POS and consonants)
            hit = None
            if it.get("known_id") or it.get("known"):
                hit = store.get(it["known_id"]) if it.get("known_id") else next(
                    (e for e in store.find_all(it["ar"], it["variety"]) if e["status"] != "retired"
                     and same_word(it, e)), None)
                if not hit:
                    rep["unresolved_known"].append({"unit": u, "ar": it["ar"], "gloss": it.get("gloss", "")})
                    held_by_unit[u].append({"ar": it["ar"], "gloss": it.get("gloss", ""), "matches": [], "item": raw,
                                            "why": "marked known, but no entry matches: give the right `known_id`, "
                                                   "or make it a new item with a verdict and picture"})
                    continue
            if not hit:
                if (it.get("verdict") or {}).get("verdict") == "drop":
                    rep["dropped"] += 1
                    continue
                if not it.get("pack"):            # a pack's card was checked where it was made: keep its check
                    from panko.ingest.verify import item_key
                    it = apply([it], {item_key(it): _verdict_record(it)})[0]
                same = [e for e in store.find_all(it["ar"], it["variety"]) if e["status"] != "retired"
                        and pos_compatible(it.get("pos"), e.get("pos"))]
                hit = next((e for e in same if same_word(it, e)), None)
                if not hit:
                    hit = _set_aside(store, it, u, rep, pos_compatible, same_word)
                if not hit and same:
                    it["ar"] = add_shadda(it["ar"], it.get("tl", ""))
                    it["homograph"] = True
                    rep["homographs"].append(f"{it['ar']} {it.get('tl', '')} '{it.get('gloss', '')}' ≠ "
                                             + ", ".join(f"{e['id']} {e['ar']} {e.get('tl', '')}" for e in same))
            if hit:
                k = hit["id"]
                item = {"kind": hit["kind"], "variety": hit["variety"], "ar": hit["ar"], "entry_id": k,
                        "role": "taught", "examples": it.get("examples", [])}
                if it.get("pack"):                # your card stays yours: a pack only fills an empty picture
                    item |= {"role": "pack", "origin": it["origin"]}
                    if it.get("image") and not hit.get("image") and hit.get("picture_pref") != "none":
                        store.put({**store.get(k), "image": it["image"]})
                if k in known:
                    _add_examples(known[k], item)
                else:
                    known[k] = item
                continue
            g = ("pack", it["origin"]["id"]) if it.get("pack") else _group(it)   # a pack's cards are distinct already
            if g in groups:
                _add_examples(groups[g], it)
                rep["merged"] += 1
                continue
            if not it.get("homograph") and not it.get("distinct"):
                near = index.near(it)
                if near:
                    held_by_unit[u].append({"ar": it["ar"], "tl": it.get("tl", ""), "gloss": it.get("gloss", ""),
                                            "matches": near, "item": raw, "why": "close to an entry you have: "
                                            "resubmit it with `known_id` if it's the same word, or `distinct: true` "
                                            "if it isn't"})
                    continue
            groups[g] = it
            it["role"] = "pack" if it.get("pack") else "taught"
            new.append(it)
            pic = it.get("picture")
            if pic and pic.get("choice") != "skip":
                plans[f"{it['ar']}|{it.get('gloss', '')}"] = {k: pic.get(k, "") for k in ("choice", "query", "prompt",
                                                                                       "reason")}
    src = {"id": s["id"], "kind": s["kind"], "tag": s["tag"], "title": s["title"], "date": s.get("date", ""),
           "path": s["path"], "trust": s.get("trust", 70)}
    if new:
        from panko import checks
        rep["morph_doubtful"] = checks.flag(new)    # items of a variety with an analyser ([morph])
    if known or new:
        r = ingest({"source": src, "items": [*known.values(), *new]}, store)
        rep["new"], rep["known"] = len(r["new"]), len(r["known"])
    if s["type"] == "audio" and (known or new):
        rep["clips"] = _clips(s, [*known.values(), *new])
    if plans:
        p = WORK / sid / "pictures.json"
        old = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps({**old, **plans}, ensure_ascii=False, indent=1))
    for u in todo:
        r = result(sid, u)
        r["held"] = held_by_unit[u]
        r["status"] = "held" if r["held"] else "ingested"
        if r["held"]:
            r["items"] = [h["item"] for h in r["held"]]
        r["ingested"] = _now()
        _save_result(sid, u, r)
        rep["held"] += [{"unit": u, **{k: v for k, v in h.items() if k != "item"}} for h in r["held"]]
    return rep


def _clips(s: dict, items: list[dict]) -> dict:
    """Native clips of what the recording says: each item's headword and its sentences from this recording. A clip is
    never cut from the learner's voice; text already clipped keeps its first clip."""
    from panko.media import clips
    words = transcript(s["id"])["words"]
    rep = {"cut": 0, "kept": 0, "not_found": []}
    for it in items:
        texts = [it["ar"].rstrip(".؟?!")] + [ex["ar"] for ex in it.get("examples", [])
                                             if ex.get("source", "").startswith(s["title"])]
        for i, t in enumerate(texts):
            had = clips.lookup(t)
            got = had or clips.clip(t, words, s["tracks"], s["title"], avoid=s.get("learner", ""))
            if had:
                rep["kept"] += 1
            elif got:
                rep["cut"] += 1
            elif i == 0:
                rep["not_found"].append(it["ar"])
    return rep


def decide(sid: str, unit: str, ar: str, known_id: str = "", distinct: bool = False) -> dict:
    """Settle a held item: it's entry `known_id`, or a `distinct` new word. The unit goes back to `submitted`."""
    from panko.store.normalize import bare
    if bool(known_id) == bool(distinct):
        raise ValueError("give either known_id or distinct")
    r = result(sid, unit)
    if not r or r["status"] != "held":
        raise ValueError(f"{sid} {unit} has nothing held")
    hit = [it for it in r["items"] if bare(it["ar"]) == bare(ar)]
    if not hit:
        raise KeyError(f"{ar} isn't held in {unit}; held: {', '.join(it['ar'] for it in r['items'])}")
    for it in hit:
        if known_id:
            it.update(known_id=known_id)
            for k in ("verdict", "picture", "distinct"):
                it.pop(k, None)
        else:
            it["distinct"] = True
    r["status"] = "submitted"
    _save_result(sid, unit, r)
    return {"unit": unit, "decided": [it["ar"] for it in hit], "as": known_id or "distinct"}


def plans(sid: str | None = None) -> dict:
    """Picture plans saved by ingest, for the review page."""
    out = {}
    for p in sorted(WORK.glob(f"{sid or '*'}/pictures.json")):
        out |= json.loads(p.read_text())
    return out
