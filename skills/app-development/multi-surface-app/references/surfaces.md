# Surfaces — up to seven thin adapters over one core

Each surface is < 300 lines of glue. If you are writing validation, a state
machine, or a protocol string here, stop — it belongs in contract/core/client.
Which backend each surface talks to comes from the stack decision
(`references/tech-stack.md`): single-js → everything HTTP/`--direct` to the JS
daemon; dual → JS surfaces to the JS executor, Tauri to the Rust executor;
rust-core-napi → in-process napi where native binaries are allowed, HTTP daemon
otherwise (document per surface: `in-process napi` vs `HTTP daemon`).

## 1. CLI — `apps/cli` (the npx entry, always first)

- `package.json`: `"bin": { "<name>": "dist/cli.mjs" }`, `engines node>=20`,
  esbuild bundle to single-file ESM (`buildBinary()` + `#!/usr/bin/env node`).
  Publishable → `npx <name> serve`.
- Commands: `serve` (start host: `--port/--host/--store/--web-dir/--token`),
  `open` (serve + open browser), plus domain verbs that call the client.
- Dual mode: **daemon** (default — discover via `--daemon=<url>` or
  `~/.<product>/daemon.json`, `createClient(baseUrl)`) vs **--direct**
  (in-process `new Manager(ports)` — zero daemon, for scripts/offline).
- TUI externals note: keep React/opentui `external` (single copy + runtime native).

## 2. Web — `apps/web` (browser, always second)

- SPA in **Svelte (SvelteKit `adapter-static`), React (Vite), or any framework the
  user names** → `dist/`. Host serves it at `/` (`--web-dir=apps/web/dist`);
  standalone `npx <cli> open` just opens the URL.
- Flavors from ONE codebase: `build` (daemon-hosted), `build-desktop`
  (Tauri `frontendDist`, relative base), `build-dsh` (DSH-embedded static).
  Differences are base-path + API-endpoint injection ONLY — never forked components.
- `packages/web-ui` holds the components; `apps/web` is routes + wiring.
- Runtime-mode tristate (kkterminal pattern): web UI detects
  `window.__kunkun__` → kunkun transport, `#token=`/`?rpc=` → websocket to daemon,
  else demo with mock client. Kunkun SDK lazy-imported per mode, never bundled
  into the standalone build.

## 3. TUI — `apps/tui` (terminal fullscreen, stack must match backend language)

| Backend language | TUI stack | Guidance |
|---|---|---|
| JS/TS | **uniview** (Solid) or opentui (`@opentui/core` + `@opentui/react`) | Thin front over the SAME client; daemon/`--direct` dual mode; keep UI libs `external` in the bundle (single copy + runtime native) |
| Rust | **ratatui** (+ crossterm) | Load the `ratatui-dev` skill for aesthetics/event-loop patterns; TUI calls the Rust core crate directly or the daemon HTTP API |
| Go (only if the user chose Go) | **bubbletea** | Same thin-front rule; this skill gives no further Go guidance |

- Whichever stack: renders lists/forms, sends intents via client/core, never
  re-implements rules. Same daemon/`--direct` dual mode as CLI.
- Discovery: `--daemon=` flag → `daemon.json` → default `http://127.0.0.1:<port>`.
- Binary: `dist/tui.mjs` (JS) or a cargo binary (Rust), invoked as its own `bin` entry.

## 4. Desktop — `apps/desktop` (Tauri 2, independent app; backend per stack decision)

- `apps/desktop/package.json` → `src-tauri/tauri.conf.json`:
  `"frontendDist": "../../web/build-desktop"`, updater endpoints, CSP
  (`connect-src 'self' ipc: http://ipc.localhost`).
- Backend wiring depends on the stack shape:
  - single-js: TS `createDesktopClient({ invoke })` shim over the SAME JS logic.
  - dual-js-rust: Rust side links the executor crate in-process (`tunnel_*` /
    `scan_*` commands, route-for-route mirror of the HTTP API); no sidecar, no
    port, no Node probing. This is why the dual shape exists.
  - rust-core-napi: Rust side links THE engine crate (same aggregation as the CLI);
    `verify-native-artifacts` gate proves the bundle contains no JS runtime.
- Separate cargo workspace — root `cargo build` never sees WebView.
- Build: `scripts/build-desktop.ts` (web flavor → `tauri build` → dmg/nsis/deb/AppImage).

### 4b. Desktop alternative — GPUI native (`apps/gpui`, Rust desktop-only only)

- Only when the stack decision says `frontend: gpui` (Q0 desktop-only + Rust
  backend). Separate cargo workspace binary (`apps/gpui` or `apps/desktop-gpui`),
  links the Rust core/executor crate in-process — same isolation rule as Tauri.
- No `frontendDist`, no web flavor, no web-ui reuse. Ships as a native binary, not
  a web bundle. Choosing this means the web-based surfaces (§2/§5/§6/§7) do not
  exist for this product — record that exclusion explicitly.
- Never scaffold alongside Tauri; one desktop frontend at a time.

## 5. VS Code — `apps/vscode` (or `integrations/vscode`)

- `package.json`: `main: ./dist/extension.js`, `contributes.commands/views`,
  `spacelens.cliPath` config (path to CLI on PATH). esbuild CJS, `vscode` external.
- `src/supervisor.ts`: attach-or-spawn staged `server.mjs` (fetch-injectable for tests).
  `src/extension.ts`: wires start/stop/probe/openWorkbench. Secrets (API keys) in
  `SecretStorage` ONLY — webview never sees them (`hasKey`, never the key).
- Webview reuses `packages/web-ui` (vite build into `webview/`), talks via
  `protocol.ts` bridge; sandboxed (`default-src 'none'`), model calls forwarded
  through the extension host. Package with `vsce package` → `.vsix`.

## 6. DSH plugin — `integrations/dsh` (or `apps/dsh`)

- `package.json` shape (space-lens `apps/dsh`, tokspeed):
  `exports { ".": "./dist/host.js", "./client": "./dist/client.js" }`,
  `dsh: { bundle: { patch: "./cordis.patch.yml" }, client: { platform: "web", immediately: true } }`.
- Host half (`dist/host.js`): assembles a REAL Manager + Hono inside the Harness
  process, mounts at `/<product>`, loopback/Origin guards. Client half
  (`dist/client.js`): registers panel + frames the prebuilt `web/` static.
- Build: `scripts/build-dsh-plugin.ts` (web `build-dsh` flavor → host/client bundle).
- Test: clean-session plugin load + panel discovery + shared-core unit tests reused.

## 7. Kunkun — `apps/kunkun-plugin` (or `integrations/kunkun`)

- `package.json` `kunkun` field (kkterminal real manifest):
  `identifier`, `commands[]` with `mode: "custom-view"`, `main: "/"`, `dist: "dist"`,
  `devMain: "http://127.0.0.1:5173"`, `window: {width,height}`, `permissions`
  (`storage`, `backend: { script: "$EXTENSION/dist/backend.js", runtime: "node",
  capabilities: { subprocess/nativeAddons } }`).
- `dist/` = SAME Svelte UI as web (copy-web-assets). `dist/backend.js` (tsdown) =
  the SAME `@<product>/node` engine hosted by a Kunkun backend process.
- Build: web build → copy-web-assets → tsdown backend → copy-pty-native.

## Surface decision table (transports filled per stack decision — no "TBD")

| Need | Surface | single-js | dual-js-rust | rust-core-napi |
|---|---|---|---|---|
| Scripting, CI, `npx` | CLI | `--direct` in-process | `--direct` (JS executor) | `--direct` (napi) or daemon |
| Human browser | Web | `fetch(http)` to daemon | `fetch(http)` to JS daemon | `fetch(http)` to daemon |
| SSH/no-browser | TUI | `fetch(http)` or `--direct` | same (JS side) | napi in-process or daemon |
| Offline installable | Tauri | `invoke` shim (same JS) | `invoke` → Rust executor | `invoke` → Rust engine |
| Editor-adjacent | VS Code | spawn CLI + webview bridge | spawn JS daemon + bridge | spawn napi CLI + bridge (never compile Rust in the extension) |
| Agent-harness panel | DSH | in-process host + framed web | in-process JS host + framed web | in-process JS host (napi where allowed) + framed web |
| Launcher (Kunkun) | Kunkun | backend.js + custom-view | backend.js (JS executor) + custom-view | backend.js + custom-view (HTTP daemon if host takes no natives) |
