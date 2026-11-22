# Decisions

Newest first. One paragraph each: what, and why. Reverse one by adding a new entry.

**2026-11-22 · Every ingested item is checked before it becomes a card; the checks are kept.**
You weren't sure some of the teacher's words were authentic or used everywhere. Each item is checked against
Routledge's *Introductory Course in Moroccan Arabic*, DODa (Darija Open Dataset, incl. its sentence corpus),
Wiktionary and the web, and gets a verdict (ok, fix, regional, uncommon, doubtful, drop) with evidence.
`panko ingest --verdicts` applies them: fixes replace fields, a short usage note goes on the card back ("the
everyday word is ساروت sarut"), unconfirmed items get `panko::doubtful`. The verdict is stored on the entry.
Hand-made `--overrides` win over verdicts (a checker once confused دار/يدير "to do" with دار/يدور "to turn").

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
The headword is read by both (man, then woman), and examples alternate between them, so you hear
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
