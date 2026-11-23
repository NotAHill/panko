# Roadmap and status

Update the **Now** section at the end of every work session: it's what a fresh session
(or one after context compaction) reads first. Personal details (names, collection numbers, paid plans) go in
`data/STATUS.md` (git-ignored), not here: this repo is public.

## Now (2026-11-23)
- **Built:** the Panko store (SQLite) with in-place sync to Anki; provider chains for audio (ElevenLabs), pictures
  (real photos from Wikidata, Commons, Openverse, Pexels and Pixabay first; generated drawings otherwise) and the
  language model (Claude by default); migration of studied old-deck notes with their history (`panko migrate`).
- **Standalone track S1–S6 done:** the language-model layer, generic prompts, chat mode (`panko mcp`), API mode
  (`panko work run`), settings for any learner (`panko init`, `panko refs`), and packaging (AGPL-3.0-or-later,
  README quickstart, fake-Anki sync tests).
- **Sources run so far:** lessons and teacher sheets, the learner's old shared Darija decks (checked, with a region
  pass), and the public-domain Peace Corps *Moroccan Arabic* textbook (run through Panko's own prompts).
- **Next:** S7, checking that the commands reproduce what the chat agents produced (one teacher sheet, one old-deck
  batch), with deck rows as a unit type for API mode. Pictures for the Peace Corps candidates are being searched.
- The learner's own state (deck sizes, what's waiting on whom, plans) is in `data/STATUS.md` (git-ignored).

## Phases
| # | Phase | Status |
|---|---|---|
| 0 | Card design in a sandbox (note types, templates, real pictures) | v0.3 done |
| 1 | Provider layer: audio, pictures, LLM, behind swappable chains | ElevenLabs working (cached); OpenAI image generation working (`panko draw`); Azure untested (no key) |
| 2 | Panko store (SQLite) as source of truth; re-render notes from it | built: store, ingest inbox, in-place sync |
| 3 | Source adapters: teacher PDFs (vision LLM), Granola transcripts, Peace Corps, old Darija decks | lesson + 6 teacher PDFs + notes ingested and in Anki (extraction by Claude in chat); old Darija decks stages 1–2 in Anki (checked + region pass) |
| 4 | Lesson recording (two tracks) + guided speech-to-text + teacher clips | not started; needs teacher's consent |
| 5 | Verification: lexicon grounding, CAMeL Tools checks, doubt flags | verdict files (Routledge, DODa, web) applied at ingest; CAMeL not started |
| 6 | Migrate studied notes from old decks (pylib, Anki closed, one full sync) | Darija: done (studied notes converted, history kept); Fusha decks later |
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
| S7 | **Check it matches** | Re-run one teacher sheet and one old-deck batch through the commands and compare with what the agents produced. Fix the prompts until they agree. Then the Fusha round (Phase 6, second round) runs on the commands too. |

Open: Arabic varieties only at first, or any language. (Settled 2026-11-23: AGPL-3.0-or-later, published on GitHub; Opus for every step, batches for big runs.)

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
