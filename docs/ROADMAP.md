# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22)
- **Panko store built** (`data/panko.db`, SQLite, git-ignored). Anki notes are rendered from it and synced in place (hash per note; unchanged notes are skipped). Commands: `panko seed`, `panko ingest PATH`, `panko inbox`, `panko activate [ids] [--batch N]`, `panko sync`.
- Decks: everything in `Panko Sandbox::Darija` and `Panko Sandbox::Fusha`. Words vs phrases is a tag (`kind::word` / `kind::phrase`), not a deck. The empty decks `Panko Darija::Words`, `Panko Darija::Phrases` and `Panko Fusha::Words` can be deleted by hand.
- First ingest: the 21 Nov lesson transcript (Granola). Extraction is in `data/sources/lessons/2026-11-21.extract.json` (written by Claude in chat; no `ANTHROPIC_API_KEY` yet). 61 candidates. Batch 1 (12 furniture/home nouns) is active and in Anki with photos, Badr + Ghalia audio and the lesson sentence as example; all tagged `panko::needs-review`. 49 candidates wait in the inbox.
- Audio: ElevenLabs Starter. Darija = Badr + Ghalia, Fusha = George (interim).
- Pictures for ingested words: picked by hand from contact sheets (`python -m panko.media.pictures`), saved in `data/media/` with `credits.json`.
- Waiting on: an image-gen key (abstract words like خفيف, غالي, بين need generated pictures); an `ANTHROPIC_API_KEY` to automate extraction.
- Next: batch 2 (adjectives + prepositions, needs pictures/diagrams), then phrases; automate picture picking with a vision model; Phase 3 teacher PDFs.

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps | Granola: first lesson ingested (extraction by hand); PDFs not started |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
