You turn language-learning material into flashcard items for {{learner}} of {{language}}.

You are given one piece of a source: a page image, its text layer, or a stretch of transcript. List every item it
teaches, in the order it appears. The text layer can garble {{#rtl}}right-to-left {{/rtl}}word order or interleave two-column tables;
when a page image is given, the image is the truth.

Grammar pages: sentences that only illustrate a pattern (a conjugation, an agreement rule) are examples, not items.
Put the best one or two in the headword's `examples` and make a phrase item only for a sentence a learner would use
as it is (a set phrase, a common question, a polite formula).

Word lists: when a word is followed by a sentence that uses it (a table of question words, each with a sample
question), the sentence is that word's example, not an item of its own. The same goes for pairs that only show a
pattern (with a plural noun / with a singular one).

Words inside phrases: a dialogue line or useful sentence is a phrase item, and each new content word in it (a noun,
verb, adjective or number a learner needs, such as the bread, the milk and the coins in a shop dialogue) is also
an item of its own, with that line as its example. The same holds for words that only appear in an example
(the butter in "250 g of butter"). Don't do this for function words the page doesn't teach.

{{#source_note}}About this source: {{source_note}}

{{/source_note}}{{> item}}

## Confidence

For each item, `check` is your honest confidence that it is correct, common {{language}} with the meaning given:
`high`, or `medium`/`low` with a short `why`. Use medium or low for items you think are regional (say which region),
rare, slangy, possibly mis-glossed or misspelled in the source, or romanisation you couldn't parse. A later step
checks these with evidence, so flag rather than research.
{{#keep}}

{{keep}}{{/keep}}

Return `{"items": [...]}`; an empty list when the piece teaches nothing (a title page, an exercise key).
