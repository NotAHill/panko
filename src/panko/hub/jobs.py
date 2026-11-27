"""Background jobs for the hub: long or paid steps run one at a time (the store is SQLite, and two paid runs should
never race the budget), each with its own log of what the step printed.

`print` inside a job goes to that job's log: stdout is swapped once for a proxy that writes to the log of the job
running on the current thread, and to the real stdout otherwise.

With a `path`, jobs and the end of their logs are kept in that file, so a restart (a deploy, a reboot) doesn't lose
them. A job that was queued or running when the hub stopped comes back as "interrupted"; each job keeps the request
that started it (`replay`), so the hub can start it again (`panko.hub.api.resume`).
"""
from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_LINES = 3000
KEPT_JOBS = 60          # in the file: the newest jobs, each with the end of its log
KEPT_LINES = 400
OVER = ("done", "failed", "cancelled", "interrupted")
_local = threading.local()


class _Proxy(io.TextIOBase):
    def __init__(self, real):
        self.real = real

    def write(self, s: str) -> int:
        job = getattr(_local, "job", None)
        if job is None:
            return self.real.write(s)
        job._write(s)
        return len(s)

    def flush(self):
        if getattr(_local, "job", None) is None:
            self.real.flush()

    def isatty(self):
        return False


@dataclass
class Job:
    kind: str
    title: str
    fn: Callable | None = field(repr=False)
    paid: bool = False
    replay: dict | None = None       # the request that started it: {"handler", "path", "query", "body", "resumed"}
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: str = "queued"           # queued | running | done | failed | cancelled | interrupted
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    log: list[str] = field(default_factory=list)
    result: object = None
    error: str = ""
    resumed_as: str = ""             # an interrupted job started again: the new job's id
    _part: str = ""

    def _write(self, s: str):
        text = self._part + s
        *lines, self._part = text.split("\n")
        self.log.extend(lines)
        if len(self.log) > MAX_LINES:
            del self.log[: len(self.log) - MAX_LINES]

    def say(self, line: str):
        self._write(line + "\n")

    def view(self, tail: int | None = 400) -> dict:
        log = self.log + ([self._part] if self._part else [])
        return {"id": self.id, "kind": self.kind, "title": self.title, "paid": self.paid, "status": self.status,
                "created": self.created, "started": self.started, "finished": self.finished,
                "log": log[-tail:] if tail else log, "lines": len(log), "result": self.result, "error": self.error,
                "resumable": self.resumable(), "resumed_as": self.resumed_as}

    def resumable(self) -> bool:
        return self.status == "interrupted" and bool(self.replay) and not self.resumed_as

    def saved(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k not in ("fn", "_part", "log")}
        d["log"] = (self.log + ([self._part] if self._part else []))[-KEPT_LINES:]
        try:
            json.dumps(d["result"], default=str)
        except (TypeError, ValueError):
            d["result"] = str(d["result"])
        return d


class Jobs:
    def __init__(self, path: Path | None = None):
        self._jobs: dict[str, Job] = {}
        self._q: queue.Queue[Job] = queue.Queue()
        self._lock = threading.Lock()
        self.path = Path(path) if path else None
        if self.path:
            self._load()
        if not isinstance(sys.stdout, _Proxy):
            sys.stdout = _Proxy(sys.stdout)
        threading.Thread(target=self._worker, name="panko-hub-jobs", daemon=True).start()
        if self.path:
            threading.Thread(target=self._saver, name="panko-hub-jobs-save", daemon=True).start()

    def _load(self):
        try:
            rows = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        names = set(Job.__dataclass_fields__) - {"fn", "_part"}
        for d in rows if isinstance(rows, list) else []:
            try:
                j = Job(**{k: v for k, v in d.items() if k in names}, fn=None)
            except TypeError:
                continue
            if j.status in ("queued", "running"):     # cut off by a restart
                j.status, j.finished = "interrupted", j.finished or time.time()
                j.say("— stopped by a restart of the server" if j.started else "— not started: the server restarted")
            self._jobs[j.id] = j
        self.save()

    def save(self):
        if not self.path:
            return
        with self._lock:
            rows = [j.saved() for j in sorted(self._jobs.values(), key=lambda j: -j.created)[:KEPT_JOBS]]
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(rows, ensure_ascii=False, default=str))
            os.replace(tmp, self.path)
        except OSError as e:          # a full disk mustn't stop a job
            sys.__stderr__.write(f"jobs: couldn't save {self.path}: {e}\n")

    def _saver(self, every: float = 2):
        """The log of a running job, every few seconds (status changes are saved straight away)."""
        while True:
            time.sleep(every)
            if any(j.status == "running" for j in self._jobs.values()):
                self.save()

    def submit(self, kind: str, title: str, fn: Callable[[Job], object], paid: bool = False,
               replay: dict | None = None) -> Job:
        """Queue `fn(job)`; what it returns becomes the job's result, what it prints its log."""
        job = Job(kind, title, fn, paid, replay)
        with self._lock:
            self._jobs[job.id] = job
        self._q.put(job)
        self.save()
        return job

    def interrupted(self) -> list[Job]:
        """Jobs a restart cut off that can be started again, oldest first."""
        return sorted((j for j in self._jobs.values() if j.resumable()), key=lambda j: j.created)

    def get(self, jid: str) -> Job | None:
        return self._jobs.get(jid)

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: -j.created)

    def busy(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.status in ("queued", "running")]

    def cancel(self, jid: str) -> bool:
        """Only a job still waiting can be cancelled: a running step can't be stopped halfway safely."""
        j = self._jobs.get(jid)
        if j and j.status == "queued":
            j.status, j.finished = "cancelled", time.time()
            self.save()
            return True
        return False

    def _worker(self):
        while True:
            job = self._q.get()
            if job.status != "queued":
                continue
            job.status, job.started = "running", time.time()
            self.save()
            _local.job = job
            try:
                job.result = job.fn(job)
                job.status = "done"
            except Exception as e:     # a failed step is reported on the job, never takes the hub down
                job.error = f"{type(e).__name__}: {e}"
                job._write(traceback.format_exc())
                job.status = "failed"
            finally:
                _local.job = None
                if job._part:
                    job._write("\n")
                job.finished = time.time()
                self.save()
