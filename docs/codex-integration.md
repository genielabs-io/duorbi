# Codex integration / Codex에서 사용하기

The command-line bridge works independently of Codex configuration. These examples make delegation convenient; they are optional and are not installed automatically.

For an agent performing the installation, start with [INSTALL.md](../INSTALL.md). It defines installation scope, configuration preservation and completion checks.

## Make the executable visible

Install from the checkout with `uv tool install --python 3.13 .`. In the execution environment used by Codex, verify:

```sh
command -v duorbi
command -v agy
duorbi --version
```

On Windows, use PowerShell instead:

```powershell
Get-Command duorbi, agy
duorbi --version
```

The Antigravity launcher must resolve to native `agy.exe`; `.bat`/`.cmd` wrappers are rejected. `uv tool dir --bin` reports the Duorbi launcher directory. See [INSTALL.md](../INSTALL.md) for platform prerequisites and literal UTF-8 stdin examples.

If Codex does not inherit your shell PATH, use the resolved absolute `duorbi` executable path in your local agent instructions. Do not put your personal executable path into a public copy of the template.

The server must also find `agy.exe`/`agy` on its own PATH. An absolute agy path written in instructions does not configure Duorbi's backend. If needed, prepend the verified agy directory to PATH in the process that starts the server, and retain that setup in local launch instructions for fresh chats. See [server executable lookup](../INSTALL.md#ensure-the-server-can-find-agy) and the [authorized live/restart scenario](../INSTALL.md#6-optional-live-collaboration-check).

## Agent and project instructions

1. Inspect [examples/antigravity-a2a.toml](../examples/antigravity-a2a.toml).
2. Copy it to the project's `.codex/agents/antigravity-a2a.toml`, or to `~/.codex/agents/antigravity-a2a.toml` for personal use across projects. Preserve any existing custom role rather than overwriting it blindly.
3. Append the relevant instructions from [examples/AGENTS.md](../examples/AGENTS.md) to the project `AGENTS.md`, or your personal `~/.codex/AGENTS.md`. Merge the snippet with existing instructions.
4. Start a fresh Codex chat if configuration changes are not loaded in an existing session. Custom role discovery depends on the Codex version and configuration. If the role is unavailable, the lead agent can use the same CLI directly.

See the official [Codex subagent documentation](https://developers.openai.com/codex/subagents/) and [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md/) for your installed version's configuration details. Duorbi does not patch Codex or install a model into its agent runtime.

## Suggested workflow

The role resolves the actual target project's absolute path, checks `info` and `status`, starts a matching loopback server if necessary, and retains its process handle. It sends scoped excerpts for review via UTF-8 stdin, using a literal PowerShell here-string or a prompt file to avoid interpolation. It launches argv directly without a shell, including on Windows. It retains a returned context ID for follow-up turns, or inspects project `sessions` when resuming after a new Codex chat or bridge restart.

If an unrelated process occupies the derived port, choose another `--port` and pass it to every server/client command. Do not stop another task's server. If using a custom state directory, pass the same `--state-dir` or environment setting everywhere.

When the user specifies Gemini or Claude, inspect `agy models` and pass an available exact ID as `duorbi call ... --model MODEL_ID`. Do not put the model name in the prompt as a substitute for selection. Use the same saved `--context` to change perspective within a discussion, or `--new` for an independent review. Omission leaves the choice to agy; pin a model by supplying it each turn. `--continue` does not filter by model. See [model selection](../README.md#choose-gemini-or-claude) for version compatibility and requested-model metadata.

Codex should treat Antigravity's answer as a collaborator's advice, verify substantive claims and make its own final judgment. Failed calls must be reported as failures. A locally produced answer must never be attributed to Antigravity without a successful actual call.

## Korean prompts

> 제미나이한테 현재 설계를 검토시켜 줘. 관련 코드만 보내고 파일은 수정하지 않게 해 줘.

> 제미나이와 이전 대화를 이어가 줘. 지난 제안에서 놓친 점을 물어봐 줘.

> 제미나이와 새 대화로 시작해서 이 변경사항을 검토해 줘.

이 예제에서 “제미나이”는 Antigravity `agy`의 협업 별칭입니다. 제품 자체에 관한 질문이나 단순 이름 언급으로는 실행하지 않습니다. 새 독립 작업은 `--new`, 같은 논의의 후속 요청은 저장된 `--context`, 이전 ID가 대화에 없으면 `sessions` 확인 후 `--continue`를 사용합니다. 여러 논의 중 대상이 모호하면 먼저 확인합니다.

## Lifecycle and permissions

There is no boot-time service. A Codex agent starts a server only when needed, and stops the server it started when done. Saved IDs remain available for the next invocation. Antigravity must already be authenticated, and every real call uses its normal allowance.

The adapter uses plan mode and supports text analysis/review. It does not relay tool approvals or create an OS sandbox. Delegation does not grant authority to edit files, bypass approvals, change settings, or send external messages.
