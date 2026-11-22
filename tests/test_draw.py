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
