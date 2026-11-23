"""Running language-model work for Panko's commands (extract, check, examples, picture decisions…).

`run(task, asks)` sends each `Ask` to the first ready provider in `[llm] chain` and returns {id: Answer}:
- estimate first: input tokens counted on a sample, output tokens guessed, priced from `[llm.prices]`;
  a run whose estimate is over the budget (`[llm] budget_usd`, or `budget=`) stops before spending anything,
  and a run stops early if its actual spend passes the budget;
- cache: every successful answer is kept under cache/llm/<task>/, so a re-run (after a crash, a fix to one item,
  or `collect`) only pays for what's missing;
- usage log: each paid answer is appended to data/llm-usage.jsonl (`panko llm usage` sums it);
- batch=True submits the uncached asks as one half-price batch instead; `collect()` saves the answers into the
  cache when the batch is done, and running the same command again then returns them.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from panko.providers.base import LLM, Answer, Ask


class BudgetExceeded(RuntimeError):
    pass


def _root() -> Path:
    from panko.config import ROOT
    return ROOT


def _cache_dir(task: str) -> Path:
    return _root() / "cache" / "llm" / task


def _usage_file() -> Path:
    return _root() / "data" / "llm-usage.jsonl"


def _batches_file() -> Path:
    return _root() / "data" / "llm-batches.json"


def provider(name: str | None = None, task: str | None = None) -> LLM:
    """The first ready provider in `[llm] chain`. `[llm.tasks]` can give a task its own model
    (e.g. `extract = "claude-haiku-5-5"`): the provider that serves that model family is used with it."""
    from panko import providers
    from panko.config import settings
    ready = providers.chain("llm")
    if name:
        ready = [p for p in ready if p.name == name]
    if not ready:
        raise RuntimeError("no language model is ready: set ANTHROPIC_API_KEY (or another provider) in .env, "
                           "and check `[llm] chain` in config/panko.toml")
    model = settings().get("llm", {}).get("tasks", {}).get(task or "")
    if not model:
        return ready[0]
    p = next((x for x in ready if (x.name == "anthropic") == model.startswith("claude")), ready[0])
    return type(p)({**p.cfg, "model": model})


def budget_default() -> float:
    from panko.config import settings
    return float(settings().get("llm", {}).get("budget_usd", 5))


def key(p: LLM, a: Ask) -> str:
    """Cache key: same provider, model, prompt, input (file contents, not paths), schema and limits → same answer."""
    parts = [x if isinstance(x, str) else {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in x.items()}
             for x in a.parts]
    blob = json.dumps([p.name, p.model, a.system, parts, a.schema, a.max_tokens, a.effort], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _cached(task: str, k: str) -> Answer | None:
    f = _cache_dir(task) / f"{k}.json"
    return Answer(**json.loads(f.read_text())) if f.exists() else None


def _save(task: str, k: str, ans: Answer):
    d = _cache_dir(task)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{k}.json").write_text(json.dumps(asdict(ans), ensure_ascii=False))
    f = _usage_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "task": task, "id": ans.id, "model": ans.model,
                             "batch": ans.batch, "usage": ans.usage, "cost": round(ans.cost, 6)}) + "\n")


# Output tokens per request (thinking included) before the usage log has measured a task: from the 2026-11-23 runs.
EXPECT_OUT = {"extract": 7000, "check": 4500, "pictures-plan": 2000, "examples": 2500, "deck": 9000, "clashes": 3000,
              "pictures-pick": 1500}


def expected_out(task: str, model: str | None = None) -> int:
    """Average output tokens of this task's past answers (same model when it has 3+), else EXPECT_OUT, else 1500."""
    f = _usage_file()
    rows = []
    if f.exists():
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if r["task"] == task and r.get("usage", {}).get("output"):
                rows.append(r)
    same = [r for r in rows if r.get("model") == model]
    rows = same if len(same) >= 3 else rows
    if len(rows) >= 3:
        return int(sum(r["usage"]["output"] for r in rows) / len(rows))
    return EXPECT_OUT.get(task, 1500)


def estimate(p: LLM, asks: list[Ask], expect_out: int, sample: int = 5) -> dict:
    """Cost of sending `asks` (the uncached ones) to `p`. Input tokens are counted on up to `sample` asks and
    scaled; `expect_out` is the expected output tokens per ask (thinking included)."""
    from panko.providers.llm import price
    n = len(asks)
    if not n:
        return {"asks": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "usd_batch": 0.0, "priced": True}
    step = max(1, n // sample)
    counted = [c for c in (p.count_tokens(a) for a in asks[::step][:sample]) if c is not None]
    per_in = sum(counted) / len(counted) if counted else sum(len(str(x)) for x in asks[0].parts + [asks[0].system]) / 3
    tin, tout = int(per_in * n), expect_out * n
    pr = price(p.model)
    usd = (tin * pr["input"] + tout * pr["output"]) / 1e6 if pr else 0.0
    return {"asks": n, "input_tokens": tin, "output_tokens": tout, "usd": round(usd, 4), "usd_batch": round(usd / 2, 4),
            "priced": bool(pr), "model": p.model}


def run(task: str, asks: list[Ask], *, expect_out: int | None = None, budget: float | None = None, batch: bool = False,
        workers: int = 4, llm: LLM | None = None, quiet: bool = False) -> dict[str, Answer]:
    """Answers for every ask: cached ones for free, the rest from the model (or submitted as a batch)."""
    from panko.providers.llm import OutOfCredits
    p = llm or provider(task=task)
    budget = budget_default() if budget is None else budget
    keys = {a.id: key(p, a) for a in asks}
    if len(keys) != len(asks):
        raise ValueError("ask ids must be unique")
    out = {a.id: c for a in asks if (c := _cached(task, keys[a.id]))}
    todo = [a for a in asks if a.id not in out]
    if not todo:
        return out
    est = estimate(p, todo, expect_out or expected_out(task, p.model))
    cost_now = est["usd_batch"] if batch else est["usd"]
    say = (lambda *m: None) if quiet else (lambda *m: print(*m, file=sys.stderr, flush=True))
    say(f"{task}: {len(out)} cached, {len(todo)} to ask {p.name}/{p.model}"
        + (f", about ${cost_now:.2f}{' (batch, half price)' if batch else ''}" if est["priced"] else ", price unknown"))
    if est["priced"] and cost_now > budget:
        raise BudgetExceeded(f"{task}: estimated ${cost_now:.2f} is over the budget of ${budget:.2f}; "
                             f"raise it with --budget or [llm] budget_usd")
    if batch:
        bid = p.batch_submit(todo)
        f = _batches_file()
        rec = json.loads(f.read_text()) if f.exists() else {}
        rec[bid] = {"task": task, "provider": p.name, "model": p.model, "keys": {a.id: keys[a.id] for a in todo},
                    "submitted": time.strftime("%Y-%m-%d %H:%M"), "done": False}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rec, indent=1))
        say(f"{task}: submitted batch {bid}; `panko llm collect` saves the answers, then run this again")
        return out

    spent, stop = [0.0], []

    def one(a: Ask) -> Answer:
        if stop:
            return Answer(id=a.id, error=f"skipped: {stop[0]}")
        try:
            ans = p.ask(a)
        except OutOfCredits as e:
            stop.append(str(e))
            return Answer(id=a.id, error=str(e))
        spent[0] += ans.cost
        if spent[0] > budget and not stop:
            stop.append(f"budget of ${budget:.2f} reached")
        return ans

    with ThreadPoolExecutor(workers) as ex:
        for ans in ex.map(one, todo):
            if ans.usage:                    # a paid answer is logged even if it failed
                if ans.error:
                    _log_only(task, ans)
                else:
                    _save(task, keys[ans.id], ans)
            out[ans.id] = ans
    errs = sum(1 for a in todo if out[a.id].error)
    say(f"{task}: done, ${spent[0]:.2f} spent, {errs} failed" + (f" ({stop[0]})" if stop else ""))
    return out


def _log_only(task: str, ans: Answer):
    f = _usage_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "task": task, "id": ans.id, "model": ans.model,
                             "batch": ans.batch, "usage": ans.usage, "cost": round(ans.cost, 6), "error": ans.error}) + "\n")


def collect(llm: LLM | None = None) -> dict[str, dict]:
    """Save the answers of every finished batch into the cache; report the rest. Returns {batch id: summary}."""
    from panko import providers
    f = _batches_file()
    rec = json.loads(f.read_text()) if f.exists() else {}
    report = {}
    for bid, r in rec.items():
        if r.get("done"):
            continue
        p = llm or next((x for x in providers.chain("llm") if x.name == r["provider"]), None)
        if p is None:
            report[bid] = {"status": f"provider {r['provider']} not ready"}
            continue
        st = p.batch_status(bid)
        report[bid] = {"task": r["task"], **st}
        if not st["done"]:
            continue
        saved = failed = 0
        for ans in p.batch_results(bid):
            k = r["keys"].get(ans.id)
            if k and not ans.error:
                _save(r["task"], k, ans)
                saved += 1
            else:
                failed += 1
                if ans.usage:
                    _log_only(r["task"], ans)
        r.update(done=True, saved=saved, failed=failed)
        report[bid].update(saved=saved, failed=failed)
    if rec:
        f.write_text(json.dumps(rec, indent=1))
    return report


def usage(since: str = "") -> dict:
    """Spend from the usage log, by task and by model, optionally since a date (YYYY-MM-DD)."""
    f = _usage_file()
    tot = {"usd": 0.0, "by_task": {}, "by_model": {}, "answers": 0}
    if not f.exists():
        return tot
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if since and r["at"] < since:
            continue
        tot["usd"] += r["cost"]
        tot["answers"] += 1
        tot["by_task"][r["task"]] = tot["by_task"].get(r["task"], 0) + r["cost"]
        tot["by_model"][r["model"]] = tot["by_model"].get(r["model"], 0) + r["cost"]
    tot["usd"] = round(tot["usd"], 4)
    return tot
