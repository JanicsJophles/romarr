# Filesystem publication and limits

The companion hardens inherited download/import behavior before writing final library files:

- Direct and debrid downloads use unpredictable, exclusively created partial files. A finished file is published atomically without overwriting an existing destination or following a pre-existing partial symlink.
- Provider-supplied directory names cannot escape the configured download root. Provider file paths are reduced to a safe basename; symlink destinations are refused.
- Import refuses source symlinks and escaped platform-directory destinations. Single files and multi-file sets are staged before publication, so an interrupted copy does not expose a truncated ROM. An explicitly requested overwrite retains a recoverable previous set if publication and rollback both fail.
- Download publication requires a filesystem supporting same-filesystem hard links. Unsupported filesystems fail closed rather than falling back to a race-prone overwrite. The server's staging/library filesystem is separate from any downstream SD-card synchronization.

`ROMARR_MAX_DOWNLOAD_BYTES` limits each direct/debrid file to 64 GiB by default. It must be a positive integer. Advertised sizes are checked early, but actual streamed bytes enforce the limit even when a server lies or omits Content-Length. Failed or oversized transfers clean up their private partial file. This bound applies to the built-in clients; an external torrent/Usenet client has its own limits.

An explicitly configured valid `UMASK` is applied to completed built-in downloads without changing the process-global mask from a worker thread. Partial data remains private while it is written. Without that explicit setting, the download stays private to its owner; the normal container entrypoint supplies and validates UMASK.

These protections do not create an OS sandbox. Restrict who can modify the service's configuration, source files and parent directories. They also do not guarantee compatibility or safety of game content, and a checksum match is not a malware scan.
