---
name: cloudflare-ai-search-manual-sync
description: Create, manage, sync, and maintain a Cloudflare AI Search instance with manual document upload via the items API. Unlike the R2/web-crawl auto-index approach, this covers the admin API pattern — list, diff, upload, delete, and sync. Use when the user wants to build a custom content pipeline for AI Search without relying on R2 or web crawling.
---

# Cloudflare AI Search — Manual Sync & Maintenance

This skill covers the **manual document upload** pattern for Cloudflare AI Search. Instead of pointing AI Search at an R2 bucket or website (auto-index), you push documents via the admin API. This gives you:

- **Fine-grained control** over what gets indexed
- **Immediate updates** (no 6-hour wait for auto-index)
- **Custom metadata** (e.g., `sha256` for change detection)
- **Diff-based sync** (only upload changed files, delete removed ones)

## Two APIs — Which Binding?

Cloudflare AI Search has two API generations. This skill uses the **new** one:

| Aspect | Old API | New API (this skill) |
|--------|---------|---------------------|
| Binding | `ai` + `autorag("name")` | `ai_search` (single-instance) |
| Chat | `aiSearch({ query })` | `chatCompletions({ messages })` |
| Document upload | Auto via R2/Web crawl | Manual via `items.upload()` |
| wrangler config | `{ "ai": { "binding": "AI" } }` | `{ "ai_search": [{ "binding": "AI_SEARCH", "instance_name": "...", "remote": true }] }` |

## Architecture

```
[Documents on disk (MDX, MD, HTML, TXT, JSON, etc.)]
        |
        |  sync-docs.ts (diff → upload/delete)
        v
[Cloudflare AI Search instance]
  - items.upload(key, content, { metadata })
  - items.list()
  - items.delete(id)
        |
        |  chatCompletions({ messages, stream: true })
        v
[Your App / Chat UI / API]
```

## Step 1 — Provision the Instance

```bash
# Create an AI Search instance
pnpm wrangler ai-search create my-knowledge-base \
  --hybrid-search \
  --cache \
  --json
```

All available flags:

| Flag | Purpose |
|------|---------|
| `--embedding-model` | e.g. `@cf/qwen/qwen3-embedding-0.6b` |
| `--generation-model` | e.g. `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
| `--chunk-size` | Document chunk size (min 64) |
| `--chunk-overlap` | Chunk overlap |
| `--hybrid-search` | Enable vector + keyword |
| `--reranking` | Enable reranking + specify model |
| `--cache` | Enable response caching |
| `--score-threshold` | Min relevance (0-1) |

Other management commands:

```bash
pnpm wrangler ai-search list                               # List all instances
pnpm wrangler ai-search get my-knowledge-base              # Get details
pnpm wrangler ai-search update my-knowledge-base \         # Update config
  --generation-model @cf/meta/llama-4-scout-17b-16e-instruct
pnpm wrangler ai-search stats my-knowledge-base            # Usage stats
pnpm wrangler ai-search delete my-knowledge-base --force   # Delete
pnpm wrangler ai-search search my-knowledge-base \         # Test search
  --query "what is this project about?"
```

## Step 2 — Configure the Binding

In your Worker's `wrangler.jsonc`:

```jsonc
{
  "compatibility_flags": ["nodejs_compat"],
  "ai_search": [
    {
      "binding": "AI_SEARCH",
      "instance_name": "my-knowledge-base",
      "remote": true
    }
  ]
}
```

Run `pnpm wrangler types` to generate types.

## Step 3 — Admin API Endpoints

The AI Search items API supports a CRUD-like pattern. You need these endpoints in your Worker:

### Items

| Operation | What it does |
|-----------|-------------|
| `instance.items.list({ page, per_page })` | List all indexed items (paginated) |
| `instance.items.upload(key, content, { metadata })` | Upsert a document by key |
| `instance.items.delete(id)` | Delete by item ID |
| `instance.update({ custom_metadata })` | Add custom metadata schema (idempotent) |

### Custom Metadata for Change Detection

Add a `sha256` metadata field to track content changes:

```ts
await env.AI_SEARCH.update({
  custom_metadata: [{ field_name: 'sha256', data_type: 'text' }],
});
```

### Type Signature

```ts
interface AiSearchInstance {
  items: {
    list(params: { page?: number; per_page?: number }): Promise<{
      result: Array<{ id: string; key: string; status: string; file_size?: number; metadata?: Record<string, string> }>;
      result_info?: { total_count: number };
    }>;
    upload(key: string, content: string, options?: { metadata?: Record<string, string> }): Promise<{ id: string; key: string }>;
    delete(id: string): Promise<void>;
  };
  update(params: { custom_metadata: Array<{ field_name: string; data_type: string }> }): Promise<{ custom_metadata: unknown }>;
  chatCompletions(params: {
    messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>;
    stream?: boolean;
  }): Promise<ReadableStream>;
}
```

## Step 4 — Chat Completions (RAG)

The `chatCompletions()` method does managed RAG automatically:

```ts
const stream = await env.AI_SEARCH.chatCompletions({
  messages: [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'What is this project about?' },
  ],
  stream: true,
});

// SSE stream (OpenAI-compatible format)
return new Response(stream as ReadableStream, {
  headers: {
    'content-type': 'text/event-stream',
    'cache-control': 'no-cache',
    connection: 'keep-alive',
  },
});
```

Key details:
- You don't need to manually retrieve context — AI Search does hybrid search internally and injects results into the LLM prompt
- The SSE format matches OpenAI's standard: `data: {"choices":[{"delta":{"content":"..."}}]}`
- Non-streaming: omit `stream: true` to get a response object instead

## Step 5 — The Sync Script

A sync script is a standalone script (Bun/Node.js) that:

1. Walk a local directory for documents
2. Compute SHA-256 hashes of each file
3. List remote items via the admin API
4. Diff: new files → upload, changed files → update, deleted files → remove
5. Execute the plan

Essential structure:

```ts
// 1. Walk local files
type LocalFile = {
  relPath: string;   // e.g. "docs/getting-started.mdx"
  sha256: string;    // content hash
  content: string;
};

// 2. List remote items
type RemoteItem = {
  id: string;
  key: string;
  status: string;
  metadata?: { sha256?: string };
};

// 3. Diff
// toUpload: local - remote
// toUpdate: local sha256 !== remote sha256
// toDelete: remote - local

// 4. Execute
for (const f of toUpload) upload(f);
for (const f of toUpdate) upload(f);  // same API, upsert by key
for (const r of toDelete) deleteById(r.id);
```

Full reference implementation: [references/sync-script.ts](references/sync-script.ts)

Add to `package.json`:

```jsonc
{
  "scripts": {
    "sync-docs": "bun --env-file=.env.local scripts/sync-docs.ts"
  }
}
```

Env vars:

```
SYNC_URL=http://localhost:3000   # Worker URL
SYNC_TOKEN=<bearer-token>        # Must match wrangler secret
```

Run:

```bash
# Dry-run
bun scripts/sync-docs.ts

# Apply changes
bun scripts/sync-docs.ts --apply

# Full re-index
bun scripts/sync-docs.ts --apply --wipe-first
```

## Step 6 — Maintenance

### Monitoring

```bash
# Check instance stats
pnpm wrangler ai-search stats my-knowledge-base

# List instances
pnpm wrangler ai-search list --json

# Test search from CLI
pnpm wrangler ai-search search my-knowledge-base --query "test query" --json
```

### Updating Configuration

```bash
# Change models, chunk size, reranking, etc.
pnpm wrangler ai-search update my-knowledge-base \
  --chunk-size 128 \
  --reranking true \
  --reranking-model @cf/baai/bge-reranker-base
```

### Full Re-index

```bash
# 1. Wipe all items
bun scripts/sync-docs.ts --apply --wipe-first
# 2. Then re-upload fresh
bun scripts/sync-docs.ts --apply
```

### Re-creating an Instance

```bash
# 1. Note current config
pnpm wrangler ai-search get my-knowledge-base --json > config-backup.json

# 2. Delete
pnpm wrangler ai-search delete my-knowledge-base --force

# 3. Re-create with same config
pnpm wrangler ai-search create my-knowledge-base --hybrid-search --cache --json

# 4. Re-sync documents
bun scripts/sync-docs.ts --apply
```

## Comparison: Manual Upload vs Auto-Index

| Factor | Manual Upload (this skill) | R2 / Web Crawl (auto) |
|--------|---------------------------|----------------------|
| Update speed | Immediate (via API) | Every 6 hours |
| Content control | Full (what + when) | Limited to R2 files / sitemap |
| Custom metadata | Yes (any fields) | Built-in only (filename, folder, timestamp) |
| Diff-based sync | Yes (sha256 tracking) | No (re-indexes everything) |
| Best for | Docs, blogs, custom pipelines | Stable content, hands-off |
| Sync script needed | Yes | No |

## Common Mistakes

| Mistake | Cause | Fix |
|---------|-------|-----|
| Forgetting `nodejs_compat` | AI Search binding not available | Add `"compatibility_flags": ["nodejs_compat"]` |
| Auth mismatch | SYNC_TOKEN differs | `wrangler secret put SYNC_TOKEN` + same value in `.env.local` |
| Wrong SYNC_URL | Pointing to wrong env | `http://localhost:3000` for dev, production URL for deployed |
| SSE parsing breaks | Expecting non-standard format | AI Search uses OpenAI-compatible SSE |
| `items.upload()` silently overwrites | It's an upsert by key | Keys must be unique within an instance |
| Instance name mismatch | wrangler.jsonc name != actual instance | Verify with `wrangler ai-search list` |
| `update()` returns wrong type | The API response shape | It returns `{ custom_metadata }` not the full instance |

## References

- [Full sync script](references/sync-script.ts) — Ready-to-use Bun script
- [Cloudflare AI Search Docs](https://developers.cloudflare.com/ai-search/)
- [Wrangler AI Search Commands](https://developers.cloudflare.com/ai-search/wrangler-commands/)
