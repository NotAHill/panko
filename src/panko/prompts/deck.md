You turn rows from old shared flashcard decks into checked items for {{learner}} of {{language}}.

The decks were made by other learners and are unverified: glosses are often loose or wrong,{{#standard}} {{standard}} is mixed in,{{/standard}}
spellings vary, plurals sit after a `/`, and some {{script}} is garbled. For each row, either write corrected
items with a verdict, or drop it with a reason. Extract and check in one pass.

{{#source_note}}About this deck: {{source_note}}

{{/source_note}}## The rows

Each row is `{"id", "ar", "tl", "en", "picture_hint", "studied", "evidence"}`, plus `fields` (the whole note,
field name → text) when Panko doesn't know the deck's note type: then `ar` and `en` are guesses, so read `fields`
and take the word and its meaning from wherever they are (instructions and hints are not meanings).
- `ar` may hold `word / plural`, `word, plural` (with the language's own comma), `(synonym)`, or two words run together (two synonyms for one
  meaning). Split it: one item per real headword; a plural goes in `plural`.
- `en` may be empty when the deck's back was a picture; then `picture_hint` (the picture's file name) is the meaning.
- `tl` is the deck's own romanisation, if any: keep it when it's sound and in the style below, otherwise rewrite it.
- Many rows are sentences: keep one as a phrase only if it is natural, useful and short; otherwise take the useful
  word from it, or drop it.
- `evidence` is what Panko found for the row (see Evidence).

{{> item}}

Differences for deck rows:
- Apply your verdict directly in the item: correct `ar`, `gloss`, `pos` and so on in place. The verdict is `fix`
  whenever you changed what the row said (its word, spelling or meaning, beyond tidying wording), `ok` only when
  the row was right as given.
- Every item carries its row's `src_id` (a split row gives several items with the same `src_id`).
- For examples, prefer a corpus sentence from the evidence when it is natural and uses the word in this sense
  (`source`: "corpus"; keep its text, tidy its romanisation); otherwise write one.
- `region`: as in the verdict. Tags: add `region::<slug>` for regional items (`region::north`) and
  `panko::doubtful` for doubtful ones.
- A real but less usual synonym of an everyday word: `cards` = `["recognition"]` and name the everyday word in
  `gloss_note` ("{{ex_everyday}}"). Otherwise `cards` = `[]` (the defaults).
- Append the verdict's learner note to `gloss_note` (words) or `usage` (phrases), and leave `learner_note` in
  `check` too.

{{> verdict}}

{{> evidence}}

## Drop (in `dropped`, with a short `why`)
- Not {{language}}: {{#standard}}{{standard}}-only words speakers don't use in speech (keep {{standard}}-ish words
  that are used, register "{{standard}}-ish"), {{/standard}}words of another language mislabelled as {{language}},
  fragments, junk, rows with no target-language text.
- Proper nouns of little use (place names other than countries and major cities, people's names).
- Wrong or unnatural sentences you can't confidently fix.
{{#keep}}- {{keep}}
{{/keep}}{{#drop}}- {{drop}}
{{/drop}}
Every row `id` appears as some item's `src_id` or in `dropped`. Return `{"items": [...], "dropped": [...]}`.
