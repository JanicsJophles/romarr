# Candidate release audit

Status: **experimental companion fork; staged pipeline, container/security and desktop/mobile visual gates passed.**

## Provenance and license

- Source repository: https://github.com/BlizzHacker/romarr
- Source commit: `06378a70b94d8eb5646cd9720c52a992f5e2a09a`
- Source checkout was clean when exported; files were copied from `git archive`, not its working-directory caches.
- MIT copyright: `Copyright (c) 2026 MOVE WEIGHT`.
- `LICENSE` and `NOTICE` retained verbatim.
- NOTICE identifies BlizzHacker (Wade) as the original author and objects to derivatives implying independence or reusing branding without authorization. The candidate therefore labels itself a fork explicitly. The README and image labels identify a companion fork, retain attribution and make no claim of upstream endorsement. No rebranded community submission or claim to upstream branding is part of this candidate.
- This is a code/license inventory, not a legal assurance about operation or content acquisition.

## Selected source boundary

Included upstream: `romarr/`, `tests/`, `docker/`, dependency declarations, Dockerfile, pytest configuration, license/notice, ignore files, and archived documentation. Public Proxmox/scripts/contrib sources, an empty example environment and compose skeleton were later restored for packaging regression coverage; compose now builds this fork locally. Included custom code: chat API, durable request state, read-only download telemetry, their UI integration, and deterministic tests.

Excluded: deployment scripts, remote activation helpers, actual configuration, account data, keys, host inventories, downloaded content, screenshots, caches, histories, and backups. Personal device/user assumptions were removed from the chat system prompt. The public repository is JanicsJophles/romarr; only the allowlisted source and audit artifacts are published. CI validates trusted branches and does not deploy services or publish images. Original upstream Git history was not imported into this isolated release candidate.

A text scan found no operator-specific names, hostnames, or filesystem paths in copied application/custom-test source. Generic upstream private-address fixtures and sample secret strings remain test data. This is not a substitute for a dedicated secret scan immediately before publication.

## Dependencies and distribution

- Runtime and test dependency versions are pinned to the tested environment. See DEPENDENCIES.md for the runtime package-license metadata inventory. The final-image [SBOM](audit/runtime-sbom.cdx.json), [license inventory](audit/license-inventory.json), [source hashes](audit/build-context.sha256) and [build attestation](audit/build-attestation.json) are recorded.
- Docker pins the Python 3.13 Alpine base-image digest and installs OS packages from Alpine repositories. The upstream external `rom-hub` package installation was removed; plugin execution/catalogue loading are disabled in the candidate. The resolved final-image inventory includes OS and Python dependencies and their distinct licenses.
- Docker title/vendor labels identify a companion fork. No release image is published; recorded image hashes refer to the isolated acceptance build.
- Third-party package license notices must accompany distributed bundles/images where their licenses require it. The generated image SBOM and license reports describe this exact image; this project's MIT license does not replace dependency licenses.
- Metadata, covers, logos and provider catalogues have independent terms. No game cover assets are bundled by this candidate. Runtime metadata access requires operator configuration and review of the provider's terms.

## Completed gates

- Python suite: **2157 passed, 2 skipped, 1 network test deselected, 10 subtests passed** after the final filesystem/resource and archive-argument fixes. Real-loopback tests cover custom API authentication and error redaction. Deterministic tests cover request persistence, duplicate prevention, review holds across restart, and disabled plugin execution.
- Final Linux/amd64 image was built and smoke-tested in an isolated container host. Startup, unauthenticated health, rejected unauthenticated API access, UID 1000, umask 0002, unchanged mounted-media ownership/modes, attribution files and disabled plugin boundary passed. The smoke container had no network access.
- Trivy scan of the final runtime image reported **zero detected vulnerabilities and zero detected secrets**. Installer/vendor findings were fixed by removing pip and ensurepip from the runtime image, not suppressed.
- Verified image ID: `sha256:d595f54fe5132870d662902eaf74ce6e4e46f8e34da5eb0787237f9c91b9d7a6`. The test operator confirmed copied runtime source matched the candidate files.
- The synthetic end-to-end harness passed all eight checks locally and in the final image as UID 1000 with external networking disabled: authenticated request, idempotent duplicate, real loopback HTTP download, folder import, byte integrity, durable imported status, restart persistence, and no repeat transfer. The fixture is a generated test payload; no commercial content or real provider was involved. Run `python scripts/stage_companion.py` to repeat it.
- Desktop and 390×844 mobile Requests visual checks passed. The mobile navigation drawer leaves content full width; opening it makes background content inert, and Escape closes it and restores focus to the menu button.
- Python runtime and test package versions are pinned. LICENSE and NOTICE remain byte-identical to upstream and are included in the image. The README identifies this as a companion fork, with upstream source/commit/author attribution and no endorsement claim.
- Chat setup and privacy are documented in CHAT-SETUP.md. File-based optional configuration and support for one AI provider are explicit initial-build limits, not undisclosed unfinished setup.
- CI runs only on dedicated Atlas labels for trusted same-repository branches/manual dispatch, with repository guards, no public pull-request trigger, minimal permissions, no stored checkout credentials, isolated container smoke checks, cleanup and recurring image scans.

## Remaining acceptance scope

The tested initial source is introduced through a pull request to the protected main branch of JanicsJophles/romarr. Required python and smoke checks run on a dedicated self-hosted runner. Publication does not deploy this fork to the personal production service or publish a container image.

The requested staged request-to-import and narrow-display visual gates are complete for the tested scope. This does not establish every real downloader, archive, library backend or storage filesystem combination. The new reconciliation and import protections have not been deployed to the personal production service. No live-provider acquisitions were used as acceptance tests.

Describe this as an experimental companion fork, not a stable production release based solely on these checks. The final-image SBOM contains 41 components and the license scan recorded 73 detections; all 49 allowlisted build-context file hashes matched the isolated builder. The base-image digest and Python versions are pinned, but mutable Alpine repositories and the absence of wheel artifact hash locks mean bit-for-bit reproducibility is not promised. Scanner results are a point-in-time observation, not a guarantee against unknown vulnerabilities.

Filesystem and resource boundaries are documented in [FILESYSTEM-BOUNDARIES.md](FILESYSTEM-BOUNDARIES.md) and [RESOURCE_LIMITS.txt](RESOURCE_LIMITS.txt). Import publication requires hardlink support. Large imports/downloads have configurable positive byte limits; archive subprocesses have deadlines. Tests cover symlink/path escapes, atomic publication, partial-copy failure, unsafe archive member arguments and resource exhaustion. These protections do not sandbox a privileged local process that can mutate parent directories concurrently.

## Packaging decisions

The candidate compose file builds the local fork, binds its port to loopback, requires explicit library/download paths, and does not substitute an upstream image. Public upstream Proxmox scripts and install documentation are retained as clearly labelled references; they install upstream, not this fork. Their regression tests read the archived upstream README. Plugin tests now verify that this build cannot execute or enable plugins, even when packages and opt-out environment flags are present; the old tests requiring unsandboxed execution were replaced with checks of the supported boundary, not skipped.

CI is configured only for project-specific Atlas labels, triggered by pushes to trusted same-repository branches and manual dispatch. No public pull-request trigger is enabled. Repository write access must therefore be restricted to trusted maintainers; unreviewed fork code must never be copied onto a trusted branch merely to run CI.

## Request reconciliation change

SAB's explicit failed history now reconciles into durable queue/history state during import polls and Requests refreshes, preserving release identity, indexer and a non-secret client label. Raw error text and nested source URLs are never copied. Client failures remain reviewable and do not automatically trigger a replacement. A refused handoff, elapsed stall timer, client outage or unavailable history no longer proves that a release is bad. Legacy failure flags produced by age/rejection are excluded from automatic retirement. Verified content failures retain existing retirement behavior. Deterministic reconciliation tests cover restart persistence, duplicate/other-client ambiguity, category filtering, outage and elapsed time, legacy flags, and redaction.
