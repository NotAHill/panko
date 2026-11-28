"""The picture pool of a hosted Panko (picture reuse stage 2): what is shared, who sees it, and how a Panko uses it."""
import os
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("starlette")
pytest.importorskip("argon2")

from starlette.testclient import TestClient  # noqa: E402

from panko.host import app as host_app  # noqa: E402
from panko.host.pankos import Running  # noqa: E402
from panko.host.pool import Pool, kind_of, open_licence, prefs  # noqa: E402
from panko.store import Store  # noqa: E402

PW = "a-long-test-password"


@pytest.fixture
def data():
    d = Path(tempfile.mkdtemp(prefix="pkp-", dir="/tmp" if os.path.isdir("/tmp") else None))
    yield d


def a_panko(home: Path, cards: list[tuple], hub_toml: str = "") -> None:
    """A user's folder: cards (id, gloss, pos, image or None) and their media files."""
    (home / "data" / "media").mkdir(parents=True, exist_ok=True)
    (home / "config").mkdir(parents=True, exist_ok=True)
    if hub_toml:
        (home / "config" / "hub.toml").write_text(hub_toml)
    s = Store(home / "data" / "panko.db")
    for eid, gloss, pos, im in cards:
        e = {"id": eid, "kind": "word", "variety": "iraqi", "ar": "خبز", "gloss": gloss, "pos": pos}
        if im:
            (home / "data" / "media" / im["file"]).write_bytes(f"jpeg of {im['file']}".encode())
            e["image"] = im
        s.put(e, status="active")


BREAD = {"file": "_panko_photo_a1.jpg", "provider": "commons", "license": "CC BY-SA 4.0", "credit": "Photo: X (CC BY-SA)",
         "page": "https://commons.example/bread"}


def test_only_pictures_anyone_may_share_go_in():
    for lic in ("CC BY 4.0", "CC BY-SA 3.0", "CC CC0 1.0", "Public domain", "CC PDM 1.0", "cc-by-sa"):
        assert open_licence(lic), lic
    for lic in ("CC BY-NC-SA 4.0", "CC BY-ND 4.0", "Pexels License", "Pixabay Content License", "", "All rights reserved"):
        assert not open_licence(lic), lic
    assert kind_of(BREAD, True, False) == "photo"
    assert kind_of(BREAD, False, True) is None
    assert kind_of({**BREAD, "provider": "source", "license": "CC0"}, True, True) is None      # cut from your sheet
    assert kind_of({**BREAD, "reused_from": "x"}, True, True) is None
    drawn = {"file": "_panko_gen_a.jpg", "provider": "generate", "prompt": "a loaf"}
    assert kind_of(drawn, True, False) is None and kind_of(drawn, True, True) == "drawing"


def test_a_config_that_cant_be_read_shares_nothing(tmp_path):
    (tmp_path / "config").mkdir()
    assert prefs(tmp_path) == {"use": True, "share": True, "share_drawings": False}
    (tmp_path / "config" / "hub.toml").write_text("[images\nbroken")
    assert prefs(tmp_path)["share"] is False


def test_the_pool_fills_from_cards_and_never_tells_who(data):
    pool = Pool(data)
    amina, omar = data / "users" / "u1", data / "users" / "u2"
    a_panko(amina, [("a1", "bread (a loaf)", "noun", BREAD),
                    ("a2", "glass", "noun", {"file": "_panko_photo_a2.jpg", "provider": "pexels", "license": "Pexels License"}),
                    ("a3", "door", "noun", {"file": "_panko_src_a3.jpg", "provider": "source", "license": ""}),
                    ("a4", "to eat", "verb", {"file": "_panko_gen_a4.jpg", "provider": "generate", "prompt": "eating"})])
    a_panko(omar, [("o1", "bread", "noun", None)])
    assert pool.fill([("u1", amina), ("u2", omar)]) == {"u1": 1, "u2": 0}
    got = pool.search("bread", "u2")
    assert len(got) == 1 and got[0]["license"] == "CC BY-SA 4.0" and got[0]["credit"] == BREAD["credit"]
    assert set(got[0]) == {"name", "kind", "license", "credit", "page"}         # no user, card or gloss
    assert pool.search("bread", "u1") == []                                      # your own come from your Panko
    assert pool.search("glass", "u2") == [] and pool.search("eat", "u2") == []
    assert pool.path(got[0]["name"]).read_bytes() == b"jpeg of _panko_photo_a1.jpg"
    assert pool.path("../host.db") is None
    # she shares her drawings too: one more; then stops sharing photos: only the drawing is left
    (amina / "config" / "hub.toml").write_text("[images]\nshare_drawings = true\n")
    pool.fill([("u1", amina), ("u2", omar)])
    assert [x["kind"] for x in pool.search("eat", "u2")] == ["drawing"]
    (amina / "config" / "hub.toml").write_text("[images]\nshare = false\nshare_drawings = true\n")
    pool.fill([("u1", amina), ("u2", omar)])
    assert pool.search("bread", "u2") == [] and pool.stats()["pictures"] == 1
    # she leaves: everything only she shared goes
    pool.fill([("u2", omar)])
    assert pool.stats() == {"pictures": 0, "bytes": 0, "drawings": 0, "people": 0}
    assert not [p for p in (data / "pool").iterdir()]


def test_two_people_with_the_same_photo_keep_one_copy(data):
    pool = Pool(data)
    for uid in ("u1", "u2"):
        a_panko(data / "users" / uid, [(f"{uid}-1", "bread", "noun", BREAD)])
    pool.fill([("u1", data / "users" / "u1"), ("u2", data / "users" / "u2")])
    assert pool.stats()["pictures"] == 1 and pool.stats()["people"] == 2
    pool.forget("u1")
    assert pool.stats()["pictures"] == 1                                         # still u2's
    a_panko(data / "users" / "u3", [])
    assert len(pool.search("bread", "u3")) == 1


class _Alive:
    def poll(self):
        return None


def test_only_a_panko_here_can_search_and_only_signed_in_people_see_files(data):
    a = host_app.app(data)
    door = a.state.door
    c = TestClient(a, base_url="http://door.test", follow_redirects=False)
    assert c.get("/host/pool/search?q=bread").status_code == 403
    assert c.get("/host/pool/search?q=bread", headers={"X-Panko-Front": "guess"}).status_code == 403
    assert c.get("/host/pool/file/0123456789abcdef01234567.jpg").status_code == 401
    a_panko(data / "users" / "u1", [("a1", "bread", "noun", BREAD)])
    door.pool.fill([("u1", data / "users" / "u1")])
    door.pankos.running["u2"] = Running(_Alive(), data / "run" / "u2.sock", "u2-secret-0123456789")
    r = c.get("/host/pool/search?q=bread", headers={"X-Panko-Front": "u2-secret-0123456789"})
    assert r.status_code == 200 and len(r.json()["pictures"]) == 1
    name = r.json()["pictures"][0]["name"]
    f = c.get(f"/host/pool/file/{name}", headers={"X-Panko-Front": "u2-secret-0123456789"})
    assert f.status_code == 200 and f.content == b"jpeg of _panko_photo_a1.jpg"
    door.pankos.running.clear()


def test_the_pool_registers_like_the_other_sources():
    """In a fresh process (here it's imported by the tests): a provider file the package doesn't import never
    registers, which once left the pool out on the server."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", "from panko import providers; print(providers.available('images'))"],
                         capture_output=True, text=True, check=True).stdout
    assert "'pool'" in out and "'yours'" in out


def test_a_panko_offers_the_pool_and_takes_a_picture_from_it(tmp_path, monkeypatch):
    from panko import providers
    from panko.media import pictures
    from panko.providers.images import pool as P
    monkeypatch.setenv("PANKO_HOSTED", "1")
    monkeypatch.setenv("PANKO_POOL_URL", "http://127.0.0.1:1/host/pool")
    asked = {}

    class R:
        def __init__(self, body):
            self.body = body
            self.content = body if isinstance(body, bytes) else b""

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def fake(path, **kw):
        asked[path] = kw
        if path == "/search":
            return R({"pictures": [{"name": "ab" * 12 + ".jpg", "kind": "photo", "license": "CC BY 4.0",
                                    "credit": "Photo: Y (CC BY)", "page": "https://p"}]})
        from io import BytesIO

        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (40, 30), (200, 150, 90)).save(buf, "JPEG")
        return R(buf.getvalue())
    monkeypatch.setattr(P, "_ask", fake)
    assert "pool" in [p.name for p in pictures._searchers()]
    cands = providers.get("images", "pool").search("bread")
    assert cands[0]["thumb"].startswith("/host/pool/file/") and asked["/search"]["params"]["q"] == "bread"
    s = Store(tmp_path / "t.db")
    s.put({"id": "o1", "kind": "word", "variety": "iraqi", "ar": "خبز", "gloss": "bread", "pos": "noun"}, status="active")
    im = pictures.use("o1", {**cands[0], "provider": "pool"}, store=s, out=tmp_path)
    assert im["provider"] == "pool" and im["credit"] == "Photo: Y (CC BY)" and im["license"] == "CC BY 4.0"
    assert (tmp_path / im["file"]).exists() and any(k.startswith("/file/") for k in asked)
    assert kind_of(im, True, True) is None                    # taken from the pool: not shared back as new
    monkeypatch.delenv("PANKO_POOL_URL")
    assert "pool" not in [p.name for p in pictures._searchers()]
