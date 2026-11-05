# Codex adapter

Keep the shared intake, register, plan/review/implement loop and write-set ownership.
Translate host-specific settings rather than copying Claude agent configuration.

## Dispatch and context

Inspect the actual spawn tool's schema before dispatch: CLI, desktop and managed
hosts can expose different parameters.

- Where `fork_context` exists, use `false` for self-contained implementation or
  review briefs. This omits parent chat history, not system instructions, project
  rules or tools. Include the task, relevant owner decisions, plan/diff, file/symbol
  manifest, worktree, write set, base commit and checks.
- Use `true` only when the task needs substantial parent discussion that a brief
  cannot convey efficiently. Forking history does not establish a cache hit or saving.
- For a closely related follow-up, use `send_input` on the same worker. If closed,
  use `resume_agent` first when supported. Review fixes do not automatically need
  a new worker. For independent review, prefer a fresh brief and evidence.
- Use completion notifications or the host's wait API. Close completed agents once
  no follow-up is expected; open completed agents can consume concurrency slots.
- Verify the assigned workspace. A subagent is not automatically a separate worktree.
  Integrate isolated changes using the host's mechanism, or check shared-tree diffs.

In the desktop session inspected on 2026-10-31, `spawn_agent` exposed
`fork_context`, `message/items`, `model`, and `reasoning_effort`, but no role selector.
In that interface, include worker instructions in the brief; do not invent
`agent_type` or Claude's `subagent_type`. Recheck on other hosts and versions.

## Custom worker

The template [lane-worker.toml](../templates/agents/lane-worker.toml) is for Codex
clients that support selecting custom agents. Copy it to `.codex/agents/` for a
project or `~/.codex/agents/` for personal use, then verify the role is discoverable
and selectable in the target client. It is a template, not an automatic installation.
It inherits model/effort; use the user's routing preferences rather than assuming
a Sonnet-to-Codex model equivalence.

Codex custom agents use TOML with `name`, `description`, `developer_instructions`
and supported config overrides. The template disables apps, plugins and memories
for a code-only worker; enable capabilities that a task actually needs. This is
not a guarantee that all MCP tools disappear. Custom roles inherit parent MCP,
provider and permissions; they cannot replace those settings. Do not translate
Claude's `tools`, `disallowedTools`, `maxTurns` or cache-TTL keys into TOML.
A narrow write set is an instruction, not a filesystem permission boundary.

## Budget and measurement

Resume versus fresh is a task decision. Fresh workers must reread code and may lose
important reasoning; handoffs can add retries. There is no validated universal
150k-token or 150-turn cutoff. Configure an optional checkpoint budget per project
and measure accepted-task cost before enforcing it.

For Codex rollout files use `model-routing/scripts/usage.py codex --path <rollout>`
to take before/after snapshots, then `usage.py diff before.json after.json`. Count
parent and task-owned children once. Cached input is a subset of input and reasoning
is a subset of output; do not add them twice. API valuation and subscription quota
are different quantities. To query live account rate limits (primary 5h and secondary
weekly windows via Codex App Server), run `model-routing/scripts/quota.py codex`. Claude
startup tests and TTL savings are not Codex results.

Compare the same task/base commit/acceptance checks with the same model and effort;
include parent coordination, child calls, handoffs, retries, time and final quality.
Repeat trials when justified. Different days' totals cannot isolate an optimization.

## Sources

Checked 2026-10-31: [official subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents),
plus the running host's spawn/send/resume/wait/close tool schemas. The schema exposed
in the current host governs what can actually be invoked.
