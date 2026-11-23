"""Setup for another learner: the starter config, reference downloads, decks and the migration card map."""
import tomllib

import httpx
import pytest

from panko import config, evidence, setup


def test_env_template_matches_the_repo_example():
    from panko.config import CHECKOUT
    keys = lambda t: sorted(line.split("=")[0] for line in t.splitlines() if "=" in line and not line.startswith("#"))  # noqa: E731
    assert keys((setup.TEMPLATES / "env.example").read_text()) == keys((CHECKOUT / ".env.example").read_text())


def test_init_config_from_answers(tmp_path):
    text = setup.render({"language": "Egyptian Arabic", "varieties": ["masri", "fusha"], "deck_root": "Arabic",
                         "profile": "Sam", "wiktionary": "Egyptian Arabic"})
    c = tomllib.loads(text)
    assert c["learner"]["language"] == "Egyptian Arabic" and c["learner"]["varieties"] == ["masri", "fusha"]
    assert c["anki"]["decks"] == {"masri": "Arabic::Masri", "fusha": "Arabic::Fusha"} and c["anki"]["profile"] == "Sam"
    assert c["audio"]["elevenlabs"]["voices_masri"] == []
    [wik] = c["evidence"]["corpora"]                                     # no DODa: not a Darija learner
    assert wik["url"].endswith("/Egyptian%20Arabic/kaikki.org-dictionary-EgyptianArabic.jsonl")
    assert "hijab" not in text.lower() and "oussama" not in text.lower()
    darija = tomllib.loads(setup.render({}))
    assert [x["name"] for x in darija["evidence"]["corpora"]][0].startswith("Darija Open Dataset")
    p = tmp_path / "config" / "panko.toml"
    setup.write_config({}, path=p)
    assert (tmp_path / ".env").exists()
    with pytest.raises(FileExistsError):
        setup.write_config({}, path=p)
    setup.write_config({"language": "X"}, force=True, path=p)
    assert (tmp_path / "config" / "panko.toml.bak").exists() and 'language = "X"' in p.read_text()


def test_download_open_references(tmp_path, monkeypatch):
    refs = [{"name": "DODa", "path": str(tmp_path / "doda"), "present": False,
             "url": "https://github.com/o/r", "include": ["semantic categories/"]},
            {"name": "Wiktionary", "path": str(tmp_path / "w.jsonl"), "present": False,
             "url": "https://kaikki.org/x.jsonl", "include": []},
            {"name": "Book", "path": str(tmp_path / "b.txt"), "present": False, "url": "", "include": []}]
    monkeypatch.setattr(evidence, "references_status", lambda: refs)

    def handler(req):
        u = str(req.url)
        if "git/trees" in u:
            return httpx.Response(200, json={"tree": [
                {"type": "blob", "path": "semantic categories/food.csv"},
                {"type": "blob", "path": "semantic categories/malenames.csv"},
                {"type": "blob", "path": "ongoing/02.csv"}]})
        return httpx.Response(200, content=b"darija_ar,eng\n" if u.endswith(".csv") else b'{"word": "x"}\n')
    got = evidence.download(client=httpx.Client(transport=httpx.MockTransport(handler)), say=lambda *a: None)
    assert [r["done"] for r in got] == ["downloaded 1 files", "downloaded 0 KB", "missing: add this file yourself"]
    assert [f.name for f in (tmp_path / "doda").iterdir()] == ["food.csv"] and (tmp_path / "w.jsonl").exists()


def test_decks_come_from_config(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"anki": {"decks": {"darija": "Mine::Darija"}}})
    assert config.deck("darija") == "Mine::Darija" and config.deck("fusha") == "Panko Sandbox::Fusha"
    assert config.deck("masri") == "Panko::Masri"


def test_card_map_detected_from_templates(monkeypatch):
    pytest.importorskip("anki")
    from panko.anki import migrate

    class Note(dict):
        def note_type(self):
            return {"name": "Someone's deck", "tmpls": [{"ord": 0, "qfmt": "{{English}}<br>{{hint:Hint}}"},
                                                         {"ord": 1, "qfmt": "{{#Arabic}}{{Arabic}}{{/Arabic}}"}]}
    monkeypatch.setattr(config, "settings", lambda: {"anki": {}})
    assert migrate.card_map(Note(English="to dig", Arabic="حفر", Hint="")) == {0: "production", 1: "recognition"}
    monkeypatch.setattr(config, "settings", lambda: {"anki": {"card_map": {"Someone's deck": ["recognition", ""]}}})
    assert migrate.card_map(Note()) == {0: "recognition"}


def test_skill_file(tmp_path):
    from panko import skill
    p = skill.write(tmp_path)
    t = p.read_text()
    assert p == tmp_path / "panko" / "SKILL.md" and t.startswith("---\nname: panko\ndescription: ")
    assert "panko_photo_search" in t and "panko_clashes" in t and "{{" not in t
