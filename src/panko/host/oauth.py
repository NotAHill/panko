"""Chat mode on the server (H4): the front door is an OAuth 2.1 authorisation server, so the learner's own Claude
(claude.ai, Claude Desktop, Claude Code) can use their Panko's MCP tools at `<site>/mcp`.

How a Claude connects (the MCP authorisation spec):
1. It calls `/mcp` without a token and gets 401 with a link to `/.well-known/oauth-protected-resource`, which names
   this site as the authorisation server; `/.well-known/oauth-authorization-server` lists the endpoints.
2. It registers (`/register`, dynamic client registration), or uses an https URL as its client id that points to its
   metadata document (fetched here, from public addresses only).
3. It sends the learner to `/authorize` with a PKCE challenge. They sign in as usual and say yes on a consent page
   that names the app and where it sends them back.
4. It trades the code for tokens at `/token`: an access token (1 hour) and a refresh token (30 days, replaced each
   time it's used). `/mcp` takes the access token only, never the session cookie, and passes the call to the user's
   own Panko.

Every connection is a grant the learner sees on their account page and can end. Codes and tokens are stored only as
SHA-256 hashes. A code used twice ends the grant it belongs to (someone copied it). Disabling an account, deleting
it or changing its password ends its grants."""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit

SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (
    id TEXT PRIMARY KEY, secret TEXT, name TEXT NOT NULL DEFAULT '', redirect_uris TEXT NOT NULL,
    auth_method TEXT NOT NULL DEFAULT 'none', metadata_doc INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_grants (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, client_id TEXT NOT NULL,
    client_name TEXT NOT NULL DEFAULT '', redirect_uri TEXT NOT NULL DEFAULT '', created REAL NOT NULL, last_used REAL);
CREATE TABLE IF NOT EXISTS oauth_codes (
    code TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES oauth_grants(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS oauth_tokens (
    token TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES oauth_grants(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, expires REAL NOT NULL);
"""

SCOPE = "panko"
CODE_SECONDS = 600
ACCESS_SECONDS = 3600
REFRESH_DAYS = 30
AUTH_METHODS = ("none", "client_secret_post", "client_secret_basic")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class OAuthError(Exception):
    """An answer in OAuth's own error format (RFC 6749 §5.2)."""

    def __init__(self, error: str, description: str = "", status: int = 400):
        super().__init__(description or error)
        self.error, self.description, self.status = error, description, status

    def body(self) -> dict:
        return {"error": self.error, **({"error_description": self.description} if self.description else {})}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def redirect_ok(uri: str) -> bool:
    """https anywhere, or http back to this computer (apps like Claude Code listen on a local port). No fragments."""
    try:
        u = urlsplit(uri)
    except ValueError:
        return False
    if u.fragment or not u.hostname:
        return False
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in LOOPBACK)


def same_redirect(given: str, registered: str) -> bool:
    """Exact match, except that a loopback address may use any port (RFC 8252 §7.3)."""
    if given == registered:
        return True
    a, b = urlsplit(given), urlsplit(registered)
    return (a.scheme == b.scheme == "http" and a.hostname in LOOPBACK and a.hostname == b.hostname
            and a.path == b.path and a.query == b.query)


class OAuth:
    """The records behind the endpoints, in the front door's `host.db`."""

    def __init__(self, store):
        self.db = store.db          # the tables are made with the store's own

    # ---- clients
    def register(self, meta: dict) -> dict:
        """Dynamic client registration (RFC 7591): public clients, or ones with a secret if they ask for one."""
        uris = meta.get("redirect_uris")
        if not isinstance(uris, list) or not uris or not all(isinstance(u, str) and redirect_ok(u) for u in uris):
            raise OAuthError("invalid_redirect_uri", "redirect_uris: https addresses, or http on this computer")
        method = meta.get("token_endpoint_auth_method") or "none"
        if method not in AUTH_METHODS:
            raise OAuthError("invalid_client_metadata", f"token_endpoint_auth_method: one of {', '.join(AUTH_METHODS)}")
        grants = meta.get("grant_types") or ["authorization_code", "refresh_token"]
        if "authorization_code" not in grants:
            raise OAuthError("invalid_client_metadata", "grant_types must include authorization_code")
        name = str(meta.get("client_name") or "")[:100]
        cid = "pc_" + secrets.token_urlsafe(18)
        secret = secrets.token_urlsafe(32) if method != "none" else None
        now = time.time()
        with self.db:
            self.db.execute("DELETE FROM oauth_clients WHERE metadata_doc = 0 AND created < ? AND id NOT IN "
                            "(SELECT client_id FROM oauth_grants)", (now - 86400,))     # registered, never used
            self.db.execute("INSERT INTO oauth_clients (id, secret, name, redirect_uris, auth_method, created) "
                            "VALUES (?, ?, ?, ?, ?, ?)", (cid, _hash(secret) if secret else None, name,
                                                          json.dumps(uris), method, now))
        out = {"client_id": cid, "client_id_issued_at": int(now), "client_name": name, "redirect_uris": uris,
               "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
               "token_endpoint_auth_method": method}
        if secret:
            out |= {"client_secret": secret, "client_secret_expires_at": 0}
        return out

    def client(self, cid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM oauth_clients WHERE id = ?", (cid or "",)).fetchone()
        if not r:
            return None
        return dict(r) | {"redirect_uris": json.loads(r["redirect_uris"])}

    def remember_document(self, cid: str, doc: dict) -> dict:
        """A client whose id is the https address of its metadata document (fetched by the caller)."""
        if doc.get("client_id") != cid:
            raise OAuthError("invalid_client", "the metadata document's client_id isn't its own address")
        uris = doc.get("redirect_uris")
        if not isinstance(uris, list) or not uris or not all(isinstance(u, str) and redirect_ok(u) for u in uris):
            raise OAuthError("invalid_client", "the metadata document's redirect_uris aren't usable")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO oauth_clients (id, secret, name, redirect_uris, auth_method, "
                            "metadata_doc, created) VALUES (?, NULL, ?, ?, 'none', 1, ?)",
                            (cid, str(doc.get("client_name") or urlsplit(cid).hostname or "")[:100], json.dumps(uris),
                             time.time()))
        return self.client(cid)

    def client_ok(self, c: dict, secret: str | None) -> bool:
        if c["auth_method"] == "none":
            return True
        return bool(secret) and bool(c["secret"]) and secrets.compare_digest(_hash(secret), c["secret"])

    # ---- the learner says yes: a grant and a code
    def approve(self, user_id: str, c: dict, redirect_uri: str, challenge: str) -> str:
        gid = "g" + secrets.token_hex(8)
        code = secrets.token_urlsafe(32)
        now = time.time()
        with self.db:
            self.db.execute("DELETE FROM oauth_codes WHERE expires < ?", (now - 86400,))
            self.db.execute("INSERT INTO oauth_grants (id, user_id, client_id, client_name, redirect_uri, created) "
                            "VALUES (?, ?, ?, ?, ?, ?)", (gid, user_id, c["id"], c["name"], redirect_uri, now))
            self.db.execute("INSERT INTO oauth_codes (code, grant_id, redirect_uri, challenge, expires) VALUES "
                            "(?, ?, ?, ?, ?)", (_hash(code), gid, redirect_uri, challenge, now + CODE_SECONDS))
        return code

    # ---- tokens
    def _issue(self, gid: str) -> dict:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        with self.db:
            self.db.execute("DELETE FROM oauth_tokens WHERE expires < ?", (now,))
            self.db.execute("INSERT INTO oauth_tokens (token, grant_id, kind, expires) VALUES (?, ?, 'access', ?)",
                            (_hash(access), gid, now + ACCESS_SECONDS))
            self.db.execute("INSERT INTO oauth_tokens (token, grant_id, kind, expires) VALUES (?, ?, 'refresh', ?)",
                            (_hash(refresh), gid, now + REFRESH_DAYS * 86400))
        return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_SECONDS,
                "refresh_token": refresh, "scope": SCOPE}

    def _grant_of(self, gid: str) -> dict | None:
        r = self.db.execute("SELECT g.* FROM oauth_grants g JOIN users u ON u.id = g.user_id WHERE g.id = ? AND "
                            "u.disabled = 0", (gid,)).fetchone()
        return dict(r) if r else None

    def exchange(self, c: dict, code: str, redirect_uri: str, verifier: str) -> dict:
        r = self.db.execute("SELECT * FROM oauth_codes WHERE code = ?", (_hash(code or ""),)).fetchone()
        if not r:
            raise OAuthError("invalid_grant", "unknown code")
        g = self._grant_of(r["grant_id"])
        if r["used"]:                    # a code used twice: someone else has it, so the grant ends
            self.end_grant(r["grant_id"])
            raise OAuthError("invalid_grant", "code already used")
        with self.db:
            self.db.execute("UPDATE oauth_codes SET used = 1 WHERE code = ?", (r["code"],))
        if not g or g["client_id"] != c["id"]:
            raise OAuthError("invalid_grant", "the code wasn't issued to this client")
        if r["expires"] < time.time():
            raise OAuthError("invalid_grant", "the code has expired")
        if redirect_uri != r["redirect_uri"]:
            raise OAuthError("invalid_grant", "redirect_uri isn't the one given to /authorize")
        if not verifier or not secrets.compare_digest(s256(verifier), r["challenge"]):
            raise OAuthError("invalid_grant", "PKCE: the code_verifier doesn't match")
        return self._issue(g["id"])

    def refresh(self, c: dict, token: str) -> dict:
        r = self.db.execute("SELECT * FROM oauth_tokens WHERE token = ? AND kind = 'refresh' AND expires > ?",
                            (_hash(token or ""), time.time())).fetchone()
        g = self._grant_of(r["grant_id"]) if r else None
        if not g or g["client_id"] != c["id"]:
            raise OAuthError("invalid_grant", "unknown or expired refresh token")
        with self.db:
            self.db.execute("DELETE FROM oauth_tokens WHERE token = ?", (r["token"],))     # used once, replaced
        return self._issue(g["id"])

    def user_for(self, access: str) -> tuple[dict, dict] | None:
        """(user, grant) for a valid access token."""
        r = self.db.execute(
            "SELECT g.id AS gid, g.client_name, g.last_used, u.* FROM oauth_tokens t JOIN oauth_grants g ON "
            "g.id = t.grant_id JOIN users u ON u.id = g.user_id WHERE t.token = ? AND t.kind = 'access' AND "
            "t.expires > ? AND u.disabled = 0", (_hash(access or ""), time.time())).fetchone()
        if not r:
            return None
        d = dict(r)
        grant = {"id": d.pop("gid"), "client_name": d.pop("client_name"), "last_used": d.pop("last_used")}
        if time.time() - (grant["last_used"] or 0) > 60:
            with self.db:
                self.db.execute("UPDATE oauth_grants SET last_used = ? WHERE id = ?", (time.time(), grant["id"]))
        return d, grant

    def revoke(self, token: str) -> None:
        """RFC 7009: ends the grant the token belongs to (both kinds); unknown tokens are fine."""
        r = self.db.execute("SELECT grant_id FROM oauth_tokens WHERE token = ?", (_hash(token or ""),)).fetchone()
        if r:
            self.end_grant(r["grant_id"])

    # ---- what the account page shows
    def grants(self, user_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, client_name, redirect_uri, created, last_used FROM oauth_grants WHERE user_id = ? "
            "AND EXISTS (SELECT 1 FROM oauth_tokens t WHERE t.grant_id = oauth_grants.id AND t.expires > ?) "
            "ORDER BY created DESC", (user_id, time.time()))]

    def end_grant(self, gid: str, user_id: str | None = None) -> None:
        with self.db:
            if user_id:
                self.db.execute("DELETE FROM oauth_grants WHERE id = ? AND user_id = ?", (gid, user_id))
            else:
                self.db.execute("DELETE FROM oauth_grants WHERE id = ?", (gid,))

    def end_all(self, user_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM oauth_grants WHERE user_id = ?", (user_id,))


# ---- metadata documents

def protected_resource(base: str) -> dict:
    """RFC 9728: what `/mcp` is and who issues its tokens."""
    return {"resource": f"{base}/mcp", "authorization_servers": [base], "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"], "resource_name": "Panko"}


def authorization_server(base: str) -> dict:
    """RFC 8414."""
    return {"issuer": base, "authorization_endpoint": f"{base}/authorize", "token_endpoint": f"{base}/token",
            "registration_endpoint": f"{base}/register", "revocation_endpoint": f"{base}/revoke",
            "scopes_supported": [SCOPE], "response_types_supported": ["code"], "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": list(AUTH_METHODS),
            "revocation_endpoint_auth_methods_supported": list(AUTH_METHODS),
            "code_challenge_methods_supported": ["S256"], "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True}


def back_to(redirect_uri: str, **params) -> str:
    sep = "&" if urlsplit(redirect_uri).query else "?"
    return redirect_uri + sep + urlencode({k: v for k, v in params.items() if v})


def document_url_ok(cid: str) -> bool:
    """A client id that is a metadata document's address: https, a path, a public host (never this server's own
    network)."""
    try:
        u = urlsplit(cid)
    except ValueError:
        return False
    if u.scheme != "https" or not u.hostname or u.path in ("", "/") or u.fragment or u.username or u.password:
        return False
    host = u.hostname
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        return "." in host and not host.endswith((".local", ".internal", ".localhost", ".lan", ".home.arpa"))


async def fetch_document(cid: str) -> dict:
    """The client's metadata document, at most 64 KB, without following redirects. The address it resolves to must be
    public too (no reaching into the server's network through DNS)."""
    import asyncio
    import socket

    import httpx
    if not document_url_ok(cid):
        raise OAuthError("invalid_client", "client_id: unknown client")
    host = urlsplit(cid).hostname
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as ex:
        raise OAuthError("invalid_client", f"couldn't look up {host}") from ex
    if not infos or not all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos):
        raise OAuthError("invalid_client", "the client's address isn't public")
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as c:
            async with c.stream("GET", cid, headers={"Accept": "application/json"}) as r:
                if r.status_code != 200:
                    raise OAuthError("invalid_client", f"the client's metadata document answered {r.status_code}")
                body = b""
                async for chunk in r.aiter_bytes():
                    body += chunk
                    if len(body) > 65536:
                        raise OAuthError("invalid_client", "the client's metadata document is too large")
        doc = json.loads(body)
    except (httpx.HTTPError, ValueError) as ex:
        raise OAuthError("invalid_client", "couldn't read the client's metadata document") from ex
    if not isinstance(doc, dict):
        raise OAuthError("invalid_client", "the client's metadata document isn't an object")
    return doc
