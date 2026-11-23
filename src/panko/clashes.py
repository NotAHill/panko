"""Gloss clashes: production cards whose fronts would show the same gloss (`panko clashes`).

A production card shows the gloss and the learner says the word, so two cards glossed "to look" leave the answer
open. `find` groups entries that share a sense (one gloss segment, normalised); the `clashes` prompt (API mode) or
the learner's Claude (chat mode, `panko_clashes`) decides per card: keep, sharpen the gloss, recognition only (a
less usual synonym), or drop a duplicate. `apply` writes the decisions; a duplicate already in Anki is never retired
here (the learner decides), it becomes recognition-only instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from panko import llm, prompts

CHUNK = 15      # groups per request


def senses(gloss: str) -> set[str]:
    out = set()
    for seg in re.split(r"[;,/]", re.sub(r"\([^)]*\)", "", (gloss or "").lower())):
        seg = re.sub(r"^(to|a|an|the)\s+", "", seg.strip(" .!?'\"")).strip()
        if len(seg) > 2:
            out.add(seg)
    return out


def _production(e: dict) -> bool:
    return "production" in e.get("cards", ["recognition", "production"])


def find(store, focus: list[str] | None = None, statuses=("active", "candidate")) -> list[dict]:
    """Groups [{id, sense, entries}] of 2+ production cards (same variety, different words) sharing a sense. With
    `focus`, only groups that include one of those entry ids (e.g. the new candidates)."""
    from panko.dedupe import nar
    by = {}
    for st in statuses:
        for e in store.entries(st):
            if e["kind"] in ("word", "phrase") and _production(e):
                for s in senses(e.get("gloss", "")):
                    by.setdefault((e["variety"], s), []).append(e)
    groups, seen = [], set()
    for (_variety, s), es in sorted(by.items()):
        es = list({e["id"]: e for e in es}.values())
        if len({nar(e["ar"]) for e in es}) < 2 or (focus and not any(e["id"] in focus for e in es)):
            continue
        key = tuple(sorted(e["id"] for e in es))
        if key in seen:
            continue
        seen.add(key)
        groups.append({"id": f"g{len(groups) + 1}", "sense": s, "entries": [
            {k: e.get(k, "") for k in ("id", "ar", "tl", "pos", "gloss", "status")} for e in es]})
    return groups


def _asks(groups):
    return [prompts.ask("clashes", f"clashes-{groups[i]['id']}", ["\n".join(json.dumps(g, ensure_ascii=False)
                                                                           for g in groups[i:i + CHUNK])],
                        run={"web_search": False}) for i in range(0, len(groups), CHUNK)]


def decide(groups: list[dict], **kw) -> dict:
    """{entry id: {"gloss"} | {"cards": ["recognition"], "note"} | {"drop": why}} from the `clashes` prompt; `keep`
    decisions are left out. Groups whose answer is still in a batch are left out too."""
    got = llm.run("clashes", _asks(groups), **kw) if groups else {}
    out = {}
    for a in got.values():
        if a.error:
            continue
        for r in a.data.get("results", []):
            for d in r.get("decisions", []):
                if d["action"] == "gloss" and d.get("gloss"):
                    out[d["entry_id"]] = {"gloss": d["gloss"], **({"note": d["note"]} if d.get("note") else {})}
                elif d["action"] == "recognition":
                    out[d["entry_id"]] = {"cards": ["recognition"], "note": d.get("note", "")}
                elif d["action"] == "drop":
                    out[d["entry_id"]] = {"drop": d.get("why") or "duplicate"}
    return out


def apply(store, decisions: dict) -> dict:
    """Write decisions to the store. Dropped candidates are retired; a dropped card that is already active becomes
    recognition-only and is listed for the learner."""
    rep = {"gloss": 0, "recognition": 0, "retired": 0, "for_you": []}
    for eid, d in decisions.items():
        e = store.get(eid)
        if not e:
            continue
        if "drop" in d and e["status"] == "candidate":
            store.set_status(eid, "retired")
            rep["retired"] += 1
            continue
        if "drop" in d:
            rep["for_you"].append({"id": eid, "ar": e["ar"], "why": d["drop"]})
            d = {"cards": ["recognition"], "note": ""}
        note = d.get("note", "")
        if note:
            field = "usage" if e["kind"] == "phrase" else "gloss_note"
            if note not in e.get(field, ""):
                e[field] = (e.get(field, "") + " " + note).strip()
        if "gloss" in d:
            e["gloss"] = d["gloss"]
            rep["gloss"] += 1
        if "cards" in d:
            e["cards"] = d["cards"]
            rep["recognition"] += 1
        store.put(e)
    return rep


def estimate(groups: list[dict], llm_provider=None) -> dict:
    p = llm_provider or llm.provider(task="clashes")
    est = llm.estimate(p, _asks(groups), llm.expected_out("clashes", p.model))
    return {"groups": len(groups), "model": p.model, "usd": round(est["usd"], 2), "usd_batch": round(est["usd"] / 2, 2)}


def save(decisions: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decisions, ensure_ascii=False, indent=1))
