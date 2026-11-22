# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22, evening)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`). The empty decks `Panko Darija::Words`, `Panko Darija::Phrases`, `Panko Fusha::Words` can be deleted by hand.
- **In Anki: 432 Panko notes** in `Panko Sandbox::Darija` / `::Fusha`: the 9 sandbox entries plus batches 1–9 (furniture, house, shopping, emotions, verbs, food, grammar & position, greetings/numbers/time, people/places/family). Everything from the 21 Nov lesson, six teacher PDFs and Oussama's notes is in. Photos for concrete words and item phrases (`data/media/`), small diagrams for position words; دار "house" and abstract words have no picture. ف has no headword audio (TTS returns nothing for one letter).
- **Inbox: 4 candidates**, the unconfirmed idioms (`panko::doubtful`). All ingested items were checked against Routledge's *Introductory Course in Moroccan Arabic*, DODa and the web (`data/sources/teacher/verify-out-*.json`); 14 non-everyday synonyms have the recognition card only. Findings for the learner: `data/sources/teacher/CHECK-REPORT.md`.
- Waiting on: the learner asking Oussama about the doubtful items (tsuffet, mkachkach, mberred s-soug, tiyyer liya l-ferkh, damani l-7al, kanachha); an image-gen key; an `ANTHROPIC_API_KEY` to automate extraction.
- Next: **ingest your other Darija cards** (the shared Darija decks, ~110 notes, and any Darija in other decks) as a source, and check every item the same way as the teacher material (Routledge, DODa, web), because shared-deck content is unverified. Read-only via MCP → extraction JSON → `panko ingest --verdicts`. Items Panko already has just gain a sighting. Notes you've *studied* are kept for Phase 6 (Change Note Type, history kept); unstudied ones become candidates and the old note is retired later.
- After that: ask Oussama about the 4 doubtful idioms; picture gaps (دار, abstract words) once an image-gen key exists.

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks next (with checks) |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
