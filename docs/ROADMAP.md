# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-22)
- Sandbox v0.2 is live in Anki (`Panko Sandbox::Darija`, `::Fusha`, 21 cards) with the redesigned layout.
- Waiting on: your feedback on v0.2 cards; an ElevenLabs key in `.env` plus a Moroccan voice ID in `config/panko.toml`.
- Next: wire the audio chain into the sandbox builder; A/B ElevenLabs vs Azure on ~10 Darija words; picture picking by a vision model instead of by hand.

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | in progress (v0.2) |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | skeleton done; ElevenLabs/Azure/gpt-image untested (no keys) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | not started |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps | not started |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) + delete prototype note types | not started |
| 7 | Chat interface: Panko's own MCP server | not started |

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
- Which ElevenLabs voice for Darija (needs a listening test)?
