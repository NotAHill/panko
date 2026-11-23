from PIL import Image

from panko.media.pictures import GEN_PREFIX, draw
from panko.store import Store


class FakeGen:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, out):
        self.prompts.append(prompt)
        Image.new("RGB", (1024, 1024), "white").save(out)


def test_draw_sets_picture_and_skips_entries_with_one(tmp_path):
    s = Store(tmp_path / "t.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "نسى", "gloss": "to forget"}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "قط", "gloss": "cat",
           "image": {"file": "cat.jpg", "credit": "Commons"}}, status="active")
    g = FakeGen()
    r = draw({"dw-1": "keys left on the table", "dw-2": "a cat"}, store=s, out=tmp_path, gen=g)
    assert list(r) == ["dw-1"] and g.prompts == ["keys left on the table"]   # real picture kept
    img = s.get("dw-1")["image"]
    assert img["file"] == f"{GEN_PREFIX}dw-1.jpg" and (tmp_path / img["file"]).exists()
    assert img["credit"].startswith("Illustration generated")
    assert not list(tmp_path.glob("*.png"))


def _store(tmp_path):
    s = Store(tmp_path / "t.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "قط", "gloss": "cat"}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "نسى", "gloss": "to forget"}, status="active")
    s.put({"id": "dw-3", "kind": "word", "variety": "darija", "ar": "ف", "gloss": "in"}, status="active")
    return s


def test_export_lists_cards_without_picture(tmp_path):
    from panko.media.pictures import export
    s = _store(tmp_path)
    e = s.get("dw-1")
    e["image"] = {"file": "x.jpg"}
    s.put(e)
    assert [r["id"] for r in export(s)] == ["dw-2", "dw-3"]


def test_apply_downloads_photos_credits_them_and_returns_prompts(tmp_path):
    import json

    from panko.media.pictures import apply
    s = _store(tmp_path)
    run = tmp_path / "run01"
    run.mkdir()
    (run / "cands.json").write_text(json.dumps({"dw-1": [{"thumb": "t0"}, {"thumb": "t1", "provider": "commons",
                                    "page": "https://c/cat", "author": "Ann", "license": "CC BY 4.0"}]}))

    def fake_download(c, path):
        assert c["thumb"] == "t1"
        path.write_bytes(b"jpg")

    r = apply({"dw-1": {"photo": {"dir": str(run), "index": 1}}, "dw-2": {"prompt": "keys left behind"},
               "dw-3": {"skip": "grammar word"}}, store=s, out=tmp_path, download=fake_download)
    assert r["photo"] == 1 and r["skip"] == 1 and r["prompts"] == {"dw-2": "keys left behind"}
    img = s.get("dw-1")["image"]
    assert img["file"] == "_panko_proto_dw-1.jpg" and "Wikimedia Commons" in img["credit"] and "Ann" in img["credit"]
    assert "_panko_proto_dw-1.jpg" in json.loads((tmp_path / "credits.json").read_text())


class FakeBatchGen:
    def __init__(self):
        self.submitted = {}

    def batch_submit(self, prompts):
        self.submitted = prompts
        return "batch_1"

    def batch_status(self, bid):
        return {"id": bid, "status": "completed"}

    def batch_results(self, b):
        import io
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), "white").save(buf, "PNG")
        return {"dw-2": buf.getvalue(), "dw-3": "error: refused"}


def test_batch_submit_then_collect(tmp_path, monkeypatch):
    from panko.media import pictures
    s = _store(tmp_path)
    monkeypatch.setattr(pictures, "_batches_file", lambda: tmp_path / "draw-batches.json")
    g = FakeBatchGen()
    assert pictures.draw_batch({"dw-2": "keys", "dw-3": "inside"}, store=s, gen=g) == "batch_1"
    assert g.submitted == {"dw-2": "keys", "dw-3": "inside"}
    rep = pictures.collect(store=s, out=tmp_path, gen=g)
    assert rep["batch_1"]["saved"] == 1 and rep["batch_1"]["errors"] == 1
    assert s.get("dw-2")["image"]["file"] == f"{GEN_PREFIX}dw-2.jpg" and not s.get("dw-3").get("image")
    assert pictures.collect(store=s, out=tmp_path, gen=g) == {}   # already collected


def test_to_jpeg_flattens_transparency_and_only_shrinks(tmp_path):
    import io

    from panko.media.pictures import _to_jpeg
    buf = io.BytesIO()
    Image.new("RGBA", (1600, 400), (0, 0, 0, 0)).save(buf, "PNG")    # transparent pictogram
    _to_jpeg(buf.getvalue(), tmp_path / "big.jpg", 800, 85)
    with Image.open(tmp_path / "big.jpg") as im:
        assert im.format == "JPEG" and im.size == (800, 200) and im.getpixel((10, 10)) > (240, 240, 240)
    Image.new("RGB", (100, 50), "red").save(tmp_path / "small.png")
    _to_jpeg(tmp_path / "small.png", tmp_path / "small.jpg", 640, 80)
    with Image.open(tmp_path / "small.jpg") as im:
        assert im.size == (100, 50)
