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
- **Phase 6, second round (later, your call 2026-11-23: Fusha waits)**: one more conversion + full upload covering
  - Fusha: Arabiyyah Bayna Yadayk 1–3 (535 reviewed of 1,526; fields: vowelled `past \ present \ imperative \ masdar` or `singular \ plural`, Form, Root, Hans Wehr link) and iExplore (82 of 137; Wiktionary link). Open questions: Fusha transliteration style, unreviewed notes later as new cards?
  - Serious Explorer is **Darija** (60 notes, all reviewed): Arabic + transliteration only inside a picture of text, a real recording of each word, a photo on the back. Ask whether to use the recordings as word audio.
  - 14 reviewed Darija notes whose word was already a Panko card (merged as duplicates, history not carried: شرب, خاف, سوق, ماشي مشكل, حومة, مرا…): convert the old note for that entry and delete the newer, unreviewed Panko note.
- **Peace Corps downloaded** (2026-11-23, public domain, from Live Lingua) to the SSD, linked as `data/sources/peace-corps/`: the 2011 textbook (199 pages) and 34 tracks (40 min). The PDF text layer is usable but is almost all **scholarly transliteration** (ع for ʕ, Cyrillic н for ḥ, x for kh; Arabic script is rare), and two-column vocabulary pages interleave, so Arabic script must be derived and checked, with page images where columns mix. Each track = one book section read by native speakers, announced with its page (track 9 = dialogue p. 6 … track 34 = p. 141; track 1 = 12-min intro; 2–8 pronouns, demonstratives, numbers; 9–34 dialogues). Scribe transcripts with word timings: `data/sources/peace-corps/scribe/` (force `language_code=ara`; auto-detect called one track English).
- **Direction change (your call, 2026-11-23): Panko becomes a standalone package.** Everything Claude and its agents did in chat becomes a `panko` command, so another learner can run the whole pipeline themselves. See the **Standalone** track below. Peace Corps is the first source to be run entirely by Panko's own commands.
- **S1 built** (`panko.llm` + `providers/llm/`): Claude by default, OpenAI once a model is set; estimates, budget cap, cache, usage log, batches; tested with a fake model. Live-tested with Claude.
- **S2 built** (2026-11-23): six generic prompts in `src/panko/prompts/` with strict schemas; `[learner]` and `[evidence]` in config hold everything personal; `[llm.tasks]` picks a model per step. Live check: the packaged extract prompt on Peace Corps p. 93 gave 31 correct items with Arabic, both transliterations and an example each ($0.17 on Opus, one flag on *9hwa mherrsa*).
- **Peace Corps through Panko (2026-11-23)**: six varied pages run by Panko's own prompts on Opus (extract → local evidence → check → picture plan) for $1.65; the other 177 pages done in chat by nine agents with the same prompts and evidence helper (no API spend), merged and ingested. Result: **743 new candidates** in the inbox after a near-duplicate pass (835 ingested; 92 were spelling or wording variants of existing entries and were retired, their book sentences moved over; not activated: waiting for pictures), 1,983 sightings, the book's sentences added to 1,131 known entries. Verdicts on the new items: 701 ok, 15 uncommon (bookish), 14 doubtful (mostly clothing loans and fruit names only the book has), 6 regional, 3 fixed. Picture plans are saved per item (`data/sources/peace-corps/extract/*.pictures.json`) for `panko pictures`. Prompt fixes from the test: the source wins over memory unless there's evidence; grammar-page sentences become examples.
- **Lessons for S3** (from the merge): the store's match key ignores shadda, so doubled verbs (ضحك d7ek / ضحّك de77ek) collide; 37 were kept apart as homographs by hand. S3 should match on Arabic + transliteration. The evidence helper needs full POS names and spelling variants (گ/ق/ڭ, ى/ا). Known items need a way to carry a new sense (the book adds senses like دار "to do", سال "to be owed"; listed for review, not applied). The cost estimate must use each prompt's real output size. Ingest's exact-match check missed 92 near-duplicates (ما كاين مشكل / ما كاين حتى مشكل, سبيطار / صبيطار, تقابل / تقابل مع, feminine forms), so S3 needs a fuzzy duplicate pass (`dupes.py` on the SSD is the prototype) before items reach the inbox.
- Next: S3 chat mode (Panko as an MCP server, `docs/SPEC-mcp.md`), so the rest of Peace Corps and any other learner's sources run on a Claude subscription; then S4 commands for unattended API runs. Model choice settled (2026-11-23, three-model test): Opus for every step, batches for big runs; Peace Corps ≈ $58 standard, ≈ $29 as batches. Re-run the test once S3's evidence lookup exists.

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
| 7 | Chat interface: Panko's own MCP server | now Standalone S3 (chat mode); spec in `docs/SPEC-mcp.md` |

## Standalone track (from 2026-11-23)
Goal: someone else learning a language this way installs Panko, points it at their sources and Anki, and gets the
same checked cards, without a Claude Code session doing the thinking. Today the LLM steps (extract, check, region,
sentences, clashes, picture decisions) are briefs in `data/` (git-ignored) run by Claude agents in chat.

| # | Step | What "done" means |
|---|---|---|
| S1 ✅ | **LLM provider chain** (built and live-tested 2026-11-23) | `providers/llm/`: Claude by default (Anthropic SDK), OpenAI as an alternative, same interface. Structured JSON output checked against a schema, retries, prompt caching, the Batch API for big runs (half price). Every paid run prints a cost estimate first and honours a budget cap. |
| S2 ✅ | **Prompts in the package** (built 2026-11-23) | The briefs move to `src/panko/prompts/` as generic prompts. Personal choices move to config: teacher and their Arabizi style, region, transliteration order, picture rules (hijab, no fez), what to skip. |
| S3 | **Chat mode: Panko as an MCP server** (decided 2026-11-23) | A learner with a Claude subscription runs the pipeline with no API credits: their Claude reads pages and judges, Panko serves tools (pages, rendered prompts, evidence, schema-checked submit, inbox, sync) plus a skill with the workflow. Same prompts and schemas as API mode. Spec: `docs/SPEC-mcp.md`. Done when the remaining Peace Corps pages run through it in Claude Desktop. |
| S4 | **A command per step** (API mode, for unattended runs) | `panko extract` (PDF pages via vision, text, transcripts, deck rows), `panko check` (verify + region, with evidence), `panko examples`, `panko dedupe` (clashes), `panko pictures decide`. Parallel, resumable, cached per item; they write the JSON that `ingest` / `pictures apply` already read, so the human review points stay. |
| S5 | **Evidence and settings for anyone** | `panko init` writes the config: Anki profile, deck names, varieties, voices, keys. Nothing hard-coded (profile "User 1", "Panko Sandbox", the old-deck card map: detect which side shows Arabic from the templates, with an override file). Open evidence downloads itself (DODa); private dictionaries are a path in config. |
| S6 | **Packaging and docs** | README quickstart for a new learner, licence, a worked example on a free source (Peace Corps), tests with a fake Anki and fake LLM. Publish when you decide. |
| S7 | **Check it matches** | Re-run one teacher sheet and one old-deck batch through the commands and compare with what the agents produced. Fix the prompts until they agree. Then the Fusha round (Phase 6, second round) runs on the commands too. |

Open: licence and where to publish; Arabic varieties only at first, or any language; which model for bulk work (cost vs quality).

## Open questions
- Two decks or a separate Quranic deck?
- Fusha production cards on by default?
- Transliteration on Fusha cards?
