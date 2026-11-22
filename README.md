# Panko

Turns language-learning sources into complete, verified Anki cards. Built for learning Moroccan
Darija and Fusha/Quranic Arabic, and designed so card layouts can change later without losing review
history.

- **How it fits together:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (diagrams)
- **Where it's at:** [docs/ROADMAP.md](docs/ROADMAP.md)
- **Why:** [docs/DECISIONS.md](docs/DECISIONS.md)
- **Card design:** [docs/SPEC-note-types.md](docs/SPEC-note-types.md)

## Setup
```bash
uv sync --all-extras
cp .env.example .env    # add the keys for the providers you use
uv run panko providers  # shows which providers are ready
```

Anki must be running with the [Anki MCP Server add-on](https://ankiweb.net/shared/info/124672614) installed. Then:

```bash
uv run panko sandbox --reset   # rebuild the Panko Sandbox decks
```

## Develop
```bash
uv run pytest -q
uv run ruff check .
uv run pre-commit install
```
