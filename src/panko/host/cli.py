"""`panko host …`: run the front door, make an invite (the first admin's too), list people, purge deleted folders.

The data folder is `--data`, else `PANKO_HOST_DATA`, else /srv/panko. Settings for `serve` come from flags or the
environment (Compose sets them): PANKO_HOST_URL (the public address, for invite links), PANKO_QUOTA_GB,
PANKO_UPLOAD_MB, PANKO_IDLE_MINUTES."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def add_parser(sub) -> None:
    h = sub.add_parser("host", help="the front door of a hosted Panko: serve, invite, users, purge "
                       "(needs: uv sync --extra host; see docs/SPEC-hosted.md)")
    h.add_argument("--data", default=os.environ.get("PANKO_HOST_DATA", "/srv/panko"),
                   help="the front door's data folder (users' Panko folders, sockets, logs, host.db)")
    hs = h.add_subparsers(dest="hcmd")
    sv = hs.add_parser("serve", help="run the front door (Caddy in front gives it HTTPS)")
    sv.add_argument("--bind", default=os.environ.get("PANKO_HOST_BIND", "127.0.0.1"))
    sv.add_argument("--port", type=int, default=int(os.environ.get("PANKO_HOST_PORT", "8800")))
    sv.add_argument("--url", default=os.environ.get("PANKO_HOST_URL", ""), help="the public address, e.g. "
                    "https://yourname.duckdns.org (invite links use it)")
    sv.add_argument("--quota-gb", type=float, default=float(os.environ.get("PANKO_QUOTA_GB") or 5))
    sv.add_argument("--upload-mb", type=float, default=float(os.environ.get("PANKO_UPLOAD_MB") or 500))
    sv.add_argument("--idle", type=float, default=float(os.environ.get("PANKO_IDLE_MINUTES") or 20),
                    help="minutes before an idle user's Panko is stopped")
    sv.add_argument("--proxy", default=os.environ.get("PANKO_TRUSTED_PROXY", "127.0.0.1"),
                    help="the address of the proxy in front (Caddy) whose X-Forwarded-* headers are trusted")
    iv = hs.add_parser("invite", help="print an invite link that works once (use --admin for the first account)")
    iv.add_argument("--admin", action="store_true")
    iv.add_argument("--days", type=float, default=7)
    iv.add_argument("--note", default="")
    iv.add_argument("--url", default=os.environ.get("PANKO_HOST_URL", ""))
    hs.add_parser("users", help="the accounts, their disk use and when they were last seen")
    pg = hs.add_parser("purge", help="remove deleted accounts' folders for good")
    pg.add_argument("--days", type=float, default=0, help="only those deleted at least this many days ago")


def run(args, ap) -> None:
    try:
        import argon2  # noqa: F401
        import starlette  # noqa: F401

        from panko.host.store import HostStore
    except ImportError:
        ap.error("the front door needs the extra: uv sync --extra host")
    data = Path(args.data).expanduser().resolve()
    if args.hcmd == "serve":
        import uvicorn

        from panko.host.app import app
        a = app(data, idle_minutes=args.idle, quota_gb=args.quota_gb, upload_mb=args.upload_mb, base_url=args.url)
        print(f"✻ Panko front door on http://{args.bind}:{args.port} (data in {data})", flush=True)
        uvicorn.run(a, host=args.bind, port=args.port, log_level="warning", proxy_headers=True,
                    forwarded_allow_ips=args.proxy)
    elif args.hcmd == "invite":
        st = HostStore(data / "host.db")
        token = st.invite(admin=args.admin, days=args.days, note=args.note)
        base = (args.url or "http://127.0.0.1:8800").rstrip("/")
        print(f"{base}/host/invite/{token}\n  works once, for {args.days:g} days"
              + (", for an admin account" if args.admin else ""))
    elif args.hcmd == "users":
        from panko.host.app import _du
        from panko.host.pages import ago, size
        st = HostStore(data / "host.db")
        us = st.users()
        if not us:
            print("no accounts yet: `panko host invite --admin` makes the first")
        for u in us:
            flags = ", ".join(f for f, on in (("admin", u["admin"]), ("disabled", u["disabled"])) if on)
            print(f"{u['name']:<20} {size(_du(data / 'users' / u['id'])):>8}  last seen {ago(u['last_seen'])}"
                  + (f"  ({flags})" if flags else ""))
    elif args.hcmd == "purge":
        d = data / "deleted"
        gone = 0
        for p in sorted(d.iterdir()) if d.exists() else []:
            if time.time() - p.stat().st_mtime >= args.days * 86400:
                shutil.rmtree(p)
                gone += 1
        print(f"removed {gone} deleted folder{'s' if gone != 1 else ''} for good")
    else:
        ap.parse_args(["host", "--help"])
