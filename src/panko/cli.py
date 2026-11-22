"""`panko` command. Subcommands grow as phases land."""
from __future__ import annotations

import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd, rest = (argv[0], argv[1:]) if argv else ("help", [])
    if cmd == "sandbox":
        from panko.sandbox.build import main as run
        return run(rest)
    if cmd == "voices":
        from panko.media.audition import run
        return run(all_voices="--all" in rest)
    if cmd == "providers":
        from panko import providers
        for cap in ("audio", "images"):
            ready = [p.name for p in providers.chain(cap)]
            print(f"{cap}: available={providers.available(cap)} ready-in-chain-order={ready}")
        return 0
    print("usage: panko sandbox [--reset] | panko providers | panko voices [--all]")
    return 0
