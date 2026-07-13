---
name: building-agent-orchestration
description: Use when designing, implementing, or reviewing background agents, subagent delegation, parallel research agents, agent teams, task routing, result collection, cancellation, or multi-agent coordination
---

# Building Agent Orchestration

## Overview

Use the simplest coordination model that gives the user reliable results. Prompt-only delegation is easy but weakly enforceable. Tool-backed background tasks and team systems need explicit state, limits, cancellation, and tests.

## Source Authority

- Official target harness docs are authoritative for available subagent, session, and plugin APIs.
- OpenCode docs and local references are strongest for OpenCode command, agent, tool, and plugin behavior.
- oh-my-openagent Team Mode and background-agent internals are observed production patterns, not official OpenCode guarantees.

## When Not To Use

- Use `writing-opencode-plugins` when the task is only plugin hooks or custom tools.
- Use `injecting-agent-behavior` when the task is only commands, skills, agents, rules, or context injection.
- Use `porting-agent-plugins-across-harnesses` for cross-harness portability or capability matrices.
- Use `testing-agent-plugins` for testing-only tasks.

## Choose The Coordination Model

| Need | Use |
| --- | --- |
| One specialist answer now | Direct subagent or `@agent` |
| Several independent investigations | Parallel background tasks |
| Parent continues working while children run | Background task tools with task IDs |
| Shared task board, mailbox, and lifecycle | Team system |
| Just a better prompt | Command or skill, not orchestration |

## Background Task Pattern

1. Launch returns `task_id` immediately.
2. Task state moves through `pending`, `running`, `completed`, `error`, or `cancelled`.
3. Concurrency is limited per model, provider, or configured key.
4. Parent collects results with a separate output tool such as `background_output`.
5. Cancellation releases slots and cleans up state.
6. Parent notifications are idempotent.
7. Persist child job IDs or handles so result collection survives parent context changes.
8. Use event hooks or polling to observe progress without blocking launch.

## Team Pattern

- Use a lead only when coordination is truly shared.
- Store team config, runtime state, mailbox, tasklist, and worktrees in predictable directories.
- Validate member eligibility before spawning.
- Use atomic locks for task claiming and mailbox writes.
- Forbid nested teams unless there is a proven lifecycle design.
- Add max members, max messages, max turns, and max wall-clock limits.
- Treat tmux panes as visualization/control surfaces, not source-of-truth state.
- Keep a task ledger so claims, completion, and reassignment are auditable.

## Delegation Prompts

- Give each agent one goal and one deliverable.
- Include constraints, output format, and whether writes are allowed.
- Do not bundle unrelated goals into one deep agent call.
- Do not ask read-only agents to mutate shared team state.

## Testing

- Test concurrent launch does not wait sequentially.
- Test FIFO queueing and concurrency release.
- Test cancellation and cleanup.
- Test duplicate idle/error/completion edges produce one parent notification.
- Test team task claiming with competing members.
- Test mailbox delivery, ack, broadcast, and payload limits.
- Test member eligibility rejection and nested-team denial.

## Common Mistakes

- Using prompt wording to pretend parallelism is guaranteed.
- Building Team Mode when background tasks are enough.
- Missing cancellation or cleanup paths.
- Letting subagents recursively spawn unlimited agents.
- Sharing mutable state without locks.
