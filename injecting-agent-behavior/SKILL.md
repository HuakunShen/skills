---
name: injecting-agent-behavior
description: Use when adding or reviewing agent commands, command skills, SKILL.md discovery, custom agents, rules, instructions, MCP wiring, context injection, or behavior nudges in coding-agent tools
---

# Injecting Agent Behavior

## Overview

Behavior injection should use the least invasive primitive that works. Prefer documented command, skill, agent, rule, instruction, permission, and MCP mechanisms before hidden message transforms.

## When Not To Use

- Use `writing-opencode-plugins` when authoring plugin structure, hooks, packaging, or runtime integration.
- Use `building-agent-orchestration` for background agents, task routing, or team coordination.
- Use `porting-agent-plugins-across-harnesses` for cross-harness portability or capability matrices.
- Use `testing-agent-plugins` for testing-only tasks.

## Source Authority

- Official OpenCode docs are authoritative for `.opencode/commands`, `command` config, `.opencode/agents`, `agent` config, `SKILL.md` discovery paths, and permissions.
- Superpowers demonstrates bootstrap and skills path registration for OpenCode.
- oh-my-openagent demonstrates large-scale command, skill, and Claude Code plugin compatibility loaders.

## Default Priority

1. Project files: commands, agents, skills, rules, or MCP config in the project.
2. User/global config: reusable commands, agents, skills, and permissions.
3. Plugin `config` hook: register paths or config when packaging reusable behavior.
4. Chat or system transforms: only for context that cannot be represented by files/config.

## Commands

- Use `.opencode/commands/<name>.md` or `config.command`.
- In `config.command`, the prompt field is `template`; in markdown command files, the body is the template.
- Use `$ARGUMENTS` for the full argument string and `$1`, `$2`, `$3` for positional arguments.
- Use `` !`command` `` only when command output is safe to include in the prompt.
- Use `@path/to/file` references when file content is intentionally prompt context.
- Set `agent`, `subtask`, and `model` when routing matters.

## Skills

- Put skills in `.opencode/skills/<name>/SKILL.md`, `~/.config/opencode/skills/<name>/SKILL.md`, `.claude/skills`, or `.agents/skills` as supported by the harness.
- `name` must match the directory name and use lowercase hyphen separators.
- `description` should describe when to load the skill.
- Use `config.skills.paths` only when packaging a plugin that contributes a skills directory.
- Test duplicate names and priority because real harness behavior can differ from expectations.

## Agents

- Use `.opencode/agents/<name>.md` or `config.agent`.
- Set `mode` to `primary`, `subagent`, or `all` deliberately.
- For OpenCode, prefer the permission field; use legacy tools toggles only when maintaining an existing config.
- Use `hidden: true` only for internal subagents that should not appear in user autocomplete.

## Rules, Instructions, And MCPs

- Use documented project/user rule or instruction files for stable always-on guidance when available.
- Use plugin config/instructions registration only when packaging reusable behavior and label it as harness/plugin-specific.
- Use MCP config for external tools/resources; test server discovery and env allowlists separately.
- Do not use message transforms to simulate MCPs or rules.

## Context Injection

- Prefer files and config over hidden message parts.
- Treat plugin `config.instructions` as observed plugin/config behavior; prefer documented project files when they solve the problem.
- If using a message transform, add an idempotency marker and skip if already injected.
- Keep injected text short and scoped to the current session or task.
- Do not inject secrets.

## Testing

- Use fixture directories for commands, skills, and agents.
- Assert discovered names, scope, content markers, and disabled-plugin behavior.
- Test command argument substitution and subtask routing.
- Test command, agent, tool, and skill access permissions where the harness exposes them.
- Test duplicate command/skill names across project and global scopes.
- Test repeated transform invocations so hidden context is not duplicated.

## Common Mistakes

- Loading every rule into every session when a command or skill would be on-demand.
- Hiding behavior in transforms with no discoverability.
- Forgetting command and skill priority tests.
- Mixing Claude Code plugin manifest assumptions into plain OpenCode config without an adapter.
- Using `.opencode/agent` when OpenCode documents `.opencode/agents`.
