<p align="center"><img src="assets/logo.svg" width="160" alt="Panko logo: a slice of toast with a piece and crumbs breaking off"></p>

# Panko

Panko turns language-learning material into checked Anki cards. That material can be textbook pages, a teacher's
sheets, photos of a notebook or a transcript. Each card gets a picture, real example sentences, audio, both scripts
and a note on where the word is used. Panko was built for Moroccan Darija and Fusha/Quranic Arabic. The language,
the varieties, the decks and the house rules all live in one settings file, so another learner can point it at
another variety.

Panko updates notes in place, so changing the card design later never costs you your review history. Words you
already have are recognised, so a second book only adds what's new.

- **How it fits together:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (diagrams)
- **Where it's at:** [docs/ROADMAP.md](docs/ROADMAP.md)
- **Why:** [docs/DECISIONS.md](docs/DECISIONS.md)
- **Card design:** [docs/SPEC-note-types.md](docs/SPEC-note-types.md)

## What you need
- Python 3.12+ and [uv](https://docs.astral.sh/uv/). Poppler for PDFs, ffmpeg for recordings.
- Anki desktop with the [Anki MCP Server add-on](https://ankiweb.net/shared/info/124672614). Panko pushes cards
  through it while Anki is open.
- Someone to do the reading, in one of two modes:
  - **Chat mode:** your own Claude (Desktop or Code) reads the pages through Panko's MCP server. No API key is
    needed, and there's nothing to pay beyond your Claude plan.
  - **API mode:** Panko calls the language model itself. You need an Anthropic (or OpenAI) key. It's good for big
    sources, and half price with `--batch`.
- Optional keys in `.env`: ElevenLabs for audio and speech-to-text, Pexels or Pixabay for more photos, OpenAI for drawings when no
  photo fits.

## Quickstart
Install, then make a Panko folder. Your settings, store, pictures and audio live there, never in the code.

```bash
uv tool install "panko[mcp,hub] @ git+https://github.com/<you>/panko"   # or: uv sync --all-extras in a checkout
```

```bash
mkdir ~/panko && cd ~/panko
```

```bash
panko init          # a few questions: language, script, varieties, gloss language, deck names, Anki profile
```

Panko works for any language. Two languages come as presets, which fill in the script, how the prompts describe
the language (spelling, verb forms, where loanwords come from), the reference dictionaries, the speech-to-text
language and the voices to audition:

```bash
panko init --language spanish            # or moroccan-darija; any other name starts neutral
```

For another language, give its script when asked (a Unicode script name: Latin, Cyrillic, Arabic, Devanagari…, or
`Han, Hiragana, Katakana` for Japanese), then fill in `[learner]` and `[learner.examples]` in the config. A language
written in Latin letters needs no romanisation: answer `-` and cards show the word alone.

`init` writes `config/panko.toml` and a `.env` for your keys, then checks what's ready (`panko init --check` runs
the check again). Panko finds this folder from wherever you are inside it, or from `PANKO_HOME`.

Next, get the free reference data. The checking steps cite it as evidence:

```bash
panko refs --download
```

### Add a source
Any PDF, folder of page photos or text transcript works. As a worked example, the Peace Corps Morocco *Moroccan
Arabic* textbook is a US government work, so it's in the public domain:

```bash
panko work add moroccan-arabic.pdf --kind textbook --title "Peace Corps Moroccan Arabic"
```

An old Anki deck can be a source too. Panko exports it read-only while Anki is open:

```bash
panko work add --deck "My old Darija deck" --kind deck --title "Old deck" --trust 30
```

A lesson or film recording works too. It is transcribed once (speech-to-text, paid, or a transcript you already
have), and each word it says becomes the card's audio in the real speaker's voice. Record a lesson only with your
teacher's consent:

```bash
panko work add lesson-12.m4a --kind lesson --title "Lesson 12" --speakers teacher,me --learner me
```

```bash
panko work transcribe lesson-12 --estimate   # minutes of audio it would send; drop --estimate to run it
```

The source is split into units: one per page, photo, stretch of transcript, 25 deck rows or three minutes of a recording. `panko work status` shows where
you are.

### Chat mode (no key)
```bash
panko mcp --config  # prints the snippet for Claude Desktop, and the `claude mcp add` line for Claude Code
```

Add the snippet, restart Claude and say *"Let's work through the Peace Corps book with Panko."* Claude reads
`panko_guide`, then goes page by page. For each item it looks up evidence, checks it and plans a picture. It
submits each page, and Panko validates it and checks it for duplicates. You can stop at any point and carry on in
another chat.

### API mode
```bash
panko work run peace-corps-moroccan-arabic -n 5 --estimate   # what 5 pages would cost
```

```bash
panko work run peace-corps-moroccan-arabic -n 5              # stops before spending over budget_usd
```

```bash
panko work ingest peace-corps-moroccan-arabic
```

`--batch` sends each step as a half-price batch. Run `panko llm collect` when it's back, then run the command
again. `panko llm usage` shows what you've spent.

### Review, then make cards
```bash
panko inbox --html        # a review page of the new candidates
```

```bash
panko verify              # free checks by tools: harakat and roots (Standard Arabic), dictionary look-ups (dialect)
```

Standard Arabic checks need [CAMeL Tools](https://camel-tools.readthedocs.io) and its database. It pulls in torch,
so give it its own environment and point `PANKO_CAMEL_PYTHON` in `.env` at that environment's python:

```bash
uv venv -p 3.12 /path/to/camel && uv pip install -p /path/to/camel/bin/python camel-tools==1.6.0
CAMELTOOLS_DATA=/path/to/camel-data /path/to/camel/bin/camel_data -i morphology-db-msa-r13
```

Then set `PANKO_CAMEL_PYTHON=/path/to/camel/bin/python` and `CAMELTOOLS_DATA=/path/to/camel-data` in `.env`.

```bash
panko work decide SOURCE UNIT WORD --known ID   # a held near-duplicate is the same word (or --distinct)
```

```bash
panko activate --batch 1  # candidates become cards on the next sync
```

```bash
panko sync --dry-run      # what would change in Anki, and the audio it would pay for
```

```bash
panko sync                # Anki open: renders and pushes, updating notes in place
panko export darija.apkg  # a package to share (uv sync --extra apkg); no review history, nothing personal
panko pack build darija-food --title "Darija: food" --tag topic::food   # a Panko pack another Panko can import
panko library import darija-food-v1.panko.zip                        # its new cards land in your inbox
panko publish darija-peace-corps --title "Moroccan Arabic" --tag src::textbook::peace-corps --dry-run
                          # a deck for the public library: what goes in, what's left out (drop --dry-run to build)
```

Cards go to the decks named in `[anki.decks]`. Panko never writes the card's own notes field: that's yours.

### The hub: all of it in your browser
```bash
panko hub                 # installed with the hub extra above
```

A local dashboard in a terminal style: what needs doing, your sources (upload a PDF, page photos, a transcript, a
recording, or name an Anki deck) and their units, the inbox with each card previewed as Anki will show it (front and
back, every card of the note, pictures and audio), editing, the free tool checks, gloss clashes, pictures, what a
sync would change, spend by day and task, and the log of every background step. Paid steps always show an estimate
first and ask, with a budget, like a terminal permission prompt. Keyboard first: `/` for commands, `g` then a letter
to jump, `j`/`k`, `a` activate, `r` reject, `space` (or a click on the card) flips it, `?` lists the rest.

It is also where you make Panko yours. **Card design** sets what the back of a card shows and in what order, adds up
to four sections of your own (a mnemonic, a culture note), and sets sizes and fonts, with a live preview; it reaches
Anki on a normal sync. **Pictures** (on the same page) picks the photo sources and whether Panko may draw a picture
when no photo fits; any card can ask for a photo, a drawing or none. **Voices** lets you listen to ElevenLabs voices
for your language and accent and choose the ones that read your cards. These choices are saved in
`config/hub.toml`, on top of `config/panko.toml`. "Show me around" in the sidebar walks through it all.

It only answers on this computer (127.0.0.1), and only through the link it prints: the link carries a one-time key.

## Settings
Everything personal is in `config/panko.toml`:

- `[learner]`: the language, varieties, gloss language, transliteration style, regions and topics. It also holds
  picture rules, such as what a photo must or must not show.
- `[evidence]`: the reference corpora and your own dictionaries. A dictionary you own stays on your machine.
- `[anki]`: the add-on's address, the profile, the decks, and how old note types map to Panko's cards for
  migrations.
- Provider chains for the language model, audio and pictures. The first provider that's ready does each job.
  Reorder them freely.

The prompts in `src/panko/prompts/` read these values and contain nothing personal.

## Licence
Panko is free software under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, change and
share it. If you run a changed version as a service for other people, you must offer them its source. Copyright (C)
2026 NotAHill. Contributions are welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md).

## Develop
```bash
uv sync --all-extras
```

```bash
uv run pytest -q
```

```bash
uv run ruff check .
```

```bash
uv run pre-commit install
```
