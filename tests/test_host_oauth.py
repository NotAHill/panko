"""Chat mode on the server (H4): the front door as an OAuth server for the learner's own Claude, and `/mcp` reached
with its token only. The full run starts a real Panko and calls its MCP tools through the door."""
import base64
import hashlib
import os
import secrets
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("starlette")
pytest.importorskip("argon2")
pytest.importorskip("mcp")

from starlette.testclient import TestClient  # noqa: E402

from panko.host import app as host_app  # noqa: E402
from panko.host import oauth  # noqa: E402

PW = "a-long-test-password"
BASE = "https://door.test"
CB = "https://claude.example/api/mcp/auth_callback"
MCP_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json",
               "mcp-protocol-version": "2025-06-18"}


@pytest.fixture
def data():
    d = Path(tempfile.mkdtemp(prefix="pko-", dir="/tmp" if os.path.isdir("/tmp") else None))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def no_limits():
    host_app.FAILS.clear()
    host_app.REGISTERED.clear()
    yield


def door(data):
    a = host_app.app(data, base_url=BASE, idle_minutes=0)
    a.state.door.store.add_user("amina", PW)
    return a


def client(a):
    return TestClient(a, base_url=BASE, follow_redirects=False)


def sign_in(c):
    r = c.post("/host/login", data={"name": "amina", "password": PW}, headers={"Origin": BASE})
    assert r.status_code == 303


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def register(c, **extra):
    r = c.post("/register", json={"client_name": "Claude", "redirect_uris": [CB], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def get_code(c, cid, challenge, redirect=CB, state="st-1"):
    q = {"response_type": "code", "client_id": cid, "redirect_uri": redirect, "code_challenge": challenge,
         "code_challenge_method": "S256", "state": state, "resource": f"{BASE}/mcp"}
    page = c.get("/authorize", params=q)
    assert page.status_code == 200 and "connect Claude?" in page.text, page.text[:300]
    dest = urlsplit(redirect)
    assert f"form-action 'self' {dest.scheme}://{dest.netloc};" in page.headers["content-security-policy"]
    r = c.post("/authorize", data={**q, "do": "allow"}, headers={"Origin": BASE})
    assert r.status_code == 303
    back = urlsplit(r.headers["location"])
    got = parse_qs(back.query)
    assert f"{back.scheme}://{back.netloc}{back.path}" == redirect and got["state"] == [state]
    assert got["iss"] == [BASE]
    return got["code"][0]


def tokens(c, cid, code, verifier, redirect=CB):
    return c.post("/token", data={"grant_type": "authorization_code", "client_id": cid, "code": code,
                                  "redirect_uri": redirect, "code_verifier": verifier})


def rpc(c, token, method, params=None, n=1):
    return c.post("/mcp", headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
                  json={"jsonrpc": "2.0", "id": n, "method": method, **({"params": params} if params else {})})


# ---- discovery

def test_mcp_without_a_token_points_to_the_metadata(data):
    a = door(data)
    c = client(a)
    sign_in(c)                                   # the session cookie is no use here
    r = c.post("/mcp", headers=MCP_HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"' in r.headers["www-authenticate"]
    pr = c.get("/.well-known/oauth-protected-resource/mcp").json()
    assert pr["resource"] == f"{BASE}/mcp" and pr["authorization_servers"] == [BASE]
    asm = c.get("/.well-known/oauth-authorization-server").json()
    assert asm["issuer"] == BASE and asm["code_challenge_methods_supported"] == ["S256"]
    assert asm["registration_endpoint"] == f"{BASE}/register" and asm["client_id_metadata_document_supported"]
    assert c.options("/token").headers["access-control-allow-origin"] == "*"


def test_registration_takes_only_safe_redirects(data):
    c = client(door(data))
    for bad in (["http://claude.example/cb"], ["https://x.example/cb#frag"], ["javascript:alert(1)"], [], "x"):
        assert c.post("/register", json={"redirect_uris": bad}).status_code == 400
    ok = register(c, redirect_uris=["http://127.0.0.1:33418/callback"])
    assert ok["client_id"].startswith("pc_") and "client_secret" not in ok
    with_secret = register(c, token_endpoint_auth_method="client_secret_post")
    assert with_secret["client_secret"]


# ---- the whole run, with a real Panko behind the door

def test_claude_connects_and_uses_the_tools(data):
    a = door(data)
    with TestClient(a, base_url=BASE, follow_redirects=False) as c:
        cid = register(c)["client_id"]
        verifier, challenge = pkce()
        # signed out: sent to sign in first, and back here after
        q = {"response_type": "code", "client_id": cid, "redirect_uri": CB, "code_challenge": challenge,
             "code_challenge_method": "S256", "state": "s"}
        r = c.get("/authorize", params=q)
        assert r.status_code == 303 and r.headers["location"].startswith("/host/login?next=%2Fauthorize%3F")
        nxt = parse_qs(urlsplit(r.headers["location"]).query)["next"][0]
        r = c.post("/host/login?next=" + __import__("urllib.parse").parse.quote(nxt, safe=""),
                   data={"name": "amina", "password": PW}, headers={"Origin": BASE})
        assert r.status_code == 303 and r.headers["location"] == nxt
        code = get_code(c, cid, challenge)
        t = tokens(c, cid, code, verifier)
        assert t.status_code == 200, t.text
        t = t.json()
        assert t["token_type"] == "Bearer" and t["expires_in"] == 3600 and t["refresh_token"]
        assert t["access_token"].encode() not in (data / "host.db").read_bytes()
        # the tools, from her own Panko
        init = rpc(c, t["access_token"], "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                       "clientInfo": {"name": "t", "version": "1"}})
        assert init.status_code == 200, init.text
        assert init.json()["result"]["serverInfo"]["name"] == "panko"
        uid = a.state.door.store.by_name("amina")["id"]
        chat = data / "users" / uid / "data" / "work" / "chat.json"
        assert '"connect"' in chat.read_text()          # the hub shows chat mode once Claude connects
        names = {x["name"] for x in rpc(c, t["access_token"], "tools/list", n=2).json()["result"]["tools"]}
        assert {"panko_guide", "panko_sources", "panko_submit"} <= names
        sync = rpc(c, t["access_token"], "tools/call", {"name": "panko_sync", "arguments": {}}, n=3).json()
        assert sync["result"]["isError"] and "apkg" in sync["result"]["content"][0]["text"]
        # the account page lists the connection
        assert "connected apps" in c.get("/host/account").text and f"{BASE}/mcp" in c.get("/host/account").text
        # refresh: a new pair, and the old refresh token is spent
        r2 = c.post("/token", data={"grant_type": "refresh_token", "client_id": cid,
                                    "refresh_token": t["refresh_token"]}).json()
        assert r2["access_token"] != t["access_token"]
        again = c.post("/token", data={"grant_type": "refresh_token", "client_id": cid,
                                       "refresh_token": t["refresh_token"]})
        assert again.status_code == 400 and again.json()["error"] == "invalid_grant"
        # ending the connection from the account page cuts it off
        gid = a.state.door.oauth.grants(a.state.door.store.by_name("amina")["id"])[0]["id"]
        c.post(f"/host/account/connection/{gid}", headers={"Origin": BASE})
        assert rpc(c, r2["access_token"], "tools/list").status_code == 401


# ---- what must fail

def test_the_code_needs_its_verifier_and_works_once(data):
    c = client(door(data))
    sign_in(c)
    cid = register(c)["client_id"]
    verifier, challenge = pkce()
    code = get_code(c, cid, challenge)
    assert tokens(c, cid, code, "not-the-verifier-" + "x" * 30).json()["error"] == "invalid_grant"
    code = get_code(c, cid, challenge)
    assert tokens(c, cid, code, verifier, redirect=CB + "/other").json()["error"] == "invalid_grant"
    code = get_code(c, cid, challenge)
    first = tokens(c, cid, code, verifier).json()
    assert tokens(c, cid, code, verifier).json()["error"] == "invalid_grant"          # used twice …
    assert rpc(c, first["access_token"], "tools/list").status_code == 401             # … ends the grant
    other = register(c)["client_id"]
    code = get_code(c, cid, challenge)
    assert tokens(c, other, code, verifier).json()["error"] == "invalid_grant"        # another app's code


def test_consent_is_checked(data):
    c = client(door(data))
    sign_in(c)
    cid = register(c)["client_id"]
    _, challenge = pkce()
    q = {"response_type": "code", "client_id": cid, "code_challenge": challenge, "code_challenge_method": "S256"}
    bad = c.get("/authorize", params={**q, "redirect_uri": "https://evil.example/cb"})
    assert bad.status_code == 400 and "location" not in bad.headers                   # never sent to a stranger
    assert c.get("/authorize", params={**q, "client_id": "nobody", "redirect_uri": CB}).status_code == 400
    plain = c.get("/authorize", params={**q, "redirect_uri": CB, "code_challenge_method": "plain"})
    assert "error=invalid_request" in plain.headers["location"]
    r = c.post("/authorize", data={**q, "redirect_uri": CB, "do": "allow"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    no = c.post("/authorize", data={**q, "redirect_uri": CB, "do": "deny"}, headers={"Origin": BASE})
    assert "error=access_denied" in no.headers["location"]


def test_disabling_or_a_new_password_ends_connections(data):
    a = door(data)
    c = client(a)
    sign_in(c)
    cid = register(c)["client_id"]
    verifier, challenge = pkce()
    t = tokens(c, cid, get_code(c, cid, challenge), verifier).json()
    st, uid = a.state.door.store, a.state.door.store.by_name("amina")["id"]
    st.set_password(uid, PW + "-new")
    assert a.state.door.oauth.user_for(t["access_token"]) is None
    sign_in_new = c.post("/host/login", data={"name": "amina", "password": PW + "-new"}, headers={"Origin": BASE})
    assert sign_in_new.status_code == 303
    t = tokens(c, cid, get_code(c, cid, challenge), verifier).json()
    st.update(uid, disabled=1)
    assert a.state.door.oauth.user_for(t["access_token"]) is None


def test_loopback_apps_may_use_any_port_and_secret_clients_need_their_secret(data):
    c = client(door(data))
    sign_in(c)
    cid = register(c, redirect_uris=["http://127.0.0.1:1111/callback"])["client_id"]
    verifier, challenge = pkce()
    code = get_code(c, cid, challenge, redirect="http://127.0.0.1:2222/callback")
    assert tokens(c, cid, code, verifier, redirect="http://127.0.0.1:2222/callback").status_code == 200
    reg = register(c, token_endpoint_auth_method="client_secret_basic")
    code = get_code(c, reg["client_id"], challenge)
    assert tokens(c, reg["client_id"], code, verifier).status_code == 401
    code = get_code(c, reg["client_id"], challenge)
    basic = base64.b64encode(f"{reg['client_id']}:{reg['client_secret']}".encode()).decode()
    r = c.post("/token", headers={"Authorization": f"Basic {basic}"}, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": CB, "code_verifier": verifier})
    assert r.status_code == 200, r.text


def test_metadata_document_addresses_must_be_public():
    ok = oauth.document_url_ok
    assert ok("https://claude.ai/oauth/claude-code-client-metadata")
    for bad in ("http://claude.ai/x", "https://claude.ai", "https://127.0.0.1/x", "https://10.0.0.2/x",
                "https://printer.local/x", "https://user:pw@claude.ai/x", "https://[::1]/x"):
        assert not ok(bad), bad
    assert oauth.same_redirect("http://localhost:5/cb", "http://localhost:9/cb")
    assert not oauth.same_redirect("https://a.example:5/cb", "https://a.example:9/cb")
    assert not oauth.same_redirect("http://localhost:5/cb2", "http://localhost:9/cb")
