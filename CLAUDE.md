# Panko: notes for agents

Panko turns language-learning sources (lessons, teacher PDFs, Peace Corps material,
film/TV clips, old decks) into verified Anki cards for Moroccan Darija and Fusha/Quranic
Arabic. Single user. They review on Anki desktop, AnkiMobile and AnkiWeb.

## Read first
1. `docs/ROADMAP.md`: **Now** section = current state and next step. `data/STATUS.md` (git-ignored) = the learner's own state: decks, counts, what's waiting.
2. `docs/DECISIONS.md`: why things are the way they are.
3. `docs/ARCHITECTURE.md`: Mermaid diagrams + code map. Keep the diagrams in sync with the code; the user edits the stack by pointing at boxes.
4. `docs/SPEC-note-types.md`: fields, card types, display rules. `docs/SPEC-library.md`: the deck library (S10 step 2). `docs/SPEC-hosted.md`: the hosted Panko (S10 step 3). `docs/archive/` holds dated records (early research, the v0.1 prototype): don't work from them.

## Run
- `uv sync --all-extras`, `uv run pytest -q`, `uv run ruff check .`
- `uv run panko init [--language L] [--check]`: starter config for a new learner (from `src/panko/templates/panko.example.toml` plus a language preset in `src/panko/templates/languages/`; writes `config/` and `.env` in the Panko folder) and a check of what's ready. Everything about the language (script, matching, card fonts, prompt wording) comes from `[learner]` via `src/panko/lang/`; Arabic rules live in `lang/arabic.py`, never in prompts or other modules. `uv run panko refs [--download]`: reference data, fetching the open ones.
- `uv run panko providers`: which providers are ready.
- `uv run panko voices [--all]`: audition ElevenLabs Moroccan voices (paid plan); writes `cache/voices/index.html`.
- `uv run panko seed`: load the hand-written sandbox entries into the store (`data/panko.db`).
- `uv run panko ingest PATH`: add an extraction JSON's new items to the inbox; `panko inbox` lists them; `panko activate [ids] [--batch N]` promotes them.
- `uv run panko pictures export|search|apply`: pictures for cards without one. Real photos first (contact sheets from Wikidata, Commons, Openverse, Pexels, Pixabay; `--providers` to try others), drawings otherwise; `panko pictures decide [--searched DIRS] [--estimate]` makes the per-card decisions with the model (plan → search → pick from the sheets; chat mode has the same as tools), then `pictures apply`.
- `uv run panko examples [--estimate]`: example sentences for words without one (chat mode: `panko_examples_todo` then `panko_examples_save`; the hub's examples page offers both). `uv run panko clashes [--estimate]` then `--apply`: production cards with ambiguous glosses. `uv run panko mcp --skill DIR`: the chat workflow as a Claude skill.
- `uv run panko draw FILE [--force] [--batch]`, `panko draw --collect`: drawings for `{entry id: scene}` (OpenAI, style in `config/panko.toml`). `--batch` = OpenAI Batch API, half price, results within 24 h.
- `uv run panko hub [--port 8770] [--no-open]`: the local dashboard (needs `uv sync --extra hub`; the `hub` entry in `.claude/launch.json` runs it for the browser pane with the dev key `dev-preview`: open `/?t=dev-preview` first; `hub-fresh` runs it against an empty Panko folder on the SSD, to try it as a first-time user; `hub-hosted` runs it in hosted mode, `PANKO_HOSTED=1`, against another SSD folder). On the server: `panko hub --socket PATH` behind the front door (`PANKO_FRONT_SECRET`); hosted mode keeps every path inside the user's folder (`config.inside`, `config.public_url`, `config.room_for`): see `docs/SPEC-hosted.md`. `src/panko/hub/`: `api.py` (JSON routes over the same modules as the commands; long or paid steps are jobs; paid ones answer with an estimate unless `confirm: true`), `jobs.py` (one at a time, output captured), `preview.py` (cards as Anki shows them, media inline, sandboxed), `static/` (vanilla JS, no build step; escape everything from entries with `html```). Hub choices (card design `[cards]`, picture chain, voices) are written to `config/hub.toml`, laid over `panko.toml` by `config.settings()`; card design (`cards/design.py`) changes templates and CSS only, never fields.
- The Anki add-on (H3, `src/panko/anki_addon/`, served as `/addon/panko-sync.ankiaddon`): pulls a hosted Panko's cards into Anki on a device code from the account page (`anki/remote.py` is the server side; `tests/test_anki_addon.py` runs a whole sync into a scratch collection). Each Panko gets its own note types there.
- `uv run panko host serve|invite [--admin]|users|purge [--data DIR]`: the front door of a hosted Panko (needs `uv sync --extra host`; `src/panko/host/`: accounts and invites, each user's own `panko hub --socket` started on demand, the proxy, admin; `oauth.py` makes it the OAuth server so a learner's own Claude reaches their Panko's MCP tools at `<site>/mcp`, chat mode on the server). The `host` entry in `.claude/launch.json` runs it locally with data on the SSD; make an invite with `PANKO_HOST_DATA=… uv run panko host invite --admin` first. Deploying: `deploy/README.md` (Oracle Always Free, DuckDNS, Caddy, restic).
- `uv run panko mcp`: Panko as an MCP server for chat mode (the learner's Claude does the reading; needs `uv sync --extra mcp`); `--config` prints the Claude Desktop/Code snippet. Core logic in `work.py` (units, submit, ingest with duplicate checks), `evidence.py`, `dedupe.py`; workflow text in `prompts/chat.md`.
- `uv run panko work add PATH --kind K --title T` (PDF, photo folder, transcript, an exported deck `.json`, or a recording: `--track`, `--speakers`, `--learner`, `--transcript`, then `work transcribe SOURCE [--estimate]` (paid speech-to-text, `[stt]` chain); ingest cuts native clips into `data/media` via `media/clips.py`; `--deck NAME` exports one from Anki read-only; decks split into 25-row units for the `deck` prompt) / `work status` / `work run SOURCE [-n N] [--batch] [--budget] [--estimate]` (API mode) / `work ingest SOURCE` / `work decide SOURCE UNIT AR --known ID|--distinct`: the same unit queue as chat mode.
- `uv run panko verify [ids] [--status candidate|active|all] [--apply] [--tag-active]`: free checks by tools (`checks.py`): Standard Arabic against the `[morph]` analyser (CAMeL Tools, in its own environment via `PANKO_CAMEL_PYTHON`), dialect words against the references; `--apply` holds candidates with spelling/harakat/root problems as `panko::doubtful`. Also runs at ingest.
- `uv run panko sync --dry-run`: what a sync would change and the audio it would pay for (no Anki, no spend).
- `uv run panko export FILE [--variety V] [--personal]`: active cards as an .apkg to share (needs `uv sync --extra apkg`; built in a scratch collection, never the real Anki; the hub saves to `[export] dir`, which for this learner is on the SSD).
- `uv run panko pack build ID --title T [--variety V] [--tag T]` / `panko library import FILE [--activate]`: a deck as one `.panko.zip` that another Panko imports through the normal ingest (`library.py`, `docs/SPEC-library.md`). `panko publish ID --title T [--tag T] --dry-run` first, then without: a deck for the public library (pack, .apkg, index entry, report; picture licences, private sentences and names checked; `[library]` in config). It never uploads; publishing is the user's step. `panko library list|get ID [--activate]`: decks from the library's index (`[library] index`, a URL or a file), downloaded with a sha256 check and imported; the hub's library page does the same.
- `uv run panko sync`: render active entries and push templates/CSS/media/notes to Anki, updating notes in place (Anki must be open with the MCP add-on on 127.0.0.1:3141).
- `uv run panko llm ping|usage|collect`: check the language model, see spend, save finished batches. Code that needs an LLM calls `panko.llm.run(task, asks)` (estimate, budget, cache, batches); never call a vendor SDK directly. Prompts live in `src/panko/prompts/` (`prompts.ask(name, id, parts)`); personal choices go in `[learner]` / `[evidence]` in config, never in a prompt file (a test checks).
- `uv run panko migrate [ids] [--report FILE]`: dry run of Phase 6 (studied old-deck notes → Panko notes, history kept). `--apply` converts for real: Anki closed, needs `uv sync --extra migrate`, then one full sync (upload).
- Personal data (transcripts, extractions, the store, ingested pictures) lives in `data/`, which is git-ignored.

## Hard rules
- **Never cause a full sync casually.** Adding/removing/reordering fields or card templates, deleting a note type, or Change Note Type forces one. Template and CSS edits don't. Field lists in `note_types.py` are frozen (a test guards them).
- Never touch decks outside `Panko Sandbox` without the user's explicit OK. Their review history matters.
- Never write the `MyNotes` field. User edits win over Panko's.
- **In a Claude session, you are the model: use chat mode.** Reading sources, checks, picture picks, examples and gloss clashes go through the Panko MCP tools (`.mcp.json` registers `panko mcp` for this folder; `panko_prompt` gives each step's instructions), with subagents for big batches. The API-mode commands (`work run`, `pictures decide`, `examples`, `clashes`, `work transcribe`, `draw`) spend the user's API credits: run one only when the user asks for API mode, and only after showing its `--estimate` and getting a yes for that run. "Do the pictures" is not a yes to spend.
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
- The repo is public. Never put the teacher's name, collection or review counts, or paid-plan details in tracked files: they go in `data/STATUS.md`.
- Secrets go in `.env` (git-ignored); list new ones in `.env.example`.
- Worktrees for parallel agents go on the external SSD: `/Volumes/external_ssd/worktrees/panko/<branch>`. The internal disk is nearly full.
