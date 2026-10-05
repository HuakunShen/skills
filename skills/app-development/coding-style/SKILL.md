---
name: coding-style
description: >-
  Huakun Shen's personal coding style and engineering standards, distilled from his real
  repositories (kunkun, refyard, xross-dev, CrossCopy, ListenFlow, space-lens, uniview,
  model-jetty, logic-foundry, polymarket-quant, localsend-rs, kunkun-services, ...).
  USE THIS SKILL whenever you write, review, refactor, or scaffold ANY code for this
  user in ANY language: choosing between TypeScript / Rust / Go, creating or extending
  a monorepo (pnpm workspace, cargo workspace), splitting library vs app packages,
  adding dependencies, designing types / errors / runtime boundaries, publishing
  packages, writing commits or repo rules, or judging a diff against his standards.
  Core doctrine: modularity + type safety are the top priority in every language;
  architecture impact is assessed before any new code lands; core logic goes into
  libraries that are source-linked inside the workspace and only built for publish;
  architectural rules are machine-enforced, never prose. Trigger words: type safety,
  modularity, monorepo, workspace, splitting libraries, library + app, language
  selection, new projects, adding dependencies, tsdown, strict tsconfig,
  discriminated union, error codes, closed error codes, thiserror, zod, valibot,
  code review standards, coding style.
---

# Coding Style — Huakun's Personal Coding Standards

This skill is the personal coding style and engineering standards of Huakun (Huakun Shen), distilled from forensic analysis of his 17+ real repositories (analysis date 2026-10-05; every citation is annotated `repo:file:line`, and `samples/` contains verbatim excerpts of real code). **Your role (AI): write, review, and scaffold code for him according to these standards; when uncertain, defer to his real repositories, not to generic best practices.**

This style in one sentence: **Types are not documentation; they are machine-enforced contracts. Structure is not a convenience for organizing code; it is a way of solidifying architectural decisions into the filesystem.** Type discipline is grep-verifiable (handwritten code contains 0 instances of `any`/`as unknown as`/`@ts-ignore`), and architectural boundaries are enforced by scripts and custom ESLint rules (enforced rather than encouraged).

## Core Principles (Six, in Priority Order)

1. **Modularity + type safety is the top priority** — in every language. In TS: `strict` is only the starting point (always layered with `noUncheckedIndexedAccess` and the like), types are derived from values (`as const` + `typeof`), external input passes a schema at the boundary, errors are a closed code table; in Rust: newtype IDs, fail-closed enums, `#![forbid(unsafe_code)]`; in Go: typed string constants + JSON tags; even plain JS requires schema-validated config + handwritten narrowing. **A language without a type system is not a license to abandon type discipline.**
2. **Architecture first**: every time something is added to a project, assess its impact on the overall structure before writing code. Before adding, ask three questions: Is this a new host (`apps/`), a new domain library (`packages|crates`), or an adaptation for someone else's project (`integrations/`)? Does the core logic import host APIs (if yes → move it to the host layer, injected via a Port)? Might a second project need it (if yes → split it into a library now)?
3. **Split complex projects into library + app**: whenever a future project might reuse something, split the core logic into a library; the shell (app) only does composition and host adaptation. Libraries must be host-free (no `node:*`/DOM/electron/tauri); host capabilities are injected via Ports/traits. The endgame for future reuse is recovery as a git submodule or publishing to a registry — this is the fundamental reason for preferring monorepos.
4. **monorepo/workspace first**: use each language's native solution — TS uses pnpm workspace (+ Turborepo), Rust uses cargo workspace; no cross-language unified orchestration (no nx/lerna/bazel anywhere). But a monorepo is not dogma: if the scale does not warrant one (single-crate library, single-file plugin, pure content repo), skip it; the moment a second host or second consumer appears, adopt one immediately.
5. **Language selection matrix**: in the AI era, **TypeScript** is the first choice (nearly all agent tooling is written in TS); among compiled languages, prefer **Rust** (core engines/CLIs/FFI; the build environment is heavy → optimize compile time at the crate-splitting level, which is no reason to avoid it); for something lighter and faster (cross-compiled single binary deploying long-running processes) use **Go** — but note Go is low-frequency and scenario-driven, not a default option; do not proactively suggest it unless the user names it.
6. **Internal source links directly; build only for publishing**: for packages consumed by monorepo-internal dependencies, `exports` points directly at TypeScript source files (`"./src/index.ts"`); other workspace packages import directly, zero build. Only libraries published externally to npm are compiled with tsdown (library), and self-contained CLIs are bundled with esbuild. Configuring a build for a package consumed only internally is an anti-pattern.

## Language Selection Cheat Sheet

| Scenario | Choice | Rationale |
|---|---|---|
| Default, AI tooling, glue code, full-stack | TypeScript | Self-described "first choice in the AI era is TS"; 10+ primary repositories |
| Performance/systems programming/P2P/crypto/core engines | Rust | Self-described "for compiled languages, prefer Rust (but the build environment is heavy)"; compile cost is managed (service crates compile in seconds) rather than avoided |
| Cross-compiled single binary, long-running collection processes scp'd to servers | Go | Only proven case: polymarket-quant; narrow trigger conditions, do not proactively recommend |
| Build scripts/validation scripts | TypeScript run with bun | 21/22 of refyard `scripts/` are .ts; no new bare .sh |
| Restricted dialects (ArkTS), plain JS plugins | Do not lower the bar; restore discipline with patterns | Handwritten typed JSON parsers/decoders, schema-validated config |

## Per-Language Cheat Sheet (read docs/ for details)

**TypeScript** (`docs/typescript.md`):
- On top of `strict`, always layer `noUncheckedIndexedAccess` (commonly plus `exactOptionalPropertyTypes`/`verbatimModuleSyntax`); `noEmit: true`, with type checking separated from building.
- Zero escape hatches: handwritten code forbids `any`/`as unknown as`/`@ts-ignore` (grep-verified: 0 occurrences); when a type errors → fix the modeling, do not add assertions.
- Literals are written exactly once: `as const` values + `typeof`-derived unions; when two tables must agree, write `Equal<A,B>` + `Expect` compile-time assertions; do not use `enum`.
- Polymorphic data is always a discriminated union (`kind`/`type` literal); mutually exclusive optional fields use `?: never`.
- All external input (HTTP/SSE/IPC/disk) passes zod/valibot at the boundary — requests use `strictObject`, responses may use `.loose()`; DTO types are derived with `z.infer`; one schema library per repository, never mixed.
- Errors: a closed code table (`as const`) + code-carrying Error classes + `isXxx` shape guards; consumers branch on code, never on message text; a given code always maps to the same HTTP status (exhaustive Record).
- Every source file starts with a module header comment (responsibility + architectural position; only constraints code cannot express).
- Three toolchain forms: internal packages point `exports` at src (no build) / published packages produce dist with tsdown / dual-condition exports (`uniview-source`); CLI artifacts are esbuild-bundled into a single zero-dependency file.

**Rust** (`docs/rust.md`):
- cargo workspace by default; dependencies are centralized in `[workspace.dependencies]` with child crates using `.workspace = true`; directory categories double as dependency whitelists, enforced by a check script that reads `cargo metadata` as a CI gate.
- Structural isolation uses a second workspace (desktop shells/Tauri live separately; the root workspace's `default-members` contains only headless crates).
- Errors: dual track — thiserror (libraries; add Serialize/Deserialize + `#[non_exhaustive]` when enums go on the wire) / anyhow (composition-root CLIs); every `#[error]` is a complete sentence; catch-all unknown variants are forbidden.
- Newtype IDs validate at construction; state machines transition via `Result<Self>`; permissions become types, not booleans; in-process stringly-typed contracts are forbidden (`serde_json::Value` is allowed only at real serialization boundaries).
- Traits are small and focused (for injection and seams, not OOP); `#![forbid(unsafe_code)]` by default, with FFI boundaries the only exemption zone, and every unsafe fn carries `# Safety`.
- rust-toolchain pinned exactly (with incident comments), clippy `-D warnings`, rustfmt defaults; repositories without CI encode architectural rules as hygiene tests.

**Go and others** (`docs/go-and-others.md`):
- Go: `pkg/<domain>` (libraries with no persistence opinions) + `apps/<name>/{cmd,internal}` (composition and persistence); typed string constants + JSON tags (no iota); errors via `fmt.Errorf("pkg: do thing: %w", err)` with inputs quoted as `%q`; config resolution follows flag > env > default through a unified helper; lenient degradation on hot paths is concentrated into named functions (only the boundary layer is strict).
- Python: `typing.Literal` discriminators + pandera with lazy imports; full function annotations.
- ArkTS: typed even without `any` — handwritten JSON trees + fail-closed decoders; import the shared TS contract directly instead of hand-writing a fourth copy.
- Kotlin/cross-language: when the same logic is implemented in multiple languages, pure functions + injection + one golden fixture (with recorded hash) adjudicate all languages.
- Shell: no bare shell; logic-bearing scripts are TypeScript run with bun.

**Project structure** (`docs/structure.md`):
- Fixed directory naming: `apps/*` (shells) / `packages/*` (TS libraries, `@product/pkg`) / `crates/*` (Rust, product prefix) / `vendors/*` (submodules) / `integrations/*` (embedded into other parties' hosts) / `tests/` (cross-package tests).
- Internal dependencies are always `workspace:*`; third-party versions go into pnpm `catalog:` / the root `[workspace.dependencies]`, and package manifests list only names; upgrades must appear in the task's own commit.
- Boundaries are machine-enforced: check-boundaries scripts (outputting `file:line:column`), custom ESLint rules, cargo metadata gates — **an architectural claim without a gate does not count**.
- Vendoring: Cargo `exclude` names paths one by one (no glob support — globs silently fail), `[patch.crates-io]` with documented invalidation conditions; pnpm submodules are brought in member by member + mirrored in catalog; cross-repo dependencies are one-way only, reverse dependencies forbidden.

**Toolchain and AI collaboration** (`docs/ai-tooling.md`):
- Evidence honesty is the supreme iron rule: never claim a verification passed that was not run; report NOT RUN as NOT RUN; every number is traceable.
- Commits: `type(scope): lowercase complete English sentence` (states user-visible behavior, not imperative), scope = package/app, one logical change per commit, no Co-Authored-By; no push, no publish, no deploy.
- Rules must be machine-enforced; models are routed by cost tier; anything learned gets written back in the same round (AGENTS.md/handbook/ADR/journal/skill).

## Red Lines (instant veto in review)

- ❌ `any` / `as unknown as` / `@ts-ignore` / eslint-disable used to mask type errors
- ❌ The same set of literals hand-written in two places (one copy in a type, one in z.enum)
- ❌ Consuming external input in a handler via `body as CreateRequest`
- ❌ `throw new Error("...")` + callers branching on the message string
- ❌ Logic written into `apps/` shells; portable packages importing host APIs
- ❌ Configuring builds for internal packages; in-workspace imports going through dist or cross-package relative paths reaching into other packages
- ❌ Inlining dependency versions in child crates; `exclude = ["vendors/*"]` (globs silently fail)
- ❌ Architectural rules written only in comments with no gate attached
- ❌ Claiming tests pass without real tool output

## What to Read When (progressive disclosure)

| Scenario | Read first |
|---|---|
| Writing/reviewing any TS code, tsconfig, publishing | `docs/typescript.md` |
| Writing/reviewing any Rust code, Cargo.toml, FFI | `docs/rust.md` |
| Writing Go/Python/ArkTS/Kotlin/plain JS/scripts | `docs/go-and-others.md` |
| Creating new projects, adding packages/crates, touching workspace/dependencies/vendors | `docs/structure.md` |
| Commits, CI, AGENTS.md, agent collaboration rules | `docs/ai-tooling.md` |
| Needing to see what real code looks like | `samples/` (all annotated with provenance) |

Every file in `samples/` is a verbatim positive example excerpted from a real repository (the file header notes the repo/file/line numbers); there are also a few constructed counterexamples marked `❌` (explicitly labeled as non-repository code). Read the corresponding sample before writing code, then start.

## Known Exceptions (do not treat these repositories as the template to correct against)

- logic-foundry builds internal packages to dist with tsc — the only exception to "internal means source" among all primary repositories (an early project).
- space-lens uses yarn (the only multi-package repo not on pnpm); uniview's AGENTS.md claims tabs but the code follows prettier defaults (semicolons + spaces) — **the code is authoritative**.
- Recent kunkun-services commits carry a `Co-Authored-By: GLM` trailer — the target state remains no attribution; rules are written and applied assuming no attribution.
- xross-interop-lab's contract crates use dense Chinese comments (following the design docs' language); comments in all other repositories are entirely English — product/library code comments are always English.
