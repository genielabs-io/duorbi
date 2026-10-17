# Changelog

## Unreleased — source version 0.1.0

- Replace a2acode with a Duorbi text executor and server assembly using the official A2A Python SDK. Preserve existing conversation IDs, SQLite schema, CLI commands and Mac/Windows process handling.
- Recheck disappearing macOS process groups after transient EPERM during cleanup, while retaining errors for live groups or failed process listings.
- Use provider-neutral result metadata and advertise only supported text-collaboration capabilities.
- Update SDK license provenance, packaged notices, architecture and upgrade instructions.
- Clarify cutover of existing agent launchers and record manual macOS live conversation continuation across the switch and server restart.

- Add native Windows state paths, byte-range locks and Job Object process-tree containment while retaining macOS paths, locks and graceful cleanup.
- Preserve literal argv and UTF-8 pipes; require native `agy.exe` on Windows.
- Configure macOS/Windows Python 3.13/3.14 source and installed-wheel CI, with portable fake-CLI HTTP/restart and Unicode coverage. See [verification scope](docs/verification.md) for executed checks.
- Add PowerShell installation and local verification instructions. No new release or tag is created.

## 0.1.0 — 2026-10-16 (withdrawn)

First tagged GitHub release of Duorbi. The release, assets and tag were removed on 2026-10-17. Current installation uses the `main` branch; see [INSTALL.md](INSTALL.md).

- Local Codex-to-Antigravity A2A collaboration with durable project conversation IDs.
- Explicit new, continue and selected-context calls, with strict resume validation.
- Portable user-state paths and published, locked runtime dependencies.
- Selected Duorbi icon, English/Korean README diagrams and optional Codex setup examples.
- Fake-CLI regression tests, clean-wheel verification and macOS Python 3.13/3.14 CI.
- A second review of public history, metadata, source and release archives for private data and machine-specific paths; see [release review](docs/release-review-0.1.0.md).

## 0.1.0a1 — local public-source candidate

- Package the Antigravity A2A adapter as the `duorbi` command.
- Replace private checkout paths with published runtime dependencies and portable user-state locations.
- Retain project-scoped conversation selection, durable ID mappings, strict resume checks and process cleanup.
- Provide English/Korean documentation, optional Codex examples, fake-CLI integration tests and macOS CI configuration.

This source candidate does not imply a published GitHub or package-registry release.
