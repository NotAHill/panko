# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first. Personal details (names, collection numbers, paid plans) go in
`data/STATUS.md` (git-ignored), not here: this repo is public.

## Now (2026-11-26)
- **Built:** the Panko store (SQLite) with in-place sync to Anki; provider chains for audio (ElevenLabs), pictures
  (real photos from Wikidata, Commons, Openverse, Pexels and Pixabay first; generated drawings otherwise) and the
  language model (Claude by default); migration of studied old-deck notes with their history (`panko migrate`).
- **Standalone track S1–S6 done:** the language-model layer, generic prompts, chat mode (`panko mcp`), API mode
  (`panko work run`), settings for any learner (`panko init`, `panko refs`), and packaging (AGPL-3.0-or-later,
  README quickstart, fake-Anki sync tests).
- **Sources run so far:** lessons and teacher sheets, the learner's old shared Darija decks (checked, with a region
  pass), and the public-domain Peace Corps *Moroccan Arabic* textbook (run through Panko's own prompts).
- **S7 done (2026-11-23): the commands reproduce the chat agents.** Old Anki decks are now a source like any other:
  `panko work add --deck NAME` exports one read-only (studied notes marked), it splits into 25-row units, and API
  mode runs the `deck` prompt on them (rows you already have are known for free); chat mode follows the same prompt.
  A teacher sheet (2 pages) and 25 deck rows were run through API mode and compared with the agents' results. First
  run: the deck matched closely, but the sheet gave 31 items to the agents' 55, because words inside dialogue lines
  weren't items of their own. Prompt fixes: new content words in a phrase or example become items too; a verb with a
  fixed preposition keeps it in the headword (تخلص من); no shadda in Darija headwords; a second sense after a
  semicolon; a deck row that was corrected is `fix`, not `ok`; the check is told the source, and a teaching source's
  word is never `doubtful` on memory alone (the usual word goes in `usual_word` instead). After the fixes: sheet 51 of
  the agents' 55 headwords plus useful extras (half, litre, how much, shop), deck 23 of 23; remaining differences are
  gloss punctuation and romanisation detail, and a few evidence-backed fixes the agents missed. Cost $2.21 in all.
- **CI fix (2026-11-23):** picture conversion uses Pillow instead of macOS-only `sips`; Pillow is a core
  dependency.
- **Doubtful items stay out of Anki** until cleared: `activate --batch` skips `panko::doubtful`; naming one by id
  clears it. Cards for a variety in `[learner.translit] none_for` (Fusha) show no transliteration.
- **S8 built (2026-11-23): no step needs a hand-written brief any more.** `panko pictures decide` chooses a picture
  per card (saved plan or the `pictures-plan` prompt → photo search on the free sites, reusing earlier search
  folders → the `pictures-pick` prompt looks at each contact sheet; about $0.004 a card on Opus), writing decisions
  that `panko pictures apply` reads. `panko examples` gives words without one a sentence from the learner's sources
  or the corpora (or writes one). `panko clashes` finds production cards whose glosses share a sense and decides:
  sharpen, recognition-only or drop (a card already in Anki is never removed, only made recognition-only, and
  listed for the learner). Chat mode has all of it as tools (`panko_pictures_todo`, `panko_photo_search`,
  `panko_pictures_save`, `panko_pictures_apply`, `panko_clashes`, `panko_clashes_apply`, `panko_audio` to hear a
  card before syncing), and `panko mcp --skill DIR` writes the workflow as a Claude skill. Tested with a fake model.
- **Focus: the product (your call, 2026-11-25).** Work on Panko itself comes first; moving your own cards (Peace
  Corps pictures, activation and sync, the Fusha round of Phase 6) is paused and tracked in `data/STATUS.md`.
- **Phase 4 built (2026-11-25): recordings are sources.** `panko work add lesson.m4a [--track call.m4a] --speakers
  teacher,me --learner me` registers a recording; `panko work transcribe SOURCE [--estimate]` runs speech-to-text
  (the new `[stt]` chain, ElevenLabs Scribe first; paid) or `--transcript FILE` uses one you have. Word times give
  three-minute units read like pages (`[m:ss] speaker: …`, chat tool `panko_transcribe`). At ingest each item the
  recording says, and each of its sentences from it, gets a clip of the real speaker (ffmpeg, `data/media`), which
  the card plays instead of a synthetic voice; never the learner's voice. Tried free on a Peace Corps track with its
  existing transcript: six clips cut and found by the audio chain. Not yet: a real lesson end to end, guiding
  speech-to-text with the sheet, a second engine to compare.
- **Phase 5 built (2026-11-25): checks by tools, not judgement.** `panko verify [ids] [--status] [--apply]` (chat
  tool `panko_verify`) checks Standard Arabic entries against a morphological analyser (the new `[morph]` chain,
  CAMeL Tools first): headword, plural, present, imperative, masdar and every word of a written example must be one
  of the analyser's readings (same letters, harakat a subset), the card's root one of theirs, the part of speech
  fitting. Spelling, harakat or root problems hold a candidate as `panko::doubtful`; the rest is listed. New items
  are checked at ingest, and the analyser's readings are evidence for the check prompt. Dialect words are never
  checked with a Standard Arabic analyser: the ones no reference lists are listed for your teacher. Reference look-ups are indexed once, so a full run takes seconds.
  Run for real with CAMeL Tools 1.6 (`calima-msa-r13`, in its own environment on another disk): its output showed
  more spelling conventions (case ending left off, dagger alif for fatha, no shadda on a sun letter after the
  article), now evened out, and it knows few imperatives, so imperatives are judged only by the ones it has.
- **S9 built (2026-11-25): any language.** The language is config, not code: `[learner] script` (Unicode script
  names) drives the submit check, card fonts and direction, and reference columns; matching keys work for any script
  (case, articles, optional accent folding) and the Arabic rules sit in `panko.lang.arabic`, touching Arabic letters
  only (every stored key unchanged). The Darija wording left the prompts for `[learner]` / `[learner.examples]`; a
  test keeps prompt files language-free. `panko init --language spanish` (or `moroccan-darija`) fills script, prompt
  wording, references, speech-to-text language and voice audition from a preset; Spanish is tested end to end
  (source → submit without romanisation → ingest → Latin-script card). The card class rename means the next sync
  updates every note's HTML once (normal sync).
- **S10 step 1 built (2026-11-26): the local hub.** Your call on scope: all three (local dashboard first, made
  very good; then a shareable deck library; then a private hosted service). `panko hub` serves a dashboard on
  127.0.0.1: a terminal in glass (monospace, blue with the logo's green and crust, a slow aurora with grain, a
  command palette on `/`, permission-prompt dialogs for paid steps): overview, sources (upload or path or Anki deck; units grid; read with the model;
  ingest; held items to decide), the inbox and every card (search, flags, keyboard triage, bulk activate/reject,
  editing, a preview of each card as Anki shows it, look-ups), tool checks and gloss clashes, pictures, the sync
  plan and sync, spend, job logs, and setup (readiness, references, config, chat-mode snippet, a first-run wizard).
  The same modules as the commands sit behind it; long or paid steps are background jobs with their own log; paid
  ones always estimate first and run only when confirmed, with a budget. Tested with a scratch store and checked in
  the browser on the real one (nothing paid, nothing synced).
- **Hub round 2 built (2026-11-26).** Card design (section order and visibility, your own sections in the spare
  fields, fronts, default card types, sizes, font, your CSS, with a live preview; templates and CSS only, so a normal
  sync), picture choices (photo sources and order, drawings on or off, style and rules; per card: photo, drawing or
  none, and what it should show), a voice picker (ElevenLabs library by language, accent and man or woman, with
  samples, up to four per variety), a walkthrough of the interface, a tag filter, references looked up as soon as a
  card opens, each source listed once per card, a click on the preview flips it. Choices go in `config/hub.toml`.
  `panko examples` now covers short phrases too (most phrase cards have no example yet: run it with `--estimate`).
  The card HTML lost its "·" separators, so the next sync updates every note in place once (normal sync).
- **Hub round 3 (2026-11-26).** Voices as a list per variety; the sources page lists the sources from before the
  queue (and filters cards by source); "no picture" per card or per tag; retired cards say why, with duplicates
  linked both ways; a ? on each box says what it is for; the check box in plain words; the full logo in the header.
  Tested as a first-time user against an empty folder (setup, empty overview, first source): fixed pages that failed
  before setup, a slow page painting over the next one, setup defaults, and same-title sources replacing each other.
  Retired is now two tabs, duplicates and rejected; rejected words no longer come back to the inbox. Cards can be
  shared as an .apkg (`panko export`, or "share as a file" on the sync page). Gloss clashes are settled card by
  card in the hub, with the model as an optional suggester. The status bar shows chat mode or API mode.
- **S10 step 2 planned (2026-11-26): the deck library.** Spec: `docs/SPEC-library.md`. Each deck is a Panko pack
  plus an .apkg built from it. The library is a separate public GitHub repo, with an index and the files on
  releases. Only you publish for now. Learners use a library page in the hub or `panko library`. Importing a pack
  is ingest, so duplicates, holds and rejected words work as for any source. The first deck is the Peace Corps words
  (public domain).
- **Next:** L1 of the library (the pack format, `panko pack build`, `panko library import`, round-trip tests), then
  L2–L4 as the spec lays out, then step 3 (a private hosted service).
- The learner's own state (deck sizes, what's waiting on whom, plans) is in `data/STATUS.md` (git-ignored).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); OpenAI image generation working (`panko draw`); Azure untested (no key) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stages 1–2 in Anki (checked + region pass) |
| 4 | Lessons and recordings as sources: speech-to-text, timed units, native clips | built 2026-11-25 (Scribe, units, clips at ingest); still to do: a real lesson end to end, speech-to-text guided by the sheet, a second engine to compare. Recording your own lessons needs your teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | built 2026-11-25: `panko verify`, `[morph]` chain (CAMeL Tools, in its own environment), checks at ingest, readings as evidence, ungrounded dialect words listed; run with real CAMeL Tools 2026-11-25. Later: CATT as a second vote on harakat, roots from Qabas/kaikki, conjugation tables generated |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) | Darija: done (studied notes converted, history kept). Second round (Fusha decks, Serious Explorer) after other languages are supported: one Fusha deck, production cards on, no transliteration; Serious Explorer's pictures and word recordings are kept, example sentences and their audio generated |
| 7 | Chat interface: Panko's own MCP server | built as Standalone S3 (`panko mcp`); spec in `docs/SPEC-mcp.md` |

## Standalone track (from 2026-11-23)
Goal: someone else learning a language this way installs Panko, points it at their sources and Anki, and gets the
same checked cards, without a Claude Code session doing the thinking. Today the LLM steps (extract, check, region,
sentences, clashes, picture decisions) are briefs in `data/` (git-ignored) run by Claude agents in chat.

| # | Step | What "done" means |
|---|---|---|
| S1 ✅ | **LLM provider chain** (built and live-tested 2026-11-23) | `providers/llm/`: Claude by default (Anthropic SDK), OpenAI as an alternative, same interface. Structured JSON output checked against a schema, retries, prompt caching, the Batch API for big runs (half price). Every paid run prints a cost estimate first and honours a budget cap. |
| S2 ✅ | **Prompts in the package** (built 2026-11-23) | The briefs move to `src/panko/prompts/` as generic prompts. Personal choices move to config: teacher and their Arabizi style, region, transliteration order, picture rules (hijab, no fez), what to skip. |
| S3 ✅ | **Chat mode: Panko as an MCP server** (decided 2026-11-23) | A learner with a Claude subscription runs the pipeline with no API credits: their Claude reads pages and judges, Panko serves tools (pages, rendered prompts, evidence, schema-checked submit, inbox, sync) plus a skill with the workflow. Same prompts and schemas as API mode. Spec: `docs/SPEC-mcp.md`. Built 2026-11-23 (`panko mcp`); the planned done-test (rest of Peace Corps) was moot since chat agents finished the book, so it was tried on a done page instead. Still to add: pictures/audio tools and a skill file. |
| S4 ✅ | **A command per step** (API mode, for unattended runs; built 2026-11-23 as `panko work run` over the S3 units: one pipeline instead of separate commands, deck rows and `examples` not yet wired) | `panko extract` (PDF pages via vision, text, transcripts, deck rows), `panko check` (verify + region, with evidence), `panko examples`, `panko dedupe` (clashes), `panko pictures decide`. Parallel, resumable, cached per item; they write the JSON that `ingest` / `pictures apply` already read, so the human review points stay. |
| S5 ✅ | **Evidence and settings for anyone** (built 2026-11-23: `panko init`, `panko refs`, `[anki]` decks/profile/card map) | `panko init` writes the config: Anki profile, deck names, varieties, voices, keys. Nothing hard-coded (profile "User 1", "Panko Sandbox", the old-deck card map: detect which side shows Arabic from the templates, with an override file). Open evidence downloads itself (DODa); private dictionaries are a path in config. |
| S6 ✅ | **Packaging and docs** (built 2026-11-23; AGPL-3.0-or-later; publishing is your call) | README quickstart for a new learner, licence, a worked example on a free source (Peace Corps), tests with a fake Anki and fake LLM. Publish when you decide. |
| S7 ✅ | **Check it matches** (done 2026-11-23 on a teacher sheet and 25 deck rows; the Fusha round waits for your call) | Re-run one teacher sheet and one old-deck batch through the commands and compare with what the agents produced. Fix the prompts until they agree. Then the Fusha round (Phase 6, second round) runs on the commands too. |

| S8 ✅ | **The steps still done by agents** (built 2026-11-23) | Picture choice from the contact sheets as a command (`pictures-pick` prompt, API) and as chat tools; example sentences (`examples` prompt) and gloss clashes as commands; an audio tool and a packaged skill file for chat mode. Then the Peace Corps pictures run on the chat-mode picture step. |
| S9 ✅ | **Any language** (built 2026-11-25) | Nothing Arabic-specific left in code or prompts: script detection, romanisation rules, references and voices come from config; a worked setup for a second language. Built as `panko.lang` + language presets (Moroccan Darija, Spanish); Arabic rules kept in one module; Spanish tested end to end. Not yet: a real Spanish source run with the model, presets for more languages, a morphological analyser for a second language. |
| S10 | **Panko hub** (step 1 built 2026-11-26; step 2 planned, `docs/SPEC-library.md`) | A web dashboard or app: search pre-built language decks, or configure your own (language, varieties, sources, card types) and have Panko build it; the same pipeline behind it. Three steps (your call, 2026-11-26): (1) a local dashboard, `panko hub`, built; (2) a shareable deck library; (3) a hosted web service, private at first. |

Order (your call, 2026-11-23; product first from 2026-11-25): Phase 4 (lessons and recordings, built), Phase 5
(verification, built), S9 (any language, built), S10. Card migration (Peace Corps pictures and sync, the Fusha round of Phase 6) waits until
you pick it up again. Settled: AGPL-3.0-or-later, published on GitHub; Opus for every step, batches
for big runs; one Fusha deck, production cards on by default for every language, no transliteration on Fusha cards.

## Open questions
- (none open)
