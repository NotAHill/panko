# Decisions

Newest first. One paragraph each: what, and why. Reverse one by adding a new entry.

**2026-11-23 · Pictures are converted with Pillow, a core dependency; no macOS-only tools.**
Photo downloads and drawings were turned into JPEGs with `sips`, which exists only on macOS. CI (Ubuntu) failed
on it, and so would any learner on Linux or Windows. Pillow does the same job everywhere (JPEG, longest side
capped, never enlarged, transparency on white). Every card needs a picture, so Pillow is now a core dependency;
the `images` extra stays, empty, so older install commands still work.

**2026-11-23 · The last hand-run steps become commands and chat tools.**
Picture choice, example sentences and gloss clashes were briefs agents followed. They are now prompts in the
package with a command (API mode) and tools (chat mode) each, writing the same files, so another learner never
needs a brief. Picture choice searches photos for drawing-planned cards too, since a photo is free and a drawing
isn't, and reuses earlier search folders. A clash decision never removes a card already in Anki: a duplicate there
becomes recognition-only and is listed for the learner, because its review history matters.

**2026-11-23 · Fusha: one deck, production cards, no transliteration; doubtful items wait.**
Fusha gets one deck (no separate Quranic deck). Production cards (English → target) are on by default for every
language, Fusha included. Fusha cards show only the Arabic script: `[learner.translit] none_for` lists varieties
without transliteration, so another learner can choose the same for theirs. Serious Explorer's notes convert to
Panko notes keeping their pictures and word recordings; their example sentences and audio are generated. That
second Phase 6 round waits until Panko supports other languages. Doubtful items are kept in the store but not
activated until the learner clears one (by naming its id), so nothing unconfirmed reaches Anki.

**2026-11-23 · Words inside a taught phrase are items too; a teaching source isn't doubted on memory.**
S7 compared API mode with the chat agents. The packaged extract prompt kept a shop dialogue's lines as phrases but
not the words in them (bread, milk, change, dirham), so a sheet gave 31 items where the agents gave 55. A learner
needs those words, so each new content word in a phrase or example becomes an item with that line as its example.
The check also marked a teacher's words doubtful because it would have said them differently. A teaching source
now wins over memory: the item stays `ok`, the more usual word goes in `usual_word` and a learner note, and only
evidence can make it `doubtful` or `fix` (it did for ربعة, which DODa lists as "four"). Verbs with a fixed
preposition keep it in the headword (تخلص من), as in the learner's existing cards.

**2026-11-23 · AGPL-3.0-or-later, with a contributor agreement.**
Panko is open source so other learners can run and improve it. The AGPL rather than MIT means anyone who runs a changed
Panko as a service must share their changes, and it fits the AGPL `anki` library that migrations use. The owner isn't
bound by the licence, so a paid hosted service or a commercial licence stays possible. Outside contributions would
block that, so `CONTRIBUTING.md` asks contributors to grant the right to relicense what they contribute. Released
versions stay AGPL.

**2026-11-23 · Code and data apart: a Panko folder, templates in the package.**
An installed Panko can't keep a learner's config, store and media next to its code, so Panko works in a *Panko folder*:
`PANKO_HOME` if set, else the nearest folder up from the working directory that has `config/panko.toml` (like git finds
a repo), else the source checkout it runs from. A developer's checkout is its own Panko folder, so nothing moved. The
config and `.env` templates moved into the package (`src/panko/templates/`) so `panko init` works from a wheel. The
Claude snippet from `panko mcp --config` names the folder with `PANKO_HOME` for an install, since Claude starts the
server from its own working directory.

**2026-11-23 · Settings for another learner: a generic template, your config states your choices.**
`panko init` writes `config/panko.toml` from `panko.example.toml`, a template with no personal choices (no
dress rules, teacher, voices or private books), filled with a few answers; a learner adds their own rules to it.
Everything that was hard-coded for one person moved to config with the old values as defaults: deck names, the Anki
address and profile, the collection path (per operating system), and the migration card map, which is now detected
from the old note type's templates when config doesn't name it, since other people's decks use other note types. Open
reference data downloads itself (`panko refs --download`: DODa from its repo, Wiktionary from kaikki.org's extracts);
private books are only ever a path. Media file prefixes and note type names stay fixed: changing them would orphan
existing media and notes.

**2026-11-23 · "Same letters, another word" only when a doubled consonant says so.**
Transliterations are noisy: a model wrote شحال as `chhal` where the card has `sh7al`, and comparing whole consonant
skeletons made it a new word. Real same-letter pairs in Darija differ by gemination (ضحك d7ek / ضحّك de77ek,
رجع rje3 / rejje3, علاقة 3ala9a / 3alla9a), so two items with the same letters are different words only when their
skeletons are equal once doubled letters are collapsed but differ as written; any other mismatch is treated as the
same word with a spelling slip. POS splits a word only for verb vs anything else (دار house / to do) and noun vs
function word (ما water / not); adverb vs pronoun or adjective vs adverb are the same word labelled differently.

**2026-11-23 · API mode writes the same unit results as chat mode.**
`panko work run` is one pipeline per unit (extract → local evidence → check → picture plan) that ends in the same
`work.submit` a chat reader calls, rather than separate `extract`/`check`/`pictures` commands writing their own
files. One path into the store means one set of rules for validation and duplicates, and a source can be started in
chat and finished by API (or the reverse). Words the learner has are found locally before the paid steps, so they cost
nothing beyond extraction; near-duplicates go to the check as evidence and are still held at ingest for the learner
(the model doesn't get to decide "same word"). The budget covers the whole run, not each step; in batch mode each
step is one batch and re-running picks up from the cache. Output-size estimates come from the usage log per task.

**2026-11-23 · Chat mode: one result per unit, duplicates decided at ingest, sentences reach known cards.**
In chat the reader submits one result per unit (page, photo or transcript stretch): the unit's items, each already
checked and given a picture plan, rather than three separate submissions per step. The nine Peace Corps agents
worked this way and it halves the round trips; the prompts are still the packaged `extract`, `check` and
`pictures-plan`, read once per session. Results are schema-checked on submit (bounced with the errors) and wait in
`data/work/` until ingest, so a book can span many chats and nothing half-done reaches the store. Ingest, not the
reader, has the last word on duplicates: same letters and POS is the same word only when the transliterations'
consonants agree (ضحك d7ek ≠ ضحّك de77ek, which gets its shadda); anything close to an entry (spelling, wording, same
gloss) is held until the reader says `known_id` or `distinct`, instead of being merged or added silently. Known
words now get the source's sentences (skipping ones Panko wrote and ones that differ only in harakat), which the old
ingest dropped. Retired entries still count as "have it", so a rejected word doesn't come back. Paid steps stay
behind a dry run: `panko_sync()` shows notes and audio cost, `confirm=true` only after the learner agrees.

**2026-11-23 · No visible divider on card backs.**
Backs began with `<hr id="answer">`, which drew a line above the picture and made the card jump on flip (Anki scrolls
to `#answer` with `scrollIntoView()`). An empty anchor at the top still scrolled by the card's padding on backs
taller than the window, so backs have no `#answer` at all: Anki then shows the back from the top.

**2026-11-23 · More free picture sources before a paid drawing; no Unsplash.**
Two thirds of the Peace Corps picture plans were drawings, each one paid. The picture chain is now
source → Wikidata → Commons → Openverse → Pexels → Pixabay → generate. Wikidata goes first because a word's
Wikidata item usually has one well-chosen main image (P18) on Commons, which is precise for concrete nouns; it is
skipped for verbs ("to run" matched a brook). Pexels and Pixabay need free keys and both licences allow downloading
the file, which Anki media needs. Unsplash is left out: its API terms require hotlinking its servers, and an Anki
card can't. iNaturalist (animals, plants; only openly licensed photos) and ARASAAC (pictograms for actions) are
registered but off by default: ARASAAC is CC BY-NC-SA (personal use only) and its flat pictograms don't have the
hand-made look; try either for one run with `panko pictures search --providers inaturalist,arasaac`. Contact sheets
take candidates from each site in turn (10 per row, each tagged with its site) so the new sources show up next to
Commons. Every search answer is cached in `cache/images/` and each site is spaced politely; a site that rate-limits
for long is paused for the run (Pexels allows 200 searches an hour, so a big run fills over several passes, the
cache keeping what's done). Pixabay's image links expire after a day, so the chosen photo is looked up again before
download.

**2026-11-23 · Chat mode first: Panko runs inside the learner's own Claude.**
A third-party app can't bill a model call to someone's Claude subscription, so a Panko that only calls the API makes
every learner buy credits (~$30 a textbook). Instead Panko becomes an MCP server: the learner's Claude (Desktop,
claude.ai, Code) reads pages and judges, Panko serves the deterministic parts (pages, rendered prompts, evidence,
"already in your deck?", schema-checked submit, inbox, Anki sync). Same prompts and schemas as API mode, so results
match; API mode stays for unattended and batch runs. Spec: `docs/SPEC-mcp.md`.

**2026-11-23 · Opus stays the model for every step.**
A three-model test of the packaged prompts (about $0.80) found no step where a cheaper model is safe for the
learner. On checking, Haiku agreed with the earlier evidence-backed verdicts about as often as Opus (24 vs 27 of
50) but by saying `ok` to rows that had real errors, so a wrong word would reach a card unflagged; Sonnet agreed on
15, rewrote good rows and made some wrong corrections. On extraction both broke the house transliteration rules. For
examples and picture plans all three were usable, with a little Fusha creeping into the cheaper models' sentences.
The saving lever is batches (half price), not a smaller model. `[llm.tasks]` keeps the per-step override for anyone
who wants it, and the test should be re-run when evidence lookup lands (S3), since all three models judged from
memory here.

**2026-11-23 · Prompts ship with Panko; the learner's choices live in config.**
The briefs that agents followed in chat are now generic prompts in `src/panko/prompts/` (extract, deck, check,
examples, pictures-plan, pictures-pick), with shared parts (`_item`, `_verdict`, `_evidence`) and a strict JSON
schema each. Everything personal is filled in from `config/panko.toml`: `[learner]` (language, varieties, the
teacher's Arabizi style and the scholarly one, mainstream city standard, regions, topics, what to keep or drop,
picture rules) and `[evidence]` (which corpora and dictionaries the checker should trust and how to read them). A
test fails if a prompt file names a person, city, dictionary or picture rule, so another learner changes config,
not prompts. Prompts render the same for a whole run, so prompt caching makes the long instructions nearly free
after the first request. The packaged extract prompt writes the full item (glosses, grammar, an example per word),
so it costs about 6× more per page than a bare transcription: $0.17 for the densest Peace Corps page on Opus. On
that page Sonnet ($0.07) and Haiku ($0.005) read the words right but broke the house transliteration and article
rules, so extraction stays on Opus; cheaper models can be set per step in `[llm.tasks]` once an eval shows they hold up.

**2026-11-23 · How Panko spends on language models.**
Every LLM step goes through one runner (`panko.llm.run`). Before a run it counts input tokens on a sample and
prices the whole run; if the estimate is over the budget (`[llm] budget_usd`, $5 by default, `--budget` per run) it
stops before spending, and it stops mid-run if actual spend passes the budget. Successful answers are cached by
their exact input (prompt, file contents, schema, model), so re-running a command after a crash or a fix only pays
for what's missing, and big runs can go as half-price batches. Claude Opus 5.5 is the default (effort `medium`,
raised per task where it pays), with structured JSON output so answers always parse, and server-side refusal
fallbacks on. OpenAI sits behind the same interface for anyone who prefers it.

**2026-11-23 · Panko becomes a standalone package.**
Until now the thinking steps (extracting from PDFs and transcripts, checking glosses and region, writing example
sentences, resolving clashes, deciding pictures) were briefs in `data/` run by Claude agents in a chat session. You
want other learners to be able to do the same, so each of those steps becomes a `panko` command backed by an LLM
provider chain (Claude by default, swappable, per the no-lock-in rule), with the briefs turned into packaged prompts
and your personal choices moved into config. The human checkpoints stay: commands write the same reviewable JSON
files, and nothing reaches Anki without `ingest` / `activate` / `sync`. Peace Corps is the first source done this way.

**2026-11-23 · Phase 6: studied old-deck notes become Panko notes in place (`panko migrate`).**
Each old note you reviewed changes note type (official `anki` library, Anki closed) so every card keeps its id,
reviews and schedule. Old cards map by what they show first: Arabic → Recognition, English → Production. Panko then
fills the fields from the store, adds its tags to yours, moves the cards to `Panko Sandbox::Darija` and links the
note, so `panko sync` updates it from then on. Your old Front/Back stays verbatim in the hidden `Spare3`/`Spare4`
fields (including your own audio recordings), and sync never writes those two. A card you reviewed always keeps a
front, even on an entry that would otherwise be recognition-only; a never-reviewed old card for a card type that's
off is dropped. A note that held two words goes to the first; the second becomes a new note. Dry run by default; a
real run refuses while Anki is open and backs up the collection first. One full sync follows.

**2026-11-23 · The picture step is a command: `panko pictures export → search → apply`.**
It used to be agents plus scripts in a scratch folder. Now `export` lists cards without a picture, an agent decides
photo / drawing / skip per card (`PICTURE-BRIEF.md`) using `search` for Commons/Openverse contact sheets, and `apply`
downloads and credits the photos and draws the rest. Drawings can go through OpenAI's Batch API (`--batch`, collected
with `panko draw --collect`): half the price, no rate limit, results within 24 hours. Use it for big runs.

**2026-11-23 · No separate picture check; the hijab rule lives in the prompt.**
A vision check after each picture run (hijab, text, modesty) flagged mostly false positives: you looked at
every flagged picture and found them all fine. Once the hijab rule was in the house style, none of the ~1,400
drawings checked showed uncovered hair. So the check step is dropped: the style in `config/panko.toml` and the
prompt briefs carry the rules, and photos are chosen with them in mind.

**2026-11-23 · Drawings add a woman only when the scene needs one.**
Naming women in the house style ("every woman wears a hijab") nudged the model to put a woman in most pictures:
about two-thirds showed one, though a fifth of the prompts asked for one. The style now says: if a woman or girl
appears, she wears a hijab; don't add people the scene doesn't need. Prompts name exactly the people they want.
Applies from the next drawing run; existing pictures stay.

**2026-11-22 · Cards with no real picture get a generated drawing that helps you remember the word.**
Verbs, adjectives and abstract words rarely have a usable photo, so most of them had no picture. Now
`panko draw FILE` asks OpenAI's gpt-image-2 (low quality: in a test it looked as good as medium for these, at
about a ninth of the cost) for a hand-drawn ink-and-watercolour picture-dictionary drawing: one clear scene that shows
the exact sense ("to borrow": money moving towards the person), with no writing. Every woman and girl wears a
hijab and modest clothes (your wish, for religious reasons), and no clichés like fezzes. The house style lives in
`config/panko.toml`; per-word scene prompts are written by Claude (`data/sources/decks/DRAW-BRIEF.md`), and
words a picture wouldn't help (grammar particles, very abstract words) are skipped. Real pictures still come first,
and a generated one never replaces one. It's credited as "Illustration generated (model)" in Sources.

**2026-11-22 · Stage 2 of the old decks keeps only words common in DODa.**
Dave's Darija, Casablanca 1–2 and Darija hold ~5,400 headwords Panko doesn't have yet, many of them rare or
one-off sentences. Only rows with at least 10 hits in DODa's 86k-sentence corpus or a DODa word-list entry,
and at most six words long, go through extraction (1,763 rows), so effort and audio go to vocabulary you'll meet.
The rest stay in the deck exports and can be revisited.

**2026-11-22 · Long deck sentences become examples, never fronts.**
A long sentence makes a poor card (hard to recall whole from English) but is often the best example there is: real
Darija someone wrote down. So sentences longer than a short phrase, and sentences the extraction dropped as too long,
are checked for being natural and correctly translated, then attached as an example to a word they contain. They show
on that word's back and are read by both voices. Unnatural or unconfirmable ones are still dropped.

**2026-11-22 · Every example is read by both voices; one tap plays Badr, then Ghalia.**
With examples alternating, a card with one example only ever had the man's voice. Now the headword and every
example get both voices, and one ▶ tap plays them in turn. The template script plays the `<audio>` elements in a
button one after another (template edit, no full sync). It roughly doubles example TTS.

**2026-11-22 · Deck words get a dedicated region check.**
The first check of the old-deck rows looked at meaning and spelling; nearly everything came back pan-Moroccan by
default. A second pass (`data/sources/decks/REGION-BRIEF.md`) asks, per word, where in Morocco it's used
(north, Fes-Meknes, east, south, Hassaniya, rural), its register and the usual word, with evidence
(DODa, Routledge, Wiktionary's Moroccan entries, dialect papers, forums). Regional words get a `region::` tag and a
one-line note on the card back; cards already in Anki update in place.

**2026-11-22 · Old deck notes: extracted and checked in one pass, in stages; studied ones are never re-added.**
The six old Darija decks hold far more notes than were ever studied. Stage 1 is the notes you studied, the Peace Corps Darija
Dictionary and Most Used Moroccan (~1,080 rows). Rows are pre-matched against the store and DODa by script
(word lists and the 86k-sentence corpus), so the web is only needed for unattested items. Because the deck is
the least trusted source, extraction and checking happen together (`data/sources/decks/DECK-BRIEF.md`).
Each entry keeps `origin` (deck, note id, studied). `activate` skips entries from studied notes: Phase 6
converts those old notes in place so their review history survives, instead of adding a second note.
Stage 2 (Dave's Darija, Casablanca 1–2, Darija: ~8,900 rows) waits for your go-ahead.

**2026-11-22 · Your existing Darija cards are a source like any other, and get checked.**
Shared-deck cards are unverified, so they go through extraction and the same check (Routledge, DODa, web) before
anything becomes a Panko card. Studied notes keep their history through the Phase 6 migration; unstudied ones are
mined and later retired.

**2026-11-22 · Homographs are allowed in Anki; PankoID identifies a note.**
Anki rejects a note whose first field repeats another's ("duplicate"). Darija has real homographs (دار "house",
دار/يدير "to do", دار/يدور "to turn"), so sync adds notes with duplicates allowed and finds them by `PankoID`.

**2026-11-22 · Every ingested item is checked before it becomes a card; the checks are kept.**
You weren't sure some of the teacher's words were authentic or used everywhere. Each item is checked against
Routledge's *Introductory Course in Moroccan Arabic*, DODa (Darija Open Dataset, incl. its sentence corpus),
Wiktionary and the web, and gets a verdict (ok, fix, regional, uncommon, doubtful, drop) with evidence.
`panko ingest --verdicts` applies them: fixes replace fields, a short usage note goes on the card back ("the
everyday word is ساروت sarut"), unconfirmed items get `panko::doubtful`. The verdict is stored on the entry.
Hand-made `--overrides` win over verdicts. Keys are bare Arabic + part of speech, so two same-POS homographs from different sources (دار/يدور "to turn", دار/يدير "to do") collide in one key; split those by hand.

**2026-11-22 · In a set of synonyms, only the everyday word gets a production card.**
"Window" can't have two right answers on the English front. The everyday word (شرجم, ساروت, نعس, بيت…) gets both
cards; the others (شباك, مفتاح, رقد, غرفة…) get the recognition card only, so you still understand them.

**2026-11-22 · Homographs with different parts of speech are separate entries.**
دار "house" and دار "to do" no longer merge: the store matches on bare Arabic *and* part of speech.

**2026-11-22 · Words and phrases are told apart by tag, not deck. Everything sits under `Panko Sandbox` for now.**
Decks are a scheduling choice; tags are free and filterable. Decks: `Panko Sandbox::Darija` and
`Panko Sandbox::Fusha`, tags `kind::word` / `kind::phrase`. Supersedes the Words/Phrases decks.

**2026-11-22 · The Panko store (SQLite, `data/panko.db`) is the source of truth; Anki notes are rendered from it.**
Each entry is a JSON record keyed by a stable ID (`dw-00001`); the note's `PankoID` matches it. Sync renders the
note, compares a hash, and updates changed notes in place, so review history survives any design change. Sources and
sightings (who said what, where) are stored apart from entries, which is how a later source adds an example to a
word you already have instead of making a duplicate. Duplicates are matched on bare Arabic (no harakat, unified alef,
article stripped).

**2026-11-22 · Ingested words land in an inbox and go to Anki in small batches.**
`panko ingest` adds new items as candidates; `panko activate` promotes them. This keeps each day's new cards to a
handful and leaves room to fix pictures before cards appear. Everything ingested is tagged `panko::needs-review`
until checked.

**2026-11-22 · Until there is an Anthropic API key, Claude writes the extraction file in chat.**
The ingest step reads a JSON file (source + items) either way, so automating it later changes nothing downstream.

**2026-11-23 · Fusha words get the same two cards as Darija: Arabic + audio, and picture + English.**
The plural, verb-form and root cards repeated the same word several times a day, so they're off. The picture, grammar line
(plural, present · imperative · masdar, root) and examples are on the back. The extra templates stay
unused; removing them would force a full sync.

**2026-11-23 · Darija voices: Badr and Ghalia (ElevenLabs v3).**
Out of a six-voice audition, both were understood as Darija by speech-to-text, and only Badr was heard as كنابي exactly.
(Updated 2026-11-22: every example is now read by both too; see the newer entry.) The headword is read by both (man, then woman), and examples alternate between them, so you hear
two speakers without doubling the cost. Fusha keeps the built-in George for now. Voices are listed by name in
`config/panko.toml`; `uv run panko voices` re-runs the audition.

**2026-11-23 · Recognition front = Arabic + audio; no separate Listening card.**
You asked for hearing and reading together. `EnableListening` stays unused (the template is kept,
because removing it would force a full sync). On the back, the word plays again.

**2026-11-23 · Anki's page direction is pinned to LTR in CSS.**
Anki picks the direction from the first letter on the card. Once the badge was gone, the back
started with Arabic, so the English turned RTL (full stops at the start, Sources arrow flipped).
Only `.ar` elements are RTL now.

**2026-11-23 · Production fronts show the picture + English; no separate picture-only card.**
A picture alone was ambiguous. `EnablePicture` stays unused (the template is kept, because removing it would force a full sync).

**2026-11-23 · Words and phrases go in separate subdecks: `<Variety>::Words` and `<Variety>::Phrases`.**
Each gets its own daily limits, and slower phrase reviews don't crowd out vocabulary. There are also
`kind::word` and `kind::phrase` tags for searching. The Anki MCP add-on allows only two deck levels, so
the sandbox decks are `Panko Darija::Words` and the like.

**2026-11-23 · Scripture is cited under the example, and never voiced by TTS.**
"Quran 16:75 (An-Nahl)" shows under the verse. This is content, not provenance. Audio for verses
will come from real recitation.

**2026-11-23 · (Superseded by Badr + Ghalia.) Interim Darija voice: ElevenLabs v3, built-in voice "George".**
Free ElevenLabs accounts can't use library voices (Badr, Ghalia… the Moroccan ones) or voice
design through the API. George round-tripped through ElevenLabs speech-to-text almost word for
word, so he reads it as Darija rather than MSA, but the accent isn't Moroccan. Switch by
changing `voice_darija` once on a paid plan.

**2026-11-22 · Example audio is tap-to-play mp3, word audio is a `[sound:]` tag.**
Anki autoplays every `[sound:]` tag on a side, so examples can't use them. A small
template script plays an `<audio>` element on tap. It must be mp3: desktop Anki's web
view can't decode AAC/m4a (this is why the v0.1 button did nothing).

**2026-11-22 · Cards carry no provenance, badges or hints in the body.**
Your feedback on v0.1: a card from a lesson must look like any other card. Sources and
audio/picture credits go only in the collapsed Sources section. The variety (Darija,
Fusha) comes from the deck, so no badge. Production fronts show only the English.

**2026-11-22 · Every external capability sits behind a provider chain.**
Audio, pictures, image generation, LLM and speech-to-text each have a named chain in
`config/panko.toml`, tried in order. This avoids vendor lock-in: use the best tool for each
job and swap it when something better appears. Real sources always come before synthetic
ones (native audio before TTS; a found photo before a generated one).

**2026-11-22 · No fallback to a voice that speaks the wrong variety.**
The macOS MSA voice reading Darija was "very wrong". Darija cards stay silent (no Listening
card) until a proper voice or a teacher clip exists.

**2026-11-22 · Teacher-said words not already in Panko become cards; teacher audio becomes example audio.**
No separate "you said it" or "correction" cards.

**2026-11-21 · Standalone app writing into real Anki, not a clone or fork.**
AnkiMobile is closed source, so fork-only features would never reach the phone. Two access
paths: the Anki MCP Server add-on while Anki is open, and the `anki` pylib with Anki closed
for schema changes (Change Note Type migrations).

**2026-11-21 · Build fresh note types; migrate only studied notes.**
Unstudied shared-deck notes are mined as source material, not converted. The AR • deck is
dropped; its audio will be re-pulled from the original Peace Corps source.
