# Panko as an MCP server (chat mode)

**Goal:** a learner with a Claude subscription runs the whole pipeline without API credits. Their own Claude
(Claude Desktop, claude.ai with a local connector, or Claude Code) does the reading and judging; Panko provides
the tools: files, prompts, evidence, validation, the store and Anki. Panko never calls a model in this mode.

The same prompts and schemas as API mode (`src/panko/prompts/`). Only the transport changes:

| | API mode (S1) | Chat mode (this spec) |
|---|---|---|
| Who runs the model | `panko.llm.run()` with an API key | The user's Claude, in a chat |
| Prompt | system prompt of the request | returned by `panko_prompt` |
| Answer | JSON from the API | sent back through `panko_submit`, checked against the same schema |
| Cost | API credits (batches halve it) | the user's subscription usage |
| Unattended | yes | no: it runs while they chat |

## Tools

Grouped by step. All return JSON. Paths are relative to the Panko project. Names are prefixed `panko_` so they read
clearly next to other connectors.

### Sources
- `panko_sources()`: configured sources and their state (pages done, items in, items pending).
- `panko_add_source(path, kind, title)`: register a PDF, transcript, deck export or image folder.
- `panko_next_work(source, n=5)`: the next unprocessed units (pages, transcript chunks, deck rows), so Claude
  works through a book in steady batches and can stop and resume across chats.
- `panko_page(source, page)`: the page image (MCP image content) plus its text layer.
- `panko_chunk(source, id)`: a transcript stretch or a batch of deck rows as text.

### Prompts
- `panko_prompt(name, **vars)`: the rendered prompt (`extract`, `deck`, `check`, `examples`, `pictures-plan`,
  `pictures-pick`) with the learner's config filled in, plus its JSON schema. Claude reads it before a step.

### Evidence (free, local)
- `panko_evidence(words: [{ar, tl_alt, pos}])`: for each word, whether the learner already has it (entry id,
  gloss), then hits from the configured corpora and dictionaries (DODa, Wiktionary, Routledge…). The step that
  makes checking cheap: known words skip checking and pictures entirely.

### Submitting work
- `panko_submit(step, unit, data)`: validates `data` against the step's schema and the unit, then stores it as a
  pending result (`data/work/<source>/<step>/<unit>.json`). Returns the errors to fix if it doesn't validate, so a
  sloppy answer is bounced back to Claude instead of reaching the store.
- `panko_pending(source)`: units extracted but not yet checked, checked but no picture plan, and so on.
- `panko_ingest(source)`: merges the pending results (extract + verdicts + picture plans), drops duplicates and
  adds new items to the inbox, exactly like `panko ingest --verdicts`.

### Review and Anki
- `panko_inbox(filter)`, `panko_entry(id)`: what's waiting and what an entry will look like.
- `panko_activate(ids | batch)`: promote candidates. `panko_edit(id, fields)`: corrections the learner asks for
  in chat (never `MyNotes`).
- `panko_sync(dry_run=True)`: render and push to Anki; the dry run lists what would change. Schema-changing
  operations (anything that forces a full sync) are not exposed.

### Pictures and audio (paid services stay opt-in)
- `panko_photo_search(id)`: Commons/Openverse contact sheet as an image; `panko_submit("pictures-pick", ...)`
  records the choice.
- `panko_draw(ids, batch=True)`, `panko_audio(ids)`: OpenAI drawings and ElevenLabs audio. They spend the
  user's own keys, so each returns a cost estimate first and needs `confirm=True`.

## Skill / plugin
A Claude skill (or Claude Code plugin) ships with the server: "how to run Panko". Work through `panko_next_work`
in batches; for each unit get the prompt, read the page, extract, call `panko_evidence`, check only new items,
plan pictures, `panko_submit`; `panko_ingest` at the end of a session; never sync without asking. It holds the
workflow, not the language rules: those stay in the prompts and the learner's config.

## Limits to say plainly
- Subscription usage limits apply. A 190-page book is several sessions, which `panko_next_work` makes painless.
- Not unattended and no batch discount: for a big job someone wants done overnight, API mode is still there.
- Quality depends on the model the user picks in their Claude app. The prompts assume a strong one; the
  three-model test (2026-11-23) showed cheaper models break the house style and pass errors.

## Build order
1. Server skeleton (Python MCP SDK, stdio), `panko mcp` to run it, config snippet for Claude Desktop/Code.
2. Read-only tools: sources, page, prompt, evidence, inbox.
3. `panko_submit` with schema validation and `panko_ingest`.
4. `panko_next_work` / `panko_pending` (resumable batches).
5. The skill, then activate/sync/edit, then pictures and audio.
6. Test: run the remaining Peace Corps pages through it in Claude Desktop and compare with API-mode output.
