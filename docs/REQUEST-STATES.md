# Request state and retry behavior

The Requests page combines durable request/queue records with read-only client telemetry. An accepted handoff does not mean game bytes have arrived. `metadata` means waiting for torrent metadata; `downloaded` means the client finished but library import is still pending; only `imported` means the library import completed.

The current telemetry adapters support qBittorrent and SABnzbd. Other configured client types retain their normal import behavior but may have less detailed progress reporting. Client timeouts or missing matches display status unavailable rather than asserting a failed release or successful transfer.

SABnzbd's explicit Failed history is reconciled into durable queue/history state during scheduled import polls and Requests refreshes. Release identity, indexer and client label are retained; raw failure messages and nested source URLs are not sent to the browser. Imported rows cannot be downgraded by old failure history. Ambiguous legacy rows sharing a release title are not guessed.

A client-reported failure or refused handoff requires review before automatic searches can retry it. That hold persists across restart. The scheduler and RSS matching skip held requests and existing active downloads. Use the explicit manual search/request flow after checking the client; no replacement is started merely because you viewed status.

Elapsed time, stalled peers, missing metadata and unavailable clients do not prove a bad release. These conditions never create a blocklist entry or automatic replacement. Older timer/rejection failure flags are also excluded from automatic retirement. Verified content failures, such as an imported archive containing no ROMs, retain the existing configured blocklist/replacement behavior.

Client histories are bounded to recent entries. Failure reconciliation currently matches release titles plus the stored client label where available; it is not a universal provider job-ID protocol. Keep client history until imports/reconciliation complete, and inspect the client when status is ambiguous.
