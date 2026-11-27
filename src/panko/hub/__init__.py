"""The Panko hub: a local web dashboard over the same store, sources and jobs the commands use.

`panko hub` serves it on 127.0.0.1 and opens the browser. Only this computer can reach it, and only through the
launch link: the link carries a random token that becomes an HttpOnly cookie, every request must name a local host
(no DNS rebinding), and changes need a header a cross-site form can't send. Card previews render in sandboxed
iframes (srcdoc, opaque origin, media inline), so text from a shared deck can't run in the hub's own page.

On the server (`panko hub --socket PATH`, docs/SPEC-hosted.md) it listens on a Unix socket instead, behind the front
door, which has already signed the user in: every request must carry the front door's secret
(`PANKO_FRONT_SECRET`) in place of the host check and the launch token. Changes still need the header.
"""
from __future__ import annotations

import contextlib
import os
import re
import secrets
import webbrowser
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from panko.hub import api
from panko.hub.jobs import Jobs

STATIC = Path(__file__).parent / "static"
COOKIE = "panko_hub"
LOCAL = {"127.0.0.1", "localhost", "[::1]"}
UPLOAD_NAME = re.compile(r"[^\w.\-]+")


class Guard:
    """Host check and the token (cookie, or `?t=` once) on everything; a header on changes. Card previews carry their
    media inline, so nothing is left open for the sandboxed frames."""

    def __init__(self, app, token: str, front: str | None = None):
        self.app, self.token, self.front = app, token, front

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        req = Request(scope)
        if self.front:      # behind the front door: its secret stands for the host check and the launch token
            if not secrets.compare_digest(req.headers.get("x-panko-front", ""), self.front):
                return await JSONResponse({"error": "not through the front door"}, 403)(scope, receive, send)
            return await self._changes(req, scope, receive, send)
        host = (req.headers.get("host") or "").rsplit(":", 1)[0] if not (req.headers.get("host") or "").startswith("[") \
            else (req.headers.get("host") or "").split("]")[0] + "]"
        if host not in LOCAL:
            return await JSONResponse({"error": "the hub only answers on this computer"}, 403)(scope, receive, send)
        path = scope["path"]
        if path.startswith("/anki/"):
            # the Anki add-on, pointed at your own Panko: its lasting code (made on the sync page), or the hub's key
            # while this hub runs
            from panko.anki import remote
            auth = req.headers.get("authorization", "")
            given = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
            if given and any(c and secrets.compare_digest(given, c) for c in (self.token, remote.local_code())):
                return await self.app(scope, receive, send)
            return await JSONResponse({"error": "the add-on's code isn't right"}, 401)(scope, receive, send)
        given = req.query_params.get("t")
        if given and secrets.compare_digest(given, self.token):
            r = RedirectResponse(path if path != "/" else "/", 303)
            r.set_cookie(COOKIE, self.token, httponly=True, samesite="strict", path="/")
            return await r(scope, receive, send)
        if not secrets.compare_digest(req.cookies.get(COOKIE, ""), self.token):
            if path.startswith("/api/"):
                return await JSONResponse({"error": "open the hub from the link `panko hub` printed"}, 401)(
                    scope, receive, send)
            return await HTMLResponse(LOCKED, 401)(scope, receive, send)
        return await self._changes(req, scope, receive, send)

    async def _changes(self, req, scope, receive, send):
        if self.front and (scope["path"] == "/mcp" or scope["path"].startswith("/anki/")):
            # chat mode and the Anki add-on: the front door let them in on their own token, no cookie
            return await self.app(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD") and req.headers.get("x-panko") != "1":
            return await JSONResponse({"error": "missing X-Panko header"}, 403)(scope, receive, send)
        return await self.app(scope, receive, send)


LOCKED = """<!doctype html><meta charset=utf-8><title>Panko hub</title>
<body style="background:#1a1a1a;color:#d6d6d6;font:15px ui-monospace,Menlo,monospace;padding:48px">
<p style="color:#d97757">✻ panko hub</p><p>This page needs the link that <code>panko hub</code> printed in your
terminal (it carries a one-time key). Run it again if you lost it.</p></body>"""


async def index(request: Request):
    """The page, with the script and style named by version so an updated Panko is never served stale."""
    page = (STATIC / "index.html").read_text()
    for name in ("app.js", "app.css"):
        page = page.replace(f"/static/{name}", f"/static/{name}?v={int((STATIC / name).stat().st_mtime)}")
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


def uploads_dir() -> Path:
    from panko.config import ROOT
    return ROOT / "data" / "sources" / "uploads"


async def upload(request: Request):
    """Files chosen in the browser → data/sources/uploads/<folder>/; answers the path to register as a source. On the
    server an upload has a size limit and must fit in the user's quota."""
    from panko.config import host_limits, hosted, room_for
    if hosted():
        try:
            size = int(request.headers.get("content-length") or -1)
        except ValueError:
            size = -1
        limit = host_limits()["upload_mb"] * 1e6
        if size < 0:
            return JSONResponse({"error": "upload without a size"}, 411)
        if size > limit:
            return JSONResponse({"error": f"that's {size / 1e6:,.0f} MB; one upload can be up to "
                                          f"{limit / 1e6:,.0f} MB: send the files in parts"}, 413)
        try:
            room_for(size)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, 413)
    form = await request.form()
    files = [f for f in form.getlist("files") if hasattr(f, "filename") and f.filename]
    if not files:
        return JSONResponse({"error": "no files"}, 400)
    folder = UPLOAD_NAME.sub("-", str(form.get("folder") or "")).strip("-. ")
    base = uploads_dir()
    out = base / folder if folder else base
    out.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        name = UPLOAD_NAME.sub("-", Path(f.filename).name).strip("-. ") or "file"
        p = out / name
        p.write_bytes(await f.read())
        saved.append(p)
    path = out if folder or len(saved) > 1 else saved[0]
    from panko.config import ROOT
    shown = path.relative_to(ROOT) if hosted() else path     # the server's own paths aren't shown
    return JSONResponse({"path": str(shown), "files": [p.name for p in saved]})


def app(token: str | None = None, front: str | None = None) -> Starlette:
    api.JOBS = api.JOBS or Jobs()
    routes = [Route("/", index), Route("/api/upload", upload, methods=["POST"]), *api.ROUTES,
              Route("/media/{name}", api.media), Route("/export/file/{name}", api.export_file),
              Route("/addon/panko-sync.ankiaddon", api.addon_file), Route("/addon/panko.mcpb", api.extension_file),
              Route("/anki/pull", api.anki_pull, methods=["POST"]), Route("/anki/done", api.anki_done, methods=["POST"]),
              Route("/anki/media/{name}", api.anki_media), Mount("/static", StaticFiles(directory=STATIC), name="static")]
    lifespan = None
    if front and _mcp_ready():      # behind the front door: chat mode for the learner's own Claude, at /mcp
        from panko.mcp_server import http_app
        endpoint, sm = http_app()
        routes.append(Route("/mcp", Connected(endpoint), methods=["GET", "POST", "DELETE"]))

        @contextlib.asynccontextmanager
        async def lifespan(_):
            async with sm.run():
                yield
    a = Starlette(routes=routes, lifespan=lifespan)
    a.state.token = token or secrets.token_urlsafe(24)
    a.add_middleware(Guard, token=a.state.token, front=front)
    return a


class Connected:
    """The MCP endpoint, noting every call as chat mode in use, so the hub shows it as soon as Claude connects (it
    lists the tools), not only after its first tool call."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("method") == "POST":
            from panko import modes
            modes.mark_chat("connect")
        await self.inner(scope, receive, send)


def _mcp_ready() -> bool:
    try:
        import mcp  # noqa: F401
        return True
    except ImportError:
        return False


def port_free(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # as uvicorn does: a port just let go is free
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def bind_socket(path: str | Path):
    """A Unix socket only this user can open (uvicorn would make its own readable by everyone). A socket file left by
    a hub that's gone is replaced; one a hub still answers on is not."""
    import socket
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.connect(str(p))
            raise SystemExit(f"a Panko hub is already listening on {p}")
        except (ConnectionRefusedError, FileNotFoundError):
            p.unlink(missing_ok=True)
        finally:
            probe.close()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        s.bind(str(p))
    finally:
        os.umask(old)
    os.chmod(p, 0o600)
    s.listen(128)
    return s


def keep_jobs() -> None:
    """Jobs kept in the Panko folder across restarts; the free ones a restart cut off start again by themselves."""
    import threading

    from panko.config import ROOT
    api.JOBS = Jobs(ROOT / "data" / "work" / "jobs.json")
    if api.JOBS.interrupted():
        threading.Timer(2, api.resume_interrupted).start()      # once the hub answers


def serve_socket(path: str | Path):
    """On the server: behind the front door, on a Unix socket, with its secret from PANKO_FRONT_SECRET."""
    import uvicorn
    front = os.environ.get("PANKO_FRONT_SECRET", "")
    if len(front) < 16:
        raise SystemExit("serving on a socket needs PANKO_FRONT_SECRET (16 characters or more), which the front door "
                         "sends with every request")
    sock = bind_socket(path)
    keep_jobs()
    a = app(front=front)
    print(f"✻ Panko hub on {path}" + (" (hosted)" if os.environ.get("PANKO_HOSTED") else ""), flush=True)
    try:
        uvicorn.run(a, fd=sock.fileno(), log_level="warning")
    finally:
        Path(path).unlink(missing_ok=True)


def serve(port: int = 8770, open_browser: bool = True, token: str | None = None):
    import uvicorn
    if not port_free(port):      # before printing a link that would lead nowhere
        raise SystemExit(f"Port {port} is already in use, probably by a Panko hub that's still running: stop it with "
                         f"Ctrl-C in its terminal, or start this one with --port {port + 1}.")
    keep_jobs()
    a = app(token)
    url = f"http://127.0.0.1:{port}/?t={a.state.token}"
    print(f"✻ Panko hub on {url}\n  (only this computer can open it; Ctrl-C stops it)", flush=True)
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(a, host="127.0.0.1", port=port, log_level="warning")


__all__ = ["app", "serve", "serve_socket", "Response"]
