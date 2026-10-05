# TypeScript Conventions

> Evidence sources (personally read on 2026-10-05): the tsconfig / package.json / source code of 8 repos under `/Volumes/Portable2TB/ExtDev/` — refyard, kunkun, kunkun-services, model-jetty, logic-foundry, uniview, ListenFlow, and space-lens. Companion samples: `../samples/tsconfig.base.json`, `../samples/ts-*.ts`, `../samples/ts-package-*.json`.

TypeScript is Huakun's default language (TS is the first choice in the AI era; almost all agent tooling is written in TS). Core creed: **types are not documentation, they are machine-enforced contracts** — types are derived from a single source of values, external input passes schema validation at the boundary, errors branch on closed code sets, and architectural constraints are enforced by scripts and custom ESLint rules rather than by code review.

## 1. Compiler Baseline: strict Is Only the Starting Point

Every repo's tsconfig sets `strict: true`, and it never appears alone — a set of extra flags is always layered on top. Baseline template (refyard `tsconfig.base.json`, the single repo-wide base that all packages extend; sample `../samples/tsconfig.base.json`):

```jsonc
"strict": true,
"noUncheckedIndexedAccess": true,
"noImplicitOverride": true,
"noFallthroughCasesInSwitch": true,
"noUnusedLocals": true,
"noUnusedParameters": true,
"verbatimModuleSyntax": true,
"isolatedModules": true
```

- model-jetty (`tsconfig.json:7-11`) adds `exactOptionalPropertyTypes` on top of this, with target ES2024 + NodeNext; kunkun core (`packages/core/tsconfig.json:11-18`) likewise adds `exactOptionalPropertyTypes`; externally published packages use the strictest community preset: the kunkun sdk is `"extends": "@tsconfig/strictest/tsconfig.json"`.
- Common conventions: `noEmit: true` (type checking is separated from building; builds are handed to tsdown/esbuild), `moduleResolution: "bundler"` (or NodeNext), target ES2022+; the core library (refyard) adds `"types": []` — no host global types are loaded at all, locking portability in at the tsconfig level.

**Zero escape hatch discipline** (verified by grep: 0 hits for `@ts-(ignore|expect-error)|as unknown as|: any\b` across all hand-written source in refyard packages/apps; the only 4 hits live in generated code `paraglide/runtime.*`):

- ✅ New package: extend the repo's base tsconfig; for a new base, copy the flag list above verbatim.
- ✅ Hitting a type error: fix the type modeling (discriminated unions, generic narrowing, type guards), not add `as`.
- ❌ `as unknown as X`, `@ts-ignore`, or eslint-disable to paper over type errors — these pass neither review nor the in-house gates.
- ❌ Shipping bare `"strict": true` — every repo layers at least `noUncheckedIndexedAccess` on top.

The only legal form when an assertion is truly needed: `unknown` is first checked with `in`, then narrowed (kunkun-services `errors.ts:110`: `"code" in error` followed by `(error as { code: unknown }).code`).

## 2. Types Derived from Values: Single Source of Truth

Literals are written exactly once (inside `as const` values), and types are derived with `typeof`; cross-table consistency is locked down with exhaustive `Record`s or type-level assertions, so "changing A and forgetting B" becomes a compile error outright. This is the most distinctive TS technique here.

### 2a. `as const` Lists → Derived Unions

```ts
// ListenFlow packages/listenflow-core/src/codes.ts:162-164 (comment verbatim: union derived from the list, so they cannot disagree)
] as const;
export type ListenFlowInputCode = (typeof LISTENFLOW_INPUT_CODES)[number];
```

The object form has the same shape (kunkun-services `apps/api/src/errors.ts:9-50`): `export const ErrorCodes = { ... } as const;` → `export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];`

### 2b. Exhaustive Record: Adding a Code Without a Status Fails to Compile

```ts
// ListenFlow packages/listenflow-core/src/errors.ts:42
const STATUS_BY_CODE: Record<ListenFlowInputCode, ListenFlowInputStatus> = {
  platform_config_invalid: 400,
  platform_config_conflict: 409,
  capacity_paused: 503,  // the pause is temporary and operator-lifted
```

### 2c. Type-Level Proofs (Equal/Expect): Schema Table and Operation List Match Key-for-Key

```ts
// refyard packages/git-contract/src/operations.ts:685-701 (sample ../samples/ts-derived-types.ts)
type Equal<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
type Expect<T extends true> = T;
export type _SchemasMatchTargetList = Expect<Equal<keyof typeof OPERATION_SCHEMAS, MutationKind>>;
export type _MutationCount = Expect<Equal<(typeof OPERATION_TARGET_LIST)["length"], 45>>;
```

The companion mapped types are complete (`operations.ts:652-683`): `type MutationKind = (typeof OPERATION_TARGET_LIST)[number][0]`, `type OperationFor<K extends MutationKind> = z.infer<(typeof OPERATION_SCHEMAS)[K]>`, and `type MutationOperation = { [K in MutationKind]: OperationFor<K> }[MutationKind]`.

- ✅ Enums / error codes / schema tables: write the `as const` value first, derive all types with `typeof`.
- ✅ Wherever two tables must stay consistent, write an `Equal<A, B>` + `Expect` compile-time assertion.
- ❌ Hand-copying both sides — `type Kind = "a" | "b"` in one place and `z.enum(["a", "b"])` in another.
- ❌ Using `enum` (the repos almost exclusively use literal unions + `as const`; no `enum` declarations were seen).

## 3. Discriminated Unions Are the Default Modeling Technique

All polymorphic data — events, operations, state machines, RPC messages — is modeled as a union with a literal discriminant field (`kind`/`type`). Two flavors:

**Schema version (zod/valibot)** — the discriminant field is a literal, and the common envelope is factored into an `as const` object that gets spread in (sample `../samples/ts-discriminated-union.ts`):

```ts
// kunkun packages/ai-protocol/src/events.ts:26-34, 61
const envelope = { protocolVersion: ProtocolVersionV1Schema, requestId: ..., sequence: ... } as const;
export const AiStreamEventV1Schema = v.variant("type", [
  v.strictObject({ ...envelope, type: v.literal("start") }),
  v.strictObject({ ...envelope, type: v.literal("text-delta"), delta: v.string() }),
]);
export type AiStreamEventV1 = Readonly<v.InferOutput<typeof AiStreamEventV1Schema>>;

// refyard packages/git-contract/src/operations.ts:560-570 (confirmation semantics for destructive operations)
abortRebase: z.strictObject({
  kind: z.literal("abortRebase"),
  confirmed: confirmedField,   // const confirmedField = z.literal(true)
})
```

**Pure-type version (zero-dependency repos)** — mutually exclusive fields are enforced with `?: never`:

```ts
// logic-foundry packages/document/src/model.ts:6-9
export interface PrimitiveComponent extends ComponentBase { kind: PrimitiveGateKind; definitionId?: never; definitionVersion?: never }
export interface ModuleInstance extends ComponentBase { kind: 'MODULE'; definitionId: string; definitionVersion: number }
export type Component = PrimitiveComponent | ModuleInstance
```

When `Omit` over a union would collapse into an intersection, a hand-rolled `DistributiveOmit` is written with the reason documented (kunkun `events.ts:63-73`, comment verbatim: "A bare `Omit<Union, K>` collapses to the intersection of the members' keys, which would erase `delta`, `error`, `usage`...").

- ✅ New message/event/operation types: one literal discriminant field + strictObject members; common envelope factored out as an `as const` spread.
- ✅ Optional mutually exclusive fields use negative fields like `definitionId?: never` (when there is no schema).
- ❌ Boolean flag combinations (`isStart && isDelta`) or a grab-bag optional interface to express mutually exclusive shapes.

## 4. Runtime Boundaries: All External Input Goes Through a Schema

Compile-time types only cover what stays in-process; any data crossing process/network/disk boundaries (HTTP bodies, SSE, IPC, plugin messages, JSON read in by CLIs) must be validated at the boundary with zod/valibot, with DTO types inferred backwards via `z.infer`/`v.InferOutput` — `z.infer` appears 118 times across the refyard repo (measured).

**Directionality**: requests (input we must parse) use `strictObject` so unknown fields are rejected; responses (the peer may evolve) can be loose to preserve forward compatibility:

```ts
// refyard packages/git-client/src/client.ts:66-67
const clientHealthResponseSchema = healthResponseSchema.loose();
const clientCapabilitiesResponseSchema = capabilitiesResponseSchema.loose();
// ListenFlow packages/listenflow-contracts/src/schemas.ts:7 — the file header comment states the same policy
```

**One schema definition, three consumers** (the header of kunkun-services `apps/api/src/routes/listenflow/schemas.ts:1-27` spells out the triple duty): (1) `validator(...)` attaches to Hono routes for upfront 400 validation and types `c.req.valid()`; (2) `resolver(...)` feeds the OpenAPI document; (3) a type-level drift guard at the bottom of the file asserts the schema covers every field the service returns — "A column added to `listenflow_items` that reaches a response now fails the build here rather than going undocumented for a year". Existing enums are imported from Drizzle `enumValues` rather than re-copied ("status cannot mean one set of strings in the database and another here"). Row types are schema-derived too: `type ItemRow = typeof listenflowItems.$inferSelect`.

**Numeric bounds go into the schema, not the docs**: every field of the wire schema in model-jetty `integrations/dsh/src/contracts.ts:6-22` carries `.max()`/`.min(1)`; even `index` is `z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER)`.

**Zero-dependency alternative**: repos without a schema library (logic-foundry) do not degrade to `as` — hand-written type predicates validate `unknown` field by field (`packages/document/src/schema.ts:22-27`: `function isSafeCoord(val: unknown): val is number { ... }`), returning a custom `Result<T,E>` discriminated union. Pure JS plugins (dsh-plugin-tokspeed) likewise use `typeof x === 'number' && Number.isFinite(x)` throughout the file.

- ✅ New HTTP/RPC/IPC endpoints: request schema as `strictObject` + discriminated union, types exported via `z.infer`; responses use `.loose()` depending on compatibility needs.
- ✅ When defining cross-end shared contracts, add drift guards (type-level assertions or compile-time contract tests, e.g. kunkun-services' `hono-client-route-type.test.ts`).
- ❌ Handlers that hand-write `body as CreateRequest` and consume external input directly.
- ❌ Mixing zod and valibot in the same repo (each repo picks exactly one; vendored third-party code excepted).

## 5. Error Handling: Closed Error Code Table + code-carrying Error + Structured Guards

A unified pattern, executed word-for-word identically across three repos (sample `../samples/ts-errors.ts`):

1. **Closed code set**: all error codes listed in `as const`, with comments declaring it closed on purpose (refyard `git-contract/src/errors.ts:13-62`'s `PROBLEM_CODES`; every code carries a doc comment, including `UncertainOutcome`: "Git may have changed things, but the outcome could not be confirmed. Never auto-retried.").
2. **code-carrying Error classes**: the error codes form a string literal union, and the Error carries `readonly code` plus an optional `readonly context` (kunkun `packages/core/src/permission-broker/errors.ts:18-33`).
3. **Structured guards, no reliance on instanceof**: after crossing bundles/serialization, `instanceof` breaks down, so guards degrade to shape checks (kunkun-services `apps/api/src/errors.ts:102-108`'s `isApiError`: `"code" in error && "status" in error && "message" in error`, then per-field `typeof` narrowing).

Consumers branch on `error.code`, never on message text — refyard `errors.ts:66-67`: "Clients branch on these, not on message text"; kunkun-services `errors.ts:68-69`: "A stable code. Branch on this, never on `message`". `details` holds only flat, redacted facts (refyard: "Flat, redacted facts: field names, limits, Git exit codes. Never file contents"; a validation error's `path` "never contains the value that failed (which may be a secret)"). On the HTTP side, one code always maps to one status (ListenFlow `STATUS_BY_CODE` comment: "same failure cannot be a 400 through one door and a 404 through another").

- ✅ Adding a new failure branch: first add the code to the closed table (with a doc comment), then switch on it at the consumer; map HTTP status via an exhaustive Record.
- ❌ `throw new Error("something failed")` followed by callers doing `catch (e) { if (e.message.includes(...)) }`.
- ❌ Stuffing whole objects that may contain sensitive values into error context.

## 6. exactOptionalPropertyTypes Companion: Conditional Spreads to Rebuild Optional Fields

Repos with this flag on (model-jetty, kunkun core, logic-foundry) share a fixed idiom: when rebuilding a DTO from unknown input, optional fields are rebuilt precisely with conditional spreads and never passed through directly — preventing ghost `undefined` properties at the type level (sample `../samples/ts-exact-optional.ts`):

```ts
// model-jetty packages/core/src/contracts/request-schemas.ts:47-49 (comment: Exact optional properties are reconstructed, never asserted from unknown input.)
...(parsed.data.tools === undefined ? {} : { tools: parsed.data.tools.map((tool) => ({ ... })) }),
...(parsed.data.instructions === undefined ? {} : { instructions: parsed.data.instructions }),
```

- ✅ When constructing objects with optional fields, use `...(x === undefined ? {} : { x })`.
- ❌ Spreading `{ ...parsed.data }` in one go, passing optional fields of unknown origin straight through.

## 7. Restrained Use of readonly and Generics

- DTO/interface fields are heavily `readonly`; constant objects are always `as const`; model-jetty factory functions return `Object.freeze({...})`, and services are not expressed as classes (only Error uses a class).
- `satisfies` is used sparingly (5 occurrences across refyard packages, 3 in space-lens) — only when "keep literal inference while checking the type" is needed (e.g. space-lens `apps/tui/src/cli-config.ts:3-4`).
- Generics are restrained: all generics in refyard are confined to single points like `send<Response>(schema: z.ZodType<Response>)` (`client.ts:175-179`); uniview uses `createPluginRuntime<T extends Transport<RPCMessage>>` only in the transport-layer abstraction. No unnecessary generic layers are written.

## 8. Module Organization and Naming

**Module header comments are a hard convention**: every source file opens with a passage on "what this file is responsible for and where it sits in the architecture", written entirely in English, explaining only constraints the code cannot express. Example (sample `../samples/ts-module-header.ts`):

```ts
// refyard packages/git-core/src/ports.ts:1-9
/**
 * The private host interface that portable core is allowed to use.
 *
 * This file is the whole point of the architecture: core plans Git commands and
 * parses their output, but it cannot spawn, read, encode, time or cancel anything
 * itself. Those arrive through `GitHostPort`, which only the trusted Node host
 * implements. ...
 */
```

**Naming**: files are kebab-case (git-core is split into domain directories like `plan/status.ts` and `parse/`); types/interfaces are PascalCase; discriminant fields conventionally `kind` or `type`; constants SCREAMING_SNAKE (`PROBLEM_CODES`, `OPERATION_TARGET_LIST`). Rust↔TS bridges use `#[napi(js_name = "ignoreHidden")]` to align to camelCase (space-lens `packages/node/src/lib.rs:21-30`).

**Architectural constraints are machine-enforced**: portable packages are forbidden from importing host APIs (node:*/DOM/electron), enforced not by comments but by scripts/rules — refyard `scripts/check-boundaries.ts` (parses with oxc, violations reported as file:line:column), kunkun's custom ESLint rule `eslint-rules/enforce-runtime-layering.mjs` (modeled on VS Code code-layering; importing electron from the portable layer fails lint), model-jetty `scripts/boundaries.ts` (static import analysis via the TS compiler API, fail-closed). Most packages' `lint` script is just `tsc --noEmit` — type checking is the lint.

**Import extensions (two camps coexist, no unification)**: refyard uses `.js` specifiers (for compatibility with running directly on Node); kunkun-services uses `.ts` specifiers (96 occurrences, paired with `allowImportingTsExtensions: true`); kunkun core uses no extension. Follow the existing style of the repo you are in.

## 9. Toolchain Dual Mode: Internal Code Linked Directly, Build Only to Publish (Core Rule)

Stated in their own words: "for packages depended on internally within the monorepo, just export the TypeScript source files directly; packages in other workspaces import them directly, no compile step needed; only libraries published to npm for external users compile with tools like tsdown". The code confirms this fully, in three mature forms:

### Pattern A — Internal Packages: exports Point Directly at src (Most Common)

```jsonc
// refyard packages/git-core/package.json (sample ../samples/ts-package-internal.json; same shape: kunkun packages/core, space-lens packages/contract)
{
  "name": "@refyard/git-core",
  "version": "0.0.0",
  "private": true,
  "exports": { ".": "./src/index.ts", "./*": "./src/*.ts" },
  "scripts": { "check": "tsc --noEmit -p tsconfig.json" }
}
```

Characteristics: `private: true` + `version: 0.0.0` + `workspace:*` cross-references + no build script (only check). kunkun core provides deep-path subpath exports per domain (`"./agent": "./src/agent/index.ts"`), avoiding barrels that drag in side effects. Tests import by package name rather than relative paths; cross-package relative-path reach-ins are rejected by check-boundaries.

### Pattern B — Published Packages: tsdown Build + types

```jsonc
// kunkun packages/sdk/package.json (sample ../samples/ts-package-published.json)
"exports": {
  ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js" },
  "./manifest": { "types": "./dist/manifest/index.d.ts", "import": "./dist/manifest/index.js" }
},
"scripts": { "build": "tsdown && pnpm run generate-schema" }
```

tsdown.config.ts has multiple entries, with comments even explaining why a single entry stays narrow (kunkun sdk: `implementService` bypasses the barrel to avoid the side-effect import of `@uniview/react-renderer` — "A service-only plugin has no reason to bundle the worker-view React renderer"). uniview's published packages also use tsdown.

**CLI artifact exception**: refyard's npm-published `refyard` package skips tsdown and is bundled into a single file with esbuild — `scripts/build-release.ts:11-13`: "The CLI is bundled with its workspace packages inside it, so the tarball has no `dependencies` at all and nothing resolves `workspace:*` at run time". Before publishing there is a pack-smoke check plus an assertion that artifacts must not contain build-machine paths. In short: **libraries use tsdown; self-contained CLIs use esbuild bundling**.

### Pattern C — One Package, Two Forms: Custom Export Conditions

```jsonc
// uniview packages/protocol/package.json (8 packages in uniview use this pattern; sample ../samples/ts-package-dual-condition.json)
"exports": {
  ".": {
    "uniview-source": "./src/index.ts",   // workspace consumers resolve to source
    "default": "./dist/index.mjs"         // npm consumers get the build output
  }
},
"publishConfig": { "access": "public", "exports": { ".": "./dist/index.mjs" } }
```

### Decision Rules

1. Package consumed only within this monorepo → Pattern A (exports point at src, no build, check via `tsc --noEmit`).
2. Package to be published to npm for external users → Pattern B (tsdown produces dist + d.ts) or C (when workspace-internal consumers should keep consuming source).
3. What gets published is an executable CLI, not a library → bundle with esbuild into a zero-dependency single file.
4. Counter-example: logic-foundry builds its internal packages to `dist/index.js` — the sole exception among all the primary repos (an early project); do not imitate.

- ✅ Adding a new internal shared package: private + exports pointing at src + workspace:*; no build script.
- ✅ Publishing a package: add a tsdown.config.ts (multiple entries, naming each entry's responsibility), switch exports to dist + types, publish via Trusted Publishing.
- ❌ Configuring tsc build/emit for internal packages — an extra build artifact nobody consumes, plus stale-dist problems.
- ❌ Importing via dist within the workspace (or reaching across packages with relative paths like `../../packages/core/src/...`) — importing by package name is an iron rule.

## 10. Do/Don't Quick Reference

| Scenario | ✅ Do | ❌ Don't |
|---|---|---|
| Strictness | strict + noUncheckedIndexedAccess (+exactOptionalPropertyTypes/verbatimModuleSyntax) | Bare strict; lenient options beyond skipLibCheck |
| Type assertions | Zero any/@ts-ignore; unknown + `in` + guard narrowing | `as unknown as`, `@ts-ignore`, lazy any |
| Enums | `as const` values + `typeof`-derived unions | Hand-copied literal lists, `enum` |
| Polymorphic data | Discriminated unions (kind/type literal), strictObject members | Boolean flag combinations, optional grab-bags |
| External input | zod/valibot strictObject at boundaries; requests strict / responses loose | Casting with as inside handlers; trusting caller memory |
| Consistency | Exhaustive Records / Equal-Expect type proofs | Relying on comments to remind about syncing |
| Errors | Closed code table + code-carrying Error + isXxx guards | Matching on message strings |
| Optional fields | Conditional spread `...(x === undefined ? {} : { x })` | Passing through via direct spread |
| Module headers | Every file opens with responsibility + position, only constraints code can't express | No header comment, or restating the next line of code |
| Internal packages | exports point at src, no build | Building internal packages with tsc too; cross-package relative paths |
| Publishing | tsdown (libraries) / esbuild bundle (CLIs) | Publishing source paths; tarballs carrying workspace:* |
