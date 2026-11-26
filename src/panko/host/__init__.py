"""The front door of a hosted Panko (docs/SPEC-hosted.md): accounts, invites and admin, each user's own Panko
started on demand behind it, and everything else proxied to that Panko over its Unix socket.

`panko host serve` runs it; Caddy in front gives it HTTPS. Modules: `store` (users, invites, sessions in
`<data>/host.db`), `pankos` (start and stop each user's Panko), `app` (the routes and the proxy), `pages` (HTML)."""
