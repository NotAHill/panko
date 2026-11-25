"""`panko` command."""
from __future__ import annotations

import argparse


def main(argv=None):
    try:
        _main(argv)
    except FileNotFoundError as e:
        if "panko init" not in str(e):
            raise
        raise SystemExit(str(e)) from None


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="panko")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("providers", help="which providers are ready")
    v = sub.add_parser("voices", help="audition ElevenLabs Moroccan voices")
    v.add_argument("--all", action="store_true")
    sub.add_parser("seed", help="load the hand-written sandbox entries into the store")
    sy = sub.add_parser("sync", help="push active entries to Anki (updates notes in place)")
    sy.add_argument("--dry-run", action="store_true", help="list what would change and the audio still to pay for")
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
    rf = sub.add_parser("refs", help="the reference corpora and dictionaries: show them, download the open ones")
    rf.add_argument("--download", action="store_true", help="fetch the open ones that are missing")
    rf.add_argument("--force", action="store_true", help="with --download: fetch them again even if present")
    mc = sub.add_parser("mcp", help="run Panko as an MCP server for Claude (chat mode, no API key needed)")
    mc.add_argument("--config", action="store_true", help="print the Claude Desktop / Claude Code config instead")
    mc.add_argument("--skill", metavar="DIR", help="write the chat workflow as a Claude skill: DIR/panko/SKILL.md "
                    "(e.g. ~/.claude/skills for Claude Code)")
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

    if args.cmd == "providers":
        from panko import providers
        for cap in ("audio", "images", "llm"):
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
    elif args.cmd == "mcp" and args.skill:
        from panko import skill
        print("wrote", skill.write(args.skill))
    elif args.cmd == "mcp":
        try:
            from panko import mcp_server
        except ImportError:
            ap.error("the MCP server needs the extra: uv sync --extra mcp")
        if args.config:
            print(mcp_server.config_snippet())
        else:
            mcp_server.main()
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
                s.set_status(eid, "retired")
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
        groups = clashes.find(s, None if args.all else [e["id"] for e in s.entries("candidate")])
        if args.estimate:
            print(json.dumps(clashes.estimate(groups), indent=1))
            return
        d = clashes.decide(groups, batch=args.llm_batch, budget=args.budget)
        clashes.save(d, path)
        kinds = {k: sum(1 for v in d.values() if k in v) for k in ("gloss", "cards", "drop")}
        print(f"{len(groups)} groups: {kinds}; saved to {path}. Look it over, then `panko clashes --apply`.")
    elif args.cmd == "pictures":
        _pictures(args, pic)
    else:
        ap.print_help()


def _init(args):
    from panko import setup
    if not args.check and (args.force or not setup.CONFIG.exists()):
        d = dict(setup.DEFAULTS)
        profiles = setup.anki_profiles()
        if profiles:
            d["profile"] = profiles[0]

        def ask(key, q):
            if args.yes:
                return d[key]
            shown = ", ".join(d[key]) if isinstance(d[key], list) else d[key]
            got = input(f"{q} [{shown}]: ").strip()
            return ([x.strip() for x in got.split(",")] if isinstance(d[key], list) else got) if got else d[key]

        answers = {"language": ask("language", "Language your cards teach"),
                   "gloss_language": ask("gloss_language", "Your language (for meanings)"),
                   "varieties": ask("varieties", "Varieties, comma-separated (deck per variety)"),
                   "deck_root": ask("deck_root", "Deck to put them under"),
                   "profile": ask("profile", f"Anki profile{' (found: ' + ', '.join(profiles) + ')' if profiles else ''}"),
                   "translit": ask("translit", "Romanisation to show first"),
                   "wiktionary": ask("wiktionary", "Wiktionary language name for evidence (blank to skip)")}
        print("wrote", setup.write_config(answers, force=args.force))
    elif not args.check:
        print(f"{setup.CONFIG} exists (edit it, or `panko init --force` to start over). Checking what's ready:")
    for what, ok, detail in setup.check():
        print(f"  {'✓' if ok else '✗'} {what:<34} {detail}")


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
              f"{r['dropped']} dropped, {r['merged']} merged, {len(r['homographs'])} homographs kept apart")
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

    from panko import llm
    if args.lcmd == "ping":
        from panko.providers.base import Ask
        p = llm.provider()
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
                  "required": ["ok", "word"], "additionalProperties": False}
        a = Ask(id="ping", system="Answer in JSON.", schema=schema, max_tokens=2000, effort="low",
                parts=["Give the Moroccan Darija word for 'water' in Arabic script."])
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
