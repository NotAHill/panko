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
    sub.add_parser("inbox", help="list candidates waiting to become cards")
    a = sub.add_parser("activate", help="turn candidates into cards on next sync")
    a.add_argument("ids", nargs="*")
    a.add_argument("--batch", type=int)
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
        from panko.ingest import ingest
        r = ingest(args.path)
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
    else:
        ap.print_help()
