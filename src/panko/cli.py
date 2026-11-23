"""`panko` command."""
from __future__ import annotations

import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(prog="panko")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("providers", help="which providers are ready")
    v = sub.add_parser("voices", help="audition ElevenLabs Moroccan voices")
    v.add_argument("--all", action="store_true")
    sub.add_parser("seed", help="load the hand-written sandbox entries into the store")
    sub.add_parser("sync", help="push active entries to Anki (updates notes in place)")
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
        from panko.anki.sync import sync
        sync()
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
        for p in pictures.search(json.loads(args.queries), Path(args.outdir)):
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
