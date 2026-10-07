# Optional game discovery chat

Chat is optional. Library and request management work without an AI provider. This adapter currently supports Gemini with IGDB catalogue verification; it does not support arbitrary model providers. No provider keys or accounts ship with the project.

## Enable it on your own instance

1. Configure an IGDB metadata provider in ROMarr's settings using your own credentials. The chat adapter uses that provider to verify suggested titles and platforms and to obtain cover metadata.
2. Create `game-chat-key.json` in the host directory mounted at `/config`. Its contents are a JSON object with a single `key` string holding your own Gemini API key. Edit this file locally; do not put it in the repository, an issue, screenshot or chat transcript. Restrict its permissions to `0600` and ensure the container's configured user can read it. The normal entrypoint assigns the configuration directory to `PUID:PGID`.
3. Open **Find games** and ask a short question. The adapter uses the configured Gemini account and the model currently named in `romarr/chat.py`; account availability, provider quotas and catalogue lookup can fail independently.
4. Review suggestions yourself. Chat does not start a download or change your device. The separate release-search and explicit request actions use only the services you have configured.

The UI currently has no provider-key editor or connection-test screen. File-based configuration is intentional for this initial adapter; if the key file is absent, unreadable or invalid, chat returns a generic unavailable message. Other features continue to work. To disable chat, remove the key file and clear the conversation in the browser. Restarting is not required because the adapter reads the file for each request.

## Information sent and retained

- Clicking Send transmits the recent user/assistant conversation to your ROMarr server and then to the configured Gemini provider. The server includes its game-discovery instructions. Do not put credentials or sensitive personal information in chat.
- Suggested game titles and platform constraints are queried against IGDB. The server checks its own library locally to label matching titles as already owned. It does not send game files, download-client credentials or indexer keys to the model.
- The browser retains the conversation in session storage. Clear chat to remove that local conversation. Thorpilot maintains its own app-local history; clearing one client does not clear the other.
- This adapter does not deliberately persist conversation bodies on the ROMarr server. Your reverse proxy, debugging tools and provider may have separate logging/retention behavior. Review and configure those services yourself; clearing local chat cannot erase their records.
- Provider billing, availability and data-handling terms belong to the operator's account. There is no project-operated proxy, shared AI account or central telemetry service.

## API and limits

`POST /api/v1/game-chat` uses the same authenticated API gate as other administrator actions. Accepts `messages`, an array of 1–20 objects containing `role` (`user` or `assistant`) and `content` (1–3000 characters). The final message must be from the user; serialized bodies over 64,000 bytes are rejected.

Success returns `reply`, up to five verified `games`, and an `unverified` count. A provider or catalogue failure can return HTTP 200 with an `error` field, so clients must inspect that field rather than treating every 200 as an answer. The adapter allows two concurrent chats and no model-initiated tools. Recommendations are not proof of availability, authorization, or emulator compatibility.
