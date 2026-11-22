import re

from panko.cards import build as B
from panko.cards import note_types as T
from panko.sandbox import seed
from panko.store import Store


def notes():
    return [B.to_note({**e, "status": "active"}) for e in seed.entries()]


def test_seed_ids_unique_and_fields_valid():
    ids = [e["id"] for e in seed.entries()]
    assert len(ids) == len(set(ids))
    for n in notes():
        fields = T.WORD_FIELDS if n["model"] == T.WORD_MODEL else T.PHRASE_FIELDS
        assert set(n["fields"]) <= set(fields)
        assert "MyNotes" not in n["fields"]  # never written by Panko


def test_seed_media_files_exist():
    for n in notes():
        for f in re.findall(r"(_panko_proto_[\w.]+\.(?:jpg|svg|mp3))", str(n["fields"])):
            assert (seed.MEDIA / f).exists(), f


def test_every_entry_makes_recognition_and_production_only():
    for n in notes():
        on = {k for k, v in n["fields"].items() if k.startswith("Enable") and v}
        assert on == {"EnableProduction"}, (n["fields"].get("Word") or n["fields"].get("Phrase"), on)


def test_decks_by_variety_and_kind_tags():
    for e, n in zip(seed.entries(), notes(), strict=True):
        assert n["deck"] == f"Panko Sandbox::{e['variety'].title()}"
        assert f"kind::{e['kind']}" in n["tags"]


def test_seed_loads_into_store(tmp_path):
    s = Store(tmp_path / "t.db")
    assert seed.load(s) == len(seed.entries())
    assert len(s.entries("active")) == len(seed.entries())
