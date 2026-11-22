from panko.ingest.verify import apply, item_key


def word(ar, **kw):
    return {"kind": "word", "variety": "darija", "ar": ar, "tl": "x", "gloss": "g", "pos": "noun",
            "said": {"ar": "s", "tl": "s", "en": "s"}, **kw}


def test_key_ignores_article_and_separates_pos():
    assert item_key(word("الشرجم")) == "شرجم|noun"
    assert item_key({"kind": "phrase", "ar": "واخا"}) == "واخا|phrase"


def test_verdicts_drop_fix_note_and_tags():
    items = [word("شرجم"), word("كاعي"), word("ليمون"), word("سوسي")]
    v = {"شرجم|noun": {"verdict": "regional", "region": "Fes, north", "learner_note": "Mainly Fes and the north."},
         "كاعي|noun": {"verdict": "drop"},
         "ليمون|noun": {"verdict": "fix", "fix": {"gloss": "oranges", "example_en": "One orange."}},
         "سوسي|noun": {"verdict": "doubtful"}}
    out = {i["ar"]: i for i in apply(items, v, {"سوسي|noun": {"cards": ["recognition"]}})}
    assert "كاعي" not in out
    assert out["شرجم"]["gloss_note"] == "Mainly Fes and the north."
    assert "region::fes-north" in out["شرجم"]["tags"] and out["شرجم"]["check"]["verdict"] == "regional"
    assert out["ليمون"]["gloss"] == "oranges" and out["ليمون"]["said"]["en"] == "One orange."
    assert "panko::doubtful" in out["سوسي"]["tags"] and out["سوسي"]["cards"] == ["recognition"]
    assert items[0].get("tags") is None  # input untouched
