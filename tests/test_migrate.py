"""Phase 6 migration on a throwaway Anki collection: history survives, cards map by direction."""
import pytest

pytest.importorskip("anki")

from anki.collection import Collection  # noqa: E402

from panko.anki import migrate as M  # noqa: E402
from panko.cards import note_types as T  # noqa: E402
from panko.store import Store  # noqa: E402


def _model(col, name, fields, tmpls):
    mm = col.models
    m = mm.new(name)
    for f in fields:
        mm.add_field(m, mm.new_field(f))
    for t in tmpls:
        tt = mm.new_template(t["Name"])
        tt["qfmt"], tt["afmt"] = t["Front"], t["Back"]
        mm.add_template(m, tt)
    mm.add(m)
    return mm.by_name(name)


@pytest.fixture
def col(tmp_path):
    c = Collection(str(tmp_path / "c.anki2"))
    _model(c, T.WORD_MODEL, T.WORD_FIELDS, T.WORD_TEMPLATES)
    _model(c, T.PHRASE_MODEL, T.PHRASE_FIELDS, T.PHRASE_TEMPLATES)
    _model(c, "Darija Vocab", ["Front", "Back"], [{"Name": "Card 1", "Front": "{{Front}}", "Back": "{{Back}}"},
                                                   {"Name": "Card 2", "Front": "{{Back}}", "Back": "{{Front}}"}])
    _model(c, "Basic-64524", ["English", "Darija (with audio)"],
           [{"Name": "Card 1", "Front": "{{English}}", "Back": "{{Darija (with audio)}}"}])
    yield c
    c.close()


def _old(col, model, a, b):
    n = col.new_note(col.models.by_name(model))
    n.fields[0], n.fields[1] = a, b
    col.add_note(n, col.decks.id("Darija"))
    return n


def _entry(store, eid, nid, ar, gloss, kind="word", **kw):
    store.put({"id": eid, "kind": kind, "variety": "darija", "ar": ar, "tl": "x", "gloss": gloss, "tags": [],
               "sources": [], "origin": {"notes": [{"nid": nid, "studied": True}]}, **kw}, "candidate")


def test_convert_keeps_history_and_maps_cards(col, tmp_path):
    st = Store(tmp_path / "s.db")
    vocab = _old(col, "Darija Vocab", "حفر", "to dig")
    dave = _old(col, "Basic-64524", "Thank you", "شكرا [sound:mine.mp3]")
    rec = vocab.cards()[0]
    rec.reps, rec.ivl = 7, 30
    col.update_card(rec)
    _entry(st, "dw-1", vocab.id, "حفر", "to dig")
    _entry(st, "dw-2", vocab.id, "حفّر", "to dig deep")          # shares the old note → new note later
    _entry(st, "dp-1", dave.id, "شكرا", "thank you", kind="phrase")

    rows = M.plan(st, col)
    assert [r["nid"] for r in rows] == [dave.id, vocab.id, None]
    res = M.convert(st, col, rows)
    assert res["converted"] == 2 and res["new_on_next_sync"] == 1

    v = col.get_note(vocab.id)
    assert v.note_type()["name"] == T.WORD_MODEL
    assert v["Word"] == "حفر" and v["Gloss"] == "to dig" and v["PankoID"] == "dw-1"
    assert (v["Spare3"], v["Spare4"]) == ("حفر", "to dig")            # old content kept
    kept = col.get_card(rec.id)
    assert kept.ord == 0 and kept.reps == 7 and kept.ivl == 30        # Recognition, same card, same history
    assert col.decks.name(kept.did) == "Panko Sandbox::Darija"

    d = col.get_note(dave.id)
    assert d.note_type()["name"] == T.PHRASE_MODEL
    assert {c.ord for c in d.cards()} == {0, 1}                        # English-first card → Production; Recognition added
    assert d["Spare4"] == "شكرا [sound:mine.mp3]"

    assert st.get("dw-1")["status"] == "active" and st.link("dw-1")["note_id"] == vocab.id
    assert st.get("dw-2")["status"] == "active" and st.link("dw-2") is None


def test_unreviewed_old_card_does_not_force_a_card_type(col, tmp_path):
    st = Store(tmp_path / "s.db")
    n = _old(col, "Darija Vocab", "دروك", "now")
    _entry(st, "dw-1", n.id, "دروك", "now", cards=["recognition"])
    M.convert(st, col, M.plan(st, col))
    assert [c.ord for c in col.get_note(n.id).cards()] == [0]
    assert st.get("dw-1")["cards"] == ["recognition"]


def test_second_run_skips_notes_already_converted(col, tmp_path):
    st = Store(tmp_path / "s.db")
    n = _old(col, "Darija Vocab", "كسب / ربح", "to gain")
    _entry(st, "dw-1", n.id, "كسب", "to earn")
    _entry(st, "dw-2", n.id, "ربح", "to win")
    M.convert(st, col, [r for r in M.plan(st, col) if r["eid"] == "dw-1"])   # test batch
    rows = M.plan(st, col)
    assert rows == [{"eid": "dw-2", "nid": None, "ar": "ربح", "gloss": "to win", "shared_with": n.id}]
