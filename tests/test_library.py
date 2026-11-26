"""Panko packs: built from one Panko, imported into another through the normal ingest."""
import json
import zipfile
from pathlib import Path

import pytest

from panko import config, library, work
from panko.anki import sync
from panko.media import audio
from panko.store import Store

LEARNER = {"learner": {"language": "Moroccan Darija", "varieties": ["darija"]}}
CLIP = "_panko_proto_fake_berra.mp3"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Two Panko folders' worth of media and work dirs in tmp, a fake voice, and the publisher's store."""
    for d in ("pub-media", "audio", "work", "pics"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(config, "settings", lambda: LEARNER)
    monkeypatch.setattr(sync, "MEDIA_DIRS", [tmp_path / "pub-media", tmp_path / "audio"])
    monkeypatch.setattr(audio, "MEDIA", tmp_path / "audio")
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(library, "pictures_dir", lambda: tmp_path / "pics")
    (tmp_path / "pub-media" / "berra.jpg").write_bytes(b"\xff\xd8 a picture")
    (tmp_path / "audio" / CLIP).write_bytes(b"ID3 audio")
    (tmp_path / "audio" / CLIP.replace(".mp3", ".txt")).write_text("fake voice")
    monkeypatch.setattr(audio, "speak", lambda text, *a, **k: audio.Voiced(CLIP, "fake voice") if text == "برّا" else None)
    pub = Store(tmp_path / "pub.db")
    pub.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "برّا", "tl": "berra", "gloss": "outside",
             "pos": "adverb", "image": {"file": "berra.jpg", "credit": "Wikimedia Commons, CC BY"},
             "sources": ["Lesson with my teacher"], "tags": ["topic::places", "src::teacher::lesson-1", "panko::x"],
             "check": {"verdict": "ok", "summary": "as my teacher said", "evidence": [{"source": "Teacher sheet"}]},
             "examples": [{"ar": "سير برّا", "en": "Go outside", "source": "Lesson with my teacher"},
                          {"ar": "برّا سخون", "en": "It's hot outside", "source": "written by Panko"}]}, status="active")
    pub.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "سبيطار", "tl": "sbitar", "gloss": "hospital",
             "pos": "noun"}, status="active")
    pub.put({"id": "dw-3", "kind": "word", "variety": "darija", "ar": "زربوط", "tl": "zerbut", "gloss": "spinning top",
             "pos": "noun"}, status="active")
    pub.put({"id": "dw-4", "kind": "word", "variety": "darija", "ar": "طوموبيل", "tl": "tomobil", "gloss": "car",
             "pos": "noun", "tags": ["panko::doubtful"]}, status="active")
    pub.put({"id": "dw-5", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "gloss": "glass"},
            status="candidate")
    pub.put({"id": "dw-6", "kind": "word", "variety": "darija", "ar": "يبس", "tl": "ybes", "gloss": "to dry out",
             "pos": "verb"}, status="active")
    pub.put({"id": "dw-7", "kind": "word", "variety": "darija", "ar": "يبّس", "tl": "yebbes", "gloss": "to dry (something)",
             "pos": "verb"}, status="active")
    return tmp_path, pub


def _pack(tmp, pub):
    r = library.build(tmp / "out", "darija-test", "Darija test deck", store=pub)
    return r, zipfile.ZipFile(r["path"])


def test_a_pack_holds_active_cards_media_and_nothing_personal(env):
    tmp, pub = env
    r, z = _pack(tmp, pub)
    assert (r["cards"], r["doubtful_left_out"], r["pictures"], r["audio"]) == (5, 1, 1, 1)
    meta = json.loads(z.read("pack.json"))
    assert meta["format"] == 1 and meta["varieties"] == ["darija"] and meta["language"] == "Moroccan Darija"
    cards = [json.loads(x) for x in z.read("entries.jsonl").decode().splitlines()]
    assert [c["id"] for c in cards] == ["dw-1", "dw-2", "dw-3", "dw-6", "dw-7"]
    berra = cards[0]
    assert "sources" not in berra and berra["tags"] == ["topic::places"] and berra["check"] == {"verdict": "ok"}
    assert [x["source"] for x in berra["examples"]] == ["", "written by Panko"]
    text = z.read("entries.jsonl").decode()
    assert "teacher" not in text.lower() and "MyNotes" not in text
    assert {"media/berra.jpg", f"audio/{CLIP}", f"audio/{CLIP.replace('.mp3', '.txt')}"} <= set(z.namelist())
    assert json.loads(z.read("credits.json"))["pictures"] == {"berra.jpg": "Wikimedia Commons, CC BY"}
    with pytest.raises(ValueError, match="slug"):
        library.build(tmp / "out", "Not A Slug", "x", store=pub)


def test_import_into_an_empty_panko_makes_inbox_cards_with_their_media(env, monkeypatch):
    tmp, pub = env
    r, _ = _pack(tmp, pub)
    (tmp / "audio" / CLIP).unlink()                 # the importer's audio cache starts empty
    (tmp / "audio" / CLIP.replace(".mp3", ".txt")).unlink()
    me = Store(tmp / "me.db")
    rep = library.import_pack(r["path"], store=me)
    assert (rep["new"], rep["known"], rep["held"]) == (5, 0, [])      # يبس and يبّس stay two cards
    new = me.entries("candidate")
    berra = next(e for e in new if e["ar"] == "برّا")
    assert berra["image"]["file"] == "berra.jpg" and (tmp / "pics" / "berra.jpg").exists()
    assert (tmp / "audio" / CLIP).exists() and (tmp / "audio" / CLIP.replace(".mp3", ".txt")).exists()
    assert berra["origin"]["pack"] == "darija-test" and berra["origin"]["id"] == "dw-1" and berra["origin"]["hash"]
    assert berra["sources"] == ["Darija test deck"] and "src::pack::pack-darija-test" in berra["tags"]
    assert berra["check"] == {"verdict": "ok"} and berra["gloss"] == "outside"
    [sig] = me.sightings(berra["id"])
    assert sig["role"] == "pack" and json.loads(sig["note"])["id"] == "dw-1"
    # the same pack again changes nothing
    again = library.import_pack(r["path"], store=me)
    assert again["new"] == 0 and len(me.entries("candidate")) == 5
    monkeypatch.setattr(work, "WORK", tmp / "work2")            # another Panko folder, with its own queue
    assert library.import_pack(r["path"], store=Store(tmp / "me2.db"), activate=True)["activated"] == 5


def test_import_keeps_your_cards_holds_near_ones_and_rejected_stays_rejected(env):
    tmp, pub = env
    r, _ = _pack(tmp, pub)
    me = Store(tmp / "me.db")
    me.put({"id": "dw-10", "kind": "word", "variety": "darija", "ar": "برّا", "tl": "berra", "gloss": "out, outside",
            "pos": "adverb", "MyNotes": "mine"}, status="active")
    me.put({"id": "dw-11", "kind": "word", "variety": "darija", "ar": "سبيطال", "tl": "sbital", "gloss": "hospital",
            "pos": "noun"}, status="active")
    me.put({"id": "dw-12", "kind": "word", "variety": "darija", "ar": "زربوط", "tl": "zerbut", "gloss": "spinning top",
            "pos": "noun"}, status="candidate")
    me.set_status("dw-12", "retired", why="rejected in the inbox")
    rep = library.import_pack(r["path"], store=me)
    # known counts the rejected word too: it gets the sighting, and stays rejected
    assert rep["new"] == 2 and rep["known"] == 2 and len(rep["held"]) == 1 and len(rep["rejected_again"]) == 1
    mine = me.get("dw-10")
    assert mine["gloss"] == "out, outside" and mine["MyNotes"] == "mine"          # your card stays yours
    assert mine["image"]["file"] == "berra.jpg"                                    # its empty picture is filled
    assert [x["ar"] for x in mine["examples"]] == ["سير برّا"]                     # real sentences only
    assert mine["examples"][0]["source"] == "Darija test deck"
    assert rep["held"][0]["ar"] == "سبيطار" and me.get("dw-12")["status"] == "retired"
    # a held card is settled like any source's
    work.decide("pack-darija-test", rep["held"][0]["unit"], "سبيطار", known_id="dw-11")
    assert work.ingest_source("pack-darija-test", me)["known"] == 1
    assert sorted(e["ar"] for e in me.entries("candidate")) == ["يبس", "يبّس"]


def test_a_pack_for_another_language_or_variety_is_refused(env, monkeypatch):
    tmp, pub = env
    r, _ = _pack(tmp, pub)
    monkeypatch.setattr(config, "settings", lambda: {"learner": {"language": "Spanish", "varieties": ["spanish"]}})
    with pytest.raises(ValueError, match="for Moroccan Darija"):
        library.import_pack(r["path"], store=Store(tmp / "x.db"))
    monkeypatch.setattr(config, "settings", lambda: {"learner": {"language": "Moroccan Darija", "varieties": ["fusha"]}})
    with pytest.raises(ValueError, match="variety you learn"):
        library.import_pack(r["path"], store=Store(tmp / "y.db"))


# ---- publish --------------------------------------------------------------------------------------------------------

@pytest.fixture
def lib(env, monkeypatch):
    """The publisher's cards with the things publishing must catch: a photo of unknown licence, a private lesson
    naming the teacher, a public textbook sentence."""
    tmp, pub = env
    settings = {**LEARNER, "library": {"public_sources": ["Peace Corps textbook"], "repo": "me/panko-decks"}}
    monkeypatch.setattr(config, "settings", lambda: settings)
    pub.db.execute("INSERT INTO sources (id, kind, title) VALUES ('lesson-1', 'lesson', 'Lesson with Samir, 2 Nov')")
    pub.db.commit()
    (tmp / "pub-media" / "sbitar.jpg").write_bytes(b"\xff\xd8 hospital")
    e = pub.get("dw-1")
    e["examples"].append({"ar": "برّا كاين الشمش", "en": "Outside there's sun", "source": "Peace Corps textbook p. 20"})
    pub.put(e, status="active")
    e = pub.get("dw-2")
    e["image"] = {"file": "sbitar.jpg", "credit": '<a href="https://x">Wikimedia Commons</a>, Someone, GODL-India'}
    pub.put(e, status="active")
    e = pub.get("dw-3")
    e["notes"] = "Samir says kids still play with it"
    e["examples"] = [{"ar": "زربوط جديد", "en": "A new top", "source": "Peace Corps textbook p. 9"}]
    pub.put(e, status="active")
    e = pub.get("dw-7")
    e["gloss"] = "to dry (Samir's word)"
    pub.put(e, status="active")
    return tmp, pub


def test_publish_leaves_out_what_isnt_safe_to_share(lib):
    tmp, pub = lib
    r = library.publish("darija-test", "Darija test deck", out=tmp / "lib", store=pub, dry_run=True)
    assert not (tmp / "lib").exists()                                  # a dry run writes nothing
    assert r["version"] == 1 and r["cards"] == 4                       # يبّس names Samir in its gloss: left out
    assert r["left_out"] == {"doubtful": 1, "pictures": 1, "cards_naming_someone": 1,
                             "examples_from_private_sources": 1}
    assert r["scrubbed"] == 1 and r["pictures"] == 1                    # زربوط keeps its card, loses its note
    assert "GODL-India" in r["report"] and "Lesson with my teacher: 1" in r["report"]

    r = library.publish("darija-test", "Darija test deck", out=tmp / "lib", store=pub, apkg=False,
                        index=tmp / "index.json")
    _, cards = library.read(r["files"][0])
    by = {c["id"]: c for c in cards}
    assert set(by) == {"dw-1", "dw-2", "dw-3", "dw-6"}
    assert [x["source"] for x in by["dw-1"]["examples"]] == ["written by Panko", "Peace Corps textbook p. 20"]
    assert "image" not in by["dw-2"] and "notes" not in by["dw-3"]
    text = zipfile.ZipFile(r["files"][0]).read("entries.jsonl").decode()
    assert "Samir" not in text and "teacher" not in text.lower()
    entry = json.loads(Path(r["entry"]).read_text())
    assert entry["picture_licences"] == {"CC BY": 1} and entry["licence"] == "CC BY-SA 4.0"
    assert entry["files"][0]["sha256"] and entry["files"][0]["kind"] == "pack"
    assert "me/panko-decks" in r["upload"][0] and "Samir" in Path(r["report"]).read_text()
    # the next one is v2, and the index keeps one entry per deck
    r2 = library.publish("darija-test", "Darija test deck", out=tmp / "lib", store=pub, apkg=False,
                         index=tmp / "index.json")
    idx = json.loads((tmp / "index.json").read_text())
    assert r2["version"] == 2 and [d["version"] for d in idx["decks"]] == [2]
    # and a published pack imports like any other
    rep = library.import_pack(r2["files"][0], store=Store(tmp / "me.db"))
    assert rep["new"] == 4


def test_publish_builds_the_apkg_from_the_pack(lib):
    pytest.importorskip("anki")
    tmp, pub = lib
    r = library.publish("darija-test", "Darija test deck", out=tmp / "lib", store=pub)
    apkg = Path(r["files"][1])
    assert apkg.suffix == ".apkg" and apkg.stat().st_size > 0
    names = zipfile.ZipFile(apkg).namelist()
    assert "collection.anki21b" in names or "collection.anki21" in names
    assert not list((tmp / "lib").glob(".*-media"))                    # the scratch folder is gone
