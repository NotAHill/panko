"""Free, local evidence for words: does the learner already have it, and what do the reference sources say?

`lookup(words)` takes `[{ar, tl, tl_alt, pos, gloss, variety}]` (only `ar` is required) and returns, per word:
- `panko`: the entry the learner already has (same letters, compatible POS and transliteration), or null;
- `same_letters`: entries with the same letters that are another word (other POS, or the consonants of the
  transliteration differ: ضحك d7ek / ضحّك de77ek), so a new item there is a homograph, not a duplicate;
- `near`: near-duplicates by spelling, transliteration and gloss (فالدار / ف الدار), to look at before adding;
- `hits`: lines from the corpora and dictionaries in `[evidence]` (config/panko.toml).

Reference files are read by shape, so another learner points config at their own:
- a folder of CSVs (one column of Arabic, one of English; a file named *sentences* is a sentence corpus);
- a JSON-lines dictionary (`word` plus `senses[].glosses`, as Wiktionary extracts are);
- a plain-text dictionary, searched for the scholarly transliteration (and the Arabic).
"""
from __future__ import annotations

import csv
import json
import re
from functools import cache
from pathlib import Path

from panko.config import ROOT, settings
from panko.dedupe import Index, same_word
from panko.store import Store
from panko.store.normalize import strip_article

POS_ALIASES = {"n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb", "prep": "preposition",
               "pron": "pronoun", "conj": "conjunction", "interj": "interjection", "num": "number",
               "part": "particle", "phrase": ""}
ARABIC = re.compile(r"[؀-ۿ]")
MAX_HITS = 4


def norm_pos(pos: str | None) -> str:
    p = (pos or "").strip().lower().rstrip(".")
    return POS_ALIASES.get(p, p)


def variants(ar: str) -> list[str]:
    """Spellings to try: گ/ڭ for g written as ك or ق, and a final ا/ى/ي."""
    out = [ar]
    for g in "گڭ":
        if g in ar:
            out += [ar.replace(g, "ك"), ar.replace(g, "ق")]
    if ar.endswith("ا"):
        out.append(ar[:-1] + "ى")
    elif ar.endswith(("ى", "ي")):
        out.append(ar[:-1] + "ا")
    return list(dict.fromkeys(out))


def _tokens(s: str) -> set[str]:
    s = re.sub(r"[\u200e\u200f\u202a-\u202e.؟?!:;\"«»]", " ", s or "")
    return {strip_article(t) for t in re.split(r"[\s,،/()]+", s) if t}


def _path(p: str) -> Path:
    return Path(p) if Path(p).is_absolute() else ROOT / p


@cache
def _references() -> list[dict]:
    """Each configured corpus/dictionary loaded once: {name, kind: rows|sentences|jsonl|text, data}."""
    ev = settings().get("evidence", {})
    refs = []
    for c in [*ev.get("corpora", []), *ev.get("dictionaries", [])]:
        p = _path(c.get("path", ""))
        if p.is_dir():
            for f in sorted(p.glob("*.csv")):
                rows = list(csv.DictReader(open(f, encoding="utf-8")))
                if not rows:
                    continue
                cols = list(rows[0])
                ar = next((k for k in cols if any(ARABIC.search(r.get(k) or "") for r in rows[:20])), None)
                en = next((k for k in cols if k.lower() in ("eng", "en", "english", "gloss", "meaning")), None)
                if ar:
                    kind = "sentences" if "sentence" in f.stem else "rows"
                    refs.append({"name": f"{c['name']} ({f.stem})", "kind": kind,
                                 "data": [(r[ar], r.get(en, "") if en else "") for r in rows if r.get(ar)]})
        elif p.suffix == ".jsonl" and p.exists():
            d = {}
            for line in open(p, encoding="utf-8"):
                x = json.loads(line)
                gl = "; ".join(g for s in x.get("senses", []) for g in s.get("glosses", [])[:1])[:160]
                d.setdefault(x.get("word", ""), []).append(f"{x.get('pos', '')}: {gl}" if x.get("pos") else gl)
            refs.append({"name": c["name"], "kind": "jsonl", "data": d})
        elif p.exists():
            refs.append({"name": c["name"], "kind": "text", "data": p.read_text(encoding="utf-8").splitlines()})
    return refs


_INDEX: dict[int, tuple] = {}


def _index(i: int) -> tuple[dict, dict, tuple]:
    """For reference i (rows, sentences or text lines): {token: [row numbers]}, {whole entry: [row numbers]} and, for
    text, (its lines lowercased, {latin word: [line numbers]}), built once per loaded reference, so looking a
    word up doesn't re-read every row."""
    ref = _references()[i]
    hit = _INDEX.get(id(ref["data"]))
    if hit and hit[0] is ref["data"]:
        return hit[1]
    tok, whole = {}, {}
    rows = ref["data"] if ref["kind"] == "text" else [a for a, _ in ref["data"]] if ref["kind"] != "jsonl" else []
    for n, a in enumerate(rows):
        for t in _tokens(a):
            tok.setdefault(t, []).append(n)
        whole.setdefault(strip_article(a), []).append(n)
    text = ("", [])
    if ref["kind"] == "text":
        low = [line.lower() for line in rows]
        words: dict[str, list[int]] = {}
        for n, line in enumerate(low):
            for w in set(re.findall(r"\w+", line)):
                words.setdefault(w, []).append(n)
        text = (low, words)
    _INDEX[id(ref["data"])] = (ref["data"], (tok, whole, text))
    return tok, whole, text


def _hits(ar: str, tl_alt: str) -> list[str]:
    from panko.store.normalize import bare
    b = strip_article(ar)
    one_word = " " not in b
    out, rows = [], {}
    for i, ref in enumerate(_references()):
        if ref["kind"] == "rows":
            tok, whole, _ = _index(i)
            for n in sorted({*whole.get(b, []), *(tok.get(b, []) if one_word else [])}):
                a, en = ref["data"][n]
                rows.setdefault((a, en.strip().lower()), ref["name"])
        elif ref["kind"] == "sentences" and one_word:
            ss = [ref["data"][n] for n in _index(i)[0].get(b, [])]
            if ss:
                out.append(f"{ref['name']}: {len(ss)} sentences, e.g. {ss[0][0]} '{ss[0][1]}'")
        elif ref["kind"] == "jsonl":
            for w in dict.fromkeys((b, bare(ar), ar)):
                if w in ref["data"]:
                    out.append(f"{ref['name']} {w}: {' | '.join(ref['data'][w][:2])}")
                    break
        elif ref["kind"] == "text":
            k = (tl_alt or "").lower().replace("ʿ", "ɛ").replace("ḥ", "ħ")
            pat = re.compile(rf"(?<![\wɛħ]){re.escape(k)}(?![\wɛħ])") if len(k) >= 3 else None
            tok, _, (low, words) = _index(i)
            found = set(tok.get(b, [])) if one_word and len(b) >= 3 else set()
            if pat:
                first = re.match(r"\w+", k)
                lines = words.get(first.group(), []) if first else range(len(low))
                found |= {n for n in lines if pat.search(low[n])}
            out += [f"{ref['name']} l.{n + 1}: {ref['data'][n].strip()[:140]}" for n in sorted(found)][:2]
    rows_out = [f"{name}: {a} '{en}'" for (a, en), name in rows.items()][:MAX_HITS]
    return rows_out + out


def sentences(ar: str, n: int = 5) -> list[dict]:
    """Up to n corpus sentences using this word: [{ar, en, source}] (shortest first: they make the best examples)."""
    b = strip_article(ar)
    out = []
    for ref in _references():
        if ref["kind"] == "sentences":
            out += [{"ar": a, "en": en, "source": ref["name"]} for a, en in ref["data"]
                    if (b in _tokens(a) if " " not in b else b in a)]
    return sorted(out, key=lambda s: len(s["ar"]))[:n]


def _short(e: dict) -> dict:
    return {k: e.get(k, "") for k in ("id", "status", "ar", "tl", "pos", "gloss")}


def lookup(words: list[dict], store: Store | None = None, refs: bool = True) -> list[dict]:
    store = store or Store()
    default_variety = (settings().get("learner", {}).get("varieties") or ["darija"])[0]
    index = Index(store.entries(None))
    out = []
    for w in words:
        ar, pos, variety = w["ar"].strip(), norm_pos(w.get("pos")), w.get("variety") or default_variety
        item = {**w, "ar": ar, "pos": pos}
        panko, same = None, []
        for v in variants(ar):
            for e in store.find_all(v, variety):
                if e["status"] == "retired" or e["id"] in {x["id"] for x in same} or (panko and e["id"] == panko["id"]):
                    continue
                if panko is None and same_word(item, e):
                    panko = e
                else:
                    same.append(_short(e))
        skip = {panko["id"]} if panko else set()
        skip |= {x["id"] for x in same}
        out.append({"ar": ar, "panko": _short(panko) if panko else None, "same_letters": same,
                    "near": [] if panko else index.near(item, skip=skip),
                    "hits": _hits(ar, w.get("tl_alt", "")) if refs else []})
    if refs:
        _morph_hits(words, out, default_variety)
    return out


def _morph_hits(words: list[dict], out: list[dict], default_variety: str) -> None:
    """For a variety with a morphology database ([morph]), the analyser's readings of a one-word item go first in
    its hits: the harakat, root and POS a checked item should match."""
    from panko.checks import TOKEN, morph_for
    by_var: dict[str, list[int]] = {}
    for i, w in enumerate(words):
        if len(TOKEN.findall(w["ar"])) == 1:
            by_var.setdefault(w.get("variety") or default_variety, []).append(i)
    for variety, idx in by_var.items():
        m = morph_for(variety)
        if not m:
            continue
        db = m.dbs()[variety]
        an = m.analyse([TOKEN.findall(words[i]["ar"])[0] for i in idx], variety)
        for i in idx:
            rs = an.get(TOKEN.findall(words[i]["ar"])[0], [])
            seen = dict.fromkeys(f"{r['diac']} {r.get('pos', '')}" + (f", root {r['root']}" if r.get("root") else "")
                                 for r in rs)
            line = (f"{m.name} ({db}) readings: " + "; ".join(list(seen)[:6])) if rs else \
                f"{m.name} ({db}): no reading of this word (check the spelling)"
            out[i]["hits"] = [line, *out[i]["hits"]]


# ---- downloading the open references -------------------------------------------------------------------------------

def references_status() -> list[dict]:
    """Each configured corpus/dictionary: where it lives, whether it's there, and whether Panko can download it."""
    ev = settings().get("evidence", {})
    out = []
    for c in [*ev.get("corpora", []), *ev.get("dictionaries", [])]:
        p = _path(c.get("path", ""))
        there = p.is_dir() and any(p.iterdir()) if p.is_dir() else p.exists()
        out.append({"name": c["name"], "path": str(p), "present": bool(there), "url": c.get("url", ""),
                    "include": c.get("include", [])})
    return out


def _github_files(url: str, include: list[str], client) -> list[tuple[str, str]]:
    """(raw URL, file name) for the CSVs of a GitHub repo under the `include` folders (people-name lists skipped)."""
    owner, repo = re.match(r"https://github\.com/([^/]+)/([^/#?]+)", url).groups()
    tree = client.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1").raise_for_status()
    paths = [t["path"] for t in tree.json()["tree"] if t["type"] == "blob" and t["path"].endswith(".csv")
             and (not include or t["path"].startswith(tuple(include))) and "names" not in t["path"].rsplit("/", 1)[-1]]
    return [(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{p}", p.rsplit("/", 1)[-1]) for p in paths]


def download(force: bool = False, client=None, say=print) -> list[dict]:
    """Fetch every configured reference that has a `url` and isn't on disk yet (all of them with `force`)."""
    import httpx
    client = client or httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "panko"})
    report = []
    for r in references_status():
        p = Path(r["path"])
        if not r["url"]:
            report.append({**r, "done": "present" if r["present"] else "missing: add this file yourself"})
            continue
        if r["present"] and not force:
            report.append({**r, "done": "present"})
            continue
        if r["url"].startswith("https://github.com/"):
            p.mkdir(parents=True, exist_ok=True)
            files = _github_files(r["url"], r["include"], client)
            for raw, name in files:
                (p / name).write_bytes(client.get(raw).raise_for_status().content)
            report.append({**r, "done": f"downloaded {len(files)} files"})
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(p.suffix + ".part")
            with client.stream("GET", r["url"]) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            tmp.replace(p)
            report.append({**r, "done": f"downloaded {p.stat().st_size // 1024} KB"})
        say(f"{r['name']}: {report[-1]['done']}")
    _references.cache_clear()
    _INDEX.clear()
    return report
