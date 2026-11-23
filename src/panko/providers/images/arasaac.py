"""ARASAAC pictograms (Government of Aragón), useful for verbs and actions a photo can't show. No key.
Licence CC BY-NC-SA 4.0: personal, non-commercial use only. The style is a flat pictogram, not the hand-made look
the cards aim for, so it is off by default: add "arasaac" to the [images] chain, or
`panko pictures search --providers arasaac`."""
from __future__ import annotations

from urllib.parse import quote

from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.web import get_json

AUTHOR = "Sergio Palao (ARASAAC, Government of Aragón)"


@register("images", "arasaac")
class Arasaac(ImageSearch):
    label = "ARASAAC"

    def search(self, query, limit=6):
        data = get_json("arasaac", f"https://api.arasaac.org/api/pictograms/en/search/{quote(query.strip())}",
                        gap=0.5, missing=[])        # 404 = no pictogram for this word
        out = []
        for x in data[:limit]:
            pid = x.get("_id")
            if pid is None:
                continue
            words = ", ".join(k.get("keyword", "") for k in x.get("keywords", [])[:3])
            out.append({"url": f"https://static.arasaac.org/pictograms/{pid}/{pid}_2500.png",
                        "thumb": f"https://static.arasaac.org/pictograms/{pid}/{pid}_500.png",
                        "title": words, "author": AUTHOR, "license": "CC BY-NC-SA 4.0",
                        "page": f"https://arasaac.org/pictograms/en/{pid}"})
        return out
