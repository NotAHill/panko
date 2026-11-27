"""Any language: script, matching, prompts, cards and a whole source for a Spanish learner set up by `panko init`."""
import re
import tomllib
from pathlib import Path

import pytest

from panko import config, dedupe, evidence, lang, prompts, setup, work
from panko.cards import build
from panko.cards import note_types as T
from panko.store import Store


def use(monkeypatch, cfg: dict):
    monkeypatch.setattr(config, "settings", lambda: cfg)
    monkeypatch.setattr(build, "settings", lambda: cfg)
    monkeypatch.setattr(evidence, "settings", lambda: cfg)
    evidence._references.cache_clear()


@pytest.fixture
def spanish(monkeypatch):
    cfg = tomllib.loads(setup.render({"language": "spanish"}))
    use(monkeypatch, cfg)
    yield cfg
    evidence._references.cache_clear()


def test_scripts_are_read_from_unicode():
    assert lang.script_of("ñ") == "Latin" and lang.script_of("ش") == "Arabic" and lang.script_of("食") == "Han"
    assert lang.script_of("ж") == "Cyrillic" and lang.script_of("ّ") == "" and lang.script_of("3") == ""
    assert lang.tokens("¿Dónde está la estación?") == ["Dónde", "está", "la", "estación"]
    assert lang.tokens("كَتَبَ الْوَلَدُ") == ["كَتَبَ", "الْوَلَدُ"] and lang.tokens("नमस्ते दुनिया") == ["नमस्ते", "दुनिया"]


def test_spanish_preset(spanish):
    L = spanish["learner"]
    assert L["script"] == "Latin" and L["varieties"] == ["spanish"] and L["translit"]["main"] == ""
    assert spanish["stt"]["elevenlabs"]["language"] == "spa" and spanish["morph"]["camel"]["dbs"] == {}
    assert [c["name"] for c in spanish["evidence"]["corpora"]] == ["Wiktionary, Spanish entries"]
    assert lang.label() == "Latin script" and not lang.is_rtl() and not lang.romanised()
    assert lang.in_target("comprar") and not lang.in_target("شرى")


def test_matching_with_articles_and_case(spanish):
    assert lang.bare("¿Qué Tal?") == "qué tal" and lang.strip_article("La Casa") == "casa"
    assert lang.strip_article("los") == "los"                         # an article alone is a word
    assert dedupe.nar("la casa") == dedupe.nar("Casa")
    assert lang.consonants("casa") == "casa"                           # vowels are written: no skeleton key


def test_french_elision(monkeypatch):
    use(monkeypatch, {"learner": {"script": "Latin", "articles": ["le", "la", "l'", "les"]}})
    assert lang.strip_article("l'eau") == "eau" and lang.strip_article("L’école") != "lécole"
    assert lang.strip_article("le pain") == "pain"


def test_marks_folded_only_when_asked(monkeypatch):
    use(monkeypatch, {"learner": {"script": "Latin"}})
    assert lang.bare("papá") != lang.bare("papa")
    use(monkeypatch, {"learner": {"script": "Hebrew", "fold_marks": True}})
    assert lang.bare("שָׁלוֹם") == "שלום" and lang.is_rtl()


def test_prompts_for_spanish(spanish):
    for name in prompts.PROMPTS:
        text = prompts.render(name)
        assert not re.search(r"[؀-ۿ]", text), name
        assert not re.search(r"\b(Darija|Fusha|Arabizi|harakat|shadda|Moroccan)\b", text), name   # Arabic: a loan source
    extract = prompts.render("extract")
    assert "Spanish text in Latin script, with its accents" in extract and "no romanisation" in extract
    assert "comprar" in extract and "right-to-left" not in extract


def test_prompt_files_assume_no_language():
    """S9: everything about a language comes from config; the prompt files are the same for every learner."""
    for f in Path(prompts.__file__).parent.glob("*.md"):
        text = f.read_text()
        assert not re.search(r"[֐-ࣿ]", text), f"{f.name} has Arabic or Hebrew script"
        assert not re.search(r"\b(Darija|Fusha|Arabic|Arabizi|harakat|shadda|Moroccan|Quran)\b", text), f.name


def test_a_spanish_source_end_to_end(spanish, tmp_path, monkeypatch):
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(work, "PAGES", tmp_path / "pages")
    t = tmp_path / "leccion.txt"
    t.write_text("En la tienda\n¿Cuánto cuesta el pan?\nUn kilo de manzanas, por favor.")
    work.add_source(str(t), "lesson", "En la tienda")
    item = {"kind": "word", "ar": "la manzana", "tl": "", "gloss": "apple", "pos": "noun", "gender": "f",
            "examples": [{"ar": "Un kilo de manzanas, por favor.", "en": "A kilo of apples, please.",
                          "source": "source"}],
            "verdict": {"verdict": "ok", "summary": "fine"}, "picture": {"choice": "skip"}}
    bad = work.submit("en-la-tienda", "c001", {"items": [{**item, "ar": "تفاحة"}]})
    assert not bad["ok"] and any("Latin script" in e for e in bad["errors"])
    assert work.submit("en-la-tienda", "c001", {"items": [item]})["ok"]       # no romanisation needed
    store = Store(tmp_path / "es.db")
    rep = work.ingest_source("en-la-tienda", store)
    assert rep["new"] == 1
    [e] = store.entries("candidate")
    assert e["variety"] == "spanish" and e["id"].startswith("sw-")
    assert store.find("manzana", "spanish")["id"] == e["id"]                  # found without its article
    note = build.to_note(e)
    assert note["deck"] == "Panko::Spanish" and note["fields"]["Translit"] == "" and note["fields"]["Register"] == "Spanish"
    assert 'class="tgt ex-tgt" dir="auto"' in note["fields"]["ExamplesHTML"]
    css = T.css()
    assert "direction: ltr" in css and "Georgia" in css and "Naskh" not in css


def test_cards_for_two_scripts(monkeypatch):
    use(monkeypatch, {"learner": {"script": "Arabic", "varieties": ["darija", "spanish"],
                                  "scripts": {"spanish": "Latin"}}})
    css = T.css()
    assert ".tgt { font-family: \"Noto Naskh Arabic\"" in css and "direction: rtl" in css
    assert '[data-v="Spanish"] .tgt, .tgt[data-v="Spanish"] { font-family: "Iowan Old Style"' in css
    assert lang.in_target("hola", "spanish") and not lang.in_target("hola", "darija")


def test_japanese_takes_a_list_of_scripts(monkeypatch):
    use(monkeypatch, {"learner": {"script": ["Han", "Hiragana", "Katakana"], "varieties": ["japanese"]}})
    assert lang.in_target("食べる") and lang.in_target("コーヒー") and not lang.in_target("taberu")
    assert lang.label() == "Han, Hiragana or Katakana script" and "Hiragino" in lang.font()[0]


# ---- a PDF's text layer

def test_a_scans_ocr_layer_is_not_trusted_for_a_non_latin_script(monkeypatch):
    monkeypatch.setattr(lang, "_learner", lambda: {"script": "Arabic"})
    ocr = "kam shahar bis-sana\n(a Sly ga eS\njadlen() ناككوا 5\n$51stLyaby otزان daa"
    assert lang.text_layer(ocr, ocr=True) == "ocr"
    assert "OCR" in lang.layer_note("ocr") and "Arabic" in lang.layer_note("ocr")
    assert lang.text_layer("") == "none" and lang.text_layer("116 | 22") == "none"
    clean = "kam shahar bis-sana     كم شهر بالسنة؟\nis-seef haar loo baarid bil-9iraaq?   الصيف حار لو بارد بالعراق؟"
    assert lang.text_layer(clean) == "ok"                                  # Arabizi digits in Latin words are fine
    assert lang.text_layer("ﻣﺮﺣﺒﺎ kam shahar") == "shaped"   # presentation forms
    assert lang.text_layer("$51stLy otزان 95833؟بالش Bjl> 5ناككوا x|y") == "garbled"
    monkeypatch.setattr(lang, "_learner", lambda: {"script": "Latin"})
    assert lang.text_layer("la casa es grande", ocr=True) == "ok"         # OCR is fine for Latin


def test_the_model_gets_only_a_trusted_layer(monkeypatch, tmp_path):
    import shutil
    if not shutil.which("pdftotext"):
        pytest.skip("needs poppler")
    monkeypatch.setattr(lang, "_learner", lambda: {"script": "Arabic"})
    monkeypatch.setattr(work, "WORK", tmp_path / "work")
    monkeypatch.setattr(work, "PAGES", tmp_path / "pages")
    monkeypatch.setattr(work, "sources", lambda: {"s": {"id": "s", "type": "pdf", "path": str(tmp_path / "x.pdf"),
                                                        "units": ["p001"]}})
    monkeypatch.setattr(work, "book_page", lambda s, u: 1)

    class Done:
        def __init__(self, out):
            self.stdout = out
    calls = []

    def run(cmd, **kw):
        calls.append(cmd[0])
        if cmd[0] == "pdftoppm":
            (tmp_path / "pages" / "s" / "p001.png").write_bytes(b"png")
        return Done("kam shahar bis-sana\njadlen() ناككوا 5" if cmd[0] == "pdftotext" else "")
    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(work, "_ocr_page", lambda p, n: True)
    p = work.page("s", "p001")
    assert p["text"] == "" and "ناككوا" in p["layer"] and p["layer_state"] == "ocr"
    monkeypatch.setattr(work, "_ocr_page", lambda p, n: False)
    assert work.page("s", "p001")["layer_state"] in ("ok", "garbled")
