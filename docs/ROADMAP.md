# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22, late)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko draw FILE [--force]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`).
- **In Anki: 1,115 Panko notes** (sandbox entries, lesson + teacher batches 1–9, old-deck stage 1 batches 10–31). Every headword and example is read by Badr and Ghalia; one ▶ tap plays both. ElevenLabs: 19.8k / 40k characters used this month (resets ~22 Dec).
- **Generated pictures** (`panko draw`, gpt-image-2 low): every active card without a real picture gets a hand-drawn ink + watercolour drawing that shows the exact sense; skipped where a picture wouldn't help (grammar words, numbers above 10, very abstract or sensitive words). Women always in hijab, no fez clichés, no text. Scene prompts: `data/sources/decks/DRAW-BRIEF.md`, `work/draw-go*.json`. The first run used a stale style (settings() is cached per process), so all 767 are being redrawn; then a hijab/text check of every picture, then `panko sync`.
- **Old-deck stage 2 in the inbox** (Dave's Darija, Casablanca 1–2, Darija): filtered to rows common in DODa (1,763 rows) → extracted + checked + region in one pass (`STAGE2-BRIEF.md`) → 1,541 items, 250 dropped → 42 cross-chunk duplicates merged, gloss clashes resolved (192 sharpened, 24 recognition-only, 27 duplicates retired) → **1,472 candidates in batches 32–75** (ordered by DODa frequency) + 9 doubtful. Long deck sentences became **110 checked examples** on existing words (`SENTENCE-BRIEF.md`), plus 15 everyday words/formulas they revealed (عطش, جوع, برد, صهد, موعد, عمر, الله يرحمو, البركة ف راسك, رمضان مبارك…).
- **Inbox: ~1,600**: stage 2 (batches 32–75), 98 entries from studied notes (Phase 6), doubtful items.
- **Blocker for activating stage 2: audio.** Both voices for all stage-2 words + examples ≈ 77k ElevenLabs characters; ~20k are left this month on Starter (40k/month). Either a bigger plan (Creator: 100k/month) or ~4 batches a month.
- Stage-2 pictures: real photos for concrete nouns first (Commons/Openverse contact sheets), generated drawings for the rest, per batch before activation.
- Waiting on: the learner asking Oussama about doubtful/low-confidence items (both CHECK-REPORTs); غتاصب keep/drop.
- Next: hijab/text check + sync of the redrawn pictures; then activate stage-2 batches as audio allows; Phase 6 (migrate the 98 studied notes with history).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); OpenAI image generation working (`panko draw`); Azure untested (no key) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stage 1 in Anki (checked + region pass); stage 2 checked and in the inbox (batches 32–75) |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
