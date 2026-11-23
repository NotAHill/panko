"""The LLM runner with a fake model: cache, budget, usage log, batches, out-of-credits; and Claude's request body."""
import json

import pytest

from panko import llm
from panko.providers.base import LLM, Answer, Ask
from panko.providers.llm import OutOfCredits, cost


class Fake(LLM):
    name, model = "fake", "claude-opus-5-5"

    def __init__(self, fail=(), broke_after=None):
        super().__init__({})
        self.calls, self.fail, self.broke_after, self.batches = [], set(fail), broke_after, {}

    def ask(self, a):
        if self.broke_after is not None and len(self.calls) >= self.broke_after:
            raise OutOfCredits("no credits")
        self.calls.append(a.id)
        if a.id in self.fail:
            return Answer(id=a.id, model=self.model, error="refused", usage={"input": 10, "output": 0})
        u = {"input": 1000, "output": 500}
        return Answer(id=a.id, model=self.model, data={"echo": a.parts[0]}, usage=u, cost=cost(self.model, u))

    def count_tokens(self, a):
        return 1000

    def batch_submit(self, asks):
        bid = f"b{len(self.batches)}"
        self.batches[bid] = asks
        return bid

    def batch_status(self, bid):
        return {"done": True, "status": "ended", "counts": {}}

    def batch_results(self, bid):
        return [Answer(id=a.id, model=self.model, data={"echo": a.parts[0]}, usage={"input": 1000, "output": 500},
                       cost=cost(self.model, {"input": 1000, "output": 500}, batch=True), batch=True)
                for a in self.batches[bid]]


@pytest.fixture(autouse=True)
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_root", lambda: tmp_path)
    return tmp_path


def asks(n):
    return [Ask(id=f"a{i}", system="task", parts=[f"item {i}"]) for i in range(n)]


def test_run_caches_and_logs(tmp_root):
    f = Fake()
    out = llm.run("t", asks(3), llm=f, quiet=True)
    assert [out[f"a{i}"].data for i in range(3)] == [{"echo": f"item {i}"} for i in range(3)]
    assert out["a0"].cost == pytest.approx((1000 * 4 + 500 * 20) / 1e6)
    again = llm.run("t", asks(4), llm=f, quiet=True)          # only the new one is asked
    assert f.calls.count("a0") == 1 and f.calls.count("a3") == 1 and len(again) == 4
    assert len((tmp_root / "data" / "llm-usage.jsonl").read_text().splitlines()) == 4
    assert llm.usage()["answers"] == 4


def test_failed_answers_are_not_cached(tmp_root):
    f = Fake(fail={"a1"})
    out = llm.run("t", asks(2), llm=f, quiet=True)
    assert out["a1"].error and not out["a0"].error
    llm.run("t", asks(2), llm=f, quiet=True)
    assert f.calls.count("a1") == 2 and f.calls.count("a0") == 1


def test_budget_stops_before_spending():
    f = Fake()
    with pytest.raises(llm.BudgetExceeded):
        llm.run("t", asks(100), llm=f, budget=0.10, expect_out=1500, quiet=True)
    assert f.calls == []


def test_out_of_credits_stops_the_run():
    f = Fake(broke_after=2)
    out = llm.run("t", asks(6), llm=f, workers=1, quiet=True)
    assert len(f.calls) == 2
    assert sum(1 for a in out.values() if a.error) == 4


def test_batch_then_collect_then_rerun_is_free(tmp_root):
    f = Fake()
    assert llm.run("t", asks(3), llm=f, batch=True, quiet=True) == {}
    rec = json.loads((tmp_root / "data" / "llm-batches.json").read_text())
    assert list(rec) == ["b0"]
    rep = llm.collect(llm=f)
    assert rep["b0"]["saved"] == 3
    out = llm.run("t", asks(3), llm=f, quiet=True)
    assert f.calls == [] and out["a2"].batch and out["a2"].cost == pytest.approx((1000 * 4 + 500 * 20) / 2e6)


def test_cache_key_follows_file_contents(tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(b"one")
    f = Fake()
    k1 = llm.key(f, Ask(id="x", system="s", parts=[{"image": img}]))
    img.write_bytes(b"two")
    assert llm.key(f, Ask(id="x", system="s", parts=[{"image": img}])) != k1


def test_claude_request_body(tmp_path):
    from panko.providers.llm.claude import Claude
    img = tmp_path / "page.png"
    img.write_bytes(b"\x89PNG")
    c = Claude({"model": "claude-opus-5-5", "effort": "medium"})
    schema = {"type": "object", "properties": {"w": {"type": "string"}}, "required": ["w"], "additionalProperties": False}
    b = c.params(Ask(id="1", system="Extract.", parts=["Page 3", {"image": img}], schema=schema, effort="high"))
    assert b["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert b["output_config"] == {"effort": "high", "format": {"type": "json_schema", "schema": schema}}
    assert [x["type"] for x in b["messages"][0]["content"]] == ["text", "image"]
    assert b["messages"][0]["content"][1]["source"]["media_type"] == "image/png"


def test_task_model_override(monkeypatch):
    from panko import config
    from panko.providers.llm.claude import Claude
    real = config.settings()
    fake = {**real, "llm": {**real.get("llm", {}), "tasks": {"extract": "claude-haiku-5-5"}}}
    monkeypatch.setattr(config, "settings", lambda: fake)
    monkeypatch.setattr("panko.providers.chain", lambda cap: [Claude({"model": "claude-opus-5-5", "effort": "medium"})])
    assert llm.provider(task="extract").model == "claude-haiku-5-5"
    assert llm.provider(task="extract").cfg["effort"] == "medium"
    assert llm.provider(task="check").model == "claude-opus-5-5"
