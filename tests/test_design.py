"""Choices made in the hub: the config/hub.toml overlay, card design (never a full sync), picture wishes, voices."""
import re
import tomllib

import pytest

from panko import config
from panko.cards import build
from panko.cards import design as D
from panko.cards import note_types as T
from panko.media import pictures, voices

BASE = """
[learner]
language = "Moroccan Arabic"
varieties = ["darija", "fusha"]

[images]
chain = ["wikidata", "commons", "generate"]

[audio.elevenlabs]
voices_darija = ["Badr"]
voice_ids = { Badr = "abcdefgh12345678" }

[audio.elevenlabs.library]
language = "ar"
accent = "moroccan"
"""


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "panko.toml").write_text(BASE)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    config.settings.cache_clear()
    yield tmp_path
    config.settings.cache_clear()


# ---- the overlay

def test_dump_toml_round_trips():
    data = {"a": 1, "b": "two\nlines \"q\"", "c": [1, "x"], "d": {"e": True, "f": {"g": 1.5}, "h-i": {"j": "k"}},
            "voice_ids": {"Badr": "abc"}}
    assert tomllib.loads(config.dump_toml(data)) == data


def test_hub_choices_override_panko_toml_and_can_be_undone(root):
    assert config.settings()["images"]["chain"] == ["wikidata", "commons", "generate"]
    config.save_choices("images", {"chain": ["commons"]})
    config.save_choices("audio.elevenlabs", {"voices_darija": ["Ghalia"]})
    s = config.settings()
    assert s["images"]["chain"] == ["commons"]
    assert s["audio"]["elevenlabs"]["voices_darija"] == ["Ghalia"]
    assert s["audio"]["elevenlabs"]["library"]["accent"] == "moroccan"      # untouched keys stay
    assert "voices_darija" in (root / "config" / "panko.toml").read_text()  # panko.toml is never written
    config.save_choices("images", {"chain": None})
    assert config.settings()["images"]["chain"] == ["wikidata", "commons", "generate"]


# ---- card design

def test_the_default_design_is_the_built_in_one():
    assert T.word_templates({}) == T.WORD_TEMPLATES and T.phrase_templates({}) == T.PHRASE_TEMPLATES
    assert D.css(D.normalise({})) == ""


def test_normalise_keeps_the_answer_and_clamps_values():
    d = D.normalise({"word_back": ["picture", "nonsense"], "word_size": 500, "gloss_size": "x", "font": "comic",
                     "default_cards": ["typed", "production"], "align": "right"})
    assert d["word_back"][0] == "picture" and {"word", "gloss"} <= set(d["word_back"]) and "nonsense" not in d["word_back"]
    assert d["word_size"] == 96 and d["gloss_size"] == 24 and d["font"] == "system" and d["align"] == "center"
    assert d["default_cards"] == ["recognition", "production", "typed"]


def test_any_design_keeps_the_fields_and_templates_so_no_full_sync():
    d = D.normalise({"word_back": ["extra1", "gloss", "word"], "phrase_back": ["translation", "phrase", "extra2"],
                     "extras": [{"slot": "extra1", "label": "Mnemonic"}, {"slot": "extra2", "label": "Culture"}],
                     "front_audio": False, "production_picture": False, "font": "serif", "custom_css": ".x{}</style>"})
    for tmpls, ref, fields in [(T.word_templates(d), T.WORD_TEMPLATES, T.WORD_FIELDS),
                               (T.phrase_templates(d), T.PHRASE_TEMPLATES, T.PHRASE_FIELDS)]:
        assert [t["Name"] for t in tmpls] == [t["Name"] for t in ref]
        used = {re.sub(r"^[#^/]|^\w+:", "", m).strip() for t in tmpls for side in ("Front", "Back")
                for m in re.findall(r"\{\{([^}]+)\}\}", t[side])}
        assert used <= set(fields) | {"FrontSide"}, used - set(fields)
    back = T.word_templates(d)[0]["Back"]
    assert back.index("Spare1") < back.index("{{Gloss}}") < back.index("{{Word}}") and "Mnemonic" in back
    assert "{{Audio}}" not in T.word_templates(d)[0]["Front"]
    assert "Image" not in T.word_templates(d)[1]["Front"]
    assert "</style>" not in T.css(d) and "Georgia" in T.css(d)


def test_section_labels_are_plain_text():
    d = D.normalise({"extras": [{"slot": "extra1", "label": "<b>{{Word}}</b>"}, {"slot": "extra9", "label": "no"}],
                     "word_back": ["word", "gloss", "extra1"]})
    assert d["extras"] == [{"slot": "extra1", "label": "&lt;b&gt;Word&lt;/b&gt;"}]
    assert "{{Word}}</b>" not in D.back("word", d)


def test_own_sections_and_default_cards_reach_the_note(monkeypatch):
    monkeypatch.setattr(build, "settings", lambda: {"learner": {}})
    d = {"extras": [{"slot": "extra1", "label": "Mnemonic"}], "default_cards": ["recognition", "typed"]}
    e = {"id": "dw-1", "kind": "word", "variety": "darija", "ar": "كلب", "gloss": "dog",
         "extra": {"extra1": "sounds like 'kelp'", "extra2": "not in the design"}}
    f = build.to_note(e, design=d)["fields"]
    assert f["Spare1"] == "sounds like 'kelp'" and not f.get("Spare2")
    assert f["EnableTyped"] == "y" and not f.get("EnableProduction")
    assert build.to_note({**e, "cards": ["recognition", "production"]}, design=d)["fields"]["EnableProduction"] == "y"


def test_no_config_means_the_built_in_design(root):
    (root / "config" / "panko.toml").unlink()
    config.settings.cache_clear()
    assert D.load() == D.normalise({})


# ---- picture wishes

def test_picture_wishes_travel_with_the_card_and_none_means_none(monkeypatch):
    class St:
        def entries(self, status):
            return [{"id": "a", "ar": "أتاي", "kind": "word", "gloss": "tea", "picture_pref": "photo",
                     "picture_request": "a glass of mint tea"},
                    {"id": "b", "ar": "و", "kind": "word", "gloss": "and", "picture_pref": "none"},
                    {"id": "c", "ar": "كاس", "kind": "word", "gloss": "glass"}]
    rows = {r["id"]: r for r in pictures.export(St())}
    assert set(rows) == {"a", "c"}
    assert rows["a"]["request"] == "wants a real photo; a glass of mint tea" and "request" not in rows["c"]


def test_drawings_follow_the_chain(root):
    assert pictures.drawings_allowed()
    config.save_choices("images", {"chain": ["commons"]})
    assert not pictures.drawings_allowed()


# ---- voices

def test_library_search_uses_the_config_accent_unless_any(root, monkeypatch):
    seen = []
    monkeypatch.setattr(voices, "_get", lambda path, params=None: seen.append((path, params)) or
                        {"voices": [{"name": "Ghalia", "voice_id": "v1", "public_owner_id": "o1", "gender": "female",
                                     "preview_url": "https://x/s.mp3"}], "has_more": True})
    r = voices.library(gender="female")
    assert r["more"] and r["voices"][0]["sample"] == "https://x/s.mp3" and r["voices"][0]["owner"] == "o1"
    assert seen[-1] == ("/shared-voices", {"page_size": 30, "page": 0, "language": "ar", "accent": "moroccan",
                                           "gender": "female"})
    voices.library(accent="any", gender="robot")
    assert "accent" not in seen[-1][1] and "gender" not in seen[-1][1]


def test_choosing_adds_a_library_voice_once_and_saves_the_order(root, monkeypatch):
    posted = []
    account = [{"name": "panko-Ghalia", "voice_id": "already1234"}]
    monkeypatch.setattr(voices, "_get", lambda path, params=None: {"voices": account})
    monkeypatch.setattr(voices, "_post", lambda path, body: posted.append((path, body)) or {"voice_id": "added5678"})
    r = voices.choose("darija", [{"voice_id": "lib0000001", "name": "Ghalia Warm", "owner": "o1"},
                                 {"voice_id": "lib0000002", "name": "Yassin", "owner": "o2"},
                                 {"voice_id": "abcdefgh12345678", "name": "Badr"}])
    assert r["voices"] == ["Ghalia", "Yassin", "Badr"]
    assert posted == [("/voices/add/o2/lib0000002", {"new_name": "panko-Yassin"})]
    el = config.settings()["audio"]["elevenlabs"]
    assert el["voices_darija"] == ["Ghalia", "Yassin", "Badr"]
    assert el["voice_ids"] == {"Badr": "abcdefgh12345678", "Ghalia": "already1234", "Yassin": "added5678"}


def test_choosing_checks_its_input(root):
    with pytest.raises(ValueError):
        voices.choose("klingon", [{"voice_id": "abcdefgh1"}])
    with pytest.raises(ValueError):
        voices.choose("darija", [])
    with pytest.raises(ValueError):
        voices.choose("darija", [{"voice_id": "../../etc"}])


def test_each_variety_gets_its_own_voices(root, monkeypatch):
    config.save_choices("audio.elevenlabs", {"library": {"language": "ar", "accent": "moroccan",
                                                         "fusha": {"accent": "modern standard"}}})
    assert voices.filters("darija") == {"language": "ar", "accent": "moroccan"}
    assert voices.filters("fusha") == {"language": "ar", "accent": "modern standard"}
    account = [{"name": n, "voice_id": n.lower(), "labels": {"accent": a, "gender": g}} for n, a, g in
               [("Roger", "american", "male"), ("Badr", "moroccan", "male"), ("panko-Ghalia", "moroccan", "female"),
                ("Mousa", "modern standard", "male")]]
    monkeypatch.setattr(voices, "_get", lambda path, params=None: {"voices": account})
    assert [v["name"] for v in voices.yours("darija")] == ["panko-Ghalia", "Badr"]      # Panko's own first
    assert [v["name"] for v in voices.yours("darija", gender="female")] == ["panko-Ghalia"]
    assert [v["name"] for v in voices.yours("fusha")] == ["Mousa"]
    assert len(voices.yours("fusha", any_accent=True)) == 4
