"""API mode: Panko's own language-model run over a source's units, for unattended or batch work.

`run(source)` takes the next units (or the ones given) through the same steps a reader does in chat mode:
1. extract: the `extract` prompt on the page image + text layer (or the transcript stretch);
2. evidence: local, free (panko.evidence). Words the learner already has become `known_id` items and skip the paid
   steps; same-letter words and near-duplicates are passed to the check as evidence;
3. check: the `check` prompt on the unit's new items with their evidence;
4. pictures: the `pictures-plan` prompt on the items not dropped.
Old deck exports take a shorter road: rows the learner already has (local evidence) become known items, and the
rest go to the `deck` prompt, which extracts and checks in one pass; then pictures as above.
Each unit's result is then submitted to panko.work exactly like a chat result, so validation, duplicate holds and
ingest are the same in both modes. Every step goes through panko.llm (estimate, budget, cache, batches): a re-run
only pays for what's missing, and with `batch=True` each step is one half-price batch (`panko llm collect`, then
run again to go on to the next step).
"""
from __future__ import annotations

import json

from panko import evidence, llm, prompts, work

STEPS = ("extract", "check", "pictures-plan")
VERDICT_KEYS = ("verdict", "region", "urban_rural", "register", "usual_word", "learner_note", "confidence", "summary",
                "evidence")


def _source_note(s: dict) -> str:
    if s["type"] == "deck":
        return f"{s['title']}, an old shared deck ({s.get('deck', '')})"
    if s["type"] == "audio":
        who = f"; {s['learner']} is the learner, so their lines may contain mistakes" if s.get("learner") else ""
        return (f"{s['title']} ({s['kind']}), a recording transcribed by speech-to-text: words can be misheard or "
                f"written in the wrong script, so trust what the context and evidence support; what the teacher "
                f"teaches, corrects or repeats matters most{who}")
    return f"{s['title']} ({s['kind']})" + ("; the page image is the truth, the text layer may interleave columns"
                                            if s["type"] == "pdf" else "")


def _parts(sid: str, unit: str) -> list:
    p = work.page(sid, unit)
    parts = [{"image": str(p["image"])}] if p["image"] else []
    if p["page"] is not None:
        parts.append(f"Printed page number: {p['page']}")
    if p["text"]:
        parts.append(("Text layer:\n" if p["image"] else "") + p["text"])
    return parts


def _evidence_lines(r: dict) -> list[str]:
    out = list(r["hits"])
    out += [f"The learner has another word with these letters: {e['id']} {e['ar']} {e['tl']} ({e['pos'] or '-'}) "
            f"'{e['gloss']}'" for e in r["same_letters"]]
    out += [f"Close to an entry the learner has: {e['id']} {e['ar']} {e['tl']} '{e['gloss']}'" for e in r["near"]]
    return out or ["no local evidence"]


def _spent() -> float:
    return llm.usage()["usd"]


def _step(task, asks, ctx) -> dict:
    if not asks:
        return {}
    left = ctx["budget"] - (_spent() - ctx["start"])
    if left <= 0:
        raise llm.BudgetExceeded(f"budget of ${ctx['budget']:.2f} used up before {task}")
    return llm.run(task, asks, budget=left, batch=ctx["batch"], llm=ctx["llm"], quiet=ctx["quiet"])


def run(sid: str, units: list[str] | None = None, n: int = 5, *, batch: bool = False, budget: float | None = None,
        llm_provider=None, quiet: bool = False, effort: str | None = None, store=None) -> dict:
    """Extract, check and plan pictures for units of `sid`, submitting each finished unit. Returns a report:
    {done, waiting (batch not back yet), failed {unit: why}, spent}."""
    s = work.source(sid)
    todo = units or work.next_work(sid, n)
    ctx = {"budget": llm.budget_default() if budget is None else budget, "start": _spent(), "batch": batch,
           "llm": llm_provider, "quiet": quiet}
    run_vars = {"web_search": False}
    rep = {"source": sid, "units": todo, "done": [], "waiting": {}, "failed": {}, "spent": 0.0}
    kw = {"effort": effort} if effort else {}

    def answered(answers, ids, step):
        ok = []
        for i in ids:
            a = answers.get(i)
            if a is None:
                rep["waiting"][i.split("#")[0]] = step
            elif a.error:
                rep["failed"][i.split("#")[0]] = f"{step}: {a.error}"
            else:
                ok.append(i)
        return ok

    if s["type"] == "deck":
        known, new, units_ok = _deck(sid, s, todo, ctx, store, answered, run_vars, kw, rep)
        done_check = set(units_ok)
    else:
        known, new, units_ok, done_check = _pages(sid, s, todo, ctx, store, answered, run_vars, kw)

    # 4. picture plans for what stays
    def stays(it):
        return it.get("verdict", {}).get("verdict") != "drop"

    pic_units = [u for u in units_ok if u in done_check and any(stays(it) for it in new[u])]
    pic_fields = ("kind", "ar", "tl", "gloss", "gloss_note", "pos", "tags")
    pp = _step("pictures-plan", [prompts.ask("pictures-plan", f"{u}#pic", ["\n".join(
        _item_view(it, pic_fields) for it in new[u] if stays(it))], run=run_vars, **kw) for u in pic_units], ctx)
    pictured = set(answered(pp, [f"{u}#pic" for u in pic_units], "pictures-plan"))

    # 5. submit finished units
    for u in units_ok:
        if u not in done_check or (u in pic_units and f"{u}#pic" not in pictured):
            continue
        plans = {r["id"]: r for r in pp[f"{u}#pic"].data.get("results", [])} if f"{u}#pic" in pictured else {}
        items = list(known[u])
        for it in new[u]:
            if stays(it):
                p = plans.get(it["_id"]) or {"choice": "skip", "reason": "no plan returned"}
                it["picture"] = {k: p.get(k, "") for k in ("choice", "query", "prompt", "reason")}
            items.append({k: v for k, v in it.items() if not k.startswith("_")})
        r = work.submit(sid, u, {"items": items})
        if r["ok"]:
            rep["done"].append(u)
        else:
            rep["failed"][u] = "submit: " + "; ".join(r["errors"][:5])
    rep["spent"] = round(_spent() - ctx["start"], 4)
    return rep


def _item_view(it, fields):
    return json.dumps({"id": it["_id"], **{k.lstrip("_"): it.get(k, "") for k in fields}}, ensure_ascii=False)


def _pages(sid, s, todo, ctx, store, answered, run_vars, kw):
    """Pages, photos and transcripts: extract, local evidence, check. Returns (known, new, units_ok, checked)."""
    # 1. extract
    ex = _step("extract", [prompts.ask("extract", u, _parts(sid, u), run={**run_vars, "source_note": _source_note(s)},
                                       **kw) for u in todo], ctx)
    units_ok = answered(ex, todo, "extract")

    # 2. evidence: split known from new
    known, new = {}, {}
    for u in units_ok:
        page = work.book_page(s, u)
        items = ex[u].data.get("items", [])
        looked = evidence.lookup([{k: it.get(k, "") for k in ("ar", "tl", "tl_alt", "pos", "gloss", "variety")}
                                  for it in items], store) if items else []
        known[u], new[u] = [], []
        for i, (it, ev) in enumerate(zip(items, looked, strict=True)):
            it = {k: v for k, v in it.items() if k in work.ITEM["properties"] and v not in (None, "")}
            it["pos"] = evidence.norm_pos(it.get("pos"))
            if page is not None:
                it["page"] = page
            if ev["panko"]:
                known[u].append({k: it[k] for k in ("kind", "ar", "tl", "pos", "gloss", "page", "examples") if k in it}
                                | {"known_id": ev["panko"]["id"]})
            else:
                new[u].append({**it, "_id": f"i{i}", "_evidence": _evidence_lines(ev)})   # near ones are held at ingest

    # 3. check the new items
    check_fields = ("kind", "ar", "tl", "tl_alt", "gloss", "gloss_note", "pos", "examples", "_evidence")
    ck = _step("check", [prompts.ask("check", f"{u}#check", ["\n".join(_item_view(it, check_fields) for it in new[u])],
                                     run={**run_vars, "source_note": _source_note(s)}, **kw)
                         for u in units_ok if new[u]], ctx)
    checked = set(answered(ck, [f"{u}#check" for u in units_ok if new[u]], "check"))
    for u in units_ok:
        if not new[u] or f"{u}#check" not in checked:
            continue
        res = {r["id"]: r for r in ck[f"{u}#check"].data.get("results", [])}
        for it in new[u]:
            r = res.get(it["_id"])
            if r is None:
                it["verdict"] = {"verdict": "doubtful", "summary": "the check returned no result for this item"}
                continue
            v = {k: r[k] for k in VERDICT_KEYS if r.get(k) not in (None, "", [])}
            v["fix"] = {f["field"]: f["value"] for f in r.get("fix") or [] if f.get("field")}
            it["verdict"] = v
    return known, new, units_ok, {u for u in units_ok if not new[u] or f"{u}#check" in checked}


def _deck(sid, s, todo, ctx, store, answered, run_vars, kw, rep):
    """Old deck rows: rows the learner has become known items; the `deck` prompt extracts and checks the rest."""
    rows, known, new, asks = {}, {}, {}, []
    for u in todo:
        rows[u] = work.page(sid, u)["rows"]
        with_ar = [r for r in rows[u] if r["ar"]]
        looked = dict(zip((str(r["nid"]) for r in with_ar), evidence.lookup(
            [{"ar": r["head"] or r["ar"], "tl": r["tl"], "gloss": r["en"]} for r in with_ar], store), strict=True)) \
            if with_ar else {}
        known[u], todo_rows = [], []
        for r in rows[u]:
            ev = looked.get(str(r["nid"]))
            if ev and ev["panko"]:
                e = ev["panko"]
                known[u].append({"kind": e.get("kind") or "word", "ar": e["ar"], "gloss": e.get("gloss") or r["en"]
                                 or "-", "known_id": e["id"]})
            else:
                todo_rows.append(work.deck_row(r) | {"evidence": _evidence_lines(ev) if ev else ["no local evidence"]})
        rows[u] = todo_rows
        if todo_rows:
            asks.append(prompts.ask("deck", u, ["\n".join(json.dumps(r, ensure_ascii=False) for r in todo_rows)],
                                    run={**run_vars, "source_note": _source_note(s)}, max_tokens=32000, **kw))
    ans = _step("deck", asks, ctx)
    ok = set(answered(ans, [a.id for a in asks], "deck"))
    units_ok = [u for u in todo if u in ok or not rows[u]]
    for u in units_ok:
        new[u] = []
        if u not in ok:
            continue
        by_id = {r["id"]: r for r in rows[u]}
        data = ans[u].data
        rep.setdefault("dropped_rows", {})[u] = data.get("dropped", [])
        for i, it in enumerate(data.get("items", [])):
            row = by_id.get(str(it.get("src_id")), {})
            c = it.get("check") or {}
            v = {k: c[k] for k in VERDICT_KEYS if c.get(k) not in (None, "", [])} or {"verdict": "doubtful",
                                                                                      "summary": "no verdict returned"}
            if v["verdict"] == "fix":   # corrections are already in the item: record the corrected values
                v["fix"] = {f: it[f] for f in ("ar", "tl", "gloss") if it.get(f)}
            item = {k: x for k, x in it.items() if k in work.ITEM["properties"] and k != "check"
                    and x not in (None, "", [])}
            item["pos"] = evidence.norm_pos(item.get("pos"))
            item["verdict"] = v
            if row:
                item["origin"] = {"deck": s["id"], "nid": int(row["id"]) if row["id"].isdigit() else row["id"],
                                  "studied": bool(row.get("studied"))}
            new[u].append({**item, "_id": f"i{i}"})
    return known, new, units_ok


def estimate(sid: str, units: list[str] | None = None, n: int = 5, llm_provider=None) -> dict:
    """What `run` would cost for these units: extract input counted on the real pages, the rest from measured
    averages (check and pictures run only on new items, so a source full of known words costs less)."""
    from panko.providers.llm import price
    s = work.source(sid)
    todo = units or work.next_work(sid, n)
    first = "deck" if s["type"] == "deck" else "extract"
    p = llm_provider or llm.provider(task=first)
    run = {"web_search": False, "source_note": _source_note(s)}
    if first == "deck":   # rows plus ~2 evidence lines each; rows the learner already has would cost nothing
        asks = [prompts.ask("deck", u, ["\n".join(json.dumps(work.deck_row(r) | {"evidence": ["x" * 120] * 2},
                                                              ensure_ascii=False) for r in work.page(sid, u)["rows"])],
                            run=run) for u in todo]
    else:
        asks = [prompts.ask("extract", u, _parts(sid, u), run=run) for u in todo]
    est = llm.estimate(p, asks, llm.expected_out(first, p.model))
    pr = price(p.model) or {"input": 0, "output": 0}
    rest = (("pictures-plan", 2100),) if first == "deck" else (("check", 3400), ("pictures-plan", 2100))
    follow = sum((tin * pr["input"] + llm.expected_out(t, p.model) * pr["output"]) / 1e6 for t, tin in rest) * len(todo)
    total = est["usd"] + follow
    return {"units": len(todo), "model": p.model, f"{first}_usd": est["usd"], "check_and_pictures_usd": round(follow, 4),
            "usd": round(total, 2), "usd_batch": round(total / 2, 2)}
