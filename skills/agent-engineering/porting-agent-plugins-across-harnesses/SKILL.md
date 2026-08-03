---
name: porting-agent-plugins-across-harnesses
description: Use when porting, designing, or reviewing plugins, skills, commands, tools, MCPs, or agent workflows across OpenCode, Claude Code, Codex, Gemini, Cursor, or multiple coding-agent harnesses
---

# Porting Agent Plugins Across Harnesses

## Overview

Port behavior, not implementation details. Put deterministic logic in a portable core and keep each harness adapter responsible for its own hooks, paths, permissions, tools, UI, and session APIs.

## Source Authority

- Official target harness docs are authoritative for each adapter.
- OpenCode docs and local references are strongest for OpenCode.
- Treat Claude Code, Codex, Gemini, Cursor capability entries as hypotheses until verified against current target docs or an installed harness.

## When Not To Use

- Use `writing-opencode-plugins` for OpenCode-only plugin implementation.
- Use `injecting-agent-behavior` for single-harness commands, skills, agents, rules, or context injection.
- Use `building-agent-orchestration` for background agents, task routing, or team coordination.
- Use `testing-agent-plugins` for testing-only tasks.

## Split Core From Adapters

Portable core owns:

- Config schema and migration.
- Prompt templates and formatting.
- Parsing and validation.
- Business rules.
- Deterministic helper functions.
- Tests that run without a coding-agent harness.

Harness adapters own:

- Plugin entrypoint and manifest.
- Hook registration.
- Tool names and permission keys.
- Command, skill, agent, and MCP discovery paths.
- Auth, UI toasts, logging, and shell integration.
- Session, subagent, and compaction APIs.

## Capability Matrix

Create a matrix before porting:

This table is a starting template. Add one column for every target harness named in the task, and mark unknown capabilities as verify, omit, or unsupported rather than guessing.

| Capability | OpenCode | Claude Code | Codex | Decision |
| --- | --- | --- | --- | --- |
| Commands | `.opencode/commands`, config `command` | verify current plugin/command support | verify current plugin/component support | Map or omit |
| Skills | `SKILL.md` discovery and `skill` tool | verify current skills support | verify current component support | Map or omit |
| Subagents | agents and task/subagent mechanisms | verify current task/subagent support | verify current session/agent support | Map or omit |
| Hooks | OpenCode plugin hooks | verify current hook model | verify current event model | Adapter-specific |
| MCP | config and observed skill-embedded patterns | verify current MCP config support | verify current MCP support | Adapter-specific |

For every row, choose one of: `native`, `adapter shim`, `MCP boundary`, `documented omission`, or `unsupported`.

## Tool Mapping

- Map Claude Code `TodoWrite` to OpenCode `todowrite` when adapting skills.
- Map Claude Code `Task` to OpenCode subagent mechanisms or background tools only if the target supports them.
- Map shell and file tools by capability, not by exact name.
- Do not expose a skill to a harness if its required tools are unavailable.

## Build Order

- Start with the portable core and the one adapter the user needs now.
- Do not build a generic runtime for future harnesses before a real adapter needs it.
- Add optional capabilities only when a target harness proves they are needed.
- Keep unsupported features explicit instead of silently degrading behavior.

## Acceptance Tests

- Clean-session plugin load test for every adapter that claims support.
- Command/skill/agent discovery test for every adapter that claims support.
- Shared core unit tests that run once and are reused by all adapters.
- Negative test for unsupported features: the adapter should fail closed or document the omission.
- Capability matrix review that rejects claimed parity without a native feature, shim, MCP boundary, or documented omission.

## Common Mistakes

- Copying OpenCode hook names into a harness that does not have those hooks.
- Hiding adapter assumptions inside shared core.
- Claiming Team Mode or background agents are portable when the target cannot spawn child sessions.
- Forgetting tool-name translation in ported skills.
- Overbuilding an abstract runtime instead of shipping one core plus one real adapter.
