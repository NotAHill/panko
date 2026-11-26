"""Each user's own Panko: a `panko hub --socket` process with PANKO_HOME set to their folder, started when they
arrive and stopped after it has been idle a while (never while one of its jobs runs).

Layout under the front door's data folder:
    users/<id>/      the user's Panko folder (config, .env, store, media)
    run/<id>.sock    their hub's socket (the folder is open to the front door only)
    logs/<id>.log    what their Panko printed
A process gets a small environment of its own: never the front door's, only what a Panko needs plus the server's
shared settings (`PASS_ENV`, `PANKO_DEFAULT_*`)."""
from __future__ import annotations

import asyncio
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# from the front door's own environment into each user's Panko: the server's tools and its shared photo keys
PASS_ENV = ("PATH", "LANG", "LC_ALL", "TZ", "PANKO_CAMEL_PYTHON", "CAMELTOOLS_DATA", "SSL_CERT_FILE")
SHARED_PREFIX = "PANKO_DEFAULT_"
START_TIMEOUT = 30


@dataclass
class Running:
    proc: subprocess.Popen
    sock: Path
    secret: str
    started: float = field(default_factory=time.time)
    used: float = field(default_factory=time.time)


class Pankos:
    def __init__(self, data: Path, *, idle_minutes: float = 20, quota_gb: float = 5, upload_mb: float = 500):
        self.data = Path(data)
        self.idle = idle_minutes * 60
        self.quota_gb, self.upload_mb = quota_gb, upload_mb
        self.running: dict[str, Running] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        for d, mode in (("users", 0o700), ("run", 0o700), ("logs", 0o700)):
            (self.data / d).mkdir(parents=True, exist_ok=True)
            os.chmod(self.data / d, mode)

    def home(self, uid: str) -> Path:
        return self.data / "users" / uid

    def sock(self, uid: str) -> Path:
        return self.data / "run" / f"{uid}.sock"

    def env(self, uid: str, secret: str, quota_gb: float | None) -> dict:
        env = {k: os.environ[k] for k in PASS_ENV if os.environ.get(k)}
        env.update({k: v for k, v in os.environ.items() if k.startswith(SHARED_PREFIX) and v})
        env.update({"HOME": str(self.home(uid)), "PANKO_HOME": str(self.home(uid)), "PANKO_HOSTED": "1",
                    "PANKO_FRONT_SECRET": secret, "PANKO_QUOTA_GB": str(quota_gb or self.quota_gb),
                    "PANKO_UPLOAD_MB": str(self.upload_mb), "PYTHONUNBUFFERED": "1"})
        return env

    def alive(self, uid: str) -> Running | None:
        r = self.running.get(uid)
        if r and r.proc.poll() is None:
            return r
        if r:
            self.running.pop(uid, None)
        return None

    async def ensure(self, uid: str, quota_gb: float | None = None) -> Running:
        """The user's Panko, started if it isn't running. Waits until its socket answers."""
        lock = self._locks.setdefault(uid, asyncio.Lock())
        async with lock:
            r = self.alive(uid)
            if r:
                r.used = time.time()
                return r
            home, sock = self.home(uid), self.sock(uid)
            home.mkdir(parents=True, exist_ok=True)
            os.chmod(home, 0o700)
            secret = secrets.token_urlsafe(32)
            log = open(self.data / "logs" / f"{uid}.log", "ab")    # noqa: SIM115  the process keeps it
            proc = subprocess.Popen([sys.executable, "-m", "panko", "hub", "--socket", str(sock)], cwd=home,
                                    env=self.env(uid, secret, quota_gb), stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
            log.close()
            deadline = time.time() + START_TIMEOUT
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"your Panko stopped while starting (see logs/{uid}.log on the server)")
                if _answers(sock):
                    r = Running(proc, sock, secret)
                    self.running[uid] = r
                    return r
                await asyncio.sleep(0.1)
            _stop(proc)
            raise RuntimeError("your Panko took too long to start: try again in a minute")

    async def busy(self, uid: str) -> bool:
        """True while one of the user's jobs is queued or running (a read, a sync): it isn't stopped then."""
        r = self.alive(uid)
        if not r:
            return False
        import httpx
        try:
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(r.sock)), timeout=5) as c:
                jobs = (await c.get("http://panko/api/jobs", headers={"X-Panko-Front": r.secret})).json()
        except Exception:  # noqa: BLE001  a Panko that doesn't answer isn't doing a job for anyone
            return False
        rows = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
        return any(j.get("status") in ("queued", "running") for j in rows if isinstance(j, dict))

    async def reap(self) -> list[str]:
        """Stop the Pankos idle for longer than the limit. Returns who was stopped."""
        stopped = []
        for uid in list(self.running):
            r = self.alive(uid)
            if r and time.time() - r.used > self.idle:
                if await self.busy(uid):
                    r.used = time.time()
                    continue
                self.stop(uid)
                stopped.append(uid)
        return stopped

    async def reaper(self, every: float = 60):
        while True:
            await asyncio.sleep(every)
            try:
                await self.reap()
            except Exception as e:  # noqa: BLE001  the reaper must keep going
                print(f"reaper: {e}", file=sys.stderr)

    def stop(self, uid: str) -> None:
        r = self.running.pop(uid, None)
        if r:
            _stop(r.proc)
        self.sock(uid).unlink(missing_ok=True)

    def stop_all(self) -> None:
        for uid in list(self.running):
            self.stop(uid)


def _answers(sock: Path) -> bool:
    if not sock.exists():
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(sock))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _stop(proc: subprocess.Popen, wait: float = 10) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(wait)
    except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait(5)
