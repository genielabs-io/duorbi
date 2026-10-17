# Contributing

This is a macOS and native Windows preview. Keep changes scoped to the Antigravity text-collaboration adapter; discuss additional providers, desktop transports or background services before adding them.

## Local checks

Use Python 3.13+ and uv, from this checkout:

```sh
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/check_public.py
uv build
uv run --frozen python scripts/check_public.py --archives dist
```

The tests use fake CLI executables and temporary state. They start local HTTP servers and owned process trees, so restricted sandboxes may require explicit permission for those operations. Windows fixtures use a native console executable; tests never fall through to the real `agy`. Windows uses Job Object containment and byte-range locks; preserve equivalent cleanup/locking coverage on both platforms. Do not point tests at real Antigravity history or a real Duorbi state directory.

## Installed-wheel verification

```sh
uv run --frozen python scripts/verify_wheel.py
```

Build first. The verifier creates a temporary virtual environment, installs the built wheel and dependencies, and runs the CLI plus copied tests from outside this checkout with PYTHONPATH removed. It can require network access to install dependencies. It calls no real model. Temporary environments and fixture histories are removed afterward.

## Changes and reports

- Add meaningful regressions for persistence, resume selection, failure handling or packaging changes.
- Preserve strict resume semantics, per-context locking and cleanup before success publication.
- Update both README languages when behavior changes. Describe tested compatibility separately from intended support.
- Do not commit live IDs, databases, credentials, prompts, transcripts, logs, personal paths or vendored environments. The publication checker is a narrow guard, not a complete secret scanner.
- Source/packaging changes should pass the configured macOS/Windows × Python 3.13/3.14 CI, including source tests, archive checks and clean-wheel tests. Only POSIX signal-specific cases and unavailable Windows symlink privileges may have platform-specific skips; ordinary HTTP/new/resume/restart and Unicode-path coverage must run on both operating systems. A local check does not mean GitHub CI has executed.

## Dependency updates

The official `a2a-sdk[http-server]` is pinned because Duorbi uses its server execution, routing and protobuf interfaces. Change the pin deliberately, resolve `uv.lock`, and verify the complete fake-CLI HTTP restart/cancellation suite plus installed wheel. Keep subprocess ownership and durable conversation recovery independent of SDK in-memory task history. Do not patch installed SDK files to make tests pass.

## Release preparation

Review source and built archives, run clean-wheel verification, and read the compatibility/limitations documentation. Preserve the MIT license, THIRD_PARTY_NOTICES and the unmodified A2A SDK Apache license in both wheel and source archive; the archive guard checks their presence. When upgrading dependencies or changing distribution formats, repeat the [license and distribution review](docs/license-review.md), including applicable upstream NOTICE and source-availability obligations. Publish only after the owner authorizes the actual remote destination and release. Never include a local research workspace, its runtime state or its Git history in a source release.
