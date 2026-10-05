# Project Structure and Monorepo Conventions

> Evidence sources (read firsthand on 2026-10-05): workspace manifests / scripts / design docs of xross-dev, refyard-native-desktop-ssh, refyard, kunkun, kunkun-services, uniview, model-jetty, space-lens, and ListenFlow. Companion samples: `../samples/ts-package-*.json`.

## 0. Core principles

Structure is not a convenience for organizing code; it is a way of **hardening architecture decisions into the file system**. The same pattern recurs everywhere: **directory names are architecture declarations, boundaries are enforced by scripts, versions are consolidated into a single manifest, and reuse is reclaimed via submodules/published packages**. The self-described "fundamental reason for preferring monorepos" — splitting core logic into a library in anticipation that other future projects will use it, then installing it via git submodule or a published package — has a complete, traceable evidence chain in the code (space-lens's engine extracted out to kuntu, kunkun-services's vendors/listenflow, kunkun's vendors/*).

But the monorepo is not dogma: single-crate projects (localsend-rs), single-file plugins (dsh-plugin-tokspeed), and pure content repos (garbage-tracking) all have no workspace. **If the scale is not there, do not adopt a monorepo; the moment a second host or a second consumer appears, adopt it immediately.**

## 1. Workspace choice: native solution per language, stacked for multi-stack

1. **TS repo = pnpm workspace + Turborepo**. pnpm-workspace.yaml declares `apps/*` + `packages/*` (plus `integrations/*`, `generated/*`, `examples/*` as needed); turbo.json defines only a minimal task set: `build` (with `^build`), `check`/`check-types` (with `^check`), and `dev` (`cache: false, persistent: true`).
2. **Rust repo = Cargo workspace**; TS and Rust coexist at the same repository root **without interfering with each other** — no cross-language unified tooling at all (no nx, no lerna, no bazel).
3. **Very large Rust repos split directories by architecture category**: `members = ["crates/*/*"]`, where the category is the path (contract/kernel/platform/runtime/service/adapter/app/composition/probe/testkit; xross-dev `Cargo.toml:3`).
4. **Structural isolation via a second workspace**: the desktop shell (Tauri/WebView) gets its own workspace so the root workspace cannot "see" the WebView dependencies.

Real code — xross-dev's three-in-one monorepo (`Cargo.toml:1-3`):

```toml
[workspace]
resolver = "3"
members = ["crates/*/*"]
```

refyard-native-desktop-ssh uses a separate workspace for structural isolation (`apps/desktop/src-tauri/Cargo.toml:1-11`, sample `../samples/rust-workspace-isolation.toml`):

```toml
# The desktop shell is its own workspace, and that is the point of this file.
#
# `cargo build` at the repository root must never need a WebView: ... Keeping the desktop
# crate in a separate workspace makes that structural — the root workspace cannot see
# these dependencies, so nothing in `crates/` can reach them by accident.
[workspace]
```

Meanwhile the root workspace uses `default-members` to include only headless crates, so a bare `cargo build` never pulls in WebView.

The turbo task graph stays minimal (`refyard-native-desktop-ssh/turbo.json:4-18`):

```json
"tasks": {
  "build": {
    "dependsOn": ["^build"],
    "inputs": ["$TURBO_DEFAULT$", ".env*"],
    "outputs": ["dist/**", "build/**", ".svelte-kit/**"]
  },
  "check": { "dependsOn": ["^check"], "outputs": [] },
  "dev": { "cache": false, "persistent": true }
}
```

- ✅ Multi-stack projects: the root carries `pnpm-workspace.yaml` + `Cargo.toml [workspace]` + `turbo.json` side by side, with each of the three manifests governing its own language layer; cross-language coordination is chained via a root-level `just` file (xross-dev) or the root `package.json` scripts.
- ❌ Introducing nx/bazel/lerna-style cross-language orchestration for the sake of "uniformity" — not one of his repos has it.
- ❌ Wrapping a single-crate library (localsend-rs) in a workspace; a monorepo is introduced only when a second host/consumer appears.

## 2. Directory layout: fixed naming, consistent across repos

| Directory | Contents | Evidence |
|---|---|---|
| `apps/*` | Deliverable shells (web/cli/desktop/tui/server/vscode...), doing only composition and host adaptation | refyard 4, kunkun 11, xross-dev 16 |
| `packages/*` | Reusable TS libraries, named `@scope/name` where scope = product name | `@refyard/*`, `@kunkunsh/*`, `@xross/*`, `@services/*` |
| `crates/*` | Rust libraries + bins, named with a product prefix | `xross-*`, `refyard-*`, `kuntu-*` |
| `vendors/*` | External/self-owned open-source dependencies as git submodules | xross-dev 8, kunkun 5, kunkun-services 2 |
| `integrations/*` | Adapter layers that embed into other host products | refyard's `integrations/{kunkun,xross}`, model-jetty's `integrations/{dsh,kunkun}` |
| `generated/*` | Generated code (protobuf), never hand-edited | xross-dev `generated/*` |
| `tests/` | Cross-package tests centralized at the repo root, subdivided by type | refyard `tests/{contract,core,node,integration,portable,graph,e2e,pack,security,compat,fixtures}` |

Crates get a second-level directory split by **architecture category** once they grow large enough (unique to xross-dev: 37 contract crates plus kernel/platform/runtime/service/adapter/app/composition/probe/testkit). The value of category directories shows up in §3's gates: directory location determines the dependency whitelist.

- ✅ Adding a host = adding one directory under `apps/` that only imports packages, never copies logic (refyard's single git-core is consumed by four hosts: web/cli/desktop/vscode).
- ✅ Embedding into someone else's product (Kunkun plugins, DSH plugins) → `integrations/`; neither an app nor a library, it is a third identity.
- ❌ Putting domain logic into `apps/` — refyard's AGENTS.md:161-169 explicitly lists each directory's single responsibility (`apps/cli/: argv parsing, doctor, open/serve lifecycle`).
- ❌ Hand-writing wire types instead of creating a contract package — every product has a single contracts package (`packages/git-contract`, `packages/listenflow-contracts`, `@space-lens/contract`, xross's 37 contract crates).

## 3. The library + app split: core logic sinks down, shells only compose, boundaries machine-enforced

This is the core self-stated preference, and the one with the richest code evidence. The split is not "best effort" — it is **enforced by scripts/rules**:

**(a) The TS portable layer forbids host APIs — a homegrown boundary script**. `refyard-native-desktop-ssh/scripts/check-boundaries.ts:1-43`:

```ts
/**
 * `pnpm check:boundaries` — enforce the portable-core claim.
 *
 * Fails when a portable package imports a host module, touches a host global or
 * host read, hides a dependency behind a dynamic import, leaves its own `src` via
 * a relative import, or ships a tsconfig that would let a host API type-check.
 *
 * Exits non-zero with `file:line:column` so an editor can jump to the violation.
 */
```

Tests/scripts must import by package name; relative imports crossing package boundaries are forbidden.

**(b) A homegrown ESLint rule**. kunkun's `eslint-rules/enforce-runtime-layering.mjs` (modeled on VS Code's code-layering): "portable → files under packages/*. MUST NOT import the bare `electron` module...". The rule decides by **resolved filesystem paths** rather than text matching, and even the known gap (`.svelte` not covered) is written into the rule's header comment.

**(c) Rust category dependency gates**. xross-dev's `scripts/check-boundaries.ts:24-33`:

```ts
const CATEGORIES: Record<string, readonly string[]> = {
  contract: ['contract'],
  kernel: ['contract', 'kernel'],
  runtime: ['contract', 'kernel'],
  service: ['contract', 'platform'],
  probe: ['contract'],
  platform: ['contract'],
  adapter: ['contract', 'service'],
```

It reads `cargo metadata` instead of grepping manifests, so "a crate cannot escape the rules by relocating". There is also `FROZEN_KERNEL` pinning the fabric at a single point, and `EXTERNAL_OWNERS` fencing loro/notify/iroh/quinn into exactly one category — meaning an external dependency may be **imported by only one category across the whole repo**; services can only consume traits and never see `loro::` types.

### Rules

1. **Any logic a second host/second project might use gets extracted into a library**; libraries are kept host-free (banning `node:*`/DOM/Buffer/electron/tauri), with host capabilities injected through Port interfaces.
2. **The split declaration goes into AGENTS.md's directory responsibility table, paired with an executable check script**; "enforced rather than encouraged".
3. **On the Rust side, linking the same service crate into a daemon, a standalone bin, or a mobile app is a build decision, not a rewrite** (xross-service-host's positioning).
4. **Single-instance external dependencies are fenced into exactly one category** (EXTERNAL_OWNERS), keeping backend choices swappable.

- ✅ kunkun's single `@kunkunsh/core` is validated by 5 hosts: desktop (Electron), desktop-tauri, cli, web, light-shell.
- ❌ `import { Buffer } from "node:buffer"` inside a portable package — check-boundaries fails outright.
- ❌ Writing boundary rules only in AGENTS.md without a script — "the kind of wish older repos could only express in comments becomes a gate here".

## 4. Internal dependencies and version management

1. **Internal packages depend on each other exclusively via `workspace:*`**, declared in each package's own package.json (rather than as implicit phantom dependencies).
2. **Internal package exports point straight at TS source — zero-build direct wiring**: `"exports": { ".": "./src/index.ts", "./*": "./src/*.ts" }`. Large packages list deep paths one by one (kunkun core lists ~50 subpath exports, `packages/core/package.json:7-57`) to avoid barrels dragging in side effects.
3. **Versions live in one place**: pnpm `catalog:` (or a named catalog) collects all third-party versions while package manifests write only names; Rust uses `[workspace.dependencies]` to pin the path of every internal crate and the version of every external dependency at the root.
4. **Upgrades must appear in the task's own commit** — refyard pnpm-workspace.yaml:12-14 verbatim: "Every dependency version lives here so a package.json can only ask for a name. ... bumping a version means editing this file, which shows up in the task's own commit."
5. **Single-instance dependencies must be pinned to one global copy**: libraries sensitive to module-level state or symbol compatibility, such as solid-js/react/svelte/ai-sdk, break silently with two copies (catalog pinning + `overrides` + an alignment check script; kunkun's `check-ai-sdk-version-alignment.ts`: "the two copies' `instanceof` fails at runtime").

Real code — internal package source-direct wiring (`refyard-native-desktop-ssh/packages/git-core/package.json:2-15`, sample `../samples/ts-package-internal.json`):

```json
{
  "name": "@refyard/git-core",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "exports": { ".": "./src/index.ts", "./*": "./src/*.ts" },
  "devDependencies": { "@refyard/git-contract": "workspace:*" }
}
```

Rust version consolidation (xross-dev pins crypto primitives at workspace level, `Cargo.toml:168-171`):

```toml
# The vault's crypto suite, fixed by ADR 0035 §1: SHA-256, Ed25519
# `verify_strict`, XChaCha20-Poly1305, HPKE base X25519-HKDF-SHA256. Pinned here
# rather than in the vault crates so the codec and the service cannot drift onto
# two versions of one primitive and then disagree about bytes.
```

A named catalog solves "two compiler versions coexisting" — `refyard-native-desktop-ssh/pnpm-workspace.yaml:57-64`: the main repo uses TS 7 (native port), while `svelte-check` needs the compiler API and alone uses TS 6 via `catalog:svelte`, the comment ending in "Nothing else may use it".

- ✅ `"zod": "catalog:"` in a package — the version exists only in pnpm-workspace.yaml, in one place.
- ✅ Crates inherit via `version.workspace = true` / `edition.workspace = true`.
- ❌ Writing literal versions like `"zod": "^4.6.5"` in package manifests; scattered versions mean silent drift to latest.
- ❌ Two copies of `solid-js`/`@ai-sdk/provider` entering the dependency tree.

## 5. Internal source-direct wiring vs external publishing: one clear dividing line

Self-stated: "packages that are internal monorepo dependencies can simply export the TypeScript source files directly... only libraries published to npm for others are compiled with a tool like tsdown." The code confirms it, in three shapes (details in `typescript.md` §9; samples `../samples/ts-package-*.json`):

### Shape A: purely internal packages — direct source wiring, no build script

`private: true`, `version: 0.0.0`, and a scripts section containing only `check: tsc --noEmit`. xross's `@xross/sdk` is the same: `"main": "src/index.ts"`.

### Shape B: consumed inside the workspace and also published to npm — dual-condition exports

`uniview/packages/protocol/package.json:8-18`:

```json
"exports": {
  ".": {
    "uniview-source": "./src/index.ts",
    "default": "./dist/index.mjs"
  }
}
```

A custom `uniview-source` export condition: consumers inside the workspace read the TS source directly, while npm installers get dist.

### Shape C: hybrid — runtime from dist, types from src

kunkun-services's sdk (`design/CROSS_REPO_DEPENDENCY_ARCHITECTURE.md:285-299`): `"import": "./dist/server/index.js", "types": "./src/server/index.ts"` — published Node ESM consumers never execute .ts, while type-checking inside the workspace does not require a build before every code change.

### The rigor of publishing

Published packages build with `tsdown && node scripts/assert-public-dist.ts` — asserting that dist actually exists before publishing; `files` contains only dist + README. uniview treats npm publishing as a distributed system: immutable run directories, SHA-256-verified tarballs, and tests for the publish script itself.

- ✅ Editing an internal package's code → downstream workspace packages see it instantly, with no build step and no watch orchestration.
- ✅ Needing to publish → bring in tsdown + the `assert-public-dist` assertion + a `pack:dry` smoke test.
- ❌ Giving dist build pipelines to packages used only inside the monorepo — pure added build time per change cycle. (Exception: logic-foundry's internal packages go through dist builds — the sole counterexample across all primary repos; do not imitate it.)

## 6. The endpoint of reuse: git submodule reclamation and one-way cross-repo dependencies

The self-stated "we can install it later via git submodule or a published package" is not an aspiration — it is an action completed three times:

### (a) Engine extraction + submodule reclamation (consumed via rename)

space-lens's scanning engine was extracted in 2026-09 into the standalone kuntu repo and vendored back as `vendors/kuntu`. On the consuming side, `space-lens/packages/node/Cargo.toml:13-17`:

```toml
[dependencies]
napi        = "3.0.0"
napi-derive = "3.0.0"
space-lens = { package = "kuntu-scan", path = "../../vendors/kuntu/crates/kuntu-scan" }
```

The `package =` rename confines the upstream name to one spot in the dependency declaration, so this repo's code is unaffected by upstream renames.

### (b) A closed-source repo consuming an open-source submodule, with the direction strictly one-way

kunkun-services brings the entire open-source Kunkun repo into its workspace as the `vendors/kunkun` submodule; README.md:63: "Direction is strictly one-way: kunkun-services imports from vendors/kunkun, never the reverse." Public contracts (DTOs/schemas/typed clients) live on the open-source side and private implementations on the closed-source side, and the design doc hardens the forbidden direction with a mermaid diagram. **"What both sides need is written once, in the open-source repo"** is that document's explicit owner directive.

### (c) Rules for wiring vendors into the workspace

- **Cargo**: vendored submodules must be `exclude`d from the root workspace, and **named individually** (exclude does not support globs; `vendors/*` is silently accepted and matches nothing — see the xross-dev `Cargo.toml:11-13` comment). Where patching is needed, use `[patch.crates-io]` with the expiry condition spelled out.
- **pnpm**: packages inside submodules are listed individually in `packages:` rather than globbing whole directories, with a comment explaining why only the dependency closure is taken (xross-dev `pnpm-workspace.yaml:6-27`: 19 packages taking only the closure of `@uniview/tui-solid`, avoiding pulling in an unused React runtime and tests). **Nested monorepos** (kkterminal/refyard/excalidraw) have their roots excluded with `!` and the needed members named individually, preventing turbo from reading foreign root configs (kunkun `pnpm-workspace.yaml:6-46`).
- The submodule's catalog must be mirrored into the host workspace, or `pnpm install` fails with `ERR_PNPM_CATALOG_ENTRY_NOT_FOUND_FOR_SPEC` (kunkun-services `pnpm-workspace.yaml:34-38` comment).

- ✅ Foreseeing that a second project will use it → extract the library now; when reuse day actually arrives → extract into a standalone repo + bring it back as a submodule + isolate the name with a rename.
- ✅ For vendored dependencies, do the exclude/individual naming on your own repo's side (committable changes) rather than editing the submodule's manifest.
- ❌ The open-source submodule importing closed-source repo packages in the reverse direction — explicitly forbidden by the design doc, with verification commands attached.
- ❌ `exclude = ["vendors/*"]` — the glob silently fails; it looks like it works but actually excludes nothing.

## 7. Known exceptions and tensions (self-description vs code facts)

1. **"pnpm workspace first" — space-lens uses yarn**. `space-lens/package.json:61`: `"packageManager": "yarn@4.14.1"`, no pnpm-lock. It is the only multi-package non-pnpm repo among the 17 projects; the reason was not determined. polymarket-quant, for its part, has no workspace tooling at all. **Conclusion: pnpm is the overwhelming mainstream (10+ repos), but not 100%.**
2. **"Internal packages export TS source directly, no compilation needed" — three exceptions/evolved shapes**: (a) logic-foundry's internal libraries go through dist builds after all; (b) kunkun-services's sdk is a hybrid of import→dist / types→src; (c) uniview uses a custom condition to serve both kinds of consumers. **Source-direct remains the default, but packages that "are consumed internally and also published" evolve into the hybrid shape.**
3. **The "Rust build environment is heavy" concern does not match the actual investment (framed as a tension, not a contradiction)**: xross-dev has ~436k lines of Rust, a pinned toolchain + dual musl targets + a cargo-zigbuild cross-compilation matrix. "Heavy" has not stopped him from using Rust heavily where P2P/crypto/performance is needed. Language choice actually follows "performance/systems programming → Rust; glue CLIs → Go; everything else → TS".

## 8. Operating sequence (structural decisions when adding something new)

1. First ask: **is this a new host, a new domain library, or an adapter for another project?** → corresponding respectively to `apps/`, `packages|crates`, `integrations/`.
2. Before any core logic enters a library, ask: **does it import host APIs?** If yes → move it into a host-layer package and inject it via Port interfaces.
3. New package: `@product-name/package-name` + `private: true` + exports pointing at src + dependencies written as `workspace:*` + third-party versions into the catalog. New crate: `product-prefix-name` + `xxx.workspace = true` inheritance + internal path dependencies named in the root `[workspace.dependencies]`.
4. Changing a dependency version = editing pnpm-workspace.yaml / the root Cargo.toml, so it shows up in this task's own commit.
5. Write the directory responsibility table into AGENTS.md and pair it with a check script (the kind that can output file:line:column) — **an architecture declaration without a gate does not count**.
6. Foreseeing a second consumer → split now; when extracting: standalone repo + `vendors/` submodule + Cargo exclude naming each one / pnpm including members one by one + rename consumption + one-way dependencies.
