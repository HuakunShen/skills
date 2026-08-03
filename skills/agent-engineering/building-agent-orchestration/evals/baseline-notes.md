# Baseline Notes: building-agent-orchestration

## Eval 1

- Prompt summary: parallel research agents and later result collection
- Missing or weak behavior:
  - Did not explicitly require immediate `task_id` semantics.
  - Did not specify cancellation behavior.
  - Did not define concurrency limits or slot release.
  - Did not test duplicate parent notifications.
  - Did not name an output collection tool such as `background_output`.
- Useful baseline behavior:
  - Recommended detached fan-out with persisted handles.
  - Included child job IDs and durable storage.
  - Suggested event hooks or polling.
  - Kept result collection separate from launch.

## Eval 2

- Prompt summary: Team Mode with lead, tasks, mailbox, and tmux
- Missing or weak behavior:
  - Did not explicitly require atomic file locks for task claims or mailbox writes.
  - Did not validate member eligibility before spawn.
  - Did not forbid nested teams.
  - Did not define max wall-clock, message, turn, or member limits.
  - Did not test competing claims, mailbox ack, or mailbox broadcast.
- Useful baseline behavior:
  - Recommended a lead agent, task ledger, mailbox, worker agents, and orchestrator runtime.
  - Treated tmux as presentation only.
