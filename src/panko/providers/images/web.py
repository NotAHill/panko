"""Shared HTTP for picture search: polite spacing per site, one short retry on 429, JSON answers cached under
`cache/images/<site>/`. A site that says "too many requests" for longer than a short wait is paused for the rest of
the run (its searches raise `RateLimited`, which `pictures.candidates` logs and skips)."""
from __future__ import annotations

import hashlib
import json
import threading
import time

import httpx

from panko import USER_AGENT

UA = {"User-Agent": USER_AGENT}
SECRET_PARAMS = ("key",)        # never part of a cache file name
sleep = time.sleep              # tests replace this

_locks: dict[str, threading.Lock] = {}
_last: dict[str, float] = {}
_paused: dict[str, float] = {}
_guard = threading.Lock()


class RateLimited(httpx.HTTPError):
    pass


def _cache_file(site: str, url: str, params: dict):
    from panko import config
    public = {k: v for k, v in sorted((params or {}).items()) if k not in SECRET_PARAMS}
    key = hashlib.sha1(json.dumps([url, public], sort_keys=True, default=str).encode()).hexdigest()[:20]
    return config.CACHE / "images" / site / f"{key}.json"


def _retry_after(r: httpx.Response, default: float) -> float:
    try:
        return float(r.headers.get("Retry-After", default))
    except ValueError:
        return default


def get_json(site: str, url: str, params: dict | None = None, headers: dict | None = None, *, gap: float = 1.0,
             ttl: float = 30 * 86400, missing=...):
    """GET a JSON answer, from the cache when it's younger than `ttl` seconds. At most one request per `gap`
    seconds per site. `missing` is returned (and cached) on a 404 when given; otherwise a 404 raises."""
    f = _cache_file(site, url, params or {})
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        return json.loads(f.read_text())
    with _guard:
        lock = _locks.setdefault(site, threading.Lock())
    with lock:
        if _paused.get(site, 0) > time.time():
            raise RateLimited(f"{site}: rate limit reached; paused for this run")
        for attempt in range(2):
            wait = _last.get(site, 0) + gap - time.time()
            if wait > 0:
                sleep(wait)
            r = httpx.get(url, params=params, headers={**UA, **(headers or {})}, timeout=30, follow_redirects=True)
            _last[site] = time.time()
            if r.status_code != 429:
                break
            ra = _retry_after(r, 60)
            if attempt == 0 and ra <= 30:
                sleep(ra)
                continue
            _paused[site] = time.time() + ra
            raise RateLimited(f"{site}: rate limit reached (retry after {ra:.0f}s); skipping it for now")
    if r.status_code == 404 and missing is not ...:
        data = missing
    else:
        r.raise_for_status()
        data = r.json()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False))
    return data


def reset():
    """Forget pauses and spacing (tests, or a new run in the same process)."""
    _last.clear()
    _paused.clear()
