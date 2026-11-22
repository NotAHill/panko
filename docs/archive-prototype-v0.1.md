# Panko sandbox prototype

This builds spec v0.1 (`../SPEC-note-types.md`) inside your real Anki, isolated from your other decks:

- **Note types:** `Panko • Word (proto)` (10 card templates) and `Panko • Phrase (proto)` (6 card templates)
- **Decks:** `Panko Sandbox::Darija` (4 words + 3 phrases) and `Panko Sandbox::Fusha` (2 words). Together they produce 28 cards.
- **Tags:** every note is tagged `panko::prototype`; Darija notes are also tagged `panko::needs-review`

Run it with `python3 build_sandbox.py`. Anki must be open with the Anki MCP Server add-on running. Re-running pushes template and CSS edits to the note types and skips notes that already exist.

## What's a placeholder
- **Audio:** the macOS "Majed" voice, which speaks MSA, not Darija.
- **Pictures:** simple drawings.
- **Darija transliterations and glosses:** written by hand from the 21 Nov transcript and the Module 6 sheet. They haven't been checked.

## What to test on your iPhone
1. Harakat: do marks clip, especially shadda + vowel? Is the font readable?
2. Example audio: does **A (sound tag)** autoplay, and does **B (tap button)** play when tapped?
3. Does the collapsible **Sources** section open and close?
4. Picture cards, production cards and listening cards: do the fronts feel right?
5. Overall layout in dark mode.

## Cleanup
Deleting the prototype note types later changes Anki's schema, which means **one full sync**. Plan: do the cleanup in the same full sync as the migration of your old decks, after syncing every device first. All media files start with `_panko_proto_`.
