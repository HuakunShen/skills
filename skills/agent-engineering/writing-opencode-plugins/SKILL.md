---
name: writing-opencode-plugins
description: Use when writing, modifying, debugging, packaging, or reviewing OpenCode plugins, custom tools, plugin hooks, shell-backed tools, npm/local plugin setup, or @opencode-ai/plugin code
---

# Writing OpenCode Plugins

## Overview

OpenCode plugins are JavaScript or TypeScript modules that return OpenCode plugin capabilities such as tools and hooks. Prefer the smallest official surface that solves the problem: local plugin files, custom tools, commands, agents, skills, permissions, and documented hooks before experimental message transforms or session mutation.

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
        args: {
          name: tool.schema.string().describe("Name to include in the response"),
        },
        async execute(args) {
          return JSON.stringify({ directory, worktree, name: args.name })
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
- Use Bun.$ in standalone .opencode/tools files, or close over the plugin context $ for plugin-registered tools.
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
- Test repeated hook/session injection to prove hidden or synthetic content is not duplicated.
- Smoke-test plugin syntax/imports.
- Run optional `opencode run --print-logs --format json` integration tests only in isolated temp config directories.

## Common Mistakes

- Treating oh-my-openagent internals as official OpenCode API.
- Using experimental message transforms for something a command, skill, or agent file can do.
- Calling raw session prompt APIs from multiple hooks without a shared gate.
- Returning huge unstructured tool output.
- Overriding built-in tool names accidentally.
