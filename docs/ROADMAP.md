# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22, evening)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`). The empty decks `Panko Darija::Words`, `Panko Darija::Phrases`, `Panko Fusha::Words` can be deleted by hand.
- **In Anki: 585 Panko notes** (deck batches 10–13, everyday verbs, added 2026-11-22) in `Panko Sandbox::Darija` / `::Fusha`: the 9 sandbox entries plus batches 1–9 (furniture, house, shopping, emotions, verbs, food, grammar & position, greetings/numbers/time, people/places/family). Everything from the 21 Nov lesson, six teacher PDFs and Oussama's notes is in. Photos for concrete words and item phrases (`data/media/`), small diagrams for position words; دار "house" and abstract words have no picture. ف has no headword audio (TTS returns nothing for one letter).
- **Inbox: 650 candidates.** 4 unconfirmed idioms from the teacher material, plus **stage 1 of your old Darija decks**: notes you studied in any deck, the Peace Corps Darija Dictionary and Most Used Moroccan (1,080 rows → 800 new entries, 142 dropped, the rest already in Panko and recorded as sightings). Each row was extracted and checked in one pass (`data/sources/decks/DECK-BRIEF.md`; DODa pre-matched by script, Routledge, Wiktionary, web): 655 ok, 120 corrected (wrong glosses, imperatives as headwords, typos), 32 uncommon/bookish, 1 regional, 22 doubtful. Report: `data/sources/decks/CHECK-REPORT.md`.
  - Unstudied, non-doubtful items sit in **batches 10–31** (10–13 done) (themed, 17–48 each: verbs ×5, home, people, emotions, work, time, food, cooking, school, health, grammar, greetings, body, travel, money, mixed ×3). `panko activate --batch N` then `panko sync`.
  - **98 entries come from notes you studied**: `activate` skips them (entry `origin.studied`); Phase 6 converts those old notes in place so history survives.
  - Most examples on deck items are "written by Panko, not yet checked"; DODa corpus sentences were often mistranslated, so few were used.
  - Homographs that differ only by shadda (وصل/وصّل, خرج/خرّج, صلح/صلّح, نقص/نقّص, سال ×2) are kept apart with the item flag `homograph`.
- Waiting on: the learner asking Oussama about the doubtful items (tsuffet, mkachkach, mberred s-soug, tiyyer liya l-ferkh, damani l-7al, kanachha); an image-gen key; an `ANTHROPIC_API_KEY` to automate extraction.
- Next: activate deck batches 14–31 a few at a time (pictures for concrete nouns first). **Stage 2** of the old decks (Dave's Darija, Casablanca 1–2, Darija: ~8,900 rows, ~7,000 distinct) needs your go-ahead: same pipeline, roughly 10× stage 1's cost.
- After that: ask Oussama about the doubtful items; picture gaps once an image-gen key exists; Phase 6 migration of studied notes.

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stage 1 ingested (checked); stage 2 pending |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
