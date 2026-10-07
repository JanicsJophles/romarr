# ROMarr companion fork — work in progress

An experimental companion fork of the *arr for games, [BlizzHacker/ROMarr](https://github.com/BlizzHacker/romarr), adding a persistent request dashboard and optional conversational game discovery for a self-hosted library. This is not the original project or an official upstream release.

This candidate is **experimental**; its automated tests, isolated container/security checks, synthetic request-to-import staging and desktop/mobile visual checks pass. The tested scope and remaining operational limits are recorded in the release audit. No hosted service, content collection, credentials, provider subscription, or configured indexer is supplied. Operators configure their own integrations. The application can delegate acquisition and perform imports when those integrations are enabled; describing it as merely a passive catalogue would be inaccurate.

## Development

Use Python 3.13 in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

The default test selection excludes tests marked `network`. Custom request-state and game-chat tests use mocked services. Tests do not authorize downloading content or contacting an operator's services.

The source includes upstream Docker support, but no prebuilt image for this fork is published. ROM Hub execution is disabled and its external package is excluded from the image. The Python suite, isolated image scan and synthetic request-to-import checks pass; the release audit records their scope and artifacts.

See [request states and retry behavior](docs/REQUEST-STATES.md) for what statuses mean and when manual review is required.

## New capabilities

- Persisted request status across page refreshes, with client telemetry.
- Optional game discovery chat, checked against catalogue metadata.
- Companion API endpoints suitable for Thorpilot.

Chat requires operator-supplied AI-provider and catalogue credentials. The current adapter reads a private `/config/game-chat-key.json` file containing a `key` field. No such file is included. See [chat setup and privacy](docs/CHAT-SETUP.md) for exact configuration, data flow and current limitations.

## Attribution

Based on upstream commit `06378a70b94d8eb5646cd9720c52a992f5e2a09a`. Original copyright is **2026 MOVE WEIGHT**, with upstream authorship identified as **BlizzHacker (Wade)**. Upstream's MIT [LICENSE](LICENSE) and [NOTICE](NOTICE) are preserved unchanged. The MIT license permits modification and redistribution under its conditions; it does not establish permission to imply upstream endorsement or ownership of project branding.

See [the release audit](docs/RELEASE-AUDIT.md) and the archived [upstream README](docs/UPSTREAM-README.md) for provenance and remaining work. The archived README describes upstream, not verified features or deployment instructions for this fork.

## Upstream integration reference

The retained [installation reference](docs/INSTALL.md) and Proxmox scripts target upstream ROMarr, not this companion fork. Do not use them to install this candidate. Public source examples are retained for provenance and upstream regression checks; no operator configuration is included.

The core supports disc platforms including PlayStation, PlayStation 2, PSP, GameCube, Wii and Dreamcast, as well as cartridge systems. Browser play routes are optional integrations: EmulatorJS, Ruffle, js-dos and Emularity depend on configured external services and file compatibility. The companion does not bundle emulator cores, BIOS files, keys or games.

Additional inherited disc platform mappings include Saturn, Neo Geo CD and Amiga CD32. Optional play routes include a Download action for operator-managed files, Archive.org Emularity links, and an operator-supplied streaming service configured with `STREAM_SERVER_URL`. Listing a route does not guarantee a particular title runs or is available.

For an operator-configured GGrequestz integration, the receiving webhook is `REQUEST_WEBHOOK_URL=http://romarr:6868/api/v1/webhook/ggrequestz` (replace the example service address for your installation). `GGREQUESTZ_URL` goes the other direction: it is the link back to that UI, not request delivery. Review `request.auto_approve` before enabling inbound requests.

## Safe visual preview

`python scripts/preview_companion.py` serves the actual UI at `http://127.0.0.1:8792/#requests` with fictional demo/homebrew request rows. It is loopback-only, contains no service configuration, and rejects all mutations. This is a visual fixture, not a running acquisition service.
