# License and distribution review

Reviewed on 2026-10-17 for the official-SDK migration and Duorbi's Python wheel/source-distribution format. This is an engineering review of licensing evidence and packaging, not a legal opinion or an audit of proprietary service terms.

## Current ownership boundary

Duorbi's original text executor, server assembly, Antigravity connection, storage and CLI use MIT. The A2A protocol implementation comes from the separately installed **official `a2a-sdk[http-server]` 1.2.2**, under Apache-2.0. Dependencies retain their own terms. Apache-2.0 permits use and redistribution subject to its conditions; it does not require Duorbi's separate original code to adopt Apache-2.0.

The migration removes a2acode's `build_app`, backend event types and runtime requirement. The replacement uses SDK execution/request-handler/task/route interfaces and an original Duorbi backend call returning a verified result. SDK or a2acode implementation source is not vendored. Keeping an API integration is distinct from copying upstream implementation; any future copied or derived source must retain its applicable attribution.

## Inspected SDK artifacts

Both artifacts were downloaded from the exact URLs in [PyPI 1.2.2 metadata](https://pypi.org/pypi/a2a-sdk/1.2.2/json), SHA-256 checked against that metadata and inspected without executing downloaded code.

| Artifact | SHA-256 | License member |
|---|---|---|
| `a2a_sdk-1.2.2-py3-none-any.whl` | `f2aa9692f3e3034f58ebff501e091d43affa416878c734fd63016ae0b8ea8c66` | `a2a_sdk-1.2.2.dist-info/licenses/LICENSE` |
| `a2a_sdk-1.2.2.tar.gz` | `09be001a90fae9634d54041471feca1014201ec22f7107f0883309a2b4027a15` | `a2a_sdk-1.2.2/LICENSE` |

The wheel declares `License-Expression: Apache-2.0` and `License-File: LICENSE`. No separate NOTICE member was found in either archive. Duorbi includes the unmodified SDK license bytes at `licenses/a2a-sdk-LICENSE.txt`; their SHA-256 is `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`. This attribution supplies the verified upstream text; it does not imply upstream endorsement or change SDK licensing.

The package's `license-files` explicitly includes Duorbi's MIT LICENSE, THIRD_PARTY_NOTICES.md and the SDK Apache text. The archive guard requires nonempty copies in both Duorbi wheel and source archive. License presence alone is not a complete compliance scan.

## Previous integration

Earlier source revisions used a2acode 0.8.0 (Apache-2.0). Its published wheel/source archive omitted the license text, so Duorbi included a verified upstream copy. The earlier audit is preserved in [repository history](https://github.com/genielabs-io/duorbi/blob/28b0f01/docs/license-review.md). That finding concerned those artifacts; it is not a finding against the official SDK. The current migration removes a2acode rather than relabeling or relicensing its server. Historical adapter evidence and the withdrawn release review remain marked as historical.

## Dependency and distribution limits

The refreshed lock and the corresponding installed macOS distribution metadata/license files were inspected after synchronization. Every locked dependency had license files in its installed metadata; `a2acode` was absent from both the lock and the synchronized environment. The direct dependencies use Apache-2.0 or BSD-3-Clause. The SDK HTTP-server extra adds Starlette and SSE-Starlette under BSD-3-Clause. Transitive terms include MIT, ISC, BSD and other expressions. `certifi` includes MPL-2.0-covered certificate data, and `requests` includes NOTICE. Do not describe the complete environment as MIT or free of obligations.

This review does not constitute a line-by-line audit of all upstream source, embedded native libraries or every platform-specific wheel. The preceding Windows review inspected colorama 0.4.6; removing its upstream dependency path does not transfer that evidence to other packages. Inspect the current lock rather than relying on historical dependency lists.

Duorbi currently distributes its own Python wheel/source archive with separately resolved dependencies, not a container, native application or offline environment. A new format needs review of all included components and source-availability obligations. Adding an agent requires review of that implementation's license and provider terms. A2A compatibility does not grant service-access or executable redistribution rights.

Codex and Antigravity names identify compatibility. This review does not establish trademark clearance, patent freedom-to-operate, exclusivity of generated artwork or permission for every future proprietary-service use.

## Verification procedure

```sh
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/check_public.py
uv build
uv run --frozen python scripts/check_public.py --archives dist
uv run --frozen python scripts/verify_wheel.py
```

Compare packaged license/notice bytes with the checkout and inspect wheel `License-File` metadata. Check resolved dependencies and a fresh installed wheel for the removed package rather than relying on imports succeeding in an old environment. Current test/CI evidence belongs in [verification.md](verification.md); earlier counts are historical.

## Primary sources

- [Official SDK repository](https://github.com/a2aproject/a2a-python) and [PyPI 1.2.2 metadata](https://pypi.org/pypi/a2a-sdk/1.2.2/json).
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0): sections 1, 2, 4 and 6.
- [Mozilla MPL 2.0 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/): distribution and file-level obligations.
- [Python package license-expression specification](https://packaging.python.org/en/latest/specifications/license-expression/).
