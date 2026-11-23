"""`panko sync` against a fake Anki: adds once, skips unchanged, updates in place, never writes MyNotes."""
import pytest

from panko.anki import sync
from panko.cards import note_types as T
from panko.media.audio import Silent
from panko.store import Store


class FakeAnki:
    def __init__(self):
        self.models, self.decks, self.media, self.notes, self.calls = {}, set(), {}, {}, []

    def __call__(self, name, args):
        self.calls.append(name)
        if name == "model_names":
            return {"modelNames": list(self.models)}
        if name == "create_model":
            self.models[args["model_name"]] = args
            return {}
        if name in ("update_model_templates", "update_model_styling", "tag_add", "card_change_deck"):
            assert name != "update_model_templates" or args["model_name"] in self.models
            return {}
        if name == "create_deck":
            self.decks.add(args["deck_name"])
            return {}
        if name == "store_media_file":
            self.media[args["filename"]] = True
            return {}
        if name == "get_media_files_names":
            return {"files": list(self.media)}
        if name == "delete_media_file":
            self.media.pop(args["filename"])
            return {}
        if name == "find_notes":
            pid = args["query"].split("PankoID:")[1].strip('"')
            return {"noteIds": [n for n, x in self.notes.items() if x["fields"].get("PankoID") == pid]}
        if name == "add_note":
            nid = len(self.notes) + 1
            self.notes[nid] = {"fields": dict(args["fields"]), "deck": args["deck_name"], "model": args["model_name"]}
            return {}
        if name == "update_notes":
            for n in args["notes"]:
                assert "MyNotes" not in n["fields"], "Panko must never write MyNotes"
                self.notes[n["id"]]["fields"].update(n["fields"])
            return {}
        if name == "notes_info":
            return {"notes": [{"cards": [1, 2]} for _ in args["notes"]]}
        raise AssertionError(f"unexpected Anki call {name}")


@pytest.fixture
def anki(monkeypatch):
    fake = FakeAnki()
    monkeypatch.setattr(sync, "tool", fake)
    monkeypatch.setattr(sync.mcp, "init", lambda: None)
    return fake


def test_sync_adds_skips_and_updates_in_place(anki, tmp_path):
    s = Store(tmp_path / "s.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "gloss": "glass",
           "pos": "noun", "examples": [], "tags": []}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "طابلة", "gloss": "table"}, status="candidate")
    r = sync.sync(s, Silent())
    assert (r["added"], r["updated"], r["unchanged"]) == (1, 0, 0)
    assert set(anki.models) == {T.WORD_MODEL, T.PHRASE_MODEL} and anki.decks == {"Panko Sandbox::Darija"}
    [note] = anki.notes.values()
    assert note["fields"]["PankoID"] == "dw-1" and note["fields"]["MyNotes"] == ""   # candidates stay out
    note["fields"]["MyNotes"] = "my mnemonic"
    assert sync.sync(s, Silent())["unchanged"] == 1 and anki.calls.count("add_note") == 1
    e = s.get("dw-1")
    s.put({**e, "gloss": "glass, cup"})
    assert sync.sync(s, Silent())["updated"] == 1
    assert "cup" in str(note["fields"]) and note["fields"]["MyNotes"] == "my mnemonic"


def test_dry_run_touches_nothing(anki, tmp_path):
    s = Store(tmp_path / "s.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "كاس", "gloss": "glass"}, status="active")
    p = sync.plan(s)
    assert p["add"] == ["dw-1"] and not anki.calls
