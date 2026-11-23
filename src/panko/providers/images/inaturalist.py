"""iNaturalist taxa search: one photo per matching species, for animals and plants. No key; iNaturalist asks for
about one request a second. Only openly licensed photos are kept (many are "all rights reserved").
Off by default: add "inaturalist" to the [images] chain, or `panko pictures search --providers inaturalist`."""
from __future__ import annotations

import re

from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import get_json


def licence(code: str) -> str:
    code = code.lower()
    return "CC0" if code == "cc0" else "CC " + code.removeprefix("cc-").upper()


def author(attribution: str) -> str:
    """"(c) Jane Doe, some rights reserved (CC BY)" or "no rights reserved, uploaded by Jane Doe" → "Jane Doe"."""
    a = attribution or ""
    m = re.match(r"\(c\)\s*(.*?),\s*(some|all|no) rights", a) or re.search(r"uploaded by\s+(.+?)\s*$", a)
    return m.group(1) if m else a


@register("images", "inaturalist")
class INaturalist(ImageSearch):
    label = "iNaturalist"

    def search(self, query, limit=6):
        data = get_json("inaturalist", "https://api.inaturalist.org/v1/taxa", gap=1.0,
                        params={"q": query, "is_active": "true", "per_page": max(limit, 5), "locale": "en"})
        out = []
        for t in data.get("results", []):
            ph = t.get("default_photo") or {}
            if not ph.get("license_code") or not ph.get("medium_url"):
                continue
            name = t.get("preferred_common_name") or ""
            out.append({"url": ph.get("original_url") or ph["medium_url"], "thumb": ph["medium_url"],
                        "title": f"{name} ({t.get('name', '')})" if name else t.get("name", ""),
                        "author": author(ph.get("attribution", "")), "license": licence(ph["license_code"]),
                        "page": f"https://www.inaturalist.org/taxa/{t['id']}"})
        return out[:limit]
