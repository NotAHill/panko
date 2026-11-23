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


def test_studied_deck_items_are_not_activated(tmp_path):
    st = Store(tmp_path / "t.db")
    x = {"source": {"id": "deck-x", "kind": "deck", "title": "Old deck"}, "items": [
        {"kind": "word", "variety": "darija", "ar": "كلب", "gloss": "dog", "pos": "noun", "batch": 1,
         "origin": {"deck": "x", "nid": 1, "studied": True}},
        {"kind": "word", "variety": "darija", "ar": "مش", "gloss": "cat", "pos": "noun", "batch": 1,
         "origin": {"deck": "x", "nid": 2, "studied": False}}]}
    (tmp_path / "x.json").write_text(json.dumps(x))
    ingest(tmp_path / "x.json", st)
    assert [st.get(i)["ar"] for i in activate(st, batch=1)] == ["مش"]


def test_doubtful_items_wait_until_cleared(tmp_path):
    st = Store(tmp_path / "t.db")
    st.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "غتاصب", "gloss": "x", "batch": 2,
            "tags": ["panko::doubtful"]}, status="candidate")
    assert activate(st, batch=2) == [] and st.get("dw-1")["status"] == "candidate"
    assert activate(st, ids=["dw-1"]) == ["dw-1"]          # named by id: the learner cleared it
    assert st.get("dw-1")["status"] == "active" and "panko::doubtful" not in st.get("dw-1")["tags"]


def test_homograph_flag_keeps_entries_apart(tmp_path):
    st = Store(tmp_path / "t.db")
    x = {"source": {"id": "s", "kind": "deck", "title": "S"}, "items": [
        {"kind": "word", "variety": "darija", "ar": "وصل", "gloss": "to arrive", "pos": "verb"},
        {"kind": "word", "variety": "darija", "ar": "وصّل", "gloss": "to drop off", "pos": "verb", "homograph": True}]}
    (tmp_path / "x.json").write_text(json.dumps(x))
    assert len(ingest(tmp_path / "x.json", st)["new"]) == 2
