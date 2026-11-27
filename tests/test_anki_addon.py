"""The Anki add-on (H3): a whole sync from a real hub into a scratch Anki collection, through the add-on's own code
(`anki_addon/core.py`), with the rules it must keep: MyNotes, review history, no full sync, notes updated in place."""
import pytest

pytest.importorskip("starlette")
pytest.importorskip("anki")

from anki.collection import Collection  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from panko import hub  # noqa: E402
from panko.anki import remote  # noqa: E402
from panko.anki import sync as S  # noqa: E402
from panko.anki_addon import core  # noqa: E402
from panko.cards import note_types as T  # noqa: E402
from panko.hub import api  # noqa: E402
from panko.hub.jobs import Jobs  # noqa: E402
from panko.store import Store  # noqa: E402

TOKEN = "test-token"
PIC = "_panko_proto_dw-1.jpg"


class Via:
    """The add-on's net.Panko, but through the test client: the hub's key as its bearer code, no cookie."""

    def __init__(self, c, code=TOKEN):
        self.c, self.h = c, {"Authorization": f"Bearer {code}"}

    def call(self, path, body):
        r = self.c.post(path, json=body, headers=self.h)
        assert r.status_code == 200, r.text
        return r.json()

    def media(self, name):
        r = self.c.get("/anki/media/" + name, headers=self.h)
        r.raise_for_status()
        return r.content


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(api, "_store", lambda: Store(db))
    media = tmp_path / "media"
    media.mkdir()
    (media / PIC).write_bytes(b"\xff\xd8 a picture")
    monkeypatch.setattr(S, "MEDIA_DIRS", [media])
    monkeypatch.setattr(remote, "_state_file", lambda: tmp_path / "anki-addon.json")
    s = Store(db)
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "برّا", "tl": "berra", "gloss": "outside",
           "pos": "adverb", "image": {"file": PIC, "credit": "Photo: A (CC BY 4.0)"},
           "examples": [{"ar": "الدراري كيلعبو برّا.", "en": "The kids are playing outside."}]}, status="active")
    s.put({"id": "dp-1", "kind": "phrase", "variety": "darija", "ar": "لاباس؟", "tl": "labas?",
           "gloss": "how are you?"}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "كاس", "gloss": "glass"}, status="candidate")
    api.JOBS = Jobs()
    c = TestClient(hub.app(TOKEN), base_url="http://127.0.0.1:8770")
    (tmp_path / "anki").mkdir()
    col = Collection(str(tmp_path / "anki" / "collection.anki2"))
    yield c, s, col
    col.close()


def notes_of(col, pid):
    return [col.get_note(n) for n in col.find_notes(f'"PankoID:{pid}"')]


def test_a_whole_sync_then_updates_in_place(env):
    c, s, col = env
    r = core.run(col, Via(c))
    assert (r["added"], r["updated"], r["failed"]) == (2, 0, [])
    names = remote.model_names()
    assert col.models.by_name(names["word"]) and col.models.by_name(names["phrase"])
    assert col.models.by_name(T.WORD_MODEL) is None          # its own note types, not the shared ones
    (w,) = notes_of(col, "dw-1")
    assert w.note_type()["name"] == names["word"] and w["Gloss"] == "outside" and PIC in w["Image"]
    assert col.media.have(PIC) and r["media"] >= 1             # and any audio already made for it
    assert not notes_of(col, "dw-2")                          # candidates stay out
    assert s.link("dw-1")["note_id"] == w.id and s.link("dp-1")

    # what's yours stays yours: MyNotes, the deck you moved it to, a tag you added, review history, the schema
    w["MyNotes"] = "my own note"
    w.add_tag("mine")
    col.update_note(w)
    card = w.cards()[0]
    col.set_deck([card.id], col.decks.id("My deck"))
    card = col.get_card(card.id)                                 # a card you've studied
    card.type, card.queue, card.ivl, card.due = 2, 2, 12, col.sched.today + 12
    col.update_card(card)
    col.db.execute("insert into revlog values (?,?,?,?,?,?,?,?,?)", 1_700_000_000_000, card.id, -1, 3, 12, 4, 2500,
                   8000, 1)
    revs, scm = col.db.scalar("select count() from revlog"), col.db.scalar("select scm from col")
    e = s.get("dw-1")
    s.put({**e, "gloss": "outside, out"}, status="active")
    r = core.run(col, Via(c))
    assert (r["added"], r["updated"]) == (0, 1)
    (w,) = notes_of(col, "dw-1")
    assert w["Gloss"] == "outside, out" and w["MyNotes"] == "my own note" and w.has_tag("mine")
    after = col.get_card(card.id)
    assert after.did == col.decks.id("My deck") and (after.ivl, after.due, after.queue) == (12, card.due, 2)
    assert col.db.scalar("select count() from revlog") == revs and col.db.scalar("select scm from col") == scm

    # nothing changed: nothing sent, nothing written
    r = core.run(col, Via(c))
    assert (r["added"], r["updated"]) == (0, 0)


def test_card_design_changes_reach_anki_without_a_full_sync(env, monkeypatch):
    c, s, col = env
    core.run(col, Via(c))
    scm = col.db.scalar("select scm from col")
    monkeypatch.setattr(T, "css", lambda design=None: ".card { color: teal; }")
    core.run(col, Via(c))
    assert col.models.by_name(remote.model_names()["word"])["css"] == ".card { color: teal; }"
    assert col.db.scalar("select scm from col") == scm


def test_a_note_type_with_other_fields_is_refused_not_changed(env):
    c, s, col = env
    mm = col.models
    m = mm.new(remote.model_names()["word"])
    mm.add_field(m, mm.new_field("Front"))
    t = mm.new_template("Card 1")
    t["qfmt"], t["afmt"] = "{{Front}}", "{{Front}}"
    mm.add_template(m, t)
    mm.add_dict(m)
    with pytest.raises(core.Refused, match="other fields"):
        core.run(col, Via(c))
    assert [f["name"] for f in mm.by_name(remote.model_names()["word"])["flds"]] == ["Front"]
    assert not col.find_notes("")


def test_a_note_from_a_panko_package_is_updated_not_copied(env):
    c, s, col = env
    old = {"name": T.WORD_MODEL, "fields": T.WORD_FIELDS, "css": "",
           "templates": [{"name": t["Name"], "front": t["Front"], "back": t["Back"]} for t in T.word_templates()]}
    m = core.ensure_models(col, [old])[T.WORD_MODEL]
    n = col.new_note(m)
    n["Word"], n["PankoID"], n["Gloss"] = "برّا", "dw-1", "old gloss"
    n.guid = remote.guid("dw-1")
    col.add_note(n, col.decks.id("Panko::Darija"))
    r = core.run(col, Via(c))
    assert (r["added"], r["updated"]) == (1, 1)               # the phrase is new; the word was already there
    (w,) = notes_of(col, "dw-1")
    assert w.id == n.id and w["Gloss"] == "outside"


def test_big_decks_come_in_rounds(env, monkeypatch):
    c, s, col = env
    monkeypatch.setattr(remote, "PAGE", 1)
    seen = []
    r = core.run(col, Via(c), say=seen.append)
    assert r["added"] == 2 and len(seen) == 2 and "1 to go" in seen[0]


def test_the_add_on_routes_need_the_code(env):
    c, s, col = env
    assert c.post("/anki/pull", json={"addon": 1}).status_code == 401
    assert c.post("/anki/pull", json={"addon": 1}, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.post("/anki/pull", json={"addon": 0}, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 426
    v = Via(c)
    assert c.get("/anki/media/..%2F..%2Fetc%2Fpasswd", headers=v.h).status_code == 404
    assert c.get("/anki/media/notpanko.jpg", headers=v.h).status_code == 404
    assert v.media(PIC) == b"\xff\xd8 a picture"


def test_the_add_on_file_is_a_zip_anki_can_install(env):
    import io
    import json
    import zipfile
    c, s, col = env
    c.get(f"/?t={TOKEN}", follow_redirects=False)
    r = c.get("/addon/panko-sync.ankiaddon")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert {"__init__.py", "core.py", "net.py", "ui.py", "manifest.json", "config.json"} <= names
    assert not any("__pycache__" in x or "/" in x for x in names)
    assert json.loads(z.read("manifest.json"))["package"] == "panko_sync"


def test_audio_is_made_on_the_server_price_first(env):
    c, s, col = env
    c.get(f"/?t={TOKEN}", follow_redirects=False)
    from panko import providers
    r = c.post("/api/audio/make", json={}, headers={"X-Panko": "1"})
    if not any(x.name != "native" for x in providers.chain("audio")):     # no voice key (as in CI): says so
        assert r.status_code == 400 and "ELEVENLABS_API_KEY" in r.json()["error"]
    else:
        assert set(r.json()["estimate"]) == {"clips", "characters"}
