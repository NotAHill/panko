"""Hosted mode (PANKO_HOSTED=1, docs/SPEC-hosted.md): the front-door guard, paths kept inside the user's folder,
keys set from the hub without leaking, upload limits and quota, local-only routes refused."""
import os
import socket
import stat
import threading
import time

import pytest

pytest.importorskip("starlette")
pytest.importorskip("multipart")

from starlette.testclient import TestClient  # noqa: E402

from panko import config, hub, setup, work  # noqa: E402
from panko.hub import api  # noqa: E402
from panko.hub.jobs import Jobs  # noqa: E402
from panko.store import Store  # noqa: E402

FRONT = "front-door-secret-0123456789"
H = {"X-Panko": "1", "X-Panko-Front": FRONT}


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A user's Panko folder on the server, with the hub behind the front door."""
    root = tmp_path / "users" / "amina"
    (root / "config").mkdir(parents=True)
    monkeypatch.setenv("PANKO_HOSTED", "1")
    monkeypatch.setenv("PANKO_QUOTA_GB", "0.001")     # 1 MB
    monkeypatch.setenv("PANKO_UPLOAD_MB", "0.5")
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(setup, "ROOT", root)
    monkeypatch.setattr(setup, "CONFIG", root / "config" / "panko.toml")
    setup.write_config({"language": "Moroccan Darija", "varieties": ["darija"]}, path=root / "config" / "panko.toml")
    config.settings.cache_clear()
    monkeypatch.setattr(work, "WORK", root / "data" / "work")
    monkeypatch.setattr(work, "PAGES", root / "cache" / "pages")
    monkeypatch.setattr(api, "_store", lambda: Store(root / "data" / "panko.db"))
    monkeypatch.setattr(hub, "uploads_dir", lambda: root / "data" / "sources" / "uploads")
    for k in ("PEXELS_API_KEY",):
        monkeypatch.delenv(k, raising=False)
    api.JOBS = Jobs()
    c = TestClient(hub.app(front=FRONT), base_url="http://panko.example.org")
    yield c, root
    config.settings.cache_clear()


def test_the_front_door_secret_stands_for_the_host_and_the_token(home):
    c, _ = home
    assert c.get("/api/meta").status_code == 403                                     # straight to the hub
    assert c.get("/api/meta", headers={"X-Panko-Front": "guess"}).status_code == 403
    assert c.get("/api/meta", headers=H).status_code == 200                           # any host name, no token
    assert c.post("/api/setup/keys", json={}, headers={"X-Panko-Front": FRONT}).status_code == 403  # changes: header


def test_paths_outside_the_folder_are_refused(home, tmp_path):
    c, root = home
    elsewhere = tmp_path / "users" / "omar" / "lesson.txt"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("سلام")
    r = c.post("/api/sources", json={"title": "x", "kind": "notes", "path": str(elsewhere)}, headers=H)
    assert r.status_code == 400 and "upload" in r.json()["error"]
    r = c.post("/api/sources", json={"title": "x", "kind": "notes", "path": "../omar/lesson.txt"}, headers=H)
    assert r.status_code == 400                                                       # no climbing out either
    with pytest.raises(ValueError):
        config.inside("/etc/passwd")
    assert config.inside("data/x.txt") == root / "data" / "x.txt"


def test_local_only_routes_and_server_paths(home):
    c, root = home
    assert c.post("/api/open", json={"what": "folder"}, headers=H).status_code == 403
    assert c.post("/api/sync", json={"confirm": True}, headers=H).status_code == 403
    m = c.get("/api/meta", headers=H).json()
    assert m["hosted"] is True and str(root) not in str(m) and m["root"] == ""


def test_keys_are_written_for_the_user_and_never_sent_back(home):
    c, root = home
    names = [k["name"] for k in c.get("/api/setup/keys", headers=H).json()["keys"]]
    assert "ANTHROPIC_API_KEY" in names and "PANKO_CAMEL_PYTHON" not in names      # local tools aren't the user's
    try:
        r = c.post("/api/setup/keys", json={"name": "PEXELS_API_KEY", "value": "pk-123"}, headers=H)
        assert r.status_code == 200 and "pk-123" not in r.text
        env = root / ".env"
        assert "PEXELS_API_KEY=pk-123" in env.read_text() and stat.S_IMODE(env.stat().st_mode) == 0o600
        assert os.environ["PEXELS_API_KEY"] == "pk-123"                              # works without a restart
        listed = c.get("/api/setup/keys", headers=H)
        assert "pk-123" not in listed.text
        assert next(k for k in listed.json()["keys"] if k["name"] == "PEXELS_API_KEY")["set"]
        assert c.post("/api/setup/keys", json={"name": "PANKO_CAMEL_PYTHON", "value": "/bin/sh"},
                      headers=H).status_code == 400
        assert c.post("/api/setup/keys", json={"name": "PEXELS_API_KEY", "value": "a\nPANKO_CAMEL_PYTHON=/bin/sh"},
                      headers=H).status_code == 400                                  # no smuggled lines
        c.post("/api/setup/keys", json={"name": "PEXELS_API_KEY", "value": ""}, headers=H)
        assert "PEXELS_API_KEY" not in os.environ
    finally:
        os.environ.pop("PEXELS_API_KEY", None)


def test_uploads_have_a_size_limit_and_a_quota(home):
    c, root = home
    small = c.post("/api/upload", files={"files": ("sheet.txt", b"x" * 1000)}, headers=H)
    assert small.status_code == 200 and small.json()["path"] == "data/sources/uploads/sheet.txt"   # no server path
    big = c.post("/api/upload", files={"files": ("big.bin", b"x" * 600_000)}, headers=H)
    assert big.status_code == 413 and "in parts" in big.json()["error"]
    (root / "data" / "filler.bin").write_bytes(b"x" * 800_000)                        # the folder nearly full
    full = c.post("/api/upload", files={"files": ("more.bin", b"x" * 300_000)}, headers=H)
    assert full.status_code == 413 and "left" in full.json()["error"]


def test_downloads_from_the_config_must_be_public_https(monkeypatch):
    monkeypatch.setenv("PANKO_HOSTED", "1")
    for bad in ("http://example.org/x", "https://localhost/x", "https://127.0.0.1/x", "https://169.254.169.254/x",
                "https://10.0.0.5/x", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            config.public_url(bad)
    assert config.public_url("https://github.com/x/y") == "https://github.com/x/y"
    monkeypatch.delenv("PANKO_HOSTED")
    assert config.public_url("http://127.0.0.1/x")                                    # locally, your call


def test_the_store_uses_wal_on_the_server(home):
    _, root = home
    s = Store(root / "data" / "panko.db")
    assert s.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


@pytest.fixture
def short(tmp_path):
    """A folder with a short path: Unix socket paths are capped at about 100 bytes."""
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="pk-", dir="/tmp" if os.path.isdir("/tmp") else None)
    from pathlib import Path
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_a_hub_on_a_socket_only_its_user_can_open(short, monkeypatch):
    tmp_path = short
    path = tmp_path / "run" / "hub.sock"
    s = hub.bind_socket(path)
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        with pytest.raises(SystemExit):              # a socket a hub still listens on isn't taken over
            hub.bind_socket(path)
    finally:
        s.close()
    s2 = hub.bind_socket(path)                       # one left behind is replaced
    s2.close()
    monkeypatch.delenv("PANKO_FRONT_SECRET", raising=False)
    with pytest.raises(SystemExit):
        hub.serve_socket(tmp_path / "other.sock")    # never without the front door's secret


def test_two_users_side_by_side_over_sockets(short):
    """Two hubs on two sockets answer for their own folders (each process has its own PANKO_HOME in real use; here
    one app per socket in threads, which is enough to check the transport and the guard)."""
    import uvicorn
    tmp_path = short
    servers = []
    for name in ("a", "b"):
        sock = hub.bind_socket(tmp_path / f"{name}.sock")
        srv = uvicorn.Server(uvicorn.Config(hub.app(front=FRONT + name), fd=sock.fileno(), log_level="error"))
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        servers.append((srv, sock))
    try:
        for _ in range(100):
            if all(s.started for s, _ in servers):
                break
            time.sleep(0.05)

        def get(name, secret):
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            c.connect(str(tmp_path / f"{name}.sock"))
            c.sendall(f"GET /api/jobs HTTP/1.1\r\nHost: x\r\nX-Panko-Front: {secret}\r\nConnection: close\r\n\r\n".encode())
            out = b""
            while chunk := c.recv(65536):
                out += chunk
            c.close()
            return int(out.split(b" ", 2)[1])
        assert get("a", FRONT + "a") == 200 and get("b", FRONT + "b") == 200
        assert get("a", FRONT + "b") == 403                    # one user's secret doesn't open another's hub
    finally:
        for srv, _ in servers:
            srv.should_exit = True
        time.sleep(0.3)
        for _, sock in servers:
            sock.close()
