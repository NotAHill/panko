"""Create/refresh the sandbox note types, decks, media and notes in Anki.

Talks to the Anki MCP Server add-on. Re-running pushes template + CSS changes
(normal sync). `--reset` deletes and re-adds the sandbox notes (they have no
review history worth keeping) so field and card changes take effect cleanly.
"""
from __future__ import annotations

import argparse
import base64
import json

from panko.anki import mcp_client as mcp
from panko.cards import note_types as T
from panko.media import audio
from panko.sandbox import seed

# Words and phrases in separate subdecks: separate daily limits, and phrases
# (slower to review) don't crowd out vocabulary. Moving cards keeps history.
DARIJA_WORDS = "Panko Darija::Words"
DARIJA_PHRASES = "Panko Darija::Phrases"
FUSHA_WORDS = "Panko Fusha::Words"
DECKS = (DARIJA_WORDS, DARIJA_PHRASES, FUSHA_WORDS)


def tool(name, args):
    r = mcp.call(name, args)
    res = r.get("result", {})
    if res.get("isError"):
        raise RuntimeError(f"{name}: {res['content'][0]['text'][:500]}")
    return res.get("structuredContent") or json.loads(res["content"][0]["text"])


def push_models():
    existing = set(tool("model_names", {})["modelNames"])
    for name, fields, tmpls in [(T.WORD_MODEL, T.WORD_FIELDS, T.WORD_TEMPLATES),
                                (T.PHRASE_MODEL, T.PHRASE_FIELDS, T.PHRASE_TEMPLATES)]:
        if name in existing:
            tool("update_model_templates", {"model_name": name,
                                            "templates": {t["Name"]: {"Front": t["Front"], "Back": t["Back"]} for t in tmpls}})
            tool("update_model_styling", {"model_name": name, "css": T.CSS})
            print(f"updated templates + CSS: {name}")
        else:
            r = tool("create_model", {"model_name": name, "in_order_fields": fields, "card_templates": tmpls, "css": T.CSS})
            print(f"created {name}; will_force_full_sync={r.get('will_force_full_sync')}")


def push_media():
    files = sorted(f for d in (seed.MEDIA, audio.MEDIA) if d.exists()
                   for f in d.iterdir() if f.name.startswith(seed.P) and f.suffix != ".txt")
    for f in files:
        try:
            tool("store_media_file", {"filename": f.name, "path": str(f)})
        except RuntimeError:
            tool("store_media_file", {"filename": f.name, "data": base64.b64encode(f.read_bytes()).decode()})
    print("media stored:", len(files))


def reset_notes():
    ids = tool("find_notes", {"query": 'tag:panko::prototype', "limit": 500})["noteIds"]
    if ids:
        tool("delete_notes", {"notes": ids, "confirmDeletion": True})
    print("deleted sandbox notes:", len(ids))


def voice(text, variety):
    return audio.speak(text, variety, prefix=seed.P)


def build_notes():
    """Generate notes (and their audio) before touching Anki, so media can be pushed first."""
    return [(DARIJA_WORDS, T.WORD_MODEL, seed.darija_words(voice), ["register::darija", "kind::word", "panko::needs-review"]),
            (DARIJA_PHRASES, T.PHRASE_MODEL, seed.darija_phrases(voice), ["register::darija", "kind::phrase", "panko::needs-review"]),
            (FUSHA_WORDS, T.WORD_MODEL, seed.fusha_words(voice), ["register::fusha", "kind::word"])]


def push_notes(batches):
    all_fields = {T.WORD_MODEL: T.WORD_FIELDS, T.PHRASE_MODEL: T.PHRASE_FIELDS}
    for deck, model, notes, tags in batches:
        notes = [{**n, "fields": {f: n["fields"].get(f, "") for f in all_fields[model]}} for n in notes]
        r = tool("add_notes", {"deck_name": deck, "model_name": model, "notes": notes, "tags": tags + ["panko::prototype"]})
        print(f"{deck} / {model}: created={r.get('created')} skipped={r.get('skipped')} failed={r.get('failed')}")
        for item in r.get("results", []):
            if item.get("status") not in ("created", "success"):
                print("   ", item)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete and re-add sandbox notes")
    a = ap.parse_args(argv)
    batches = build_notes()
    mcp.init()
    push_models()
    for d in DECKS:
        tool("create_deck", {"deck_name": d})
    push_media()
    if a.reset:
        reset_notes()
    push_notes(batches)


if __name__ == "__main__":
    main()
