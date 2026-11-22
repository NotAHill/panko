import re

from panko.cards import note_types as T


def fields_used(tmpl: str) -> set[str]:
    return {m.split(":")[-1] for m in re.findall(r"{{[#^/]?([^}]+)}}", tmpl)} - {"FrontSide"}


def test_templates_only_reference_existing_fields():
    for fields, tmpls in [(T.WORD_FIELDS, T.WORD_TEMPLATES), (T.PHRASE_FIELDS, T.PHRASE_TEMPLATES)]:
        for t in tmpls:
            missing = (fields_used(t["Front"]) | fields_used(t["Back"])) - set(fields)
            assert not missing, (t["Name"], missing)


def test_fronts_give_no_hints():
    prod = next(t for t in T.WORD_TEMPLATES if t["Name"] == "2 Production")["Front"]
    assert fields_used(prod) == {"EnableProduction", "Gloss"}


def test_register_is_never_shown():
    for t in T.WORD_TEMPLATES + T.PHRASE_TEMPLATES:
        assert "{{Register}}" not in t["Front"] + t["Back"]


def test_field_lists_frozen():
    # changing these forces a full sync on every device; bump deliberately
    assert len(T.WORD_FIELDS) == 44 and len(T.PHRASE_FIELDS) == 29
