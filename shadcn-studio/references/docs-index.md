# Documentation index and verified integration facts

Checked 2026-11-02. Recheck vendor pages before setup because IDE support and CLI syntax can change.

## Shadcn Studio index

`https://shadcnstudio.com/llms.txt` is a table of contents with links to product and block documentation. It links to the MCP server, IDE extension, blocks, pages, illustrations, templates, themes and CLI docs. Read the topic page for operational details.

## Agent support distinction

The official MCP page currently lists VS Code, Cursor, Windsurf, Cline and Claude Code, and describes React, Next.js and TypeScript project compatibility. It explicitly states Codex MCP support is not available due to a response-size parsing limitation. Use shadcn CLI registry in Codex. The official IDE-extension page separately describes IDE agents and CLI-based agents, but that does not imply the Studio MCP server is compatible with every agent.

## Context7 lookups

- Resolved Shadcn Studio: `/llmstxt/shadcnstudio_llms_txt` (high reputation; official llms.txt-backed docs).
- Resolved shadcn/ui: `/shadcn-ui/ui`, version `shadcn@4.21.0`.
- The Context7 registry docs confirm environment placeholders in registry params and namespaced `shadcn add` commands.
- The Context7 Studio docs confirm Pro registry configuration, Claude MCP setup, and the current Codex MCP limitation.

## Primary sources

- [Shadcn Studio llms.txt](https://shadcnstudio.com/llms.txt)
- [Studio CLI docs](https://shadcnstudio.com/docs/getting-started/how-to-use-shadcn-cli)
- [Studio MCP docs](https://shadcnstudio.com/docs/getting-started/shadcn-studio-mcp-server)
- [Studio IDE extension docs](https://shadcnstudio.com/docs/getting-started/shadcn-studio-ide-extension)
- [Studio Pro docs](https://shadcnstudio.com/docs/getting-started/introduction-pro)
- [shadcn/ui components.json](https://ui.shadcn.com/docs/components-json)
- [shadcn/ui registry authentication](https://ui.shadcn.com/docs/registry/authentication)
- [shadcn-svelte docs](https://www.shadcn-svelte.com/)
