---
name: cloudflare-monorepo
description: >
  Multi-Cloudflare-Worker monorepo pattern using pnpm workspace + turbo.
  Covers apps/api (Hono + WorkerEntrypoint RPC), apps/web (SvelteKit or TanStack Start),
  packages/db (shared Drizzle/D1 schema), and typed service-binding RPC between workers.
  Use when scaffolding, modifying, or reviewing a CF monorepo with 2+ workers.
---

# Cloudflare Multi-Worker Monorepo Skill

> Pattern distilled from **kunkun-services** (SvelteKit + Hono), **polyinsight** (TanStack Start + Hono), and **MyWeb** (TanStack Start + Fumadocs).

## 1. Architecture Overview

```
monorepo/
├── apps/
│   ├── api/              # CF Worker — API gateway + typed RPC entrypoint
│   └── web/              # CF Worker — SSR frontend
├── packages/
│   └── db/               # Shared D1 schema (Drizzle ORM) + client factory
├── package.json          # Root workspace scripts (turbo)
├── pnpm-workspace.yaml   # apps/*, packages/*
└── turbo.json            # dev, build, lint pipelines
```

| Concern | Owner | Runtime |
|---------|-------|---------|
| HTTP API (public + internal) | `apps/api` | Hono on CF Worker |
| Typed RPC for in-CF callers | `apps/api` | `WorkerEntrypoint` class |
| SSR frontend | `apps/web` | SvelteKit or TanStack Start on CF Worker |
| Database schema & client | `packages/db` | Drizzle ORM + D1 (SQLite) |
| Migrations | `packages/db/drizzle/migrations/` | Drizzle Kit + `wrangler d1 migrations apply` |

## 2. Directory & Naming Conventions

- **Apps**: `apps/<name>` — deployable Workers. Prefer short names: `api`, `web`, `dashboard`.
- **Packages**: `packages/<name>` — shared libraries. Key ones:
  - `packages/db` — D1 schema, Drizzle client factory, migrations.
  - `packages/ui` — shared UI components (optional).
- **Package naming**: use a workspace prefix, e.g. `@scope/api`, `@scope/db`.
- **One-way dependency rule**: `apps/web` may import from `apps/api` (types only) and `packages/db`. `apps/api` must **never** import from `apps/web`.

## 3. API Worker (`apps/api/`)

### 3.1 File Split: `app.ts` vs `index.ts`

Always split the Hono app from the Worker entrypoint:

- **`src/app.ts`** — pure Hono app. No `cloudflare:workers` imports. Used by:
  - HTTP routes (`export default app`)
  - Node-side tooling (OpenAPI export, SDK codegen, tests)
- **`src/index.ts`** — Worker entrypoint. Exports:
  - `class ApiEntrypoint extends WorkerEntrypoint` (RPC surface)
  - `export default { fetch: app.fetch, scheduled?, queue? }` (HTTP + cron + queue)

### 3.2 RPC Entrypoint Pattern

```ts
// src/index.ts
import { WorkerEntrypoint } from "cloudflare:workers";
import app from "./app.ts";
import type { ApiBindings } from "./bindings.ts";

export class ApiEntrypoint extends WorkerEntrypoint<ApiBindings> {
  async ping(): Promise<{ ok: true; env: string }> {
    return { ok: true, env: this.env.ENVIRONMENT };
  }

  async doSomething(input: SomeInput, viewerUserId: string | null) {
    return doSomethingCore(this.env, input, viewerUserId);
  }
}

export default app;
```

- **Core logic lives outside the class** — in `core.ts` or `services/<domain>/core.ts` — so HTTP routes and RPC methods can share it.
- **Forward `userId` from caller** — the web worker is already authenticated (Clerk/WorkOS/AuthKit); it passes the user id over RPC. The API worker trusts the caller because service bindings are structurally unreachable from the public internet.

### 3.3 Bindings Interface

```ts
// src/bindings.ts
export interface ApiBindings {
  DB: D1Database;
  CACHE: KVNamespace;
  AI: Ai;
  ENVIRONMENT: "development" | "production";
  // secrets appear as optional strings
  INTERNAL_API_SECRET?: string;
}
```

- Use a **named interface** (`ApiBindings`), not the ambient `CloudflareBindings`, so cross-workspace consumers can import it without collision.

### 3.4 Exports in `package.json`

```json
{
  "name": "@scope/api",
  "exports": {
    ".": { "import": "./src/index.ts", "types": "./src/index.ts" },
    "./app": { "import": "./src/app.ts", "types": "./src/app.ts" },
    "./bindings": { "import": "./src/bindings.ts", "types": "./src/bindings.ts" }
  }
}
```

The web worker imports the `ApiEntrypoint` class **as a type only** to cast the service binding stub.

## 4. Web Worker (`apps/web/`)

### 4.1 Framework Choices

| Framework | Adapter / Plugin | Notes |
|-----------|-----------------|-------|
| **SvelteKit** | `@sveltejs/adapter-cloudflare` | Set `platformProxy: { configPath: "wrangler.jsonc" }` in `svelte.config.js` |
| **TanStack Start** | `@cloudflare/vite-plugin` | Add `cloudflare({ viteEnvironment: { name: "ssr" } })` in `vite.config.ts` |

### 4.2 Calling API via Service Binding

In SvelteKit server hooks:

```ts
// src/hooks.server.ts
export const handle = async ({ event, resolve }) => {
  if (event.platform?.env.API) {
    const result = await event.platform.env.API.syncUser({ ... });
    event.locals.userId = result.userId;
  }
  return resolve(event);
};
```

In TanStack Start server functions:

```ts
// src/server-fns/example.ts
import { createServerFn } from "@tanstack/react-start";
import { getApi } from "#/lib/cf-api-client";

export const doThing = createServerFn({ method: "POST" }).handler(async () => {
  const api = getApi();
  return api.ping();
});
```

### 4.3 Typing the Binding

`wrangler types` generates `worker-configuration.d.ts` with:

```ts
interface __BaseEnv_Env {
  API: Service /* entrypoint ApiEntrypoint from my-api-dev */;
}
```

Override in your framework's type declarations to get full typing:

**SvelteKit** (`src/app.d.ts`):

```ts
declare global {
  namespace App {
    interface Platform {
      env: CloudflareBindings & {
        API: Service<import("@scope/api").ApiEntrypoint>;
      };
      ctx: ExecutionContext;
    }
  }
}
```

**TanStack Start** (custom env helper):

```ts
// src/lib/cf-api-client.ts
import type { ApiEntrypoint } from "@scope/api";
import { getCFEnv } from "#/lib/cf-env";

export function getApi(): Service<ApiEntrypoint> {
  const env = getCFEnv();
  if (!env.API) throw new Error("API binding missing");
  return env.API as unknown as Service<ApiEntrypoint>;
}
```

> `wrangler types` does not follow cross-worker imports for the generic, so the cast is required.

## 5. Wrangler Configuration

### 5.1 API Worker (`apps/api/wrangler.jsonc`)

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "my-api-dev",
  "main": "src/index.ts",
  "compatibility_date": "2026-05-28",
  "compatibility_flags": ["nodejs_compat"],
  "workers_dev": true,
  "observability": { "enabled": true },
  "upload_source_maps": true,
  "vars": {
    "ENVIRONMENT": "development",
    "PUBLIC_WEB_ORIGIN": "http://localhost:5173"
  },
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "my-db-dev",
      "database_id": "...",
      "migrations_dir": "../../packages/db/drizzle/migrations",
      "remote": true
    }
  ],
  "kv_namespaces": [
    { "binding": "CACHE", "id": "..." }
  ]
}
```

### 5.2 Web Worker (`apps/web/wrangler.jsonc`)

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "my-web-dev",
  // SvelteKit build output
  "main": ".svelte-kit/cloudflare/_worker.js",
  // TanStack Start
  // "main": "./src/server.ts",
  "compatibility_date": "2026-05-28",
  "compatibility_flags": ["nodejs_als"],
  "workers_dev": true,
  "preview_urls": true,
  "assets": {
    "binding": "ASSETS",
    "directory": ".svelte-kit/cloudflare"
  },
  "vars": {
    "ENVIRONMENT": "development",
    "PUBLIC_API_ORIGIN": "http://localhost:8787"
  },
  "services": [
    {
      "binding": "API",
      "service": "my-api-dev",
      "entrypoint": "ApiEntrypoint"
    }
  ],
  "observability": { "enabled": true }
}
```

### 5.3 Key Config Rules

| Rule | Why |
|------|-----|
| `compatibility_flags: ["nodejs_compat"]` | Required for Hono, Drizzle, and most npm packages on Workers |
| `migrations_dir` points to `packages/db/drizzle/migrations` | Single source of truth for D1 schema |
| `"remote": true` on bindings | Use real CF resources in dev; Miniflare simulation is limited for Vectorize/AI Search |
| `upload_source_maps: true` | Stack traces in observability point to original TS |
| Web `assets.directory` matches adapter output | SvelteKit: `.svelte-kit/cloudflare`; TanStack Start: usually `dist/` or build dir |

## 6. Shared Database (`packages/db/`)

### 6.1 Schema Definition

```ts
// src/schema.ts
import { sqliteTable, text, integer, index } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  createdAt: integer("created_at", { mode: "timestamp" }),
});
```

### 6.2 Client Factory

```ts
// src/client.ts
import { drizzle } from "drizzle-orm/d1";
import * as schema from "./schema.js";

export function createDb(db: D1Database) {
  return drizzle(db, { schema });
}
```

### 6.3 Drizzle Config

```ts
// drizzle.config.ts
import { defineConfig } from "drizzle-kit";

const isLocal = process.env.LOCAL_DB === "true";

export default defineConfig(
  isLocal
    ? {
        out: "./drizzle/migrations",
        schema: "./src/schema.ts",
        dialect: "sqlite",
        dbCredentials: { url: "./drizzle/local.db" },
      }
    : {
        out: "./drizzle/migrations",
        schema: "./src/schema.ts",
        dialect: "sqlite",
        driver: "d1-http",
        dbCredentials: {
          accountId: process.env.CLOUDFLARE_ACCOUNT_ID!,
          databaseId: process.env.CLOUDFLARE_DATABASE_ID!,
          token: process.env.CLOUDFLARE_D1_TOKEN!,
        },
      },
);
```

### 6.4 Ownership Model

| Pattern | When to use |
|---------|-------------|
| **Single owner** (web writes schema, api reads) | Web is the control plane; api is the data plane. Migrations managed from web's package scripts. Api's `wrangler.jsonc` points to the same `migrations_dir`. |
| **Shared ownership** | Both workers write. Pick one app to run `drizzle-kit generate`; both apply migrations. |

## 7. TypeScript Configuration

### 7.1 API Worker

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "types": ["./worker-configuration.d.ts"],
    "paths": {
      "@scope/db/*": ["../../packages/db/src/*"],
      "@scope/db": ["../../packages/db/src/index.ts"]
    }
  },
  "include": ["src/**/*", "worker-configuration.d.ts", "../../packages/db/src/**/*"]
}
```

### 7.2 Web Worker (SvelteKit)

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*", "worker-configuration.d.ts"],
  "exclude": ["../api/src/**/*"]
}
```

> The `exclude` prevents TS from picking up api's source files and causing type collisions.

## 8. Root Workspace Scripts

```json
{
  "scripts": {
    "build": "turbo build",
    "dev": "turbo dev",
    "lint": "turbo lint",
    "format": "biome format --write",
    "check": "turbo check",
    "db:generate": "pnpm --filter @scope/db db:generate",
    "db:migrate:local": "pnpm --filter @scope/api wrangler d1 migrations apply my-db-dev --local",
    "db:migrate:remote": "pnpm --filter @scope/api wrangler d1 migrations apply my-db-dev --remote",
    "cf:typegen": "pnpm --filter @scope/api cf-typegen && pnpm --filter @scope/web cf-typegen",
    "dev:cf": "wrangler dev -c apps/api/wrangler.jsonc -c apps/web/wrangler.jsonc"
  }
}
```

| Script | Purpose |
|--------|---------|
| `dev` | Turbo runs all apps in parallel. Often too noisy — prefer `cd apps/<x> && pnpm dev`. |
| `dev:cf` | Runs both workers in one `wrangler dev` process with service bindings wired. |
| `cf:typegen` | Regenerates `worker-configuration.d.ts` for both apps after binding changes. |
| `db:generate` | Runs `drizzle-kit generate` from the shared schema package. |

## 9. Development Workflow

### 9.1 Starting from scratch

1. `pnpm install`
2. `cp apps/web/.env.example apps/web/.env.local` (fill auth keys if needed)
3. `pnpm db:generate` (if schema changed)
4. `pnpm db:migrate:local` or `pnpm db:migrate:remote`
5. `pnpm cf:typegen`
6. `pnpm dev:cf` (or run each app separately)

### 9.2 After changing bindings

1. Edit `wrangler.jsonc`
2. Run `pnpm cf:typegen` in the affected app
3. Commit the updated `worker-configuration.d.ts`

### 9.3 After changing D1 schema

1. Edit `packages/db/src/schema.ts`
2. `pnpm db:generate`
3. `pnpm db:migrate:local` (test) or `pnpm db:migrate:remote` (deploy)
4. All workers referencing the same `migrations_dir` stay in sync

## 10. Deployment

### 10.1 Per-App Deploy

```bash
cd apps/api && pnpm deploy   # wrangler deploy
cd apps/web && pnpm deploy   # build + wrangler deploy
```

### 10.2 Environment Strategy

Use separate workers for dev/staging/prod rather than wrangler `env` blocks when possible:

| Env | API Worker | Web Worker | D1 DB |
|-----|-----------|-----------|-------|
| dev | `my-api-dev` | `my-web-dev` | `my-db-dev` |
| prod | `my-api-prod` | `my-web-prod` | `my-db-prod` |

This avoids accidental cross-environment service binding calls.

## 11. Best Practices

| Practice | Rationale |
|----------|-----------|
| **Use service bindings, not HTTP** | Zero latency, zero auth overhead, structurally private |
| **Keep `app.ts` free of `cloudflare:workers`** | Node-side tooling (tests, OpenAPI export) can import routes |
| **Re-export RPC input/output types from `apps/api`** | Web worker imports them to stay type-safe |
| **Scope RPC methods by `userId`** | Even with structural trust, defensively scope DB queries per user |
| **Use `ctx.waitUntil()` for side effects** | Keep RPC method latency low; fire off outbox drains, index updates, etc. |
| **Never store request state in module-level vars** | Workers are single-threaded isolates, but requests interleave on the same isolate |
| **Commit auto-generated files** | `worker-configuration.d.ts`, TanStack `routeTree.gen.ts`, Drizzle migrations — all committed, never hand-edited |

## 12. Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `API binding missing` in local dev | `@cloudflare/vite-plugin` or `adapter-cloudflare` not configured with `wrangler.jsonc` | Check `svelte.config.js` `platformProxy.configPath` or `vite.config.ts` `cloudflare()` plugin |
| Type error on `env.API.ping()` | `Service<ApiEntrypoint>` generic not applied | Cast in app.d.ts or client helper: `env.API as unknown as Service<ApiEntrypoint>` |
| `drizzle-orm` type errors in web | Web tsconfig includes api source files | Add `"exclude": ["../api/src/**/*"]` to web tsconfig |
| Build hangs after "Tunnel closed" (TanStack Start) | `@cloudflare/vite-plugin` + prerender conflict | Disable prerender: `prerender: { enabled: false }` in `tanstackStart()` plugin options |
| Vectorize / AI Search not working locally | Binding not supported in Miniflare | Set `"remote": true` and test against deployed worker, or mock |
| D1 schema drift between workers | One worker applied old migrations | Ensure both `wrangler.jsonc` files point to the same `migrations_dir` |

## 13. Decision Trees

### "I need to add a new CF resource (Queue, R2, etc.)"

```
Add binding to apps/api/wrangler.jsonc
  → Add field to src/bindings.ts
  → Run pnpm cf:typegen in apps/api
  → If web also needs it, add to apps/web/wrangler.jsonc + run cf:typegen there
```

### "I need to share logic between HTTP routes and RPC methods"

```
Extract to src/services/<domain>/core.ts
  → Import in route handlers (src/routes/...) for HTTP
  → Import in ApiEntrypoint methods for RPC
  → Both surfaces share validation + business logic
```

### "I need a third worker (e.g. cron worker, queue consumer)"

```
Create apps/worker/
  → Copy wrangler.jsonc pattern from apps/api/
  → If it needs D1, point migrations_dir to packages/db/drizzle/migrations
  → If it needs to call api, add services binding to ApiEntrypoint
  → Add to pnpm-workspace.yaml (already covered by apps/*)
```

## 14. Reference Implementations

- **kunkun-services** (`/Users/hk/Dev/kunkun-services`): SvelteKit web + Hono API + shared D1 + service binding RPC + WorkOS auth
- **polyinsight** (`/Users/hk/Dev/kunkun-services/references/polyinsight`): TanStack Start dashboard + Hono cf-api + shared D1 (`@polyinsight/d1-schema`) + Clerk auth + Vectorize + Queues + Cron
- **MyWeb** (`/Users/hk/Dev/kunkun-services/references/MyWeb`): TanStack Start docs site + Fumadocs + `@cloudflare/vite-plugin` + AI Search + rate limits

When in doubt, consult these repos for concrete wiring examples.
