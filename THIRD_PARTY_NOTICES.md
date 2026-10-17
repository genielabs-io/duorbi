# Third-party notices

## Scope of Duorbi's MIT license

[LICENSE](LICENSE) applies to Duorbi's original adapter, project-session storage, command-line integration, examples and documentation. It does not relicense a2acode, the A2A SDK, other dependencies, or separately installed products. Their authors retain their rights and their own license terms apply.

Duorbi uses the A2A server provided by **a2acode**. Duorbi does not implement that server. Its wheel contains the Duorbi adapter and metadata; its source archive additionally contains documentation, examples, tests and assets. Neither archive vendors the a2acode package or a dependency environment. A package installer resolves the declared dependencies separately.

## a2acode

- Upstream project: [kanywst/a2acode](https://github.com/kanywst/a2acode), by kanywst and upstream contributors.
- Runtime requirement: **a2acode 0.8.0**, published on [PyPI](https://pypi.org/project/a2acode/0.8.0/).
- License: **Apache-2.0**. An unmodified copy is included at [licenses/a2acode-LICENSE.txt](licenses/a2acode-LICENSE.txt).
- License source: upstream tag `v0.8.0`, resolved to commit [`edddb318a4dcf9a424672cdac79cb3d52fac9021`](https://github.com/kanywst/a2acode/tree/edddb318a4dcf9a424672cdac79cb3d52fac9021); [original LICENSE](https://github.com/kanywst/a2acode/blob/edddb318a4dcf9a424672cdac79cb3d52fac9021/LICENSE).
- No separate upstream `NOTICE` file was found in that commit or the published 0.8.0 wheel/source archive reviewed on 2026-10-17. This file is Duorbi's attribution notice, not a purported upstream NOTICE.

Duorbi imports upstream backend result interfaces and `build_app`, and uses the A2A SDK to send requests. It does not vendor or modify the upstream server package. The Antigravity adapter is maintained in Duorbi. Upstream's generic metadata/error text retains Claude-specific names; Duorbi exposes the CLI conversation identifier as `agent_session_id`.

The published a2acode 0.8.0 wheel and source archive declare Apache-2.0 but omit a license-text file. Duorbi therefore ships the verified upstream license text and this attribution in **both** its own wheel and source archive. This supplies a readable notice to Duorbi recipients; it does not alter upstream artifacts or certify their packaging compliance. See the [artifact review](docs/license-review.md).

Historical adapter development also used upstream commit `d0856d4640acd80134d54d049f3f5d1b5c5c44b4`. That is a development reference, not the identity of the published 0.8.0 artifacts.

## Other direct runtime dependencies

These are the versions in the reviewed `uv.lock`; installation from version ranges may resolve differently. Dependencies are separately installed and retain their own notices.

| Component | Reviewed version | License | Upstream |
|---|---|---|---|
| A2A Python SDK (`a2a-sdk`) | 1.2.2 | Apache-2.0 | [a2aproject/a2a-python](https://github.com/a2aproject/a2a-python) |
| HTTPX | 0.28.1 | BSD-3-Clause | [encode/httpx](https://github.com/encode/httpx) |
| Protocol Buffers Python (`protobuf`) | 6.33.6 | BSD-3-Clause | [protocolbuffers/protobuf](https://github.com/protocolbuffers/protobuf) |
| Uvicorn | 0.54.0 | BSD-3-Clause | [Kludex/uvicorn](https://github.com/Kludex/uvicorn) |

Transitive dependencies have additional terms. In particular, `certifi` includes an **MPL-2.0** certificate bundle, and `requests` carries an upstream **NOTICE**. These are not covered by Duorbi's MIT license. Refer to the exact installed distributions and `uv.lock` when assessing a complete environment.

## Redistribution formats

The current Duorbi wheel/source archive uses separate dependency installation. If you distribute a container, standalone binary, application bundle, vendored source tree or offline environment containing dependencies, review that **complete artifact** again. Preserve each included component's copyright/license notices, any applicable NOTICE, and source-availability obligations such as those for MPL-covered files. The a2acode attribution here is not a substitute for every dependency's requirements.

If upstream files are copied or modified in a future change, retain applicable upstream notices and identify modified files as required by Apache-2.0 section 4. Duorbi's MIT license does not replace those obligations.

## Separately installed products and trademarks

Antigravity, Codex and uv are separately installed tools. Duorbi does not redistribute their executables, credentials or service access. Their product/service terms remain separate from the open-source license review. Compatibility names do not indicate sponsorship or endorsement by their owners, a2acode contributors, or the Apache Software Foundation. Apache-2.0 does not grant general trademark rights.
