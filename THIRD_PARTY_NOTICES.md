# Third-party notices

Duorbi began as a local adapter around an unmodified a2acode checkout. The public package extracts the adapter and depends on the published upstream release; it does not bundle that checkout, its virtual environment, or private runtime records.

## a2acode

- Author: kanywst and upstream contributors
- Source: https://github.com/kanywst/a2acode
- Runtime version: **0.8.0** from PyPI
- License: **Apache-2.0**; [upstream license](https://github.com/kanywst/a2acode/blob/main/LICENSE)
- Historical adapter development reference: upstream commit `d0856d4640acd80134d54d049f3f5d1b5c5c44b4`. This identifies the original checkout, not an assertion that a separately published wheel is byte-identical to that commit.

Duorbi calls upstream backend interfaces and `build_app`, and uses the A2A SDK to send requests. No upstream source files are copied into this distribution. Upstream's generic metadata/error text retains Claude-specific names; Duorbi exposes the CLI conversation identifier as `agent_session_id`.

## Other dependencies

The resolved dependency set is in `uv.lock`; package distributions carry their own license metadata. The direct runtime components include the [A2A Python SDK](https://github.com/a2aproject/a2a-python), [HTTPX](https://github.com/encode/httpx), and [Uvicorn](https://github.com/Kludex/uvicorn). Installing Duorbi installs the dependencies declared in `pyproject.toml` under their respective terms.

Antigravity, Codex and uv are separately installed tools. Duorbi does not redistribute their executables or grant rights to their services. Product names identify compatibility and do not indicate endorsement.
