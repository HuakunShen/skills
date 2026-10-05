# Go and Other Languages Guidelines

> Evidence sources (personally read on 2026-10-05): polymarket-quant (the only Go repo), xross-interop-lab tools, ListenFlow ArkTS/Kotlin, dsh-plugin-tokspeed, refyard scripts. Companion samples: `../samples/go-*.go`, `../samples/kotlin-golden-fixture.kt`, `../samples/arkts-typed-json.ets`.

## 0. The Real Position on the Language Map (calibrate expectations first)

Across the 17 key projects: **TypeScript is the dominant language by far**, **Rust is the compiled-language mainstay**, and **Go appears in exactly one project** — polymarket-quant (about 45%, `pkg/` + `apps/collect-data/` + `src/go/`). A `find -maxdepth 3 -name go.mod` scan over `/Volumes/Portable2TB/ExtDev` shows that **the user's own projects contain only one go.mod — polymarket-quant's**; all other hits are in the `others/` reference-clone directory (15+ upstream clones such as syncthing, kopia, rclone, mutagen, lazygit, netbird, tailscale, restic, croc, pocketbase).

This confirms and refines the self-description "for compiled languages I prefer Rust (but the build environment is heavy); when I want something lighter and faster I use Go": in polymarket-quant the two coexist with a clear division of labor — **Rust (`src/*.rs`) is the defining version of the domain logic (thiserror discriminated error enums), while Go is "a second implementation of the same logic plus the actually deployed collection CLI"**, because Go can `GOOS=linux GOARCH=amd64 go build` a single binary that is scp'd straight to a remote server (README.md:4-5). "Light and fast" refers to a light deployment pipeline, not a second heavyweight project: this Go repo has no CI, no golangci config, only 4 `*_test.go` test files, and a toolchain of gofmt defaults + the standard library.

> **⚠️ Operational implication**: "when I want something lighter and faster I use Go" is a **real but rarely triggered** preference — the trigger is "a long-running collection process that needs a cross-compiled single binary dropped onto a server", not "consider Go by default for new projects". **Do not proactively suggest Go unless the user names it; when the user names it or the scenario matches (cross-compilation / single binary / system-level daemon / the reference project is written in Go), write Go according to Section 1 of this chapter.**

## 1. Go: polymarket-quant as the only empirical evidence

### 1.1 How the library/app split takes shape in Go: `pkg/` (libraries with no persistence opinions) + `apps/*/internal/` (composition and disk persistence)

There is an evolution record: the 2026-05-04 journal (`.journal/2026-05-04-collector-library-extraction.md`) and commit fb1d479 document the decision to extract the collection logic from `apps/collect-data` into a reusable `pkg/` library. The current layering:

- `pkg/collector`, `pkg/live`, `pkg/hub`, `pkg/binance` = reusable libraries; the core libraries **explicitly declare that they hold no persistence opinions**;
- `apps/collect-data/cmd/` = the Cobra CLI shell; `apps/collect-data/internal/` = the persistence implementation (recorder/uploader), using Go's `internal/` visibility rules to lock the non-reusable parts inside the app;
- `src/go/` = domain-pure logic mirroring Rust/Python.

`pkg/collector/doc.go` is the self-description of the whole design (sample `../samples/go-library-doc.go`):

```go
// Package collector exposes a high-level, persistence-free Polymarket data collector.
// ...
// The collector has no opinions about how messages are persisted. Consumers
// register typed handlers (OnQuote, OnTrade, OnBook, OnPrice, OnKline,
// OnLifecycle, OnHealth) and decide whether to publish to NATS, write to a
// database, drop into a ring buffer, or any combination of those.
```

**Rule**: for new Go code, first ask "could this logic be consumed by a second program"; if yes → `pkg/<domain>/`, with types and handler registration going into the library and persistence/IO opinions staying in `internal/`; if no → `apps/<name>/internal/`. The library's public API is funneled through type-alias re-exports into a single import path: `pkg/collector/collector.go:26-36` aliases out 9 types such as `live.QuoteMessage` ("consumers can use a single import path … and only fall back to pkg/live for advanced needs").

- ✅ `pkg/collector` exposes typed `OnQuote/OnTrade/OnBook` handler registration and never opens files itself
- ❌ importing `os` inside `pkg/` to open JSONL files, or letting a library function take a `dataDir string` parameter (that is `apps/collect-data/internal/recorder`'s job)

### 1.2 Typing technique: typed string constants + struct json tags, not iota enums

The Go-side equivalent of a "discriminated union" is a **named string type + const values**, and every wire struct carries `json` tags (sample `../samples/go-wire-and-hotpath.go`):

```go
// polymarket-quant pkg/live/types.go:11-16, 53-65
type TokenSide string

const (
    TokenSideUp   TokenSide = "up"
    TokenSideDown TokenSide = "down"
)

type QuoteMessage struct {
    Slug        string    `json:"slug"`
    AssetID     string    `json:"assetId"`
    TokenSide   TokenSide `json:"tokenSide"`
    TimestampMs int64     `json:"timestampMs"`
    // ...
}
```

State machines use string-returning methods instead of enums: `EventDescriptor.StatusAt(now) string` returns `"upcoming"/"live"/"ended"` — matching the TS-side literal discriminated unions and the Python-side `typing.Literal` one for one.

**Rule**: to express a closed value domain in Go, use `type X string` + named consts so the JSON wire carries readable strings; struct fields must carry `json` tags (wire types mirror TS/Python with shared field names). Do not use `iota` integer enums — they break cross-language wire readability.

- ✅ `LifecycleAction = string` + `LifecycleUpsert LifecycleAction = "upsert"`
- ❌ `type Status int` + `iota` — it serializes into numbers, and the TS/Python side cannot mirror it

### 1.3 Error handling: `fmt.Errorf` with `%w` wrapping + package-name prefix; panic only for unreachable branches

Library/app errors all use idiomatic Go error wrapping, with a package-name prefix in the message for easy log location (sample `../samples/go-errors.go`):

```go
// polymarket-quant apps/collect-data/internal/recorder/recorder.go:49-58
if err := os.MkdirAll(dir, 0o755); err != nil {
    return fmt.Errorf("recorder: mkdir %s: %w", dir, err)
}
```

Parse failures return an error carrying the original input (`fmt.Errorf("unknown slug format: %q", slug)`); `panic` appears only in the `default:` unreachable branch of a switch (the upstream constructors are already exhaustive).

**Rule**: Go errors are always wrapped with `fmt.Errorf("pkgname: what failed: %w", err)`; error messages must include the offending input value (`%q`); panic is limited to logically unreachable default branches. Note that this does **not** use a Rust-style discriminated error enum (`SlugError` in `src/slug.rs:22-37` has 5 variants; the Go version is just an error string) — this is a pragmatic downgrade within Go, not an oversight: **in the same repo, Rust is the contract-defining version, and Go errors only need to avoid interrupting the caller.**

### 1.4 Configuration: a three-level CLI flag > env (via godotenv) > default fallback, funneled into one helper

Every configurable item follows the same pattern, implemented centrally by a single function (sample `../samples/go-config-fallback.go`):

```go
// polymarket-quant apps/collect-data/cmd/root.go:102-112
func valueFromFlagOrEnv(cmd *cobra.Command, flagName, currentValue, envKey string) string {
    if cmd.Flags().Changed(flagName) {
        return currentValue
    }
    if v := os.Getenv(envKey); v != "" {
        return v
    }
    return currentValue
}
```

**Rule**: every flag in a Go CLI must have an env name and a default, resolved through the unified helper; optional heavy dependencies (S3/NATS) are constructed lazily; `.env` is loaded with godotenv before flag parsing and does not override existing shell variables. Direct `os.Getenv` in business code is forbidden.

### 1.5 [Explicit tension point] lenient hot-path degradation vs. global "type-safety purism"

The global rule is "validate external input with schemas at the boundary, fail-closed", but the Go collection hot path is written as **lenient degradation**:

```go
// polymarket-quant pkg/live/types.go:245-262
func ParseFloat(raw string) float64 {
    v, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
    if err != nil {
        return 0
    }
    return v
}

func TokenSideForAsset(upTokenID, downTokenID, assetID string) TokenSide {
    switch assetID {
    case upTokenID:
        return TokenSideUp
    case downTokenID:
        return TokenSideDown
    default:
        return TokenSideDown
    }
}
```

Timestamp parsing tries multiple formats one by one and returns an error on failure, but `ParseFloat`/`TokenSide` just hand back default values. **Interpretation (annotated: inferred from code structure, not verbally confirmed by the user)**: a long-running WS collector would rather record one bad message as 0/Down than crash the process; meanwhile the TS dashboard boundary (zod) and the Rust domain layer (thiserror) are strict. In other words, **validation strength is layered by path**: human-facing data exits/entries are strict, machine-to-machine hot paths are lenient.

**Rule**: when writing Go collection/long-running processes, first ask which path this code is on: the **boundary layer** (humans read it, decisions depend on it) → strict validation returning errors; the **hot path** (thousands of WS messages per second) → lenient degradation + logging, but degradation points must be centralized (turn them into named functions instead of scattered `if err != nil { continue }`). ❌ returning an error for every field on the hot path so the entire collector stalls; likewise ❌ silently swallowing errors like this at schema boundaries (TS side).

### 1.6 Three-language mirror discipline: "Must update all 3"

polymarket-quant's domain logic (series/slug/constants) is manually mirrored in Rust/Go/Python in three places, kept in sync via the AGENTS.md routing table rather than code generation:

```
| Add/change symbol or interval | src/constants.rs + src/go/constants.go + src/polyquant_common/constants.py | Must update all 3 |
| Change slug format logic      | src/slug.rs + src/go/slug.go + src/polyquant_common/slug.py | Must update all 3 |
```

(Source: `polymarket-quant/AGENTS.md:29-31`; the same file's ANTI-PATTERNS section states verbatim "DO NOT update one language without updating the other two for domain logic".) Even the comments are mirrored across the three implementations: Rust explains the three slug formats and the ET timezone rules, the Python module docstring explains the same thing, and the Go version uses godoc to explain the same format dispatch. **Behavioral alignment relies on shared test data** (see the golden fixture pattern in Section 4).

**Rule**: when asked to change polymarket-quant's domain logic, default to changing all three places in one commit; if not all are done, state explicitly "the other two are not yet updated".

### 1.7 Other Go facts (toolchain and habits)

- **Comments all in English**: grepping all `.go` files under `pkg/`, `apps/collect-data/`, and `src/go/` for CJK hits 0 (verified). godoc style `// FuncName ...`, high comment density on public APIs (61 in `pkg/collector`), near-zero comments in pure-data struct files — **comments are invested at boundaries, not internals**.
- **Standard library for tests**: 4 `*_test.go` files, native `t.Fatal` + table-driven standalone Test functions, **no testify** (hand-written `if got, want := ...; got != want` comparisons).
- **Minimal dependencies + submodule replace**: `go.mod:66` `replace github.com/HuakunShen/polymarket-kit/go-client => ./vendors/polymarket-kit/go-client` (the vendored SDK is consumed one-way as a git submodule). Runtime dependencies are only infrastructure-grade: cobra/zerolog/parquet/nats/prometheus/aws-sdk/gorilla/godotenv.
- **Deployment is cross-compilation**: the README leads with `GOOS=linux GOARCH=amd64 go build ... && scp` as its first documentation.
- **No lint config**: no golangci/`go vet` config files anywhere in the repo (verified); the only quality gate is tests — the Go side is **lightweight pragmatism**.

### 1.8 When using Go: guidelines

> Items 1-4 have polymarket-quant evidence; items 5-7 are **drafts** inferred from the self-description and the reference shelf.

1. Layering per 1.1: `pkg/<domain>` (pure logic/types, no persistence) + `apps/<name>/cmd` (Cobra shell) + `apps/<name>/internal` (disk persistence); if the domain-pure logic serves multiple languages, put it in `src/go/` mirroring the other languages.
2. Typing per 1.2: typed string constants + json tags; no iota, no `interface{}`/`any` for carrying data.
3. Errors per 1.3: `%w` wrapping + package-name prefix + `%q` with input; hot-path degradation points centralized into named functions.
4. Configuration per 1.4: flag > env > default, unified helper, lazy construction of optional dependencies.
5. (Draft) Standard library first: the reference shelf (syncthing/tailscale/restic/croc/pocketbase) is all standard-library culture; polymarket-quant keeps runtime dependencies at 9 or fewer. Before adding a new dependency, first ask whether the standard library/`golang.org/x` covers it.
6. (Draft) Concurrency primitives are plainly combined with `sync.RWMutex`/`sync.WaitGroup`/`context.CancelFunc`/`atomic.Bool` (`collector.go:57-77` evidence: one RWMutex for the handler registry, stopFn+wg for lifecycle); no concurrency frameworks.
7. (Draft) Goroutine lifecycles must be stoppable: the pattern of a Collector exposing `Stop()` (context cancel + WaitGroup wait); long-running processes must be able to exit gracefully.

### 1.9 The Go reference shelf (`others/`)

The `others/` directory collects canonical Go implementations by problem domain: file transfer (croc, magic-wormhole), sync/backup (syncthing, mutagen, restic, kopia, rclone, seafile, sftpgo), networking/P2P (netbird, tailscale, bore, dumbpipe), streaming (r50-mediamtx, r51-gortsplib), backend (pocketbase), TUI (lazygit), device control (scrpcpy). The r-numbered directories map one-to-one to xross-interop-lab's research numbering (r30-croc, r31-syncthing, r50-mediamtx) and serve as reference material for interop research. **Operational implication: when writing Go or doing protocol interop, first check whether `others/` holds a reference implementation for the relevant domain, and read it before writing code.** (Annotated: the act of collecting is verified; which specific patterns were absorbed cannot be proven from the clones themselves.)

## 2. Python: type annotations + Literal discrimination + pandera lazy imports + gate tests

Python appears in two places: the analysis side of polymarket-quant (`src/polyquant_common/`, Streamlit dashboard) and the tooling side of xross-interop-lab (23 files in `tools/`).

### 2.1 Mirroring TS discriminated unions: `typing.Literal`

```python
# polymarket-quant src/polyquant_common/orderbook/_types.py:1-10
DataFileType = Literal["book", "price_change", "last_trade_price", "tick_size_change"]

ALL_DATA_FILE_TYPES: tuple[DataFileType, ...] = (
    "book", "price_change", "last_trade_price", "tick_size_change",
)
```

A closed value domain gets both the Literal type and a runtime tuple — isomorphic to Go's `TokenSide` consts and TS's literal unions. Private modules take the `_` prefix (`_types.py`/`_schemas.py`/`_paths.py`), separated from the public entry points (`loader.py`).

### 2.2 Lazy imports for heavy dependencies: `empty()` stays dependency-free, `validate()` is where pandera gets imported

```python
# polymarket-quant src/polyquant_common/orderbook/_schemas.py:18-50 (the file-header docstring states explicitly: imports pandera lazily on first call / Validation is opt-in)
class BookRawSchema:
    @classmethod
    def empty(cls) -> pl.DataFrame:
        return pl.DataFrame(schema={...})

    @classmethod
    def validate(cls, df: pl.DataFrame, lazy: bool = False) -> pl.DataFrame:
        import pandera.polars as pa
```

**Rule**: Python's runtime schema validation (pandera ≈ TS's zod/valibot) exists, but **heavy imports are always deferred to first use**, and factory functions stay usable with zero dependencies. The DataFrame's dtype schema is the type declaration, aligned three ways with Go struct json tags and TS zod schemas.

### 2.3 Gate tests: pure-stdlib unittest + doc-vs-implementation cross assertions

xross-interop-lab's `tools/test_*.py` (23 files) use pure-stdlib `unittest` (no pytest dependency) and **compile documentation discipline into tests**: line-by-line checks of the spec field tables' source annotations, plus greps forbidding blocked wire vocabulary from appearing in the implementation:

```python
# xross-interop-lab tools/test_quickshare_gate.py:36-45
FORBIDDEN_IN_IMPL = [
    r"_fc9f5ed42c8a", r"quickshare\.google", r"advertisingcontext",
    r"\bmdns\b", r"\bbonjour\b", r"\bble\b", r"\bgms\b",
]
```

(How to run it is written in the module docstring: `python3 -m unittest discover -s tools -p 'test_*.py'`.)

**[Comment-language exception, noted as-is]**: these lab tools' docstrings/comments are in **Chinese**, contrary to the repo-wide "English comments" habit — the lab is a research context where Chinese is the working language. Meanwhile, polymarket-quant's Python docstrings are in English. **Rule: product/library code comments are in English; one-off research tools and lab gate tests may use Chinese, following the existing language of the repository they live in.**

### 2.4 Python has no lint config

polymarket-quant has no ruff/flake8 config (verified); quality is maintained by annotation habits + pandera validation + pytest. The toolchain is uv (uv.lock + .python-version 3.12) + hatchling for building wheels.

## 3. ArkTS: taking "TypeScript without any" seriously

HarmonyOS's ArkTS appears in xross-dev (about 24k lines) and ListenFlow (88 .ets files). ListenFlow's `Contracts.ets` is the best specimen of type discipline in this language (sample `../samples/arkts-typed-json.ets`):

```typescript
/**
 * ArkTS is NOT an arbitrary TypeScript runtime: there is no `any`, no dynamic
 * property access and no structural duck-typing at the boundary. This file is
 * therefore the ONE place where wire JSON becomes domain values:
 *   1. a hand-written JSON parser builds a typed [JsonValue] tree (no
 *      JSON.parse into untyped objects, no `as` casts papering over shapes);
 *   2. explicit decoders validate every field they read and return a
 *      [DecodeResult] carrying a PATHED error instead of silently defaulting —
 *      a missing or mistyped field is a refusal, never a guess;
 */
// ListenFlow apps/harmony/entry/src/main/ets/domain/Contracts.ets:1-13
```

Three concrete techniques:

1. **Hand-written typed JSON tree**: a `JsonKind` enum (object/array/string/number/boolean/null) + a `JsonValue` base class, with subclasses each implementing `asObject()/asString()` narrowing (the base class returns null), because "ArkTS rejects structural casts from the base class". No `JSON.parse` into untyped objects.
2. **Decoders fail-closed**: every field is validated explicitly, and errors carry a path ("a missing or mistyped field is a refusal, never a guess") — verbatim alignment with the TS-side zod strictObject philosophy, just hand-written.
3. **No hand-written fourth copy of wire types**: the contracts package (`packages/listenflow-contracts`) is also an hvigor module, and the ArkTS client imports the same TS source directly — the generator's docstring states plainly "ArkTS .ets imports ordinary .ts", avoiding a fourth hand-written copy of the schemas.

**Rule**: in restricted dialects / reflection-free languages, **do not loosen type discipline because the language is weak** — restore the discipline through patterns (hand-written parsers/decoders/narrowing methods); for shared contracts, prefer letting the language directly consume the existing sources/artifacts rather than hand-copying another one.

Also note ArkTS hard constraints: `.ets` files are Java-like in style, fields must have explicit type annotations, and `null` replaces `undefined` (the effect() factory fills every optional field with null, commented: "no field is invented").

## 4. Kotlin and the cross-language golden fixture: one test dataset adjudicates all languages

ListenFlow's playback state-machine reducer is implemented in four places (TS/Swift/Kotlin/ArkTS), and **one hash-annotated fixture file adjudicates them all** (sample `../samples/kotlin-golden-fixture.kt`):

```kotlin
/**
 * Kotlin port of the TypeScript playback reducer (P4-T05,
 * `packages/listenflow-domain/src/playback-reducer.ts`; iOS parity in P6-T02)
 * — the shared cross-language playback contract (REQ-043).
 *
 * Pure: `reducePlayback(state, event, context)` folds one driver event into
 * the next state plus an ORDERED list of effects. The golden fixture file is
 * hash-identical (1dd03571…) to the TypeScript and Swift suites' ...
 */
object PlaybackReducer {
    const val PREPARE_BUDGET_MS: Long = 2000
    /** JavaScript's Number.MAX_SAFE_INTEGER — the TS "no expiry" lane marker. */
    const val MAX_SAFE_INTEGER: Long = 9_007_199_254_740_991L
}
// ListenFlow apps/android/core/domain/src/main/kotlin/sh/kunkun/mobile/core/domain/PlaybackReducer.kt:12-38
```

Companion discipline:
- **Pure reducer**: no clock/network/storage; `context` injects nowMs and permission facts — the ArkTS version's comment is verbatim identical ("Pure: no clock, no network, no storage — `context` carries nowMs"). Cross-language portability comes from pure functions + injection.
- **Explicit semantic bridging**: Kotlin's `MAX_SAFE_INTEGER = 9_007_199_254_740_991L` pins JS's Number semantics into a constant with its origin commented, keeping behavior identical across all four platforms.
- **Comments reference task IDs and specs**: P4-T05, REQ-043, and AC-P7-T02-01 appear in KDoc/ArkTS docblocks — cross-platform parity is task-driven and traceable.

**Rule**: when the same domain logic needs multi-language implementations, (a) each implementation is a pure function with host capabilities injected as parameters; (b) one golden fixture (hash recorded) is shared by all languages' tests; (c) each copy's comments state whose port it is, the corresponding task ID, and the invariant list; (d) platform semantic differences (JS Number, etc.) are pinned down with explicit constants + comments, not left to luck.

- ✅ `PlaybackReducer.kt`'s fixture hashes match TS/Swift/ArkTS, with comments listing 3 invariants
- ❌ casually renaming a field or changing effect order on the Kotlin side without touching the fixture (all four platforms drift immediately)

## 5. Pure JavaScript: keeping type discipline even without a type system

dsh-plugin-tokspeed is a 535-line zero-build ESM plugin (no TS, no build step). But type discipline did not vanish; it just changed form:

1. **Config boundary validated by schema** (schemastery):

```javascript
// dsh-plugin-tokspeed index.js:47-60
export const Config = z.object({
  /** File size cap in bytes; the oldest lines rotate out. 0 disables the cap. */
  maxFileBytes: z.natural().default(DEFAULT_MAX_FILE_BYTES),
  /** Ceiling on a credible decode rate (tok/s); a faster reading means the provider delivered a burst, not a stream. */
  maxPlausibleTps: z.natural().min(1).default(DEFAULT_MAX_PLAUSIBLE_TPS),
  /** Write sessionId into each sample; disable on shared data directories. */
  includeSessionIds: z.boolean().default(true),
```

   and the schema is applied twice: once when merging the user's config.json at initialization, and again after a POST patch.
2. **Hand-written narrowing instead of the compiler**: `typeof x === 'number' && Number.isFinite(x)` everywhere; absent values uniformly use `null`, not `undefined`.
3. **Constants carry comments**: `MIN_DECODE_MS = 250` paired with "Decode windows shorter than this measure delivery granularity, not decoding" — every magic number has a why.

**Rule**: when the host platform confines you to pure JS, do not write "no types anyway, whatever" code: configuration goes through schema declaration + defaults + re-validation, runtime discrimination uses hand-written narrowing, and magic numbers become named constants with their rationale commented.

## 6. Shell: no bare shell — build/validation scripts are TypeScript run by bun

refyard's `scripts/` directory was verified to hold 22 entries, 21 of them `.ts`; `find refyard -maxdepth 2 -name "*.sh"` hits 0. AGENTS.md writes this up as a structural rule:

- `AGENTS.md:202`: `scripts/  TypeScript dev scripts (boundaries, contract, portable, pack, bench)`
- `AGENTS.md:250`: `bun 1.4.0 runs TypeScript dev scripts (bun scripts/check-boundaries.ts), never the product.`

**Rule**: build/validation/release scripts are always written in TypeScript (typed path operations, reusable workspace packages, oxc parsing capability) and run with bun; do not add new bare `.sh` or `.mjs` files. Exception: when the host ecosystem forces it (justfile, Dockerfile, GitHub Actions YAML), follow that ecosystem.

## 7. Self-description vs. code facts: comparison table

| Self-description | Code facts | Verdict |
|---|---|---|
| "when I want something lighter and faster I use Go" | Of the 17 key projects, polymarket-quant is the only Go repo, with no CI/lint and few tests; but `others/` collects 15+ canonical Go projects | ✅ the preference is real, but the trigger is narrow (single-binary cross-compiled deployment / long-running collection). **Low-frequency and scenario-driven, not a default option** |
| "modularization + type safety hold in any language" | Go: pkg/internal layering + library extraction journal; Python: Literal + pandera; ArkTS: hand-written typed JSON tree; pure JS: schema + hand-written narrowing | ✅ holds across all languages; the technique changes shape per language ecosystem without changing its spirit |
| "for compiled languages I prefer Rust (heavy environment); Go is light and fast" | Inside polymarket-quant the same logic exists as Rust (defining version, thiserror enums) alongside Go (deployment version, error strings) | ✅ the division of labor matches: Rust is domain definition and heavy engineering, Go is light-and-fast deployment |
| Global "type-safety purism/fail-closed" | On Go hot paths, `ParseFloat` returns 0 on failure and an unknown assetID defaults to Down | ⚠️ **explicit tension**: validation strength is layered by path (lenient hot-path degradation vs. strict boundaries). It is deliberate design rather than a violation, but the user has not verbally confirmed the boundary of this principle |
| "prefer monorepo/workspace per language" | The Go repo polymarket-quant has **no** workspace (go.mod is a single module; vendors point to a submodule via replace) | ⚠️ the Go workspace (`go.work`) was never used; Go's reuse unit is module + replace. This self-description has no evidence on the Go side |
