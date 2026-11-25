"""Deterministic checks: Standard Arabic against a (fake) morphological analyser, dialect words against references."""
import pytest

from panko import checks, evidence, work
from panko.providers.base import Morph
from panko.store import Store

READINGS = {
    "مَثَّلَ": [{"diac": "مَثَّلَ", "lex": "مَثَّل", "root": "م.ث.ل", "pos": "verb"},
                {"diac": "مُثِّلَ", "lex": "مَثَّل", "root": "م.ث.ل", "pos": "verb"}],
    "كِتَاب": [{"diac": "كِتابُ", "lex": "كِتاب", "root": "ك.ت.ب", "pos": "noun"}],
    "كُتُب": [{"diac": "كُتُبٌ", "lex": "كِتاب", "root": "ك.ت.ب", "pos": "noun"}],
    "كِتَب": [{"diac": "كُتُبٌ", "lex": "كِتاب", "root": "ك.ت.ب", "pos": "noun"}],
    "مَثَلًا": [{"diac": "مَثَلاً", "lex": "مَثَل", "root": "م.ث.ل", "pos": "noun"}],
    "الْكِتَابَ": [{"diac": "الكِتابَ", "lex": "كِتاب", "root": "ك.ت.ب", "pos": "noun"}],
    "قَرَأْتُ": [{"diac": "قَرَأْتُ", "lex": "قَرَأ", "root": "ق.ر.#", "pos": "verb"}],
    "اكل": [{"diac": "أَكَلَ", "lex": "أَكَل", "root": "أ.ك.ل", "pos": "verb"}],
}


class FakeMorph(Morph):
    name = "fake"

    def __init__(self):
        super().__init__({"dbs": {"fusha": "fake-msa"}})
        self.asked = []

    def analyse(self, words, variety):
        self.asked.append(sorted(words))
        return {w: READINGS.get(w, []) for w in words}


def fw(eid, ar, **kw):
    return {"id": eid, "kind": "word", "variety": "fusha", "ar": ar, "gloss": "x", **kw}


def test_harakat_rules():
    assert checks.consistent("كِتَاب", "كِتابُ")            # a fatha before alif and a missing case ending are fine
    assert checks.consistent("كتاب", "كِتابُ")              # no harakat at all: fine
    assert checks.consistent("مَثَلًا", "مَثَلاً")            # tanween before or after the alif
    assert checks.consistent("الْكِتَابَ", "الكِتابَ")        # sukun is ignored
    assert not checks.consistent("كَتَاب", "كِتابُ")         # a wrong vowel
    assert not checks.same_letters("اكل", "أَكَلَ")
    assert checks.same_root("ق ر أ", "ق.ر.#") and checks.same_root("م ث ل", "م.ث.ل")
    assert not checks.same_root("م ث ر", "م.ث.ل")


def test_conventions_seen_in_real_camel_output():
    assert checks.consistent("شَيْءٌ", "شَيْء") and checks.consistent("يَكْتُبُ", "يَكْتُب")  # ending left off
    assert checks.consistent("مَاءٌ", "ماءُ") and checks.consistent("هُدًى", "هُدَى")       # tanween ~ its vowel
    assert checks.consistent("مُسْتَشْفًى", "مُسْتَشْفَى")
    assert checks.consistent("هَٰذَا", "هٰذا") and checks.consistent("اللَّه", "اللّٰه")    # dagger alif ~ fatha
    assert checks.consistent("الرَّحْمَٰن", "الرَحْمٰنِ") and checks.consistent("وَالشَّمْسُ", "والشَمْسُ")
    assert not checks.consistent("الشُّمْس", "الشَمْس")                                    # still a wrong vowel
    assert not checks.consistent("يَكْتِبُ", "يَكْتُب") and not checks.consistent("هُدِى", "هُدَى")
    assert not checks.consistent("كَتَبُ", "كَتَبَ")              # an ending the reading has must agree


def test_imperatives_only_against_imperative_readings():
    verb = [{"diac": "مَثَلَ", "root": "م.ث.ل", "pos": "verb", "asp": "p"}]
    assert checks.check_word("مَثِّلْ", verb, field="imperative")[0]["problem"] == "unknown"   # CAMeL lacks it
    help_ = [{"diac": "ساعَدَ", "root": "س.ع.د", "pos": "verb", "asp": "p"},
             {"diac": "ساعِدْ", "root": "س.ع.د", "pos": "verb", "asp": "c"}]
    assert checks.check_word("سَاعِدْ", help_, field="imperative") == []
    assert checks.check_word("سَاعُدْ", help_, field="imperative")[0]["problem"] == "harakat"


def test_check_entries_finds_hard_and_soft_problems():
    m = FakeMorph()
    res = checks.check_entries([
        fw("ok", "مَثَّلَ", pos="verb", root="م ث ل"),
        fw("vowel", "كِتَاب", pos="noun", root="ك ت ب", plural="كِتَب، كُتُب",
           examples=[{"ar": "قَرَأْتُ الْكِتَابَ.", "en": "I read the book."},
                     {"ar": "ضَرَبَ اللَّهُ مَثَلًا", "cite": "Quran 16:75"}]),
        fw("root", "مَثَّلَ", pos="noun", root="م ث ر"),
        fw("hamza", "اكل", pos="verb"),
        fw("unknown", "زَرْزُور", pos="noun"),
        {"id": "dw-1", "kind": "word", "variety": "darija", "ar": "بزاف", "gloss": "a lot"},
    ], m)
    assert res["ok"] == []
    assert [(p["field"], p["problem"], p["suggest"]) for p in res["vowel"]] == [("plural", "harakat", "كُتُبٌ")]
    assert {p["problem"] for p in res["root"]} == {"root", "pos"}
    assert res["hamza"][0]["problem"] == "spelling" and res["hamza"][0]["suggest"] == "أَكَلَ"
    assert res["unknown"][0]["problem"] == "unknown" and not checks.hard(res["unknown"])
    assert "dw-1" not in res                                    # no database for Darija: never checked by MSA rules
    assert len(m.asked) == 1 and "اللَّهُ" not in m.asked[0]     # one call; the Quran quote isn't checked


def test_run_tags_candidates_only_and_lists_ungrounded(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    s.put(fw("fw-1", "اكل", pos="verb"), status="candidate")
    s.put(fw("fw-2", "مَثَّلَ", pos="verb", root="م ث ل"), status="candidate")
    s.put(fw("fw-3", "اكل", pos="verb"), status="active")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "زربوط", "gloss": "spinning top"},
          status="candidate")
    monkeypatch.setattr(checks, "morph_for", lambda v: FakeMorph() if v == "fusha" else None)
    monkeypatch.setattr(evidence, "_hits", lambda ar, tl="": [])
    r = checks.run(s, ("candidate", "active"), apply=True, morph=FakeMorph())
    assert [d["id"] for d in r["doubtful"]] == ["fw-1", "fw-3"] and r["fine"] == 1 and r["tagged"] == 1
    assert "panko::doubtful" in s.get("fw-1")["tags"] and "panko::doubtful" not in s.get("fw-3").get("tags", [])
    assert s.get("fw-1")["check"]["morph"][0]["problem"] == "spelling"
    assert [u["id"] for u in r["ungrounded"]] == ["dw-1"]
    r = checks.run(s, ("active",), apply=True, tag_active=True, morph=FakeMorph(), grounding=False)
    assert "panko::doubtful" in s.get("fw-3")["tags"]


def test_ingest_holds_items_with_a_hard_problem(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(checks, "morph_for", lambda v: FakeMorph() if v == "fusha" else None)
    t = tmp_path / "sheet.txt"
    t.write_text("x")
    s = Store(tmp_path / "t.db")
    work.add_source(str(t), "teacher-sheet", "Sheet")
    ok = {"kind": "word", "variety": "fusha", "ar": "مَثَّلَ", "tl": "maththala", "gloss": "to represent",
          "pos": "verb", "verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}}
    bad = {**ok, "ar": "اكل", "tl": "akala", "gloss": "to eat"}
    assert work.submit("sheet", "c001", {"items": [ok, bad]})["ok"]
    rep = work.ingest_source("sheet", s)
    assert rep["morph_doubtful"] == 1
    by = {e["ar"]: e for e in s.entries("candidate")}
    assert "panko::doubtful" in by["اكل"]["tags"] and "panko::doubtful" not in by["مَثَّلَ"].get("tags", [])


def test_evidence_shows_the_readings(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, "morph_for", lambda v: FakeMorph() if v == "fusha" else None)
    monkeypatch.setattr(evidence, "_hits", lambda ar, tl="": ["DODa: something"])
    got = evidence.lookup([{"ar": "مَثَّلَ", "variety": "fusha"}, {"ar": "بزاف", "variety": "darija"},
                           {"ar": "زَرْزُور", "variety": "fusha"}], Store(tmp_path / "t.db"))
    assert got[0]["hits"][0].startswith("fake (fake-msa) readings: مَثَّلَ verb, root م.ث.ل")
    assert got[1]["hits"] == ["DODa: something"]
    assert "no reading" in got[2]["hits"][0]


@pytest.mark.parametrize("ready", [False])
def test_camel_provider_not_ready_without_python(monkeypatch, ready):
    from panko.providers.morph.camel import Camel
    monkeypatch.delenv("PANKO_CAMEL_PYTHON", raising=False)
    c = Camel({"dbs": {"fusha": "calima-msa-r13"}, "python": "/nonexistent/python"})
    assert c.ready() is ready and Camel({}).ready() is False
