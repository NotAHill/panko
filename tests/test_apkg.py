"""Sharing cards as an .apkg: built in a scratch collection, no history, nothing personal unless asked."""
import pytest

pytest.importorskip("anki")

from anki.collection import Collection, ImportAnkiPackageRequest  # noqa: E402
from anki.import_export_pb2 import ImportAnkiPackageOptions  # noqa: E402

from panko.anki import apkg  # noqa: E402
from panko.media import audio  # noqa: E402
from panko.store import Store  # noqa: E402


def test_a_package_has_the_active_cards_and_their_pictures_and_nothing_personal(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    (media / "_panko_proto_berra.jpg").write_bytes(b"\xff\xd8 not really a jpeg")
    monkeypatch.setattr(apkg, "MEDIA_DIRS", [media])
    monkeypatch.setattr(audio, "speak", lambda *a, **k: None)
    s = Store(tmp_path / "t.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "برّا", "tl": "berra", "gloss": "outside",
           "pos": "adverb", "image": {"file": "_panko_proto_berra.jpg", "credit": "Wikimedia Commons, CC BY"},
           "sources": ["Lesson with my teacher"], "tags": ["topic::places", "src::teacher::lesson-1"],
           "examples": [{"ar": "سير برّا", "en": "Go outside", "source": "Lesson with my teacher"}]}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "gloss": "glass"}, status="candidate")
    out = tmp_path / "share.apkg"
    r = apkg.export(out, ["darija"], store=s)
    assert (r["notes"], r["media"], r["media_missing"]) == (1, 1, 0) and out.stat().st_size > 0

    friend = Collection(str(tmp_path / "friend.anki2"))
    friend.import_anki_package(ImportAnkiPackageRequest(package_path=str(out),
                                                        options=ImportAnkiPackageOptions(with_scheduling=False)))
    [nid] = friend.find_notes("")
    n = friend.get_note(nid)
    assert n["PankoID"] == "dw-1" and n["MyNotes"] == "" and n.guid == apkg._guid("dw-1")
    assert "Lesson with my teacher" not in " ".join(n.fields) and "Wikimedia Commons" in n["SourcesHTML"]
    assert "topic::places" in n.tags and not any(t.startswith(("src::", "panko::")) for t in n.tags)
    assert [d.name for d in friend.decks.all_names_and_ids() if d.name.startswith("Panko")] == ["Panko", "Panko::Darija"]
    assert n.note_type()["id"] == apkg._model_id(n.note_type()["name"])
    friend.close()

    r2 = apkg.export(tmp_path / "personal.apkg", None, personal=True, store=s)
    assert r2["personal"] and r2["notes"] == 1


def test_no_active_cards_is_said_plainly(tmp_path):
    with pytest.raises(ValueError, match="no active cards"):
        apkg.export(tmp_path / "x.apkg", store=Store(tmp_path / "t.db"))
