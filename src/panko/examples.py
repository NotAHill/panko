"""Example sentences for entries that lack them (`panko examples`, API mode).

For each entry, candidates come from the learner's own sources (sightings: the sentence a word appeared in) and the
open corpora (panko.evidence.sentences); the `examples` prompt picks a natural one or writes one. Results go into
the store, so the next sync shows and voices them.
"""
from __future__ import annotations

import json
import re

from panko import evidence, llm, prompts
from panko.store.normalize import bare

CHUNK = 20


def todo(store, status: str = "active", ids: list[str] | None = None, tag: str = "", want: int = 1) -> list[dict]:
    """Entries with fewer than `want` examples. A short phrase ("somehow", "on the way") gets one too; a phrase that
    is already a whole sentence (longer than SHORT_PHRASE words, or ending like one) is its own example."""
    return [e for e in store.entries(status) if needs_example(e) and len(e.get("examples", [])) < want
            and (not ids or e["id"] in ids) and (not tag or tag in e.get("tags", []))]


SHORT_PHRASE = 4          # words: a phrase this short is shown in a sentence of its own


SENTENCE_END = re.compile(r"[.?!؟]\s*$")


def needs_example(e: dict) -> bool:
    """A word does; a short phrase does unless it is a whole sentence (it ends like one: "How was the trip?")."""
    if e["kind"] == "word":
        return True
    return (len(e["ar"].split()) <= SHORT_PHRASE and not SENTENCE_END.search(e["ar"])
            and not SENTENCE_END.search(e.get("gloss") or ""))


def candidates(e: dict, store, n: int = 5) -> list[dict]:
    have = {bare(x.get("ar", "")) for x in e.get("examples", [])}
    out = [{"ar": s["ar"], "tl": s.get("tl", ""), "en": s.get("en", ""), "source": s.get("title", "")}
           for s in store.sightings(e["id"]) if s.get("ar")]
    out += evidence.sentences(e["ar"], n)
    seen, uniq = set(have), []
    for c in out:
        if bare(c["ar"]) not in seen:
            seen.add(bare(c["ar"]))
            uniq.append(c)
    return [{"cid": f"c{i}", **c} for i, c in enumerate(uniq[:n])]


def row(e: dict, store, want: int = 1) -> dict:
    """What the `examples` prompt sees for one entry (API mode, and chat mode's panko_examples_todo)."""
    return {"id": e["id"], "kind": e["kind"], "ar": e["ar"], "tl": e.get("tl", ""), "pos": e.get("pos", ""),
            "gloss": e.get("gloss", ""), "examples": e.get("examples", []), "candidates": candidates(e, store),
            "wanted": want - len(e.get("examples", []))}


def _asks(entries, store, want):
    rows = [json.dumps(row(e, store, want), ensure_ascii=False) for e in entries]
    return [prompts.ask("examples", f"examples-{entries[i]['id']}", ["\n".join(rows[i:i + CHUNK])],
                        run={"web_search": False}) for i in range(0, len(rows), CHUNK)]


def add(store, results: list[dict], want: int = 1, apply: bool = True) -> dict:
    """Add examples [{id, examples: [{ar, tl, en, source}], note}] to their entries: never replacing one, never the
    same sentence twice, at most up to `want` each. Returns {added, entries, skipped {id: note}, results}."""
    rep = {"added": 0, "entries": 0, "skipped": {}, "results": {}}
    for r in results:
        e = store.get(r.get("id", ""))
        if not e:
            rep["skipped"][r.get("id", "")] = "no such card"
            continue
        have = {bare(x.get("ar", "")) for x in e.get("examples", [])}
        new = []
        for x in r.get("examples", []):
            if x.get("ar") and bare(x["ar"]) not in have:
                have.add(bare(x["ar"]))
                new.append({k: (x.get(k) or "").strip() for k in ("ar", "tl", "en", "source")})
        new = new[:max(0, want - len(e.get("examples", [])))]
        rep["results"][e["id"]] = new
        if not new:
            rep["skipped"][e["id"]] = r.get("note", "")
            continue
        rep["added"] += len(new)
        rep["entries"] += 1
        if apply:
            store.put({**e, "examples": [*e.get("examples", []), *new]})
    return rep


def run(entries: list[dict], store, want: int = 1, apply: bool = True, **kw) -> dict:
    """Ask for examples and (with apply) add them to the store. Returns {added, entries, skipped {id: note},
    waiting (still in a batch)}."""
    asks = _asks(entries, store, want)
    got = llm.run("examples", asks, **kw) if asks else {}
    results, waiting = [], 0
    for a in asks:
        ans = got.get(a.id)
        if ans is None or ans.error:
            waiting += 1
            continue
        results += ans.data.get("results", [])
    return {**add(store, results, want, apply), "waiting": waiting}


def estimate(entries: list[dict], store, want: int = 1, llm_provider=None) -> dict:
    p = llm_provider or llm.provider(task="examples")
    est = llm.estimate(p, _asks(entries, store, want), llm.expected_out("examples", p.model))
    return {"entries": len(entries), "model": p.model, "usd": round(est["usd"], 2), "usd_batch": round(est["usd"] / 2, 2)}
