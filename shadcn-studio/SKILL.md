---
name: shadcn-studio
description: Use when configuring or using Shadcn Studio Pro/free registries, CLI, MCP, IDE extension, themes, blocks, or adapting Studio React components for Svelte or another framework/language.
---

# Shadcn Studio

Use Shadcn Studio as a source of React/shadcn UI assets and design references. Start from the target repository's actual framework, shadcn setup, aliases, styling, and agent instructions. Do not assume every Studio feature supports every framework or agent.

## Choose the integration

| Need | Preferred path | Notes |
|---|---|---|
| Install an exact Studio component/block/page/theme in React | shadcn CLI v4 + `components.json` registry | Pro auth is URL params from environment variables. |
| Generate/inspire/refine UI via Studio MCP | Studio MCP in a supported IDE | Current official docs list VS Code, Cursor, Windsurf, Cline, Claude Code; React/Next/TypeScript project scope. |
| Codex workflow | CLI registry + this skill/project instructions | Official Studio MCP page currently says Codex is unsupported because its tool response exceeds Codex's 10 KB parsing limit. Do not claim Codex MCP works. |
| Visual browse/edit | Shadcn Studio IDE extension | Configure Pro credentials in its settings UI, never in prompts. |
| Copilot | Download official Copilot instruction file into `.github/instructions/` | Guidance only, not an agent install or registry setup. |
| Svelte/Vue/other target | Port selected source into native target idioms | Catalog is React-oriented; don't install TSX into a non-React source tree. |

## Setup a project

1. Identify the app/package being modified. In a monorepo, inspect all `components.json` files and choose the one whose aliases and CSS path point to the target package.
2. Check for shadcn CLI v4 and a valid `components.json`. Follow [Studio CLI docs](https://shadcnstudio.com/docs/getting-started/how-to-use-shadcn-cli); Studio says CLI v2 is deprecated.
3. Confirm `EMAIL` and `LICENSE_KEY` placeholders match private environment variable names available to the CLI. Keep actual values in ignored local environment files or a secret manager. Never print, paste, commit, or place credentials in an agent instruction, URL displayed in logs, command history, or report.
4. Premium registry namespaces are `@ss-components`, `@ss-blocks`, `@ss-pages`, `@ss-illustrations`, `@ss-themes`. Install only requested items, e.g. `npx shadcn@latest add @ss-blocks/<item>` using the exact item identifier from Studio.
5. Validate access with one selected item only when requested. Do not install a guessed item to probe credentials. Separate auth/network errors from invalid item IDs.
6. Inspect installed source and dependencies. Adapt aliases, CSS tokens, icons, and primitive versions to the target app. Do not overwrite existing local components without inspecting diffs.

## Agent setup

Run `scripts/setup.sh [project-root]` from this skill to install a project-local copy of this skill and idempotent pointers for Codex (`AGENTS.md`), Claude Code (`CLAUDE.md`), Cursor (`.cursor/rules/`), and OpenCode (`AGENTS.md`). It can fetch official Copilot instructions. It does not install MCP servers or inject credentials.

For Copilot, the documented destination is `.github/instructions/shadcn-studio.instructions.md`; `curl --create-dirs` creates parent directories. The file is explicitly published as Copilot instructions. Other agents need their own discoverable instructions; merely creating `.github/` does not configure them.

### MCP

Read the current official [Studio MCP setup](https://shadcnstudio.com/docs/getting-started/shadcn-studio-mcp-server) first. It documents `/cui`, `/iui` (Pro), `/rui`, and `/ftc` (requires Figma MCP), and currently names Claude Code, VS Code, Cursor, Windsurf, and Cline. Claude Code commands are project-specific. Use the account's current MCP onboarding values; do not assume MCP API key and registry license key are interchangeable.

Do not run commands with real credentials embedded in shell text. Prefer secure interactive setup or a secret manager. In Codex, use registry CLI instead of Studio MCP while the official compatibility notice remains.

## Porting to Svelte or another language/framework

Treat the Studio item as a visual/behavioral reference and a source of permitted assets, not as a drop-in dependency. Work one requested item at a time:

1. Fetch/install the exact React source into a temporary/private React staging project with a matching `components.json`; keep it out of the target Svelte build.
2. Inspect the item and dependencies: structure, state/events, accessibility, responsive breakpoints, CSS variables, icons, images, animation libraries, and licenses.
3. Map concepts to target-native building blocks. For Svelte use the project's Svelte version, shadcn-svelte conventions and Bits UI where appropriate; use Svelte 5 runes only if the target uses Svelte 5.
4. Rebuild markup, state, effects, handlers, composition, and styling in native source. React hooks/JSX/Radix APIs do not translate mechanically. Preserve semantics, keyboard/focus behavior, loading/empty/error states, and responsive behavior.
5. Reuse only assets/styles the license permits. Don't mirror a paid catalog into a shared/public store. Fetch the minimum requested files and dependencies.
6. Compare target behavior and appearance against the reference. Report what was ported, approximated, and any dependency or licensing uncertainty.

## Documentation and freshness

Use [Shadcn Studio llms.txt](https://shadcnstudio.com/llms.txt) as the vendor documentation index; follow links to topic pages for details. High-value pages:

- [CLI / registry setup](https://shadcnstudio.com/docs/getting-started/how-to-use-shadcn-cli)
- [IDE extension](https://shadcnstudio.com/docs/getting-started/shadcn-studio-ide-extension)
- [Studio MCP](https://shadcnstudio.com/docs/getting-started/shadcn-studio-mcp-server)
- [Pro account and license](https://shadcnstudio.com/docs/getting-started/introduction-pro)
- [shadcn/ui CLI v4 registries](https://ui.shadcn.com/docs/components-json) and [registry authentication](https://ui.shadcn.com/docs/registry/authentication)
- [shadcn-svelte docs](https://www.shadcn-svelte.com/)

When current library/API/CLI behavior matters, resolve `Shadcn Studio` (`/llmstxt/shadcnstudio_llms_txt`) and the target library in Context7, then fetch docs for the exact concept. Prefer vendor docs for Studio-specific behavior and official target-framework docs for porting. Cite URLs in durable notes.

## Troubleshooting

- Missing parent after curl: use `curl --create-dirs -fL -o .github/instructions/shadcn-studio.instructions.md <official-file-url>`; verify the file exists and is nonempty.
- 401/403: verify account, email, license entitlement, env availability from the command working directory, and the selected package config. Never expose the credential.
- Unknown item: verify namespace and slug in Studio UI/docs; don't infer a paid slug from a marketing heading.
- Wrong install target: run from the intended package root and inspect that package's `components.json` paths/aliases.
- Non-React incompatibility: stage React separately and port semantics; registry installation is not a transpiler.
- Agent ignores guidance: check its native discovery path and put a concise pointer in project instructions. Downloading a file alone doesn't make another agent load it.
