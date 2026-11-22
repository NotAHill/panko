# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first.

## Now (2026-11-23)
- Sandbox v0.3 in Anki: decks `Panko Darija::Words`, `Panko Darija::Phrases`, `Panko Fusha::Words` (19 cards; recognition fronts carry audio, no Listening cards). The old empty `Panko Sandbox` deck can be deleted by hand.
- Audio: ElevenLabs Starter plan. Darija = Badr + Ghalia, Fusha = George (interim). `uv run panko voices` auditions voices.
- Pictures: real photos for all concrete words. "Next to" is an interim diagram. The karni phrase has no picture yet; it needs an image-generation key (OpenAI, Gemini or Recraft).
- Waiting on: image-gen key; v0.3 phone check (audio on recognition fronts, LTR fix).
- Next: vision-model picture picking + generation fallback; start Phase 2 (Panko store).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | in progress (v0.2) |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); Azure + image generation untested (no keys) |
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
