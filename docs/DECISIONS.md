# Decisions

Newest first. One paragraph each: what, and why. Reverse one by adding a new entry.

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
button one after another (template edit, no full sync). It roughly doubles example TTS: about 29,000 of the
40,000 monthly ElevenLabs characters for all cards up to batch 31.

**2026-11-22 · Deck words get a dedicated region check.**
The first check of the old-deck rows looked at meaning and spelling; nearly everything came back pan-Moroccan by
default. A second pass (`data/sources/decks/REGION-BRIEF.md`) asks, per word, where in Morocco it's used
(north, Fes-Meknes, east, south, Hassaniya, rural), its register and the usual word, with evidence
(DODa, Routledge, Wiktionary's Moroccan entries, dialect papers, forums). Regional words get a `region::` tag and a
one-line note on the card back; cards already in Anki update in place.

**2026-11-22 · Old deck notes: extracted and checked in one pass, in stages; studied ones are never re-added.**
The six old Darija decks hold ~9,900 notes, not ~110. Stage 1 is the notes you studied, the Peace Corps Darija
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

**2026-11-23 · Darija voices: Badr and Ghalia (ElevenLabs v3, Starter plan).**
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
