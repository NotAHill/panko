"""The front door (H2): invites, sign-in, sessions, the admin pages, and each user's own Panko started behind it and
reached through the proxy. The end-to-end test starts real `panko hub --socket` processes for two users."""
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("starlette")
pytest.importorskip("argon2")

from starlette.testclient import TestClient  # noqa: E402

from panko.host import app as host_app  # noqa: E402
from panko.host.store import HostStore  # noqa: E402

PW = "a-long-test-password"


@pytest.fixture
def data():
    """A short folder: Unix socket paths are capped at about 100 bytes."""
    d = Path(tempfile.mkdtemp(prefix="pkh-", dir="/tmp" if os.path.isdir("/tmp") else None))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def no_throttle():
    host_app.FAILS.clear()
    yield
    host_app.FAILS.clear()


def client(a, base="http://door.test"):
    return TestClient(a, base_url=base, follow_redirects=False)


def post(c, path, data, origin="http://door.test"):
    return c.post(path, data=data, headers={"Origin": origin})


# ---- the store

def test_invites_work_once_and_tokens_are_only_hashed(data):
    st = HostStore(data / "host.db")
    token = st.invite(admin=True, note="me")
    u = st.accept(token, "amina", PW)
    assert u["admin"] == 1 and u["name"] == "amina"
    with pytest.raises(ValueError):
        st.accept(token, "omar", PW)                        # used
    raw = (data / "host.db").read_bytes()
    assert token.encode() not in raw and PW.encode() not in raw
    assert st.check("amina", PW) and not st.check("amina", "wrong-password") and not st.check("nobody", PW)
    s = st.start_session(u["id"])
    assert st.session_user(s)["id"] == u["id"]
    st.update(u["id"], disabled=1)
    assert st.session_user(s) is None and not st.check("amina", PW)   # disabled: signed out, can't sign in


def test_names_and_passwords_are_checked(data):
    st = HostStore(data / "host.db")
    for name, pw in (("A", PW), ("ok-name", "short"), ("amina", "amina-is-my-password")):
        with pytest.raises(ValueError):
            st.add_user(name, pw)


# ---- the pages

def test_sign_in_needs_an_account_and_this_sites_own_form(data):
    a = host_app.app(data)
    c = client(a)
    assert c.get("/").headers["location"] == "/host/login"
    assert c.get("/api/meta").status_code == 401
    st = a.state.door.store
    st.add_user("amina", PW)
    assert post(c, "/host/login", {"name": "amina", "password": PW}, origin="http://evil.test").status_code == 403
    assert post(c, "/host/login", {"name": "amina", "password": "nope-nope-nope"}).status_code == 401
    r = post(c, "/host/login?next=/host/account", {"name": "Amina", "password": PW})
    assert r.status_code == 303 and r.headers["location"] == "/host/account"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "amina" in c.get("/host/account").text
    assert post(c, "/host/login?next=//evil.test", {"name": "amina", "password": PW}).headers["location"] == "/"


def test_too_many_wrong_passwords_wait(data):
    a = host_app.app(data)
    a.state.door.store.add_user("amina", PW)
    c = client(a)
    for _ in range(5):
        post(c, "/host/login", {"name": "amina", "password": "wrong-wrong-wrong"})
    assert post(c, "/host/login", {"name": "amina", "password": PW}).status_code == 429


def test_an_invite_makes_the_account_and_signs_in(data):
    a = host_app.app(data)
    st = a.state.door.store
    token = st.invite()
    c = client(a)
    assert c.get(f"/host/invite/{token}").status_code == 200
    assert c.get("/host/invite/not-a-token").status_code == 404
    r = post(c, f"/host/invite/{token}", {"name": "omar", "password": PW, "password2": PW + "x"})
    assert "passwords aren&#x27;t the same" in r.text
    r = post(c, f"/host/invite/{token}", {"name": "omar", "password": PW, "password2": PW})
    assert r.status_code == 303 and st.by_name("omar")
    assert c.get(f"/host/invite/{token}").status_code == 404           # once only


def test_admin_pages_are_for_admins(data):
    a = host_app.app(data, base_url="https://panko.example.org")
    st = a.state.door.store
    boss, other = st.add_user("boss", PW, admin=True), st.add_user("omar", PW)
    c = client(a)
    post(c, "/host/login", {"name": "omar", "password": PW})
    assert c.get("/host/admin").status_code == 403
    c2 = client(a)
    post(c2, "/host/login", {"name": "boss", "password": PW})
    assert "omar" in c2.get("/host/admin").text
    r = post(c2, "/host/admin/invite", {"note": "for a friend"})
    assert "https://panko.example.org/host/invite/" in r.text
    post(c2, f"/host/admin/user/{other['id']}", {"do": "disable"})
    assert st.user(other["id"])["disabled"] == 1
    assert c.get("/host/account").status_code == 303                   # omar was signed out
    r = post(c2, f"/host/admin/user/{other['id']}", {"do": "delete", "confirm": "wrong"})
    assert "Type their name" in r.text and st.user(other["id"])
    r = post(c2, f"/host/admin/user/{other['id']}", {"do": "delete", "confirm": "omar"})
    assert st.user(other["id"]) is None
    post(c2, f"/host/admin/user/{boss['id']}", {"do": "disable"})       # an admin can't lock themself out
    assert st.user(boss["id"])["disabled"] == 0


# ---- each user's own Panko, through the proxy (real processes)

def test_each_user_gets_their_own_panko_behind_the_door(data):
    a = host_app.app(data, idle_minutes=0)
    st = a.state.door.store
    amina, omar = st.add_user("amina", PW), st.add_user("omar", PW)
    with TestClient(a, base_url="http://door.test", follow_redirects=False) as c1, \
            TestClient(a, base_url="http://door.test", follow_redirects=False) as c2:
        post(c1, "/host/login", {"name": "amina", "password": PW})
        post(c2, "/host/login", {"name": "omar", "password": PW})
        m1 = c1.get("/api/meta")
        assert m1.status_code == 200 and m1.json()["hosted"] is True and m1.json()["config"] is False
        assert c1.get("/").status_code == 200 and "app.js" in c1.get("/").text
        # amina sets up her Panko; omar's stays untouched
        r = c1.post("/api/setup", json={"answers": {"language": "Moroccan Darija", "varieties": ["darija"]}},
                    headers={"X-Panko": "1", "Origin": "http://door.test"})
        assert r.status_code == 200, r.text
        assert c1.get("/api/meta").json()["config"] is True
        assert c2.get("/api/meta").json()["config"] is False
        assert (data / "users" / amina["id"] / "config" / "panko.toml").exists()
        assert not (data / "users" / omar["id"] / "config").exists()
        # an upload lands in her folder, and a change from another site is refused at the door
        up = c1.post("/api/upload", files={"files": ("sheet.txt", "سلام".encode())},
                     headers={"X-Panko": "1", "Origin": "http://door.test"})
        assert up.json()["path"] == "data/sources/uploads/sheet.txt"
        assert c1.post("/api/setup", json={}, headers={"X-Panko": "1", "Origin": "http://evil.test"}).status_code == 403
        # the hub never sees the session cookie, and the browser never sees the hub's secret
        assert "x-panko-front" not in {k.lower() for k in m1.headers}
        door = a.state.door
        assert door.pankos.alive(amina["id"]) and door.pankos.alive(omar["id"])
        assert door.pankos.alive(amina["id"]).secret != door.pankos.alive(omar["id"]).secret
        # idle ones are stopped (idle limit 0 here), and start again on the next visit
        time.sleep(0.05)
        import asyncio
        stopped = asyncio.run(door.pankos.reap())
        assert set(stopped) == {amina["id"], omar["id"]}
        assert c1.get("/api/meta").json()["config"] is True
        # the account page offers her folder as a zip with her config in it
        z = c1.get("/host/account/export")
        assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
        import io
        import zipfile
        assert "panko/config/panko.toml" in zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert not door.pankos.running                                     # all stopped with the door
