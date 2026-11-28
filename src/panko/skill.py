"""A Claude skill for chat mode: the workflow text as SKILL.md, for Claude Code or Claude Desktop.

The Panko MCP server has the tools; the skill tells the learner's Claude when to use them. `panko mcp --skill DIR`
writes DIR/panko/SKILL.md (Claude Code reads skills from ~/.claude/skills or a project's .claude/skills).
"""
from __future__ import annotations

from pathlib import Path

DESCRIPTION = ("Turn language-learning material (textbook pages, teacher sheets, transcripts, old Anki decks) into "
               "checked Anki cards with Panko's MCP tools: extract, check with evidence, pictures, gloss clashes, sync. "
               "Use when the learner wants to work through a source with Panko or review what's waiting.")


def text() -> str:
    """The chat guide, filled in from this learner's config (call `panko_guide` for the submit schema)."""
    from panko import prompts
    guide = prompts.render("chat").strip()
    return (f"---\nname: panko\ndescription: {DESCRIPTION}\n---\n\n{guide}\n\n"
            "Call `panko_guide` at the start of a session for the exact result format `panko_submit` accepts.\n")


def write(dir: Path) -> Path:
    out = Path(dir).expanduser() / "panko" / "SKILL.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text(), encoding="utf-8")
    return out
