# Request state and retry behavior

The Requests page combines durable request/queue records with read-only client telemetry. An accepted handoff does not mean game bytes have arrived. `metadata` means waiting for torrent metadata; `downloaded` means the client finished but library import is still pending; only `imported` means the library import completed.

The current telemetry adapters support qBittorrent and SABnzbd. Other configured client types retain their normal import behavior but may have less detailed progress reporting. Client timeouts or missing matches display status unavailable rather than asserting a failed release or successful transfer.

SABnzbd's explicit Failed history is reconciled into durable queue/history state during scheduled import polls and Requests refreshes. Release identity, indexer and client label are retained; raw failure messages and nested source URLs are not sent to the browser. Imported rows cannot be downgraded by old failure history. Ambiguous legacy rows sharing a release title are not guessed.

A client-reported failure or refused handoff requires review before automatic searches can retry it. That hold persists across restart. The scheduler and RSS matching skip held requests and existing active downloads. Use the explicit manual search/request flow after checking the client; no replacement is started merely because you viewed status.

Elapsed time, stalled peers, missing metadata and unavailable clients do not prove a bad release. These conditions never create a blocklist entry or automatic replacement. Older timer/rejection failure flags are also excluded from automatic retirement. Verified content failures, such as an imported archive containing no ROMs, retain the existing configured blocklist/replacement behavior.

New SABnzbd requests retain the single `nzo_id` returned by submission. New qBittorrent magnet requests retain their v1 BTIH infohash (hexadecimal or base32 magnets). These IDs survive restart and are used with the client label for progress, failure reconciliation, and import selection. A renamed download still matches its ID; an old same-title attempt with a different ID does not. If an ID was saved, missing or mismatched client IDs never fall back to title matching. Submission still happens only once.

Older records, other client adapters, qBittorrent HTTP torrent URLs, and submissions without one unambiguous returned ID retain a conservative legacy fallback: client label and release title must identify a unique match. This is not universal job tracking. Multiple configured instances with the same client label are not independently identified yet. Client histories are bounded to recent entries; keep them until imports/reconciliation complete and inspect the client when status is ambiguous.

API references: [SABnzbd addurl and history](https://sabnzbd.org/wiki/advanced/api), [qBittorrent WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-4.1%29).

The request-list response also includes optional `client_warnings`, a list of `{client, status, detail}` objects from the same cached telemetry snapshot as the request rows. The website displays these as downloader-wide observations above the list, even if a newer search produced no selected release or there are no requests. Tracker DNS errors do not establish why an indexer search found no acceptable release; each request's outcome remains unchanged. Raw tracker addresses, exceptions, and connection strings are excluded. Older clients can ignore this additive field; an empty list clears a previous warning after the next successful refresh.
