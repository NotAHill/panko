"""Panko note types: fields, card templates and CSS (spec v0.2).

Field lists are frozen for the prototype models: adding/removing/reordering fields
forces a full sync. Templates and CSS can change freely (normal sync)."""

WORD_MODEL = "Panko • Word (proto)"
PHRASE_MODEL = "Panko • Phrase (proto)"

WORD_FIELDS = [
    "Word", "WordBare", "WordPartial", "WordPrompt", "Translit", "TranslitAlt",
    "Register", "POS", "Gloss", "GlossNote",
    "Audio", "AudioSource", "Image", "ImageSource",
    "Root", "Pattern", "VerbForm", "Present", "Imperative", "Masdar", "Preposition", "Gender", "Plural",
    "ExamplesHTML", "MorphologyHTML", "LinksHTML", "NotesHTML", "SourcesHTML", "MyNotes",
    "EnableProduction", "EnableListening", "EnablePicture", "EnablePlural", "EnableVerbForms",
    "EnableRoot", "EnableTyped", "EnableSpare1", "EnableSpare2",
    "PankoID", "PankoData", "Spare1", "Spare2", "Spare3", "Spare4",
]

PHRASE_FIELDS = [
    "Phrase", "PhraseFull", "PhrasePrompt", "Translit", "TranslitAlt", "Register",
    "Translation", "Literal", "Audio", "AudioSource", "Image", "ImageSource",
    "UsageHTML", "KeyWordsHTML", "DialogueHTML", "NotesHTML", "SourcesHTML", "MyNotes",
    "EnableProduction", "EnableListening", "EnableTyped", "EnableSpare1", "EnableSpare2",
    "PankoID", "PankoData", "Spare1", "Spare2", "Spare3", "Spare4",
]

CSS = r"""
/* Anki picks the page direction from the first letter on the card, so a back that
   starts with Arabic turned the English RTL. Pin LTR; only .ar is RTL. */
html, body, #qa, .card { direction: ltr; }
.card { font-family: -apple-system, "Helvetica Neue", "Segoe UI", Roboto, sans-serif;
  font-size: 18px; line-height: 1.45; text-align: center; padding: 20px 16px; }
.ar { font-family: "Noto Naskh Arabic", "Geeza Pro", "Al Nile", "Traditional Arabic", serif;
  direction: rtl; unicode-bidi: isolate; line-height: 2; }
.en, .tl, .gloss, .gnote, .gram, .block, .ex-tl, .ex-en, .cite, .prompt, table.rel, details.srcs { direction: ltr; unicode-bidi: isolate; }
.word { font-size: 48px; }
.phrase { font-size: 32px; }
.prompt { font-size: 32px; margin-top: 24px; }
.cue { font-size: 15px; opacity: .55; margin-top: 4px; }
.ans { margin-bottom: 4px; }
.pic img { max-width: 100%; max-height: 220px; border-radius: 8px; }
.tl { font-size: 17px; opacity: .65; }
.tl2 { font-size: 15px; margin-left: 10px; opacity: .8; }
.gloss { font-size: 24px; margin-top: 6px; }
.gnote { font-size: 15px; opacity: .6; }
.gram { font-size: 15px; opacity: .75; margin-top: 8px; }
.gram .ar { font-size: 19px; line-height: 1.6; }
.block { text-align: left; max-width: 560px; margin: 22px auto 0; }
.lbl { font-size: 13px; opacity: .5; margin-bottom: 6px; }
.ex { padding: 10px 0; border-top: 1px solid rgba(128,128,128,.2); }
.ex:first-child { border-top: 0; }
.ex-ar { font-size: 24px; text-align: right; line-height: 1.7; }
.ex-tl { font-size: 14px; opacity: .6; }
.ex-en { font-size: 16px; }
.cite { font-size: 13px; opacity: .55; margin-top: 2px; }
.say { display: inline-block; width: 26px; height: 26px; margin-right: 8px; vertical-align: middle;
  border-radius: 50%; border: 1px solid rgba(128,128,128,.5); cursor: pointer; position: relative; }
.say::after { content: ""; position: absolute; left: 10px; top: 7px; border-style: solid;
  border-width: 6px 0 6px 9px; border-color: transparent transparent transparent currentColor; opacity: .75; }
.say.on { background: rgba(128,128,128,.25); }
table.rel { border-collapse: collapse; font-size: 16px; }
table.rel td { padding: 2px 14px 2px 0; vertical-align: baseline; }
table.rel td.ar { font-size: 21px; text-align: right; line-height: 1.6; }
.notes { font-size: 16px; }
.mine { padding: 8px 10px; border-radius: 6px; background: rgba(255,214,0,.1); }
details.srcs { font-size: 13px; opacity: .55; }
details.srcs summary { cursor: pointer; }
details.srcs ul { margin: 6px 0 0; padding-left: 18px; }
"""

# Example audio: tapping .say plays its <audio> children one after another (one per voice). Anki's own [sound:] tags
# autoplay, so only the headword uses those. Audio must be mp3: desktop Anki's
# web view can't decode AAC/m4a.
PLAY_JS = r"""<script>
document.querySelectorAll('.say').forEach(function (b) {
  b.onclick = function (e) {
    e.preventDefault(); e.stopPropagation();
    var list = b.querySelectorAll('audio'); if (!list.length) return;
    document.querySelectorAll('.say audio').forEach(function (x) { x.pause(); x.onended = null; });
    document.querySelectorAll('.say.on').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    (function play(i) {
      if (i >= list.length) { b.classList.remove('on'); return; }
      var a = list[i]; a.currentTime = 0; a.onended = function () { play(i + 1); }; a.play();
    })(0);
  };
});
</script>"""

# ---------- Word ----------

WORD_BACK_BLOCK = r"""
{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}
<div class="ar word">{{Word}}</div>
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
<div class="tl">{{Translit}}{{#TranslitAlt}}<span class="tl2">{{TranslitAlt}}</span>{{/TranslitAlt}}</div>
<div class="gloss">{{Gloss}}</div>
{{#GlossNote}}<div class="gnote">{{GlossNote}}</div>{{/GlossNote}}
{{#MorphologyHTML}}<div class="gram">{{MorphologyHTML}}</div>{{/MorphologyHTML}}
{{#ExamplesHTML}}<div class="block">{{ExamplesHTML}}</div>{{/ExamplesHTML}}
{{#LinksHTML}}<div class="block"><div class="lbl">Related</div>{{LinksHTML}}</div>{{/LinksHTML}}
{{#NotesHTML}}<div class="block notes">{{NotesHTML}}</div>{{/NotesHTML}}
{{#MyNotes}}<div class="block mine">{{MyNotes}}</div>{{/MyNotes}}
{{#SourcesHTML}}<div class="block"><details class="srcs"><summary>Sources</summary>{{SourcesHTML}}</details></div>{{/SourcesHTML}}
""" + PLAY_JS


def _word_back(top: str = "") -> str:
    return top + '\n<hr id="answer">\n' + WORD_BACK_BLOCK


WORD_TEMPLATES = [
    {"Name": "1 Recognition",
     "Front": '<div class="ar word">{{WordPrompt}}</div>{{#Audio}}<div>{{Audio}}</div>{{/Audio}}',
     "Back": _word_back()},
    {"Name": "2 Production",
     "Front": '{{#EnableProduction}}{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}<div class="prompt">{{Gloss}}</div>{{/EnableProduction}}',
     "Back": _word_back()},
    {"Name": "3 Listening",
     "Front": '{{#EnableListening}}{{#Audio}}<div class="prompt">{{Audio}}</div>{{/Audio}}{{/EnableListening}}',
     "Back": _word_back()},
    {"Name": "4 Picture",
     "Front": '{{#EnablePicture}}{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}{{/EnablePicture}}',
     "Back": _word_back()},
    {"Name": "5 Plural",
     "Front": '{{#EnablePlural}}{{#Plural}}<div class="ar word">{{Word}}</div><div class="cue">plural</div>{{/Plural}}{{/EnablePlural}}',
     "Back": _word_back('<div class="ar word ans">{{Plural}}</div>')},
    {"Name": "6 Verb forms",
     "Front": '{{#EnableVerbForms}}{{#Masdar}}<div class="ar word">{{Word}}</div><div class="cue">present · masdar</div>{{/Masdar}}{{/EnableVerbForms}}',
     "Back": _word_back('<div class="ar word ans">{{Present}} · {{Masdar}}</div>')},
    {"Name": "7 Root",
     "Front": '{{#EnableRoot}}{{#Root}}<div class="ar word">{{Word}}</div><div class="cue">root</div>{{/Root}}{{/EnableRoot}}',
     "Back": _word_back('<div class="ar word ans">{{Root}}</div>')},
    {"Name": "8 Typed",
     "Front": '{{#EnableTyped}}<div class="prompt">{{Gloss}}</div>{{type:WordBare}}{{/EnableTyped}}',
     "Back": '{{#EnableTyped}}{{type:WordBare}}{{/EnableTyped}}\n<hr id="answer">\n' + WORD_BACK_BLOCK},
    {"Name": "9 Spare 1",
     "Front": '{{#EnableSpare1}}{{EnableSpare1}}{{/EnableSpare1}}',
     "Back": _word_back()},
    {"Name": "10 Spare 2",
     "Front": '{{#EnableSpare2}}{{EnableSpare2}}{{/EnableSpare2}}',
     "Back": _word_back()},
]

# ---------- Phrase ----------

PHRASE_BACK_BLOCK = r"""
{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}
<div class="ar phrase">{{#PhraseFull}}{{PhraseFull}}{{/PhraseFull}}{{^PhraseFull}}{{Phrase}}{{/PhraseFull}}</div>
{{#Audio}}<div>{{Audio}}</div>{{/Audio}}
<div class="tl">{{Translit}}{{#TranslitAlt}}<span class="tl2">{{TranslitAlt}}</span>{{/TranslitAlt}}</div>
<div class="gloss">{{Translation}}</div>
{{#Literal}}<div class="gnote">literally “{{Literal}}”</div>{{/Literal}}
{{#UsageHTML}}<div class="block notes">{{UsageHTML}}</div>{{/UsageHTML}}
{{#KeyWordsHTML}}<div class="block"><div class="lbl">Words</div>{{KeyWordsHTML}}</div>{{/KeyWordsHTML}}
{{#DialogueHTML}}<div class="block">{{DialogueHTML}}</div>{{/DialogueHTML}}
{{#NotesHTML}}<div class="block notes">{{NotesHTML}}</div>{{/NotesHTML}}
{{#MyNotes}}<div class="block mine">{{MyNotes}}</div>{{/MyNotes}}
{{#SourcesHTML}}<div class="block"><details class="srcs"><summary>Sources</summary>{{SourcesHTML}}</details></div>{{/SourcesHTML}}
""" + PLAY_JS


def _phrase_back(top: str = "") -> str:
    return top + '\n<hr id="answer">\n' + PHRASE_BACK_BLOCK


PHRASE_TEMPLATES = [
    {"Name": "1 Recognition",
     "Front": '<div class="ar phrase">{{PhrasePrompt}}</div>{{#Audio}}<div>{{Audio}}</div>{{/Audio}}',
     "Back": _phrase_back()},
    {"Name": "2 Production",
     "Front": '{{#EnableProduction}}{{#Image}}<div class="pic">{{Image}}</div>{{/Image}}<div class="prompt">{{Translation}}</div>{{/EnableProduction}}',
     "Back": _phrase_back()},
    {"Name": "3 Listening",
     "Front": '{{#EnableListening}}{{#Audio}}<div class="prompt">{{Audio}}</div>{{/Audio}}{{/EnableListening}}',
     "Back": _phrase_back()},
    {"Name": "4 Typed",
     "Front": '{{#EnableTyped}}<div class="prompt">{{Translation}}</div>{{type:Phrase}}{{/EnableTyped}}',
     "Back": '{{#EnableTyped}}{{type:Phrase}}{{/EnableTyped}}\n<hr id="answer">\n' + PHRASE_BACK_BLOCK},
    {"Name": "5 Spare 1",
     "Front": '{{#EnableSpare1}}{{EnableSpare1}}{{/EnableSpare1}}',
     "Back": _phrase_back()},
    {"Name": "6 Spare 2",
     "Front": '{{#EnableSpare2}}{{EnableSpare2}}{{/EnableSpare2}}',
     "Back": _phrase_back()},
]
