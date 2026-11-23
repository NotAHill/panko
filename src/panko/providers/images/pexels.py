"""Pexels photo search. Free key (PEXELS_API_KEY); default limit 200 requests an hour, 20,000 a month.
Pexels License: free to use and download, no attribution required; we credit the photographer and Pexels anyway,
as the API guidelines ask. Answers are cached, so re-running a search costs nothing."""
from __future__ import annotations

from panko.config import secret
from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import get_json


@register("images", "pexels")
class Pexels(ImageSearch):
    label = "Pexels"
    needs = ("PEXELS_API_KEY",)

    def search(self, query, limit=6):
        data = get_json("pexels", "https://api.pexels.com/v1/search", gap=1.0,
                        headers={"Authorization": secret("PEXELS_API_KEY") or ""},
                        params={"query": query, "per_page": limit, "size": "medium"})
        return [{"url": x["src"].get("original"), "thumb": x["src"].get("large") or x["src"].get("medium"),
                 "title": x.get("alt") or "", "author": x.get("photographer") or "", "license": "Pexels License",
                 "page": x.get("url")} for x in data.get("photos", []) if x.get("src")]
