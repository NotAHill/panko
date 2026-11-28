"""Which way the model's work gets done: chat mode (the learner's own Claude, through `panko mcp`) or API mode (Panko
calls the model with a key, paid). Both can be available at once; the hub shows each one's state.

Chat mode can't be detected from here (Claude starts the server when it wants it), so the MCP server notes the time
of each tool call in `data/work/chat.json`; "connected" means a call in the last few minutes.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from panko import work

RECENT = 15 * 60        # seconds: a tool call this recent counts as connected
_last_write = 0.0


def _path():
    return work.WORK / "chat.json"


def mark_chat(tool: str) -> None:
    """Note a chat-mode tool call (at most every 20 s, so busy sessions don't write constantly). Never fails."""
    global _last_write
    now = time.time()
    if now - _last_write < 20:
        return
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"last": datetime.now(UTC).isoformat(timespec="seconds"), "tool": tool}), encoding="utf-8")
        _last_write = now
    except OSError:
        pass


def chat() -> dict:
    """{"last": ISO time or "", "ago": seconds or None, "active": bool}."""
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
        ago = int((datetime.now(UTC) - datetime.fromisoformat(d["last"])).total_seconds())
        return {"last": d["last"], "ago": ago, "active": ago < RECENT}
    except (OSError, ValueError, KeyError):
        return {"last": "", "ago": None, "active": False}


def api() -> dict:
    """{"ready": bool, "provider": name, "model": model}: whether paid steps can run here."""
    try:
        from panko import providers
        chain = providers.chain("llm")
    except Exception:  # a provider that can't load means API mode isn't ready
        chain = []
    if not chain:
        return {"ready": False, "provider": "", "model": ""}
    p = chain[0]
    return {"ready": True, "provider": p.name, "model": getattr(p, "model", "")}


def state() -> dict:
    return {"chat": chat(), "api": api()}
