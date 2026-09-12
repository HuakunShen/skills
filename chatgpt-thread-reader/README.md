# ChatGPT Thread Reader POC

This is a first feasibility probe for reading ChatGPT conversation URLs from reusable AI skills.

It has two deliberately separate paths:

- The skill instructions use `mcp__codex_app__read_thread` when the host exposes that internal Codex App capability.
- The TypeScript script speaks to local `codex app-server` and proves that its `thread/read` history is a local Codex store, not a ChatGPT Web URL fetcher.

Run the tests:

```bash
npm test
```

Parse a URL:

```bash
npm run parse -- --url 'https://chatgpt.com/g/g-p-example/c/00000000-0000-4000-8000-000000000000'
```

Probe local app-server history:

```bash
node --experimental-strip-types scripts/read-chatgpt-thread.ts \
  --mode app-server \
  --url 'https://chatgpt.com/g/g-p-example/c/00000000-0000-4000-8000-000000000000'
```

The second command should not be interpreted as a Web-chat reader. A `thread not found` result for a Web conversation UUID is the expected boundary evidence.
