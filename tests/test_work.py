"""Chat mode: duplicate checks, evidence, the unit work queue, ingest, and the MCP server's tools."""
import json

import anyio
import pytest

from panko import dedupe, evidence, work
from panko.store import Store


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(work, "PAGES", tmp_path / "pages")
    t = tmp_path / "lesson.txt"
    t.write_text("\n".join(f"line {i}" for i in range(70)))
    s = Store(tmp_path / "t.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "ضحك", "tl": "d7ek", "pos": "verb",
           "gloss": "to laugh"}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "pos": "noun",
           "gloss": "glass, cup"}, status="active")
    s.put({"id": "dp-1", "kind": "phrase", "variety": "darija", "ar": "فالدار", "tl": "f d-dar",
           "gloss": "at home"}, status="active")
    src = work.add_source(str(t), "lesson", "Lesson 4", date="2026-11-23")
    return s, src


def new(ar, tl, gloss, pos="noun", kind="word", **kw):
    return {"kind": kind, "ar": ar, "tl": tl, "gloss": gloss, "pos": pos,
            "verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}, **kw}


def test_dedupe_helpers():
    assert dedupe.skel("de77ek") == "d77k" and dedupe.skel("chrab") == dedupe.skel("shrab")
    assert dedupe.add_shadda("ضحك", "de77ek") == "ضحّك" and dedupe.add_shadda("ضحك", "d7ek") == "ضحك"
    assert dedupe.same_word({"tl": "d7ek"}, {"tl": "d7ek"}) and not dedupe.same_word({"tl": "de77ek"}, {"tl": "d7ek"})
    assert dedupe.nar("ف الدار") == dedupe.nar("فالدار")
    assert dedupe.same_word({"tl": "chhal", "pos": "adverb"}, {"tl": "sh7al", "pos": "pronoun"})   # spelling noise
    assert not dedupe.same_word({"tl": "rje3", "pos": "verb"}, {"tl": "rejje3", "pos": "verb"})    # doubled: another word
    assert not dedupe.same_word({"tl": "dar", "pos": "verb"}, {"tl": "dar", "pos": "noun"})
    assert dedupe.pos_compatible("adjective", "adverb") and not dedupe.pos_compatible("noun", "particle")


def test_evidence_tells_known_homograph_and_near(ws):
    s, _ = ws
    known, homo, near = evidence.lookup([{"ar": "كاس", "pos": "n"}, {"ar": "ضحّك", "tl": "de77ek", "pos": "verb"},
                                         {"ar": "ف الدار", "tl": "f d-dar"}], s, refs=False)
    assert known["panko"]["id"] == "dw-2"
    assert homo["panko"] is None and homo["same_letters"][0]["id"] == "dw-1"
    assert near["panko"] is None and near["near"][0]["id"] == "dp-1"


def test_units_and_validation(ws):
    _, src = ws
    assert src["units"] == ["c001", "c002"] and work.next_work("lesson-4") == ["c001", "c002"]
    assert work.page("lesson-4", "c002")["text"].startswith("line 60")
    bad = work.submit("lesson-4", "c001", {"items": [{"kind": "word", "ar": "kas", "gloss": "glass", "colour": "x"},
                                                     {"kind": "word", "ar": "طابلة", "gloss": "table"}]})
    assert not bad["ok"] and any("colour" in e for e in bad["errors"])
    bad = work.submit("lesson-4", "c001", {"items": [{"kind": "word", "ar": "طابلة", "gloss": "table"}]})
    assert not bad["ok"] and any("tl" in e for e in bad["errors"]) and any("verdict" in e for e in bad["errors"])
    ok = work.submit("lesson-4", "c001", {"items": [new("طابلة", "tabla", "table", pos="n")]})
    assert ok["ok"] and work.state("lesson-4")["c001"] == "submitted" and work.next_work("lesson-4") == ["c002"]


def test_ingest_known_homograph_held_and_dropped(ws):
    s, _ = ws
    sentence = {"ar": "عطيني كاس د الما", "tl": "3tini kas d l-ma", "en": "Give me a glass of water."}
    work.submit("lesson-4", "c001", {"items": [
        {"kind": "word", "ar": "كاس", "gloss": "glass", "known_id": "dw-2", "examples": [{**sentence, "source": "source"}]},
        new("ضحك", "de77ek", "to make laugh", pos="verb"),
        new("ف الدار", "f d-dar", "at home", kind="phrase", pos=""),
        new("طابلة", "tabla", "table", picture={"choice": "photo", "query": "wooden table"}),
        new("طابلة", "tabla", "table", examples=[{"ar": "الطابلة كبيرة", "en": "The table is big."}]),
        new("سربى", "serba", "to serve", pos="verb", verdict={"verdict": "drop", "summary": "not Darija"}),
    ]})
    r = work.ingest_source("lesson-4", s)
    assert r["known"] == 1 and r["new"] == 2 and r["dropped"] == 1 and r["merged"] == 1
    assert s.get("dw-2")["examples"][0]["source"] == "Lesson 4" and len(s.sightings("dw-2")) == 1
    work.submit("lesson-4", "c002", {"items": [{"kind": "word", "ar": "كاس", "gloss": "glass", "known_id": "dw-2",
                                                "examples": [{**sentence, "ar": "عطيني كاس دْ الما."}]}]})
    work.ingest_source("lesson-4", s, units=["c002"])
    assert len(s.get("dw-2")["examples"]) == 1      # the same sentence with a sukun and a full stop isn't added again
    homo = s.find_all("ضحك", "darija")
    assert {e["ar"] for e in homo} == {"ضحك", "ضحّك"}
    table = next(e for e in s.entries("candidate") if e["ar"] == "طابلة")
    assert table["check"]["verdict"] == "ok" and table["examples"][0]["en"] == "The table is big."
    assert work.plans("lesson-4") == {"طابلة|table": {"choice": "photo", "query": "wooden table", "prompt": "",
                                                       "reason": ""}}
    assert [h["ar"] for h in r["held"]] == ["ف الدار"] and work.state("lesson-4")["c001"] == "held"
    # decided: it's the same phrase
    work.submit("lesson-4", "c001", {"items": [{"kind": "phrase", "ar": "ف الدار", "gloss": "at home",
                                                "known_id": "dp-1"}]})
    r = work.ingest_source("lesson-4", s)
    assert r["known"] == 1 and not r["held"] and work.state("lesson-4")["c001"] == "ingested"


def test_mcp_tools_round_trip(ws):
    pytest.importorskip("mcp")
    from mcp import Client

    from panko import mcp_server

    async def go():
        async with Client(mcp_server.server) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert {"panko_guide", "panko_page", "panko_submit", "panko_ingest", "panko_sync", "panko_photo_search",
                    "panko_pictures_todo", "panko_pictures_save", "panko_pictures_apply", "panko_audio"} <= names
            guide = (await c.call_tool("panko_guide", {})).content[0].text
            assert "panko_evidence" in guide and '"items"' in guide
            p = await c.call_tool("panko_prompt", {"name": "check"})
            assert "schema" in json.loads(p.content[0].text)
            page = await c.call_tool("panko_page", {"source": "lesson-4", "unit": "c001"})
            assert "line 0" in page.content[0].text
            r = await c.call_tool("panko_submit", {"source": "lesson-4", "unit": "c001",
                                                   "result": {"items": [{"kind": "word", "ar": "x", "gloss": "y"}]}})
            assert json.loads(r.content[0].text)["ok"] is False

    anyio.run(go)


def test_mcp_tools_print_nothing_on_stdout(capsys):
    pytest.importorskip("mcp")
    from panko import mcp_server

    @mcp_server.quiet
    def noisy():
        print("hello")
    noisy()
    out = capsys.readouterr()
    assert out.out == "" and "hello" in out.err
