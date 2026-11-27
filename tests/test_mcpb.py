"""Chat mode as a Claude Desktop extension (track D4): what the bundle holds and where it's offered."""
import io
import json
import zipfile

import pytest

pytest.importorskip("mcp")

from panko import mcpb  # noqa: E402


def unzip(data: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    return {n: z.read(n) for n in z.namelist()}


def test_the_bundle_is_a_uv_extension_that_installs_this_release():
    files = unzip(mcpb.bundle("1.2.3"))
    assert set(files) == {"manifest.json", "pyproject.toml", "src/server.py", "icon.png"}
    m = json.loads(files["manifest.json"])
    assert m["manifest_version"] == "0.4" and m["version"] == "1.2.3" and m["icon"] == "icon.png"
    assert m["server"]["type"] == "uv" and m["server"]["entry_point"] == "src/server.py"
    assert m["server"]["mcp_config"]["env"] == {"PANKO_HOME": "${user_config.folder}"}
    assert m["user_config"]["folder"]["type"] == "directory" and m["user_config"]["folder"]["default"] == "${HOME}/Panko"
    names = {t["name"] for t in m["tools"]}
    assert {"panko_guide", "panko_submit", "panko_sources"} <= names
    assert all(t["description"] and len(t["description"]) <= 200 for t in m["tools"])
    assert 'dependencies = ["pankohub==1.2.3"]' in files["pyproject.toml"].decode()
    assert 'main(["mcp"])' in files["src/server.py"].decode()
    assert files["icon.png"][:8] == b"\x89PNG\r\n\x1a\n"


def test_a_local_hub_offers_its_own_folder(tmp_path):
    m = json.loads(unzip(mcpb.bundle("1.0.0", folder=tmp_path))["manifest.json"])
    assert m["user_config"]["folder"]["default"] == str(tmp_path)


def test_the_hub_serves_it_on_your_own_computer_only(monkeypatch):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from panko import hub
    c = TestClient(hub.app("k"), base_url="http://127.0.0.1:8770")
    c.get("/?t=k")
    r = c.get("/addon/panko.mcpb")
    assert r.status_code == 200 and "manifest.json" in unzip(r.content)
    monkeypatch.setenv("PANKO_HOSTED", "1")
    assert c.get("/addon/panko.mcpb").status_code == 404


def test_panko_mcp_bundle_writes_the_file(tmp_path, capsys):
    from panko.cli import main
    main(["mcp", "--bundle", str(tmp_path)])
    assert (tmp_path / "panko.mcpb").exists() and "wrote" in capsys.readouterr().out
