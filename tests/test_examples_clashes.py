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
    assert d == {"dw-2": {"gloss": "address (French loan)"}, "dw-3": {"drop": "same word"}}
    r = clashes.apply(store, {**d, "dw-1": {"drop": "test: an active card is never retired"}})
    assert store.get("dw-3")["status"] == "retired" and store.get("dw-2")["gloss"] == "address (French loan)"
    assert store.get("dw-1")["status"] == "active" and store.get("dw-1")["cards"] == ["recognition"]
    assert r["for_you"][0]["id"] == "dw-1"
    assert clashes.senses("to look (at); to watch, see") == {"look", "watch", "see"}
