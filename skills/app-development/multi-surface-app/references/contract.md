# Contract — the closed source of truth

`packages/contract` is the ONLY place wire shapes are declared. Server, client,
TUI, web-ui, and every plugin import it; nobody re-declares a path or a field.
Single dependency: `zod` (one schema library per repo, never mixed).
In dual/rust shapes the Rust side mirrors it with serde structs validated against
the same `fixtures/` corpus — a mirror, never a second contract.

## 1. Files

```
packages/contract/src/
  index.ts      # re-exports only
  routes.ts     # TUNNEL_ROUTES / SCAN_ROUTES: { name: { method, path } } as const + path helpers
  tunnel.ts     # request/response schemas per route (or scan.ts, apps.ts, … per domain)
  errors.ts     # PROBLEM_CODES as const + CodedError class + code→HTTP status Record (exhaustive)
  version.ts    # CONTRACT_VERSION + compatibility check (server/client handshake)
  events.ts     # SSE event schemas (discriminated union on `type`)
```

## 2. Routes table (copy this shape)

```ts
// packages/ssh-contract/src/routes.ts — real pattern from ssh-tunnel-ui
export const TUNNEL_ROUTES = {
  health:        { method: "GET",    path: "/api/health" },
  listProfiles:  { method: "GET",    path: "/api/profiles" },
  createProfile: { method: "POST",   path: "/api/profiles" },
  getProfile:    { method: "GET",    path: "/api/profiles/:id" },
  startTunnel:   { method: "POST",   path: "/api/states/:id/start" },
} as const;
export type TunnelRouteName = keyof typeof TUNNEL_ROUTES;

export function statePath(id: string): string {
  return `/api/states/${encodeURIComponent(id)}`;
}
```

Rules:

- Paths + methods declared ONCE as `as const`; helpers (`statePath(id)`) build
  URLs so `encodeURIComponent` cannot be forgotten or disagree.
- Requests: `z.strictObject({...})` — unknown fields rejected (catches client drift).
- Responses: `schema.loose()` (or `.catchall(unknown)`) — server may add fields
  without breaking old fronts.
- DTO types derived via `z.infer`; literals written once (`as const` + `typeof`),
  never `enum`; polymorphic payloads are discriminated unions (`kind`/`type`).

## 3. Errors (closed table, never message-branching)

```ts
export const PROBLEM_CODES = ["not_found", "validation", "conflict", "probe_failed"] as const;
export type ProblemCode = (typeof PROBLEM_CODES)[number];
export class TunnelError extends Error {
  constructor(readonly code: ProblemCode, message: string) { super(message); }
}
export const PROBLEM_STATUS: Record<ProblemCode, number> = {
  not_found: 404, validation: 400, conflict: 409, probe_failed: 502,
};
```

Consumers branch on `code`, never on `message`. `check-contract.ts` asserts the
`Record` is exhaustive (add a code → compiler forces a status).

## 4. Typed client (hand-written, fetch-injected)

```ts
// packages/client — one method per route, validates every response
export interface Transport { fetch: typeof fetch; baseUrl: string; token?: string }
export function createTunnelClient(t: Transport): TunnelClient { … }
```

- Caller injects `fetch`: browser native, node, VS Code, DSH, Tauri `invoke`
  (`invokeTransport` maps methods to `invoke("tunnel_*")` — same interface,
  zero ports, used by Tauri Phase-1 to drop the Node runtime).
- Every response passes its contract schema before returning; failures throw the
  coded error from `errors.ts`.
- `check-contract` test: every key of the routes table has a client method AND a
  server handler; missing coverage fails CI.

## 5. Version + events

- `version.ts` exports `CONTRACT_VERSION`; `/api/health` returns it; client warns
  (not crashes) on major skew — responses are `.loose()` so skew degrades gracefully.
- `events.ts` SSE schemas (`{ type: "state_changed", state: … }`); host publishes,
  web-ui/TUI subscribe; DSH/VS Code reuse the same stream.
