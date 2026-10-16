# Local trust and reporting

Duorbi is a local development tool running as the current OS user. The HTTP server binds only to `127.0.0.1`; no authentication is configured. Project/store checks catch accidental routing errors, not hostile local callers. Do not expose it through a tunnel or use it as a public service.

Plan mode is not an additional OS filesystem sandbox. Antigravity uses its installed settings and account. Keep requests scoped to text analysis and review; this adapter does not implement tool approval round trips. Peer output is advisory and cannot grant user permission.

The ID store contains project paths and conversation identifiers. CLI stdout contains model responses. Raw agy stderr/error payloads are classified into fixed diagnostic categories rather than echoed by the adapter, but upstream exceptions and application output should still be reviewed before sharing. Keep state on a private local disk and exclude logs, histories and databases from issues and releases.

For a suspected sensitive issue, contact the repository owner privately through a channel they explicitly provide. No security email or private-reporting feature is assumed to be configured. Share only a minimal redacted reproduction; never include credentials, live conversation IDs or full private transcripts in a public issue.
