"""After `uv tool install` of the built package: Panko works on this computer as a new user's would. Starts
`panko hub` (opens its page with the launch key, reads the setup state), runs chat mode (`panko mcp`, an MCP
handshake and the tool list), and writes the Claude Desktop extension. Run with plain Python: no dependencies."""
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

os.chdir(Path.home())                 # as a new user: not inside this checkout, which has its own config
panko = shutil.which("panko")
assert panko, "panko isn't on the PATH"
print("panko at", panko, subprocess.run([panko, "--version"], capture_output=True, text=True, check=True).stdout)

# the hub
hub = subprocess.Popen([panko, "hub", "--no-open", "--port", "8771"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8", errors="replace")
try:
    url, lines, t0 = None, [], time.time()
    while time.time() - t0 < 60 and url is None:
        line = hub.stdout.readline()
        if not line:
            break
        lines.append(line)
        m = re.search(r"(http://127\.0\.0\.1:8771/\?t=\S+)", line)
        url = m.group(1) if m else None
    assert url, "the hub didn't print its link:\n" + "".join(lines)
    jar = http.cookiejar.CookieJar()
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for _ in range(40):
        try:
            page = web.open(url, timeout=10).read().decode()
            break
        except OSError:
            time.sleep(0.5)
    assert "Panko" in page, page[:300]
    meta = json.loads(web.open("http://127.0.0.1:8771/api/meta", timeout=10).read())
    print("hub: folder", meta["root"], "config:", meta["config"])
    assert Path(meta["root"]).name == "Panko" and Path(meta["root"]).parent == Path.home()
finally:
    hub.terminate()
    hub.wait(20)

# chat mode
mcp = subprocess.Popen([panko, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8")


def ask(msg):
    mcp.stdin.write(json.dumps(msg) + "\n")
    mcp.stdin.flush()
    if "id" in msg:
        line = mcp.stdout.readline()
        assert line, "chat mode stopped: " + mcp.stderr.read()[-2000:]
        return json.loads(line)


ask({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}})
ask({"jsonrpc": "2.0", "method": "notifications/initialized"})
tools = ask({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
print("chat mode:", len(tools), "tools")
assert len(tools) > 20
mcp.stdin.close()
mcp.wait(20)

# the Claude Desktop extension
out = Path.home() / "panko-smoke.mcpb"
subprocess.run([panko, "mcp", "--bundle", str(out)], check=True)
assert out.stat().st_size > 10_000
print("extension:", out.stat().st_size, "bytes")
print("ok on", sys.platform)
