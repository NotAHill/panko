"""The examples and clashes steps with a fake model."""
import json

import pytest

from panko import clashes, evidence, examples, llm
from panko.providers.base import LLM, Answer
from panko.providers.llm import cost
from panko.store import Store


class Fake(LLM):
    name, model = "fake", "claude-opus-5-5"

    def __init__(self):
        super().__init__({})
        self.seen = []

    def ask(self, a):
        rows = [json.loads(x) for x in a.parts[0].splitlines()]
        self.seen += rows
        if "decisions" in json.dumps(a.schema):
            data = {"results": [{"id": g["id"], "decisions": [
                {"entry_id": "dw-2", "action": "gloss", "gloss": "address (French loan)", "note": "", "why": ""},
                {"entry_id": "dw-3", "action": "drop", "gloss": "", "note": "", "why": "same word"},
                {"entry_id": "dw-1", "action": "keep", "gloss": "", "note": "", "why": ""}]} for g in rows]}
        else:
            data = {"results": [{"id": r["id"], "examples": [
                {"ar": r["candidates"][0]["ar"] if r["candidates"] else "هادا مثال", "tl": "x", "en": "An example.",
                 "source": "corpus", "candidate": "c0"}], "note": ""} for r in rows]}
        u = {"input": 1000, "output": 300}
        return Answer(id=a.id, model=self.model, data=data, usage=u, cost=cost(self.model, u, False))

    def count_tokens(self, a):
        return 1000


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_root", lambda: tmp_path)
    monkeypatch.setattr(evidence, "_references", lambda: [
        {"kind": "sentences", "name": "Corpus", "data": [("عطيني العنوان ديالك", "Give me your address.")]}])
    s = Store(tmp_path / "s.db")
    s.put({"id": "dw-1", "kind": "word", "variety": "darija", "ar": "عنوان", "tl": "3onwan", "gloss": "address"},
          status="active")
    s.put({"id": "dw-2", "kind": "word", "variety": "darija", "ar": "لدريسة", "tl": "ladrisa", "gloss": "address"},
          status="active")
    s.put({"id": "dw-3", "kind": "word", "variety": "darija", "ar": "لادريسة", "tl": "ladresa", "gloss": "address"},
          status="candidate")
    return s


def test_examples_prefer_a_corpus_sentence(store):
    f = Fake()
    es = examples.todo(store)
    assert {e["id"] for e in es} == {"dw-1", "dw-2"}
    r = examples.run(es, store, llm=f, quiet=True)
    assert r["added"] == 2 and store.get("dw-1")["examples"][0]["ar"] == "عطيني العنوان ديالك"
    assert examples.todo(store) == []


def test_clashes_found_decided_applied(store):
    groups = clashes.find(store, focus=["dw-3"])
    assert len(groups) == 1 and groups[0]["sense"] == "address" and len(groups[0]["entries"]) == 3
    d = clashes.decide(groups, llm=Fake(), quiet=True)
    assert d["dw-2"] == {"gloss": "address (French loan)"} and d["dw-3"]["drop"] == "same word"
    assert d["dw-3"]["same"] in ("dw-1", "dw-2")          # the card it copies, one the model kept
    r = clashes.apply(store, {**d, "dw-1": {"drop": "test: an active card is never retired"}})
    assert store.get("dw-3")["status"] == "retired" and store.get("dw-2")["gloss"] == "address (French loan)"
    assert store.get("dw-3")["merged_into"].startswith("same as ") and r["duplicates"] == 1
    assert store.get("dw-1")["status"] == "active" and store.get("dw-1")["cards"] == ["recognition"]
    assert r["for_you"][0]["id"] == "dw-1"
    assert clashes.senses("to look (at); to watch, see") == {"look", "watch", "see"}


def test_examples_add_never_replaces_or_repeats(store):
    store.put({**store.get("dw-1"), "examples": [{"ar": "فين العنوان؟", "tl": "fin l3onwan?", "en": "Where's the address?"}]})
    r = examples.add(store, [
        {"id": "dw-1", "examples": [{"ar": "فين العنوان؟"}]},                       # already there: nothing added
        {"id": "dw-2", "examples": [{"ar": "عطيني لدريسة", "tl": "3tini ladrisa", "en": "Give me the address."},
                                    {"ar": "عطيني لدريسة"}]},                       # one each, never twice
        {"id": "dw-3", "examples": [], "note": "no good sentence"},
        {"id": "nope", "examples": [{"ar": "x"}]}])
    assert r["added"] == 1 and r["entries"] == 1
    assert len(store.get("dw-1")["examples"]) == 1
    assert store.get("dw-2")["examples"] == [{"ar": "عطيني لدريسة", "tl": "3tini ladrisa", "en": "Give me the address.",
                                             "source": ""}]
    assert r["skipped"] == {"dw-1": "", "dw-3": "no good sentence", "nope": "no such card"}


def test_examples_in_chat_mode(store, monkeypatch, tmp_path):
    pytest.importorskip("mcp")
    import anyio
    from mcp import Client

    from panko import mcp_server
    monkeypatch.setattr(mcp_server, "Store", lambda: Store(tmp_path / "s.db"))   # tools run in a worker thread

    async def go():
        async with Client(mcp_server.server) as c:
            todo = json.loads((await c.call_tool("panko_examples_todo", {})).content[0].text)
            assert todo["left"] == 2 and {x["id"] for x in todo["cards"]} == {"dw-1", "dw-2"}
            one = next(x for x in todo["cards"] if x["id"] == "dw-1")
            assert one["wanted"] == 1 and one["candidates"][0]["ar"] == "عطيني العنوان ديالك"
            saved = json.loads((await c.call_tool("panko_examples_save", {"results": [
                {"id": "dw-1", "examples": [{**one["candidates"][0], "tl": "3tini l3onwan dyalek"}]}]})).content[0].text)
            assert saved == {"added": 1, "cards": 1, "skipped": {}}
            inbox = json.loads((await c.call_tool("panko_examples_todo", {"status": "candidate"})).content[0].text)
            assert inbox["left"] == 1
    anyio.run(go)
    assert store.get("dw-1")["examples"][0]["source"] == "Corpus"
    assert [e["id"] for e in examples.todo(store)] == ["dw-2"]


def test_a_phrase_that_is_a_sentence_is_its_own_example():
    phrase = {"kind": "phrase", "ar": "من فضلك", "gloss": "please"}
    assert examples.needs_example(phrase)
    assert not examples.needs_example({**phrase, "ar": "كيف كان السفر؟", "gloss": "How was the trip?"})
    assert not examples.needs_example({**phrase, "ar": "شحال هادا", "gloss": "How much is this?"})
    assert not examples.needs_example({**phrase, "ar": "واحد اثنين ثلاثة أربعة خمسة"})
