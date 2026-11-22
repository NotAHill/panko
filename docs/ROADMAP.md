# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22, evening)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place. Commands: `panko seed`, `panko ingest PATH [--verdicts F...] [--overrides F]`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko sync`.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`; words vs phrases is a tag (`kind::word` / `kind::phrase`). The empty decks `Panko Darija::Words`, `Panko Darija::Phrases`, `Panko Fusha::Words` can be deleted by hand.
- **In Anki: 1,115 Panko notes** in `Panko Sandbox::Darija` / `::Fusha`: the 9 sandbox entries, batches 1–9 from the 21 Nov lesson, six teacher PDFs and Oussama's notes, and **deck batches 10–31** (stage 1 of your old decks: verbs, home, people, emotions, work, time, food, cooking, school, health, grammar, greetings, body, travel, money, mixed). Photos for concrete words and many action verbs (`data/media/`), small diagrams for position words; abstract words have no picture. ف has no headword audio (TTS returns nothing for one letter).
- **Every headword and every example is read by both Badr and Ghalia**; one tap on an example's ▶ plays both in turn (858 example buttons, all with two voices). ElevenLabs: 19.8k / 40k characters used this month (resets ~22 Dec).
- **Inbox: 116 candidates**: 98 entries from old-deck notes you *studied* (never activated; Phase 6 converts those notes in place so history survives) and the doubtful items (`panko::doubtful`: teacher idioms + ~20 deck words no source confirmed).
- **Checks.** Teacher material: checked against Routledge, DODa and the web incl. region (`data/sources/teacher/CHECK-REPORT.md`). Old-deck stage 1 (1,080 rows → 800 entries, 142 dropped): extracted and checked in one pass (`data/sources/decks/DECK-BRIEF.md`), then a **region pass** over all 796 deck entries (`REGION-BRIEF.md`): nearly all pan-Moroccan; دروك (east), عاين (rural), مخض (countryside) tagged `region::`; 13 "not the usual word" notes added. Report: `data/sources/decks/CHECK-REPORT.md`.
  - Gloss clashes were resolved before each batch went in (one everyday word per English front; synonyms recognition-only with a note naming the everyday word). Duplicates merged: تحكّم, حتافل, تهلّا, اهتم, تفلى.
  - Most deck examples are "written by Panko, not yet checked"; DODa corpus sentences were often mistranslated, so few were used.
  - Homographs that differ only by shadda (وصل/وصّل, خرج/خرّج, صلح/صلّح, نقص/نقّص, سال ×2) are kept apart with the item flag `homograph`.
- Waiting on: the learner asking Oussama about the doubtful and low-confidence items (list in both CHECK-REPORTs); an image-gen key; an `ANTHROPIC_API_KEY` to automate extraction.
- Next: **Stage 2** of the old decks (Dave's Darija, Casablanca 1–2, Darija: ~8,900 rows, ~7,000 distinct) needs your go-ahead: same pipeline incl. the region pass, roughly 10× stage 1's cost, and ElevenLabs would need a bigger plan or several months. Phase 6 (migrate the 98 studied notes with history).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stage 1 in Anki (checked + region pass); stage 2 pending |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
