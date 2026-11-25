## The item format

An item is one word (`kind: "word"`) or one phrase or short sentence a learner would say or hear (`kind: "phrase"`).
`variety` is one of {{varieties}}. Fields with nothing to say are `""` or `[]`.

- `ar`: the {{language}} text in {{script}}{{#spelling}}, {{spelling}}{{/spelling}}. Use the source's
  spelling when it gives {{script}}; when it gives only romanisation, write the usual spelling for this variety.
  Nouns without the article unless the article belongs to the expression.
- `tl`: {{tl_main}}. {{#tl_main_rules}}Style: {{tl_main_rules}}. {{/tl_main_rules}}When the source has its own
  romanisation in this style, keep it exactly (drop capitals used only for teaching emphasis).
- `tl_alt`: {{tl_alt}}.
- `gloss`: short {{gloss_language}} meaning, as a learner wants it ("to buy", "expensive", "next to"); a second
  common sense after a semicolon ("engineering; geometry"). Phrases get a
  natural translation; `literal` holds the word-for-word sense when it helps.
- `gloss_note`: only real learner information: origin ("from French *chaise*"), register ("polite"), irregular
  gender, the everyday synonym. Never where the item came from, never doubts.
- Words: `pos`; `gender` (`m`/`f`, `n` for a neuter) for nouns in a language with grammatical gender; `plural`
  ({{script}}) when the source gives it or you are sure.
  Verbs: the headword is the dictionary form{{#ex_verb}} ({{ex_verb}}){{/ex_verb}}; a verb
  whose meaning comes with a fixed preposition keeps it in the headword{{#ex_fixed_prep}} ({{ex_fixed_prep}}){{/ex_fixed_prep}},
  a verb that merely often takes one doesn't;
  `present` is the 1st-person singular present{{#ex_present}} ({{ex_present}}){{/ex_present}} and `imperative` the
  2nd-person singular, when known.
- Phrases: `usage` is one short sentence on when you'd say it, only if the source explains it or it's useful.
- `examples`: every word needs one example sentence containing it, used in this sense: `{ar, tl, en, source}`.
  Prefer a sentence from the source itself (`source`: "source"); otherwise write one short, natural sentence
  with `source`: "written by Panko, not yet checked". Phrases don't need one.
- `related`: up to 4 genuinely useful links: synonyms the source pairs it with, the opposite, same root or family{{#standard}},
  the {{standard}} equivalent (meaning ends with "({{standard}})"){{/standard}}.
- `tags`: one `topic::` tag from: {{topics}}. Add another only if none fits.
- `notes`: a conjugation or other table the source gives for this item, as plain text; usually empty.

What becomes an item: vocabulary, key phrases, and whole sentences a learner would actually say or hear. Grammar
tables give one item per lexical word (not per conjugated form). The same word twice is one item. Skip
explanations, headings and exercise instructions.
