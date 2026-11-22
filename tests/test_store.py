import json

from panko.ingest import activate, ingest
from panko.store import Store
from panko.store.normalize import bare, strip_article


def test_normalise_matches_variants():
    assert bare("قِطْعَة") == "قطعة"
    assert bare("أَرِيكَة") == bare("اريكة")
    assert strip_article("الكنابي") == "كنابي"


def test_ingest_new_vs_known(tmp_path):
    s = Store(tmp_path / "t.db")
    s.put({"id": "x1", "kind": "word", "variety": "darija", "ar": "كنابي", "gloss": "sofa"}, status="active")
    x = {"source": {"id": "lesson-1", "kind": "lesson", "title": "Lesson 1", "date": "2026-11-21", "trust": 90},
         "items": [{"kind": "word", "variety": "darija", "ar": "الكنابي", "gloss": "sofa", "role": "used",
                    "said": {"ar": "الكنابي كبير.", "tl": "l-kanapi kbir", "en": "The sofa is big."}},
                   {"kind": "word", "variety": "darija", "ar": "طابلة", "gloss": "table", "batch": 1}]}
    p = tmp_path / "x.json"
    p.write_text(json.dumps(x, ensure_ascii=False))
    r = ingest(p, s)
    assert r["known"] == ["الكنابي"] and r["new"] == ["طابلة"]
    assert s.get("x1")["examples"][0]["en"] == "The sofa is big."   # new sentence becomes an example
    assert [e["ar"] for e in s.entries("candidate")] == ["طابلة"]
    assert len(s.sightings("x1")) == 1
    assert activate(s, batch=1) == ["dw-00001"]
    assert ingest(p, s)["new"] == []   # idempotent


def test_homographs_with_different_pos_stay_apart(tmp_path):
    from panko.store import Store
    s = Store(tmp_path / "p.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "دار", "pos": "noun"}, status="active")
    assert s.find("دار", "darija", "verb") is None
    assert s.find("الدار", "darija", "noun")["id"] == "dw-1"
    assert s.find("دار", "darija")["id"] == "dw-1"


def test_saving_a_read_entry_keeps_its_status(tmp_path):
    from panko.store import Store
    s = Store(tmp_path / "p.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "زربية"})
    e = s.get("dw-1")            # read while a candidate
    s.set_status("dw-1", "active")
    s.put(e)                     # save the stale copy
    assert s.get("dw-1")["status"] == "active"
