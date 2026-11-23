"""Pixabay photo search. Free key (PIXABAY_API_KEY); 100 requests a minute; Pixabay asks that answers be cached for
24 hours, and its image links expire after 24 hours, so `fresh` looks the photo up again before downloading.
Pixabay Content License: free to use and download, no attribution required; we credit the author and Pixabay."""
from __future__ import annotations

from panko.config import secret
from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import get_json

API = "https://pixabay.com/api/"
DAY = 86400


def _cand(x: dict) -> dict:
    return {"url": x.get("largeImageURL"), "thumb": x.get("webformatURL"), "title": x.get("tags") or "",
            "author": x.get("user") or "", "license": "Pixabay Content License", "page": x.get("pageURL"),
            "id": x.get("id")}


@register("images", "pixabay")
class Pixabay(ImageSearch):
    label = "Pixabay"
    needs = ("PIXABAY_API_KEY",)

    def search(self, query, limit=6):
        data = get_json("pixabay", API, gap=0.7, ttl=DAY, params={
            "key": secret("PIXABAY_API_KEY") or "", "q": query[:100], "image_type": "photo", "safesearch": "true",
            "per_page": max(limit, 3), "lang": "en"})
        return [_cand(x) for x in data.get("hits", [])][:limit]

    def fresh(self, c):
        if not c.get("id"):
            return c
        data = get_json("pixabay", API, gap=0.7, ttl=3600, params={"key": secret("PIXABAY_API_KEY") or "",
                                                                     "id": c["id"]})
        hits = data.get("hits", [])
        return {**c, **{k: v for k, v in _cand(hits[0]).items() if v}} if hits else c
