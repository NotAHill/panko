from panko.cards import render as R


def test_examples_have_no_provenance_labels():
    html = R.examples([R.Example("التلفاز قدام الكنابي.", "t-tilfaz 9eddam l-kanapi", "The TV is in front of the sofa.",
                                 source="Lesson, 21 Nov")])
    assert "Lesson" not in html  # sources only appear in the Sources section
    assert "say" not in html     # no audio -> no play button


def test_example_audio_is_tap_to_play_not_sound_tag():
    html = R.examples([R.Example("a", "b", "c", audio="x.mp3")])
    assert "[sound:" not in html
    assert '<audio preload="none" src="x.mp3">' in html


def test_sources_collect_examples_audio_picture():
    e = R.Entry(examples=[R.Example("a", "b", "c", source="Quran 16:75")], word_sources=["Wiktionary"],
                audio_source="ElevenLabs", image_source="Commons")
    html = R.sources(e)
    for s in ["Wiktionary", "Example 1: Quran 16:75", "Audio: ElevenLabs", "Picture: Commons"]:
        assert s in html


def test_grammar_is_readable():
    assert R.grammar(pos="noun", gender="masculine") == "<div>noun, masculine</div>"
    assert R.grammar() == ""


def test_html_is_escaped():
    assert "&lt;b&gt;" in R.examples([R.Example("<b>", "", "")])


def test_scripture_cite_shows_under_example():
    html = R.examples([R.Example("ضَرَبَ اللَّهُ مَثَلًا", "", "", cite="Quran 16:75")])
    assert '<div class="cite">Quran 16:75</div>' in html
