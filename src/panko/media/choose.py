"""Choosing a picture for each card: plan → photo search → pick from the contact sheets.

This is the step agents used to do by hand from a brief. Both modes write the same decisions, which
`pictures.apply` reads:
{entry id: {"photo": {"dir", "index"}} | {"prompt": drawing scene} | {"skip": reason}}

- API mode: `decide(cards)`. Picture plans come from ingest (saved per source), from extra plan files, or from the
  `pictures-plan` prompt for cards without one. Cards planned as photos (and, by default, drawings, since a photo
  is free and a drawing isn't) are searched on the free sites. The `pictures-pick` prompt then looks at each
  contact sheet and picks a candidate, or keeps a drawing prompt when none is good.
- Chat mode: the learner's Claude does the plan and the pick itself through the MCP tools (`panko_pictures_todo`,
  `panko_photo_search`, `panko_pictures_save`). Saved decisions go to `data/pictures/decisions.json`.
Earlier searches are reused: pass their folders and cards found there aren't searched again.
"""
from __future__ import annotations

import json
from pathlib import Path

from panko import llm, prompts
from panko.media import pictures

ROWS = 6          # cards per contact sheet (pictures.search)
PER_RUN = 24      # cards per search folder
PLAN_CHUNK = 25   # cards per pictures-plan request


def _root() -> Path:
    from panko.config import ROOT
    return ROOT


def decisions_path() -> Path:
    return _root() / "data" / "pictures" / "decisions.json"


def load_decisions(path: Path | None = None) -> dict:
    p = path or decisions_path()
    return json.loads(p.read_text()) if p.exists() else {}


def validate(decisions: dict) -> list[str]:
    """Problems that would stop `pictures.apply` (empty when fine)."""
    errs, cands = [], {}
    for eid, d in decisions.items():
        if not isinstance(d, dict) or len({"photo", "prompt", "skip"} & set(d)) != 1:
            errs.append(f"{eid}: give exactly one of photo {{dir, index}}, prompt or skip")
            continue
        if "photo" in d:
            ph = d["photo"]
            try:
                if ph["dir"] not in cands:
                    from panko.config import inside
                    cands[ph["dir"]] = json.loads((inside(ph["dir"]) / "cands.json").read_text())
                found = cands[ph["dir"]].get(eid, [])
                if not 0 <= int(ph["index"]) < len(found):
                    errs.append(f"{eid}: {ph['dir']} has no candidate {ph['index']} for it ({len(found)} found)")
            except (KeyError, TypeError, ValueError, OSError) as e:
                errs.append(f"{eid}: bad photo {ph!r} ({e})")
        elif not str(d.get("prompt", d.get("skip", ""))).strip():
            errs.append(f"{eid}: empty {'prompt' if 'prompt' in d else 'skip'}")
    return errs


def save_decisions(new: dict, path: Path | None = None) -> dict:
    """Validate and merge into the saved decisions. Returns {ok, saved, errors}."""
    errs = validate(new)
    if errs:
        return {"ok": False, "errors": errs[:25]}
    from panko.config import inside
    for d in new.values():          # stored whole, so it reads the same from any folder (the model sees short paths)
        if "photo" in d:
            d["photo"]["dir"] = str(inside(d["photo"]["dir"]))
    p = path or decisions_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    allof = {**load_decisions(p), **new}
    p.write_text(json.dumps(allof, ensure_ascii=False, indent=1))
    return {"ok": True, "saved": len(new), "total": len(allof)}


# plans -------------------------------------------------------------------------------------------------------------

def known_plans(files: list[Path] = ()) -> dict:
    """Saved picture plans, keyed "ar|gloss" (or "ar"): from ingest (data/work/*/pictures.json) and extra files."""
    from panko import work
    out = work.plans()
    for f in files:
        out |= json.loads(Path(f).read_text())
    return out


def plan_of(card: dict, plans: dict) -> dict | None:
    return plans.get(f"{card['ar']}|{card.get('gloss', '')}") or plans.get(card["ar"])


def _view(c: dict, fields) -> str:
    return json.dumps({"id": c["id"], **{k: c.get(k, "") for k in fields}}, ensure_ascii=False)


def plan_missing(cards: list[dict], plans: dict, **run) -> dict:
    """The `pictures-plan` prompt for cards with no saved plan. Returns {id: plan} (answers still in a batch are
    left out)."""
    todo = [c for c in cards if not plan_of(c, plans)]
    asks = [prompts.ask("pictures-plan", f"plan-{todo[i]['id']}", ["\n".join(
        _view(c, ("kind", "ar", "tl", "gloss", "note", "pos")) for c in todo[i:i + PLAN_CHUNK])], run={"web_search": False})
        for i in range(0, len(todo), PLAN_CHUNK)]
    got = llm.run("pictures-plan", asks, **run) if asks else {}
    out = {}
    for a in got.values():
        if not a.error:
            out |= {r["id"]: r for r in a.data.get("results", [])}
    return out


# search and pick ---------------------------------------------------------------------------------------------------

def searched(dirs: list[Path]) -> dict[str, Path]:
    """{card id: folder} for cards that already have candidates in one of these search folders."""
    out = {}
    for d in dirs:
        p = Path(d) / "cands.json"
        if p.exists():
            out |= {k: Path(d) for k, v in json.loads(p.read_text()).items() if v and k not in out}
    return out


def _sheets(d: Path) -> list[tuple[Path, list[str]]]:
    """(sheet image, the card ids on it in row order) for a search folder."""
    slugs = list(json.loads((d / "cands.json").read_text()))
    return [(d / f"sheet{i // ROWS}.jpg", slugs[i:i + ROWS]) for i in range(0, len(slugs), ROWS)
            if (d / f"sheet{i // ROWS}.jpg").exists()]


def decide(cards: list[dict], *, plan_files: list[Path] = (), searched_dirs: list[Path] = (), outdir: Path | None = None,
           search_drawings: bool = True, batch: bool = False, budget: float | None = None, llm_provider=None,
           quiet: bool = False, search=pictures.search) -> dict:
    """Decide a picture for each card (see the module docstring). Returns {decisions, counts, waiting}; decisions
    for cards whose model answers are still in a batch are left out (run again after `panko llm collect`)."""
    run = {"batch": batch, "budget": budget, "llm": llm_provider, "quiet": quiet}
    plans = known_plans(plan_files)
    fresh = plan_missing(cards, plans, **run)
    plan = {c["id"]: plan_of(c, plans) or fresh.get(c["id"]) for c in cards}
    rep = {"decisions": {}, "counts": {}, "waiting": [c["id"] for c in cards if not plan[c["id"]]]}
    by_id = {c["id"]: c for c in cards}
    look = []
    for c in cards:
        p = plan[c["id"]]
        if not p:
            continue
        if p.get("choice") == "skip":
            rep["decisions"][c["id"]] = {"skip": p.get("reason") or "planned without a picture"}
        elif p.get("choice") == "photo" or search_drawings:
            look.append(c["id"])
        else:
            rep["decisions"][c["id"]] = {"prompt": p.get("prompt") or f"An image that shows '{c['gloss']}'."}

    # search what isn't found yet, PER_RUN cards per folder
    where = searched(list(searched_dirs))
    outdir = outdir or _root() / "cache" / "pictures" / "decide"
    new = [i for i in look if i not in where]
    for n in range(0, len(new), PER_RUN):
        part = new[n:n + PER_RUN]
        d = outdir / f"run{len(list(outdir.glob('run*'))) + 1:02d}" if outdir.exists() else outdir / "run01"
        search({i: (plan[i].get("query") or by_id[i]["gloss"]) for i in part}, d)
        where |= {i: d for i in part}

    # pick: one request per contact sheet that shows a card of ours
    asks, rows = [], {}
    for d in sorted({where[i] for i in look if i in where}, key=str):
        for k, (sheet, slugs) in enumerate(_sheets(d)):
            mine = [s for s in slugs if s in by_id and s in look]
            if not mine:
                continue
            aid = f"pick-{d.name}-{k}-{'-'.join(mine)}"[:200]
            rows[aid] = (d, mine)
            asks.append(prompts.ask("pictures-pick", aid, [{"image": str(sheet)}, "\n".join(json.dumps(
                {"id": s, "gloss": by_id[s]["gloss"], "query": plan[s].get("query", ""), "prompt": plan[s].get("prompt", "")},
                ensure_ascii=False) for s in mine)], run={"web_search": False}))
    got = llm.run("pictures-pick", asks, **run) if asks else {}
    for aid, (d, mine) in rows.items():
        a = got.get(aid)
        if a is None or a.error:
            rep["waiting"] += mine
            continue
        cands = json.loads((d / "cands.json").read_text())
        res = {r["id"]: r for r in a.data.get("results", [])}
        for s in mine:
            r = res.get(s, {})
            i = r.get("index", -1)
            if isinstance(i, int) and 0 <= i < len(cands.get(s, [])):
                rep["decisions"][s] = {"photo": {"dir": str(d), "index": i}}
            elif r.get("prompt") or plan[s].get("prompt"):
                rep["decisions"][s] = {"prompt": r.get("prompt") or plan[s]["prompt"]}
            else:
                rep["decisions"][s] = {"skip": r.get("reason") or "no good photo and no drawing planned"}
    for i in look:   # searched, nothing found at all: a drawing
        if i not in rep["decisions"] and i not in rep["waiting"] and i not in where:
            rep["decisions"][i] = {"prompt": plan[i].get("prompt") or f"An image that shows '{by_id[i]['gloss']}'."}
    for d in rep["decisions"].values():
        k = next(iter(d))
        rep["counts"][k] = rep["counts"].get(k, 0) + 1
    return rep


def estimate(cards: list[dict], plan_files: list[Path] = (), llm_provider=None) -> dict:
    """Rough cost: plans for cards without one, and one pick per six cards (a contact sheet is ~2.5k image tokens)."""
    from panko.providers.llm import price
    p = llm_provider or llm.provider(task="pictures-pick")
    pr = price(p.model) or {"input": 0, "output": 0}
    plans = known_plans(plan_files)
    unplanned = sum(1 for c in cards if not plan_of(c, plans))
    sheets = -(-len(cards) // ROWS)
    usd = (sheets * (4000 * pr["input"] + llm.expected_out("pictures-pick", p.model) * pr["output"])
           + -(-unplanned // PLAN_CHUNK) * (3000 * pr["input"] + llm.expected_out("pictures-plan", p.model) * pr["output"])) / 1e6
    return {"cards": len(cards), "unplanned": unplanned, "sheets": sheets, "model": p.model, "usd": round(usd, 2),
            "usd_batch": round(usd / 2, 2)}
