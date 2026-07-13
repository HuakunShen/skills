# Agent Plugin Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a multi-harness skill family for writing, injecting, orchestrating, porting, and testing coding-agent plugins.

**Architecture:** Create five focused skills at the repository root, each with its own `SKILL.md` and `evals/evals.json`. Use the approved spec as the source of truth, but follow TDD for skills: write eval prompts, observe baseline behavior, then write each skill to address the observed gaps.

**Tech Stack:** Markdown `SKILL.md` files, JSON eval metadata, shell/Bun/OpenCode/Claude CLI reference patterns, existing Superpowers skill-creation workflow.

---

## File Structure

- Create `writing-opencode-plugins/SKILL.md`: OpenCode plugin and custom tool implementation guide.
- Create `writing-opencode-plugins/evals/evals.json`: eval prompts and expected outcomes for OpenCode plugin authoring.
- Create `injecting-agent-behavior/SKILL.md`: commands, skills, agents, instructions, MCP, and context injection guide.
- Create `injecting-agent-behavior/evals/evals.json`: eval prompts and expected outcomes for behavior injection.
- Create `building-agent-orchestration/SKILL.md`: background agents, delegation, and team coordination guide.
- Create `building-agent-orchestration/evals/evals.json`: eval prompts and expected outcomes for orchestration design.
- Create `porting-agent-plugins-across-harnesses/SKILL.md`: OpenCode, Claude Code, Codex portability guide.
- Create `porting-agent-plugins-across-harnesses/evals/evals.json`: eval prompts and expected outcomes for cross-harness porting.
- Create `testing-agent-plugins/SKILL.md`: plugin and behavior-shaping skill test strategy guide.
- Create `testing-agent-plugins/evals/evals.json`: eval prompts and expected outcomes for test planning and implementation.
- Modify `README.md`: add a short catalog entry for the five new skills.

## Shared Skill Writing Rules

Use these rules for every `SKILL.md` in this plan:

- Frontmatter must include `name` and `description` only unless a specific compatibility field is needed.
- `name` must match the directory name and use lowercase hyphenated words.
- `description` starts with `Use when...` and describes triggering conditions, not the workflow.
- Keep the body concise and task-oriented; avoid dumping full reference docs.
- Label source authority: official docs, Context7/OpenCode docs, observed Superpowers pattern, observed oh-my-openagent pattern.
- Include `When Not To Use`, `Default Approach`, `Testing`, and `Common Mistakes` sections.
- Reference other skills by name instead of copying their full content.
- Do not claim experimental OpenCode hooks are stable.

## Shared Eval JSON Shape

Each `evals/evals.json` must use this shape:

```json
{
  "skill_name": "writing-opencode-plugins",
  "evals": [
    {
      "id": 1,
      "prompt": "Build a local OpenCode plugin that adds a tool wrapping a shell script and injects one env var.",
      "expected_output": "The agent should propose a local or npm OpenCode plugin using @opencode-ai/plugin, tool.schema, shell.env, deterministic shell execution, temp/config-safe testing, and no unsafe raw session prompt injection.",
      "files": []
    }
  ]
}
```

Use the actual skill name and eval prompts listed in each task below.

### Task 1: Eval Scaffolding

**Files:**
- Create: `writing-opencode-plugins/evals/evals.json`
- Create: `injecting-agent-behavior/evals/evals.json`
- Create: `building-agent-orchestration/evals/evals.json`
- Create: `porting-agent-plugins-across-harnesses/evals/evals.json`
- Create: `testing-agent-plugins/evals/evals.json`

- [ ] **Step 1: Create eval directories**

Run:

```bash
mkdir -p writing-opencode-plugins/evals injecting-agent-behavior/evals building-agent-orchestration/evals porting-agent-plugins-across-harnesses/evals testing-agent-plugins/evals
```

Expected: command exits 0 and creates five `evals/` directories.

- [ ] **Step 2: Create OpenCode plugin evals**

Write `writing-opencode-plugins/evals/evals.json` exactly:

```json
{
  "skill_name": "writing-opencode-plugins",
  "evals": [
    {
      "id": 1,
      "prompt": "Build a local OpenCode plugin that adds a custom tool wrapping a shell script and injects PROJECT_ROOT plus MY_TOOL_TOKEN into shell commands.",
      "expected_output": "Uses @opencode-ai/plugin, exports a Plugin, defines a tool with tool.schema, calls the script through Bun.$ or ctx.$ with quoted arguments, implements shell.env for environment injection, returns structured text or JSON, and includes unit plus optional opencode run tests.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "Review this planned OpenCode plugin: it uses experimental.chat.messages.transform to inject a hidden reminder on every turn and calls client.session.promptAsync directly from two hooks. Tell me what to change before implementation.",
      "expected_output": "Warns that experimental transforms and direct prompt injection are risky, recommends file/config primitives first, requires duplicate-injection guards or a shared dispatch gate, and separates official API from observed third-party patterns.",
      "files": []
    }
  ]
}
```

- [ ] **Step 3: Create injection evals**

Write `injecting-agent-behavior/evals/evals.json` exactly:

```json
{
  "skill_name": "injecting-agent-behavior",
  "evals": [
    {
      "id": 1,
      "prompt": "Package three slash commands, two project skills, and one review subagent for OpenCode. The commands need arguments and one command should run in a subtask.",
      "expected_output": "Recommends .opencode/commands or config.command, uses $ARGUMENTS/$1 and agent/subtask/model fields correctly, creates SKILL.md files in valid discovery paths, creates an agent with mode subagent and permissions, and includes discovery tests with temp config directories.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "I want a plugin to auto-load my rules and skill docs into every session. Should I use commands, skills.paths, instructions, or chat.message transforms?",
      "expected_output": "Ranks file/config-level primitives before transforms, explains when to use commands, skills.paths, instructions/rules, MCP config, and synthetic message injection, and includes idempotency and priority tests.",
      "files": []
    }
  ]
}
```

- [ ] **Step 4: Create orchestration evals**

Write `building-agent-orchestration/evals/evals.json` exactly:

```json
{
  "skill_name": "building-agent-orchestration",
  "evals": [
    {
      "id": 1,
      "prompt": "Design an OpenCode plugin feature that launches three independent research agents in parallel, lets the parent keep working, and collects results later.",
      "expected_output": "Chooses tool-backed background tasks over prompt-only delegation, returns task IDs immediately, defines background_output and cancellation behavior, uses concurrency limits, result collection, cleanup, and tests concurrent launch plus cancellation.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "I want to build Team Mode with a lead agent, shared tasks, mailbox, and optional tmux panes. What architecture and guardrails do I need?",
      "expected_output": "Requires durable state, mailbox, tasklist with atomic locks, member eligibility, lifecycle cleanup, spawn limits, no nested teams, optional tmux integration, and tests for claims, delivery, cleanup, and duplicate notifications.",
      "files": []
    }
  ]
}
```

- [ ] **Step 5: Create cross-harness evals**

Write `porting-agent-plugins-across-harnesses/evals/evals.json` exactly:

```json
{
  "skill_name": "porting-agent-plugins-across-harnesses",
  "evals": [
    {
      "id": 1,
      "prompt": "Port an OpenCode plugin with commands, skills, MCP config, and one custom tool to Claude Code and Codex without duplicating the business logic.",
      "expected_output": "Separates portable core from adapters, creates a capability matrix, maps commands/skills/tools/MCP/permissions per harness, refuses unsupported parity claims, and proposes adapter-specific acceptance tests.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "Design a plugin package that works mainly in OpenCode today but can later support Claude Code, Codex, and Gemini. What should go in core versus adapters?",
      "expected_output": "Places parsing, formatting, config schema, prompts, and deterministic helpers in core; places hook registration, tool naming, permissions, auth, UI, filesystem paths, and session APIs in adapters; includes clean-session load tests.",
      "files": []
    }
  ]
}
```

- [ ] **Step 6: Create testing evals**

Write `testing-agent-plugins/evals/evals.json` exactly:

```json
{
  "skill_name": "testing-agent-plugins",
  "evals": [
    {
      "id": 1,
      "prompt": "Given a plugin that registers a command, custom tool, shell.env hook, and message transform, write the unit, discovery, integration, and safety tests.",
      "expected_output": "Includes direct tool.execute tests, hook input/output tests, temp config command and skill discovery tests, shell quoting tests, optional opencode run integration, and static or runtime safety checks for duplicate injection and secret leakage.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "Create a test strategy for a background-agent orchestration plugin with cancellation, retries, parent notifications, and team-style task claiming.",
      "expected_output": "Covers concurrency limits, FIFO queueing, cancellation slot release, retry classification, one parent notification per completion edge, atomic task claiming, mailbox delivery, cleanup, and spawn limits.",
      "files": []
    }
  ]
}
```

- [ ] **Step 7: Validate JSON**

Run:

```bash
python3 -m json.tool writing-opencode-plugins/evals/evals.json >/dev/null && python3 -m json.tool injecting-agent-behavior/evals/evals.json >/dev/null && python3 -m json.tool building-agent-orchestration/evals/evals.json >/dev/null && python3 -m json.tool porting-agent-plugins-across-harnesses/evals/evals.json >/dev/null && python3 -m json.tool testing-agent-plugins/evals/evals.json >/dev/null
```

Expected: command exits 0 with no output.

### Task 2: `writing-opencode-plugins` Skill

**Files:**
- Create: `writing-opencode-plugins/SKILL.md`
- Read: `docs/superpowers/specs/2026-06-02-agent-plugin-skills-design.md`
- Read: `writing-opencode-plugins/evals/evals.json`

- [ ] **Step 1: Run baseline eval prompts before writing the skill**

Run the two prompts in `writing-opencode-plugins/evals/evals.json` without loading the new skill. Save notes manually in `writing-opencode-plugins/evals/baseline-notes.md` using this exact structure:

```markdown
# Baseline Notes: writing-opencode-plugins

## Eval 1

- Prompt summary: custom tool wraps shell script and injects env vars
- Missing or weak behavior:
- Useful baseline behavior:

## Eval 2

- Prompt summary: risky message transform and direct promptAsync review
- Missing or weak behavior:
- Useful baseline behavior:
```

Expected: notes identify any missing guidance about source authority, shell safety, tests, or prompt-injection risk.

- [ ] **Step 2: Create the skill file**

Write `writing-opencode-plugins/SKILL.md` with this frontmatter and sections:

````markdown
---
name: writing-opencode-plugins
description: Use when writing, modifying, debugging, packaging, or reviewing OpenCode plugins, custom tools, plugin hooks, shell-backed tools, npm/local plugin setup, or @opencode-ai/plugin code
---

# Writing OpenCode Plugins

## Overview

OpenCode plugins are JavaScript or TypeScript modules that return hook implementations. Prefer the smallest official surface that solves the problem: local plugin files, custom tools, commands, agents, skills, permissions, and documented hooks before experimental message transforms or session mutation.

## Source Authority

- Official OpenCode docs are authoritative for plugin loading, custom tools, commands, agents, skills, permissions, `shell.env`, `event`, `tool.execute.before`, `tool.execute.after`, and documented experimental compaction hooks.
- Context7 `/websites/opencode_ai_plugins` is a current docs mirror and example source.
- Superpowers and oh-my-openagent are observed production patterns, not official API guarantees.

## When Not To Use

- Use `injecting-agent-behavior` when the task is mostly commands, skills, agents, rules, or context injection.
- Use `building-agent-orchestration` when the task is mostly background agents, subagents, or teams.
- Use `porting-agent-plugins-across-harnesses` when the task must support multiple coding tools.
- Use `testing-agent-plugins` when the user only asks how to verify a plugin.

## Default Approach

1. Identify whether the user needs a plugin, custom tool, command, agent, skill, MCP config, or plain project file.
2. Use official docs paths and hooks first.
3. Keep plugin entrypoints thin: parse config, register hooks/tools, delegate real work to testable helpers.
4. Return strings from tools; use JSON strings when the output is structured.
5. Treat experimental hooks and direct session prompt injection as risky.

## Minimal Plugin Shape

```typescript
import { type Plugin, tool } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ client, $, directory, worktree }) => {
  await client.app.log({
    body: { service: "my-plugin", level: "info", message: "Plugin initialized" },
  })

  return {
    tool: {
      project_info: tool({
        description: "Return the current OpenCode directory and worktree",
        args: {},
        async execute() {
          return JSON.stringify({ directory, worktree })
        },
      }),
    },
    "shell.env": async (_input, output) => {
      output.env.PROJECT_ROOT = directory
    },
  }
}

export default MyPlugin
```

## Shell-Backed Tools

- Define the LLM-facing tool in TypeScript even if the implementation is Python, Bash, or another binary.
- Build script paths from `context.worktree` or `directory`.
- Pass arguments through `Bun.$` or `ctx.$` interpolation instead of string concatenation.
- Set timeouts or explicit failure handling for slow scripts.
- Never expose secrets in tool output or logs.

## Hook Selection

| Need | Prefer |
| --- | --- |
| Add callable capability | `tool` or `.opencode/tools/` |
| Modify shell environment | `shell.env` |
| Guard or rewrite tool args | `tool.execute.before` |
| Truncate or annotate results | `tool.execute.after` |
| React to lifecycle events | `event` |
| Preserve compaction state | `experimental.session.compacting` with caution |
| Inject hidden context | Prefer files/config first; use message transforms only with idempotency guards |

## Testing

- Unit-test tool `execute(args, context)` directly.
- Unit-test hooks by passing fake `input` and mutable `output` objects.
- Test shell wrappers with weird arguments, non-zero exit, stderr, and missing script cases.
- Smoke-test plugin syntax/imports.
- Run optional `opencode run --print-logs --format json` integration tests only in isolated temp config directories.

## Common Mistakes

- Treating oh-my-openagent internals as official OpenCode API.
- Using experimental message transforms for something a command, skill, or agent file can do.
- Calling raw session prompt APIs from multiple hooks without a shared gate.
- Returning huge unstructured tool output.
- Overriding built-in tool names accidentally.
````

- [ ] **Step 3: Adjust from baseline notes**

If `baseline-notes.md` records a concrete failure not covered by the draft, add one bullet under `Common Mistakes` or `Testing` that directly addresses it. Do not add broad speculative sections.

- [ ] **Step 4: Verify skill frontmatter and size**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('writing-opencode-plugins/SKILL.md')
s = p.read_text()
assert s.startswith('---\nname: writing-opencode-plugins\n')
assert 'description: Use when ' in s
assert len(s.splitlines()) < 500
PY
```

Expected: command exits 0.

### Task 3: `injecting-agent-behavior` Skill

**Files:**
- Create: `injecting-agent-behavior/SKILL.md`
- Create: `injecting-agent-behavior/evals/baseline-notes.md`

- [ ] **Step 1: Run baseline eval prompts before writing the skill**

Use `injecting-agent-behavior/evals/evals.json`. Save `injecting-agent-behavior/evals/baseline-notes.md` with the same baseline notes structure used in Task 2, changing the title and eval summaries.

Expected: notes identify whether baseline behavior misses command arguments, subtask routing, skill name rules, priority, or idempotent injection.

- [ ] **Step 2: Create the skill file**

Write `injecting-agent-behavior/SKILL.md` with this content:

```markdown
---
name: injecting-agent-behavior
description: Use when adding or reviewing agent commands, command skills, SKILL.md discovery, custom agents, rules, instructions, MCP wiring, context injection, or behavior nudges in coding-agent tools
---

# Injecting Agent Behavior

## Overview

Behavior injection should use the least invasive primitive that works. Prefer documented command, skill, agent, rule, instruction, permission, and MCP mechanisms before hidden message transforms.

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
- Use `$ARGUMENTS` for the full argument string and `$1`, `$2`, `$3` for positional arguments.
- Use `!\`command\`` only when command output is safe to include in the prompt.
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
- Use permissions instead of deprecated broad tool toggles when possible.
- Use `hidden: true` only for internal subagents that should not appear in user autocomplete.

## Context Injection

- Prefer files and config over hidden message parts.
- If using a message transform, add an idempotency marker and skip if already injected.
- Keep injected text short and scoped to the current session or task.
- Do not inject secrets.

## Testing

- Use fixture directories for commands, skills, and agents.
- Assert discovered names, scope, content markers, and disabled-plugin behavior.
- Test command argument substitution and subtask routing.
- Test skill permission allow, ask, and deny behavior where the harness supports it.

## Common Mistakes

- Loading every rule into every session when a command or skill would be on-demand.
- Hiding behavior in transforms with no discoverability.
- Forgetting command and skill priority tests.
- Mixing Claude Code plugin manifest assumptions into plain OpenCode config without an adapter.
```

- [ ] **Step 3: Adjust from baseline notes**

Add one targeted bullet if baseline notes show a missed failure mode. Keep the file under 500 lines.

- [ ] **Step 4: Verify skill frontmatter and size**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('injecting-agent-behavior/SKILL.md')
s = p.read_text()
assert s.startswith('---\nname: injecting-agent-behavior\n')
assert 'description: Use when ' in s
assert len(s.splitlines()) < 500
PY
```

Expected: command exits 0.

### Task 4: `building-agent-orchestration` Skill

**Files:**
- Create: `building-agent-orchestration/SKILL.md`
- Create: `building-agent-orchestration/evals/baseline-notes.md`

- [ ] **Step 1: Run baseline eval prompts before writing the skill**

Use `building-agent-orchestration/evals/evals.json`. Save baseline notes.

Expected: notes identify whether baseline behavior misses determinism, task IDs, cancellation, concurrency, atomic state, mailbox delivery, or spawn limits.

- [ ] **Step 2: Create the skill file**

Write `building-agent-orchestration/SKILL.md` with this content:

```markdown
---
name: building-agent-orchestration
description: Use when designing, implementing, or reviewing background agents, subagent delegation, parallel research agents, agent teams, task routing, result collection, cancellation, or multi-agent coordination
---

# Building Agent Orchestration

## Overview

Use the simplest coordination model that gives the user reliable results. Prompt-only delegation is easy but weakly enforceable. Tool-backed background tasks and team systems need explicit state, limits, cancellation, and tests.

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
4. Parent collects results with a separate output tool.
5. Cancellation releases slots and cleans up state.
6. Parent notifications are idempotent.

## Team Pattern

- Use a lead only when coordination is truly shared.
- Store team config, runtime state, mailbox, tasklist, and worktrees in predictable directories.
- Validate member eligibility before spawning.
- Use atomic locks for task claiming and mailbox writes.
- Forbid nested teams unless there is a proven lifecycle design.
- Add max members, max messages, max turns, and max wall-clock limits.

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

## Common Mistakes

- Using prompt wording to pretend parallelism is guaranteed.
- Building Team Mode when background tasks are enough.
- Missing cancellation or cleanup paths.
- Letting subagents recursively spawn unlimited agents.
- Sharing mutable state without locks.
```

- [ ] **Step 3: Adjust from baseline notes**

Add one targeted bullet if the baseline misses an orchestration risk. Keep the file under 500 lines.

- [ ] **Step 4: Verify skill frontmatter and size**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('building-agent-orchestration/SKILL.md')
s = p.read_text()
assert s.startswith('---\nname: building-agent-orchestration\n')
assert 'description: Use when ' in s
assert len(s.splitlines()) < 500
PY
```

Expected: command exits 0.

### Task 5: `porting-agent-plugins-across-harnesses` Skill

**Files:**
- Create: `porting-agent-plugins-across-harnesses/SKILL.md`
- Create: `porting-agent-plugins-across-harnesses/evals/baseline-notes.md`

- [ ] **Step 1: Run baseline eval prompts before writing the skill**

Use `porting-agent-plugins-across-harnesses/evals/evals.json`. Save baseline notes.

Expected: notes identify whether baseline behavior overclaims parity, fails to separate core/adapters, or omits acceptance tests.

- [ ] **Step 2: Create the skill file**

Write `porting-agent-plugins-across-harnesses/SKILL.md` with this content:

```markdown
---
name: porting-agent-plugins-across-harnesses
description: Use when porting, designing, or reviewing plugins, skills, commands, tools, MCPs, or agent workflows across OpenCode, Claude Code, Codex, Gemini, Cursor, or multiple coding-agent harnesses
---

# Porting Agent Plugins Across Harnesses

## Overview

Port behavior, not implementation details. Put deterministic logic in a portable core and keep each harness adapter responsible for its own hooks, paths, permissions, tools, UI, and session APIs.

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

| Capability | OpenCode | Claude Code | Codex | Decision |
| --- | --- | --- | --- | --- |
| Commands | `.opencode/commands`, config `command` | plugin commands | plugin/component dependent | Map or omit |
| Skills | `SKILL.md` discovery and `skill` tool | skills/plugin support | component dependent | Map or omit |
| Subagents | agents and task/subagent mechanisms | Task/subagents | limited by Codex plugin surface | Map or omit |
| Hooks | OpenCode plugin hooks | Claude hook/plugin model | Codex events/components | Adapter-specific |
| MCP | config and observed skill-embedded patterns | MCP config | component dependent | Adapter-specific |

## Tool Mapping

- Map Claude Code `TodoWrite` to OpenCode `todowrite` when adapting skills.
- Map Claude Code `Task` to OpenCode subagent mechanisms or background tools only if the target supports them.
- Map shell and file tools by capability, not by exact name.
- Do not expose a skill to a harness if its required tools are unavailable.

## Acceptance Tests

- Clean-session plugin load test for every harness.
- Command/skill/agent discovery test for every adapter that claims support.
- Shared core unit tests that run once and are reused by all adapters.
- Negative test for unsupported features: the adapter should fail closed or document the omission.

## Common Mistakes

- Copying OpenCode hook names into a harness that does not have those hooks.
- Hiding adapter assumptions inside shared core.
- Claiming Team Mode or background agents are portable when the target cannot spawn child sessions.
- Forgetting tool-name translation in ported skills.
```

- [ ] **Step 3: Adjust from baseline notes**

Add one targeted bullet for an observed overclaim or missing adapter boundary. Keep the file under 500 lines.

- [ ] **Step 4: Verify skill frontmatter and size**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('porting-agent-plugins-across-harnesses/SKILL.md')
s = p.read_text()
assert s.startswith('---\nname: porting-agent-plugins-across-harnesses\n')
assert 'description: Use when ' in s
assert len(s.splitlines()) < 500
PY
```

Expected: command exits 0.

### Task 6: `testing-agent-plugins` Skill

**Files:**
- Create: `testing-agent-plugins/SKILL.md`
- Create: `testing-agent-plugins/evals/baseline-notes.md`

- [ ] **Step 1: Run baseline eval prompts before writing the skill**

Use `testing-agent-plugins/evals/evals.json`. Save baseline notes.

Expected: notes identify whether baseline behavior misses isolated config directories, optional integration tests, direct hook/tool tests, or static architecture audits.

- [ ] **Step 2: Create the skill file**

Write `testing-agent-plugins/SKILL.md` with this content:

```markdown
---
name: testing-agent-plugins
description: Use when writing, reviewing, or improving tests, evals, smoke tests, integration tests, discovery tests, safety audits, or verification plans for agent plugins, skills, commands, tools, hooks, or orchestration systems
---

# Testing Agent Plugins

## Overview

Agent plugins shape behavior, so test both code paths and harness behavior. Keep fast deterministic tests separate from optional integration tests that require OpenCode, Claude CLI, Codex, or other external tools.

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
- Optional `opencode run --print-logs --format json` integration tests.
- Shell wrapper tests for quoting, stderr, exit code, timeout, and missing binary behavior.

## Orchestration Tests

- Background launch returns a task ID immediately.
- Concurrent launches do not wait sequentially.
- Concurrency limits queue and release correctly.
- Cancellation releases slots and cleans up state.
- Parent notifications happen once across racing idle/error/completion edges.
- Team-style task claiming uses atomic locks.
- Mailbox delivery supports direct, broadcast, ack, and payload-limit behavior.

## Skill Tests

- Create eval prompts before writing the skill.
- Run baseline behavior without the skill and record failures.
- Run with the skill and compare output quality.
- Use marker strings to prove the intended skill version loaded.
- Use eval viewer or a written review table for human feedback.

## Static Audits

Use static audits when runtime tests can miss architectural bypasses. Examples:

- Raw `session.prompt` or `session.promptAsync` outside a dispatch gate.
- Forbidden imports or direct shell execution helpers.
- Missing cleanup registration for background managers.
- Tool names that collide with built-ins unintentionally.

## Common Mistakes

- Mutating the user's real config directory during tests.
- Requiring external CLIs for every test instead of making integration optional.
- Testing only the happy path.
- Skipping negative tests for disabled plugins, duplicate names, denied permissions, and missing files.
- Treating an agent's final answer as proof that the correct skill or plugin loaded.
```

- [ ] **Step 3: Adjust from baseline notes**

Add one targeted bullet for a missed testing category. Keep the file under 500 lines.

- [ ] **Step 4: Verify skill frontmatter and size**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('testing-agent-plugins/SKILL.md')
s = p.read_text()
assert s.startswith('---\nname: testing-agent-plugins\n')
assert 'description: Use when ' in s
assert len(s.splitlines()) < 500
PY
```

Expected: command exits 0.

### Task 7: README Catalog

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Replace `README.md` with:

````markdown
```bash
npx skills add https://github.com/HuakunShen/skills
```

## Skills

- `cloudflare-monorepo`: multi-Cloudflare-Worker monorepo patterns.
- `deepwiki-badge`: generate and insert DeepWiki badges.
- `journal`: document recent changes and decisions.
- `sync-wiki`: update `.repowiki` docs from recent changes.
- `writing-opencode-plugins`: write and review OpenCode plugins and custom tools.
- `injecting-agent-behavior`: add commands, skills, agents, rules, instructions, MCPs, and context injection.
- `building-agent-orchestration`: design background agents, delegation, and team coordination.
- `porting-agent-plugins-across-harnesses`: split portable core and adapters for OpenCode, Claude Code, Codex, and similar tools.
- `testing-agent-plugins`: test plugins, skills, commands, hooks, and orchestration systems.
````

Expected: README lists all new skills.

### Task 8: Verification and Review Package

**Files:**
- Read: all five `SKILL.md` files
- Read: all five `evals/evals.json` files
- Read: `README.md`

- [ ] **Step 1: Validate all JSON eval files**

Run:

```bash
python3 -m json.tool writing-opencode-plugins/evals/evals.json >/dev/null && python3 -m json.tool injecting-agent-behavior/evals/evals.json >/dev/null && python3 -m json.tool building-agent-orchestration/evals/evals.json >/dev/null && python3 -m json.tool porting-agent-plugins-across-harnesses/evals/evals.json >/dev/null && python3 -m json.tool testing-agent-plugins/evals/evals.json >/dev/null
```

Expected: command exits 0 with no output.

- [ ] **Step 2: Validate frontmatter names match directories**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
for p in Path('.').glob('*/SKILL.md'):
    text = p.read_text()
    expected = p.parent.name
    assert f'name: {expected}' in text, f'{p}: missing matching name'
    assert 'description: Use when ' in text, f'{p}: description must start with Use when'
print('skill frontmatter ok')
PY
```

Expected output includes `skill frontmatter ok`.

- [ ] **Step 3: Check for forbidden placeholders**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
needles = ['TB' + 'D', 'TO' + 'DO', 'implement ' + 'later', 'fill in ' + 'details']
bad = []
for p in [*Path('.').glob('*/SKILL.md'), *Path('.').glob('*/evals/evals.json')]:
    text = p.read_text()
    for n in needles:
        if n in text:
            bad.append(f'{p}: {n}')
if bad:
    raise SystemExit('\n'.join(bad))
print('no placeholders')
PY
```

Expected output includes `no placeholders`.

- [ ] **Step 4: Review source authority language**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
required = ['Source Authority', 'official', 'observed']
for p in Path('.').glob('*/SKILL.md'):
    text = p.read_text().lower()
    if p.parent.name in {'writing-opencode-plugins', 'injecting-agent-behavior'}:
        assert 'source authority' in text, f'{p}: missing source authority section'
        assert 'observed' in text, f'{p}: missing observed-pattern warning'
print('source authority checks ok')
PY
```

Expected output includes `source authority checks ok`.

- [ ] **Step 5: Inspect git diff**

Run:

```bash
git status --short
git diff -- README.md docs/superpowers/plans/2026-06-02-agent-plugin-skills.md docs/superpowers/specs/2026-06-02-agent-plugin-skills-design.md writing-opencode-plugins injecting-agent-behavior building-agent-orchestration porting-agent-plugins-across-harnesses testing-agent-plugins
```

Expected: only intended docs, skill directories, eval files, and README changes appear.

- [ ] **Step 6: Human review checkpoint**

Summarize:

- Which skills were created.
- Which eval prompts exist.
- Which verification commands passed.
- Any baseline behavior that caused skill content adjustments.

Do not commit unless the user explicitly requests it.
