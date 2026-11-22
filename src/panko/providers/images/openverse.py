"""Openverse search (CC-licensed images from Flickr, Commons, museums...). Anonymous use is rate-limited."""
from __future__ import annotations

import httpx

from panko.providers import register
from panko.providers.base import ImageSearch


@register("images", "openverse")
class Openverse(ImageSearch):
    def search(self, query, limit=6):
        r = httpx.get("https://api.openverse.org/v1/images/", timeout=30,
                      params={"q": query, "page_size": limit, "mature": "false"})
        r.raise_for_status()
        return [{"url": x["url"], "thumb": x.get("thumbnail") or x["url"], "title": x.get("title"),
                 "author": x.get("creator") or "", "license": f"CC {x.get('license', '').upper()} {x.get('license_version', '')}".strip(),
                 "page": x.get("foreign_landing_url")} for x in r.json().get("results", [])]
