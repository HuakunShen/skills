---
name: cloudflare-fumadocs-rag-agent
description: Add a RAG AI chat agent to a Fumadocs documentation site using Cloudflare AI Search. Covers provisioning, wrangler config, Hono API, content sync script, and the floating chat UI. Use when the user asks to add AI search, chat, or RAG to a Fumadocs project. This is the Cloudflare-specific version.
---

# Fumadocs RAG AI Agent

Add a RAG-powered AI chat agent to a Fumadocs documentation site using **[Cloudflare AI Search](https://developers.cloudflare.com/ai-search/)** — a managed RAG service that handles chunking, embedding, vector storage, hybrid search, and LLM generation.

## Architecture

```
[MDX content in content/docs/]
        |
        |  (sync-docs.ts script, run manually)
        v
[Cloudflare AI Search instance]
  - Auto-chunks & embeds documents
  - Hybrid search (vector + keyword)
        |
        |  (env.AI_SEARCH binding)
        v
[Hono API — POST /api/chat]
  - Receives { messages }
  - Calls instance.chatCompletions({ messages, stream: true })
  - Returns SSE stream (OpenAI-compatible format)
        |
        |  (HTTP SSE stream)
        v
[FloatingChat component in browser]
  - Sends messages, renders Markdown replies
```

## Prerequisites

- A **Cloudflare account** with Workers subscription
- An existing **Fumadocs** project (deployed on Cloudflare Workers or locally via `wrangler dev`)
- `wrangler` CLI installed and logged in
- `bun` (used for sync script — adapt to Node.js if needed)

## Step-by-step

### 1. Provision AI Search (纯命令行，不需要进网页)

`wrangler` 完全支持 AI Search 的全生命周期管理，所有操作 CLI 搞定：

```bash
# 创建实例（必填参数只有 name）
pnpm wrangler ai-search create my-agent
# 全部可选 flags:
#   --source             数据源（R2 bucket 名或网站 URL，空=手动上传文档）
#   --type               数据源类型（如 r2）
#   --embedding-model    embedding 模型（默认 @cf/baai/bge-base-en-v1.5）
#   --generation-model   LLM 模型（默认 @cf/meta/llama-3.3-70b-instruct-fp8-fast）
#   --chunk-size         文档分块大小（默认 64，最小 64）
#   --chunk-overlap      分块重叠
#   --max-num-results    每查询返回结果数
#   --reranking          是否启用重排序
#   --reranking-model    重排序模型
#   --hybrid-search      启用 vector + keyword 混合搜索
#   --cache              启用响应缓存
#   --score-threshold    最低相关性阈值（0-1）
#   --prefix             R2 key 前缀（限定索引范围）
#   --include-items      只索引匹配 glob 的 items
#   --exclude-items      排除匹配 glob 的 items
#   --custom-metadata    自定义元数据字段（可重复，如 --custom-metadata title:text --custom-metadata views:number）
#   --json               以 JSON 输出

# 推荐的最小配置（手动上传文档，用默认 embedding+LLM）
pnpm wrangler ai-search create my-agent \
  --hybrid-search \
  --cache \
  --json

# 其他管理命令
pnpm wrangler ai-search list                 # 列出所有实例
pnpm wrangler ai-search get my-agent         # 查看实例详情
pnpm wrangler ai-search update my-agent \
  --generation-model @cf/meta/llama-4-scout-17b-16e-instruct \
  --chunk-size 128                           # 更新配置
pnpm wrangler ai-search delete my-agent      # 删除实例
pnpm wrangler ai-search stats my-agent       # 使用量统计
pnpm wrangler ai-search search my-agent \
  --query "what is X"                        # 直接测试搜索

# Namespace 管理（默认 default 就够了）
pnpm wrangler ai-search namespace list
pnpm wrangler ai-search namespace create my-ns --description "..."
pnpm wrangler ai-search namespace get my-ns
pnpm wrangler ai-search namespace delete my-ns --force

# 索引任务管理（当 source 为 R2/Web 时用）
pnpm wrangler ai-search jobs list my-agent
pnpm wrangler ai-search jobs create my-agent --description "initial sync"
pnpm wrangler ai-search jobs get my-agent <job-id>
pnpm wrangler ai-search jobs cancel my-agent <job-id>
pnpm wrangler ai-search jobs logs my-agent <job-id>
```

如果你用**手动上传文档**（即通过 sync-docs.ts 脚本 PUT API），不需要 `--source` — AI Search 会自动分块和 embedding。如果希望 AI Search 直接从 R2 bucket 或爬网站自动同步，才需要 `--source` + `--type`。

注意创建的 **instance name**（即 `my-agent`）要与 wrangler.jsonc 中 `ai_search[].instance_name` 一致。

### 2. Configure wrangler.jsonc

Add the `ai_search` binding and (optionally) rate limiting to `wrangler.jsonc`:

```jsonc
{
  "name": "my-docs",
  "compatibility_flags": ["nodejs_compat"],
  "ai_search": [
    {
      "binding": "AI_SEARCH",
      "instance_name": "my-agent",
      "remote": true
    }
  ],
  "ratelimits": [
    {
      "name": "CHAT_RATE_LIMIT",
      "namespace_id": "1001",
      "simple": { "limit": 10, "period": 60 }
    }
  ]
}
```

Run `wrangler types` to generate the binding types in `worker-configuration.d.ts`.

### 3. Create the Hono API Server

Install dependencies:

```bash
pnpm add hono @hono/zod-validator zod
```

Create `src/server/api.ts` with two groups of endpoints:

**Admin endpoints** (protected by bearer token `SYNC_TOKEN`):
- `POST /api/admin/setup` — Ensure sha256 metadata schema exists
- `GET /api/admin/docs` — List all indexed items
- `DELETE /api/admin/items/:id` — Delete an item
- `PUT /api/admin/docs/:key{.+}` — Upsert a document by key

**Chat endpoint**:
- `POST /api/chat` — Accept `{ messages }`, call `env.AI_SEARCH.chatCompletions()`, pipe SSE stream to response

See [references/api-server.ts](references/api-server.ts) for the full implementation.

### 4. Create the Content Sync Script

The sync script walks `content/docs/`, computes SHA-256 hashes, diffs against remote items, and uploads/deletes as needed.

See [references/sync-docs.ts](references/sync-docs.ts) for the full script.

Add it to `package.json`:

```jsonc
// package.json
"scripts": {
  "sync-docs": "bun --env-file=.env.local scripts/sync-docs.ts"
}
```

Environment variables (`.env.local`):

```
SYNC_URL=http://localhost:3000    # or your deployed URL
SYNC_TOKEN=<your-secret-token>
```

Usage:

```bash
# Dry-run (preview changes)
pnpm sync-docs

# Apply changes
pnpm sync-docs --apply

# Wipe and re-upload everything
pnpm sync-docs --apply --wipe-first
```

### 5. Add the Env Helper

Create `src/lib/env.ts`:

```ts
import { env as cfEnv } from 'cloudflare:workers';

interface Secrets {
  SYNC_TOKEN?: string;
}

export const env = cfEnv as typeof cfEnv & Secrets;
```

### 6. Build the Frontend Chat

Create the chat hook `src/hooks/use-terminal-chat.ts` and the component `src/components/floating-chat.tsx`.

See:
- [references/use-terminal-chat.ts](references/use-terminal-chat.ts) — SSE streaming hook
- [references/floating-chat.tsx](references/floating-chat.tsx) — Terminal-styled floating chat widget

Mount `FloatingChat` in your root layout:

```tsx
// routes/__root.tsx or equivalent
import { FloatingChat } from '@/components/floating-chat';

export default function RootLayout({ children }) {
  return (
    <>
      {children}
      <FloatingChat />
    </>
  );
}
```

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| Forgetting `nodejs_compat` flag | AI Search binding needs Node.js compatibility | Add `"compatibility_flags": ["nodejs_compat"]` to wrangler.jsonc |
| `SYNC_TOKEN` mismatch | Sync script token differs from worker's `SYNC_TOKEN` secret | Set `SYNC_TOKEN` via `wrangler secret put SYNC_TOKEN` or in `.dev.vars` |
| `SYNC_URL` wrong | Pointing to wrong environment during sync | Use `http://localhost:3000` for local dev, production URL for deploy |
| SSE parsing broken | Assuming non-standard streaming format | AI Search returns OpenAI-compatible SSE — `data: {"choices":[{"delta":{"content":"..."}}]}` |
| Rate limiting too strict | Default 10 req/min may be too low for testing | Increase limit or disable during development |
| Chat not responding after deploy | AI Search binding not registered in Cloudflare dashboard | Verify the `ai_search` binding name matches your instance name |
| Documents not found by chat | Content not synced, or sync used wrong content directory | Run `pnpm sync-docs --apply` and verify `content/docs/` path |
