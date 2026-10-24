# Convert — turn an existing program into the multi-surface shape

Use this when the user says "convert <X> into this design" or "I have a script/
single-page app/CLI and want npx + web + TUI + desktop + plugins". Work in order;
one commit per step (commit style follows `coding-style`: `type(scope): sentence`).

## Step 0 — Inventory + stack decision (half a page + decision record, before touching code)

- Entry points today? (argv? `main()`? page?)
- Domain rules vs I/O: list every function that touches `node:*`/DOM/network —
  those are future Ports, not core.
- External shapes: flags, config files, HTTP paths, stored JSON — future contract.
- **Stack decision first** (`references/tech-stack.md` Q0/Q1/Q2 with the user):
  push core logic as far forward as possible (frontend > host-free core > executor
  backends > napi core). Record `single-js | dual-js-rust | rust-core-napi` +
  executor/napi function list + frontend framework + TUI stack + per-surface
  transports using the record template. A convert that skips this step rebuilds
  the backend twice — that is the most expensive mistake in this skill.
- Write it down; the rest is mechanical.

## Step 1 — Extract `packages/contract` (first commit)

1. Copy every external shape into `routes.ts` (paths+methods `as const` + helpers),
   domain schemas, `errors.ts` (closed codes + `Record<code,status>`), `version.ts`.
2. Request schemas `strictObject`, responses `.loose()`.
3. Add `scripts/check-contract.ts`: routes table ⊆ server handlers ∩ client methods.
   Until this is green, nothing else lands.

## Step 2 — Extract `packages/core` (second commit)

1. Move pure logic (parse/validate/state-machine/argv-builder) into core,
   host-free. Host capabilities become injected Ports:
   `FileStore / Process / Probe / Clock / Store`.
2. Forbid `node:*`/DOM/host imports via `check-boundaries.ts`.
3. Unit-test core with fake ports — no daemon, no network.

## Step 3 — Build `packages/client` + `packages/host-node` (third commit)

1. Client: one method per route, `fetch` injected, responses validated, coded errors.
2. Host: Hono wiring of the routes table + token auth + SSE + static SPA serving.
   `apps/server` (or `cli serve`) = 20-line composition root: parse argv → build
   real ports → `startDaemon()`.

## Step 4 — Extract `packages/web-ui` (fourth commit)

1. Move components out of the old page into `web-ui`, receiving `client` via props.
   No hardcoded URLs, no direct `fetch`, no host imports.
2. `apps/web` becomes routes + wiring over `web-ui`; verify `vite build` + host
   serves it (`--web-dir=apps/web/dist`).

## Step 5 — Add surfaces one at a time (one commit each)

Order: `cli` (serve/open/--direct) → `web` flavors (`build-desktop`, `build-dsh`)
→ `tui` → `desktop` (Tauri `frontendDist`) → `vscode` (supervisor+webview)
→ `dsh` (host.js/client.js+cordis.patch) → `kunkun` (backend.js+custom-view).
Never two adapters per commit. Each gets: entry, manifest, build script,
turbo `dependsOn` on the thing it embeds, and a smoke test
(`curl /api/health`, `vsce package`, dev-load panel).

## Checklist (gate before "done")

- [ ] `check-boundaries` + `check-contract` green
- [ ] `npx <cli> serve` + `curl /api/health` returns contract version
- [ ] Browser opens the same UI the daemon serves
- [ ] TUI runs against `--daemon=<url>` AND `--direct`
- [ ] `apps/web` builds all flavors without component forks
- [ ] Each shipped adapter loads clean (Tauri window / VS Code webview / DSH panel / Kunkun view)
- [ ] No domain literal duplicated outside `contract`; no `any`/`as unknown as`
- [ ] README documents: install matrix, `daemon.json` discovery, ports, token, flavors

## Anti-patterns (stop and refactor)

- Porting the UI first (you will fork components per host — always contract→core→client→host→ui).
- Letting the old CLI keep business logic "for now" (it becomes the second source of truth within weeks).
- Hardcoding `http://127.0.0.1:<port>` anywhere except the documented default chain.
- Copying `web/dist` per host instead of building flavors from one source.
