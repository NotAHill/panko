"""A review page for the inbox: every candidate as it would become a card, with keep/drop toggles.

`panko inbox --html [--tag TAG] [--plans FILE ...]` writes `cache/review/inbox.html`. The learner marks items to
drop (choices stay in the browser), presses "Copy drop list", and `panko reject` retires those ids.
Picture plans (`{ "ar|gloss" or "ar": {choice, query, prompt, reason} }`, written by the pictures-plan step) are shown
when given, so the learner sees what the card's picture will be before it's fetched or drawn.
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

from panko import lang
from panko.config import ROOT


def _everywhere() -> str:
    """The first configured region is the one meaning "everywhere" (pan-regional), which needs no flag."""
    return (lang._learner().get("regions") or [""])[0]

FLAG = {"fix": "fixed", "regional": "regional", "uncommon": "uncommon", "doubtful": "doubtful", "drop": "drop"}


def _group(e: dict) -> tuple[int, str]:
    for t in e.get("tags", []):
        m = re.match(r"pc::page-(\d+)", t) or re.match(r".*::page-(\d+)", t)
        if m:
            return int(m.group(1)), f"Page {m.group(1)}"
    topic = next((t.split("::", 1)[1] for t in e.get("tags", []) if t.startswith("topic::")), "other")
    return 10_000, topic.capitalize()


def _card(e: dict, plan: dict | None) -> str:
    h = html.escape
    chk = e.get("check") or {}
    verdict = chk.get("verdict", "")
    gram = " · ".join(x for x in (e.get("pos", ""), {"m": "masc.", "f": "fem."}.get(e.get("gender", ""), ""),
                                  f"pl. {e['plural']}" if e.get("plural") else "",
                                  f"pres. {e['present']}" if e.get("present") else "") if x)
    ex = (e.get("examples") or [{}])[0]
    extra = len(e.get("examples") or []) - 1
    written = "written by Panko" in (ex.get("source") or "")
    flag = (f'<span class="flag {verdict}">{FLAG[verdict]}</span>' if verdict in FLAG else "")
    if e.get("region") and e["region"] != _everywhere() and verdict != "regional":
        flag += f'<span class="flag regional">{h(e["region"])}</span>'
    note = e.get("gloss_note") or e.get("usage") or ""
    pic = ""
    if plan:
        what = plan.get("query") if plan.get("choice") == "photo" else plan.get("prompt")
        pic = f'<div class="pic"><b>{h(plan.get("choice", ""))}</b> {h(what or plan.get("reason", ""))}</div>'
    search = " ".join([e["ar"], e.get("tl", ""), e.get("gloss", ""), verdict]).lower()
    return f"""<article class="card {'flagged' if verdict in FLAG else ''}" data-id="{e['id']}" data-v="{verdict or 'ok'}"
 data-s="{h(search)}">
  <header><span class="tgt" dir="auto">{h(e['ar'])}</span>{flag}
   <button class="toggle" type="button" aria-pressed="false" title="Drop this item">Drop</button></header>
  <div class="tl">{h(e.get('tl', ''))} <span class="alt">{h(e.get('tl_alt', ''))}</span></div>
  <div class="gloss">{h(e.get('gloss', ''))}</div>
  {f'<div class="gram">{h(gram)}</div>' if gram else ''}
  {f'<div class="note">{h(note)}</div>' if note else ''}
  {f'''<div class="ex{' written' if written else ''}"><div class="tgt" dir="auto">{h(ex.get('ar', ''))}</div>
   <div class="ex-tl">{h(ex.get('tl', ''))}</div><div>{h(ex.get('en', ''))}</div>
   <div class="src">{'written by Panko, not checked' if written else h(ex.get('source', ''))}{f' · +{extra} more' if extra > 0 else ''}</div></div>''' if ex.get('ar') else ''}
  {f'<div class="why">{h(chk.get("summary", ""))}</div>' if verdict in FLAG and chk.get("summary") else ''}
  {pic}
  <div class="id">{e['id']}</div>
</article>"""


def render(entries: list[dict], plans: dict | None = None, title: str = "Inbox review") -> str:
    plans = plans or {}
    groups = defaultdict(list)
    for e in entries:
        groups[_group(e)].append(e)
    body = []
    for (_order, name), es in sorted(groups.items()):
        cards = "\n".join(_card(e, plans.get(f"{e['ar']}|{e.get('gloss', '')}") or plans.get(e["ar"])) for e in es)
        body.append(f'<section><h2>{html.escape(name)} <span>{len(es)}</span></h2><div class="grid">{cards}</div></section>')
    n_flag = sum(1 for e in entries if (e.get("check") or {}).get("verdict") in FLAG)
    return TEMPLATE.replace("{{font}}", lang.font()[0]).replace("{{title}}", html.escape(title)).replace("{{n}}", str(len(entries))) \
        .replace("{{flagged}}", str(n_flag)).replace("{{body}}", "\n".join(body)) \
        .replace("{{key}}", json.dumps("panko-review-" + title))


def write(entries: list[dict], plans: dict | None = None, title: str = "Inbox review", out: Path | None = None) -> Path:
    out = out or ROOT / "cache" / "review" / "inbox.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(entries, plans, title))
    return out


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{{title}}</title>
<style>
:root{--bg:#f7f5f0;--card:#fff;--ink:#1f1d1a;--soft:#6b665e;--line:#e4dfd5;--accent:#0f6b5c;--warn:#a15c00;
--bad:#a1281e;--drop:#efe9e0}
@media (prefers-color-scheme:dark){:root{--bg:#161513;--card:#201f1c;--ink:#ece8e1;--soft:#a39d93;--line:#34322d;
--accent:#5cc2ad;--warn:#e0a24a;--bad:#ef7b70;--drop:#1b1a18}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif}
.top{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px;
display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
h1{font-size:17px;margin:0 8px 0 0}.top input{flex:1 1 180px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;
background:var(--card);color:var(--ink);font:inherit}.top label{color:var(--soft);font-size:14px;white-space:nowrap}
.top button,.toggle{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;
padding:6px 12px;cursor:pointer}.top .primary{background:var(--accent);border-color:var(--accent);color:#fff}
.count{color:var(--soft);font-size:14px}main{padding:8px 16px 80px;max-width:1300px;margin:0 auto}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--soft);margin:22px 0 8px}
h2 span{font-weight:400}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;
flex-direction:column;gap:4px}.card.flagged{border-color:color-mix(in srgb,var(--warn) 45%,var(--line))}
.card.dropped{background:var(--drop);opacity:.55}.card.dropped header .tgt{text-decoration:line-through}
header{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.tgt{font-family:{{font}}}header .tgt{font-size:24px;
margin-inline-end:auto}.toggle{padding:3px 10px;font-size:13px}.toggle[aria-pressed=true]{background:var(--bad);color:#fff;border-color:var(--bad)}
.flag{font-size:12px;padding:1px 7px;border-radius:99px;border:1px solid currentColor;color:var(--warn)}
.flag.doubtful,.flag.drop{color:var(--bad)}.flag.fix{color:var(--accent)}
.tl{font-weight:600}.alt{font-weight:400;color:var(--soft)}.gloss{font-size:16px}.gram,.note,.why,.pic,.src,.id{font-size:13px;color:var(--soft)}
.why{color:var(--warn)}.ex{border-left:3px solid var(--line);padding:2px 0 2px 9px;margin-top:4px;font-size:14px}
.ex.written{border-left-style:dashed}.ex .tgt{font-size:17px}
.ex-tl{color:var(--soft)}.pic b{text-transform:uppercase;font-size:11px;letter-spacing:.04em}.id{margin-top:auto;opacity:.6}
.hide{display:none!important}.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--ink);
color:var(--bg);padding:8px 14px;border-radius:8px;opacity:0;transition:opacity .2s}.toast.on{opacity:1}
</style></head><body>
<div class="top"><h1>{{title}}</h1><span class="count"><b id="n">{{n}}</b> items · {{flagged}} flagged · <b id="nd">0</b> to drop</span>
<input id="q" type="search" placeholder="Search word, romanisation, gloss…" aria-label="Search">
<label><input id="fl" type="checkbox"> flagged only</label><label><input id="dr" type="checkbox"> dropped only</label>
<button id="copy" class="primary" type="button">Copy drop list</button></div>
<main>{{body}}</main><div class="toast" id="toast">Copied</div>
<script>
const KEY={{key}};let drop=new Set();try{drop=new Set(JSON.parse(localStorage.getItem(KEY)||"[]"))}catch(e){}
const cards=[...document.querySelectorAll(".card")];
function save(){try{localStorage.setItem(KEY,JSON.stringify([...drop]))}catch(e){}document.getElementById("nd").textContent=drop.size}
function paint(c){const on=drop.has(c.dataset.id);c.classList.toggle("dropped",on);c.querySelector(".toggle").setAttribute("aria-pressed",on)}
cards.forEach(c=>{paint(c);c.querySelector(".toggle").onclick=()=>{const id=c.dataset.id;drop.has(id)?drop.delete(id):drop.add(id);paint(c);save();filter()}});
function filter(){const q=document.getElementById("q").value.toLowerCase(),fl=document.getElementById("fl").checked,dr=document.getElementById("dr").checked;let n=0;
cards.forEach(c=>{const ok=(!q||c.dataset.s.includes(q))&&(!fl||c.dataset.v!=="ok")&&(!dr||drop.has(c.dataset.id));c.classList.toggle("hide",!ok);if(ok)n++});
document.getElementById("n").textContent=n;document.querySelectorAll("section").forEach(s=>s.classList.toggle("hide",!s.querySelector(".card:not(.hide)")))}
["q","fl","dr"].forEach(id=>document.getElementById(id).addEventListener("input",filter));
document.getElementById("copy").onclick=async()=>{const t="panko reject "+[...drop].join(" ");try{await navigator.clipboard.writeText(t)}catch(e){prompt("Copy this:",t)}
const el=document.getElementById("toast");el.textContent=drop.size+" ids copied";el.classList.add("on");setTimeout(()=>el.classList.remove("on"),1500)};
save();
</script></body></html>"""
