# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-23)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko draw FILE [--force]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`).
- **In Anki: 2,685 Panko notes** (incl. the 94 converted old notes): sandbox entries, lesson + teacher batches 1–9, old-deck stage 1 (batches 10–31) and **stage 2 (batches 32–75: Dave's Darija, Casablanca 1–2, Darija)**. Every headword and example is read by Badr and Ghalia (one ▶ tap plays both). ElevenLabs: **Creator plan** (141k characters/month), 36k used this period.
- **Pictures: 528 real photos/diagrams, 1,828 generated drawings, 231 none** (grammar words, numbers above 10, sensitive words). Drawings: `panko draw`, gpt-image-2 low, hand-drawn ink + watercolour, women in hijab and only when the scene needs one, no fez, no text. For new cards an agent decides photo / drawing / skip per card (`data/sources/decks/PICTURE-BRIEF.md`): photos from Commons/Openverse contact sheets first, drawings otherwise. No separate picture check (dropped: false positives).
- **Stage 2 checks**: filtered to rows common in DODa (1,763 rows) → extracted + checked + region in one pass → 1,541 items → duplicates merged, gloss clashes resolved (192 sharpened, 24 recognition-only, 27 retired). Long deck sentences became 110 checked examples (`SENTENCE-BRIEF.md`), plus 15 everyday words/formulas they revealed. Report: `data/sources/decks/CHECK-REPORT.md`.
- **Inbox: 27** doubtful items (`panko::doubtful`).
- Waiting on: the learner asking Oussama about doubtful/low-confidence items (both CHECK-REPORTs); غتاصب keep/drop.
- Picture step is a command: `panko pictures export → search → apply [--batch]` (drawings by OpenAI batch at half price, `panko draw --collect`). Batch path confirmed end to end (dp-00194, dp-00195).
- **Phase 6 (Darija) converted 2026-11-23**: the 94 studied old-deck notes are now Panko notes in `Panko Sandbox::Darija` (`panko migrate`): all 408 reviews kept, 152 of 153 old cards kept (the one dropped, مومو's English→Arabic card, was never reviewed), 34 new cards where a card type was missing. Backups on the SSD (`panko-scratch/collection-before-phase6-*.anki2`). Full upload done; the 4 second words (ربح, تخلص من, دى, قبل 'to accept') added as new notes. The AR • deck stays as it is for now (your call, 2026-11-23).
- Next after Phase 6: the studied Fusha decks (ABY, iExplore, Serious Explorer: not yet extracted); more sources (Peace Corps book + audio).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); OpenAI image generation working (`panko draw`); Azure untested (no key) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stages 1–2 in Anki (checked + region pass; 2,587 notes) |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) | Darija: done (94 notes, history kept); Fusha decks later |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
