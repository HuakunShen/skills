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

### 4.1.1 Vite-Based Multi-Worker Local Dev

If the web app is served by Vite in development, make the local entrypoint
`vite dev`, not raw multi-config `wrangler dev`. This applies to TanStack Start,
SvelteKit, and other Vite SSR frontends. Vite owns framework virtual modules,
HMR, route manifests, and dev transforms; raw Wrangler only sees the Worker
bundle surface.

Use raw multi-config `wrangler dev -c apps/web/wrangler.jsonc -c apps/api/wrangler.jsonc`
only for non-Vite entry Workers, such as a plain Hono Worker, a queue/cron
Worker, or a frontend whose adapter output is intentionally the dev entrypoint.

For **SvelteKit + `@sveltejs/adapter-cloudflare`**, configure the adapter's
platform proxy and run Vite:

```js
// apps/web/svelte.config.js
import adapter from "@sveltejs/adapter-cloudflare";

export default {
  kit: {
    adapter: adapter({
      platformProxy: {
        configPath: "wrangler.jsonc",
        // Keep Vite dev and Wrangler CLI migrations on the same local D1 state.
        // This path is resolved from the web app cwd when running `vite dev`.
        persist: { path: "../../.wrangler/state" },
      },
    }),
  },
};
```

```json
{
  "scripts": {
    "dev:workers": "vite dev --port 8788"
  }
}
```

SvelteKit server loads/actions can then use `event.platform.env.API` from the
web Worker's `services` binding. The binding comes from `apps/web/wrangler.jsonc`.
Set `platformProxy.persist` to the same directory used by local D1 migration
commands, otherwise Vite dev may read `apps/web/.wrangler/state` while
`wrangler d1 migrations apply --local` writes somewhere else.

For **TanStack Start or other Vite apps using `@cloudflare/vite-plugin`**, load
other Workers with `auxiliaryWorkers`:

```ts
// apps/web/vite.config.ts
import { cloudflare } from "@cloudflare/vite-plugin";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    cloudflare({
      viteEnvironment: { name: "ssr" },
      // Keep Vite auxiliary Workers and Wrangler CLI migrations on the same
      // local D1/R2/KV state. Without this, `pnpm db:migrate:local` may update
      // apps/api/.wrangler while `vite dev` reads apps/web/.wrangler.
      persistState: { path: "../api/.wrangler/state" },
      auxiliaryWorkers: [{ configPath: "../api/wrangler.jsonc" }],
    }),
    tanstackStart(),
    react(),
  ],
});
```

```json
{
  "scripts": {
    "dev:workers": "vite dev --port 3910"
  }
}
```

Root script convention:

```json
{
  "scripts": {
    "dev:workers": "pnpm --dir apps/web dev:workers"
  }
}
```

Both approaches start the Vite web app as the entrypoint and make API service
bindings available locally without deploying the API Worker.

When a Vite web app uses `auxiliaryWorkers`, explicitly set `persistState` to a
shared path if local bindings must be inspected or migrated by Wrangler CLI
commands from another app directory. The Cloudflare Vite plugin defaults to
`<vite-root>/.wrangler/state/v3`; standalone `wrangler dev` and
`wrangler d1 migrations apply --local` default to the Worker config directory.
If these differ, the API Worker can appear to have tables when started alone but
have an empty D1 database when started as a Vite auxiliary Worker.

### 4.2 Type-Safe API Calls: The Only Two Allowed Paths

For APIs owned by the same product/repo/team, **never call them with raw
`fetch()` from application code**. Raw fetch loses route typing, input typing,
output typing, and refactor safety. If the API is ours, use one of these two
type-safe paths:

| Path | Use when | Runtime surface |
|------|----------|-----------------|
| **Cloudflare Service Binding RPC** | The caller is another Worker in the same Cloudflare account, especially SSR/server code | `Service<ApiEntrypoint>` direct method calls |
| **Hono RPC client** | The caller must go through HTTP, such as browser code or an external process that cannot use service bindings | `hc<AppType>(origin)` |

Allowed raw `fetch()` cases:

- Third-party APIs such as npm, JSR, GitHub, Rekor, Stripe, etc.
- Asset/file fetches where no owned API contract exists.
- Low-level infrastructure code whose job is explicitly to implement a typed
  client wrapper.

Disallowed raw `fetch()` cases:

- Browser component calling `fetch("/api/...")` for an owned API.
- SvelteKit/TanStack server code calling an owned Worker over untyped HTTP
  when a service binding exists.
- Ad-hoc JSON parsing from an owned endpoint instead of using `Service<T>` or
  `hc<AppType>`.

### 4.3 Calling Internal APIs via Service Binding RPC

Use this for fully internal calls between Cloudflare Workers. It is the default
for SSR frontends calling the API Worker.

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

In SvelteKit server actions / server load functions:

```ts
// src/lib/server/api.ts
import type { ApiEntrypoint } from "@scope/api";

export function getApi(event: {
  platform?: App.Platform;
}): Service<ApiEntrypoint> {
  const api = event.platform?.env.API;
  if (!api) {
    throw new Error("API service binding is not available");
  }
  return api as unknown as Service<ApiEntrypoint>;
}
```

```ts
// src/routes/dashboard/publish/+page.server.ts
import { fail } from "@sveltejs/kit";
import type { PublishExtensionInput } from "@scope/api";
import { getApi } from "$lib/server/api";
import type { Actions } from "./$types";

export const actions: Actions = {
  default: async (event) => {
    if (!event.locals.userId) {
      return fail(401, { message: "Authentication required" });
    }

    const input: PublishExtensionInput = {
      registry: "npm",
      packageName: "example-extension",
    };

    return getApi(event).publishExtension(input, event.locals.userId);
  },
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

Service binding RPC rules:

- Import the `ApiEntrypoint` class **as a type** from the API package.
- Call methods directly: `api.searchEvents(input, userId)`.
- Put validation and business logic in shared core functions used by both HTTP
  routes and RPC methods.
- Forward authenticated `userId` from the caller and still scope DB queries by
  that `userId`.
- Do not introduce a SvelteKit `+server.ts` proxy endpoint just to reach the API
  Worker. If both sides are Workers, call the service binding.

### 4.4 Calling Owned HTTP APIs via Hono RPC Client

Use Hono RPC only when the call genuinely needs HTTP. Common cases:

- Browser code calling a same-origin SvelteKit Hono bridge.
- Local tools or external apps that do not have Cloudflare service bindings.
- Public API consumers where HTTP is the product boundary.

Export the typed Hono app contract from the API Worker:

```ts
// apps/api/src/app.ts
import { Hono } from "hono";

const app = new Hono()
  .get("/health", (c) => c.json({ ok: true }))
  .post("/extensions/publish", async (c) => {
    const input = await c.req.json<PublishExtensionInput>();
    return c.json(await publishExtensionCore(c.env, input, c.var.userId));
  });

export type AppType = typeof app;
export default app;
```

Define one typed client helper:

```ts
// apps/web/src/lib/api-client.ts
import { hc } from "hono/client";
import type { AppType } from "@scope/api/app";

export const apiClient = hc<AppType>(
  typeof window === "undefined" ? "http://localhost:8787" : window.location.origin,
);
```

Then call through the generated RPC surface, never raw paths:

```ts
const res = await apiClient.extensions.publish.$post({
  json: {
    registry: "npm",
    packageName: "example-extension",
  },
});

const data = await res.json();
```

For SvelteKit Hono-in-SvelteKit bridges, mount Hono behind a catch-all route:

```ts
// src/routes/api/[...slugs]/+server.ts
import { app } from "$lib/server";

type RequestHandler = (event: { request: Request }) => Response | Promise<Response>;

export const fallback: RequestHandler = ({ request }) => app.fetch(request);
```

Hono RPC rules:

- Export `AppType` from the Hono app module.
- Keep a single `hc<AppType>()` helper; do not scatter client construction.
- Prefer Hono RPC over raw fetch for any owned HTTP API.
- Prefer service binding RPC over Hono RPC when the caller and callee are both
  Cloudflare Workers and no public HTTP boundary is required.

### 4.5 Typing the Binding

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

### 5.4 Service Binding Local Development Behavior

**How it works:** When you run `wrangler dev -c web/wrangler.jsonc -c api/wrangler.jsonc`, Wrangler/Miniflare starts both Workers in the same local process. The web Worker's `services` binding automatically resolves to the locally-running API Worker by matching the `"service"` name.

**Vite frontend exception:** If the web Worker is a Vite-served frontend, do not
use raw multi-config `wrangler dev` as the web entrypoint. Start the web app
with `vite dev` instead. For SvelteKit, use `adapter-cloudflare` `platformProxy`;
for TanStack Start and other Cloudflare Vite plugin apps, configure the API as
an `auxiliaryWorkers` entry. See section 4.1.1.

**Important:** Service bindings do **not** have a `remote` option. Their routing is automatic:

| Scenario | Binding target |
|----------|---------------|
| `wrangler dev` with both configs | ✅ Local Worker (by name match) |
| SvelteKit `vite dev` with `adapter-cloudflare` `platformProxy` | ✅ Local service binding from wrangler config |
| TanStack/other Vite `vite dev` with API in `auxiliaryWorkers` | ✅ Local auxiliary Worker |
| `wrangler dev` only for caller | ❌ `not connected` — calls fail |
| Deployed to Cloudflare | Cloud Worker with matching name |

**No URL or hostname needed.** RPC calls like `env.API.ping()` do not use HTTP; they use Cloudflare's internal RPC protocol. The caller does not know or care about `localhost:8787` — it only knows the binding name (`API`) and the service name (`my-api-dev`).

**Other bindings** (like `ai_search`, `vectorize`) may use `"remote": true` to connect to real Cloudflare resources during local dev, but this does **not** apply to service bindings.

**Troubleshooting:** If `env.API` is undefined or calls fail in local dev, check:
1. Are both Workers running under the same `wrangler dev` command with both `-c` flags?
2. Does the `service` name in web's `wrangler.jsonc` exactly match the `name` in api's `wrangler.jsonc`?
3. Did you run `pnpm cf:typegen` after adding the binding?

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

### 6.5 D1 Local State And Migrations

Wrangler local D1 state is scoped by the persistence directory, not only by the
D1 database name. In a monorepo, make one directory the source of local runtime
state and point every local path at it:

- `wrangler d1 migrations apply --local` should run from the app that owns the
  D1 binding, or use that app's config with `--config`.
- SvelteKit Vite dev using `@sveltejs/adapter-cloudflare` should set
  `platformProxy.persist.path` to the same directory used by local migration
  scripts, for example `../../.wrangler/state` when running from `apps/web`.
- Vite entry Workers using `@cloudflare/vite-plugin` should set
  `persistState: { path: "../api/.wrangler/state" }` (adjust the path) when the
  API app owns D1 migrations.
- Do not compare Dashboard D1 data to local dev data. Dashboard shows remote
  D1; local D1 lives under `.wrangler/state/v3`.

Use `remote: true` on D1 only when local dev must hit the remote Cloudflare D1.
It can be useful for production-like testing, but it makes local UI work depend
on the remote D1 proxy. For day-to-day local development, prefer local D1 and
run migrations locally.

Migration flow:

```bash
pnpm db:generate          # only after changing packages/db/src/schema.ts
pnpm db:migrate:local     # update local D1
pnpm db:migrate:remote    # update remote D1 when ready
```

Do not run `db:generate` as a generic "sync" command. It compares the Drizzle
schema to the committed migration metadata and creates a new migration file. If
the schema did not change but metadata is out of sync, it may generate a second
`0000_*` baseline migration that tries to create tables that already exist.

Initial baseline rules:

- Pick one baseline migration and commit it with `meta/0000_snapshot.json` and
  `meta/_journal.json`.
- The journal tag must match the baseline migration filename without `.sql`.
- After the baseline is applied to any database, replacing it with another
  `0000_*` file requires resetting that database or marking migrations
  carefully. Otherwise Wrangler will attempt to apply the new baseline on top of
  existing tables.
- Prefer Drizzle-generated baselines for new projects. If a hand-written
  baseline is used, keep Drizzle metadata aligned with the actual SQL.

Resetting a local D1 for a clean baseline means dropping both app tables and
Wrangler's migration table, then reapplying migrations:

```bash
pnpm --dir apps/api exec wrangler d1 execute my-db-dev --local --command "
PRAGMA foreign_keys=off;
DROP TABLE IF EXISTS usage_events;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS episodes;
DROP TABLE IF EXISTS content_items;
DROP TABLE IF EXISTS provider_credentials;
DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS prompt_presets;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS d1_migrations;
PRAGMA foreign_keys=on;
"

pnpm db:migrate:local
```

Adjust the table list for the project. If the app seeds default rows in code,
run the normal bootstrap endpoint/server function after migrating; migrations
should create schema, not hidden runtime data, unless the project explicitly
uses SQL seed migrations.

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
    "dev:cf": "wrangler dev -c apps/api/wrangler.jsonc -c apps/web/wrangler.jsonc",
    "dev:workers": "pnpm --dir apps/web dev:workers"
  }
}
```

| Script | Purpose |
|--------|---------|
| `dev` | Turbo runs all apps in parallel. Often too noisy — prefer `cd apps/<x> && pnpm dev`. |
| `dev:cf` | Runs both workers in one raw `wrangler dev` process with service bindings wired. Use for plain Workers/non-Vite entrypoints. |
| `dev:workers` | Runs the Vite web app as the local entrypoint. SvelteKit uses `platformProxy`; TanStack/other Cloudflare Vite plugin apps use `auxiliaryWorkers`. |
| `cf:typegen` | Regenerates `worker-configuration.d.ts` for both apps after binding changes. |
| `db:generate` | Runs `drizzle-kit generate` from the shared schema package. |

## 9. Development Workflow

### 9.1 Starting from scratch

1. `pnpm install`
2. `cp apps/web/.env.example apps/web/.env.local` (fill auth keys if needed)
3. `pnpm db:generate` (if schema changed)
4. `pnpm db:migrate:local` or `pnpm db:migrate:remote`
5. `pnpm cf:typegen`
6. `pnpm dev:workers` for Vite web apps, or `pnpm dev:cf` for raw Worker entrypoints

### 9.2 After changing bindings

1. Edit `wrangler.jsonc`
2. Run `pnpm cf:typegen` in the affected app
3. Commit the updated `worker-configuration.d.ts`

### 9.3 After changing D1 schema

1. Edit `packages/db/src/schema.ts`
2. `pnpm db:generate`
3. Confirm the generated file is an increment such as `0001_*`, not a duplicate
   `0000_*` baseline
4. `pnpm db:migrate:local` (test) or `pnpm db:migrate:remote` (deploy)
5. Restart local Vite/Workers dev servers after migration if they keep binding
   state open
6. All workers referencing the same `migrations_dir` and `persistState` stay in
   sync

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
| **Use service binding RPC for internal Worker-to-Worker calls** | Zero latency, zero auth overhead, structurally private, fully typed with `Service<ApiEntrypoint>` |
| **Use Hono RPC client for owned HTTP APIs** | Keeps route names, params, input, and response shapes type-safe across HTTP |
| **Never raw-fetch owned APIs** | `fetch("/api/...")` + manual JSON parsing bypasses the contract and breaks refactor safety |
| **Keep `app.ts` free of `cloudflare:workers`** | Node-side tooling (tests, OpenAPI export) can import routes |
| **Re-export RPC input/output types from `apps/api`** | Web worker imports them to stay type-safe |
| **Scope RPC methods by `userId`** | Even with structural trust, defensively scope DB queries per user |
| **Use `ctx.waitUntil()` for side effects** | Keep RPC method latency low; fire off outbox drains, index updates, etc. |
| **Never store request state in module-level vars** | Workers are single-threaded isolates, but requests interleave on the same isolate |
| **Commit auto-generated files** | `worker-configuration.d.ts`, TanStack `routeTree.gen.ts`, Drizzle migrations — all committed, never hand-edited |

## 12. Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Browser/server code calls `fetch("/api/...")` for an owned API | Untyped bypass around the API contract | Replace with a SvelteKit/TanStack server action that calls `Service<ApiEntrypoint>`, or use `hc<AppType>()` when HTTP is required |
| `API binding missing` in local dev | `@cloudflare/vite-plugin` or `adapter-cloudflare` not configured with `wrangler.jsonc` | Check `svelte.config.js` `platformProxy.configPath` or `vite.config.ts` `cloudflare()` plugin |
| Type error on `env.API.ping()` | `Service<ApiEntrypoint>` generic not applied | Cast in app.d.ts or client helper: `env.API as unknown as Service<ApiEntrypoint>` |
| `drizzle-orm` type errors in web | Web tsconfig includes api source files | Add `"exclude": ["../api/src/**/*"]` to web tsconfig |
| Build hangs after "Tunnel closed" (TanStack Start) | `@cloudflare/vite-plugin` + prerender conflict | Disable prerender: `prerender: { enabled: false }` in `tanstackStart()` plugin options |
| Vectorize / AI Search not working locally | Binding not supported in Miniflare | Set `"remote": true` and test against deployed worker, or mock |
| D1 schema drift between workers | One worker applied old migrations | Ensure both `wrangler.jsonc` files point to the same `migrations_dir` |
| API has D1 tables when started alone, but Vite web + auxiliary API has none | Vite plugin and Wrangler CLI are using different local persistence directories | Set `cloudflare({ persistState: { path: "../api/.wrangler/state" } })` or migrate the same state directory used by Vite |
| `table ... already exists` during local migration after reset/generate | A duplicate `0000_*` baseline is being applied, or app tables were dropped but `d1_migrations` was not | Keep one baseline in migrations metadata; when resetting, drop `d1_migrations` too before `db:migrate:local` |
| `db:generate` creates another `0000_*` migration | Drizzle migration metadata is missing or out of sync with the committed baseline | Do not apply the duplicate baseline; fix `meta/_journal.json` and snapshot alignment, or reset DBs and adopt the new baseline deliberately |

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

### "I need frontend code to mutate data through our API"

```
Is the caller running on a Cloudflare Worker server surface?
  → Yes: use a server action/server function/load and call Service<ApiEntrypoint>
  → No, it must call HTTP from browser/external process:
      export AppType from the Hono app
      create one hc<AppType>() helper
      call apiClient.some.route.$post({ json })
  → Never use raw fetch("/api/...") for owned APIs
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
