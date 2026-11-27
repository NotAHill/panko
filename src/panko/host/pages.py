"""The front door's few pages: sign in, accept an invite, your account, admin. Plain HTML forms, no script, in the
hub's look. Everything shown is escaped with `e()`."""
from __future__ import annotations

import time
from html import escape

from starlette.responses import HTMLResponse

CSS = """
:root { --bg:#090c10; --panel:rgba(17,23,30,.8); --line:rgba(150,180,215,.15); --field:rgba(6,9,13,.6);
  --fg:#e3e9f0; --dim:#9aa7b6; --faint:#7f8b9a; --accent:#6ea8f2; --on-accent:#08111c; --ok:#4fb594; --warn:#e0904a;
  --bad:#ef7b72; --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace; color-scheme: dark; }
@media (prefers-color-scheme: light) { :root { --bg:#eef2f6; --panel:rgba(255,255,255,.85); --line:rgba(30,50,80,.16);
  --field:#fff; --fg:#17202b; --dim:#4b5868; --faint:#5f6b7a; --accent:#2160c4; --on-accent:#fff; --ok:#17604f;
  --warn:#8f4a17; --bad:#b4372e; color-scheme: light; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.6 var(--mono); }
main { max-width: 760px; margin: 0 auto; padding: 40px 16px 64px; }
main.narrow { max-width: 420px; }
header { display:flex; align-items:center; gap:10px; margin-bottom:28px; }
header img { width:32px; height:32px; } header b { font-size:17px; } header .grow { flex:1; }
header a, header button.link { color:var(--dim); text-decoration:none; font:inherit; background:none; border:0; cursor:pointer; padding:0; }
header a:hover, header button.link:hover { color:var(--fg); }
h1 { font-size:20px; margin:0 0 6px; font-weight:600; }
.box { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; margin:16px 0; }
.box > .t { color:var(--dim); font-size:12px; text-transform:lowercase; margin:-4px 0 12px; }
label { display:block; margin:12px 0 4px; color:var(--dim); font-size:12.5px; }
input[type=text], input[type=password], input[type=number] { width:100%; padding:9px 10px; background:var(--field);
  color:var(--fg); border:1px solid var(--line); border-radius:5px; font:inherit; }
input:focus-visible, button:focus-visible, a:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
button, .btn { display:inline-block; padding:8px 14px; border-radius:5px; border:1px solid var(--line);
  background:transparent; color:var(--fg); font:inherit; cursor:pointer; text-decoration:none; }
button.pri, .btn.pri { background:var(--accent); color:var(--on-accent); border-color:var(--accent); }
button.bad { color:var(--bad); }
.acts { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:14px; }
.muted { color:var(--dim); } .faint { color:var(--faint); } .ok { color:var(--ok); } .warn { color:var(--warn); }
.bad-t { color:var(--bad); } .nw { white-space:nowrap; }
.meter { display:inline-block; width:160px; height:8px; border-radius:4px; background:var(--field); border:1px solid var(--line); vertical-align:middle; overflow:hidden; margin-right:8px; }
.meter > i { display:block; height:100%; background:var(--ok); } .meter.near > i { background:var(--warn); } .meter.full > i { background:var(--bad); }
pre.log { white-space:pre-wrap; word-break:break-all; font-size:12px; max-height:240px; overflow:auto; background:var(--field); border:1px solid var(--line); border-radius:4px; padding:8px; margin:6px 0 0; }
.err { color:var(--bad); border:1px solid color-mix(in srgb, var(--bad) 40%, transparent); border-radius:5px;
  padding:8px 10px; margin:12px 0; }
table { width:100%; border-collapse:collapse; font-size:13px; }
td, th { text-align:left; padding:7px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--faint); font-weight:normal; font-size:12px; }
td form { display:inline; }
td button { padding:3px 8px; font-size:12px; }
code, .link-out { word-break: break-all; background:var(--field); border:1px solid var(--line); border-radius:4px;
  padding:2px 6px; }
.link-out { display:block; padding:10px; margin-top:8px; user-select:all; }
@media (max-width: 560px) { .wide { display:none; } }
"""


def e(s) -> str:
    return escape(str(s if s is not None else ""), quote=True)


def page(title: str, body: str, *, user: dict | None = None, narrow: bool = False, status: int = 200,
         form_to: str = "") -> HTMLResponse:
    """`form_to`: one more origin a form here may lead to (the consent page sends the learner back to their app, and
    browsers check a form's redirect against form-action)."""
    nav = ""
    if user:
        nav = ('<a href="/">your Panko</a><a href="/host/account">account</a>'
               + ('<a href="/host/admin">admin</a>' if user.get("admin") else "")
               + '<form method="post" action="/host/logout" style="display:inline">'
                 '<button class="link">sign out</button></form>')
    html = (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
            f'initial-scale=1"><title>{e(title)} · Panko</title><link rel="icon" href="/host/logo.svg">'
            f'<style>{CSS}</style><body><main class="{"narrow" if narrow else ""}"><header>'
            f'<img src="/host/logo.svg" alt=""><b>panko</b><span class="grow"></span>'
            f'<nav style="display:flex;gap:16px;align-items:center">{nav}</nav></header>{body}</main></body></html>')
    return HTMLResponse(html, status, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                               "Referrer-Policy": "same-origin",
                                               "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; "
                                               f"img-src 'self'; form-action 'self'{' ' + form_to if form_to else ''}; "
                                               "frame-ancestors 'none'"})


def ago(t: float | None) -> str:
    if not t:
        return "never"
    s = time.time() - t
    for unit, n in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if s >= n:
            k = int(s // n)
            return f"{k} {unit}{'s' if k != 1 else ''} ago"
    return "just now"


def quota_line(used: int, quota_gb: float) -> tuple[str, str]:
    """(level, HTML) for a Panko's disk use against its quota: a small bar, the numbers, a word when near or full."""
    from panko.config import QUOTA_NEAR
    frac = used / (quota_gb * 1e9) if quota_gb else 1
    level = "full" if frac >= 1 else "near" if frac >= QUOTA_NEAR else "ok"
    word = {"full": ' <span class="bad-t">full</span>', "near": ' <span class="warn">nearly full</span>'}.get(level, "")
    return level, (f'<span class="meter {level}" role="img" aria-label="{min(frac, 1):.0%}"><i style="width:{min(frac, 1) * 100:.1f}%"></i></span>'
                   f'{size(used)} of {quota_gb:g} GB{word}')


def size(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    return f"{n / 1e6:.0f} MB" if n >= 1e6 else "under 1 MB"
