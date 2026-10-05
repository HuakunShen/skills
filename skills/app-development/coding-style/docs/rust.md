# Rust Style Guide

> Evidence sources (read directly on 2026-10-05): the Cargo.toml / justfiles / source code of xross-dev, CrossCopy, refyard-native-desktop-ssh, localsend-rs, space-lens (kuntu), and xross-interop-lab. Companion samples: `../samples/rust-*.rs`, `../samples/rust-workspace-isolation.toml`.

## 0. Rust's role in the projects

Rust consistently occupies three positions: **core engines** (xross-dev's daemon and fabric, the kuntu file search engine, polymarket-quant's domain library), **CLI/TUI shells** (xross-cli, space-lens CLI, `xs tui`), and **FFI boundaries** (napi/JNI/C-ABI, handing the engine to Swift/Kotlin/ArkTS/Node).

The self-described "heavy build environment" never stopped him from maintaining a 436k-line Rust workspace (797 .rs files under xross-dev's `crates/`); it turned instead into written mitigations: service crates deliberately do not depend on the QUIC tree so that "the service compiles in seconds" (`crates/contract/xross-service-host/src/lib.rs:8-9`), `[profile.e2e]` turns off LTO in exchange for link speed (`Cargo.toml:259-264`), and tests run under nextest with per-test thread tuning. **Operational implication: when writing Rust in his repos, compile time is a property that can be optimized at the crate-partitioning level, not a reason to accept the status quo.**

## 1. Cargo workspace is the default organization; structural isolation beats verbal rules

- **New Rust projects default to a cargo workspace**, even with only two or three crates; standalone small libraries published to crates.io (such as localsend-rs v0.1.2) are the sole exception: a single crate with lib/bin dual targets (`src/lib.rs` exports the library API + feature-gated cli/tui modules; `src/main.rs` is only a 34-line thin entry point).
- **All dependencies (including internal path dependencies) are declared centrally in the root `[workspace.dependencies]`**, and sub-crates consume them via `dep.workspace = true`. The reasoning is written into the config itself: "crypto primitives are pinned at the workspace level ... codecs and services must not drift onto two versions of the same primitive and then disagree about bytes" (xross-dev `Cargo.toml:168-185`).
- **Directory categories act as dependency whitelists**: xross-dev's members are `crates/*/*`, split into directories by `contract / kernel / platform / runtime / service / adapter / app / composition / probe / testkit`; `scripts/check-boundaries.ts:24-79` uses `cargo metadata` to turn "a service may depend only on contract+platform" and "an app must not depend on an app" into CI gates. Sub-crates cannot route around this, because the directory location determines the rule.
- **Physical workspace splits provide structural isolation**: refyard-native's desktop shell is a separate second Cargo workspace (`apps/desktop/src-tauri/Cargo.toml` carries an empty `[workspace]` section; sample `../samples/rust-workspace-isolation.toml`), with a comment stating it plainly: "the root workspace cannot see these dependencies, so nothing in `crates/` can accidentally touch the WebView". The root workspace's `default-members` contains only headless crates, guaranteeing `cargo build` never needs WebKit. space-lens mirrors this: the root workspace members are only `packages/node` and `apps/cli`; the engine lives entirely inside the vendored submodule kuntu and is consumed through an alias: `space-lens = { package = "kuntu-scan", path = "../../vendors/kuntu/crates/kuntu-scan" }`.
- **The reusable core is a crate, not a module**. xross-service-host's lib.rs opens with a manifesto (sample `../samples/rust-service-seam.rs`): "A service names this crate and nothing else. It never names `xross-fabric`, `iroh` or `tonic`, which is what lets the same service crate be linked into the daemon, run as its own binary, or embedded in a native app — that is a **build decision, not a rewrite**". This is the Rust-side form of the "split core logic into a library" preference.
- **Vendored dependencies are folded in via `[patch.crates-io]`; excludes must be named one by one**: xross-dev patches `iroh-relay` to a vendors/ submodule and documents the invalidation condition ("Bumping `iroh` without bumping the copy in the same change is how the patch silently stops applying — `cargo tree -p iroh-relay` is the check"); the fact that `exclude` does not support globs is itself recorded as a comment.

✅ Dependency versions have exactly one place with the answer; whoever consumes sets `.workspace = true`; Tauri/WebView dependencies go into a structurally unreachable separate workspace; a service crate's Cargo.toml holds only contract/platform dependencies and compiles in seconds.
❌ Writing `tokio = { version = "1", features = [...] }` inline in a sub-crate (the second crate that needs it gets promoted to a workspace dependency with a provenance comment, see the `axum` entry at `Cargo.toml:209-212`); ❌ adding desktop crates to the root workspace and relying on code review to keep core from referencing them — "wishes that older repos could only write in comments become gates here".

## 2. Error handling: thiserror (libraries) / anyhow (composition roots) dual track; library-layer errors are wire data

The most consistent discipline, observed in all five repos:

- **Reusable library crates define domain error enums with thiserror**; nearly all 37 contract-type crates in xross-dev depend on thiserror, while anyhow concentrates in the app/platform/runtime composition roots. localsend-rs is cleaner still: the library body has zero anyhow; `anyhow` appears only in `src/cli/commands/*`, `src/tui/app.rs`, and `src/main.rs`.
- **Every `#[error(...)]` is a complete sentence, not a label** (sample `../samples/rust-contract-error.rs`):

```rust
// xross-dev crates/contract/xross-transfer-contract/src/protocol.rs:356-370
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize, thiserror::Error)]
pub enum OfferRejection {
    #[error("an offer must name what it is sending")]
    EmptyName,
    #[error("the name exceeds {max_bytes} bytes (got {actual_bytes})")]
    NameTooLong { max_bytes: usize, actual_bytes: usize },
    #[error("that is a path or an escape sequence, not a name")]
    NameIsNotAName,
    #[error("a file is one blob and a tree is a hash sequence; this offer crosses them")]
    FormatDoesNotMatchPayload,
}
```

  Note the derive list: the error is simultaneously `Serialize + Deserialize + Clone + PartialEq` — **at the contract layer, the error itself is a type that crosses the wire**; consumers branch on the variant instead of parsing the message.
- **Externally facing error enums get `#[non_exhaustive]`** (localsend-rs `src/error.rs:5`), absorb source errors with `#[from]`, and come with a `pub type Result<T> = std::result::Result<T, Error>` alias (CrossCopy `packages/xc-lib/src/error.rs:31`).
- **Enums are sectioned by domain with `// ====` banner comments for navigation**: localsend-rs's `LocalSendError` has six sections — I/O / Network / Protocol / Transfer / Auth / HTTP Status — and HTTP status codes are mapped one by one into semantic variants (`Rejected`/`RateLimited`/`InvalidPin`), not handled by a string fallback.
- **Closed error codes are a deliberate decision**: xross-interop-lab's `ErrorCode` enum has 23 codes with kebab-case serde, and the file header mandates "unknown error codes are rejected at deserialization (serde enum default behavior; **do not add a default**)". The wire enum's `from_i32` enumerates explicitly, returning an Error for unknown values instead of falling into a catch-all.
- **anyhow's proper place is the composition root**: CLI command function signatures read `pub async fn execute(command: SendCommand) -> anyhow::Result<()>` (localsend-rs `src/cli/commands/send.rs:27`); `anyhow::bail!` is used for user interruption (space-lens `apps/cli/src/main.rs:282`).
- **Panic semantics at boundaries are guarded with `compile_error!`**:

```rust
// CrossCopy apps/apple/core-ffi/src/lib.rs:22-28
#[cfg(panic = "abort")]
compile_error!(
    "crosscopy-apple-core requires panic=\"unwind\" so catch_unwind can contain \
     core panics at the C boundary; build with `--profile ffi-release`, not \
     `--release` (see the workspace Cargo.toml)."
);
```

  xross-dev's release profile likewise sets `panic = "unwind"` explicitly, with the reason in a comment: "Load-bearing: xrossd hosts services in-process; a handler panic must not take down every session on the device" (`Cargo.toml:270-272`).
- **Structured error objects win over strings**: xross-interop-lab's unified `Error` struct carries `code/message/retryable/phase/remedy` fields, and `Remedy` is deliberately a structured object, "not an arbitrary shell command".

✅ Library functions return `Result<T, DomainError>`; error enums are serde-serialized onto the wire; only CLI entry points use `anyhow::Result` + `.context()`.
❌ `use anyhow::Result` in a library crate; ❌ an uninformative `#[error("invalid")]` label; ❌ adding `#[default]` or an unknown catch-all variant to a wire enum; ❌ branching on `e.to_string().contains("timeout")`.

## 3. Types as boundaries: newtype IDs, fail-closed enums, `Result<Self>` state machines

- **Non-interchangeable values such as IDs/tokens/paths are always newtyped, with validation at construction**. xross-interop-lab uses `macro_rules! opaque_id!` to generate 7 ID newtypes in bulk (sample `../samples/rust-opaque-ids.rs`), with the validation rule written in a comment ("`[A-Za-z0-9._-]{1,64}` and must not start with `.`", guarding against `..` and hidden semantics). localsend-rs is the hand-written counterpart: `SessionId`/`FileId`/`Token`/`Port` are all `#[serde(transparent)]` newtypes; `Port::new` validates non-zero and returns a Result, while `new_unchecked` remains as an explicit escape hatch (`src/protocol/types.rs:47-172`).
- **State machines are data-carrying enums with `Result<Self>` transition methods**, so illegal transitions are compile-time-visible errors rather than panics (sample `../samples/rust-state-machine.rs`):

```rust
// localsend-rs src/core/transfer.rs:48-59
pub fn accept(self, session_id: SessionId) -> Result<Self> {
    match self {
        Self::WaitingForAcceptance { sender, files, .. } => Ok(Self::Transferring { ... }),
        _ => Err(LocalSendError::invalid_state("Cannot accept transfer from current state")),
    }
}
```

- **"No default" is itself a security property and belongs in comments and tests**. xross's `ChannelLane::from_params`: `Some(0) => Control, Some(1) => Data, None => Err(Absent)`; the doc comment states it outright: "**There is no default, and that is the security property.** Empty params and unrecognized bytes are both rejected, because a fallback is a lane a peer can reach by sending empty data", paired with a test asserting the error message does not leak the legal values (`crates/contract/xross-service-host/src/lib.rs:613-698`).
- **Permissions/capabilities are first-class types, not boolean flags**: `ServiceChannel` is itself the "already authorized channel" type — "By the time a service sees one of these, the peer has proved who it is... A service's job is the bytes, never the decision"; `ServiceDescriptor.actions` is filled in by the registry and a service may not self-report, preventing understatement/overstatement.
- **Stringly contracts are banned in-process** (documented in CrossCopy AGENTS.md:393-421): same-process Rust calls must go through typed methods; `serde_json::Value`/maps/command strings may appear only at real serialization boundaries (FFI/HTTP/CLI output/persistence), and "Every operation needs an explicit request type and response type". The canonical implementation is CrossCopy's `json_api.rs`: the legacy JSON FFI is quarantined in a single file, "Every dispatcher arm is a thin adapter: parse/convert... call a typed `CoreState` method... None of the business logic lives here".

✅ `fn publish(token: Token, file: FileId)` — parameter types prevent mix-ups; wire enums are matched exhaustively with no `_ =>` fallback.
❌ `fn publish(token: &str, file: &str)`; ❌ wire enums with `#[serde(default)]`; ❌ decoding a `serde_json::Value` at the service layer and then branching on `.get("type").as_str()`.

## 4. Trait design: built for injection and seams, not for OOP

- **The primary purpose of traits is testability and isolating the host**, with small, focused signatures: localsend-rs's `FileSystem` trait has only 6 methods (read/write/exists/metadata/create_dir_all/remove_file) plus "File system abstraction for testability and flexibility" plus a `TokioFileSystem` default implementation, with fakes injected in tests. The xross side mirrors this: `ReceiveStores`, `OperationDirectory` (a single `is_open` method).
- **Capabilities are injected as trait objects through the composition root; libraries never name the engine**: "Implemented in the kernel on the blob store and handed to the service by the composition root, so the service can publish bytes without ever naming `iroh-blobs`".
- **A supertrait can be a deliberate downcast channel**: `BlobReadAccess: std::any::Any + Send + Sync + 'static` — "`Any` is a supertrait so the kernel can get its own type back... Upcast-and-downcast in one place is the price of the contract staying transport-free". This is a rare, comment-defended use of `Any`, not the default.
- **Named traits instead of bare `Box<dyn AsyncRead + ...>`**: "`PayloadRead` — A named trait rather than a bare `Box<dyn AsyncRead + AsyncSeek + ...>` so the bound has somewhere to be documented and so a service's signature reads as what it is", with a blanket impl provided for every type satisfying the bounds.
- **Two traits beat one enum for dispatch**: the `Service` vs `RpcService` split carries a full doc-comment argument — "An RPC service and a bulk-byte service are genuinely different shapes... Folding them into one enum would make every service match on a case it does not handle". The associated type `type Protocol: irpc::Service` instead of a generic parameter "states 'this service speaks this protocol' as an invariant".
- **Async traits always take `#[async_trait]` with `Send + Sync + 'static` bounds**.
- **Trait methods carry contract docs**: "must be a pure function of its input", "must not block: store it and let a watcher read it" — side-effect constraints are written on the method, not in tests.

✅ Small 6-method traits + default impls + test fakes; capabilities injected from the composition root; every trait method states what it does not do.
❌ God traits; ❌ pulling in mockall for mocks instead of hand-writing narrow traits; ❌ a library directly doing `use tokio::fs` (in the service category, even naming tokio gets blocked by the gate).

## 5. Attitude toward unsafe: forbid by default; the FFI boundary is the only exemption zone

- **Pure-logic/contract/crypto crates always carry `#![forbid(unsafe_code)]`**: grepping xross-dev finds 19 crates; kuntu sets `[workspace.lints.rust] unsafe_code = "forbid"` at the workspace level so all 9 crates inherit it; interop-lab's 28 lib.rs files do the same. Choosing `forbid` over `deny` means even an inline `#[allow(unsafe_code)]` cannot suppress it.
- **unsafe is concentrated in FFI/OS boundary crates**: `FfiBytes::to_vec` in `xross-capability-port`, windows_lock's MutexW, and CrossCopy core-ffi's `#[unsafe(no_mangle)] extern "C"`.
- **Every unsafe fn carries a `# Safety` section stating caller obligations** (sample `../samples/rust-ffi-safety.rs`):

```rust
// xross-dev crates/contract/xross-capability-port/src/lib.rs:112-124
/// # Safety
/// `ptr` must be valid for `len` bytes, or `len` must be zero. The caller is
/// asserting the borrow described above still holds.
pub unsafe fn to_vec(self) -> Vec<u8> { ... }
```

- **Ownership rules are pinned in comments at the FFI header**: "The operation table owns every buffer, and a pointer that crosses this boundary is borrowed for the call"; ssh-ffi's ffi.rs module header spells out "`xross_ssh_connect` returns an owning pointer. The caller must eventually call `xross_ssh_free` exactly once".

✅ A library crate's first line is `#![forbid(unsafe_code)]`; unsafe appears only in plainly named files like `ffi.rs`/`windows.rs`; every unsafe fn has a `# Safety` contract.
❌ Writing unsafe in a business crate "for performance" with no benchmark comment; ❌ local `#[allow(unsafe_code)]` exemptions (impossible under forbid); ❌ C ABI functions without ownership comments.

## 6. Toolchain and lint: exact pinning, `-D warnings`, default rustfmt, rules written as tests

- **rust-toolchain.toml pins an exact version rather than stable**, and the reason is an incident postmortem: xross-dev pins `1.97.1`, with a comment recording the 2026-08-18 incident where stable drift turned the fmt gate red across 30 files, plus the operating rule that a toolchain upgrade must run `cargo fmt --all` in the same commit. interop-lab pins 1.98.0, with even the version number asserted by a hygiene test. The counterexample is refyard-native, which deliberately does not pin and comments why (the cross-compilation matrix requires a consistent channel) — **pinning or not, it is a commented decision, not an oversight**.
- **clippy is enforced with `-D warnings`**: `just check` runs `cargo clippy --workspace --all-targets -- -D warnings` (xross-dev `justfile:540`); space-lens puts `#![deny(clippy::all)]` at the top of the napi crate plus full-workspace clippy in CI.
- **No rustfmt.toml/clippy.toml; defaults are used** (a find across xross-dev, CrossCopy, refyard, and kuntu comes up empty). The exception is space-lens, which sets `tab_spaces=2`. Formatting discipline is guarded by pre-commit hooks/scripts and scoped: "cargo fmt uses -p to limit the scope; do not reformat unedited code".
- **Even repos without CI have executable gates**: interop-lab has no CI; its architecture rules (dependency whitelist, no git sources, path escapes, toolchain version) are all written as hygiene tests under `cargo test` — a hand-written, zero-dependency TOML-subset parser scans 23 manifests and asserts that the core layer bans tokio and similar network stacks:

```rust
// xross-interop-lab impl/crates/interop-contract/tests/t01_workspace_hygiene.rs:155-163
const FORBIDDEN_IN_CORE: &[&str] = &[
    "tokio", "async-std", "smol", "hyper", "axum", "warp", "actix", "reqwest", "quinn",
    "lib2p", "socket2", "hickory", "trust-dns", "futures",
];
```

- **Feature flags are build variants and must have a `--no-default-features` check**: xrossd walls each capability behind a `#[cfg(feature)]` module, and `just check` specifically runs `cargo check --no-default-features` to keep the optional half from leaking into unconditional code — a comment left in lib.rs admits this is the "third or fourth" time such a leak has been caught.
- **Release profiles are commented decisions**: xross-dev uses `opt-level = "s"` + full LTO + `panic = "unwind"` (with a load-bearing comment); refyard uses `opt-level = "s"` + thin LTO + `strip = "debuginfo"`; kuntu's comment quantifies the benefit ("22MB vs 15MB on darwin-arm64").

✅ In a new repo's first week, land rust-toolchain.toml + clippy -D warnings + forbid(unsafe_code); architecture wishes become tests.
❌ `channel = "stable"`; ❌ running clippy only "when remembered"; ❌ customizing style in rustfmt.toml and then fighting the defaults.

## 7. FFI / Tauri / napi integration patterns

- **The FFI boundary is owned by Rust and lives in its own crate**: "a native API is always behind an FFI boundary owned by Rust"; desktop/mobile share this one contract; the C-ABI implementation goes into a separate ffi crate (ffi.rs + android.rs, split into per-platform cfg files). **Hand-written headers, not generated**: "`include/xross_ssh.h`... is not generated: it is small, and it carries the threading and ownership rules that a generator would drop".
- **Android binds the Rust API directly via JNI, without adding a second marshalling layer**: "JNI already forces one marshalling layer and Rust -> C -> Rust would add a second for nothing" (xross-dev `Cargo.toml:150-153`).
- **On the napi side, `#[napi(js_name = ...)]` bridges naming to camelCase**, and core types get `Core`-prefixed aliases to avoid name collisions (space-lens `packages/node/src/lib.rs:10-18, 21-30`); the napi crate opens with `#![deny(clippy::all)]`, the manifest keeps `publish = false`, and all fields inherit via `workspace = true`.
- **DTOs only translate, never add logic**: space-lens's `impl From<ScanNode> for DirectoryNode` converts field by field; every dispatcher arm in CrossCopy's json_api is a "thin adapter".
- **Tauri shells are structurally isolated from the core** (see §1): tauri/tauri-plugin dependencies exist only in the desktop shell's separate workspace manifest; the frontend is compiled to static assets, "Nothing here links a JavaScript engine".
- **FFI semantics are expressed in types**: a closed-set `OperationStatus` (`#[repr(i32)]`, Ok/Refused/Cancelled/Failed) "rather than a passthrough of the platform's own error, so that a capability cannot smuggle a platform string into a place a peer reads"; ABI version constants are checked at registration, and a mismatch is rejected outright.

✅ FFI crates contain only the translation layer; errors crossing the boundary become closed enums; every `extern "C"` function documents ownership and lifetimes.
❌ Business logic inside napi/JNI adapters; ❌ FFI returning platform error strings for the Swift/Kotlin side to parse; ❌ adding tauri dependencies to the core workspace "just temporarily, to try it out".

## 8. Comments and configuration: every decision leaves a "why"

In his repos, **Cargo.toml files and module headers are the medium of decision records**: why a dependency is vendored, why it is excluded, why it is pinned at the workspace level, why a crate was deleted and merged into another (even the demise of `xross-account-client` left an epitaph); every trait design trade-off (why an associated type instead of a generic, why there is no default, why `Any` is a supertrait) has a doc comment carrying an ADR number. `#![deny(missing_docs)]` appears in FFI contract crates. Migration file headers declare "Copied, not written" and cite the old repo's commit hash. **Operational implication: committing a config change that does not explain "why", or a public trait without a doc comment, counts as unfinished work.**

## 9. Known exceptions and tensions

- **Comment language is not monolithic**: most repos keep Rust comments fully English (of xross-dev's 797 files, only 53 contain CJK, and mostly quoting the user verbatim), but **xross-interop-lab's contract/infrastructure crates carry high-density Chinese docs citing design-document numbers** — the only observed Rust repo with large-scale Chinese comments, close to "the contract layer follows the language of the design docs". The default is to write in English, following the existing language of the repo at hand.
- **What "pinning versions" actually means**: workspace-level single sourcing + exact toolchain pinning is real, but the crate dependencies themselves are mostly caret ranges (`tokio = "1"`, `thiserror = "2"`), not all exactly locked with `=`. What gets pinned exactly is the toolchain and primitives where "there can only be one answer".
- localsend-rs (a single-purpose library already published to crates.io) is a deliberate single crate — the workspace preference applies to projects where "multiple shells share one core", not applied blindly.
