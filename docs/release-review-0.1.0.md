# 0.1.0 privacy and portability review

Review date: 2026-10-16. This is a targeted review of public source and release contents, not a general security certification.

## Result

No private personal identity, real credential, personal machine path or developer-checkout dependency was found in the reviewed public material. No finding required blocking the release. A separate read-only reviewer independently examined the existing public history and icon metadata.

## Coverage

- The 34 tracked files and both commits preceding this release, including author/committer metadata and local historical Git blobs.
- Runtime Python, Codex examples, documentation, dependency lock, CI and build scripts.
- The selected PNG icon's visible contents and metadata/provenance chunks.
- The release source diff and rebuilt wheel/source distribution, including package metadata and archive member names/content.
- Clean-wheel installation and tests outside the developer checkout; version/metadata checks and temporary-state execution.

## Review notes

**PR-01 — Public identity.** The repository owner and GitHub noreply commit identity are intentional public project identifiers. A private author email, personal name or additional personal account identity was not found.

**PR-02 — Paths and installation.** The runtime finds `agy` on `PATH`, resolves the caller's project path, and derives state from the current user's home or explicit options/environment. No original developer username, external-volume location, Homebrew installation path or nested research virtual environment is required. Build helpers derive their checkout location from `__file__` and use the active Python executable plus temporary directories.

Evidence: [state selection](../src/duorbi/paths.py#L7), [executable discovery](../src/duorbi/agy_backend.py#L105), [clean-wheel helper](../scripts/verify_wheel.py#L12).

**PR-03 — Platform requirements.** macOS user-data directories, POSIX virtual-environment `bin` paths, OS process groups/file locks and `/bin/ps` are platform conventions, not a particular user's folder layout. macOS remains the tested target. Example absolute project paths are placeholders; temporary paths in unit tests are synthetic fixtures.

**PR-04 — Secrets and runtime records.** Credential-like strings in diagnostic tests are deliberately fake. The archive test constructs an example path to exercise rejection. Live conversation IDs, transcript files, credentials, runtime databases and private logs are not tracked or packaged. Generated local state may contain the caller's canonical project path, by design; that state is separate from distributed source.

Evidence: [diagnostic fixture](../tests/test_agy_backend.py#L89), [archive fixture](../tests/test_public_archive.py#L33), [publication guard](../scripts/check_public.py#L13).

**PR-05 — Image metadata.** The selected icon contains generated-image C2PA provenance with service certificates, timestamps and generated identifiers. The review found no personal identity, computer path, prompt or account credential in it. No ordinary EXIF or textual user metadata was found. The selected artwork is distributed unchanged.

**PR-06 — Dependency source.** The lock uses public registry packages and the local editable project marker for contributor setup. It does not reference a private repository, developer checkout or credential-bearing registry URL. The release uses published a2acode 0.8.0 without vendoring a private runtime.

## Limits

Pattern scans and manual review cannot establish that every possible sensitive value is absent. This review covers repository objects and built distributions available during preparation; it does not inspect external provider accounts, user credentials, GitHub caches or a user's runtime history. Duorbi's documented local trust/permission boundaries remain unchanged.
