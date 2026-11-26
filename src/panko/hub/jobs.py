"""Background jobs for the hub: long or paid steps run one at a time (the store is SQLite, and two paid runs should
never race the budget), each with its own log of what the step printed.

`print` inside a job goes to that job's log: stdout is swapped once for a proxy that writes to the log of the job
running on the current thread, and to the real stdout otherwise.
"""
from __future__ import annotations

import io
import queue
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_LINES = 3000
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
    fn: Callable = field(repr=False)
    paid: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: str = "queued"           # queued | running | done | failed | cancelled
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    log: list[str] = field(default_factory=list)
    result: object = None
    error: str = ""
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
                "log": log[-tail:] if tail else log, "lines": len(log), "result": self.result, "error": self.error}


class Jobs:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._q: queue.Queue[Job] = queue.Queue()
        self._lock = threading.Lock()
        if not isinstance(sys.stdout, _Proxy):
            sys.stdout = _Proxy(sys.stdout)
        threading.Thread(target=self._worker, name="panko-hub-jobs", daemon=True).start()

    def submit(self, kind: str, title: str, fn: Callable[[Job], object], paid: bool = False) -> Job:
        """Queue `fn(job)`; what it returns becomes the job's result, what it prints its log."""
        job = Job(kind, title, fn, paid)
        with self._lock:
            self._jobs[job.id] = job
        self._q.put(job)
        return job

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
            return True
        return False

    def _worker(self):
        while True:
            job = self._q.get()
            if job.status != "queued":
                continue
            job.status, job.started = "running", time.time()
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
