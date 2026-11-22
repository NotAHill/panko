# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22, evening)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`). The empty decks `Panko Darija::Words`, `Panko Darija::Phrases`, `Panko Fusha::Words` can be deleted by hand.
- In Anki: 9 sandbox entries, batch 1 (12 furniture nouns) and batch 2 (44 house & rooms entries: nouns, adjectives, phrases; 83 cards) and batch 3 (74 shopping / corner-shop / souk entries, 147 cards), batch 4 (51 emotions & character entries, 100 cards; the 4 doubtful idioms held back). Photos for concrete nouns and item phrases (`data/media/`); دار "house" still has no picture.
- **Inbox: 247 candidates** (294 words, 125 phrases): 49 from the 21 Nov lesson, 370 from six teacher PDFs and Oussama's notes (`data/sources/teacher/`). Every item was checked against Routledge's *Introductory Course in Moroccan Arabic*, DODa and the web (`verify-out-*.json`); fixes applied, 14 non-everyday synonyms get the recognition card only, 4 unconfirmed idioms tagged `panko::doubtful`. Findings for the learner: `data/sources/teacher/CHECK-REPORT.md`.
- Waiting on: the learner asking Oussama about the doubtful items (tsuffet, mkachkach, mberred s-soug, tiyyer liya l-ferkh, damani l-7al, kanachha); an image-gen key; an `ANTHROPIC_API_KEY` to automate extraction.
- Next: batch 5 (daily verbs), then food, grammar words, numbers/time; pictures per batch. Add `activate --topic`.

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps | lesson + 6 teacher PDFs + notes ingested (extraction by Claude in chat) |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
