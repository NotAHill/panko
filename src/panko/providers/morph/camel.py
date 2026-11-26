"""Morphological analysis with CAMeL Tools (NYU Abu Dhabi): every reading of a word, with harakat, lemma, root, POS.

CAMeL Tools pulls in torch and transformers, so it can live in its own environment (on another disk, say): set
`python` in [morph.camel] or PANKO_CAMEL_PYTHON in .env to that environment's interpreter. Panko runs a small
helper there over stdin/stdout. If camel_tools is importable here, the current interpreter is used. The analysis
databases are CAMeL's own download (`camel_data -i morphology-db-msa-r13`; CAMELTOOLS_DATA picks the folder).
Answers are cached per database in cache/morph/, so a word is analysed once.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

from panko.config import CACHE, hosted, secret
from panko.providers import register
from panko.providers.base import Morph

KEYS = ("diac", "lex", "root", "pos", "pattern", "asp", "num", "gen", "stt", "cas")
HELPER = r"""
import json, sys
from camel_tools.morphology.analyzer import Analyzer
from camel_tools.morphology.database import MorphologyDB
req = json.load(sys.stdin)
an = Analyzer(MorphologyDB.builtin_db(req["db"]))
out = {}
for w in req["words"]:
    seen, res = set(), []
    for a in an.analyze(w):
        r = {k: str(a.get(k, "")) for k in req["keys"]}
        t = tuple(r.values())
        if t not in seen:
            seen.add(t)
            res.append(r)
    out[w] = res
json.dump(out, sys.stdout, ensure_ascii=False)
"""


@register("morph", "camel")
class Camel(Morph):
    def python(self) -> str:
        # on the server the interpreter is the server's (its environment), never a path from the user's own config
        p = secret("PANKO_CAMEL_PYTHON") if hosted() else self.cfg.get("python") or secret("PANKO_CAMEL_PYTHON")
        if p:
            return p if os.path.exists(p) else ""
        return sys.executable if importlib.util.find_spec("camel_tools") else ""

    def ready(self) -> bool:
        return bool(self.dbs() and self.python())

    def _cache(self, db: str):
        p = CACHE / "morph" / f"camel-{db}.json"
        return p, (json.loads(p.read_text()) if p.exists() else {})

    def analyse(self, words: list[str], variety: str) -> dict[str, list[dict]]:
        db = self.dbs().get(variety)
        if not db:
            return {}
        path, cached = self._cache(db)
        todo = sorted({w for w in words if w and w not in cached})
        if todo:
            env = {**os.environ}
            data = secret("CAMELTOOLS_DATA") if hosted() else self.cfg.get("data") or secret("CAMELTOOLS_DATA")
            if data:
                env["CAMELTOOLS_DATA"] = data
            r = subprocess.run([self.python(), "-I", "-c", HELPER], env=env, capture_output=True, text=True,
                               input=json.dumps({"db": db, "words": todo, "keys": KEYS}, ensure_ascii=False))
            if r.returncode:
                raise RuntimeError(f"CAMeL Tools failed: {r.stderr.strip().splitlines()[-1] if r.stderr else r.returncode}"
                                   " (is the database installed? camel_data -i morphology-db-msa-r13)")
            cached |= json.loads(r.stdout)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cached, ensure_ascii=False))
        return {w: cached.get(w, []) for w in words}
