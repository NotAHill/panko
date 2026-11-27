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


def test_the_anki_add_on_reaches_its_own_panko_on_a_device_code(data):
    """H3: a device code made on the account page lets the add-on (and only it) reach that user's Panko, at the
    add-on's three routes, never with the cookie; ended, it stops working. Codes are kept only as hashes."""
    import re
    a = host_app.app(data, idle_minutes=0)
    st = a.state.door.store
    amina = st.add_user("amina", PW)
    st.add_user("omar", PW)
    with TestClient(a, base_url="http://door.test", follow_redirects=False) as c, \
            TestClient(a, base_url="http://door.test", follow_redirects=False) as addon:
        post(c, "/host/login", {"name": "amina", "password": PW})
        r = c.post("/api/setup", json={"answers": {"language": "Iraqi Arabic", "varieties": ["iraqi-arabic"]}},
                   headers={"X-Panko": "1", "Origin": "http://door.test"})
        assert r.status_code == 200, r.text
        page = post(c, "/host/account/anki", {"name": "my laptop"})
        assert page.status_code == 200 and "it isn't shown again" in page.text
        code = re.search(r"pkd_[\w-]+", page.text).group(0)
        assert code.encode() not in (data / "host.db").read_bytes()
        assert "pkd_" not in c.get("/host/account").text and "my laptop" in c.get("/host/account").text
        assert post(c, "/host/account/anki", {"name": "x"}, origin="http://evil.test").status_code == 303
        bearer = {"Authorization": f"Bearer {code}"}
        got = addon.post("/anki/pull", json={"addon": 1, "page": 0}, headers=bearer)
        assert got.status_code == 200, got.text
        assert [m["name"] for m in got.json()["models"]] == ["Panko • Word (Iraqi Arabic)", "Panko • Phrase (Iraqi Arabic)"]
        assert addon.post("/anki/pull", json={"addon": 1}, headers=bearer).json()["notes"] == []
        # only the add-on's routes, only with a code: not the cookie, not the hub's API
        assert c.post("/anki/pull", json={"addon": 1, "page": 0}, headers={"Origin": "http://door.test"}).status_code == 401
        assert addon.get("/anki/setup", headers=bearer).status_code == 404
        assert addon.get("/api/meta", headers=bearer).status_code == 401
        assert addon.post("/anki/pull", json={"addon": 1}, headers={"Authorization": "Bearer pkd_nope"}).status_code == 401
        # the add-on file comes from the user's own Panko
        assert c.get("/addon/panko-sync.ankiaddon").headers["content-type"] == "application/zip"
        (dev,) = st.devices(amina["id"])
        assert dev["last_used"]
        post(c, f"/host/account/anki/{dev['id']}", {})
        assert addon.post("/anki/pull", json={"addon": 1, "page": 0}, headers=bearer).status_code == 401
        # a disabled account's codes stop too
        code2 = st.add_device(amina["id"], "desk")
        st.update(amina["id"], disabled=1)
        assert addon.post("/anki/pull", json={"addon": 1, "page": 0},
                          headers={"Authorization": f"Bearer {code2}"}).status_code == 401
