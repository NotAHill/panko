"""Picture choice (API mode): plans, search, pick from contact sheets, decisions that `pictures.apply` reads."""
import json

import pytest

from panko import llm, work
from panko.media import choose
from panko.providers.base import LLM, Answer
from panko.providers.llm import cost

CARDS = [{"id": "dw-1", "ar": "كاس", "gloss": "glass", "kind": "word", "pos": "noun"},
         {"id": "dw-2", "ar": "فرح", "gloss": "to be happy", "kind": "word", "pos": "verb"},
         {"id": "dw-3", "ar": "في", "gloss": "in", "kind": "word", "pos": "preposition"},
         {"id": "dw-4", "ar": "زربية", "gloss": "carpet", "kind": "word", "pos": "noun"}]


class Fake(LLM):
    name, model = "fake", "claude-opus-5-5"

    def __init__(self):
        super().__init__({})
        self.calls = []

    def ask(self, a):
        task = "pick" if any(isinstance(p, dict) for p in a.parts) else "plan"
        self.calls.append(task)
        rows = [json.loads(x) for x in a.parts[-1].splitlines()]
        if task == "plan":
            data = {"results": [{"id": r["id"], "choice": "skip" if r["pos"] == "preposition" else "draw",
                                 "query": "", "prompt": f"scene for {r['gloss']}", "reason": "r"} for r in rows]}
        else:
            data = {"results": [{"id": r["id"], "index": 1 if r["id"] == "dw-1" else -1,
                                 "prompt": "" if r["id"] == "dw-1" else "", "reason": "none clear"} for r in rows]}
        u = {"input": 1000, "output": 200}
        return Answer(id=a.id, model=self.model, data=data, usage=u, cost=cost(self.model, u, False))

    def count_tokens(self, a):
        return 1000


def fake_search(queries, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    found = {k: [{"thumb": f"http://x/{k}/{i}", "provider": "commons"} for i in range(3)] for k in queries}
    (outdir / "cands.json").write_text(json.dumps(found))
    (outdir / "sheet0.jpg").write_bytes(b"jpg")
    return [outdir / "sheet0.jpg"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_root", lambda: tmp_path)
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(choose, "_root", lambda: tmp_path)
    (tmp_path / "plans.json").write_text(json.dumps({"كاس|glass": {"choice": "photo", "query": "drinking glass",
                                                                   "prompt": ""}}, ensure_ascii=False))
    return tmp_path


def test_decide_plans_searches_and_picks(env):
    f = Fake()
    r = choose.decide(CARDS, plan_files=[env / "plans.json"], llm_provider=f, quiet=True, search=fake_search,
                      outdir=env / "pics")
    d = r["decisions"]
    assert d["dw-1"] == {"photo": {"dir": str(env / "pics" / "run01"), "index": 1}}
    assert d["dw-2"] == {"prompt": "scene for to be happy"}          # no good photo: the planned drawing
    assert "skip" in d["dw-3"] and r["counts"] == {"skip": 1, "photo": 1, "prompt": 2}
    assert f.calls == ["plan", "pick"]                                 # one plan request, one sheet
    assert choose.save_decisions(d)["ok"] and choose.load_decisions() == d


def test_reuses_earlier_searches(env):
    f = Fake()
    fake_search({"dw-1": "glass", "dw-4": "carpet"}, env / "old")
    seen = []
    r = choose.decide(CARDS[:1] + CARDS[3:], plan_files=[env / "plans.json"], searched_dirs=[env / "old"],
                      llm_provider=f, quiet=True, search=lambda q, o: seen.append(q), outdir=env / "pics")
    assert not seen and r["decisions"]["dw-1"]["photo"]["dir"] == str(env / "old")


def test_validate_catches_bad_decisions(env):
    fake_search({"dw-1": "glass"}, env / "s")
    assert choose.validate({"dw-1": {"photo": {"dir": str(env / "s"), "index": 2}}}) == []
    errs = choose.validate({"dw-1": {"photo": {"dir": str(env / "s"), "index": 7}}, "dw-2": {"prompt": ""},
                            "dw-3": {"skip": "x", "prompt": "y"}})
    assert len(errs) == 3 and not choose.save_decisions({"dw-2": {"prompt": ""}})["ok"]
