# Tool adapters

The skill owns routing and learning; the installed tool owns invocation mechanics.

At session startup discover which worker mechanisms exist: native subagents, a CLI, a remote/cloud task, or a provider API. Check real model IDs, effort options, available modalities, workspace access, resumption, and result/usage reporting. Do not invent unsupported flags or cross-tool model availability.

| Tool style | Context to pass | Evidence to retain |
|---|---|---|
| Native subagent | Scoped task, inherited-context assumptions, applicable user policy | Agent ID, model/effort if exposed, result and checks |
| CLI worker | Workspace identity, explicit inputs, output path, data boundaries | Exact command/argv, session ID, exit status, log/artifacts |
| Cloud/remote worker | Explicit repository/artifact access and permitted external actions | Task ID, revision/branch, result artifact |
| Provider API | Task input, structured output contract, limits | Provider/model version, usage, result and validation |

Use each tool's documented background/foreground behavior. Await or poll a confirmed live handle; don't restart a task solely because an observation timed out. Resume only the correct session/workspace and preserve meaningful context.

For shell wrappers, use an argv array or correct shell quoting. Check documented stdin/server behavior; for example some OpenCode CLI versions need non-interactive stdin handling or a standalone server. Treat such findings as versioned local adapter notes, not universal flags.

### Harness-specific adapter notes

- **Antigravity (`agy` / Antigravity IDE / App):**
  - **Native subagents:** Dispatched via `invoke_subagent` (with `TypeName`, `Role`, `Prompt`, and `Workspace: inherit | branch | share`). Subagents run in the background; reactive wakeups notify the orchestrator without active polling. Dynamic agent types can be defined on-the-fly with `define_subagent`.
  - **CLI / headless workers:** Launched via `agy run` or shell commands within the terminal sandbox. Workspace boundaries and sandbox permissions (`BypassSandbox: false` default) apply strictly.
  - **Context & persistence:** Artifacts are written to `<appDataDir>/brain/<conversation-id>/...`. Session logs and transcripts are preserved at `<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`.
- **OpenCode:**
  - **CLI worker:** Dispatched via `opencode run` (support `-c` to resume session, non-interactive stdin `< /dev/null`). Custom agents in `.opencode/agents/` and commands in `.opencode/commands/`.
- **Codex:**
  - **CLI / Subagent:** Dispatched via `codex exec` (e.g. `codex exec -s read-only -m {model} -`) or `spawn_agent`. Supports custom agent definitions in `.codex/agents/*.toml`.

The user can prefer any orchestrator or worker mix. A CLI installed under one product does not grant permission, credentials, or subscription access in another.
