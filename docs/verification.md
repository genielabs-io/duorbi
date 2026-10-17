# Verification scope

This file records checks performed during public-source preparation. It does not certify a package-registry release.

The server now uses the official A2A Python SDK directly. The earlier results below describe the former integration; current migration results are recorded separately at the end.

## Historical adapter evidence

Before extraction, the adapter completed real Antigravity CLI 1.4.0 conversations on macOS, including a full A2A server shutdown/restart that retained both conversation IDs and recalled prior text. Private transcripts, real IDs and machine paths are intentionally excluded from this distribution. The computer itself was not rebooted for that check.

## Historical public package checks

The former public package was validated separately against published a2acode 0.8.0, using temporary databases and a fake CLI. The check procedure covers strict result handling, project isolation, conversation selection, store reopen, legacy-format migration, full HTTP server restart, process cleanup and installed-wheel imports.

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

### Recorded cross-platform result — 2026-10-17

Candidate commit `1e9fad009f55b5c50cd5be833b51e634d1a98349` passed all four jobs in [GitHub Actions run 39007826697](https://github.com/genielabs-io/duorbi/actions/runs/39007826697):

| Runner / Python | Source suite | Clean installed-wheel suite |
|---|---|---|
| macOS / 3.13 | 75 discovered: 63 passed, 12 Windows-only skips | Passed, same counts |
| macOS / 3.14 | 75 discovered: 63 passed, 12 Windows-only skips | Passed, same counts |
| Windows x64 / 3.13 | 75 discovered: 70 passed, 5 POSIX-only skips | Passed, same counts |
| Windows x64 / 3.14 | 75 discovered: 70 passed, 5 POSIX-only skips | Passed, same counts |

Every job also passed source/archive guards and built the wheel/source archive. Windows Job containment, owner death, cancellation during startup/handshake/cleanup, process-lock contention/crash release, new-directory ACLs, Unicode paths/stdin and server-restart restoration were exercised. The successful Windows logs contained no unclosed-transport warnings or orphan-process termination messages. Local Apple Silicon macOS source and clean-wheel checks also passed on CPython 3.13.2; local source checks on CPython 3.14.7 passed. No real model calls were made.

The first Windows candidate exposed the virtual-environment Python redirector containment issue; the recorded successful candidate launches the base interpreter directly and closes Proactor pipe transports. That failure was fixed, not skipped. Native ARM64 Windows and Linux were not exercised by this matrix.

Real Windows `agy.exe` discovery, interactive authentication and model conversation restoration require a separate live check and have not been validated by the fake CLI suite. An actual OS reboot and Linux runtime support are also unverified. A successful server restart does not establish an OS-reboot test.

## Official SDK migration checks — 2026-10-17

The current server uses official `a2a-sdk[http-server]` 1.2.2 directly. The former `a2acode` package is absent from the dependency lock and synchronized environment. SQLite schema version 1, project/store identity, default ports, CLI commands and the new/resume envelope remain unchanged; existing and imported contexts are resumed explicitly after a full server restart.

Local Apple Silicon macOS / CPython 3.14.7 checks passed after the cancellation fix: 98 tests discovered, 86 passed and 12 Windows-only skips, both from the source checkout and a clean installed wheel outside the checkout. CPython 3.13.2 source checks passed with the same counts. Source/archive guards and wheel/source builds passed. The clean-wheel probe reported SDK 1.2.2 and no `a2acode`. All three license/notice payloads matched checkout bytes in both archives; wheel metadata retained MIT for Duorbi and identified the SDK requirement separately.

New coverage includes real REST and JSON-RPC calls, exact response/session metadata, legacy metadata fallback, same-context HTTP contention, explicit SDK cancellation, repeated cancellation during cleanup, completion/cancellation races, disconnected-stream continuation, mixed-part rejection, failed cleanup without artifact/save, and application lifespan shutdown with a real fake-CLI process tree. The POSIX-only open-stream SIGTERM test verifies bounded HTTP draining before shutdown; portable lifespan and Job Object tests cover Windows ownership separately. Existing lock, state-path, legacy/imported-store and native process tests remain in the suite.

Candidate commit `410e20216e73173bccb5e778ea80b9fcc9c33e30` passed all four jobs in [GitHub Actions run 39011556436](https://github.com/genielabs-io/duorbi/actions/runs/39011556436):

| Runner / Python | Source suite | Clean installed-wheel suite |
|---|---|---|
| macOS / 3.13 | 98 discovered: 86 passed, 12 Windows-only skips | Passed, same counts |
| macOS / 3.14 | 98 discovered: 86 passed, 12 Windows-only skips | Passed, same counts |
| Windows x64 / 3.13 | 98 discovered: 88 passed, 10 POSIX-only skips | Passed, same counts |
| Windows x64 / 3.14 | 98 discovered: 88 passed, 10 POSIX-only skips | Passed, same counts |

The macOS / 3.14 candidate also passed 200 consecutive HTTP cancellation/process-tree cleanup checks. This followed a reproduced transient process-group EPERM during teardown; the fix confirms group disappearance before suppressing that error and preserves failures for live groups or unsuccessful probes. The fixture publishes its readiness marker atomically to prevent partial JSON reads. The temporary 200-repeat diagnostic step was then removed from the regular CI workflow.

Every job passed source/archive guards and built both distributions. All four installed-wheel probes confirmed official SDK 1.2.2 and no `a2acode`. The new portable cancellation, same-context contention, disconnect and lifespan process-tree cases ran on both operating systems; only the actual SIGTERM/open-stream test is POSIX-specific.

Real Antigravity authentication/model restoration on Windows, native Windows ARM64, Linux and actual OS reboot remain unverified. The automated migration tests use fake CLI fixtures and make no real model calls.

An isolated macOS uv-tool upgrade check installed the former a2acode-based 0.1.0 wheel, registered synthetic conversation IDs and reinstalled the reviewed SDK source at the same package version using `uv tool install --reinstall`. The saved context/agy ID, store identity, card name and derived port were unchanged; a2acode was removed and SDK 1.2.2 was installed. This checked upgrade mechanics and mapping preservation, without calling a real model or changing a personal tool installation.

### Manual macOS launcher cutover and live continuation

On 2026-10-17, a common local launcher was switched from the former adapter to a separate installed-wheel runtime built from commit `7325c5c4c0995d12a16aa01eff7eae23987fc9cc`. The installed Python modules matched that checkout byte for byte; the runtime contained SDK 1.2.2 and no `a2acode`. The existing state directory was retained rather than copied to the public package's default location.

Before live calls, every stored row and metadata entry matched the SQLite backup snapshot. Four local launcher checks passed: Duorbi execution, existing project/store identity and ports, explicit state override, and independence from the caller's working directory and module search path.

Two authorized real Antigravity calls then completed using the original saved context and agy conversation IDs. The first recalled earlier review findings. After a full server shutdown/restart, `--continue` selected the same conversation and recalled a marker without the prompt repeating it. All existing mappings, store UUID and creation timestamps remained intact; unrelated rows were unchanged. Owned verification servers were stopped afterward.

This is manual macOS evidence, separate from the fake-CLI CI matrix. It does not validate actual OS reboot or live Windows authentication/restoration. Private machine paths, actual IDs, prompts, transcripts, database snapshots and environments are intentionally excluded from this repository.

## Per-turn model selection — 2026-10-18

The model-selection candidate adds `call --model MODEL_ID` through a version-2 application envelope. Calls without a model retain version 1. The SQLite schema, project identity and native process ownership paths are unchanged.

On macOS with CPython 3.13.2, both the source suite and the clean installed-wheel suite discovered 108 tests: 96 passed and 12 Windows-only cases were skipped. The existing Mac/Windows Python 3.13/3.14 CI matrix runs the new portable tests, including exact model argv, malformed selections, Gemini-to-Claude switching across full HTTP server restarts, omitted selection and unavailable-model failure without fallback. Four local common-launcher checks also passed. Source/archive guards and wheel/sdist builds passed.

Three authorized real A2A turns used the installed common launcher on macOS with `agy 1.4.0`:

1. Start a new conversation with `gemini-3.8-flash-medium` and remember a harmless verification marker.
2. Stop/restart the owned server and resume the saved context with `claude-sonnet-5-5-high`; recall the exact marker without repeating it in the prompt.
3. Stop/restart again and resume with `--continue`, omitting `--model`; recall the marker again with no `requested_model` claim.

All three exited 0 with `completed`, substantive answers and the same A2A context and agy conversation IDs. Selected turns reported the exact `requested_model`; this records the argv request, not independent provider attestation. Turn counts advanced 1→2→3. Every pre-existing conversation row, store metadata and schema version remained unchanged; only one new verification conversation was added. Owned servers were stopped afterward.

This is manual macOS evidence. Live Windows authentication/model switching and actual OS reboot remain unverified. Account model availability can differ; use `agy models` rather than assuming these example IDs are available. Actual IDs, markers, transcripts, state snapshots and local paths remain private.
