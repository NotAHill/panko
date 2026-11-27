"""The front door: sign-in, invites, accounts and admin under /host/, and everything else proxied to the signed-in
user's own Panko over its Unix socket.

Changes are guarded twice: the session cookie is SameSite=Lax, and every POST must come from this site's own pages
(Origin, else Referer). The user's Panko never sees the session cookie, and can't set cookies here.

Chat mode (host/oauth.py): `/mcp` takes an OAuth access token, never the cookie, and passes the call to the user's
Panko; `/authorize`, `/token`, `/register`, `/revoke` and the two `.well-known` documents let their Claude get one."""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Route

from panko.host import oauth
from panko.host.oauth import OAuth, OAuthError
from panko.host.pages import ago, e, page, quota_line
from panko.host.pankos import Pankos
from panko.host.store import HostStore
from panko.host.watch import Watch, checks

COOKIE = "panko_session"
HOP = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization", b"te", b"trailer",
       b"transfer-encoding", b"upgrade", b"host", b"cookie", b"authorization", b"x-panko-front", b"forwarded", b"x-forwarded-for",
       b"x-forwarded-host", b"x-forwarded-proto", b"x-real-ip"}
DROP_BACK = {b"connection", b"keep-alive", b"transfer-encoding", b"set-cookie", b"server", b"date"}
LOGO = Path(__file__).resolve().parents[1] / "hub" / "static" / "logo.svg"
FAILS: dict[str, list[float]] = {}
FAIL_LIMIT, FAIL_WINDOW = 5, 900
REGISTERED: dict[str, list[float]] = {}
REGISTER_LIMIT = 30          # client registrations per address per hour (anyone can register; few need to)
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Protocol-Version, Mcp-Session-Id, "
                                        "Last-Event-ID",
        "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id, Mcp-Protocol-Version",
        "Access-Control-Max-Age": "600"}


class Door:
    def __init__(self, data: Path, *, idle_minutes: float = 20, quota_gb: float = 5, upload_mb: float = 500,
                 base_url: str = ""):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        os.chmod(self.data, 0o700)
        self.store = HostStore(self.data / "host.db")
        self.oauth = OAuth(self.store)
        self.base_url = base_url.rstrip("/")
        self.watch = Watch(self.data, self.store.db)
        self.pankos = Pankos(self.data, idle_minutes=idle_minutes, quota_gb=quota_gb, upload_mb=upload_mb,
                             base_url=self.base_url, notify=self.watch.note)
        self.clients: dict[str, httpx.AsyncClient] = {}

    # ---- helpers
    def user(self, req: Request) -> dict | None:
        return self.store.session_user(req.cookies.get(COOKIE, ""))

    def link(self, req: Request, path: str) -> str:
        return (self.base_url or f"{req.url.scheme}://{req.url.netloc}") + path

    async def client(self, uid: str, sock: Path, secret: str) -> httpx.AsyncClient:
        key = f"{uid}:{secret}"
        c = self.clients.get(key)
        if not c:
            for k in [k for k in self.clients if k.startswith(uid + ":")]:   # an old process's client
                await self.clients.pop(k).aclose()
            c = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(sock)), base_url="http://panko",
                                  timeout=httpx.Timeout(30, read=900, write=900))
            self.clients[key] = c
        return c


def same_site(req: Request) -> bool:
    """A POST from this site's own pages: Origin (or Referer) names this host."""
    here = req.headers.get("host", "")
    src = req.headers.get("origin") or req.headers.get("referer") or ""
    return bool(src) and urlsplit(src).netloc == here


def throttled(key: str) -> bool:
    now = time.time()
    FAILS[key] = [t for t in FAILS.get(key, []) if now - t < FAIL_WINDOW]
    return len(FAILS[key]) >= FAIL_LIMIT


def failed(*keys: str) -> None:
    for k in keys:
        FAILS.setdefault(k, []).append(time.time())


def with_session(resp: Response, req: Request, token: str) -> Response:
    resp.set_cookie(COOKIE, token, max_age=30 * 86400, httponly=True, samesite="lax", path="/",
                    secure=req.url.scheme == "https")
    return resp


def safe_next(n: str) -> str:
    return n if n.startswith("/") and not n.startswith("//") and not n.startswith("/\\") else "/"


def app(data: Path | str, **opts) -> Starlette:
    door = Door(Path(data), **opts)

    # ---- sign in / out
    async def login(req: Request):
        nxt = safe_next(req.query_params.get("next", "/"))
        if req.method == "GET":
            if door.user(req):
                return RedirectResponse(nxt, 303)
            return login_page(nxt)
        if not same_site(req):
            return page("sign in", '<p class="err">Sign in from this site\'s own page.</p>', narrow=True, status=403)
        form = await req.form()
        name, pw = str(form.get("name", "")).strip().lower(), str(form.get("password", ""))
        ip = req.client.host if req.client else "?"
        if throttled(f"n:{name}") or throttled(f"ip:{ip}"):
            return login_page(nxt, "Too many tries. Wait 15 minutes and try again.", name, 429)
        u = await asyncio.to_thread(door.store.check, name, pw)
        if not u:
            failed(f"n:{name}", f"ip:{ip}")
            return login_page(nxt, "That name and password don't match.", name, 401)
        FAILS.pop(f"n:{name}", None)
        token = door.store.start_session(u["id"], req.headers.get("user-agent", ""))
        return with_session(RedirectResponse(nxt, 303), req, token)

    def login_page(nxt: str, err: str = "", name: str = "", status: int = 200):
        return page("sign in", f"""<h1>sign in</h1><p class="muted">Panko is invite-only. Ask whoever runs it for an
            invite link.</p>{f'<p class="err">{e(err)}</p>' if err else ''}
            <form method="post" action="/host/login?next={quote(nxt)}" class="box">
            <label for="n">name</label><input id="n" type="text" name="name" value="{e(name)}" autocomplete="username"
            autocapitalize="none" required autofocus>
            <label for="p">password</label><input id="p" type="password" name="password" autocomplete="current-password" required>
            <div class="acts"><button class="pri">sign in</button></div></form>
            <p class="faint">No account? <a href="/host/install">Run Panko on your own computer</a> instead: free, no
            sign-up, your cards stay with you.</p>""", narrow=True, status=status)

    async def logout(req: Request):
        if not same_site(req):
            return RedirectResponse("/", 303)
        door.store.end_session(req.cookies.get(COOKIE, ""))
        r = RedirectResponse("/host/login", 303)
        r.delete_cookie(COOKIE, path="/")
        return r

    # ---- invites
    async def invite(req: Request):
        token = req.path_params["token"]
        inv = door.store.invite_ok(token)
        if not inv:
            return page("invite", '<h1>invite</h1><p class="err">This invite has expired or was used already. Ask for '
                        'a new one.</p>', narrow=True, status=404)
        err, name = "", ""
        if req.method == "POST":
            if not same_site(req):
                return page("invite", '<p class="err">Use the form on this page.</p>', narrow=True, status=403)
            form = await req.form()
            name, pw, pw2 = str(form.get("name", "")).strip().lower(), str(form.get("password", "")), \
                str(form.get("password2", ""))
            if pw != pw2:
                err = "The two passwords aren't the same."
            else:
                try:
                    u = await asyncio.to_thread(door.store.accept, token, name, pw)
                except ValueError as ex:
                    err = str(ex)
                else:
                    t = door.store.start_session(u["id"], req.headers.get("user-agent", ""))
                    return with_session(RedirectResponse("/", 303), req, t)
        return page("invite", f"""<h1>welcome to Panko</h1><p class="muted">Pick a name and a password for your
            account{' (an admin account)' if inv['admin'] else ''}. Your cards, sources and keys stay in your own folder
            on this server.</p>{f'<p class="err">{e(err)}</p>' if err else ''}
            <form method="post" class="box">
            <label for="n">name <span class="faint">letters, digits, - or _</span></label>
            <input id="n" type="text" name="name" value="{e(name)}" autocomplete="username" autocapitalize="none"
              pattern="[a-z0-9][a-z0-9_\\-]{{1,31}}" required autofocus>
            <label for="p">password <span class="faint">10 characters or more</span></label>
            <input id="p" type="password" name="password" autocomplete="new-password" minlength="10" required>
            <label for="p2">the same password again</label>
            <input id="p2" type="password" name="password2" autocomplete="new-password" minlength="10" required>
            <div class="acts"><button class="pri">make my account</button></div></form>
            <p class="faint">What's kept and who can see it: <a href="/host/privacy">privacy</a>.</p>""",
                    narrow=True)

    async def privacy(req: Request):
        return page("privacy", PRIVACY, user=door.user(req))

    async def install(req: Request):
        """For people without an account (or who'd rather not have one): Panko on their own computer."""
        from panko import INSTALL, SOURCE, UPGRADE
        return page("on your own computer", INSTALL_PAGE.format(install=e(INSTALL), upgrade=e(UPGRADE),
                                                                source=e(SOURCE)), user=door.user(req))

    async def addon(req: Request):
        """The Panko sync add-on, for anyone: it does nothing until it's given a Panko's address and code."""
        from panko.anki.addon import NAME, addon_zip
        return Response(await asyncio.to_thread(addon_zip), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{NAME}"', "Cache-Control": "no-store"})

    # ---- your account
    async def account(req: Request, fresh: str | None = None):
        u = door.user(req)
        if not u:
            return RedirectResponse("/host/login?next=/host/account", 303)
        msg = ""
        if req.method == "POST" and fresh is None:
            if not same_site(req):
                return page("account", '<p class="err">Use the form on this page.</p>', user=u, status=403)
            form = await req.form()
            old, new, new2 = (str(form.get(k, "")) for k in ("old", "new", "new2"))
            if not await asyncio.to_thread(door.store.check, u["name"], old):
                msg = '<p class="err">Your current password isn\'t right.</p>'
            elif new != new2:
                msg = '<p class="err">The two new passwords aren\'t the same.</p>'
            else:
                try:
                    await asyncio.to_thread(door.store.set_password, u["id"], new)
                except ValueError as ex:
                    msg = f'<p class="err">{e(ex)}</p>'
                else:
                    t = door.store.start_session(u["id"], req.headers.get("user-agent", ""))
                    return with_session(page("account", '<h1>account</h1><p class="ok">✔ Password changed. You\'re '
                                             'signed out everywhere else.</p><p><a href="/">back to your Panko</a></p>',
                                             user=u), req, t)
        used = await asyncio.to_thread(_du, door.pankos.home(u["id"]))
        quota = u["quota_gb"] or door.pankos.quota_gb
        mcp_url = door.link(req, "/mcp")
        conns = "".join(f"""<tr><td><b>{e(g['client_name'] or 'an app')}</b></td><td class="wide">connected
            {ago(g['created'])}</td><td>used {ago(g['last_used'])}</td><td><form method="post"
            action="/host/account/connection/{e(g['id'])}"><button>end</button></form></td></tr>"""
                        for g in door.oauth.grants(u["id"]))
        devices = "".join(f"""<tr><td><b>{e(d['name'])}</b></td><td class="wide">made {ago(d['created'])}</td>
            <td>{'synced ' + ago(d['last_used']) if d['last_used'] else '<span class="faint">not used yet</span>'}</td>
            <td><form method="post" action="/host/account/anki/{e(d['id'])}"><button>end</button></form></td></tr>"""
                          for d in door.store.devices(u["id"]))
        code = f"""<p class="ok">✔ Made. Copy the code now: it isn't shown again.</p><span class="link-out">{e(fresh)}</span>""" \
            if fresh else ""
        anki = f"""<section class="box" id="anki"><div class="t">Anki: the Panko sync add-on</div>
            <p>Your cards go into Anki on your computer through a small add-on: it adds and updates your Panko cards
            and never touches your review history or your MyNotes field.</p>
            <p>1. <a class="btn" href="/addon/panko-sync.ankiaddon">download the add-on</a> and open the file (or in
            Anki: Tools → Add-ons → Install from file), then restart Anki.<br>
            2. Make a device code for that computer here. In Anki, open Tools → Panko: settings… and paste this
            address and the code:</p><span class="link-out">{e(base(req))}</span>
            {code}
            <form method="post" action="/host/account/anki" class="acts"><input type="text" name="name" maxlength="60"
              placeholder="which computer, e.g. my laptop" aria-label="which computer" style="flex:1">
              <button class="pri">make a device code</button></form>
            <p>3. Tools → Panko: sync now. Then sync Anki as usual: your phone gets the cards through AnkiWeb.</p>
            {f'<table><tr><th>computers</th><th class="wide"></th><th></th><th></th></tr>{devices}</table>'
             if devices else ''}</section>"""
        return page("account", f"""<h1>account</h1><p class="muted">Signed in as <b>{e(u['name'])}</b>.</p>{msg}
            {anki}
            <section class="box"><div class="t">chat mode: your Claude reads the sources</div>
            <p>Add Panko to your own Claude as a connector, at this address:</p><span class="link-out">{e(mcp_url)}</span>
            <p class="muted"><b>claude.ai or Claude Desktop:</b> in Settings, under Connectors, add a custom connector
            with this address, then connect and allow it here.<br><b>Claude Code:</b>
            <code>claude mcp add --transport http panko {e(mcp_url)}</code>, then <code>/mcp</code> to sign in.</p>
            <p class="faint">Your Claude does the reading on your own plan; Panko spends nothing for it.</p>
            {f'<table><tr><th>connected apps</th><th class="wide"></th><th></th><th></th></tr>{conns}</table>'
             if conns else '<p class="faint">Nothing connected yet.</p>'}</section>
            <section class="box"><div class="t">your data</div><p>{quota_line(used, quota)[1]}</p>
            {'<p class="muted">Steps that add files (downloads, audio, pictures, Anki packages) wait until there is room. In your Panko, setup → disk shows what takes room and empties what can be made again for free; the admin can give you more.</p>' if quota_line(used, quota)[0] == 'full' else '<p class="muted">In your Panko, setup → disk shows what takes room.</p>' if quota_line(used, quota)[0] == 'near' else ''}
            <div class="acts"><a class="btn" href="/host/account/export">download everything (zip)</a></div>
            <p class="faint">Your config, keys, cards, sources and media, as a folder you can open with Panko on your own
            computer (<code>PANKO_HOME</code>). To delete your account, ask the admin.</p></section>
            <form method="post" class="box"><div class="t">change your password</div>
            <label for="o">current password</label><input id="o" type="password" name="old" autocomplete="current-password" required>
            <label for="n1">new password</label><input id="n1" type="password" name="new" autocomplete="new-password" minlength="10" required>
            <label for="n2">the new one again</label><input id="n2" type="password" name="new2" autocomplete="new-password" minlength="10" required>
            <div class="acts"><button class="pri">change it</button></div></form>""", user=u)

    async def account_device(req: Request):
        u = door.user(req)
        if not u or not same_site(req):
            return RedirectResponse("/host/account", 303)
        form = await req.form()
        return await account(req, fresh=door.store.add_device(u["id"], str(form.get("name", ""))))

    async def end_device(req: Request):
        u = door.user(req)
        if u and same_site(req):
            door.store.end_device(req.path_params["did"], u["id"])
        return RedirectResponse("/host/account#anki", 303)

    async def account_export(req: Request):
        u = door.user(req)
        if not u:
            return RedirectResponse("/host/login", 303)
        return await export_zip(u)

    async def export_zip(u: dict):
        path = await asyncio.to_thread(_zip, door.pankos.home(u["id"]), door.data / "tmp")
        return FileResponse(path, filename=f"panko-{u['name']}-{time.strftime('%Y-%m-%d')}.zip",
                            media_type="application/zip", background=BackgroundTask(path.unlink, missing_ok=True))

    # ---- admin
    def admin_only(req: Request) -> dict | None:
        u = door.user(req)
        return u if u and u["admin"] else None

    async def health_box(users: list[dict], disk: dict[str, int]) -> str:
        w = door.watch
        c = await asyncio.to_thread(checks, door.data, door.store.db)
        d = c["disk"]
        names = {x["id"]: x["name"] for x in users}
        failed = await asyncio.to_thread(w.failed_jobs, list(names), time.time() - 86400)
        tight = [(x["name"], lvl) for x in users if not x["disabled"]
                 for lvl in [quota_line(disk[x["id"]], x["quota_gb"] or door.pankos.quota_gb)[0]] if lvl != "ok"]
        disk_line = ("<span class=\"bad-t\">nearly full</span>" if d.get("low") else "<span class=\"ok\">fine</span>") + (
            f" · {d['free_gb']:g} GB free of {d['total_gb']:g} GB ({d['used_pct']:g}% used)" if "free_gb" in d else "")
        evs = "".join(f"""<tr><td class="nw faint">{ago(x['at'])}</td><td>{e(names.get(x['user_id'] or '', ''))}</td>
            <td>{e(x['text'])}{f'<details><summary class="faint">its last log lines</summary><pre class="log">{e(x["detail"])}</pre></details>' if x['detail'] else ''}</td></tr>"""
                      for x in w.events(15))
        return f"""<section class="box"><div class="t">health</div>
            <p>disk: {disk_line}<br>database: {'<span class="ok">fine</span>' if c['db'] else '<span class="bad-t">not answering</span>'}
            <br>front door started {ago(w.started)} · {len(door.pankos.running)} Panko{'s' if len(door.pankos.running) != 1 else ''} running
            {'<br>jobs failed in the last day: ' + ', '.join(f'{e(names.get(u, u))} {k}' for u, k in failed.items()) if failed else ''}
            {'<br>near their disk limit: ' + ', '.join(f'{e(n)} ({"full" if lvl == "full" else "nearly full"})' for n, lvl in tight) if tight else ''}</p>
            <p class="muted">{'Alerts go to the address in <code>PANKO_ALERT_URL</code>.' if w.alert_url else 'Alerts are off: set <code>PANKO_ALERT_URL</code> in <code>deploy/.env</code> (an ntfy.sh topic works) to hear about these on your phone.'}
            An outside check of <code>/host/health</code> tells you when the whole server is down: see <code>deploy/README.md</code>.</p>
            {f'<table><tr><th class="nw">when</th><th>who</th><th>what happened</th></tr>{evs}</table>' if evs else '<p class="faint">Nothing has happened yet.</p>'}</section>"""

    async def admin(req: Request, note: str = ""):
        a = admin_only(req)
        if not a:
            return page("admin", '<p class="err">Only an admin can open this.</p>', user=door.user(req), status=403)
        users = door.store.users()
        disk = await asyncio.to_thread(lambda: {x["id"]: _du(door.pankos.home(x["id"])) for x in users})
        rows = "".join(f"""<tr><td><b>{e(x['name'])}</b>{' <span class="faint">admin</span>' if x['admin'] else ''}
            {' <span class="warn">disabled</span>' if x['disabled'] else ''}</td>
            <td class="nw">{quota_line(disk[x['id']], x['quota_gb'] or door.pankos.quota_gb)[1]}</td>
            <td class="wide">{ago(x['last_seen'])}{' <span class="ok">· running</span>' if door.pankos.alive(x['id']) else ''}</td>
            <td><a class="btn" style="padding:3px 8px;font-size:12px" href="/host/admin/user/{x['id']}">manage</a></td></tr>"""
                       for x in users)
        invites = "".join(f"""<tr><td>{e(i['note']) or '<span class="faint">no note</span>'}{' <span class="faint">admin</span>' if i['admin'] else ''}</td>
            <td class="wide">{ago(i['created'])}</td><td>{'<span class="ok">used</span>' if i['used_by'] else
            ('<span class="faint">expired</span>' if i['expires'] < time.time() else 'open, until ' + time.strftime('%d %b', time.localtime(i['expires'])))}</td>
            <td>{'' if i['used_by'] or i['expires'] < time.time() else f'<form method="post" action="/host/admin/withdraw/{i["n"]}"><button>withdraw</button></form>'}</td></tr>"""
                          for i in door.store.invites()[:30])
        return page("admin", f"""<h1>admin</h1>{note}{await health_box(users, disk)}
            <section class="box"><div class="t">people</div><table><tr><th>name</th><th>disk</th><th class="wide">last seen</th><th></th></tr>{rows}</table></section>
            <form method="post" action="/host/admin/invite" class="box"><div class="t">invite someone</div>
            <p class="muted">Makes a link that works once, for 7 days. Send it to them yourself.</p>
            <label for="nt">note <span class="faint">who it's for, only you see it</span></label><input id="nt" type="text" name="note" maxlength="200">
            <label style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type="checkbox" name="admin" value="1"> an admin account</label>
            <div class="acts"><button class="pri">make the link</button></div></form>
            {f'<section class="box"><div class="t">invites</div><table>{invites}</table></section>' if invites else ''}""",
                    user=a)

    async def admin_invite(req: Request):
        a = admin_only(req)
        if not a or not same_site(req):
            return page("admin", '<p class="err">Not allowed.</p>', status=403)
        form = await req.form()
        token = door.store.invite(admin=form.get("admin") == "1", note=str(form.get("note", "")), by=a["id"])
        url = door.link(req, f"/host/invite/{token}")
        return await admin(req, f"""<section class="box"><div class="t">invite link</div><p class="ok">✔ Made. Copy
            it now: it isn't shown again.</p><span class="link-out">{e(url)}</span></section>""")

    async def admin_withdraw(req: Request):
        if not admin_only(req) or not same_site(req):
            return page("admin", '<p class="err">Not allowed.</p>', status=403)
        door.store.withdraw(int(req.path_params["n"]))
        return RedirectResponse("/host/admin", 303)

    async def admin_user(req: Request):
        a = admin_only(req)
        uid = req.path_params["uid"]
        x = door.store.user(uid)
        if not a or not x:
            return page("admin", '<p class="err">Not allowed.</p>', user=door.user(req), status=403)
        note = ""
        if req.method == "POST":
            if not same_site(req):
                return page("admin", '<p class="err">Use the form on this page.</p>', user=a, status=403)
            form = await req.form()
            act = form.get("do")
            if act in ("disable", "enable") and uid != a["id"]:
                door.store.update(uid, disabled=int(act == "disable"))
                if act == "disable":
                    door.pankos.stop(uid)
            elif act in ("admin", "not-admin") and uid != a["id"]:
                door.store.update(uid, admin=int(act == "admin"))
            elif act == "quota":
                try:
                    q = float(form.get("quota") or 0)
                except ValueError:
                    q = 0
                door.store.update(uid, quota_gb=q if q > 0 else None)
                door.pankos.stop(uid)                         # the new quota applies when it starts again
            elif act == "stop":
                door.pankos.stop(uid)
            elif act == "delete" and uid != a["id"]:
                if str(form.get("confirm", "")).strip().lower() != x["name"]:
                    note = '<p class="err">Type their name to delete the account.</p>'
                else:
                    door.pankos.stop(uid)
                    where = await asyncio.to_thread(_remove, door, uid)
                    door.store.remove_user(uid)
                    return await admin(req, f'<p class="ok">✔ Deleted {e(x["name"])}. Their folder is in '
                                            f'<code>{e(where)}</code> until <code>panko host purge</code>.</p>')
            if not note:
                return RedirectResponse(f"/host/admin/user/{uid}", 303)
        x = door.store.user(uid)
        me = uid == a["id"]
        return page(x["name"], f"""<h1>{e(x['name'])}</h1><p class="muted">Joined {ago(x['created'])}, last seen
            {ago(x['last_seen'])}. {'Running now.' if door.pankos.alive(uid) else 'Not running.'}</p>{note}
            <section class="box"><div class="t">account</div><div class="acts">
            {'' if me else f'<form method="post"><button name="do" value="{"enable" if x["disabled"] else "disable"}">{"enable" if x["disabled"] else "disable"}</button></form>'}
            {'' if me else f'<form method="post"><button name="do" value="{"not-admin" if x["admin"] else "admin"}">{"remove admin" if x["admin"] else "make admin"}</button></form>'}
            {'<form method="post"><button name="do" value="stop">stop their Panko</button></form>' if door.pankos.alive(uid) else ''}
            <a class="btn" href="/host/admin/export/{uid}">download their folder (zip)</a></div></section>
            <form method="post" class="box"><div class="t">disk quota</div>
            <label for="q">GB <span class="faint">empty for the server's default ({door.pankos.quota_gb:g} GB)</span></label>
            <input id="q" type="number" step="0.5" min="0" name="quota" value="{x['quota_gb'] or ''}">
            <div class="acts"><button name="do" value="quota">save</button></div></form>
            {'' if me else f'''<form method="post" class="box"><div class="t">delete</div><p class="muted">Signs them out, stops their Panko and moves their
            folder aside; <code>panko host purge</code> removes it for good. Download it first if they want a copy.</p>
            <label for="c">type <b>{e(x['name'])}</b> to confirm</label><input id="c" type="text" name="confirm" autocomplete="off">
            <div class="acts"><button class="bad" name="do" value="delete">delete the account</button></div></form>'''}
            <p><a href="/host/admin">← admin</a></p>""", user=a)

    async def admin_export(req: Request):
        x = door.store.user(req.path_params["uid"])
        if not admin_only(req) or not x:
            return page("admin", '<p class="err">Not allowed.</p>', status=403)
        return await export_zip(x)

    async def logo(req: Request):
        return FileResponse(LOGO, media_type="image/svg+xml", headers={"Cache-Control": "max-age=86400"})

    async def health(req: Request):
        """For an outside check: 503 when the disk is nearly full or the database doesn't answer. Says no more than
        that (no names, no sizes)."""
        c = await asyncio.to_thread(checks, door.data, door.store.db)
        return JSONResponse({"ok": c["ok"], "running": len(door.pankos.running),
                             "disk": "low" if c["disk"].get("low") else "ok", "db": "ok" if c["db"] else "error"},
                            status_code=200 if c["ok"] else 503)

    # ---- everything else: the user's own Panko
    async def proxy(req: Request):
        u = door.user(req)
        path = req.url.path
        if not u:
            if path.startswith(("/api/", "/media/", "/export/")):
                return JSONResponse({"error": "signed out: sign in again"}, 401)
            return RedirectResponse("/host/login" + (f"?next={quote(path)}" if path != "/" else ""), 303)
        if req.method not in ("GET", "HEAD") and not same_site(req):
            return JSONResponse({"error": "not from this site"}, 403)
        try:
            r = await door.pankos.ensure(u["id"], u["quota_gb"])
        except RuntimeError as ex:
            return page("starting", f'<p class="err">{e(ex)}</p>', user=u, status=503)
        if time.time() - (u["last_seen"] or 0) > 60:
            door.store.seen(u["id"])
        return await forward(req, u, r, path)

    async def forward(req: Request, u: dict, r, path: str, extra: dict | None = None):
        c = await door.client(u["id"], r.sock, r.secret)
        headers = [(k, v) for k, v in req.headers.raw if k.lower() not in HOP]
        headers.append((b"x-panko-front", r.secret.encode()))
        body = req.stream() if req.method in ("POST", "PUT", "PATCH", "DELETE") else None
        url = path + (f"?{req.url.query}" if req.url.query else "")
        try:
            up = await c.send(c.build_request(req.method, url, headers=headers, content=body), stream=True)
        except httpx.HTTPError:
            door.pankos.stop(u["id"])
            return JSONResponse({"error": "your Panko didn't answer: it's restarting, try again"}, 502)
        back = [(k, v) for k, v in up.headers.raw if k.lower() not in DROP_BACK]
        back.append((b"x-frame-options", b"SAMEORIGIN"))
        back += [(k.lower().encode(), v.encode()) for k, v in (extra or {}).items()]
        resp = StreamingResponse(up.aiter_raw(), up.status_code, background=BackgroundTask(up.aclose))
        resp.raw_headers = back
        return resp

    # ---- chat mode: OAuth for the learner's own Claude, and /mcp on its token
    def base(req: Request) -> str:
        return door.link(req, "")

    def cors(resp: Response) -> Response:
        resp.headers.update(CORS)
        return resp

    def preflight():
        return cors(Response(status_code=204))

    def oauth_json(data: dict, status: int = 200) -> Response:
        return cors(JSONResponse(data, status, headers={"Cache-Control": "no-store", "Pragma": "no-cache"}))

    async def resource_meta(req: Request):
        if req.method == "OPTIONS":
            return preflight()
        return cors(JSONResponse(oauth.protected_resource(base(req))))

    async def server_meta(req: Request):
        if req.method == "OPTIONS":
            return preflight()
        return cors(JSONResponse(oauth.authorization_server(base(req))))

    async def register(req: Request):
        if req.method == "OPTIONS":
            return preflight()
        ip = req.client.host if req.client else "?"
        now = time.time()
        REGISTERED[ip] = [t for t in REGISTERED.get(ip, []) if now - t < 3600]
        if len(REGISTERED[ip]) >= REGISTER_LIMIT:
            return oauth_json({"error": "slow_down", "error_description": "too many registrations; try later"}, 429)
        try:
            meta = await req.json()
            if not isinstance(meta, dict):
                raise ValueError
        except ValueError:
            return oauth_json({"error": "invalid_client_metadata", "error_description": "send JSON"}, 400)
        try:
            out = door.oauth.register(meta)
        except OAuthError as ex:
            return oauth_json(ex.body(), ex.status)
        REGISTERED[ip].append(now)
        return oauth_json(out, 201)

    async def find_client(cid: str) -> dict | None:
        """A registered client, or one whose id is the address of its metadata document (fetched, then kept for a
        day)."""
        c = door.oauth.client(cid)
        if c and not (c["metadata_doc"] and time.time() - c["created"] > 86400):
            return c
        if oauth.document_url_ok(cid):
            try:
                return door.oauth.remember_document(cid, await oauth.fetch_document(cid))
            except OAuthError:
                return c        # the copy from yesterday, if there is one
        return None

    def no_app(msg: str, status: int = 400):
        return page("connect", f'<h1>connect an app</h1><p class="err">{e(msg)}</p><p class="muted">Go back to the '
                    f'app and connect again. If it keeps happening, the app may not support this server.</p>',
                    narrow=True, status=status)

    async def authorize(req: Request):
        """The learner says whether this app may use their Panko. Problems with the app itself are shown here; other
        problems are sent back to the app, as OAuth says."""
        p = dict(req.query_params) if req.method == "GET" else {k: str(v) for k, v in (await req.form()).items()}
        c = await find_client(p.get("client_id", ""))
        if not c:
            return no_app("This app isn't known here (its client_id).")
        ru = p.get("redirect_uri") or (c["redirect_uris"][0] if len(c["redirect_uris"]) == 1 else "")
        if not ru or not any(oauth.same_redirect(ru, x) for x in c["redirect_uris"]):
            return no_app("This app asked to send you back to an address it didn't register.")
        iss, state = base(req), p.get("state", "")

        def back(**kw):
            return RedirectResponse(oauth.back_to(ru, state=state, iss=iss, **kw), 303)
        if p.get("response_type") != "code":
            return back(error="unsupported_response_type")
        if not p.get("code_challenge") or p.get("code_challenge_method", "plain") != "S256":
            return back(error="invalid_request", error_description="PKCE with S256 is required")
        if p.get("resource") and p["resource"].rstrip("/") not in (iss, f"{iss}/mcp"):
            return back(error="invalid_target", error_description="this server's resource is " + iss + "/mcp")
        u = door.user(req)
        if not u:
            if req.method == "POST":
                return no_app("You were signed out. Go back to the app and connect again.", 401)
            return RedirectResponse("/host/login?next=" + quote("/authorize?" + req.url.query, safe=""), 303)
        if req.method == "POST":
            if not same_site(req):
                return no_app("Use the buttons on this page.", 403)
            if p.get("do") != "allow":
                return back(error="access_denied", error_description="the learner said no")
            code = door.oauth.approve(u["id"], c, ru, p["code_challenge"])
            return back(code=code)
        name = c["name"] or urlsplit(c["id"]).hostname or "An app"
        dest = urlsplit(ru)
        keep = "".join(f'<input type="hidden" name="{k}" value="{e(p[k])}">' for k in
                       ("client_id", "redirect_uri", "response_type", "code_challenge", "code_challenge_method",
                        "state", "resource", "scope") if p.get(k) is not None)
        if not p.get("redirect_uri"):
            keep += f'<input type="hidden" name="redirect_uri" value="{e(ru)}">'
        return page("connect", f"""<h1>connect {e(name)}?</h1>
            <p class="muted">Signed in as <b>{e(u['name'])}</b>.</p>
            <section class="box"><p><b>{e(name)}</b> wants to use your Panko in chat: read your sources, add and edit
            cards, search for pictures, and run the free checks. Anything paid still asks you first.</p>
            <p class="faint">It sends you back to <code>{e(dest.scheme + '://' + (dest.netloc or ''))}</code>. You can
            end this connection any time on your <a href="/host/account">account</a> page.</p>
            <form method="post" action="/authorize">{keep}<div class="acts">
            <button class="pri" name="do" value="allow">allow</button><button name="do" value="deny">no</button>
            </div></form></section>""", user=u, narrow=True, form_to=f"{dest.scheme}://{dest.netloc}")

    def client_auth(req: Request, form) -> tuple[str, str | None]:
        h = req.headers.get("authorization", "")
        if h.lower().startswith("basic "):
            import base64
            from urllib.parse import unquote
            try:
                cid, _, sec = base64.b64decode(h[6:]).decode().partition(":")
                return unquote(cid), unquote(sec)
            except ValueError:
                return "", None
        return str(form.get("client_id", "")), (str(form["client_secret"]) if form.get("client_secret") else None)

    async def token(req: Request):
        if req.method == "OPTIONS":
            return preflight()
        form = await req.form()
        cid, sec = client_auth(req, form)
        c = await find_client(cid)
        if not c or not door.oauth.client_ok(c, sec):
            return oauth_json({"error": "invalid_client"}, 401)
        try:
            kind = form.get("grant_type")
            if kind == "authorization_code":
                out = door.oauth.exchange(c, str(form.get("code", "")), str(form.get("redirect_uri", "")),
                                          str(form.get("code_verifier", "")))
            elif kind == "refresh_token":
                out = door.oauth.refresh(c, str(form.get("refresh_token", "")))
            else:
                raise OAuthError("unsupported_grant_type")
        except OAuthError as ex:
            return oauth_json(ex.body(), ex.status)
        return oauth_json(out)

    async def revoke(req: Request):
        if req.method == "OPTIONS":
            return preflight()
        form = await req.form()
        door.oauth.revoke(str(form.get("token", "")))
        return oauth_json({})

    async def mcp(req: Request):
        """The learner's Claude: an access token in the Authorization header, nothing else."""
        if req.method == "OPTIONS":
            return preflight()
        meta = f'{base(req)}/.well-known/oauth-protected-resource/mcp'
        h = req.headers.get("authorization", "")
        found = door.oauth.user_for(h[7:].strip()) if h[:7].lower() == "bearer " else None
        if not found:
            err = ', error="invalid_token"' if h else ""
            return cors(JSONResponse({"error": "sign in: connect this app to your Panko"}, 401, headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{meta}"{err}, scope="{oauth.SCOPE}"'}))
        u, _ = found
        try:
            r = await door.pankos.ensure(u["id"], u["quota_gb"])
        except RuntimeError as ex:
            return cors(JSONResponse({"error": str(ex)}, 503))
        if time.time() - (u["last_seen"] or 0) > 60:
            door.store.seen(u["id"])
        return await forward(req, u, r, "/mcp", CORS)

    async def anki(req: Request):
        """The Anki add-on: a device code in the Authorization header, nothing else; only its three routes."""
        path = req.path_params["path"]
        if not (path in ("pull", "done") or (path.startswith("media/") and "/" not in path[6:])):
            return JSONResponse({"error": "not found"}, 404)
        h = req.headers.get("authorization", "")
        u = door.store.device_user(h[7:].strip()) if h[:7].lower() == "bearer " else None
        if not u:
            return JSONResponse({"error": "the device code isn't right, or was ended"}, 401)
        try:
            r = await door.pankos.ensure(u["id"], u["quota_gb"])
        except RuntimeError as ex:
            return JSONResponse({"error": str(ex)}, 503)
        if time.time() - (u["last_seen"] or 0) > 60:
            door.store.seen(u["id"])
        return await forward(req, u, r, "/anki/" + path)

    async def end_connection(req: Request):
        u = door.user(req)
        if not u or not same_site(req):
            return RedirectResponse("/host/account", 303)
        door.oauth.end_grant(req.path_params["gid"], u["id"])
        return RedirectResponse("/host/account", 303)

    def check_quotas():
        users = [u for u in door.store.users() if not u["disabled"]]
        door.watch.check_quotas([(u["id"], u["name"], _du(door.pankos.home(u["id"])), u["quota_gb"] or door.pankos.quota_gb)
                                 for u in users])

    async def watch_disk():
        from panko.host.watch import QUOTA_EVERY, WATCH_EVERY
        n = 0
        while True:
            try:
                await asyncio.to_thread(door.watch.check_disk)
                if n % QUOTA_EVERY == 0:
                    await asyncio.to_thread(check_quotas)
            except Exception as ex:  # noqa: BLE001  the watch must keep going
                print(f"watch: {ex}", file=sys.stderr)
            n += 1
            await asyncio.sleep(WATCH_EVERY)

    @contextlib.asynccontextmanager
    async def lifespan(a):
        task = asyncio.create_task(door.pankos.reaper())
        wake = asyncio.create_task(door.pankos.wake(door.store))     # jobs the restart cut off carry on
        door.watch.note("start", "the front door started", alert=False)
        watching = asyncio.create_task(watch_disk())
        try:
            yield
        finally:
            task.cancel()
            wake.cancel()
            watching.cancel()
            door.pankos.stop_all()
            for c in door.clients.values():
                await c.aclose()

    routes = [Route("/host/login", login, methods=["GET", "POST"]), Route("/host/logout", logout, methods=["POST"]),
              Route("/host/invite/{token}", invite, methods=["GET", "POST"]), Route("/host/privacy", privacy),
              Route("/host/install", install), Route("/host/panko-sync.ankiaddon", addon),
              Route("/host/account", account, methods=["GET", "POST"]), Route("/host/account/export", account_export),
              Route("/host/admin", admin), Route("/host/admin/invite", admin_invite, methods=["POST"]),
              Route("/host/admin/withdraw/{n:int}", admin_withdraw, methods=["POST"]),
              Route("/host/admin/user/{uid}", admin_user, methods=["GET", "POST"]),
              Route("/host/admin/export/{uid}", admin_export), Route("/host/logo.svg", logo),
              Route("/host/health", health),
              Route("/host/account/connection/{gid}", end_connection, methods=["POST"]),
              Route("/host/account/anki", account_device, methods=["POST"]),
              Route("/host/account/anki/{did}", end_device, methods=["POST"]),
              Route("/anki/{path:path}", anki, methods=["GET", "POST"]),
              Route("/.well-known/oauth-protected-resource", resource_meta, methods=["GET", "OPTIONS"]),
              Route("/.well-known/oauth-protected-resource/mcp", resource_meta, methods=["GET", "OPTIONS"]),
              Route("/.well-known/oauth-authorization-server", server_meta, methods=["GET", "OPTIONS"]),
              Route("/register", register, methods=["POST", "OPTIONS"]),
              Route("/authorize", authorize, methods=["GET", "POST"]),
              Route("/token", token, methods=["POST", "OPTIONS"]),
              Route("/revoke", revoke, methods=["POST", "OPTIONS"]),
              Route("/mcp", mcp, methods=["GET", "POST", "DELETE", "OPTIONS"]),
              Route("/{path:path}", proxy, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])]
    a = Starlette(routes=routes, lifespan=lifespan)
    a.state.door = door
    return a


INSTALL_PAGE = """<h1>Panko on your own computer</h1>
<p class="muted">No account, no sign-up: Panko runs on your computer and keeps your cards in a folder of your own
(<code>Panko</code> in your home folder). It's the same Panko: sources, checks, pictures, your card design, and the
Anki add-on.</p>
<section class="box"><div class="t">what's different from an account here</div>
<p>· The paid steps (audio, reading sources by API, drawings) use your own keys, added in Panko's setup. Chat mode,
where your Claude does the reading, costs nothing beyond your Claude plan.</p>
<p>· Chat mode works from Claude's desktop app or Claude Code. Claude on the web and on your phone can't reach a
program on your computer.</p>
<p>· Panko runs while its terminal window is open, and Anki gets new cards while it runs.</p>
<p>· Backing up the folder is up to you (Time Machine or any backup covers it).</p></section>
<section class="box"><div class="t">1. install it</div>
<p>Panko installs with <a href="https://docs.astral.sh/uv/">uv</a>, which brings its own Python. Open a terminal
and paste this (macOS or Linux):</p>
<code class="link-out">curl -LsSf https://astral.sh/uv/install.sh | sh</code>
<p class="faint">On Windows, in PowerShell: <code>powershell -ExecutionPolicy ByPass -c "irm
https://astral.sh/uv/install.ps1 | iex"</code> (Panko hasn't been tried on Windows yet).</p>
<p>Then open a new terminal window and install Panko:</p>
<code class="link-out">{install}</code></section>
<section class="box"><div class="t">2. start it</div>
<code class="link-out">panko hub</code>
<p>It opens in your browser and asks which language you're learning. Ctrl-C in the terminal stops it; run it again
to come back to where you were.</p></section>
<section class="box"><div class="t">3. into Anki</div>
<p><a class="btn" href="/host/panko-sync.ankiaddon">download the Panko sync add-on</a> and open the file (or in
Anki: Tools → Add-ons → Install from file), then restart Anki. On Panko's sync page, make a code and paste it with
the address shown there into Anki: Tools → Panko: settings…. Your review history and your own notes are never
touched.</p></section>
<section class="box"><div class="t">4. chat mode (optional)</div>
<code class="link-out">panko mcp --config</code>
<p>It prints what to add to Claude's desktop app (Settings → Developer → Edit Config) and the line for Claude
Code. Restart Claude, then ask it to read a source with Panko.</p></section>
<section class="box"><div class="t">later</div>
<p>Update Panko: <code>{upgrade}</code>. Panko is free software (AGPL): <a href="{source}">its source</a>.</p>
</section>"""

PRIVACY = """<h1>privacy</h1><section class="box">
<p><b>What's kept.</b> Your account (a name and a password hash), and your own Panko folder: your config, the keys you
add, your cards, the sources you upload (lesson recordings, sheets, photos) and the media made from them.</p>
<p><b>Who can see it.</b> Only you, through your account. The person who runs this server could technically read
the files on it; they're backed up nightly, encrypted.</p>
<p><b>Keys and spend.</b> Keys you add are yours and are used only for your Panko. What a paid step costs is
charged to your key, and Panko shows the price before it spends anything.</p>
<p><b>Leaving.</b> Download everything from your account page (a zip you can open with Panko on your own computer),
then ask the admin to delete your account, which removes your folder.</p>
<p><b>Recordings.</b> Record a lesson only with your teacher's consent.</p></section>"""


def _du(p: Path) -> int:
    total = 0
    for d, _, files in os.walk(p):
        for f in files:
            try:
                total += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return total


def _zip(home: Path, tmp: Path) -> Path:
    """The user's folder as a zip; SQLite stores copied with SQLite's backup, so a running Panko's store is whole."""
    tmp.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(suffix=".zip", dir=tmp)
    os.close(fd)
    out = Path(name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, files in os.walk(home):
            for f in files:
                p = Path(d) / f
                rel = p.relative_to(home)
                if p.is_symlink() or f.endswith(("-wal", "-shm", ".part")):
                    continue
                if f.endswith(".db"):
                    copy = tmp / f"{out.stem}-{f}"
                    src, dst = sqlite3.connect(p), sqlite3.connect(copy)
                    with dst:
                        src.backup(dst)
                    src.close()
                    dst.close()
                    z.write(copy, f"panko/{rel}")
                    copy.unlink()
                else:
                    z.write(p, f"panko/{rel}")
    return out


def _remove(door: Door, uid: str) -> str:
    """Move a deleted user's folder aside (purged later) and drop their log."""
    src = door.pankos.home(uid)
    dest = door.data / "deleted" / f"{uid}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.move(str(src), dest)
    (door.data / "logs" / f"{uid}.log").unlink(missing_ok=True)
    return str(dest.relative_to(door.data))
