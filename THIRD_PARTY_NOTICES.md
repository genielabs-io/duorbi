# Third-party notices

## Scope of Duorbi's MIT license

[LICENSE](LICENSE) applies to Duorbi's original server adapter, Antigravity connection, project-session storage, command-line integration, examples and documentation. It does not relicense the official A2A SDK, other dependencies or separately installed products. Their authors retain their rights and their own terms apply.

Duorbi assembles its local server using the **official A2A Python SDK**. The SDK implements the A2A protocol; Duorbi provides the text executor and connects it to the installed Antigravity CLI. Duorbi's wheel contains its own package and metadata; its source archive also includes documentation, examples, tests and assets. Neither archive vendors the SDK or a dependency environment. Dependencies are installed separately.

## Official A2A Python SDK

- Upstream: [a2aproject/a2a-python](https://github.com/a2aproject/a2a-python), by the A2A SDK authors and contributors.
- Direct requirement: **`a2a-sdk[http-server]` 1.2.2**, published on [PyPI](https://pypi.org/project/a2a-sdk/1.2.2/).
- License: **Apache-2.0**. An unmodified copy from the verified 1.2.2 wheel is included at [licenses/a2a-sdk-LICENSE.txt](licenses/a2a-sdk-LICENSE.txt) in Duorbi's wheel and source archive.
- Both published SDK 1.2.2 wheel and source archive include `LICENSE`; neither contains a separate NOTICE file in the inspected archive members. This document is Duorbi's attribution, not an upstream NOTICE.
- The SDK source is separately installed, not copied or modified inside Duorbi. See [artifact provenance and review](docs/license-review.md).

Earlier Duorbi versions used a2acode. That package and its backend interface imports have been removed from the current implementation and dependency lock. Historical audits remain identified as historical; they do not describe the current runtime.

## Other direct runtime dependencies

These are versions in the reviewed `uv.lock`; a different lock or future source revision needs another review. Dependencies retain their own notices.

| Component | Reviewed version | License | Upstream |
|---|---|---|---|
| HTTPX | 0.28.1 | BSD-3-Clause | [encode/httpx](https://github.com/encode/httpx) |
| Protocol Buffers Python (`protobuf`) | 6.33.6 | BSD-3-Clause | [protocolbuffers/protobuf](https://github.com/protocolbuffers/protobuf) |
| Uvicorn | 0.54.0 | BSD-3-Clause | [Kludex/uvicorn](https://github.com/Kludex/uvicorn) |

The SDK's HTTP-server extra installs Starlette and SSE-Starlette (BSD-3-Clause). Transitive dependencies have additional terms. In particular, `certifi` contains an **MPL-2.0** certificate bundle and `requests` carries an upstream **NOTICE**. These are not covered by Duorbi's MIT license. Consult exact installed distributions and `uv.lock` when distributing a complete environment.

## Redistribution formats

For the current Duorbi wheel/source archive, dependencies are installed separately. A container, standalone binary, application bundle, vendored source tree or offline environment containing dependencies needs review of that complete artifact. Preserve each included component's license/copyright notices, applicable NOTICE and any source-availability obligations, including those for MPL-covered files. This notice is not a substitute for every dependency's requirements.

If upstream code is copied or modified in a future change, retain applicable upstream notices and identify modifications as required by its license. Duorbi's MIT license does not replace those obligations.

## Separately installed products and trademarks

Antigravity, Codex and uv are separately installed tools. Duorbi does not redistribute their executables, credentials or service access. Product/service terms remain separate from this open-source review. Compatibility names imply no sponsorship or endorsement. Apache-2.0 does not grant general trademark rights.
