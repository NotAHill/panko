"""Panko packs: a deck as one file that another Panko can import and keep building on (docs/SPEC-library.md).

`build` writes `<id>-v<N>.panko.zip` from your cards:
- `pack.json`: what it is (id, version, title, language, varieties, counts);
- `entries.jsonl`: one card per line, without where it came from;
- `media/`: pictures; `audio/`: the audio already made, with each clip's note so sync finds it;
- `credits.json`: who made each picture, under which licence.

Never in a pack: MyNotes, sources, personal or Panko tags, the check's evidence and summary (they can name a
teacher), clips cut from your recordings, doubtful cards.

`publish` builds the same pack for the public library, after the checks that make it safe to share with
strangers: photos with a licence Panko can't read lose their picture, sentences from private sources (lessons,
teacher sheets, decks of unknown licence) are left out, and names from those sources are looked for in the card
text. It also writes the `.apkg` built from the pack, the library's index entry and a report of what was left out.
Uploading stays a manual step.

`decks` reads the library's `index.json` (`[library] index`: a URL or a file) and says which decks fit this Panko and
which you have; `get` downloads a deck's pack, checks its sha256, and imports it.

`import_pack` registers the pack as a work source of type `pack` whose units (25 cards each) are already
submitted, then runs the normal ingest. So a word you have keeps your card (and gains the pack's real sentences, and
its picture if yours has none), a near-duplicate is held for you, a word you set aside stays aside, and new cards
are written whole under your own ids. Each card remembers where it came from (`origin`: pack, id, version, hash).
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from panko import work
from panko.store import Store

FORMAT = 1
UNIT = 25                     # cards per unit, as for deck rows
WRITTEN = "written by Panko"
NATIVE = "_panko_native_"     # clips cut from the learner's recordings: never shared
KEEP = {"kind", "variety", "ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "gender", "plural", "root", "pattern",
        "form", "present", "imperative", "masdar", "examples", "related", "notes", "usage", "literal", "tags", "cards",
        "image", "ar_prompt", "ar_bare", "region", "check"}


def out_dir() -> Path:
    """`[export] dir` in your config, else cache/exports (packs can be hundreds of MB)."""
    from panko.config import CACHE, settings
    d = settings().get("export", {}).get("dir")
    return Path(d).expanduser() if d else CACHE / "exports"


def pictures_dir() -> Path:
    """Where imported pictures go: beside your own."""
    from panko.config import ROOT
    return ROOT / "data" / "media"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def card(e: dict, public: list[str] | None = None) -> dict:
    """An entry as it goes in a pack: its own fields only, nothing that says where it came from.

    With `public` (publishing), only sentences written by Panko or from a public source are kept, and a public
    source keeps its name, as attribution."""
    out = {k: v for k, v in e.items() if k in KEEP and v not in (None, "", [], {})}
    out["id"] = e["id"]
    out["tags"] = [t for t in e.get("tags", []) if not t.startswith(("src::", "panko::"))]
    exs = []
    for x in e.get("examples", []):
        src = x.get("source") or ""
        if WRITTEN in src:
            src = WRITTEN
        elif public is not None and is_public(src, public):
            pass
        elif public is not None:
            continue
        else:
            src = ""
        exs.append({**{k: v for k, v in x.items() if k not in ("source", "audio")}, "source": src})
    out["examples"] = exs
    if e.get("check"):
        out["check"] = {k: e["check"][k] for k in ("verdict", "register", "usual_word") if e["check"].get(k)}
    return out


def digest(c: dict) -> str:
    """What the pack gave for a card, so a later version can tell the learner's edits from its own."""
    return hashlib.sha1(json.dumps({k: v for k, v in c.items() if k != "id"}, sort_keys=True,
                                   ensure_ascii=False).encode()).hexdigest()[:16]


def _media(entries: list[dict]) -> tuple[dict[str, Path], dict[str, Path], int]:
    """({picture name: file}, {audio name: file}, audio not made yet) for these cards, as sync would render them."""
    from panko.anki.apkg import MEDIA_REF, _Made
    from panko.anki.sync import MEDIA_DIRS
    from panko.cards import build as B
    from panko.media import audio
    narrator, used = _Made(personal=False), set()
    for e in entries:
        n = B.to_note(e, narrator)
        used |= {a or b for a, b in MEDIA_REF.findall(" ".join(n["fields"].values()))}
    used = {u for u in used if not u.startswith(NATIVE)}
    sounds = {f.name: f for f in audio.MEDIA.glob("*.mp3") if f.name in used} if audio.MEDIA.exists() else {}
    pics = {}
    for d in MEDIA_DIRS:
        if d.exists() and d != audio.MEDIA:
            pics |= {f.name: f for f in d.iterdir() if f.name in used and f.name not in sounds}
    return pics, sounds, narrator.missing


def _select(store: Store, varieties: list[str] | None, tag: str) -> tuple[list[dict], list[dict]]:
    """(active cards of these varieties with this tag, the doubtful ones among them, left out)."""
    es = [e for e in store.entries("active") if (not varieties or e["variety"] in varieties)
          and (not tag or tag in e.get("tags", []))]
    doubtful = [e for e in es if "panko::doubtful" in e.get("tags", [])]
    es = [e for e in es if e not in doubtful]
    if not es:
        raise ValueError("no active cards to put in it")
    return es, doubtful


def _slug(pack_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,47}", pack_id):
        raise ValueError("a pack id is a short slug: lowercase letters, digits and dashes (e.g. darija-peace-corps)")


def _meta(pack_id: str, version: int, title: str, description: str, cards: list[dict], pics: dict, sounds: dict) -> dict:
    from panko import lang
    from panko.config import settings
    L = settings().get("learner", {})
    return {"format": FORMAT, "id": pack_id, "version": version, "title": title, "description": description,
            "language": L.get("language", ""), "varieties": sorted({c["variety"] for c in cards}),
            "romanised": lang.romanised(), "panko": _panko_version(), "licence": text_licence(), "created": _now(),
            "counts": {"words": sum(c["kind"] == "word" for c in cards),
                       "phrases": sum(c["kind"] == "phrase" for c in cards),
                       "pictures": len(pics), "audio": len(sounds)}}


def _panko_version() -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("panko")
    except PackageNotFoundError:
        return ""


def _write(out: Path, meta: dict, cards: list[dict], pics: dict[str, Path], sounds: dict[str, Path]) -> None:
    """The pack file itself, written through a `.part` file so a half-written pack never has the real name."""
    out.parent.mkdir(parents=True, exist_ok=True)
    need = sum(f.stat().st_size for f in [*pics.values(), *sounds.values()]) + 20_000_000
    if shutil.disk_usage(out.parent).free < need:
        raise RuntimeError(f"the pack needs about {need // 1_000_000:,} MB free in {out.parent}: set [export] dir to a "
                           "folder on a bigger disk")
    credits = {c["image"]["file"]: c["image"].get("credit", "") for c in cards
               if isinstance(c.get("image"), dict) and c["image"].get("file") in pics}
    tmp = out.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr("pack.json", json.dumps(meta, ensure_ascii=False, indent=1), zipfile.ZIP_DEFLATED)
        z.writestr("entries.jsonl", "\n".join(json.dumps(c, ensure_ascii=False) for c in cards) + "\n",
                   zipfile.ZIP_DEFLATED)
        z.writestr("credits.json", json.dumps({"pictures": credits, "audio": "speech synthesis (ElevenLabs)"
                                               if sounds else ""}, ensure_ascii=False, indent=1), zipfile.ZIP_DEFLATED)
        for name, f in pics.items():
            z.write(f, f"media/{name}", zipfile.ZIP_STORED)       # pictures and mp3 are compressed already
        for name, f in sounds.items():
            z.write(f, f"audio/{name}", zipfile.ZIP_STORED)
            if f.with_suffix(".txt").exists():
                z.write(f.with_suffix(".txt"), f"audio/{f.with_suffix('.txt').name}", zipfile.ZIP_DEFLATED)
    tmp.replace(out)


def build(out_dir: Path, pack_id: str, title: str, *, varieties: list[str] | None = None, tag: str = "",
          version: int = 1, description: str = "", audio_files: bool = True, store: Store | None = None) -> dict:
    """Write the pack for your active cards (of these varieties, with this tag). Returns what went in."""
    _slug(pack_id)
    es, doubtful = _select(store or Store(), varieties, tag)
    cards = [card(e) for e in es]
    pics, sounds, missing = _media(cards)
    if not audio_files:
        sounds = {}
    out = Path(out_dir) / f"{pack_id}-v{version}.panko.zip"
    _write(out, _meta(pack_id, version, title, description, cards, pics, sounds), cards, pics, sounds)
    return {"path": str(out), "cards": len(cards), "doubtful_left_out": len(doubtful), "pictures": len(pics),
            "audio": len(sounds), "audio_not_made": missing, "bytes": out.stat().st_size}


# ---- publish --------------------------------------------------------------------------------------------------------

# licences a published photo may carry (the library is free, so NC, ND and SA are fine); anything else loses it
OPEN = re.compile(r"^(CC0( 1\.0)?|CC CC0( 1\.0)?|CC PDM( 1\.0)?|CC BY(-NC)?(-ND|-SA)?( \d\.\d)?( [a-z]{2})?|Public domain"
                  r"|No (known copyright )?restrictions|Pexels License|Pixabay Content License|Illustration generated \(.*\)"
                  r"|Panko diagram)$", re.I)
NAMED = re.compile(r"\bwith ([A-Z][\w-]+)|\b([A-Z][\w-]+)['’]s\b")
OPTIONAL = ("notes", "usage", "gloss_note", "literal")     # fields a card can lose and still be a card


def _lib() -> dict:
    from panko.config import settings
    return settings().get("library", {})


def text_licence() -> str:
    return _lib().get("licence", "CC BY-SA 4.0")


def is_public(source: str, public: list[str]) -> bool:
    """A sentence's source names a public one (`[library] public_sources`: the start of its name)."""
    return bool(source) and any(source.lower().startswith(p.lower()) for p in public if p)


def licence(credit: str) -> str:
    """The licence at the end of a picture credit ("<a …>Wikimedia Commons</a> · author · CC BY-SA 4.0")."""
    text = re.sub(r"<[^>]+>", "", credit or "").strip()
    return re.split(r" · |, ", text)[-1].strip() if text else ""


def private_names(store: Store, public: list[str]) -> list[str]:
    """Words that mustn't appear in a published card: `[library] private_names` (keep them in config/hub.toml,
    which isn't tracked) and people named in the titles of private sources ("Lesson with X", "X's notes")."""
    names = set(_lib().get("private_names", []))
    titles = [r["title"] for r in store.db.execute("SELECT title FROM sources")]
    titles += [s.get("title", "") for s in work.sources().values() if not s.get("public")]
    for t in titles:
        if not is_public(t, public):
            names |= {a or b for a, b in NAMED.findall(t)}
    return sorted(n for n in names if len(n) > 2)


def _scrub(c: dict, names: list[str]) -> tuple[dict | None, list[str]]:
    """The card without anything naming a private person: an example or an optional field naming one is dropped,
    and a card whose word or gloss names one is left out (None). Returns (card, what was dropped)."""
    if not names:
        return c, []
    hit = re.compile("|".join(rf"\b{re.escape(n)}\b" for n in names), re.I)
    dropped = []
    image = c.get("image") if isinstance(c.get("image"), dict) else {}
    for k, v in c.items():
        if k in ("examples", "image", "id") or not hit.search(json.dumps(v, ensure_ascii=False)):
            continue
        if k not in OPTIONAL:
            return None, [k]
        dropped.append(k)
    c = {k: v for k, v in c.items() if k not in dropped}
    if image.get("prompt") and hit.search(image["prompt"]):
        c["image"] = {k: v for k, v in image.items() if k != "prompt"}
        dropped.append("image prompt")
    exs = [x for x in c.get("examples", []) if not hit.search(json.dumps(x, ensure_ascii=False))]
    if len(exs) < len(c.get("examples", [])):
        dropped.append(f"{len(c['examples']) - len(exs)} example(s)")
        c["examples"] = exs
    return c, dropped


def _next_version(pack_id: str, out_dir: Path, index: dict) -> int:
    seen = [d.get("version", 0) for d in index.get("decks", []) if d.get("id") == pack_id]
    seen += [int(m.group(1)) for f in Path(out_dir).glob(f"{pack_id}-v*.panko.zip")
             if (m := re.fullmatch(rf"{re.escape(pack_id)}-v(\d+)\.panko\.zip", f.name))]
    return max(seen, default=0) + 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def publish(pack_id: str, title: str, *, out: Path | None = None, varieties: list[str] | None = None,
            tag: str = "", version: int | None = None, description: str = "", audio_files: bool = True,
            index: Path | None = None, apkg: bool = True, dry_run: bool = False, store: Store | None = None) -> dict:
    """Build a deck for the public library: the checks, the pack, the .apkg built from it, the index entry and a
    report. With `dry_run`, only says what would go in and what would be left out. Never uploads anything."""
    _slug(pack_id)
    store = store or Store()
    dest = Path(out) if out else out_dir()
    idx = json.loads(Path(index).read_text()) if index and Path(index).exists() else {"format": 1, "decks": []}
    version = version or _next_version(pack_id, dest, idx)
    es, doubtful = _select(store, varieties, tag)
    public = list(_lib().get("public_sources", []))
    names = private_names(store, public)

    left = {"doubtful": [(e["id"], e["ar"]) for e in doubtful], "pictures": [], "named": [], "scrubbed": [],
            "examples": collections.Counter(), "no_example": []}
    cards = []
    for e in es:
        for x in e.get("examples", []):
            src = x.get("source") or ""
            if WRITTEN not in src and not is_public(src, public):
                left["examples"][re.sub(r" p\. \d+$", "", src) or "(no source)"] += 1
        c = card(e, public)
        im = c.get("image") if isinstance(c.get("image"), dict) else None
        if im and im.get("file") and not OPEN.match(licence(im.get("credit", ""))):
            left["pictures"].append((e["id"], e["ar"], licence(im.get("credit", "")) or "no credit"))
            c.pop("image")
        c, dropped = _scrub(c, names)
        if c is None:
            left["named"].append((e["id"], e["ar"], dropped[0]))
            continue
        if dropped:
            left["scrubbed"].append((e["id"], e["ar"], ", ".join(dropped)))
        if not c.get("examples") and c["kind"] == "word":
            left["no_example"].append((e["id"], e["ar"]))
        cards.append(c)
    pics, sounds, missing = _media(cards)
    if not audio_files:
        sounds = {}
    meta = _meta(pack_id, version, title, description, cards, pics, sounds)
    lic = collections.Counter(_licence_kind(licence(c["image"].get("credit", ""))) for c in cards
                              if isinstance(c.get("image"), dict) and c["image"].get("file") in pics)
    stem = f"{pack_id}-v{version}"
    rep = {"id": pack_id, "version": version, "cards": len(cards), "pictures": len(pics), "audio": len(sounds),
           "audio_not_made": missing, "picture_licences": dict(lic.most_common()),
           "left_out": {"doubtful": len(left["doubtful"]), "pictures": len(left["pictures"]),
                        "cards_naming_someone": len(left["named"]),
                        "examples_from_private_sources": sum(left["examples"].values())},
           "scrubbed": len(left["scrubbed"]), "words_without_example": len(left["no_example"]), "private_names": len(names),
           "bytes_estimate": sum(f.stat().st_size for f in [*pics.values(), *sounds.values()]), "dry_run": dry_run}
    if dry_run:
        return {**rep, "report": _report(meta, rep, left, names, public)}

    pack = dest / f"{stem}.panko.zip"
    _write(pack, meta, cards, pics, sounds)
    files = [pack]
    if apkg:
        try:
            files.append(_apkg(dest / f"{stem}.apkg", pack_id, title, cards, pics, sounds))
        except RuntimeError as err:          # Anki's library isn't installed: the pack alone still works
            rep["apkg_skipped"] = str(err)
    entry = {**{k: meta[k] for k in ("id", "version", "title", "description", "language", "varieties", "counts",
                                      "licence", "created", "panko")},
             "picture_licences": rep["picture_licences"], "audio": bool(sounds),
             "files": [{"name": f.name, "kind": "pack" if f.suffix == ".zip" else "apkg", "bytes": f.stat().st_size,
                        "sha256": _sha256(f), **({"url": _release_url(f"{pack_id}-v{version}", f.name)}
                                                  if _lib().get("repo") else {})} for f in files],
             "samples": [{k: c.get(k, "") for k in ("ar", "tl", "gloss")} for c in _samples(cards)]}
    (dest / f"{stem}.index.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1))
    report = dest / f"{stem}.report.md"
    report.write_text(_report(meta, rep, left, names, public))
    if index:
        idx["decks"] = [d for d in idx.get("decks", []) if d.get("id") != pack_id] + [entry]
        idx["decks"].sort(key=lambda d: d["id"])
        Path(index).write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n")
    return {**rep, "files": [str(f) for f in files], "entry": str(dest / f"{stem}.index.json"),
            "report": str(report), "upload": upload_steps(entry, files, index)}


def _licence_kind(lic: str) -> str:
    """A photo licence as the library lists it ("CC BY-SA 2.0" → "CC BY-SA")."""
    if lic.startswith("Illustration generated") or lic == "Panko diagram":
        return "drawn for Panko"
    if re.match(r"(CC )?CC0|CC PDM|Public domain|No (known copyright )?restrictions", lic, re.I):
        return "public domain"
    return re.sub(r"( \d\.\d)?( [a-z]{2})?$", "", lic)


def _samples(cards: list[dict], n: int = 3) -> list[dict]:
    good = [c for c in cards if c.get("examples") and c.get("image")] or cards
    step = max(1, len(good) // n)
    return good[::step][:n]


def _apkg(out: Path, pack_id: str, title: str, cards: list[dict], pics: dict, sounds: dict) -> Path:
    """The .apkg built from the pack's own cards and files, so both hold the same deck. A note's guid is the pack id
    plus the card's id there, so a newer version updates the notes from the old one."""
    from panko.anki import apkg as A
    from panko.cards import build as B
    narrator, notes = A._Made(personal=False), []
    if not sounds:                                   # published without audio: no sound on the cards either
        narrator.say = lambda *a, **k: None
    room = out.parent / f".{out.stem}-media"
    room.mkdir(exist_ok=True)
    try:
        for name, f in {**pics, **sounds}.items():     # only the pack's files, nothing else from your media
            try:
                (room / name).hardlink_to(f)
            except OSError:
                shutil.copy2(f, room / name)
        for c in cards:
            n = B.to_note({**c, "sources": [], "review": False}, narrator)
            n["deck"] = f"Panko::{title}"
            n["tags"] = [t for t in n["tags"] if not t.startswith("panko::")]
            notes.append((A._guid(f"{pack_id}/{c['id']}"), n))
        A.package(out, notes, [room])
    finally:
        shutil.rmtree(room, ignore_errors=True)
    return out


def _release_url(tag: str, name: str) -> str:
    return f"https://github.com/{_lib()['repo']}/releases/download/{tag}/{name}"


def upload_steps(entry: dict, files: list[Path], index: Path | None) -> list[str]:
    """What you do by hand to publish (Panko never uploads on its own)."""
    repo = _lib().get("repo") or "OWNER/panko-decks"
    tag = f"{entry['id']}-v{entry['version']}"
    names = " ".join(f'"{f}"' for f in files)
    return [f'gh release create {tag} {names} --repo {repo} --title "{entry["title"]} v{entry["version"]}" '
            f'--notes "{entry["description"] or entry["title"]}"',
            (f"commit {index} in your clone of {repo} and open a pull request" if index else
             f"add the entry in {tag}.index.json to index.json in {repo} and open a pull request"),
            "keep the .report.md to yourself: it names your private sources"]


def _report(meta: dict, rep: dict, left: dict, names: list[str], public: list[str]) -> str:
    """What went in and what was left out, for you (it names your sources, so it isn't uploaded)."""
    not_made = f" ({rep['audio_not_made']} not made yet)" if rep["audio_not_made"] else ""
    L = [f"# {meta['title']} v{meta['version']}", "",
         f"{rep['cards']} cards, {rep['pictures']} pictures, {rep['audio']} audio clips{not_made}. "
         f"Card text: {meta['licence']}.", ""]
    if rep["picture_licences"]:
        L += ["## Picture licences", "", *[f"- {k}: {v}" for k, v in rep["picture_licences"].items()], ""]
    L += ["## Left out", ""]
    if left["doubtful"]:
        L += [f"**{len(left['doubtful'])} doubtful cards** (`panko::doubtful`): "
              + ", ".join(f"{a} ({i})" for i, a in left["doubtful"][:30]), ""]
    if left["pictures"]:
        L += [f"**{len(left['pictures'])} pictures** with a licence Panko can't read (the card goes without):", "",
              *[f"- {a} ({i}): {lic}" for i, a, lic in left["pictures"]], ""]
    if left["examples"]:
        L += [f"**{sum(left['examples'].values())} sentences** from sources that aren't public (add a source to "
              "`[library] public_sources` once you know its licence allows it):", "",
              *[f"- {src}: {n}" + (" (a placeholder, not a source's name: worth fixing on the card)"
                                   if src.lower() in ("source", "the source") else "")
                for src, n in left["examples"].most_common()], ""]
    if left["named"]:
        L += [f"**{len(left['named'])} cards** whose text names someone from a private source:", "",
              *[f"- {a} ({i}), in {k}" for i, a, k in left["named"]], ""]
    if left["scrubbed"]:
        L += [f"**{len(left['scrubbed'])} cards** kept without a part that named someone:", "",
              *[f"- {a} ({i}): {what}" for i, a, what in left["scrubbed"]], ""]
    L += ["## Worth knowing", "",
          f"- {len(left['no_example'])} words have no example sentence left"
          + (": " + ", ".join(a for _, a in left["no_example"][:40]) + (" …" if len(left["no_example"]) > 40 else "")
             if left["no_example"] else "."),
          f"- Public sources: {', '.join(public) or 'none set'}. Names looked for: {', '.join(names) or 'none'}.",
          "- Audio: check that your voice provider's plan allows sharing its audio in a free public deck "
          "(otherwise publish with `--no-audio`).", ""]
    return "\n".join(L)


# ---- the library: list and get ----------------------------------------------------------------------------------------

def index_source() -> str:
    """Where the library's index is: `[library] index` (a URL or a file), else the library repo's index.json."""
    lib = _lib()
    if lib.get("index"):
        return str(lib["index"])
    return f"https://raw.githubusercontent.com/{lib['repo']}/main/index.json" if lib.get("repo") else ""


def library_dir() -> Path:
    """Where downloaded decks go: `[library] dir`, else beside your exports (packs are big), else cache/library."""
    from panko.config import CACHE, settings
    s = settings()
    if s.get("library", {}).get("dir"):
        return Path(s["library"]["dir"]).expanduser()
    if s.get("export", {}).get("dir"):
        return Path(s["export"]["dir"]).expanduser() / "library"
    return CACHE / "library"


def _is_url(src: str) -> bool:
    return src.startswith(("https://", "http://"))


def load_index(src: str | None = None) -> dict:
    """The library's index, checked: {"format": 1, "decks": [...]}."""
    src = src or index_source()
    if not src:
        raise ValueError("no library set: put its index in [library] index (a URL or a file), or [library] repo")
    if _is_url(src):
        import httpx
        r = httpx.get(src, timeout=20, follow_redirects=True)
        r.raise_for_status()
        idx = r.json()
    else:
        idx = json.loads(Path(src).expanduser().read_text())
    if not isinstance(idx, dict) or idx.get("format") != 1 or not isinstance(idx.get("decks"), list):
        raise ValueError(f"{src} isn't a Panko library index (format 1)")
    return idx


def have() -> dict[str, int]:
    """{pack id: version} of the packs imported into this Panko."""
    return {s["pack"]: s.get("version", 1) for s in work.sources().values() if s.get("type") == "pack" and s.get("pack")}


def decks(src: str | None = None) -> list[dict]:
    """The library's decks, each with whether it fits this Panko (its language, a variety you learn), the version you
    have and whether a newer one is out."""
    from panko.config import settings
    L = settings().get("learner", {})
    mine, vs, got = (L.get("language") or "").strip().lower(), set(L.get("varieties", [])), have()
    out = []
    for d in load_index(src)["decks"]:
        if not isinstance(d, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,47}", str(d.get("id", ""))):
            continue                                  # an entry that isn't a deck is ignored, never trusted
        lang_ok = not mine or (d.get("language") or "").strip().lower() == mine
        why = ("" if lang_ok and (not vs or vs & set(d.get("varieties", []))) else
               f"for {d.get('language')}" if not lang_ok else
               f"for {', '.join(d.get('varieties', []))}: add it to [learner] varieties to take it")
        mine_v = got.get(d["id"])
        out.append({**d, "fits": not why, "why_not": why, "have": mine_v,
                    "update": bool(mine_v) and int(d.get("version", 1)) > int(mine_v)})
    return out


def _file(entry: dict, kind: str) -> dict:
    f = next((f for f in entry.get("files", []) if f.get("kind") == kind), None)
    if not f or not re.fullmatch(r"[\w.-]+", str(f.get("name", ""))) or not re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256", ""))):
        raise ValueError(f"{entry.get('id')} has no {kind} file in the index")
    return f


def fetch(entry: dict, kind: str = "pack", *, src: str | None = None, dest: Path | None = None, progress=None) -> Path:
    """Download one of a deck's files into the library folder and check it against the index's sha256. A file already
    there with the right sha256 is used as it is. `progress(done_bytes, total_bytes)` is called while downloading."""
    f = _file(entry, kind)
    dest = Path(dest or library_dir())
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f["name"]
    if out.exists() and _sha256(out) == f["sha256"]:
        return out
    need = int(f.get("bytes", 0)) + 50_000_000
    if shutil.disk_usage(dest).free < need:
        raise RuntimeError(f"{f['name']} needs about {need // 1_000_000:,} MB free in {dest}: set [library] dir to a "
                           "folder on a bigger disk")
    src = src or index_source()
    url = f.get("url", "")
    part = out.with_suffix(out.suffix + ".part")
    beside = Path(src).expanduser().parent / f["name"] if src and not _is_url(src) else None
    if beside and beside.is_file():                # a local library: the files sit beside its index
        shutil.copyfile(beside, part)
    elif url:
        if not url.startswith("https://"):
            raise ValueError(f"{entry['id']}: only https downloads are allowed")
        import httpx
        with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r, open(part, "wb") as w:
            r.raise_for_status()
            total, done = int(r.headers.get("content-length") or f.get("bytes") or 0), 0
            for block in r.iter_bytes(1 << 20):
                w.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
    else:
        raise ValueError(f"{entry['id']}: the index gives no address for {f['name']}")
    if _sha256(part) != f["sha256"]:
        part.unlink()
        raise ValueError(f"{f['name']} doesn't match the index (sha256): not imported. Try again later")
    part.replace(out)
    return out


def get(deck_id: str, *, activate: bool = False, src: str | None = None, store: Store | None = None,
        progress=None) -> dict:
    """Download a deck from the library and import it (the normal ingest). Returns the import report."""
    d = next((x for x in decks(src) if x["id"] == deck_id), None)
    if not d:
        raise ValueError(f"no deck {deck_id!r} in the library")
    if not d["fits"]:
        raise ValueError(f"{d['title']} is {d['why_not']}")
    if d["update"]:
        raise ValueError(f"you have v{d['have']} of {d['title']}; taking v{d['version']} over it (keeping your edits) "
                         "isn't built yet")
    path = fetch(d, "pack", src=src, progress=progress)
    return {**import_pack(path, store=store, activate=activate), "file": str(path)}


# ---- import ---------------------------------------------------------------------------------------------------------

def read(path: Path) -> tuple[dict, list[dict]]:
    """(pack.json, cards) of a pack, checked."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if not {"pack.json", "entries.jsonl"} <= names:
            raise ValueError(f"{Path(path).name} isn't a Panko pack (no pack.json / entries.jsonl)")
        meta = json.loads(z.read("pack.json"))
        if meta.get("format") != FORMAT:
            raise ValueError(f"this pack is format {meta.get('format')}; this Panko reads format {FORMAT}: update Panko")
        cards = [json.loads(line) for line in z.read("entries.jsonl").decode().splitlines() if line.strip()]
    return meta, cards


def import_pack(path: Path | str, *, store: Store | None = None, activate: bool = False) -> dict:
    """Bring a pack into your Panko: register it as a source, copy its media, ingest its cards. Returns the ingest
    report plus what was skipped."""
    from panko import ingest
    from panko.config import settings
    from panko.media import audio
    path = Path(path)
    store = store or Store()
    meta, cards = read(path)
    L = settings().get("learner", {})
    mine, theirs = (L.get("language") or "").strip().lower(), (meta.get("language") or "").strip().lower()
    if mine and theirs and mine != theirs:
        raise ValueError(f"this pack is for {meta['language']}, and this Panko is set up for {L['language']}")
    have = set(L.get("varieties", []))
    keep = [c for c in cards if not have or c["variety"] in have]
    skipped = len(cards) - len(keep)
    if not keep:
        raise ValueError(f"none of its cards are for a variety you learn ({', '.join(sorted(have)) or 'none'}): "
                         f"it has {', '.join(meta.get('varieties', []))}. Add one to [learner] varieties in your config "
                         "to take its cards")

    # media: pictures beside your own, audio into the audio cache with its note, so sync finds it and pays nothing
    pics_dir = pictures_dir()
    pics_dir.mkdir(parents=True, exist_ok=True)
    audio.MEDIA.mkdir(parents=True, exist_ok=True)
    copied = 0
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            folder, _, name = n.partition("/")
            if folder not in ("media", "audio") or not name or "/" in name or name.startswith("."):
                continue
            dest = (pics_dir if folder == "media" else audio.MEDIA) / name
            if not dest.exists():
                with z.open(n) as src, open(dest, "wb") as f:
                    shutil.copyfileobj(src, f)
                copied += 1

    # the pack as a source whose units are already submitted
    sid = f"pack-{meta['id']}"
    reg = work.sources()
    reg[sid] = {"id": sid, "kind": "pack", "type": "pack", "title": meta["title"], "date": meta.get("created", "")[:10],
                "trust": 50, "tag": sid, "path": str(path), "added": _now(), "pack": meta["id"],
                "version": meta.get("version", 1), "units": [f"k{i:03d}" for i in range(1, (len(keep) - 1) // UNIT + 2)]}
    work._save_sources(reg)
    for i, u in enumerate(reg[sid]["units"]):
        if (work.result(sid, u) or {}).get("status") == "ingested":
            continue                          # importing the same pack again leaves what's done
        items = [_item(c, meta) for c in keep[i * UNIT:(i + 1) * UNIT]]
        work._save_result(sid, u, {"unit": u, "status": "submitted", "submitted": _now(), "items": items})
    rep = work.ingest_source(sid, store)
    if activate:
        new = [e["id"] for e in store.entries("candidate") if (e.get("origin") or {}).get("pack") == meta["id"]]
        rep["activated"] = len(ingest.activate(store, new))
    return {**rep, "pack": meta["id"], "version": meta.get("version", 1), "cards": len(cards),
            "other_varieties": skipped, "media_copied": copied}


def _item(c: dict, meta: dict) -> dict:
    """A pack card as a unit item: the whole card, its origin, and `pack` so ingest keeps its check and its fields."""
    it = {k: v for k, v in c.items() if k != "id"}
    it["origin"] = {"pack": meta["id"], "id": c["id"], "version": meta.get("version", 1), "hash": digest(c)}
    it["pack"] = True
    it["examples"] = [{**x, "source": x.get("source") or meta["title"]} for x in c.get("examples", [])]
    return it
