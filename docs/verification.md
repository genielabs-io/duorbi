# Verification scope

This file records checks performed during public-source preparation. It does not certify a package-registry release.

## Historical adapter evidence

Before extraction, the adapter completed real Antigravity CLI 1.4.0 conversations on macOS, including a full A2A server shutdown/restart that retained both conversation IDs and recalled prior text. Private transcripts, real IDs and machine paths are intentionally excluded from this distribution. The computer itself was not rebooted for that check.

## Public package checks

The public package is validated separately against published a2acode 0.8.0, using temporary databases and a fake CLI. The check procedure covers strict result handling, project isolation, conversation selection, store reopen, legacy-format migration, full HTTP server restart, process cleanup and installed-wheel imports.

Local results on macOS, Python 3.13.2, against the committed dependency lock:

| Check | Result |
|---|---|
| Locked source-environment regression suite | 43 tests passed |
| Wheel and source-distribution build | Both built successfully |
| Public source and archive guard | Passed; no flagged private paths/state or unsafe members |
| Wheel installed in a new temporary environment | Imported from installed site-packages; console version check passed |
| Full suite outside the source checkout, without PYTHONPATH | 43 tests passed |
| Document links and Codex example TOML | Validated locally |
| Real model calls during extraction/package checks | None |

The clean-wheel suite includes actual loopback HTTP calls to a fake CLI, process restarts and a constructed legacy-format SQLite migration. Python 3.14.7 source checks also passed the 40 core tests before the three archive-guard tests were added; the full 43-test clean-wheel result above is from Python 3.13.2.

Reproduce with the commands in [CONTRIBUTING.md](../CONTRIBUTING.md). No private runtime evidence is needed to run these checks.

The macOS Python 3.13/3.14 GitHub Actions workflow is configured in the source. The local results above were recorded before any GitHub run; current remote results are available in the repository's [Actions tab](https://github.com/genielabs-io/duorbi/actions). Linux/native Windows support and an actual OS reboot are not claimed by these checks.
