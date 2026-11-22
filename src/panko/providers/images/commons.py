"""Wikimedia Commons search (no key needed)."""
from __future__ import annotations

import re

import httpx

from panko.providers import register
from panko.providers.base import ImageSearch

UA = {"User-Agent": "panko/0.1 (personal flashcard tool)"}


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


@register("images", "commons")
class Commons(ImageSearch):
    def search(self, query, limit=6):
        r = httpx.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": limit,
            "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 800,
        })
        r.raise_for_status()
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        out = []
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata", {})
            out.append({
                "url": ii.get("url"), "thumb": ii.get("thumburl"), "title": p.get("title"),
                "author": _plain(md.get("Artist", {}).get("value", "")),
                "license": md.get("LicenseShortName", {}).get("value", ""),
                "page": ii.get("descriptionurl"),
            })
        return out
