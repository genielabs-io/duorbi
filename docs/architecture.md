# Architecture and conversation recovery

## Request path

1. `duorbi` resolves the target project's canonical absolute path, derives a loopback port and opens its state store.
2. The client checks the server's Agent Card against both project and store identity. A port collision or mismatched `--state-dir` is rejected before sending the prompt. This is an accidental-routing check, not authentication.
3. The CLI sends an A2A request with a versioned application envelope inside the message's text part.
4. The backend acquires an OS lock for this project/context, validates new/resume intent against SQLite, then invokes installed `agy` without a shell.
5. `agy -p TEXT --output-format json --mode plan --print-timeout 180s` runs in the target project. Explicit per-turn selection adds `--model MODEL_ID` as literal argv. A resumed call adds the exact stored `--conversation ID`; the bridge never uses agy's global `--continue` flag.
6. The backend accepts only normal process exit, `SUCCESS`, response text and the expected conversation ID. It finishes process cleanup and commits the mapping before publishing success.

Duorbi implements a small text-only executor and assembles the server using the official `a2a-sdk` 1.2.2 request handler, routes and task events. The SDK implements the A2A protocol; Duorbi owns the Antigravity connection and application lifecycle. The adapter uses headless JSON, not ACP. The card advertises text review and streaming, without push notifications or tool-approval relay.

## Three identifiers

| Identifier | Owner | Purpose |
|---|---|---|
| `context_id` | A2A | Chooses a continuing discussion |
| `task_id` | A2A | Identifies an individual request; not used for durable recovery |
| `agent_session_id` / stored `conversation_id` | Antigravity | Resumes the actual agy conversation |

The database maps `(canonical project, context_id)` to one immutable agy conversation ID. A conversation ID cannot be registered under another project/context in the same store. Older conversations remain available when a newer one starts. `sessions` lists creation/use timestamps and identifiers; it does not provide transcript search or titles.

## Disk state

State selection, highest priority first:

1. `--state-dir PATH` on each command.
2. Environment variable `DUORBI_STATE_DIR`.
3. macOS: `~/Library/Application Support/Duorbi`.
4. Windows: `%LOCALAPPDATA%\Duorbi`, falling back to `~/AppData/Local/Duorbi`.
5. Other POSIX: `$XDG_STATE_HOME/duorbi`, falling back to `~/.local/state/duorbi`.

Platform defaults are alternatives, not fallbacks between operating systems.

The directory contains `conversations.sqlite3`, possible SQLite WAL/SHM companions and a `locks/` subdirectory. The store uses SQLite WAL and FULL synchronization. On POSIX, new directories use mode 0700 and database/lock files use mode 0600. On Windows, Python 3.13+ applies its mode-0700 directory ACL handling to newly created private state directories; file mode 0600 alone does not establish a private Windows ACL. Existing profile/directory permissions are not rewritten. Use a private local directory with suitable ACLs.

Stored fields are canonical project path, context ID, agy conversation ID, creation/update timestamps and last-use ordering. A metadata table holds a persistent store UUID. The Agent Card incorporates a digest of the store directory and UUID. No prompt, answer, credential, approval state or interrupted-task payload is stored by this database.

POSIX uses `flock`; Windows uses a byte-range file lock. Locks are held for the full turn. Concurrent requests for the same project/context fail instead of racing. The OS releases locks after process exit or reboot; lock files can remain without indicating an active request. Independent contexts can run concurrently.

## What survives a restart

Completed mappings survive. A fresh backend reads SQLite; recovery does not depend on an in-memory SDK task or session mapping. Antigravity must still have its own matching history and the account must remain usable. The project must retain its canonical path; symlinks to that path identify the same project.

Interrupted tasks, approval prompts and exactly-once model effects are outside this feature. A crash after Antigravity responds but before the DB commit can leave an unrecorded new conversation. A resumed turn can have affected Antigravity history even if a later cleanup/save fails. Do not blindly repeat a timed-out request.

The agy execution budget is 180 seconds, with a 10-second process-exit allowance. The client defaults to 210 seconds. Client timeout or streaming disconnect alone does not cancel server work. An explicit A2A cancellation waits for owned work to finish cleanup before reporting cancellation. Graceful server shutdown cancels and awaits active executions; it does not restore interrupted tasks on restart. On POSIX, cleanup targets the invocation's process group: TERM with up to 5 seconds to finish, then KILL if required. If macOS reports EPERM while a group is disappearing, up to four process-list probes confirm its disappearance before suppressing that error; live groups and unsuccessful probes still fail cleanup. On Windows, a parent-owned, non-inherited Job Object contains the runner and its descendants. The Python runner waits for a launch token until assignment to the job, so agy cannot start outside containment. Cleanup terminates the job tree, including descendants left after the direct child exits; kill-on-close also applies if the owning parent exits. Windows requires a native `agy.exe` and rejects `.bat`/`.cmd` wrappers. All platforms pass literal argument lists without a shell and decode JSON pipes as UTF-8. Stop only server processes you own.

On Windows, the trusted launch gate runs with the base CPython executable and an absolute path to Duorbi's stdlib-only runner, in isolated (`-I`) mode. A virtual environment's `python.exe` can be a redirector that starts another interpreter before the parent can assign its PID to a Job. Using the base executable ensures the assigned PID is the process that waits for the launch token; the target command remains unchanged and can still use its own virtual environment.

## Application envelope

A2A is the transport; Duorbi requires this application-specific text payload. The launcher builds it automatically:

```json
{"version":1,"intent":"new","conversation_id":null,"text":"Review this design."}
```

Resume payloads use `intent: "resume"`, the saved agy ID in `conversation_id`, and the matching A2A `context_id`. This prevents a missing store row from silently starting a new conversation. The backend removes the envelope before passing the text to agy. Raw text-only calls from another A2A client are rejected. The initial integration target is the bundled CLI, not arbitrary A2A clients.

With `call --model MODEL_ID`, the client sends version 2 with an additional required `model` field:

```json
{"version":2,"intent":"new","conversation_id":null,"text":"Review this design.","model":"claude-sonnet-5-5-high"}
```

The server accepts v1 without a model or v2 with a validated CLI model slug. A model in v1, missing/invalid model in v2, or unknown version is rejected before launching agy. An older server rejects v2, preventing silent loss of a model selection. Upgrade the actual server runtime as well as the client. A v2 request resumes the same stored conversation and acquires the same project/context lock; no schema conversion is required.

Duorbi does not resolve aliases, select provider defaults, probe entitlements or retry a failed selection on another model. Use `agy models` for available IDs; agy validates account access. If no model is supplied, argv stays unchanged and agy owns saved/default selection. Pin a model by specifying it on every turn. No model preference is stored in Duorbi's SQLite database, and `--continue` remains project-wide. Successful selected requests add `requested_model` to A2A completion metadata and CLI output. This identifies requested argv selection, not independently verified provider identity. Plan mode, process containment and tool permissions are unchanged.

## Import and migration

For a completed conversation created before persistence, use identifiers from a trusted prior result:

```sh
duorbi import-session --project /absolute/path/to/project \
  --context KNOWN_CONTEXT_ID --conversation KNOWN_AGY_CONVERSATION_ID
```

This registers identifiers; it does not verify that Antigravity can still open them. The next resume performs that check. Do not guess IDs or import another project's conversation.

An existing store created by the original adapter can be used with `--state-dir /absolute/path/to/existing/state` on **all** commands, with the original project path. The schema and Antigravity project hash remain compatible. Stop old servers first; replace them with Duorbi servers when switching. The default public-package location is separate and does not automatically search for or copy older stores. Back up a stopped store's entire directory before a manual migration; moving a store changes its card identity and requires matching new settings on server/client.

## Upgrading from the former server integration

The official-SDK server replaces the former a2acode dependency. Stop the old server and upgrade the CLI, retaining the same canonical project and state directory. No database conversion or new conversation ID is required: schema version 1, the store UUID, project-derived card identity/port and the request envelope are unchanged. SDK task history is in memory and is not restored. New server metadata uses `agent_session_id`; the CLI also recognizes the legacy `claude_session_id` field when reading an older server response. The supported compatibility boundary is the Duorbi CLI and its saved mappings, not every optional feature of the former generic server.

### Switching an existing launcher

Source changes do not replace an already installed environment, wrapper or agent role. Check the complete path from the agent's configured command to the server process before reporting an upgrade as complete.

1. Finish active requests and stop only servers you own. Record the existing canonical project/state paths, `info` output and saved project/context/agy ID mappings privately. Back up the stopped state directory, or use SQLite's backup API for a consistent database snapshot. Preserve the current launcher for rollback.
2. Install the reviewed Duorbi revision in the intended runtime and record its provenance. An unchanged `0.1.0` version string alone does not identify the installed source revision. See [installation and explicit reinstallation](../INSTALL.md#3-install-the-cli).
3. Point the actual agent launcher to that installation. Retain the old state location explicitly, either in the wrapper's default or with `--state-dir` on every command. An explicit CLI `--state-dir` takes precedence over `DUORBI_STATE_DIR`. Changing to the package's platform default can select an empty store instead of the saved conversations.
4. Before a model call, compare `info`, saved mappings and the store UUID with the snapshot. With the same project/state paths and UUID, card identity and derived port should match too. Start the new server and verify `status` using matching settings. If a port belongs to another process, do not terminate it; use the same alternate port on server and client.
5. When a live check is authorized, resume a known saved context without creating a new conversation. Require exit 0, `completed`, substantive response text and the original context/agy IDs. Stop/restart the owned server, then resume again and ask it to recall a harmless marker without repeating the marker in the prompt. Check that mappings and unrelated rows remain intact; successful use updates the selected row's usage timestamps.

Missing history remains a failure; never silently substitute `--new`. If rolling back, stop the owned server and restore the launcher/runtime while retaining the current compatible state. Restoring an older DB snapshot after successful new calls can discard newer mappings. Keep databases, actual IDs, transcripts, logs, environment directories and machine-specific wrapper settings outside the public repository. A server-restart check is not an OS-reboot check.
