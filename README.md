# Skills

Personal collection of agent skills, grouped into installable categories.

```bash
npx skills add https://github.com/HuakunShen/skills
```

The installer shows the categories below and lets you select a whole group (space on the
group row) or individual skills. The repo also works as a Claude Code plugin marketplace:

```bash
/plugin marketplace add HuakunShen/skills
```

## Categories

### Agent Engineering — `skills/agent-engineering`

Build, extend, port, and test coding-agent plugins.

- `injecting-agent-behavior`: add commands, skills, agents, rules, instructions, MCPs, and context injection.
- `building-agent-orchestration`: design background agents, delegation, and team coordination.
- `writing-opencode-plugins`: write and review OpenCode plugins and custom tools.
- `porting-agent-plugins-across-harnesses`: split portable core and adapters for OpenCode, Claude Code, Codex, and similar tools.
- `testing-agent-plugins`: test plugins, skills, commands, hooks, and orchestration systems.

### App Development — `skills/app-development`

Building applications, across mobile, terminal, web, and peer-to-peer.

- `harmonyos-app-patterns`: HarmonyOS NEXT / ArkTS + ArkUI patterns from a shipping production app.
- `ratatui-dev`: good-looking Rust terminal UIs with ratatui and crossterm.
- `shadcn-svelte-monorepo`: shadcn-svelte in a pnpm/SvelteKit monorepo with a shared UI package.
- `iroh-development`: peer-to-peer apps with iroh (QUIC, NAT traversal, blobs, gossip, docs).

### Cloudflare — `skills/cloudflare`

The Cloudflare edge stack.

- `cloudflare-monorepo`: multi-Worker monorepo patterns (pnpm + turbo + service-binding RPC).
- `cloudflare-ai-search-manual-sync`: manage an AI Search instance via the items API.
- `cloudflare-fumadocs-rag-agent`: add a RAG chat agent to a Fumadocs site.

### Documentation — `skills/documentation`

Capture and publish what a repo knows.

- `journal`: document recent changes and decisions in a dated journal.
- `sync-wiki`: update `.repowiki` docs from recent changes.
- `building-codebase-curriculum`: turn a codebase that already works into runnable, step-by-step lessons.
- `deepwiki-badge`: generate and insert DeepWiki badges.

### Tooling — `skills/tooling`

Standalone developer utilities.

- `strip-ai-coauthors`: remove AI/agent co-author trailers from git commit history safely.
- `chatgpt-external-chrome`: drive a logged-in ChatGPT session in external Chrome and return the answer.
- `ai-web-computer-use`: use Computer Use alone to operate logged-in ChatGPT, Gemini, and NotebookLM sessions, including generation and visible downloads.
- `kunkun-browser-ai`: choose between ChatGPT Chat, Kunkun's durable Browser AI MCP, and Computer Use fallback; operate Kunkun's cross-provider browser workflows and artifact boundary.
- `mac-storage-audit-and-dev-migration`: audit macOS disk usage and safely migrate Android/HarmonyOS developer data while protecting iCloud placeholders.
- `slidev-narrated-video`: turn a Slidev deck into an audio-synchronized MP4.

## Layout

Categories come from `.claude-plugin/marketplace.json` — each entry there is one group in
the installer. To add a skill, drop it in `skills/<category>/<skill-name>/SKILL.md` and add
its path to the matching plugin's `skills` array.
