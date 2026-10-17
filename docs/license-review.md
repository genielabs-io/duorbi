# License and distribution review

Reviewed on 2026-10-17 for Duorbi's source checkout and Python wheel/source-distribution format. This is an engineering review of licensing evidence and packaging, not a legal opinion or an audit of proprietary service terms.

## Conclusion and ownership boundary

Apache-2.0 sections 1, 2 and 4 permit use of the upstream server interfaces, additions and redistribution subject to the license conditions. A separately maintained adapter can carry its own license; this does not change the upstream server's license. On the inspected implementation and packaging, Duorbi can retain MIT for its own work while depending on Apache-2.0 a2acode. We found no license requirement to obtain individual upstream permission for this use, provided the applicable conditions are met.

Duorbi calls `a2acode.server.build_app` and upstream result interfaces. It adds an Antigravity headless adapter, project-scoped conversation storage and a CLI workflow. It does not implement the upstream A2A server or redistribute Antigravity/Codex executables. README attribution and THIRD_PARTY_NOTICES distinguish these responsibilities.

## Inspected artifacts and provenance

The a2acode artifacts were fetched from PyPI's 0.8.0 metadata URLs and their SHA-256 values were verified against that metadata. They were inspected without executing downloaded code.

| Artifact | SHA-256 | License-text / NOTICE files |
|---|---|---|
| `a2acode-0.8.0-py3-none-any.whl` | `25db673375f23fd41c9c18c96b2f9bf8ed53ab04b20b31207f877d59cb6bd387` | Neither present |
| `a2acode-0.8.0.tar.gz` | `ea87ea5ed2f9c98cf7570e5ad31c44a6053ae9ded9bd884652fb18c9da50b54a` | Neither present |

PyPI metadata and the wheel declare `License-Expression: Apache-2.0`. Upstream tag `v0.8.0` resolved to commit `edddb318a4dcf9a424672cdac79cb3d52fac9021`; its tree contains `LICENSE` and no separate NOTICE. The LICENSE text matches the historical adapter reference commit as well. The copied, unmodified text has SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.

Inspection of Duorbi's built archive members found no vendored a2acode package or dependency environment. A supplementary source comparison found no identical blocks of at least seven nonblank lines between Duorbi Python files and the a2acode wheel's Python files. This comparison is supporting evidence, not proof of independent authorship or a complete provenance audit.

## Findings and corrections

| Finding | Correction |
|---|---|
| The existing Duorbi wheel included its MIT license but omitted THIRD_PARTY_NOTICES. | Declare both notices and the upstream license copy in `project.license-files`, so wheel recipients receive them. |
| a2acode 0.8.0 published archives omit their declared license's full text. | Include the exact upstream text at `licenses/a2acode-LICENSE.txt` in Duorbi's wheel and source archive; record its immutable provenance. This does not repair upstream archives. |
| General dependency wording could suggest that every distribution already carries complete license text. | Document the observed exception, direct licenses, transitive terms and redistribution boundaries. |
| The public archive guard did not reject missing notices. | Require nonempty MIT, third-party notice and a2acode license payloads in Duorbi wheels/source archives, with regression cases for either format. This is a presence check, not a complete license-compliance scanner. |

Duorbi's root LICENSE and package license expression remain MIT for its own original work. The included Apache text is expressly attributed to a separately installed dependency. Metadata alone does not license third-party work under MIT.

## Dependency and distribution limits

The locked macOS environment's installed distribution metadata/license files were inspected. The direct dependencies use Apache-2.0 or BSD-3-Clause. Transitive components also use MIT, MIT-0, ISC, BSD-2-Clause, PSF-2.0 and dual-license expressions. `certifi` additionally contains MPL-2.0-covered certificate data; do not describe the whole dependency graph as MIT or as wholly permissive. `requests` includes a NOTICE that a distributor of that package must consider.

This metadata inspection is not a line-by-line legal audit of all third-party source, embedded native libraries or platform-specific artifacts. The Windows-only locked `colorama` distribution was not installed in the original macOS review. During native Windows support preparation, the published `colorama 0.4.6` wheel was inspected separately: it includes `colorama-0.4.6.dist-info/licenses/LICENSE.txt` with BSD-3-Clause terms and Jonathan Hartley's copyright notice. Its SHA-256 matched PyPI metadata (`4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6`). This supplements artifact evidence rather than a full audit of Windows-installed native libraries. Windows support adds no runtime dependency and does not change Duorbi's MIT licensing or the existing redistribution boundaries.

No container, bundled application, standalone executable or offline dependency environment is distributed by the current build. Introducing one requires checking all included dependency notices and any source-availability obligations. Adding another agent also requires reviewing that implementation's license and the provider's applicable service terms; A2A compatibility alone grants neither redistribution nor service-access rights.

Codex and Antigravity names identify compatibility. The project claims no upstream endorsement. The review does not establish trademark clearance, patent freedom-to-operate, copyright exclusivity of generated artwork, or contractual permission for every future use of proprietary services.

## Verification

The existing publication workflow runs the source/archive guard after building. The archive tests exercise required notices in both wheel and source layouts; the clean-wheel suite verifies installation outside the checkout. Verify a candidate with:

```sh
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/check_public.py
uv build
uv run --frozen python scripts/check_public.py --archives dist
uv run --frozen python scripts/verify_wheel.py
```

Additionally compare the included license and notice bytes against the checkout and inspect wheel `License-File` metadata. Never infer that a source-repository notice is automatically present in an installed wheel.

Recorded local results for this correction: 45 source tests and 45 tests from a clean installed wheel passed; the source/archive guard passed; both archive formats contained byte-identical copies of all three required license/notice files. Wheel metadata retained `License-Expression: MIT` and listed all three `License-File` entries. No real model calls were made. GitHub CI results are reported separately in the repository's Actions tab.

## Primary sources

- [a2acode 0.8.0 PyPI metadata](https://pypi.org/pypi/a2acode/0.8.0/json)
- [a2acode LICENSE at the inspected commit](https://github.com/kanywst/a2acode/blob/edddb318a4dcf9a424672cdac79cb3d52fac9021/LICENSE)
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0): sections 1, 2, 4 and 6.
- [Mozilla MPL 2.0 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/): distribution and file-level obligations.
- [Python package license-expression specification](https://packaging.python.org/en/latest/specifications/license-expression/)
