"""`panko` command."""
from __future__ import annotations

import argparse
import os
import sys


def main(argv=None):
    for s in (sys.stdout, sys.stderr):   # Windows writes pipes in cp1252: a ✻ or Arabic would crash the print
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    try:
        _main(argv)
    except FileNotFoundError as e:
        if "panko init" not in str(e):
            raise
        raise SystemExit(str(e)) from None


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="panko")
    ap.add_argument("--version", action="version", version=f"panko {_version()}")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("providers", help="which providers are ready")
    v = sub.add_parser("voices", help="audition ElevenLabs library voices for your language ([audio.elevenlabs] library, audition)")
    v.add_argument("--all", action="store_true")
    sub.add_parser("seed", help="load the hand-written sandbox entries into the store")
    sy = sub.add_parser("sync", help="push active entries to Anki (updates notes in place)")
    sy.add_argument("--dry-run", action="store_true", help="list what would change and the audio still to pay for")
    ex = sub.add_parser("export", help="active cards as an .apkg file to share (needs `uv sync --extra apkg`)")
    ex.add_argument("file", help="where to write it, e.g. darija.apkg")
    ex.add_argument("--variety", action="append", help="only this variety (repeat for more)")
    ex.add_argument("--personal", action="store_true",
                    help="include where each word came from and clips from your lessons (left out by default)")
    pk = sub.add_parser("pack", help="a Panko pack: your active cards as one file another Panko can import")
    pksub = pk.add_subparsers(dest="kcmd")
    pb = pksub.add_parser("build", help="write <id>-v<N>.panko.zip (into [export] dir unless --out)")
    pb.add_argument("id", help="a short slug, e.g. darija-peace-corps")
    pb.add_argument("--title", required=True)
    pb.add_argument("--description", default="")
    pb.add_argument("--variety", action="append", help="only this variety (repeat for more)")
    pb.add_argument("--tag", default="", help="only cards with this tag, e.g. src::textbook::peace-corps")
    pb.add_argument("--version", type=int, default=1)
    pb.add_argument("--no-audio", action="store_true", help="leave the audio out (smaller; sync makes it again)")
    pb.add_argument("--out", help="folder to write it to")
    pu = sub.add_parser("publish", help="build a deck for the public library: checks, pack, .apkg, index entry, report "
                        "(uploading stays manual)")
    pu.add_argument("id", help="a short slug, e.g. darija-peace-corps")
    pu.add_argument("--title", required=True)
    pu.add_argument("--description", default="")
    pu.add_argument("--variety", action="append", help="only this variety (repeat for more)")
    pu.add_argument("--tag", default="", help="only cards with this tag, e.g. src::textbook::peace-corps")
    pu.add_argument("--version", type=int, help="default: one more than the last in the index or the folder")
    pu.add_argument("--no-audio", action="store_true", help="leave the audio out of both files")
    pu.add_argument("--no-apkg", action="store_true", help="only the pack")
    pu.add_argument("--index", help="your clone's index.json: its entry for this deck is replaced")
    pu.add_argument("--out", help="folder to write to (default [export] dir)")
    pu.add_argument("--dry-run", action="store_true", help="say what would go in and what would be left out; write nothing")
    lb = sub.add_parser("library", help="decks from the library: list, get, or import a Panko pack")
    lbsub = lb.add_subparsers(dest="lcmd")
    ll = lbsub.add_parser("list", help="the decks in the library ([library] index)")
    ll.add_argument("--index", help="another index: a URL or a file")
    lg = lbsub.add_parser("get", help="download a deck from the library (sha256 checked) and import it")
    lg.add_argument("id")
    lg.add_argument("--activate", action="store_true", help="make its new cards active straight away")
    lg.add_argument("--apkg", action="store_true", help="only download its .apkg (for Anki without Panko)")
    lg.add_argument("--index", help="another index: a URL or a file")
    li = lbsub.add_parser("import", help="bring a .panko.zip into your Panko (new cards go to the inbox)")
    li.add_argument("file")
    li.add_argument("--activate", action="store_true", help="make its new cards active straight away")
    wk = sub.add_parser("work", help="work through a source in units: add, status, run (API mode), ingest, decide")
    wsub = wk.add_subparsers(dest="wcmd")
    wa = wsub.add_parser("add", help="register a PDF, a folder of page photos, a text transcript, an exported deck "
                                     "(.json) or a lesson recording")
    wa.add_argument("path", nargs="?", default="", help="the file or folder (not needed with --deck)")
    wa.add_argument("--deck", default="", help="export this Anki deck (read-only; Anki open) and add it as a source")
    wa.add_argument("--kind", required=True, help="textbook | teacher-sheet | lesson | media | notes | deck")
    wa.add_argument("--title", required=True)
    wa.add_argument("--id", default="")
    wa.add_argument("--date", default="")
    wa.add_argument("--trust", type=int, default=70, help="0-100: teacher material high, shared decks low")
    wa.add_argument("--page-offset", type=int, default=0, help="PDF page number minus printed page number")
    wa.add_argument("--first", type=int, default=1, help="first PDF page to work on")
    wa.add_argument("--last", type=int, default=0, help="last PDF page to work on")
    wa.add_argument("--track", action="append", default=[], help="recordings: another file of the same session "
                    "(each mic recorded separately); repeat for more")
    wa.add_argument("--speakers", default="", help="recordings: names, comma-separated, one per track (or per "
                    "speaker in order of first speaking, for one track), e.g. teacher,me")
    wa.add_argument("--learner", default="", help="recordings: which of those names is you (never used for clips)")
    wa.add_argument("--transcript", default="", help="recordings: a speech-to-text JSON you already have (free)")
    wt = wsub.add_parser("transcribe", help="speech-to-text for a recording, with word times (paid: [stt] chain)")
    wt.add_argument("source")
    wt.add_argument("--estimate", action="store_true", help="only print how much audio it would send")
    wst = wsub.add_parser("status", help="sources and their progress, or one source in detail")
    wst.add_argument("source", nargs="?")
    wr = wsub.add_parser("run", help="extract, check and plan pictures with the language model (API mode)")
    wr.add_argument("source")
    wr.add_argument("units", nargs="*", help="these units (default: the next -n not done)")
    wr.add_argument("-n", type=int, default=5, help="how many units (default 5)")
    wr.add_argument("--batch", action="store_true", help="one half-price batch per step; `panko llm collect`, then run again")
    wr.add_argument("--budget", type=float, help="stop before spending more than this (USD); default [llm] budget_usd")
    wr.add_argument("--estimate", action="store_true", help="only print what it would cost")
    wi = wsub.add_parser("ingest", help="merge submitted units into the inbox (duplicates are held for you)")
    wi.add_argument("source")
    wd = wsub.add_parser("decide", help="settle a held item: --known ID (same word) or --distinct (new word)")
    wd.add_argument("source")
    wd.add_argument("unit")
    wd.add_argument("ar")
    wd.add_argument("--known", default="")
    wd.add_argument("--distinct", action="store_true")
    it = sub.add_parser("init", help="set up Panko: write config/panko.toml from your answers, then check what's ready")
    it.add_argument("--yes", action="store_true", help="take the defaults without asking")
    it.add_argument("--force", action="store_true", help="replace an existing config (kept as .bak)")
    it.add_argument("--check", action="store_true", help="only check what's ready")
    it.add_argument("--here", action="store_true", help="make the Panko folder in the current folder (an installed "
                    "Panko otherwise uses ~/Panko, or PANKO_HOME)")
    it.add_argument("--language", default="", help="the language your cards teach; a preset fills in the rest "
                    "(moroccan-darija, spanish), any other name starts neutral")
    rf = sub.add_parser("refs", help="the reference corpora and dictionaries: show them, download the open ones")
    rf.add_argument("--download", action="store_true", help="fetch the open ones that are missing")
    rf.add_argument("--force", action="store_true", help="with --download: fetch them again even if present")
    mc = sub.add_parser("mcp", help="run Panko as an MCP server for Claude (chat mode, no API key needed)")
    mc.add_argument("--config", action="store_true", help="print the Claude Desktop / Claude Code config instead")
    mc.add_argument("--bundle", metavar="FILE", help="write chat mode as a Claude Desktop extension (panko.mcpb): "
                    "open it in Claude's desktop app to install, nothing else needed")
    mc.add_argument("--skill", metavar="DIR", help="write the chat workflow as a Claude skill: DIR/panko/SKILL.md "
                    "(e.g. ~/.claude/skills for Claude Code)")
    hb = sub.add_parser("hub", help="the local dashboard in your browser: sources, inbox, card previews, checks, "
                        "pictures, sync and spend")
    hb.add_argument("--port", type=int, default=8770)
    hb.add_argument("--no-open", action="store_true", help="print the link without opening a browser")
    hb.add_argument("--token", default="", help=argparse.SUPPRESS)
    hb.add_argument("--socket", metavar="PATH", help="on the server: listen on this Unix socket behind the front door "
                    "(needs PANKO_FRONT_SECRET; see docs/SPEC-hosted.md)")
    from panko.host import cli as host_cli
    host_cli.add_parser(sub)
    i = sub.add_parser("ingest", help="load an extraction JSON into the store")
    i.add_argument("path")
    i.add_argument("--verdicts", nargs="*", default=[], help="verification JSON files to apply first")
    i.add_argument("--overrides", help="hand-made overrides JSON {key: {field: value} | {drop: true}}")
    ib = sub.add_parser("inbox", help="list candidates waiting to become cards")
    ib.add_argument("--html", action="store_true", help="write a review page (cache/review/inbox.html)")
    ib.add_argument("--tag", help="only candidates with this tag, e.g. src::textbook::peace-corps")
    ib.add_argument("--plans", nargs="*", default=[], help="picture-plan JSON files to show on the cards")
    rj = sub.add_parser("reject", help="retire candidates you don't want (ids from the review page)")
    rj.add_argument("ids", nargs="+")
    a = sub.add_parser("activate", help="turn candidates into cards on next sync")
    a.add_argument("ids", nargs="*")
    a.add_argument("--batch", type=int)
    d = sub.add_parser("draw", help="generate memorable illustrations from a JSON file {entry id: what to draw}")
    d.add_argument("path", nargs="?")
    d.add_argument("--force", action="store_true", help="replace pictures entries already have")
    d.add_argument("--batch", action="store_true", help="submit as an OpenAI batch (half price, within 24 h)")
    d.add_argument("--collect", action="store_true", help="save the drawings of finished batches")
    pic = sub.add_parser("pictures", help="pictures for cards: export → search → apply (see PICTURE-BRIEF.md)")
    psub = pic.add_subparsers(dest="pcmd")
    pe = psub.add_parser("export", help="cards without a picture → JSON for the decider")
    pe.add_argument("out")
    pe.add_argument("--status", default="active", choices=["active", "candidate"])
    pe.add_argument("--batch", type=int)
    pe.add_argument("--chunks", type=int, default=1, help="split into N files (out-1.json …)")
    ps = psub.add_parser("search", help="photo candidates + contact sheets")
    ps.add_argument("outdir")
    ps.add_argument("queries", help='JSON {"slug": "english query", ...}')
    ps.add_argument("--providers", help="comma-separated image providers instead of the [images] chain, "
                    "e.g. inaturalist,arasaac")
    pd = psub.add_parser("decide", help="choose a picture per card with the language model: plan → photo search → "
                         "pick from the contact sheets (API mode); writes data/pictures/decisions.json")
    pd.add_argument("--status", default="active", choices=["active", "candidate"])
    pd.add_argument("--batch", type=int, help="only this entry batch")
    pd.add_argument("--ids", nargs="*", default=[], help="only these entries")
    pd.add_argument("--tag", help="only entries with this tag, e.g. src::textbook::peace-corps")
    pd.add_argument("--plans", nargs="*", default=[], help="extra picture-plan files {ar|gloss: plan}")
    pd.add_argument("--searched", nargs="*", default=[], help="folders of earlier `pictures search` runs to reuse")
    pd.add_argument("--no-search-drawings", action="store_true", help="don't look for photos for drawing-planned cards")
    pd.add_argument("--llm-batch", action="store_true", help="half-price batches; `panko llm collect`, then run again")
    pd.add_argument("--budget", type=float, help="stop before spending more than this (USD)")
    pd.add_argument("--estimate", action="store_true", help="only print what it would cost")
    pa = psub.add_parser("apply", help="apply decisions: download photos, then draw the prompts")
    pa.add_argument("paths", nargs="*", help="decision files (default: data/pictures/decisions.json)")
    pa.add_argument("--batch", action="store_true", help="draw as an OpenAI batch instead of now")
    pa.add_argument("--no-draw", action="store_true", help="only download photos; write prompts to a file")
    ex = sub.add_parser("examples", help="example sentences for words without one (API mode): picks from your sources "
                        "and the corpora, or writes one; the next sync shows and voices them")
    ex.add_argument("--status", default="active", choices=["active", "candidate"])
    ex.add_argument("--ids", nargs="*", default=[])
    ex.add_argument("--tag", default="")
    ex.add_argument("--want", type=int, default=1, help="examples each entry should have (default 1)")
    ex.add_argument("--estimate", action="store_true")
    ex.add_argument("--llm-batch", action="store_true")
    ex.add_argument("--budget", type=float)
    cl = sub.add_parser("clashes", help="production cards that would show the same gloss: decide (API mode), then "
                        "--apply after you've looked at data/work/clashes.json")
    cl.add_argument("--all", action="store_true", help="every clash, not only those involving candidates")
    cl.add_argument("--estimate", action="store_true")
    cl.add_argument("--llm-batch", action="store_true")
    cl.add_argument("--budget", type=float)
    cl.add_argument("--apply", action="store_true", help="write the saved decisions to the store")
    vf = sub.add_parser("verify", help="check entries with deterministic tools: varieties with a morphological "
                        "analyser ([morph]) against its readings, the others against the references (free)")
    vf.add_argument("ids", nargs="*", help="these entries (default: every entry with --status)")
    vf.add_argument("--status", default="candidate", help="candidate | active | all (default candidate)")
    vf.add_argument("--apply", action="store_true", help="tag candidates with a spelling, marks or root problem "
                    "panko::doubtful (kept out of Anki until you clear them) and save the problems on the entry")
    vf.add_argument("--tag-active", action="store_true", help="with --apply: tag active entries too (they stay in "
                    "Anki, tagged)")
    vf.add_argument("--report", default="", help="also write the full report as JSON here")
    lm = sub.add_parser("llm", help="language model: ping, usage, collect batches")
    lsub = lm.add_subparsers(dest="lcmd")
    lsub.add_parser("ping", help="one tiny request to check the model works (costs a fraction of a cent)")
    lu = lsub.add_parser("usage", help="spend so far, by task and model")
    lu.add_argument("--since", default="", help="YYYY-MM-DD")
    lsub.add_parser("collect", help="save the answers of finished batches")
    m = sub.add_parser("migrate", help="Phase 6: convert studied old-deck notes in place (history kept)")
    m.add_argument("ids", nargs="*", help="only these entries (e.g. a test batch)")
    m.add_argument("--apply", action="store_true", help="really convert (Anki must be closed); default is a dry run")
    m.add_argument("--report", help="write the dry-run list to this Markdown file")
    args = ap.parse_args(argv)
    if args.cmd == "init" and args.here:     # before anything reads the Panko folder
        from pathlib import Path
        os.environ["PANKO_HOME"] = str(Path.cwd())

    if args.cmd == "providers":
        from panko import providers
        for cap in ("audio", "images", "llm", "stt", "morph"):
            print(f"{cap}: available={providers.available(cap)} ready={[p.name for p in providers.chain(cap)]}")
    elif args.cmd == "voices":
        from panko.media.audition import run
        run(all_voices=args.all)
    elif args.cmd == "seed":
        from panko.sandbox import seed
        from panko.store import Store
        print("loaded", seed.load(Store()), "entries")
    elif args.cmd == "sync":
        from panko.anki import sync
        if args.dry_run:
            p = sync.plan()
            print(f"add {len(p['add'])}, update {len(p['update'])}, unchanged {p['unchanged']}; "
                  f"audio to generate: {p['audio_clips']} clips {p['audio_chars']}")
        else:
            sync.sync()
    elif args.cmd == "export":
        from pathlib import Path

        from panko.anki import apkg
        r = apkg.export(Path(args.file).expanduser(), args.variety, args.personal)
        print(f"wrote {r['path']}: {r['notes']} cards, {r['media']} media files, {r['bytes'] / 1e6:.0f} MB"
              + (f"; {r['audio_not_made']} audio clips not made yet were left out (sync makes them)"
                 if r["audio_not_made"] else ""))
    elif args.cmd == "pack" and args.kcmd == "build":
        from pathlib import Path

        from panko import library
        r = library.build(Path(args.out).expanduser() if args.out else library.out_dir(), args.id, args.title,
                          varieties=args.variety, tag=args.tag, version=args.version, description=args.description,
                          audio_files=not args.no_audio)
        print(f"wrote {r['path']}: {r['cards']} cards, {r['pictures']} pictures, {r['audio']} audio clips, "
              f"{r['bytes'] / 1e6:.0f} MB" + (f"; {r['doubtful_left_out']} doubtful cards left out" if r["doubtful_left_out"] else "")
              + (f"; {r['audio_not_made']} clips not made yet (sync makes them)" if r["audio_not_made"] else ""))
    elif args.cmd == "publish":
        from pathlib import Path

        from panko import library
        r = library.publish(args.id, args.title, out=Path(args.out).expanduser() if args.out else None,
                            varieties=args.variety, tag=args.tag, version=args.version, description=args.description,
                            audio_files=not args.no_audio, index=Path(args.index).expanduser() if args.index else None,
                            apkg=not args.no_apkg, dry_run=args.dry_run)
        lo = r["left_out"]
        print(f"{args.id} v{r['version']}: {r['cards']} cards, {r['pictures']} pictures, {r['audio']} audio clips"
              + (f" ({r['audio_not_made']} not made yet)" if r["audio_not_made"] else ""))
        print(f"left out: {lo['doubtful']} doubtful cards, {lo['pictures']} pictures with an unreadable licence, "
              f"{lo['examples_from_private_sources']} sentences from private sources, {lo['cards_naming_someone']} cards "
              f"naming someone; {r['scrubbed']} cards trimmed; {r['words_without_example']} words left without an example")
        print("picture licences: " + ", ".join(f"{k} {v}" for k, v in r["picture_licences"].items()))
        if r["dry_run"]:
            print(f"(dry run, about {r['bytes_estimate'] / 1e6:.0f} MB of media; nothing written)\n")
            print(r["report"])
        else:
            print("wrote " + ", ".join(r["files"]) + f"\nindex entry: {r['entry']}\nreport (keep it to yourself): {r['report']}")
            if r.get("apkg_skipped"):
                print(f"no .apkg: {r['apkg_skipped']}")
            print("\nTo publish, by hand:\n" + "\n".join(f"  {i}. {step}" for i, step in enumerate(r["upload"], 1)))
    elif args.cmd == "library" and args.lcmd == "list":
        from panko import library
        ds = library.decks(args.index)
        if not ds:
            print("the library has no decks yet")
        for d in ds:
            size = sum(f.get("bytes", 0) for f in d.get("files", []) if f.get("kind") == "pack") / 1e6
            c = d.get("counts", {})
            state = (f"you have v{d['have']}" + (", a newer one is out" if d["update"] else "")) if d["have"] else ""
            print(f"{d['id']} v{d.get('version', 1)}  {d.get('title', '')}\n  {c.get('words', 0)} words, "
                  f"{c.get('phrases', 0)} phrases, {c.get('pictures', 0)} pictures, {c.get('audio', 0)} clips; "
                  f"{size:.0f} MB" + (f"; {state}" if state else "") + ("" if d["fits"] else f"; {d['why_not']}"))
    elif args.cmd == "library" and args.lcmd == "get":
        from panko import library

        def bar(done, total):
            print(f"\r  {done / 1e6:.0f} of {total / 1e6:.0f} MB" if total else f"\r  {done / 1e6:.0f} MB", end="", flush=True)
        if args.apkg:
            d = next((x for x in library.decks(args.index) if x["id"] == args.id), None)
            if not d:
                raise SystemExit(f"no deck {args.id!r} in the library")
            path = library.fetch(d, "apkg", src=args.index, progress=bar)
            print(f"\n{path}: open it with Anki to add the deck")
        else:
            r = library.get(args.id, activate=args.activate, src=args.index, progress=bar)
            print(f"\n{r['pack']} v{r['version']}: {r['new']} new cards" + (f" ({r['activated']} activated)"
                  if "activated" in r else " in your inbox") + f", {r['known']} you already had, {len(r['held'])} "
                  "held for you to decide")
    elif args.cmd == "library" and args.lcmd == "import":
        from panko import library
        r = library.import_pack(args.file, activate=args.activate)
        print(f"{r['pack']} v{r['version']}: {r['new']} new cards" + (f" ({r['activated']} activated)" if "activated" in r
              else " in your inbox") + f", {r['known']} you already had, {len(r['held'])} held for you to decide"
              + (f", {len(r['rejected_again'])} you'd rejected kept out" if r["rejected_again"] else "")
              + (f", {r['other_varieties']} of other varieties skipped" if r["other_varieties"] else "")
              + (f". Settle the held ones with `panko work decide pack-{r['pack']} …` or on the source's page in the hub"
                 if r["held"] else ""))
    elif args.cmd == "init":
        _init(args)
    elif args.cmd == "refs":
        from panko import evidence
        if args.download:
            evidence.download(force=args.force)
        for r in evidence.references_status():
            how = "present" if r["present"] else ("missing: `panko refs --download`" if r["url"]
                                                  else "missing: add this file yourself")
            print(f"{r['name']:<45} {how:<36} {r['path']}")
    elif args.cmd == "work":
        _work(args, wk)
    elif args.cmd == "mcp" and args.bundle:
        from panko import mcpb
        from panko.config import ROOT
        print("wrote", mcpb.write(args.bundle, folder=ROOT), "(open it in Claude's desktop app)")
    elif args.cmd == "mcp" and args.skill:
        from panko import skill
        print("wrote", skill.write(args.skill))
    elif args.cmd == "mcp":
        try:
            from panko import mcp_server
        except ImportError as e:
            ap.error(f"chat mode couldn't start ({e}): install Panko again (uv tool install --reinstall …, or "
                     "uv sync in a checkout)")
        if args.config:
            print(mcp_server.config_snippet())
        else:
            mcp_server.main()
    elif args.cmd == "hub":
        try:
            from panko import hub
        except ImportError as e:
            ap.error(f"the hub couldn't start ({e}): install Panko again (uv tool install --reinstall …, or "
                     "uv sync in a checkout)")
        if args.socket:
            hub.serve_socket(args.socket)
        else:
            _folder_note()
            hub.serve(args.port, not args.no_open, args.token or os.environ.get("PANKO_HUB_TOKEN") or None)
    elif args.cmd == "host":
        from panko.host import cli as host_cli
        host_cli.run(args, ap)
    elif args.cmd == "ingest":
        import json
        from pathlib import Path

        from panko.ingest import ingest
        from panko.ingest.verify import load_verdicts
        ov = json.loads(Path(args.overrides).read_text()) if args.overrides else None
        r = ingest(args.path, verdicts=load_verdicts(args.verdicts), overrides=ov)
        print(f"{r['source']}: {len(r['new'])} new candidates, {len(r['known'])} already known: {', '.join(r['known'])}")
    elif args.cmd == "inbox":
        import json
        from pathlib import Path

        from panko.store import Store
        es = [e for e in Store().entries("candidate") if not args.tag or args.tag in e.get("tags", [])]
        if args.html:
            from panko import review
            plans = {}
            for f in args.plans:
                plans.update(json.loads(Path(f).read_text()))
            print(review.write(es, plans, title=f"Inbox review{' · ' + args.tag.split('::')[-1] if args.tag else ''}"))
            return
        for e in es:
            pic = "pic" if e.get("image") else "   "
            print(f"{e['id']}  {pic}  b{e.get('batch', '-')}  {e['ar']:<28} {e.get('tl', ''):<24} {e.get('gloss', '')}")
    elif args.cmd == "reject":
        from panko.store import Store
        s, done = Store(), []
        for eid in args.ids:
            e = s.get(eid)
            if e and e.get("status", "candidate") == "candidate":
                s.set_status(eid, "retired", why="rejected")
                done.append(eid)
        print(f"retired {len(done)} candidates" + (f"; skipped {len(args.ids) - len(done)} (not candidates)" if len(done) < len(args.ids) else ""))
    elif args.cmd == "activate":
        from panko.ingest import activate
        from panko.store import Store
        print("activated:", activate(Store(), args.ids or None, args.batch))
    elif args.cmd == "draw":
        import json
        from pathlib import Path

        from panko.media import pictures
        if args.collect:
            for bid, r in pictures.collect().items():
                print(bid, r)
        elif not args.path:
            ap.error("draw needs a FILE (or --collect)")
        else:
            _draw(pictures, json.loads(Path(args.path).read_text()), args.force, args.batch)
    elif args.cmd == "llm":
        _llm(args, lm)
    elif args.cmd == "migrate":
        _migrate(args)
    elif args.cmd == "examples":
        import json

        from panko import examples
        from panko.store import Store
        s = Store()
        es = examples.todo(s, args.status, args.ids or None, args.tag, args.want)
        if args.estimate:
            print(json.dumps(examples.estimate(es, s, args.want), indent=1))
            return
        r = examples.run(es, s, args.want, batch=args.llm_batch, budget=args.budget)
        print(f"{r['added']} examples on {r['entries']} of {len(es)} entries; none for {len(r['skipped'])}"
              + (f"; {r['waiting']} requests waiting for a batch" if r["waiting"] else ""))
    elif args.cmd == "clashes":
        import json

        from panko import clashes
        from panko.config import ROOT
        from panko.store import Store
        s, path = Store(), ROOT / "data" / "work" / "clashes.json"
        if args.apply:
            print(clashes.apply(s, json.loads(path.read_text())))
            return
        found = clashes.open_groups(clashes.find(s, None if args.all else [e["id"] for e in s.entries("candidate")]), path)
        groups = clashes.undecided(found, clashes.load(path))        # not the ones you called fine or chose for
        if args.estimate:
            print(json.dumps(clashes.estimate(groups), indent=1))
            return
        d = clashes.decide(groups, batch=args.llm_batch, budget=args.budget)
        clashes.save(clashes.merge(clashes.load(path), d), path)
        kinds = {k: sum(1 for v in d.values() if k in v) for k in ("gloss", "cards", "drop")}
        print(f"{len(groups)} groups: {kinds}; saved to {path}. Look it over, then `panko clashes --apply`.")
    elif args.cmd == "verify":
        _verify(args)
    elif args.cmd == "pictures":
        _pictures(args, pic)
    else:
        ap.print_help()


def _version() -> str:
    from panko import version
    return version() or "unknown"


def _folder_note() -> None:
    """An installed Panko keeps everything in one folder: make it on first use, and say where it is."""
    from panko.config import IS_CHECKOUT, ROOT
    new = not ROOT.exists()
    ROOT.mkdir(parents=True, exist_ok=True)
    if new or not IS_CHECKOUT:
        print(f"✻ Your Panko folder: {ROOT}" + (" (new)" if new else ""), flush=True)


def _init(args):
    from panko import setup
    if not args.check and (args.force or not setup.CONFIG.exists()):
        language = args.language
        if not language and not args.yes:
            names = ", ".join(setup.presets())
            language = input(f"Language your cards teach (presets: {names}) [{setup.DEFAULTS['language']}]: ").strip()
        d = setup.defaults(language)
        profiles = setup.anki_profiles()
        if profiles:
            d["profile"] = profiles[0]

        def ask(key, q):
            if args.yes:
                return d[key]
            shown = ", ".join(d[key]) if isinstance(d[key], list) else d[key]
            got = input(f"{q} [{shown}]: ").strip()
            if got == "-":
                return ""          # "-" for none (no romanisation, no Wiktionary)
            return ([x.strip() for x in got.split(",")] if isinstance(d[key], list) else got) if got else d[key]

        print("Preset:", "yes, " + setup._slug(d["language"]) if setup.preset(d["language"]) else
              "none, so the prompts start neutral: fill in [learner] in the config afterwards")
        answers = {"language": d["language"],
                   "script": ask("script", "Script it's written in (Latin, Arabic, Cyrillic, Han…)"),
                   "gloss_language": ask("gloss_language", "Your language (for meanings)"),
                   "varieties": ask("varieties", "Varieties, comma-separated (deck per variety)"),
                   "deck_root": ask("deck_root", "Deck to put them under"),
                   "profile": ask("profile", f"Anki profile{' (found: ' + ', '.join(profiles) + ')' if profiles else ''}"),
                   "translit": ask("translit", "Romanisation to show first (- for none)"),
                   "wiktionary": ask("wiktionary", "Wiktionary language name for evidence (- to skip)")}
        print("wrote", setup.write_config(answers, force=args.force))
    elif not args.check:
        print(f"{setup.CONFIG} exists (edit it, or `panko init --force` to start over). Checking what's ready:")
    for what, ok, detail in setup.check():
        print(f"  {'✓' if ok else '✗'} {what:<34} {detail}")


def _verify(args):
    import json
    from pathlib import Path

    from panko import checks, providers
    from panko.store import Store
    ready = {v: p.name for p in providers.chain("morph") for v in p.dbs()}
    print("analyser: " + (", ".join(f"{v} ({n})" for v, n in ready.items()) or "none ready (see [morph] in config)"))
    st = ("candidate", "active") if args.status == "all" else (args.status,)
    r = checks.run(Store(), st, ids=args.ids or None, apply=args.apply, tag_active=args.tag_active)
    print(f"checked {r['checked']} with the analyser: {r['fine']} fine, {len(r['doubtful'])} with a spelling, marks "
          f"or root problem, {len(r['listed'])} with something to look at" + (f"; tagged {r['tagged']}" if args.apply else ""))
    for row in [*r["doubtful"], *r["listed"]][:40]:
        for p in row["problems"]:
            print(f"  {row['id']} {row['ar']}: {p['problem']} in {p['field']} {p['text']}"
                  + (f" → {p['suggest']}" if p.get("suggest") else ""))
    if r["ungrounded"]:
        print(f"{len(r['ungrounded'])} dialect words no reference lists (ask your teacher): "
              + ", ".join(f"{u['ar']} '{u['gloss']}'" for u in r["ungrounded"][:25]))
    if args.report:
        Path(args.report).write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(f"report: {args.report}")
    if r["doubtful"] and not args.apply:
        print("tag them with --apply (candidates only; --tag-active for cards already in Anki)")


def _work(args, parser):
    import json

    from panko import work
    if args.wcmd == "add":
        if args.deck:
            from panko.anki.export import export_deck
            path = work.WORK / "decks" / f"{work.slug(args.deck)}.json"
            d = export_deck(args.deck, path)
            print(f"exported {len(d['notes'])} notes ({sum(n['studied'] for n in d['notes'])} studied) to {path}")
            args.path = str(path)
        elif not args.path:
            parser.error("give a PATH or --deck NAME")
        s = work.add_source(args.path, args.kind, args.title, args.id, args.date, args.trust,
                            page_offset=args.page_offset, first=args.first, last=args.last, tracks=args.track,
                            speakers=[x.strip() for x in args.speakers.split(",") if x.strip()],
                            learner=args.learner, transcript=args.transcript)
        if not s["units"]:
            print(f"{s['id']}: a recording of {s['duration'] / 60:.1f} min; next: panko work transcribe {s['id']} "
                  "--estimate (or add it again with --transcript FILE)")
        else:
            print(f"{s['id']}: {len(s['units'])} units ({s['units'][0]}…{s['units'][-1]})")
    elif args.wcmd == "transcribe":
        s = work.source(args.source)
        if s["type"] != "audio":
            parser.error(f"{args.source} isn't a recording")
        mins = s["duration"] * len(s["tracks"]) / 60
        if args.estimate:
            print(f"{args.source}: {len(s['tracks'])} track(s), {mins:.1f} min of audio to send to speech-to-text "
                  "([stt] chain; billed per minute of audio on your provider's plan)")
            return
        s = work.transcribe(args.source)
        print(f"{s['id']}: transcribed ({mins:.1f} min); {len(s['units'])} units ({s['units'][0]}…{s['units'][-1]})")
    elif args.wcmd == "status":
        if args.source:
            print(json.dumps(work.pending(args.source), ensure_ascii=False, indent=1))
            return
        for sid, s in work.sources().items():
            st = work.state(sid)
            counts = ", ".join(f"{k} {sum(1 for v in st.values() if v == k)}" for k in ("todo", "submitted", "held", "ingested"))
            print(f"{sid:<28} {s['title'][:40]:<40} {counts}")
    elif args.wcmd == "run":
        from panko import pipeline
        if args.estimate:
            print(json.dumps(pipeline.estimate(args.source, args.units or None, args.n), indent=1))
            return
        r = pipeline.run(args.source, args.units or None, args.n, batch=args.batch, budget=args.budget)
        print(f"done {len(r['done'])}: {' '.join(r['done'])}; spent ${r['spent']:.2f}")
        for u, step in r["waiting"].items():
            print(f"  {u}: waiting for the {step} batch (`panko llm collect`, then run again)")
        for u, why in r["failed"].items():
            print(f"  {u}: failed at {why}")
    elif args.wcmd == "ingest":
        r = work.ingest_source(args.source)
        print(f"{len(r['units'])} units: {r['new']} new candidates, {r['known']} known (sightings), "
              f"{r['dropped']} dropped, {r['merged']} merged, {len(r['homographs'])} homographs kept apart"
              + (f", {len(r['rejected_again'])} you'd rejected kept out of the inbox" if r.get("rejected_again") else ""))
        if "clips" in r:
            c = r["clips"]
            print(f"  native clips: {c['cut']} cut, {c['kept']} already held"
                  + (f"; not found in the recording: {', '.join(c['not_found'][:12])}" if c["not_found"] else ""))
        for h in r["held"]:
            m = "; ".join(f"{x['id']} {x['ar']} '{x['gloss']}'" for x in h["matches"]) or "-"
            print(f"  held {h['unit']} {h['ar']} '{h.get('gloss', '')}' ~ {m}")
        if r["held"]:
            print("  settle each: panko work decide SOURCE UNIT AR --known ID | --distinct; then ingest again")
    elif args.wcmd == "decide":
        print(work.decide(args.source, args.unit, args.ar, args.known, args.distinct))
    else:
        parser.print_help()


def _llm(args, parser):
    import json

    from panko import lang, llm, prompts
    if args.lcmd == "ping":
        from panko.providers.base import Ask
        p = llm.provider()
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
                  "required": ["ok", "word"], "additionalProperties": False}
        a = Ask(id="ping", system="Answer in JSON.", schema=schema, max_tokens=2000, effort="low",
                parts=[f"Give the {prompts.context()['language']} word for 'water' in {lang.label()}."])
        ans = p.ask(a)
        print(f"{p.name}/{ans.model}: {ans.data if not ans.error else ans.error} · {ans.usage} · ${ans.cost:.5f}")
    elif args.lcmd == "usage":
        print(json.dumps(llm.usage(args.since), indent=1))
    elif args.lcmd == "collect":
        print(json.dumps(llm.collect(), indent=1, ensure_ascii=False))
    else:
        parser.print_help()


def _migrate(args):
    from pathlib import Path

    from panko.anki import migrate

    res = migrate.run(dry_run=not args.apply, ids=args.ids or None)
    if args.apply:
        print({k: v for k, v in res.items() if k != "rows"})
        print("Now open Anki: it will ask for a one-way sync. Choose Upload to AnkiWeb.")
        return
    if args.report:
        Path(args.report).write_text(res["report"] + "\n")
    print(res["report"])
    print(f"\n{sum(1 for r in res['rows'] if r.get('nid'))} notes to convert, "
          f"{sum(1 for r in res['rows'] if not r.get('nid'))} new. Dry run: nothing changed.")


def _draw(pictures, prompts: dict, force: bool, batch: bool):
    if batch:
        bid = pictures.draw_batch(prompts, force=force)
        print(f"submitted batch {bid}; run `panko draw --collect` later (within 24 h)" if bid else "nothing to draw")
        return
    r = pictures.draw(prompts, force=force)
    bad = sum(v.startswith("error") for v in r.values())
    print(f"drew {len(r) - bad}, failed {bad}")


def _pictures(args, parser):
    import json
    from pathlib import Path

    from panko.media import pictures
    from panko.store import Store
    if args.pcmd == "export":
        rows = pictures.export(Store(), status=args.status, batch=args.batch)
        out = Path(args.out)
        k = -(-len(rows) // args.chunks) if rows else 0
        for i in range(args.chunks):
            f = out if args.chunks == 1 else out.with_name(f"{out.stem}-{i + 1}{out.suffix}")
            f.write_text(json.dumps(rows[i * k:(i + 1) * k], ensure_ascii=False, indent=1))
            print(f, len(rows[i * k:(i + 1) * k]))
    elif args.pcmd == "search":
        names = [n.strip() for n in args.providers.split(",") if n.strip()] if args.providers else None
        for p in pictures.search(json.loads(args.queries), Path(args.outdir), names=names):
            print(p)
    elif args.pcmd == "decide":
        from panko.media import choose
        cards = [c for c in pictures.export(Store(), status=args.status, batch=args.batch, ids=args.ids or None)
                 if not args.tag or args.tag in (Store().get(c["id"]) or {}).get("tags", [])]
        if args.estimate:
            print(json.dumps(choose.estimate(cards, args.plans), indent=1))
            return
        r = choose.decide(cards, plan_files=args.plans, searched_dirs=args.searched,
                          search_drawings=not args.no_search_drawings, batch=args.llm_batch, budget=args.budget)
        s = choose.save_decisions(r["decisions"])
        print(f"{len(cards)} cards: {r['counts']}; saved to {choose.decisions_path()} ({s.get('total')} in all)")
        if r["waiting"]:
            print(f"  {len(r['waiting'])} waiting for a batch: `panko llm collect`, then run again")
        print("next: `panko pictures apply` (photos are free; drawings are paid, or `--no-draw` to keep the prompts)")
    elif args.pcmd == "apply":
        from panko.media import choose
        args.paths = args.paths or [str(choose.decisions_path())]
        decisions = {}
        for p in args.paths:
            decisions.update(json.loads(Path(p).read_text()))
        r = pictures.apply(decisions)
        print(f"photos {r['photo']}, skips {r['skip']}, prompts {len(r['prompts'])}, failed photos {r['failed']}")
        if args.no_draw:
            f = Path(args.paths[0]).with_suffix(".prompts.json")
            f.write_text(json.dumps(r["prompts"], ensure_ascii=False, indent=1))
            print("prompts written to", f)
        elif r["prompts"]:
            _draw(pictures, r["prompts"], False, args.batch)
    else:
        parser.print_help()
