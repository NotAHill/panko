"""Wikimedia Commons search (no key needed)."""
from __future__ import annotations

import re

from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import UA, get_json  # noqa: F401  (UA is re-exported for pictures.py)

API = "https://commons.wikimedia.org/w/api.php"


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def candidate(p: dict) -> dict:
    """One Commons file page (with imageinfo url|extmetadata, iiurlwidth) → a candidate."""
    ii = (p.get("imageinfo") or [{}])[0]
    md = ii.get("extmetadata", {})
    return {
        "url": ii.get("url"), "thumb": ii.get("thumburl"), "title": p.get("title"),
        "author": _plain(md.get("Artist", {}).get("value", "")),
        "license": md.get("LicenseShortName", {}).get("value", ""),
        "page": ii.get("descriptionurl"),
    }


IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 800}


@register("images", "commons")
class Commons(ImageSearch):
    label = "Wikimedia Commons"

    def search(self, query, limit=6):
        data = get_json("commons", API, gap=0.2, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": limit, **IMAGEINFO,
        })
        pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        return [candidate(p) for p in pages]
