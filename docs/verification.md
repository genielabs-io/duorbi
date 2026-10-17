# Verification scope

This file records checks performed during public-source preparation. It does not certify a package-registry release.

## Historical adapter evidence

Before extraction, the adapter completed real Antigravity CLI 1.4.0 conversations on macOS, including a full A2A server shutdown/restart that retained both conversation IDs and recalled prior text. Private transcripts, real IDs and machine paths are intentionally excluded from this distribution. The computer itself was not rebooted for that check.

## Historical public package checks

The public package is validated separately against published a2acode 0.8.0, using temporary databases and a fake CLI. The check procedure covers strict result handling, project isolation, conversation selection, store reopen, legacy-format migration, full HTTP server restart, process cleanup and installed-wheel imports.

The following results predate native Windows support. They were recorded locally on macOS, Python 3.13.2, against the then-current dependency lock:

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

The later license-packaging correction recorded 45 source tests and 45 clean-wheel tests on macOS; that is also historical evidence, described in the [license review](license-review.md).

## Native Windows support checks

The current GitHub Actions configuration targets `macos-latest` and `windows-latest`, each with Python 3.13 and 3.14. Each job runs locked source tests, source/archive checks, builds and a clean installed-wheel suite. The portable fixture is a fake native console executable on Windows. No Antigravity account, credentials or model calls are used.

Coverage includes actual loopback HTTP new/resume calls, full server restart, Unicode paths/prompts, cross-process locking, process-tree cleanup and installed CLI execution outside the checkout. POSIX-specific signal tests remain platform-specific; Windows has Job Object lifecycle coverage. Windows symlink tests may skip when the runner lacks creation privileges.

Configured tests are not proof of a completed CI run. Current remote results are available in the repository's [Actions tab](https://github.com/genielabs-io/duorbi/actions); record the exact commit and results when validating a candidate. Historical counts above do not describe the current test suite.

Real Windows `agy.exe` discovery, interactive authentication and model conversation restoration require a separate live check and have not been validated by the fake CLI suite. An actual OS reboot and Linux runtime support are also unverified. A successful server restart does not establish an OS-reboot test.
