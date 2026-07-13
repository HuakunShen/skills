# Agent Plugin Skills Design

Date: 2026-06-02

## Goal

Create a small family of reusable skills that teach agents how to design, implement, and evaluate coding-agent plugins across OpenCode, Claude Code, and Codex-style harnesses.

OpenCode is the primary target because it has the richest plugin surface in the local references and the user's daily workflow. Claude Code and Codex are compatibility targets: the skills should help an agent separate portable behavior from harness-specific adapters instead of blindly copying OpenCode patterns into every tool.

## Source Material

Use these sources with explicit authority levels:

- Public OpenCode docs: plugin loading, custom tools, commands, agents, skills, permissions, shell environment, plugin events, and documented experimental compaction hooks.
- Context7 `/websites/opencode_ai_plugins`: current OpenCode plugin examples and API summaries.
- Local `references/superpowers`: bootstrap injection, skill path registration, cross-harness tool mapping, and skill writing philosophy.
- Local `references/oh-my-openagent`: large-scale plugin architecture, hook composition, built-in commands, skill loading, background agents, team mode, CLI integration, and prompt-injection safety patterns.
- DeepWiki summaries for `obra/superpowers` and `code-yeongyu/oh-my-openagent`: cross-checking architecture and file references.

Treat third-party project internals as observed implementation patterns, not official API guarantees. Mark experimental OpenCode hooks and any direct session prompt injection as risky.

## Proposed Skill Family

### 1. `writing-opencode-plugins`

Purpose: guide implementation of OpenCode plugins and custom tools.

Trigger examples:

- User asks to write, modify, package, or debug an OpenCode plugin.
- User asks how to use `@opencode-ai/plugin`, plugin hooks, local plugin files, npm plugin packages, or OpenCode custom tools.
- User asks how a plugin should call shell scripts or external binaries.

Core content:

- Plugin entry point and installation locations.
- TypeScript plugin structure with `Plugin` and `tool` helpers.
- Official documented hooks: `event`, `tool.execute.before`, `tool.execute.after`, `shell.env`, and experimental compaction hooks such as `experimental.session.compacting`.
- Observed advanced hooks from real plugins: `config`, `chat.message`, `chat.params`, `chat.headers`, `command.execute.before`, `tool.definition`, `permission.ask`, `experimental.chat.messages.transform`, `experimental.chat.system.transform`.
- Tool creation with `tool.schema`, context fields, structured string returns, abort/cancellation awareness, and name collision cautions.
- Shell script execution through Bun `$`, with guidance to keep scripts deterministic, quote inputs, and avoid leaking secrets.
- Logging via `client.app.log()` where available.
- Safety defaults: prefer additive hooks, isolate failures, avoid raw prompt injection unless a shared gate exists.

### 2. `injecting-agent-behavior`

Purpose: guide injection of commands, skills, rules, instructions, MCPs, and contextual nudges into agents.

Trigger examples:

- User asks to add slash commands, command skills, behavior rules, auto-loaded skills, or project-level instructions.
- User asks how to make an agent load a skill automatically or expose plugin-provided skills.
- User asks how to inject context into sessions or messages.

Core content:

- Prefer file/config-level primitives before invasive message transforms.
- Commands: `.opencode/commands/*.md`, `config.command`, `$ARGUMENTS`, `$1`, `!\`command\``, `@file` references, `agent`, `subtask`, and `model` routing.
- Skills: `SKILL.md` layout, OpenCode discovery paths, name rules, description quality, permission gating, and `config.skills.paths` as an observed plugin-registration pattern.
- Agents: `.opencode/agents/*.md`, `config.agent`, `mode`, `description`, `prompt`, `model`, `permission`, `hidden`, and task permissions.
- Instructions/rules: when to inject via project files versus plugin hooks.
- MCPs: distinguish global/project MCP config from skill-embedded MCP patterns observed in oh-my-openagent.
- Message transforms: use `synthetic: true` or equivalent hidden context only when supported and only after checking for duplicate injection.

### 3. `building-agent-orchestration`

Purpose: guide multi-agent orchestration design.

Trigger examples:

- User asks to create background agents, subagent teams, task delegation, agent routing, or an orchestrator plugin.
- User asks how to parallelize agents or coordinate specialists.
- User asks about `task`, `background_output`, `call_omo_agent`, Team Mode, or similar tools.

Core content:

- Decide between prompt-only delegation, tool-backed background tasks, and durable team coordination.
- Prompt-only delegation is simple but not deterministic.
- Tool-backed background tasks provide reliable launch, task IDs, status, cancellation, and result collection.
- Team coordination needs shared durable state, mailbox, task list, atomic locks, lifecycle cleanup, and explicit member eligibility.
- Agents should be scoped by role, permissions, model requirements, and whether they can re-delegate.
- Use one goal and one deliverable per delegated task.
- Never use a team system when independent background tasks are enough.
- Avoid nested teams and unbounded agent spawning.

### 4. `porting-agent-plugins-across-harnesses`

Purpose: guide cross-harness plugin and skill portability.

Trigger examples:

- User asks to support OpenCode, Claude Code, Codex, Cursor, Gemini, or multiple coding agents.
- User asks to port a plugin or skill from one harness to another.
- User asks how to design a shared core plus adapters.

Core content:

- Split portable core logic from harness adapters.
- Portable core should own parsing, formatting, business rules, prompts, config schema, and testable deterministic helpers.
- Adapter should own hook registration, tool naming, permissions, UI toasts, auth, command discovery, MCP wiring, filesystem locations, and session APIs.
- Maintain a harness capability matrix for skills, commands, agents, subagents, hooks, tools, MCP, permissions, shell, and compaction.
- Map tool names explicitly: for example Claude Code `TodoWrite` to OpenCode `todowrite`, Claude `Task` to OpenCode subagent mechanisms, and Codex event hooks to component scripts.
- Do not claim feature parity where the target harness lacks an equivalent.
- Cross-harness acceptance tests should prove the bootstrap or entrypoint actually loads in a clean session.

### 5. `testing-agent-plugins`

Purpose: guide evaluation of behavior-shaping plugins and skills.

Trigger examples:

- User asks to verify a plugin, skill, command injection, orchestration tool, or cross-harness adapter.
- User asks to add evals or confidence checks for agent behavior.

Core content:

- Apply TDD to skill documentation and plugin behavior.
- Start with baseline pressure scenarios before writing a new skill or major behavior hook.
- Verify discovery: plugin loads, commands appear, skills appear, tools are described, agents are invokable.
- Verify behavior: command templates substitute arguments, shell output injection works, permissions gate tools, hooks mutate only intended outputs.
- Verify orchestration: background tasks launch concurrently, result collection waits correctly, cancellation works, team messages are delivered once, and state cleanup happens.
- Verify safety: no secret leakage, no duplicate internal prompt injection, no unbounded retries, no raw prompt calls outside a shared gate.
- Use eval viewer workflow for human review when creating or revising skills.
- Prefer tests that use isolated temp config directories and fixture plugins over tests that mutate a real user profile.
- Distinguish fast deterministic tests from optional integration tests that require an installed harness such as OpenCode or Claude CLI.

## Reference Test Patterns Found

The reference projects do contain useful tests. The new skills should teach agents to copy the testing ideas, not the exact code.

### Superpowers Test Patterns

Superpowers uses shell-based harness tests for end-to-end behavior:

- `tests/opencode/test-plugin-loading.sh`: creates an isolated OpenCode config, verifies plugin file registration, skill directory population, required `using-superpowers` skill, JavaScript syntax, and bootstrap-path assumptions.
- `tests/opencode/test-bootstrap-caching.sh`: verifies the OpenCode message-transform bootstrap is cached and does not repeatedly probe missing files.
- `tests/opencode/test-tools.sh`: runs `opencode run --print-logs --format json` and asserts the native `skill` tool can load personal, project, and bundled skills.
- `tests/opencode/test-priority.sh`: creates same-named skills in several scopes and documents actual priority behavior, including known upstream quirks.
- `tests/opencode/run-tests.sh`: separates no-dependency tests from optional `--integration` tests that require OpenCode.
- `tests/skill-triggering/run-test.sh`: runs Claude with a natural prompt and stream JSON output, then asserts the expected skill was invoked without explicitly naming it.
- `tests/subagent-driven-dev/run-test.sh`: exercises a skill against a complete task plan in a temp workspace.
- `tests/codex-plugin-sync/test-sync-to-codex-plugin.sh`: verifies cross-harness packaging/sync behavior for Codex plugin artifacts.

Testing lessons:

- Build isolated config homes with temp directories and cleanup traps.
- Test discovery and trigger behavior through the real harness when possible.
- Keep integration tests optional and clearly marked when external CLIs are required.
- Save raw JSON/log output for debugging failed agent behavior.
- Assert marker strings in loaded skill/command content to prove the harness loaded the intended source.

### oh-my-openagent Test Patterns

oh-my-openagent uses Bun tests for lower-level plugin behavior and shell/CLI-style integration around the harness boundary:

- `src/plugin-interface.test.ts`: constructs a plugin interface with mocked managers/hooks and asserts specific OpenCode hook behavior such as `command.execute.before` and `chat.message` side effects.
- `src/tools/slashcommand/command-discovery.test.ts`: writes fixture plugin manifests, commands, and skills into temp directories, sets environment variables such as `CLAUDE_CONFIG_DIR` and `OPENCODE_CONFIG_DIR`, and asserts command/skill discovery, scope, deduplication, and plugin-disable behavior.
- `src/features/claude-code-plugin-loader/*.test.ts`: tests cross-harness plugin component loading, caching, disabled env flags, manifest parsing, command loading, agent loading, skills, MCPs, and scope filtering.
- `src/features/builtin-commands/*.test.ts`: tests generated command templates and command registry behavior.
- `src/features/builtin-skills/*.test.ts`: tests built-in skill loading, extraction from shared files, and feature-gated skills such as team mode.
- `src/features/background-agent/*.test.ts`: tests task lifecycle, concurrency limits, polling, session idle handling, cancellation, parent wake behavior, retry/fallback behavior, compaction-aware result resolution, and spawn limits.
- `src/features/team-mode/**/*.test.ts`: tests team spec parsing, member eligibility, mailbox/tasklist state, atomic updates, lifecycle, and tool behavior.
- `src/shared/prompt-async-route-audit.test.ts`: static AST audit that fails if production code calls raw `session.prompt` or `session.promptAsync` outside approved gate paths.

Testing lessons:

- Factor plugin internals so hooks, tools, loaders, and orchestrators can be tested with dependency injection.
- Use fixture directories to test command, skill, agent, and plugin discovery priority.
- Use `beforeEach`/`afterEach` to restore environment variables and delete temp directories.
- Test negative paths: disabled plugins, unknown env values, missing manifests, duplicate names, and denied permissions.
- For orchestration, test concurrency, queueing, cancellation, retry, cleanup, and duplicate notification prevention separately.
- For architectural invariants, use static audits when runtime tests would miss bypasses.

### Tests New Skills Should Recommend

For OpenCode plugin work:

- Syntax/import smoke test for the plugin module.
- Plugin-load smoke test with a temp `OPENCODE_CONFIG_DIR` or project `.opencode/plugins/` fixture.
- Tool unit tests that call `tool.execute(args, context)` directly and assert structured output.
- Hook unit tests that call the hook with fake `input` and mutable `output`, then assert exact output changes and non-target no-op behavior.
- Command discovery tests using temp `.opencode/commands/*.md` and config `command` entries.
- Skill discovery tests using temp `.opencode/skills/<name>/SKILL.md`, global config skills, and duplicate names.
- Agent discovery tests using temp `.opencode/agents/*.md` and `config.agent` entries.
- Shell wrapper tests that pass weird arguments and verify quoting, exit-code handling, timeout handling, and stderr behavior.
- Integration tests using `opencode run --print-logs --format json` only when OpenCode is installed.

For orchestration plugins:

- Background launch returns a task ID immediately.
- Multiple independent tasks actually start without sequential waits.
- `background_output` supports non-blocking status and blocking wait modes.
- Cancellation releases concurrency slots and cleans up state.
- Parent notifications happen once even if idle/error/completion edges race.
- Spawn limits prevent recursive or unbounded delegation.
- Team-style systems use atomic locks for task claiming and mailbox writes.

For cross-harness plugins:

- Shared core tests run without any harness.
- Adapter tests verify each harness-specific path, manifest, command, skill, and hook registration.
- Acceptance tests prove a clean session loads the intended bootstrap or plugin entrypoint.
- Capability matrix tests should fail when a target harness lacks a feature but the adapter claims support.

## Skill Dependencies

The skills should cross-reference, not duplicate, existing general skills:

- Use `writing-skills` when creating or changing these skills.
- Use `test-driven-development` for plugin feature implementation.
- Use `systematic-debugging` for plugin failures or hook behavior bugs.
- Use `dispatching-parallel-agents` or an equivalent orchestration skill when analyzing independent subsystems.
- Use `verification-before-completion` before claiming a plugin or skill is working.

## Organization

Each skill gets its own directory at the repository root:

```text
writing-opencode-plugins/SKILL.md
injecting-agent-behavior/SKILL.md
building-agent-orchestration/SKILL.md
porting-agent-plugins-across-harnesses/SKILL.md
testing-agent-plugins/SKILL.md
```

Keep each `SKILL.md` focused and under roughly 500 lines. If a skill needs larger reference tables, move them to `references/` inside that skill directory.

## Evaluation Plan

Create eval prompts before writing each skill body. Each eval should compare behavior without the skill to behavior with the skill.

Initial evals:

- OpenCode plugin tool: “Build a local OpenCode plugin that adds a tool wrapping a shell script and injects one env var.”
- Command/skill injection: “Package three slash commands and two skills in an OpenCode plugin so agents can discover them.”
- Orchestration: “Design a plugin-level background-agent system for three independent research agents and safe result collection.”
- Cross-harness port: “Port an OpenCode plugin feature to Claude Code and Codex while preserving shared core logic.”
- Testing: “Create a verification plan for an agent plugin that injects context and launches background tasks.”
- Test implementation: “Given a plugin that registers a command, custom tool, and message transform, write the unit, discovery, integration, and safety tests.”

Assertions should check for concrete behaviors such as:

- Uses official paths and config keys where available.
- Separates stable API from observed third-party patterns.
- Avoids unsafe raw session prompt injection.
- Defines command/agent/skill names and permissions correctly.
- Uses deterministic shell invocation and structured tool output.
- Includes discovery, behavior, safety, and orchestration tests.
- Produces a cross-harness capability matrix when porting.
- Separates fast unit tests from optional harness integration tests.
- Uses temp config homes and fixtures instead of mutating real user config.
- Adds static architecture audits for forbidden patterns such as raw internal prompt injection when appropriate.

## Non-Goals

- Do not vendor large parts of oh-my-openagent or superpowers into these skills.
- Do not create a full plugin framework.
- Do not promise that experimental hooks are stable.
- Do not document private provider credentials or subscription-specific setup.
- Do not implement Team Mode itself; only document when a plugin should or should not attempt that level of orchestration.

## Risks and Mitigations

- Risk: skills become too broad and under-trigger.
  Mitigation: split by task intent and write description fields with concrete triggers.
- Risk: agents treat oh-my-openagent internals as official OpenCode API.
  Mitigation: label source authority in each skill and separate stable docs from observed patterns.
- Risk: orchestration guidance causes unbounded agent spawning.
  Mitigation: require explicit limits, lifecycle state, cancellation, and one deliverable per task.
- Risk: message injection creates duplicate prompts or hidden context bugs.
  Mitigation: prefer config/files first; require idempotency guards and shared dispatch gates for internal prompt APIs.
- Risk: cross-harness guidance overclaims parity.
  Mitigation: require a capability matrix and adapter-specific acceptance tests.

## Approval Gate

After this spec is reviewed, create an implementation plan that writes and evaluates the skills one at a time. Do not batch-write all skills without per-skill evals.
