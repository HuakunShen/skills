# Tech Stack — how to choose frontend, backend(s), and TUI

Decide the stack BEFORE scaffolding. The multi-surface shape is stack-agnostic:
the same contract + thin-surface discipline applies whether the backend is JS,
Rust, or both. What changes is where the core lives and how many backends you ship.
Read this file first on any new project or convert task, walk the decision tree
with the user, and record the answers (one paragraph each) before writing code.

This skill gives concrete guidance for **TypeScript/JS and Rust only**
(`coding-style` language matrix: TS first, Rust for compiled cores).
Go/bubbletea is mentioned only as a TUI option because the owner named it;
other languages are deliberately out of scope — do not invent guidance for them.

## 0. First principle: push core logic as far forward as possible

```
best → core in web-ui / frontend (pure TS, tested without any backend)
ok   → core in packages/core (host-free TS), backends are thin executors
costly → core must live in the backend (perf / syscalls / binary deps) → read §3
```

The ssh-tunnel-ui case is the model for "forward": the backends (JS + Rust)
only spawn fixed `ssh -N` commands, probe TCP, and persist JSON. ALL decisions —
which argv, which state transitions, which validations — live in the frontend /
shared core. Duplicating two thin executors (one JS, one Rust) is cheap because
they contain no decisions. Always try to shrink the backend to an executor first;
only what cannot move forward justifies napi or a Rust-only core.

Questions to ask the user:

1. Which decisions MUST run where the data/syscalls are? (If none → frontend core.)
2. Which operations are just "run this fixed command / read this file / probe this
   port"? (Those are executor methods, safe to duplicate across two backends.)
3. What actually needs native speed or OS handles? (Name the functions, not vibes.)

## 1. Decision tree

```
Q0: Which surfaces must exist? (Ask this before anything about languages.)
  - Browser / VS Code webview / DSH panel / Kunkun custom-view needed
    (any web-based surface) → frontend MUST be web UI (Svelte/React/any).
    GPUI is off the table — it cannot serve those surfaces. Go to Q1.
  - Desktop-only: a native desktop app is enough, no browser/webviews ever
    → Q0b.
  - Not sure → assume web UI (it keeps all surfaces open); note GPUI as a
    possible later split, not a starting point.

Q0b (desktop-only only): Is the backend Rust (or going Rust via Q1/Q2)?
  YES → GPUI native frontend is allowed INSTEAD of web UI (§3B):
         `apps/gpui` (or `apps/desktop-gpui`), separate cargo workspace,
         links the Rust core/executor crate in-process. No web dist, no Tauri,
         no web-based surfaces ever. Accept that choice explicitly — it closes
         the door to browser/VS Code/DSH/Kunkun reuse of the UI.
  NO (backend stays JS) → web UI via Tauri (`apps/desktop`); GPUI makes no
         sense without a Rust core. Go to Q1.

Q1: Does any hot path need native speed, heavy syscalls, or binary deps
    (disk walk at GB/s, crypto, pty, OS handles)?
  NO  → Single JS backend (§2A). Frontend core allowed. Simplest path.
  YES → Q2.

Q2: Can the hot part be isolated to a small executor API
    (e.g. `scan(dir) → snapshot`, `spawn(cmd) → handle`, `probe(host) → status`)
    while decisions stay in TS?
  YES → Dual backend (§2B): JS executor for CLI/plugins + Rust executor for Tauri.
         Same contract, two thin executors, decisions in frontend/core.
  NO (core IS the perf engine, e.g. space-lens kunto-scan) → Single Rust core
       + napi-rs for JS surfaces (§2C). Accept the packaging cost, manage it.
```

Record the outcome as: `stack: single-js | dual-js-rust | rust-core-napi`,
plus `frontend: web (Svelte|React|<other>) | gpui` with the Q0 answer attached,
plus the executor API (function list) or the napi surface (function list).
If the user cannot answer Q0–Q2, default to single-JS + web UI and note what would
force a re-decision (measured numbers, not guesses).

## 2. The three stack shapes

### 2A. Single JS backend (default, start here)

- `packages/core` (pure TS) + `packages/host-node` (Hono + node:* ports).
- All surfaces talk HTTP/SSE to the daemon, or `--direct` in-process.
- Tauri uses `invokeTransport` only as a thin shim over the SAME JS logic
  (no second engine). No napi, no multi-platform native matrix.
- When to leave: measured proof (profile numbers in the decision record) that
  a hot path cannot meet its budget in JS.

### 2B. Dual backend: JS executor + Rust executor (ssh-tunnel-ui pattern)

When the backend is an executor (fixed commands, spawn/probe/persist) and Tauri
wants a Rust core without dragging Node into the desktop bundle:

- Contract stays single (zod TS is the source of truth; Rust mirrors it with
  serde structs + a shared `fixtures/` corpus that both sides must pass).
- Decisions live in `packages/core` + `packages/web-ui` (frontend). Both executors
  implement the same small trait/interface:
  `Process(spawn/kill) / Probe(tcp) / Store(read/write JSON) / Clock`.
- JS executor: `packages/host-node` (node:* allowed here only).
- Rust executor: `crates/<core>` (trait-injected ports, `#![forbid(unsafe_code)]`,
  thiserror libraries + anyhow CLIs per `coding-style`). Tauri `src-tauri`
  links it in-process via `tunnel_*`/`scan_*` commands (route-for-route mirror
  of the HTTP API). Separate cargo workspace so root `cargo build` never sees
  a WebView.
- JS surfaces (CLI/TUI/VS Code/DSH/Kunkun) use the JS executor; Tauri uses the
  Rust executor. Neither executor contains decisions, so drift is bounded by
  the fixture corpus + `check-contract`.
- Cost: two executor implementations to keep in sync. Keep the executor API
  to ≤ ~5 methods; if it grows past that, re-run Q2 (it may be a hidden core).

### 2C. Rust core + napi-rs (space-lens pattern, perf engines only)

When the core itself must be native (scan engines, parsers, crypto):

- Rust crate is the ONLY engine (`vendors/` submodule or `crates/`).
  TS `packages/core` becomes a thin typed wrapper, not a second implementation.
- Ship JS surfaces via **napi-rs**: `packages/node` builds platform binaries,
  `optionalDependencies` per target (8+ entries), CLI bin generated at prepublish.
  Expect the packaging cost up front: multi-platform matrix, `verify-native-artifacts`
  gate (desktop bundle contains no JS runtime), updater feed, Homebrew/cask notes.
- Subpackage strategy (keep bundle size sane):
  - The npm `node` package ships napi binaries ONLY (no web dist inside).
  - `apps/cli` bundles JS glue via esbuild (single-file ESM) and depends on the
    napi package as `optionalDependencies` per platform.
  - Plugin surfaces (VS Code/DSH/Kunkun) depend on the JS API, never compile Rust;
    if a plugin host cannot take native binaries (web-only DSH client, Kunkun
    custom-view sandbox), that surface gets the HTTP path to a daemon instead of
    an in-process engine. Document per surface: `in-process napi` vs `HTTP daemon`.
  - Never pack all platform binaries into one distributable; let the package
    manager select per platform.
- FFI for SwiftUI-style shells: conservative C ABI facade (`struct_size` +
  `abi_version` + opaque handles), read-only snapshots, portable JSON export.

## 3. Frontend choice (web UI by default; GPUI only for Rust desktop-only)

### 3A. Web UI (default — required if any web-based surface exists)

`packages/web-ui` may be **Svelte (SvelteKit), React (Vite), or any framework the
user names** — the skill does not mandate one. What is mandated, regardless of
framework:

- Host-free: no `node:*`, no hardcoded URLs, no direct `fetch`. The client (or
  `BackendAdapter`) arrives via props/context. This is what lets one component
  tree serve browser + Tauri + VS Code webview + DSH panel + Kunkun view.
- One codebase, flavored builds: `build` (daemon-hosted) / `build-desktop`
  (Tauri `frontendDist`, relative base) / `build-dsh` (embedded prefix). Flavors
  differ in base-path + API-endpoint injection ONLY — never forked components.
- Runtime-mode detection (kkterminal pattern): `window.__kunkun__` → kunkun
  transport, `#token=`/`?rpc=` → websocket to daemon, else demo with mock client.
  Host SDKs lazy-imported per mode, never bundled into the standalone build.

### 3B. GPUI native frontend (Rust desktop-only, opt-in — never the default)

When Q0 says desktop-only AND the backend is Rust (dual executor or Rust core):

- `apps/gpui` (or `apps/desktop-gpui`): a **separate cargo workspace** binary that
  links the Rust core/executor crate in-process — same rule as Tauri's `src-tauri`
  isolation (root `cargo build` never sees the UI framework). Real precedent:
  `refyard/apps/desktop-gpui`, `space-lens/apps/gpui`, `ssh-tunnel-ui/apps/gpui`.
- No web dist, no webview, no `packages/web-ui` reuse. UI is Rust-native code;
  the contract still governs the engine boundary (serde mirror + `fixtures/`
  corpus), but components are NOT shared with any web surface.
- Tradeoff to state explicitly with the user: choosing GPUI **closes the door**
  to browser, VS Code webview, DSH panel, and Kunkun custom-view — all of those
  require a web UI. If any of them might come back later, start with web UI +
  Tauri instead, and keep GPUI as a possible later split (the engine boundary
  makes that split cheap).
- Never both as starting point: one frontend per project at scaffold time (web
  OR gpui). A second frontend is a later, deliberate commit once the engine
  boundary is stable and tested.

## 4. TUI choice (match the backend language)

| Backend language | TUI stack | Notes |
|---|---|---|
| JS/TS | **uniview** (Solid) or opentui (React) | Thin front over the SAME client; daemon/`--direct` dual mode; keep UI libs `external` in the bundle |
| Rust | **ratatui** (+ crossterm) | See the `ratatui-dev` skill for aesthetics/event-loop guidance; TUI calls the Rust core crate directly or the daemon HTTP API |
| Go | **bubbletea** (if the user chose Go) | Same thin-front rule; no further guidance in this skill |

Whichever stack: the TUI never re-implements validation, state machines, or
protocol strings — it renders lists/forms and sends intents via client/core.

## 5. Record template (paste into the design doc / ADR)

```md
## Stack decision (<product>, <date>)
- Surfaces needed: <browser/VS Code/DSH/Kunkun any? or desktop-only> (Q0 answer)
- Frontend: web (Svelte | React | <other>) | gpui (Q0b answer; gpui only if Rust + desktop-only)
- Backend shape: single-js | dual-js-rust | rust-core-napi (Q1/Q2 answers; Q0b may force gpui frontend)
- Executor API (dual) or napi surface (rust-core): <function list>
- TUI: uniview | opentui | ratatui | bubbletea (must match backend language)
- Per-surface transport: CLI … / Tauri … / VS Code … / DSH … / Kunkun …
  (each: in-process | HTTP daemon | invoke | kkrpc — no "TBD")
- Re-decision triggers: <measured numbers that would change this>
```
