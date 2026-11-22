from panko.cards import note_types as T
from panko.sandbox import seed


def test_seed_fields_exist_and_ids_unique():
    notes = [(T.WORD_FIELDS, n) for n in seed.darija_words() + seed.fusha_words()]
    notes += [(T.PHRASE_FIELDS, n) for n in seed.darija_phrases()]
    ids = [n["fields"]["PankoID"] for _, n in notes]
    assert len(ids) == len(set(ids))
    for fields, n in notes:
        assert set(n["fields"]) <= set(fields), set(n["fields"]) - set(fields)


def test_seed_media_files_exist():
    import re
    for n in seed.darija_words() + seed.darija_phrases() + seed.fusha_words():
        for f in re.findall(r'(_panko_proto_[\w.]+\.(?:jpg|svg|mp3))', str(n["fields"])):
            assert (seed.MEDIA / f).exists(), f
