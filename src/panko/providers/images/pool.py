"""Pictures shared on this server (`host/pool.py`): what other people here found for the same meaning. Only on a
hosted Panko, asked through the front door with this Panko's own secret; first after your own pictures in every
photo search (`[images] pool = false` turns it off). Free, and nothing is downloaded from a photo site."""
import os

import httpx

from panko.providers import register
from panko.providers.base import ImageSearch


def _ask(path: str, **kw) -> httpx.Response:
    r = httpx.get(os.environ["PANKO_POOL_URL"] + path, timeout=15,
                  headers={"X-Panko-Front": os.environ.get("PANKO_FRONT_SECRET", "")}, **kw)
    r.raise_for_status()
    return r


@register("images", "pool")
class Pool(ImageSearch):
    label = "Shared on this server"

    def ready(self) -> bool:
        from panko.config import hosted
        return hosted() and bool(os.environ.get("PANKO_POOL_URL"))

    def search(self, query, limit=6):
        try:
            rows = _ask("/search", params={"q": query, "limit": limit}).json().get("pictures", [])
        except (httpx.HTTPError, ValueError):
            return []           # the pool never stops a search of the sites
        # `thumb` is the address the browser shows (the front door serves it to you, signed in); `fetch` gets the
        # file here, on the server
        return [{"thumb": f"/host/pool/file/{x['name']}", "pool": x["name"], "title": "",
                 "author": "shared on this server", "license": x.get("license", ""), "credit": x.get("credit", ""),
                 "page": x.get("page", ""), "drawn": x.get("kind") == "drawing"} for x in rows]

    def fetch(self, c: dict) -> bytes:
        return _ask(f"/file/{c['pool']}").content
