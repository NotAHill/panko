"""Wikidata: the query → matching Wikidata items → each item's main image (P18), a file on Wikimedia Commons.
Precise for concrete nouns (animals, food, tools); finds little for actions or long descriptive queries. No key."""
from __future__ import annotations

import re

from panko.providers import register
from panko.providers.base import ImageSearch
from panko.providers.images.commons import API as COMMONS
from panko.providers.images.commons import IMAGEINFO, candidate
from panko.providers.images.web import get_json

API = "https://www.wikidata.org/w/api.php"


def label_query(query: str) -> str:
    """Wikidata matches labels, so drop leading articles: "a hammer" → "hammer"."""
    return re.sub(r"^(a|an|the)\s+", "", query.strip(), flags=re.I)


@register("images", "wikidata")
class Wikidata(ImageSearch):
    label = "Wikimedia Commons"     # the picture itself is a Commons file

    def search(self, query, limit=6):
        if re.match(r"\s*to\s", query, flags=re.I):   # a verb: Wikidata's matches would be nouns ("to run" → a brook)
            return []
        found = get_json("wikidata", API, gap=0.2, params={
            "action": "wbsearchentities", "format": "json", "language": "en", "uselang": "en", "type": "item",
            "search": label_query(query), "limit": max(limit, 5)}).get("search", [])
        if not found:
            return []
        ids = [x["id"] for x in found]
        ents = get_json("wikidata", API, gap=0.2, params={
            "action": "wbgetentities", "format": "json", "props": "claims", "ids": "|".join(ids)}).get("entities", {})
        files, item_of = [], {}
        for x in found:                                  # keep the search's ranking
            for claim in ents.get(x["id"], {}).get("claims", {}).get("P18", [])[:1]:
                name = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if name and f"File:{name}" not in item_of:
                    files.append(f"File:{name}")
                    item_of[f"File:{name}"] = x
        files = files[:limit]
        if not files:
            return []
        pages = get_json("commons", COMMONS, gap=0.2, params={
            "action": "query", "format": "json", "titles": "|".join(files), **IMAGEINFO}).get("query", {})
        norm = {n["to"]: n["from"] for n in pages.get("normalized", [])}
        by_title = {norm.get(p.get("title"), p.get("title")): p for p in pages.get("pages", {}).values()}
        out = []
        for f in files:
            p = by_title.get(f)
            if not p or "imageinfo" not in p:
                continue
            item = item_of[f]
            c = candidate(p)
            c["title"] = f"{item.get('label', '')} ({item.get('description', '')}) · {p.get('title')}"
            c["item"] = item.get("concepturi") or f"https://www.wikidata.org/wiki/{item['id']}"
            out.append(c)
        return out
