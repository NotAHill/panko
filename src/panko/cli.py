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
    wa = wsub.add_parser("add", help="register a PDF, a folder of page photos, a text transcript or an exported deck (.json)")
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
    pa = psub.add_parser("apply", help="apply decisions: download photos, then draw the prompts")
    pa.add_argument("paths", nargs="+")
    pa.add_argument("--batch", action="store_true", help="draw as an OpenAI batch instead of now")
    pa.add_argument("--no-draw", action="store_true", help="only download photos; write prompts to a file")
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
                            page_offset=args.page_offset, first=args.first, last=args.last)
        print(f"{s['id']}: {len(s['units'])} units ({s['units'][0]}…{s['units'][-1]})")
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
    elif args.pcmd == "apply":
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
