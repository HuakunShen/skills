---
name: testing-agent-plugins
description: Use when writing, reviewing, or improving tests, evals, smoke tests, integration tests, discovery tests, safety audits, or verification plans for agent plugins, skills, commands, tools, hooks, or orchestration systems
---

# Testing Agent Plugins

## Overview

Agent plugins shape behavior, so test both code paths and harness behavior. Keep fast deterministic tests separate from optional integration tests that require OpenCode, Claude CLI, Codex, or other external tools.

## Source Authority

- Official target harness docs and local project test commands are authoritative for test execution.
- Superpowers tests demonstrate harness smoke tests, skill-triggering tests, and isolated temp config setup.
- oh-my-openagent tests demonstrate plugin interface tests, fixture discovery tests, orchestration tests, and static audits as observed patterns.

## When Not To Use

- Use `writing-opencode-plugins` when the task is primarily implementing OpenCode plugin code.
- Use `injecting-agent-behavior` when the task is primarily adding commands, skills, agents, rules, or context injection.
- Use `building-agent-orchestration` when the task is primarily designing coordination behavior.
- Use `porting-agent-plugins-across-harnesses` when the task is primarily cross-harness adapter design.

## Test Layers

| Layer | What it proves |
| --- | --- |
| Unit | Tool helpers, parsers, formatters, and hook functions behave deterministically |
| Discovery | Commands, skills, agents, plugins, and MCP configs are found from expected paths |
| Integration | The real harness loads and uses the plugin in a clean session |
| Safety | Forbidden patterns, secret leakage, duplicate injection, and runaway orchestration are blocked |
| Skill eval | The agent changes behavior when the skill is available |

## OpenCode Plugin Tests

- Syntax/import smoke test for the plugin module.
- Direct `tool.execute(args, context)` tests for custom tools.
- Hook tests that pass fake `input` and mutable `output` objects.
- Temp `.opencode/commands`, `.opencode/skills`, and `.opencode/agents` fixture tests.
- Optional `opencode run --print-logs --format json` integration tests using isolated temp config directories.
- Shell wrapper tests for quoting, stderr, exit code, timeout, and missing binary behavior.
- Marker-string assertions proving the intended command, skill, or plugin source loaded.

## Orchestration Tests

- Background launch returns a task ID immediately.
- Concurrent launches do not wait sequentially.
- Concurrency limits queue and release correctly.
- FIFO queues preserve launch order when slots free.
- Cancellation releases slots and cleans up state.
- Retry classification, fallback, backoff, max-attempt, and non-retryable failure behavior are covered.
- Parent notifications happen once across racing idle/error/completion edges.
- Team-style task claiming uses atomic locks.
- Claim conflicts cannot assign the same task twice.
- Mailbox delivery supports direct, broadcast, ack, and payload-limit behavior.
- Spawn limits prevent recursive or unbounded delegation.

## Skill Tests

- Create eval prompts before writing the skill.
- Run baseline behavior without the skill and record failures.
- Run with the skill and compare output quality.
- Use marker strings to prove the intended skill version loaded.
- Use eval viewer or a written review table for human feedback.

## Static Audits

Use static audits when runtime tests can miss architectural bypasses. Examples:

- Raw `session.prompt` or `session.promptAsync` outside a dispatch gate.
- Forbidden imports, unsafe shell calls, or shell execution outside the approved wrapper.
- Missing cleanup registration for background managers.
- Tool names that collide with built-ins unintentionally.

## Common Mistakes

- Mutating the user's real config directory during tests.
- Requiring external CLIs for every test instead of making integration optional.
- Testing only the happy path.
- Skipping negative tests for disabled plugins, duplicate names, denied permissions, and missing files.
- Treating an agent's final answer as proof that the correct skill or plugin loaded.
