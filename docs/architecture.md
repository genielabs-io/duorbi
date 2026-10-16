# Architecture and conversation recovery

## Request path

1. `duorbi` resolves the target project's canonical absolute path, derives a loopback port and opens its state store.
2. The client checks the server's Agent Card against both project and store identity. A port collision or mismatched `--state-dir` is rejected before sending the prompt. This is an accidental-routing check, not authentication.
3. The CLI sends an A2A request with a versioned application envelope inside the message's text part.
4. The backend acquires an OS lock for this project/context, validates new/resume intent against SQLite, then invokes installed `agy` without a shell.
5. `agy -p TEXT --output-format json --mode plan --print-timeout 180s` runs in the target project. A resumed call adds the exact stored `--conversation ID`; the bridge never uses agy's global `--continue` flag.
6. The backend accepts only normal process exit, `SUCCESS`, response text and the expected conversation ID. It finishes process cleanup and commits the mapping before publishing success.

The transport layer is the separately installed a2acode 0.8.0. Duorbi neither modifies its source nor implements its own copy of A2A. The Antigravity adapter is headless JSON, not ACP.

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
4. Other POSIX: `$XDG_STATE_HOME/duorbi`, falling back to `~/.local/state/duorbi`.

The directory contains `conversations.sqlite3`, possible SQLite WAL/SHM companions and a `locks/` subdirectory. The store uses SQLite WAL and FULL synchronization. New directories are created with mode 0700; the database and lock files with mode 0600. Existing directory permissions are not rewritten. Use a private local directory.

Stored fields are canonical project path, context ID, agy conversation ID, creation/update timestamps and last-use ordering. A metadata table holds a persistent store UUID. The Agent Card incorporates a digest of the store directory and UUID. No prompt, answer, credential, approval state or interrupted-task payload is stored by this database.

Locks are held for the full turn. Concurrent requests for the same project/context fail instead of racing. The OS releases locks after process exit or reboot; lock files can remain without indicating an active request. Independent contexts can run concurrently.

## What survives a restart

Completed mappings survive. A fresh backend reads SQLite even when the upstream executor's in-memory session mapping is empty. Antigravity must still have its own matching history and the account must remain usable. The project must retain its canonical path; symlinks to that path identify the same project.

Interrupted tasks, approval prompts and exactly-once model effects are outside this feature. A crash after Antigravity responds but before the DB commit can leave an unrecorded new conversation. A resumed turn can have affected Antigravity history even if a later cleanup/save fails. Do not blindly repeat a timed-out request.

The agy execution budget is 180 seconds, with a 10-second process-exit allowance. The client defaults to 210 seconds. Client timeout alone does not cancel server work. Cleanup targets the invocation's process group: TERM with up to 5 seconds to finish, then KILL if required. Stop only server processes you own.

## Application envelope

A2A is the transport; Duorbi requires this application-specific text payload. The launcher builds it automatically:

```json
{"version":1,"intent":"new","conversation_id":null,"text":"Review this design."}
```

Resume payloads use `intent: "resume"`, the saved agy ID in `conversation_id`, and the matching A2A `context_id`. This prevents a missing store row from silently starting a new conversation. The backend removes the envelope before passing the text to agy. Raw text-only calls from another A2A client are rejected. The initial integration target is the bundled CLI, not arbitrary A2A clients.

## Import and migration

For a completed conversation created before persistence, use identifiers from a trusted prior result:

```sh
duorbi import-session --project /absolute/path/to/project \
  --context KNOWN_CONTEXT_ID --conversation KNOWN_AGY_CONVERSATION_ID
```

This registers identifiers; it does not verify that Antigravity can still open them. The next resume performs that check. Do not guess IDs or import another project's conversation.

An existing store created by the original adapter can be used with `--state-dir /absolute/path/to/existing/state` on **all** commands, with the original project path. The schema and Antigravity project hash remain compatible. Stop old servers first; replace them with Duorbi servers when switching. The default public-package location is separate and does not automatically search for or copy older stores. Back up a stopped store's entire directory before a manual migration; moving a store changes its card identity and requires matching new settings on server/client.
