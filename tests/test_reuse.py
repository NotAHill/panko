"""Pictures you already have: matched by meaning, shared as the same file, offered first in a search."""
import json

import pytest

from panko.media import pictures, reuse
from panko.store import Store


@pytest.fixture
def st(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(reuse, "_media", lambda: media)
    monkeypatch.setattr(pictures, "_media", lambda: media)
    for f in ("glass.jpg", "pane.jpg", "tea.jpg"):
        (media / f).write_bytes(b"jpg")
    s = Store(tmp_path / "s.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "كاس", "gloss": "glass (for drinking)", "pos": "noun",
           "image": {"file": "glass.jpg", "credit": "Commons · CC BY"}}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "زاج", "gloss": "glass (material)", "pos": "noun",
           "image": {"file": "pane.jpg", "credit": "Openverse · CC0"}}, status="active")
    s.put({"id": "dw-3", "kind": "word", "variety": "darija", "ar": "أتاي", "gloss": "tea", "pos": "noun",
           "image": {"file": "tea.jpg", "credit": "drawn", "prompt": "a teapot"}}, status="active")
    s.put({"id": "dw-4", "kind": "word", "variety": "darija", "ar": "ورقة", "gloss": "leaf", "pos": "noun",
           "image": {"file": "gone.jpg"}}, status="active")                     # its file isn't here: not offered
    s.put({"id": "fs-1", "kind": "word", "variety": "fusha", "ar": "شاي", "gloss": "Tea.", "pos": "noun",
           "picture_pref": "none"}, status="candidate")
    s.put({"id": "fs-2", "kind": "word", "variety": "fusha", "ar": "كأس", "gloss": "a glass; cup", "pos": "noun"},
          status="candidate")
    s.put({"id": "fs-3", "kind": "word", "variety": "fusha", "ar": "ورق", "gloss": "leaf", "pos": "noun"}, status="candidate")
    return s


def test_the_main_sense_of_a_gloss():
    assert reuse.key("a glass (for tea); cup") == "glass" and reuse.key("to eat, to dine") == "eat"
    assert reuse.key("Tea.") == "tea" and reuse.key("yes/no question particle") == "yes no question particle"


def test_cards_that_mean_the_same_are_matched_and_only_clear_ones_are_sure(st):
    cards = [{"id": i, **{k: st.get(i)[k] for k in ("ar", "gloss", "pos")}} for i in ("fs-1", "fs-2", "fs-3")]
    got = {m["id"]: m for m in reuse.matches(st, cards)}
    assert set(got) == {"fs-1", "fs-2"}                          # the leaf's picture file is gone
    assert got["fs-1"]["sure"] and got["fs-1"]["sources"][0]["id"] == "dw-3"
    glass = got["fs-2"]
    assert not glass["sure"] and {s["id"] for s in glass["sources"]} == {"dw-1", "dw-2"}   # a cup, or the material?


def test_using_one_shares_the_file_and_says_what_it_shows(st):
    im = reuse.use(st, "fs-1", "dw-3")
    e = st.get("fs-1")
    assert e["image"]["file"] == "tea.jpg" and e["image"]["credit"] == "drawn" and im["reused_from"] == "dw-3"
    assert e["image"]["meaning"] == {"gloss": "tea", "pos": "noun"} and "picture_pref" not in e
    with pytest.raises(ValueError):
        reuse.use(st, "fs-3", "dw-4")                            # nothing to share


def test_your_pictures_come_first_in_a_search_and_are_never_downloaded(st, tmp_path):
    got = reuse.search("glass", store=st)
    assert [c["source_id"] for c in got] == ["dw-1", "dw-2"] and got[0]["thumb"] == "/media/glass.jpg"
    assert got[0]["provider"] == "yours" and got[0]["author"] == "Darija"
    assert [c["source_id"] for c in reuse.search("tea", store=st)] == ["dw-3"]
    run = tmp_path / "run"
    run.mkdir()
    (run / "cands.json").write_text(json.dumps({"fs-2": got}))
    fetched = []
    r = pictures.apply({"fs-2": {"photo": {"dir": str(run), "index": 0}}}, store=st, out=reuse._media(),
                       download=lambda c, p: fetched.append(p))
    im = st.get("fs-2")["image"]
    assert r["photo"] == 1 and not fetched and im["file"] == "glass.jpg" and im["credit"] == "Commons · CC BY"
    assert im["provider"] == "yours" and im["reused_from"] == "dw-1" and im["meaning"]["gloss"] == "a glass; cup"


def test_photos_apply_in_a_new_panko_with_no_media_folder(tmp_path, monkeypatch):
    import panko.config
    home = tmp_path / "home"
    monkeypatch.setattr(panko.config, "ROOT", home)               # nothing saved yet: no data/media
    s = Store(tmp_path / "s.db")
    s.put({"id": "iq-1", "kind": "word", "variety": "iraqi", "ar": "كرسي", "gloss": "chair", "pos": "noun"},
          status="active")
    run = tmp_path / "run"
    run.mkdir()
    (run / "cands.json").write_text(json.dumps({"iq-1": [{"thumb": "https://x/chair.jpg", "provider": "commons",
                                                          "page": "https://x", "author": "A", "license": "CC0"}]}))
    r = pictures.apply({"iq-1": {"photo": {"dir": str(run), "index": 0}}}, store=s,
                       download=lambda c, p: p.write_bytes(b"jpg"))
    media = home / "data" / "media"
    assert r["photo"] == 1 and not r["failed"] and s.get("iq-1")["image"]["file"] == "_panko_proto_iq-1.jpg"
    assert (media / "_panko_proto_iq-1.jpg").exists() and "_panko_proto_iq-1.jpg" in json.loads(
        (media / "credits.json").read_text())
