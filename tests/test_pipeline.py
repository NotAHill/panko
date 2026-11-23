"""API mode over work units with a fake model: extract → evidence → check → pictures → submit, and the batch flow."""
import json

import pytest

from panko import evidence, llm, pipeline, work
from panko.providers.base import LLM, Answer
from panko.providers.llm import cost
from panko.store import Store

PAGE = [{"kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "gloss": "glass", "pos": "noun",
         "examples": [{"ar": "عطيني كاس", "tl": "3tini kas", "en": "Give me a glass.", "source": ""}]},
        {"kind": "word", "variety": "darija", "ar": "طابلة", "tl": "tabla", "gloss": "table", "pos": "noun"},
        {"kind": "word", "variety": "darija", "ar": "ضحك", "tl": "de77ek", "gloss": "to make laugh", "pos": "verb"},
        {"kind": "word", "variety": "darija", "ar": "زربية", "tl": "zerbiya", "gloss": "carpet", "pos": "noun"}]


class Fake(LLM):
    name, model = "fake", "claude-opus-5-5"

    def __init__(self):
        super().__init__({})
        self.calls, self.batches = [], {}

    def answer(self, a, batch=False):
        task = "extract" if "items" in a.schema["properties"] else \
            "check" if "verdict" in a.schema["properties"]["results"]["items"]["properties"] else "pictures"
        self.calls.append(task)
        if task == "extract":
            data = {"items": PAGE}
        else:
            rows = [json.loads(line) for line in a.parts[0].splitlines()]
            if task == "check":
                assert all(r["evidence"] for r in rows)
                data = {"results": [{"id": r["id"], "verdict": "drop" if r["ar"] == "زربية" else "ok",
                                     "fix": [], "summary": "ok", "evidence": ["corpus"]} for r in rows]}
            else:
                assert "زربية" not in a.parts[0]
                data = {"results": [{"id": r["id"], "choice": "photo", "query": r["gloss"], "prompt": "",
                                     "reason": ""} for r in rows]}
        u = {"input": 1000, "output": 500}
        return Answer(id=a.id, model=self.model, data=data, usage=u, cost=cost(self.model, u, batch), batch=batch)

    def ask(self, a):
        return self.answer(a)

    def count_tokens(self, a):
        return 1000

    def batch_submit(self, asks):
        bid = f"b{len(self.batches)}"
        self.batches[bid] = asks
        return bid

    def batch_status(self, bid):
        return {"done": True, "status": "ended", "counts": {}}

    def batch_results(self, bid):
        return [self.answer(a, batch=True) for a in self.batches[bid]]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_root", lambda: tmp_path)
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(evidence, "_references", lambda: [])
    t = tmp_path / "notes.txt"
    t.write_text("كاس glass\nطابلة table\n")
    s = Store(tmp_path / "t.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "كاس", "tl": "kas", "pos": "noun",
           "gloss": "glass"}, status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "ضحك", "tl": "d7ek", "pos": "verb",
           "gloss": "to laugh"}, status="active")
    work.add_source(str(t), "notes", "My notes")
    return s


def test_run_submits_checked_units(setup):
    s, f = setup, Fake()
    r = pipeline.run("my-notes", llm_provider=f, quiet=True, store=s, budget=1)
    assert r["done"] == ["c001"] and not r["failed"] and f.calls == ["extract", "check", "pictures"]
    items = {it["ar"]: it for it in work.result("my-notes", "c001")["items"]}
    assert items["كاس"]["known_id"] == "dw-1" and "verdict" not in items["كاس"]
    assert items["طابلة"]["picture"]["query"] == "table" and items["زربية"]["verdict"]["verdict"] == "drop"
    again = pipeline.run("my-notes", ["c001"], llm_provider=f, quiet=True, store=s)
    assert len(f.calls) == 3 and again["done"] == ["c001"]        # all from the cache
    ing = work.ingest_source("my-notes", s)
    assert ing["new"] == 2 and ing["known"] == 1 and ing["dropped"] == 1
    assert {e["ar"] for e in s.entries("candidate")} == {"طابلة", "ضحّك"}


def test_batch_mode_goes_step_by_step(setup):
    s, f = setup, Fake()
    steps = []
    for _ in range(4):
        r = pipeline.run("my-notes", ["c001"], llm_provider=f, quiet=True, store=s, batch=True)
        steps.append(r["waiting"].get("c001") or ("done" if r["done"] else "?"))
        llm.collect(llm=f)
    assert steps == ["extract", "check", "pictures-plan", "done"]


def test_budget_stops_before_spending(setup):
    with pytest.raises(llm.BudgetExceeded):
        pipeline.run("my-notes", llm_provider=Fake(), quiet=True, store=setup, budget=0.0001)


class FakeDeck(Fake):
    def answer(self, a, batch=False):
        if "dropped" not in a.schema["properties"]:
            return super().answer(a, batch)
        self.calls.append("deck")
        rows = [json.loads(line) for line in a.parts[0].splitlines()]
        assert [r["ar"] for r in rows] == ["طابلة / طابلات", "زربية"]    # كاس is known: not sent
        assert rows[0]["evidence"] and "fields" not in rows[0]
        data = {"items": [{"src_id": rows[0]["id"], "kind": "word", "variety": "darija", "ar": "طابلة", "tl": "tabla",
                           "gloss": "table", "pos": "noun", "plural": "طابلات", "region": "pan-Moroccan", "cards": [],
                           "check": {"verdict": "fix", "summary": "deck said 'desk'", "evidence": ["corpus"]}}],
                "dropped": [{"src_id": rows[1]["id"], "ar": "زربية", "why": "test"}]}
        u = {"input": 1000, "output": 500}
        return Answer(id=a.id, model=self.model, data=data, usage=u, cost=cost(self.model, u, batch), batch=batch)


def test_deck_rows_known_skipped_then_deck_prompt(setup, tmp_path):
    s, f = setup, FakeDeck()
    deck = tmp_path / "darija.json"
    deck.write_text(json.dumps({"deck": "Darija", "notes": [
        {"nid": 1, "studied": True, "fields": {"Front": "كاس", "Back": "glass"}},
        {"nid": 2, "studied": False, "fields": {"Front": "طابلة / طابلات", "Back": "desk"}},
        {"nid": 3, "studied": False, "fields": {"Front": "زربية", "Back": "rug"}}]}, ensure_ascii=False))
    src = work.add_source(str(deck), "deck", "Old deck: Darija", trust=30)
    assert src["type"] == "deck" and src["units"] == ["d001"]
    assert pipeline.estimate("old-deck-darija", llm_provider=f)["deck_usd"] > 0
    r = pipeline.run("old-deck-darija", llm_provider=f, quiet=True, store=s, budget=1)
    assert r["done"] == ["d001"] and f.calls == ["deck", "pictures"]
    items = work.result("old-deck-darija", "d001")["items"]
    assert items[0]["known_id"] == "dw-1"
    table = items[1]
    assert table["origin"] == {"deck": "old-deck-darija", "nid": 2, "studied": False}
    assert table["verdict"]["fix"]["gloss"] == "table" and table["picture"]["choice"] == "photo"
    rep = work.ingest_source("old-deck-darija", s)
    assert rep["new"] == 1 and rep["known"] == 1
    e = next(e for e in s.entries("candidate") if e["ar"] == "طابلة")
    assert e["origin"]["nid"] == 2 and e["plural"] == "طابلات"


def test_unknown_note_type_passes_the_whole_note(tmp_path):
    from panko.ingest.decks import rows
    p = tmp_path / "someone-elses-deck.json"
    p.write_text(json.dumps({"deck": "X", "notes": [{"nid": 9, "fields": {
        "Hint": "Recall the word.", "Word": "بزاف", "Meaning": "a lot"}}]}, ensure_ascii=False))
    _, [r] = rows(p)
    assert r["ar"] == "بزاف" and r["fields"]["Meaning"] == "a lot" and work.deck_row(r)["fields"]
