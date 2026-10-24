# Architecture — monorepo layout and dependency rules

Mined from `space-lens`, `refyard`, `ssh-tunnel-ui`, `kkterminal` (all `~/ExtDev/`).
All four agree on the same skeleton; names differ only by product prefix.
Read `tech-stack.md` FIRST: the layout below shows all three backend shapes, but
you scaffold only the one the stack decision picked (single-js → no `crates/`;
dual → thin executors both sides; rust-core-napi → Rust engine + napi wrapper).

## 1. Canonical layout

```
<product>/
  apps/
    cli/          # npx entry, bin, Effect/commander argv, serve+open
    server/       # (optional) standalone daemon binary; else cli serves
    web/          # SvelteKit/Vite static SPA, adapter-static
    tui/          # opentui / uniview fullscreen front
    desktop/      # Tauri shell: package.json + src-tauri/
    vscode/       # VS Code extension (or integrations/vscode/)
    dsh/          # DSH plugin (or integrations/dsh/)
    kunkun-plugin/# Kunkun custom-view (kkterminal pattern)
  packages/
    contract/     # @<product>/contract — zod only, routes+errors+version+events
    core/         # @<product>/core — domain logic (pure TS, or thin wrapper over Rust core)
    client/       # @<product>/client — typed fetch/SSE client, fetch-injected
    host-node/    # @<product>/host-node — JS executor: node:* ports + Hono (absent only if rust-core serves all transports)
    service/      # @<product>/service — Manager + Hono wiring (or packages/host)
    host/         # (space-lens name for service) — Hono REST+SSE+static SPA
    web-ui/       # @<product>/web-ui — shared components in Svelte, React, or any framework; host-free
    node/         # (rust-core-napi only) napi-rs binding published to npm (binaries, no web dist inside)
  crates/
    <core>/       # (dual-js-rust: thin Rust executor mirroring host-node; rust-core-napi: THE engine)
  integrations/
    dsh/ vscode/ kunkun/ xross/   # adapters into someone else's host
  scripts/
    check-boundaries.ts  check-contract.ts  build-desktop.ts  build-dsh-plugin.ts  bundle-cli.ts
    verify-native-artifacts.ts (rust shapes: desktop bundle contains no JS runtime)
  tests/ fixtures/  # fixtures/ holds the cross-implementation corpus (dual/rust shapes must both pass it)
```

Real examples:

- space-lens: `packages/{contract,client,host,node,web-ui,ai-advisor}` +
  `apps/{cli,tui,vscode,desktop,dsh,web}` + `crates/{discovery,storage-usage,…}`.
- refyard: `packages/{git-contract,git-core,git-service,git-client,host-node,backend-http,backend-tauri,git-ui}` +
  `apps/{cli,web,desktop,refyard-vscode}` + `integrations/{dsh,kunkun,xross}`.
- ssh-tunnel-ui: `packages/{ssh-contract,ssh-core,ssh-host-node,ssh-service,ssh-client,web-ui}` +
  `apps/{server,cli,tui,web,desktop,gpui}` + `crates/tunnel-core` + `integrations/{dsh,vscode}`.
- kkterminal: `packages/{core,client,node,pty}` + `apps/{cli,web,flutter,kunkun-plugin}`.

## 2. Dependency directions (enforced, not suggested)

```
contract ← everyone (no exceptions)
core → contract only (never node:*, DOM, vscode, tauri)
client → contract only (+ injected fetch)
host-node → contract (+ node:* allowed HERE ONLY)
service/host → contract + core + host-node
web-ui → contract + client (never host-node, never node:*)
apps/cli,apps/server → service/host + core + client
apps/tui → client (+ core ONLY in --direct mode via service)
apps/web → web-ui + client
apps/desktop → web dist (embedded) + client via invokeTransport
apps/vscode, integrations/* → client + web dist + supervisor (spawn)
crates/<core> → contract mirror (serde structs, same fixture corpus — never a second contract)
```
Stack variants: single-js uses all TS lines above. dual-js-rust adds the
`crates/` line (thin executor, ≤ ~5 methods, decisions stay in TS). rust-core-napi
replaces `core → contract only` with `core (thin TS wrapper) → node (napi) →
crates/<engine>`; plugin surfaces still consume the JS API or HTTP daemon, never
compile Rust themselves.

Boundary table (encode in `scripts/check-boundaries.ts`, fail CI on violation):

| Package kind | MUST NOT import |
|---|---|
| `packages/contract`, `packages/core`, `packages/web-ui`, `packages/client` | `node:*`, DOM `window`, `vscode`, `tauri`, `apps/*` |
| `apps/*` | each other (`apps/cli` ↛ `apps/web`); domain rules (move to core) |
| `spikes/*`, `*.test.*` | never imported by shippable code |

Portable packages export TS source directly (`"exports": {".": "./src/index.ts"}`);
only runnables bundle (esbuild single-file ESM + `#!/usr/bin/env node` + chmod).
See `ssh-tunnel-ui/packages/build-helper` pattern: shared `buildBinary()`.

## 3. Workspace config

- TS: pnpm workspace + turbo (`build dependsOn ^build`), `catalog:` pins
  third-party versions, internals are `workspace:*`. (space-lens is the one
  exception: yarn workspaces — same shape, different runner.)
- Rust (if any): root `[workspace] members=["crates/*"]`,
  `default-members` = headless crates ONLY. Tauri (`apps/desktop/src-tauri`)
  and GPUI are **separate workspaces** that `path`-depend on the core crate —
  root `cargo build` never sees a WebView.
- Version upgrades appear in the task's own commit; catalog diff is the review surface.

## 4. The host serves API + SPA together

`packages/host` (Hono) does two duties in one process:

- `GET/POST /api/*` per contract routes, token auth (`Authorization: Bearer`),
  `GET /api/events` SSE stream for live updates.
- `GET /*` static-serves `apps/web`'s dist (configurable `--web-dir`).

The CLI's `serve` command starts it; `--port/--host/--store/--token` flags +
`daemon.json` (`~/.<product>/daemon.json`) let every surface discover it.
This single decision is what makes browser/Tauri/VS Code/DSH/Kunkun all work:
they either open the URL, embed the dist, or frame it.

## 5. The service seam + machine interface (space-lens/refyard pattern)

- UI depends on an interface, never a transport: `WorkbenchService` /
  `BackendAdapter → BackendSession { metadata, domain, mutations, host, events }`.
  Implementations: `http` (REST+SSE bearer), `tauri` (invoke+events, no bearer),
  `kunkun` (kkrpc expose/wrap), `xross` (TCP forward). Chosen once in the
  composition root (`runtime/backend-registry.ts`).
- `--machine` mode is the plugin contract: stdout prints readiness JSON
  (`{ port, url }`), stderr prints a one-time pairing URL (`?pair=` ticket, 60s TTL
  → in-memory bearer). Supervisor (VS Code/DSH/Kunkun) parses stdout, exchanges
  the ticket, keeps the bearer in memory (never localStorage). `doctor` command
  returns exit 2 when unavailable for scripting.
- `GET /api/v1/capabilities` is the full feature set; unimplemented routes return
  honest 501 (`UNIMPLEMENTED_PATHS`), never fake 202. Unknown `/api/*` returns JSON
  404, never SPA fallback.
