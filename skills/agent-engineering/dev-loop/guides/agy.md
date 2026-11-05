# Antigravity (`agy`) adapter

Keep the shared intake, register, plan/review/implement loop and write-set ownership.
Translate host-specific settings when orchestrating or dispatching within Antigravity.

## Dispatch and context

Antigravity supports both native subagents inside the IDE/app harness and CLI worker execution via `agy`.

- **Native Subagents (`invoke_subagent`):**
  - Use `invoke_subagent` with `TypeName`, `Role`, `Prompt`, and `Workspace` (`'inherit'` for shared checkout, `'branch'` or `'share'` for worktrees).
  - Subagents run asynchronously in the background. The parent session receives a **reactive wakeup message** upon subagent completion — **do not poll in a loop**.
  - Pass a self-contained brief containing: task goal, write-set boundaries, relevant specs/diffs, base commit, and verification commands.
  - Subagent communication uses `send_message` with the worker's `ConversationId`.
  - For follow-ups, continue messaging the same subagent rather than spawning duplicate workers.
- **Dynamic Roles (`define_subagent`):**
  - If a specialized worker type is needed (e.g. read-only reviewer, test runner), create it dynamically using `define_subagent` with specific tool permissions (`EnableWriteTools: false` for strict read-only review).
- **CLI Workers (`agy` CLI):**
  - When running `agy` as an external CLI worker or in headless automation, invoke via the shell tool with non-interactive inputs.
  - Obey sandbox permissions: commands default to standard sandbox isolation (`BypassSandbox: false`). Do not bypass unless network or elevated privileges are strictly required.

## Workspace and artifacts

- Session artifacts are written directly to `<appDataDir>/brain/<conversation-id>/...`.
- Scratch scripts and temporary test files are placed in `<appDataDir>/brain/<conversation-id>/scratch/`.
- Isolated parallel lanes should specify `Workspace: 'branch'` or run inside dedicated git worktrees to prevent write-set collisions.

## Budget and measurement

- Transcripts are recorded per session in JSON Lines format:
  `<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`
- To measure token consumption before and after task execution:
  ```sh
  python3 <model-routing>/scripts/usage.py agy --transcript <transcript.jsonl> > before.json
  # Execute the delegated task...
  python3 <model-routing>/scripts/usage.py agy --transcript <transcript.jsonl> > after.json
  python3 <model-routing>/scripts/usage.py diff before.json after.json > task-usage.json
  ```
- Each `PLANNER_RESPONSE` step records exclusive `input_tokens`, `cache_read_tokens`, and `output_tokens`.
- To inspect live Antigravity subscription quotas (Gemini pool vs Claude/GPT pool 5h and weekly limits):
  ```sh
  python3 <model-routing>/scripts/quota.py agy
  ```
  When the Gemini 5-hour limit drops low, orchestrators can route tasks to the Claude/GPT pool without downtime.
