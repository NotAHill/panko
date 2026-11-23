"""Openverse search (CC-licensed images from Flickr, Commons, museums...). Anonymous use is rate-limited."""
from __future__ import annotations

from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import get_json


@register("images", "openverse")
class Openverse(ImageSearch):
    label = "Openverse"

    def search(self, query, limit=6):
        data = get_json("openverse", "https://api.openverse.org/v1/images/", gap=1.0,
                        params={"q": query, "page_size": limit, "mature": "false"})
        return [{"url": x["url"], "thumb": x.get("thumbnail") or x["url"], "title": x.get("title"),
                 "author": x.get("creator") or "",
                 "license": f"CC {x.get('license', '').upper()} {x.get('license_version', '')}".strip(),
                 "page": x.get("foreign_landing_url")} for x in data.get("results", [])]
