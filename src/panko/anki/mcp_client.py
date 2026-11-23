"""Minimal client for the Anki MCP Server add-on (streamable-HTTP JSON-RPC).

Used for everyday reads/writes while Anki is open. Schema-changing migrations go
through the anki pylib with Anki closed instead (see docs/ARCHITECTURE.md).
"""
from __future__ import annotations

import json
import sys
import urllib.request

_sid: str | None = None


def rpc(method: str, params: dict | None = None, id_: int = 1, notify: bool = False):
    global _sid
    body: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        body["id"] = id_
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "MCP-Protocol-Version": "2025-06-18"}
    if _sid:
        headers["Mcp-Session-Id"] = _sid
    from panko.config import anki
    req = urllib.request.Request(anki()["url"], data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        _sid = r.headers.get("Mcp-Session-Id") or _sid
        raw = r.read().decode()
    if notify or not raw.strip():
        return None
    if raw.lstrip().startswith("event:") or "data:" in raw[:20]:
        raw = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")][-1]
    return json.loads(raw)


def init():
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "panko", "version": "0.1"}})
    rpc("notifications/initialized", notify=True)


def call(name: str, args: dict | None = None):
    return rpc("tools/call", {"name": name, "arguments": args or {}}, id_=2)


def tools() -> list[dict]:
    return rpc("tools/list", {}, id_=3)["result"]["tools"]


if __name__ == "__main__":
    init()
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        print("\n".join(sorted(t["name"] for t in tools())))
    else:
        print(json.dumps(call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}), ensure_ascii=False, indent=1))
