# Panko: notes for agents

Panko turns language-learning sources (lessons, teacher PDFs, Peace Corps material,
film/TV clips, old decks) into verified Anki cards for Moroccan Darija and Fusha/Quranic
Arabic. Single user. They review on Anki desktop, AnkiMobile and AnkiWeb.

## Read first
1. `docs/ROADMAP.md`: **Now** section = current state and next step.
2. `docs/DECISIONS.md`: why things are the way they are.
3. `docs/ARCHITECTURE.md`: Mermaid diagrams + code map. Keep the diagrams in sync with the code; the user edits the stack by pointing at boxes.
4. `docs/SPEC-note-types.md`: fields, card types, display rules. `docs/RESEARCH.md`: background research.

## Run
- `uv sync --all-extras`, `uv run pytest -q`, `uv run ruff check .`
- `uv run panko providers`: which providers are ready.
- `uv run panko voices [--all]`: audition ElevenLabs Moroccan voices (paid plan); writes `cache/voices/index.html`.
- `uv run panko seed`: load the hand-written sandbox entries into the store (`data/panko.db`).
- `uv run panko ingest PATH`: add an extraction JSON's new items to the inbox; `panko inbox` lists them; `panko activate [ids] [--batch N]` promotes them.
- `uv run panko pictures export|search|apply`: pictures for cards without one. Real photos first (Commons/Openverse contact sheets), drawings otherwise; the per-card decisions follow `data/sources/decks/PICTURE-BRIEF.md`.
- `uv run panko draw FILE [--force] [--batch]`, `panko draw --collect`: drawings for `{entry id: scene}` (OpenAI, style in `config/panko.toml`). `--batch` = OpenAI Batch API, half price, results within 24 h.
- `uv run panko sync`: render active entries and push templates/CSS/media/notes to Anki, updating notes in place (Anki must be open with the MCP add-on on 127.0.0.1:3141).
- `uv run panko llm ping|usage|collect`: check the language model, see spend, save finished batches. Code that needs an LLM calls `panko.llm.run(task, asks)` (estimate, budget, cache, batches); never call a vendor SDK directly. Prompts live in `src/panko/prompts/` (`prompts.ask(name, id, parts)`); personal choices go in `[learner]` / `[evidence]` in config, never in a prompt file (a test checks).
- `uv run panko migrate [ids] [--report FILE]`: dry run of Phase 6 (studied old-deck notes → Panko notes, history kept). `--apply` converts for real: Anki closed, needs `uv sync --extra migrate`, then one full sync (upload).
- Personal data (transcripts, extractions, the store, ingested pictures) lives in `data/`, which is git-ignored.

## Hard rules
- **Never cause a full sync casually.** Adding/removing/reordering fields or card templates, deleting a note type, or Change Note Type forces one. Template and CSS edits don't. Field lists in `note_types.py` are frozen (a test guards them).
- Never touch decks outside `Panko Sandbox` without the user's explicit OK. Their review history matters.
- Never write the `MyNotes` field. User edits win over Panko's.
- Don't run Anki's Check Media → delete unused.

## Card style (user feedback, 2026-11-22)
- Should look hand-made: clean, simple, nothing that reads as AI output. Maximise what a learner gets.
- No provenance in the card body. Sources only in the collapsed Sources section.
- Fronts show only the prompt. No hints, no notes, no "say it in…".
- No register badge: the deck says Darija or Fusha.
- Examples are required. Real pictures preferred; generate only when none is found. Generated pictures help you remember the word (not realism); any woman or girl shown wears a hijab and modest clothes, and women appear only when the scene needs one; no fez clichés; no text.
- Transliteration: the teacher's Arabizi first (3/7/9), scholarly second.
- Avoid vendor lock-in: put the best tool per job behind a provider chain.

## Housekeeping
- Update `docs/ROADMAP.md` "Now" and add to `docs/DECISIONS.md` when something is decided.
- Secrets go in `.env` (git-ignored); list new ones in `.env.example`.
- Worktrees for parallel agents go on the external SSD: `/Volumes/external_ssd/worktrees/panko/<branch>`. The internal disk is nearly full.
