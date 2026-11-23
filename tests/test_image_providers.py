"""Picture search providers, with HTTP mocked: each answer is a canned response routed by host."""
import httpx
import pytest

from panko import providers
from panko.providers.images import web


@pytest.fixture
def http(monkeypatch, tmp_path):
    """Route httpx.get by URL substring → JSON (or (status, JSON, headers)). Records every call."""
    from panko import config
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(web, "sleep", lambda s: None)
    web.reset()
    routes, calls = {}, []

    def fake_get(url, params=None, headers=None, **kw):
        calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        for key, answer in routes.items():
            if key in url:
                ans = answer(params or {}) if callable(answer) else answer
                status, body, hdrs = ans if isinstance(ans, tuple) else (200, ans, {})
                return httpx.Response(status, json=body, headers=hdrs, request=httpx.Request("GET", url))
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(web.httpx, "get", fake_get)
    yield routes, calls
    web.reset()


def commons_page(title, idx=0):
    return {"title": title, "index": idx, "imageinfo": [{
        "url": f"https://upload/{title}", "thumburl": f"https://thumb/{title}", "descriptionurl": f"https://c/{title}",
        "extmetadata": {"Artist": {"value": '<a href="u">Ann</a>'}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]}


def test_wikidata_finds_the_items_commons_picture(http):
    routes, calls = http

    def wikidata(params):
        if params["action"] == "wbsearchentities":
            assert params["search"] == "donkey"                      # article dropped
            return {"search": [{"id": "Q19707", "label": "donkey", "description": "equine with long ears"},
                               {"id": "Q1", "label": "Donkey", "description": "a film"}]}
        assert params["ids"] == "Q19707|Q1"
        return {"entities": {"Q19707": {"claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Donkey 1.jpg"}}}]}},
                             "Q1": {"claims": {}}}}

    routes["wikidata.org"] = wikidata
    routes["commons.wikimedia.org"] = lambda p: {"query": {
        "normalized": [{"from": "File:Donkey 1.jpg", "to": "File:Donkey 1.jpg"}],
        "pages": {"5": commons_page("File:Donkey 1.jpg")}}}
    [c] = providers.get("images", "wikidata").search("a donkey", 3)
    assert c["thumb"] == "https://thumb/File:Donkey 1.jpg" and c["author"] == "Ann" and c["license"] == "CC BY-SA 4.0"
    assert c["title"].startswith("donkey (equine with long ears)") and c["item"].endswith("Q19707")
    assert calls[-1]["params"]["titles"] == "File:Donkey 1.jpg"


def test_wikidata_skips_verbs_and_misses(http):
    routes, calls = http
    routes["wikidata.org"] = {"search": []}
    wd = providers.get("images", "wikidata")
    assert wd.search("to run") == [] and calls == []
    assert wd.search("zzqx") == [] and len(calls) == 1


def test_results_are_cached_without_the_key(http, monkeypatch):
    routes, calls = http
    monkeypatch.setenv("PIXABAY_API_KEY", "secret-key")
    routes["pixabay.com"] = {"hits": [{"id": 7, "webformatURL": "https://px/7_640.jpg", "largeImageURL": "https://px/7.jpg",
                                       "tags": "mint, tea", "user": "Bo", "pageURL": "https://pixabay.com/photos/7"}]}
    pb = providers.get("images", "pixabay")
    first = pb.search("mint tea", 3)
    assert pb.search("mint tea", 3) == first and len(calls) == 1
    assert calls[0]["params"]["safesearch"] == "true"
    from panko import config
    files = list((config.CACHE / "images" / "pixabay").glob("*.json"))
    assert files and all("secret-key" not in f.name for f in files)
    assert first[0] == {"url": "https://px/7.jpg", "thumb": "https://px/7_640.jpg", "title": "mint, tea", "author": "Bo",
                        "license": "Pixabay Content License", "page": "https://pixabay.com/photos/7", "id": 7}


def test_pixabay_refreshes_expiring_links(http, monkeypatch):
    routes, _ = http
    monkeypatch.setenv("PIXABAY_API_KEY", "k")
    routes["pixabay.com"] = lambda p: {"hits": [{"id": 7, "webformatURL": "https://px/new_640.jpg"}]} if "id" in p else {}
    c = providers.get("images", "pixabay").fresh({"id": 7, "thumb": "https://px/old.jpg", "author": "Bo"})
    assert c["thumb"] == "https://px/new_640.jpg" and c["author"] == "Bo"


def test_pexels_sends_the_key_as_a_header(http, monkeypatch):
    routes, calls = http
    monkeypatch.setenv("PEXELS_API_KEY", "pk")
    routes["api.pexels.com"] = {"photos": [{"url": "https://pexels.com/photo/1", "photographer": "Cy", "alt": "a donkey",
                                            "src": {"original": "https://o/1.jpg", "large": "https://l/1.jpg"}}]}
    [c] = providers.get("images", "pexels").search("donkey", 2)
    assert calls[0]["headers"]["Authorization"] == "pk"
    assert c["thumb"] == "https://l/1.jpg" and c["author"] == "Cy" and c["license"] == "Pexels License"


def test_keyed_providers_are_not_ready_without_keys(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    names = [p.name for p in providers.chain("images")]
    assert "pexels" not in names and "pixabay" not in names and "wikidata" in names
    monkeypatch.setenv("PEXELS_API_KEY", "pk")
    assert "pexels" in [p.name for p in providers.chain("images")]


def test_inaturalist_keeps_only_open_licences(http):
    routes, _ = http
    routes["api.inaturalist.org"] = {"results": [
        {"id": 1, "name": "Opuntia", "preferred_common_name": "Prickly Pears",
         "default_photo": {"license_code": "cc-by-nc", "medium_url": "https://i/1.jpg",
                           "attribution": "(c) Peri, some rights reserved (CC BY-NC)"}},
        {"id": 2, "name": "Closed", "default_photo": {"license_code": None, "medium_url": "https://i/2.jpg"}},
        {"id": 3, "name": "Free", "default_photo": {"license_code": "cc0", "medium_url": "https://i/3.jpg",
                                                     "attribution": "no rights reserved, uploaded by Owen"}}]}
    a, b = providers.get("images", "inaturalist").search("prickly pear")
    assert (a["title"], a["author"], a["license"]) == ("Prickly Pears (Opuntia)", "Peri", "CC BY-NC")
    assert (b["author"], b["license"], b["page"]) == ("Owen", "CC0", "https://www.inaturalist.org/taxa/3")


def test_arasaac_pictograms_and_no_match(http):
    routes, _ = http
    routes["/search/cook"] = [{"_id": 2857, "keywords": [{"keyword": "cook"}]}]
    routes["/search/zzqx"] = (404, {"error": "not found"}, {})
    ar = providers.get("images", "arasaac")
    [c] = ar.search("cook")
    assert c["thumb"].endswith("/2857/2857_500.png") and c["license"] == "CC BY-NC-SA 4.0"
    assert "ARASAAC" in c["author"]
    assert ar.search("zzqx") == []


def test_rate_limit_waits_once_then_pauses_the_site(http, monkeypatch):
    routes, calls = http
    answers = iter([(429, {}, {"Retry-After": "2"}), {"results": []}])
    routes["api.openverse.org"] = lambda p: next(answers)
    ov = providers.get("images", "openverse")
    assert ov.search("tea") == [] and len(calls) == 2                       # short wait, then retry
    routes["api.openverse.org"] = (429, {}, {"Retry-After": "3600"})
    with pytest.raises(web.RateLimited):
        ov.search("cat")
    n = len(calls)
    with pytest.raises(web.RateLimited):
        ov.search("dog")                                                     # paused: no new request
    assert len(calls) == n


class Fake:
    def __init__(self, name, n):
        self.name, self.n = name, n

    def search(self, query, limit=6):
        return [{"thumb": f"{self.name}{i}", "page": "p", "author": "a", "license": "l"} for i in range(min(self.n, limit))]


def test_candidates_take_turns_across_sites(monkeypatch):
    from panko.media import pictures
    monkeypatch.setattr(pictures.providers, "chain", lambda cap, names=None: [Fake("wd", 1), Fake("cm", 3), Fake("px", 3)])
    got = [c["thumb"] for c in pictures.candidates("donkey", 3)]
    assert got == ["wd0", "cm0", "px0", "cm1", "px1", "cm2", "px2"]
    assert pictures.candidates("donkey", 3)[2]["provider"] == "px"


def test_contact_sheet_shows_every_site(monkeypatch, tmp_path):
    import json

    from PIL import Image

    from panko.media import pictures
    monkeypatch.setattr(pictures.providers, "chain",
                        lambda cap, names=None: [Fake(n, 5) for n in ("wd", "cm", "ov", "px", "pb")])
    sheets = pictures.search({"dw-1": "donkey"}, tmp_path, fetch=lambda c: Image.new("RGB", (50, 50), "gray"))
    cands = json.loads((tmp_path / "cands.json").read_text())["dw-1"]
    assert len(cands) == 10 and {c["provider"] for c in cands} == {"wd", "cm", "ov", "px", "pb"}
    assert sheets[0].exists()


def test_credit_names_the_site():
    from panko.media.pictures import _credit
    assert ">Pexels</a> · Cy · Pexels License" in _credit({"provider": "pexels", "page": "u", "author": "Cy",
                                                           "license": "Pexels License"})
    assert ">Wikimedia Commons</a>" in _credit({"provider": "wikidata"})
    assert ">Openverse</a>" in _credit({"provider": "openverse"})
