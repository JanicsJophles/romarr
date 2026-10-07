# Security

ROMarr runs on home servers next to download clients, library servers and
private services, and it holds credentials for all of them. This document says
what it protects, what it does not, and how to report a problem.

It is written to be checkable. Where it claims a property, there is a test
named for it; where something is not protected, it says so plainly rather than
implying otherwise.

## Reporting a vulnerability

This fork is unpublished. Arrange a private channel with its maintainer before sharing sensitive details. Once private reporting is enabled on the fork repository, use its `security/advisories` page. Report upstream-only issues to upstream; do not send fork-specific private configuration to another project. Never include credentials in public issues.

CI runs only on the project-specific Atlas runner for reviewed same-repository branches. There is no public pull-request execution trigger. Never run unreviewed fork code with private runner access.

## Supported versions

This candidate has no supported release yet. The notes below describe inherited authentication behavior and known limitations, with plugin behavior narrowed by this fork.

**Anything at or below `v0.7.0` has no authentication at all** — its API
answers whoever reaches the port, on a service that queues downloads and writes
to the filesystem. If you installed from a release tarball on or before
2026-08-02, upgrade. The Proxmox installer refuses to deploy a build without
`romarr/auth.py`, and so does its updater — an update that silently replaces an
authenticated build with an open one is worse than an install that does,
because the operator has already decided the thing is safe to leave running.

## What ROMarr is

An acquisition and automation service. It searches indexers, hands releases to
a download client, verifies finished files against No-Intro and Redump DATs,
and files them into a library server.

That means it is **administrator-facing software**. It deliberately reaches
arbitrary operator-supplied addresses — your Prowlarr, your qBittorrent, your
RomM — and most of them are on RFC1918 addresses. ROMarr does not and will not
block private-range destinations, because doing so would break its entire
purpose. The boundary that matters is not "which addresses may be reached" but
"who may ask ROMarr to reach them", which is authentication.

## Authentication

Required by default. There is no configuration mistake that produces an open
install; the only way off is explicit.

- A fresh install is **unclaimed**: the first visit to the web UI sets the
  password. `POST /api/v1/setup` is open only while unclaimed and answers `409`
  afterwards, so it is a one-shot rather than a standing unauthenticated
  password reset.
- Setting `ROMARR_PASSWORD` or your own `ROMARR_API_KEY` claims the install
  before it serves a request, leaving no unclaimed window. This is what a
  container template should do.
- Passwords are hashed with scrypt (N=2^14, r=8, p=1), never stored plaintext.
- Browsers hold an HMAC-signed session cookie: `HttpOnly`, `SameSite=Strict`,
  `Path=/`. `SameSite=Strict` is what stands in for CSRF tokens — another site
  cannot make an authenticated request even if it knows the URL.
- The cookie is not `Secure`, because ROMarr is normally plain HTTP on a LAN
  and a `Secure` cookie would never be stored. Put it behind TLS if it leaves
  your network.
- API clients present `X-Api-Key`, `Authorization: Bearer` or `?apikey=`. The
  query form exists for senders that cannot set headers; it will appear in
  proxy logs, so prefer a header.
- TOTP (RFC 6238) gates interactive sign-in. It deliberately does not gate the
  API key: a script cannot be prompted, and a key is already high-entropy.
- Login is rate limited. Wrong credentials return `401` without revealing
  which of password or key was wrong.
- A state file ROMarr cannot **read** stops it starting. This is an
  authentication property, not a housekeeping one, and it was got wrong: an
  unreadable `romarr.json` — the normal result of a root-owned file under a
  container running as `PUID` — used to be treated the same as a corrupt one,
  so ROMarr started from defaults and saved over it. The API key was
  regenerated, the history emptied, and **the install came back unclaimed**, so
  the next person to reach the port set the password. That was a configuration
  mistake that produced an open install, and the paragraph above was therefore
  not true. It is now two guards: the Docker entrypoint owns `/config`
  recursively and refuses to start if the state file is still unreadable, and
  the application refuses to start on an unreadable state file however it was
  launched. A file that is merely *unparseable* still falls back to defaults,
  because nothing in it can be handed back.

Exactly ten routes answer without a credential, and no others (this count is
asserted against the code, not maintained by hand):

| Route | Why |
|---|---|
| `/` | Serves the sign-in or setup screen when you are not signed in, the app when you are. |
| `/login` | The sign-in screen. It has to answer somebody holding nothing. |
| `/link` | Where a peering invitation link lands. A **constant page** — see below. |
| `/api/v1/login` | Exchanges a password or key for a session. |
| `/api/v1/setup` | First-run claim. Open only while unclaimed; `409` after. |
| `/api/health` | Container health checks have no credential to offer. |
| `/api/v1/connect/steam/return` | Steam's OpenID redirect. It *cannot* carry the session cookie — see below. |
| `/api/v1/peer/accept` | A peer redeeming an invitation you minted. Carries the one-time secret or the claim code. |
| `/api/v1/peer/shelf` | A peer reading what you share. Requires peer id + token. |
| `/api/v1/peer/netplay` | A peer proposing a session. Requires peer id + token. |

**The three peer routes are open to the *session* gate and closed to
everyone without a peer credential.** They are called by another server,
not by a person with a browser, so requiring the operator's session cookie
would make federation impossible. Each authenticates differently instead:

- `/api/v1/peer/accept` requires the **one-time invitation secret** you
  minted and sent out of band, or the **short claim code** that is the other
  half of the same invitation. Either way it is single-use and compared in
  constant time. Redeeming it does not grant access to anything — the peer is
  held **unconfirmed** until you confirm it, so a leaked invitation is
  recoverable rather than final. See *Invitation links and claim codes*.
- `/api/v1/peer/shelf` and `/api/v1/peer/netplay` require an
  `X-Peer-Id` + `X-Peer-Token` pair issued to exactly one peer, compared
  in constant time. An unconfirmed peer authenticates as nobody, and a
  confirmed peer with the default `scope: none` sees an empty shelf, so
  neither route leaks anything by existing.

**`/link` is open because it is a constant.** It takes no parameters, reads
no invitation, touches no state and returns identical bytes to every caller.
It has to be open because the person opening it is *somebody else's* operator,
who has no account here — that is the entire situation the page exists for.
There is nothing behind it to ask, so there is nothing it can be made to say.

### Invitation links and claim codes

An invitation comes in two halves and only one of them is a secret.

- **The link** — `https://your-server/link#i=<invite id>&n=<name>` — carries
  no credential. Everything identifying it is in the **fragment**, which a
  browser never puts on the wire: it does not reach the inviting server's
  access log, it is not in the `Referer` header of whatever the recipient
  clicks next, and the request a chat client makes to render a link preview
  fetches the bare path and learns nothing. Losing this link loses nothing.
- **The claim code** — eight characters, e.g. `K7RM-9TFQ` — is the credential,
  and it is deliberately *not* in the link. URLs go to places credentials must
  not: browser history, the address bar of a shared screen, sync services,
  proxy logs, link unfurlers. So the half that authorises is the half a person
  types, and it can travel by a second channel — voice, SMS, another app.

Eight characters is about forty bits, which is small, so three things carry
the weight instead of length:

1. **The code expires in 15 minutes**, where the invitation itself lives 24
   hours. A code that sits in a chat log all day is a credential sitting in a
   chat log all day. Minting another is one click.
2. **Five wrong codes destroy the invitation.** Guessing is bounded at five
   attempts per invitation, not per address, because rate-limiting by address
   is defeated by having more addresses.
3. **Redeeming still grants nothing.** A correctly guessed code produces a row
   on your Friends page marked *awaiting your confirmation*, and nothing else.
   This is the same mutual-confirmation step that makes a leaked long secret
   recoverable, and it is what makes a short code safe to use at all.

Burning an invitation is also the alarm: the friend it was meant for finds it
gone and tells you, which is how you learn somebody was guessing.

`/api/v1/peer/accept` returns the long peer token to whoever completes the
handshake. That caller has just proved it holds this exact single-use
invitation, and the token it receives opens nothing until you confirm the
peer. It is how a claim code becomes a durable credential — short code in,
long token out, once.

Revocation is one-sided and immediate: deleting a peer invalidates its
token without that peer's cooperation, and touches no other peer's.

Relationships are persisted under `_peers`, tokens included, so they survive
a restart. That table is removed from the config endpoint **by name**,
alongside `_api_key` and `_password_hash` — not by a leading-underscore rule,
because several `_`-prefixed settings (`_romm_url`, `_prowlarr_url`) are
deliberately shown, and such a rule would have hidden the wrong half and
served the tokens. A test asserts no peer token appears in that response.
Invitations are deliberately *not* persisted: they expire in 24 hours, and
keeping them across a restart would only widen the window a leaked one is
useful for. That applies doubly to the wrong-guess counter, which lives on the
invitation — a restart that resurrected an invitation would reset its budget.

`/api/health` returns one bit unauthenticated — it used to return library paths
and client URLs, which is what a health check does not need.

**The Steam return is open because it has to be, and carries its own
credential instead.** The session cookie is `SameSite=Strict`, so when Steam
redirects the browser back to ROMarr the browser deliberately withholds it and
the request arrives with nothing. Loosening the cookie to `Lax` would fix that
one flow by weakening every other route against cross-site requests, so it is
not done. Instead the start of the flow — `/api/v1/connect/steam`, which *is*
authenticated — mints a `state`: 24 bytes of `secrets.token_urlsafe`, single
use, expiring in ten minutes. The return leg is refused without a live one, so
possession of it stands in for the cookie, and it can only have come from a
signed-in session.

Two further checks apply before anything is connected: the identity Steam
asserts must match `https://steamcommunity.com/openid/id/<17 digits>` exactly,
and the whole assertion is posted back to Steam with `check_authentication` and
must come back `is_valid:true`. The parameters arrive through the user's
browser and are treated as attacker-controlled until Steam itself confirms
them.

### `ROMARR_AUTH=disabled`

Turns the gate off. **Anything reaching the port is then in, including a
request that bypassed your proxy.** If something in front already
authenticates, prefer `ROMARR_AUTH=forward`, which keeps that proxy as the
authority but verifies the request actually came through it.

Forward mode requires `ROMARR_TRUSTED_PROXIES`. Identity headers are only
believed from those CIDRs, checked against the socket peer address — never
against `X-Forwarded-For`, which anybody can set. Without the CIDR list,
forward auth would be a header anyone could send.

## Filesystem

ROMarr writes files whose names come from torrents, which are attacker
controlled.

- Every archive member is checked to resolve inside the destination before
  extraction — zip, 7z and rar alike. The check lives above the format
  readers, not inside the zip one, because the format an attacker picks is the
  one with the gap.
- Members failing the check are **dropped, not sanitised**: a release that
  needs sanitising is not one to trust.
- Multi-file sets are flattened to base names, so a set cannot traverse out of
  the directory it was given — safe by construction rather than by check.
- Existing files are never overwritten unless explicitly asked.
- Remote path mappings translate what a download client reports into what
  ROMarr can see. They are operator configuration, not attacker input.

## Secrets

- The config API masks every credential; a value is masked by field type, so a
  secret left behind after changing a provider's type is still masked.
- Backups exclude secrets unless `?secrets=1` is passed explicitly.
- The API key is stored under a leading underscore so it is structurally
  outside what `safe_settings` will serialise, rather than relying on a
  maintained list.
- Unexpected errors return a generic API message. Server logs and upstream service error paths still require review for credential redaction; do not publish raw logs.
- Neither unauthenticated page ever contains the API key.

## Plugins

ROM Hub catalogue loading, installation, enabling, and execution are disabled in this companion build. The external ROM Hub package is not installed by its Dockerfile. The old `ROM_HUB_ALLOW_UNSANDBOXED` fallback is removed. There is no environment override to re-enable plugin execution. This is a disabled capability, not a claim that plugin confinement is real but partial.

## Dependencies

ROMarr's own code is Python standard library plus `requests`. The small
surface is deliberate: fewer dependencies is fewer supply-chain paths.

## What is not protected

Stated so nobody assumes otherwise:

- **No filesystem confinement for the main service.** Plugins are disabled; the main process can access files allowed by its operating-system account.
- **No protection against a malicious library or indexer you configured.**
  ROMarr trusts responses from services you pointed it at.
- **No encryption at rest.** `romarr.json` and `.env` hold credentials in
  plaintext; they are `chmod 600` and rely on filesystem permissions.
- **No multi-user model.** There is one operator. Forward auth can require a
  group, but ROMarr does not distinguish users or keep per-user permissions.
- **No audit log of who did what**, because there is no "who".
- **No rate limiting on the API generally** — only on login.
- **The Sunshine admin credential travels over an unverified TLS
  connection.** Sunshine generates its own certificate on first run and
  nobody signs it, so ROMarr disables certificate verification to talk to
  `https://<host>:47990` at all. That connection is encrypted and **not
  authenticated**: anything already on the path between ROMarr and the host
  can impersonate it and collect `MOONLIGHT_PASS`. There is no fix available
  from ROMarr's side — pinning would need a certificate the operator has no
  way to supply — so treat that credential as LAN-only, and give Sunshine an
  admin password you do not use anywhere else. Wolf has no equivalent
  exposure: its API is a UNIX socket, and ROMarr sends it no credential.
- **Wolf's API is a full-privilege API and ROMarr does not narrow it.** Wolf's
  own documentation says that through it "you can pair clients to the server,
  execute arbitrary commands, and more". Setting `WOLF_SOCKET_PATH` or
  `WOLF_API_URL` gives ROMarr — and anything that can reach ROMarr's own
  process — that level of access to the host. ROMarr calls four read
  endpoints and one pairing endpoint, but nothing structurally confines it to
  those.
- **DAT verification is an integrity check, not a security control.** It tells
  you a file matches a known-good dump. It is not malware scanning, and an
  UNKNOWN verdict means "not in your DAT", not "dangerous".
