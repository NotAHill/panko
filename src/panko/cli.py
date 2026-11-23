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
    sub.add_parser("inbox", help="list candidates waiting to become cards")
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
    args = ap.parse_args(argv)

    if args.cmd == "providers":
        from panko import providers
        for cap in ("audio", "images"):
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
        from panko.store import Store
        for e in Store().entries("candidate"):
            pic = "pic" if e.get("image") else "   "
            print(f"{e['id']}  {pic}  b{e.get('batch', '-')}  {e['ar']:<28} {e.get('tl', ''):<24} {e.get('gloss', '')}")
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
    elif args.cmd == "pictures":
        _pictures(args, pic)
    else:
        ap.print_help()


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
