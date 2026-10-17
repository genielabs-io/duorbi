# Install Duorbi with a coding agent

This is an installation runbook for Codex or another coding agent. Follow the user's requested scope and your host's approval rules. This document does not grant extra permissions. Use authorization already given; ask only for missing decisions or access.

**Supported baseline:** macOS or native Windows, CPython 3.13+, uv, and authenticated Antigravity CLI `agy` (`agy.exe` on Windows). Duorbi is a preview installed from `main`; its package version remains 0.1.0. Linux is unverified. Automated Windows coverage uses a fake CLI; real Windows Antigravity login/collaboration is a separate, not-yet-verified check. See [verification](docs/verification.md).

## 1. Establish the target and scope

Record these before changing files:

| Input | Meaning / default |
|---|---|
| `PROJECT_DIR` | Existing absolute path of the project the user wants to work on. Resolve its canonical path. |
| `SOURCE_DIR` | Separate location for the Duorbi checkout. It is not automatically the target project. |
| Source ref | Use `main` below unless the user requests a different ref. Record the resolved commit SHA because `main` changes over time. |
| Integration | For a Codex installation request, configure the target project. CLI-only requests skip step 4. Personal/global configuration requires that scope to have been requested. |
| Live check | Run only when a real Antigravity collaboration test is authorized; it uses model allowance. |

Read applicable local instructions first. Inspect existing Duorbi installations and the specific configuration files you intend to edit. Preserve existing settings, unrelated edits and saved conversations. Do not print credentials, whole private configuration files or private project contents in the installation report.

## 2. Check prerequisites

Run in the same execution environment the agent will use. On macOS/POSIX:

```sh
uname -s
command -v git
command -v uv
command -v agy
uv --version
agy --version
uv tool list
command -v duorbi
```

On Windows, use PowerShell:

```powershell
[System.Environment]::OSVersion.VersionString
Get-Command git, uv, agy
uv --version
agy --version
uv tool list
Get-Command duorbi -ErrorAction SilentlyContinue
```

Resolve the native executable with `(Get-Command agy -CommandType Application).Source` and check that it ends in `.exe`. Duorbi rejects `.bat`/`.cmd` wrappers because it never starts a command shell. Use the official [Antigravity CLI setup](https://antigravity.google/docs/getting-started?tab=cli); do not substitute a wrapper when `agy.exe` is absent.

A missing `duorbi` is expected on a new installation. Report missing prerequisites clearly. Install them only within the user's authorized scope; otherwise provide the missing step. [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/) cover uv. Obtain Antigravity CLI from its official distribution. Do not substitute Gemini CLI, `gemini -p`, an unrelated package named `agy`, or a guessed download URL.

`agy --version` does not prove authentication. If login is needed, have the user run interactive `agy` in `PROJECT_DIR` and complete it privately. Never request tokens or login codes in chat, read credential stores, or run a model prompt just to probe login. Non-model installation checks can proceed before login.

## 3. Install the CLI

Replace the two placeholder values with the paths established in step 1; quote paths throughout. Do not assign to `HOME` or `CODEX_HOME`.

macOS/POSIX:

```sh
PROJECT_DIR='/absolute/path/to/target-project'
SOURCE_DIR='/absolute/path/to/duorbi-checkout'
git clone --branch main --depth 1 https://github.com/genielabs-io/duorbi.git "$SOURCE_DIR"
git -C "$SOURCE_DIR" rev-parse HEAD
uv tool install --python 3.13 "$SOURCE_DIR"
uv tool dir --bin
command -v duorbi
duorbi --version
duorbi --help
```

PowerShell:

```powershell
$PROJECT_DIR = 'C:\projects\target-project'
$SOURCE_DIR = 'C:\tools\duorbi-checkout'
git clone --branch main --depth 1 https://github.com/genielabs-io/duorbi.git "$SOURCE_DIR"
git -C "$SOURCE_DIR" rev-parse HEAD
uv tool install --python 3.13 "$SOURCE_DIR"
uv tool dir --bin
Get-Command duorbi
duorbi --version
duorbi --help
```

uv may download a compatible Python and package dependencies. This installs a user-level CLI, even when Codex integration is project-scoped. No PyPI publication of Duorbi is required.

If `SOURCE_DIR` already exists, inspect its origin, ref and working tree; reuse a suitable checkout. Do not reset, delete or overwrite it. If Duorbi is already installed, inspect its version and provenance; reuse a matching installation. For an authorized upgrade or replacement, review the source/version before changing it. Do not add `--force` to hide an executable conflict.

The tool directory reported by `uv tool dir --bin` must be visible to the agent, not just to an interactive terminal. If it is absent from the agent's `PATH`, resolve the installed launcher in that directory and use its absolute path in **local** instructions. Do not silently edit shell startup files or put machine-specific paths into public templates. Use that resolved launcher in the remaining commands if necessary.

Compare `duorbi --version` with `[project].version` in the selected checkout's `pyproject.toml`. The package version may stay unchanged across multiple `main` commits, so also retain the source commit SHA. A successful `--help` checks that the launcher can import the package.

## 4. Integrate with Codex

Read [the integration guide](docs/codex-integration.md), then inspect the templates from the selected checkout:

- `examples/antigravity-a2a.toml`: role instructions.
- `examples/AGENTS.md`: collaboration instructions, including an optional Korean nickname.

For project scope, add the role at `PROJECT_DIR/.codex/agents/antigravity-a2a.toml` and merge the applicable snippet into `PROJECT_DIR/AGENTS.md`. Create a missing role file from the template; if it exists, review and patch it instead of overwriting it. Merge instructions once, preserving all existing guidance. Re-running installation should produce no duplicate blocks or needless changes. Add the “제미나이” nickname only if the user wants it.

For explicitly requested personal/global scope, use the user's configured Codex home (normally `~/.codex`, or the existing `CODEX_HOME` override), including its `agents/` directory and `AGENTS.md`. Do not create a second configuration home because the default path differs from the active one. A backup of an existing private file must remain private and outside tracked public files.

Do not add a Gemini MCP server, change the user's model, enable approval bypasses, or install a boot-time service. Custom-role loading depends on the installed Codex version; a fresh chat may be needed. If the role is unavailable, follow its local instructions and call the same Duorbi CLI directly. Report that fallback accurately.

## 5. Verify without a model call

Use a temporary state directory to avoid changing the user's conversation database. Keep the `PROJECT_DIR` value from step 3. On macOS/POSIX:

```sh
CHECK_STATE=$(mktemp -d "${TMPDIR:-/tmp}/duorbi-install.XXXXXX")
duorbi info --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
duorbi sessions --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
```

PowerShell:

```powershell
$CHECK_STATE = Join-Path ([System.IO.Path]::GetTempPath()) ("duorbi-install-" + [guid]::NewGuid().ToString("N"))
duorbi info --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
duorbi sessions --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
```

Leave the Windows check directory absent so `duorbi info` creates it using Python's mode-0700 directory ACL handling.

Expect exit 0, the correct canonical project and state paths, a loopback URL, and an empty `sessions` list. `info` and `sessions` create local SQLite metadata; they do not contact a model.

For a transport check, start the server below in a managed terminal/process and retain its handle. In another terminal, pass the **same** values to `status`:

macOS/POSIX (copy the exact variable values to terminal B):

```sh
# Terminal/process A
duorbi serve --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"

# Terminal/process B: define PROJECT_DIR and CHECK_STATE to the same values first
duorbi status --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
```

PowerShell (copy the exact variable values to terminal B):

```powershell
# Terminal/process A
duorbi serve --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"

# Terminal/process B: define $PROJECT_DIR and $CHECK_STATE to the same values first
duorbi status --project "$PROJECT_DIR" --state-dir "$CHECK_STATE"
```

Wait for `status` to exit 0 with `state: ready`; a printed startup line alone is not proof of readiness. Bound readiness retries. If the derived port is occupied, choose another port and pass `--port` on both commands. Do not terminate the process occupying it. Never expose the server through a tunnel.

Stop only the server you started, using its handle or Ctrl+C. Once stopped, remove only the temporary `CHECK_STATE` directory created for this check. Never delete an existing Duorbi database or Antigravity history. These checks verify installation and local transport, **not** login, model access, delegation discovery or conversation restoration.

## 6. Optional live collaboration check

When authorized and authenticated, start/reuse a matching server using the user's intended persistent state settings. Keep the same project, state directory and port on all server/client commands:

macOS/POSIX: a quoted heredoc passes the prompt literally via stdin.

```sh
duorbi call - --new --project "$PROJECT_DIR" <<'PROMPT'
Remember the word orbit. Reply briefly. Do not edit files.
PROMPT
# Read context_id from the successful result, then use that exact value:
duorbi call - --context SAVED_CONTEXT_ID --project "$PROJECT_DIR" <<'PROMPT'
What word did I ask you to remember? Do not edit files.
PROMPT
```

PowerShell: set the pipe encoding and use single-quoted here-strings, which preserve literal `$variables` and quotes. Closing `'@` markers must start their own lines.

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
@'
Remember the word orbit. Reply briefly. Do not edit files.
'@ | duorbi call - --new --project "$PROJECT_DIR"
# Read context_id from the successful result, then use that exact value:
@'
What word did I ask you to remember? Do not edit files.
'@ | duorbi call - --context SAVED_CONTEXT_ID --project "$PROJECT_DIR"
```

For an existing UTF-8 file, use `< review-request.txt` on POSIX, or `Get-Content -Raw -Encoding UTF8 review-request.txt | duorbi call - --new --project "$PROJECT_DIR"` in PowerShell after setting `$OutputEncoding` as above. The live examples use default persistent state; include the same `--state-dir`/`--port` on every command if you override them.

Only exit 0 **and** final `type: result`, `state: completed` count as success. Preserve the returned context ID for follow-ups. A server-restart restoration check must stop/restart the owned server with the same settings, then resume that saved context. Do not claim an OS-reboot test from a server restart.

On missing history, failed login, input-required state, or timeout, report the actual failure. Do not silently retry as a new conversation or attribute a local answer to Antigravity. A client timeout does not necessarily stop the server-side task; do not retry blindly. Stop an owned server when finished; leave a pre-existing server alone.

## 7. Preserve state and report completion

Normal state directories are macOS `~/Library/Application Support/Duorbi`, Windows `%LOCALAPPDATA%\Duorbi` (fallback `~/AppData/Local/Duorbi`), and other POSIX `$XDG_STATE_HOME/duorbi` (fallback `~/.local/state/duorbi`). The database is `conversations.sqlite3` inside. Precedence is `--state-dir`, then `DUORBI_STATE_DIR`, then the platform default. Use a private local state directory. POSIX creates mode-0700 directories and mode-0600 files. Python 3.13+ applies Windows ACL handling to newly created mode-0700 directories; file mode 0600 alone does not make Windows files private, and existing directory/profile permissions are not rewritten. Both Duorbi mappings and Antigravity's own history must survive to resume conversations. The canonical project path is part of the identity. See [storage and restoration](docs/architecture.md).

Report these separately:

- Source ref, resolved commit SHA and installed version; resolved launcher path.
- Target project and integration scope; files changed or deliberately reused.
- CLI, isolated state and transport checks: passed, failed, or not run, with reasons.
- Authentication, live model call, role discovery and restoration checks: their actual status, including **not verified** when not exercised.
- Persistent state location, any remaining user action, and whether an owned server was stopped.

Installation is complete when the requested CLI/configuration changes and non-model checks pass. A pending interactive login or unrequested live test must be stated explicitly; it must not be reported as verified collaboration.

To undo a new CLI installation, `uv tool uninstall duorbi` removes the tool. Revert only the configuration changes made by this installation. Do not uninstall a pre-existing tool or delete saved conversations as automatic cleanup.
