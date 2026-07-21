---
name: iroh-development
description: >-
  Guidance for building peer-to-peer applications with iroh, the Rust-based
  modular QUIC networking stack from number0 / n0-computer for direct
  device-to-device connections with NAT traversal, hole punching, relay
  fallback, and DNS/pkarr-based discovery. Covers the core
  Endpoint / Router / ProtocolHandler + ALPN model, and the protocol layer
  built on top: iroh-blobs (content-addressed file transfer), iroh-gossip
  (pub/sub broadcast), iroh-docs (synced key-value replicas), and
  iroh-automerge (real CRDT sync). Also covers tickets (NodeTicket /
  BlobTicket / DocTicket), FFI bindings (Python / Swift / Kotlin / Node via
  iroh-ffi), WASM/browser usage, RPC over iroh connections (irpc), and
  self-hosting relay servers for local testing. USE THIS SKILL whenever the
  task touches iroh, n0-computer, EndpointId/EndpointAddr, NodeId/NodeAddr,
  MagicEndpoint, iroh-blobs, iroh-gossip, iroh-docs, iroh-ffi, sendme,
  dumbpipe, irpc, ALPN protocol handlers over QUIC, hole punching / NAT
  traversal in Rust, or building a P2P app, file-sharing tool, or chat app on
  iroh — including when the user only describes the feature ("点对点连接",
  "内网穿透", "P2P 文件传输", "gossip 广播", "QUIC 打洞", "不用服务器同步文件")
  without naming iroh explicitly. iroh reached a **stable 1.0** release on
  2026-06-15 after renaming its core types multiple times pre-1.0
  (NodeId→EndpointId, NodeAddr→EndpointAddr, MagicEndpoint→Endpoint,
  Discovery→AddressLookup) — a lot of blog posts, Stack Overflow answers,
  and LLM training data describe the older, pre-rename API. Prefer verified
  current docs (docs.rs/iroh/1.x) over recollection.
---

# Iroh Development

A map of the iroh ecosystem: what each crate is for, when to reach for which
one, and the current (stable 1.0) API shape — because iroh renamed its core
types more than once on the way to 1.0, and a lot of blog posts, Stack
Overflow answers, and LLM training data describe an older API.

## Read this first — iroh is stable (1.0) now, but docs/training data lag

**iroh reached stable 1.0 on 2026-06-15** ("Dial keys, not IPs"), and is
currently at **v1.0.2** (2026-07-06). Timeline: `1.0.0-rc.0` (2026-05-07) →
`1.0.0-rc.1` (2026-05-27, "the last one") → `1.0.0` stable (2026-06-15) →
`1.0.1` (2026-06-29) → `1.0.2` (2026-07-06, relay rate-limiting + transport
fairness fixes). **If a doc, blog post, Context7/DeepWiki result, or your
own recollection shows `0.9x`, `0.2x`, or an `rc` tag, treat it as
historical — verify against `docs.rs/iroh/1.0.2` (or newer) instead.**

1.0 ships with a real stability guarantee: **any two v1 endpoints
interoperate regardless of minor version or implementation language**, and
breaking changes now require a major-version bump. If you're still on a
`1.0.0-rc.x` build, **upgrade** — n0 is turning off public relay support for
the RC builds after **2026-09-30**.

Pre-1.0, iroh renamed its core types more than once — worth knowing so you
can read older material correctly (this is the terminology 1.0 shipped
with):

1. `MagicEndpoint` → `Endpoint` (v0.17, old).
2. `NodeId` → `EndpointId`, `NodeAddr` → `EndpointAddr`, `Discovery` →
   `AddressLookup` — the more recent rename, finalized for 1.0. If you see
   `NodeId`, `NodeAddr`, `PeerAddr`, or a `Discovery` trait in a tutorial,
   it's describing pre-1.0 iroh.
3. `NodeTicket` moved out of `iroh-base` into its own crate
   (`iroh-tickets`). `DhtAddressLookup` / `MdnsAddressLookup` moved out of
   the core `iroh` crate into `iroh-address-lookups`.

**As of 1.0, Python, Node.js, Swift, and Kotlin are officially supported
bindings** (via `iroh-ffi` and friends), not just community add-ons — see
`references/bindings-platforms.md`. Older non-Rust examples can still show
pre-rename naming (`PublicKey`/`NodeAddr`) in their snippets even though the
binding itself is now stable — check current docs per language.

## Core mental model

iroh is a layered stack, bottom to top:

```
Transport   UDP by default (Tor / Nym / Bluetooth transports exist as alternates)
   ↓
QUIC + TLS 1.3   encryption, authentication, stream multiplexing
   ↓
Endpoint    identity (key pair), address lookup/discovery, NAT traversal, relay fallback
   ↓
Router      dispatches incoming connections to a handler by ALPN
   ↓
Protocols   application-level: iroh-blobs, iroh-gossip, iroh-docs, or your own
```

Two things run at deploy time: **the iroh library inside your app** (the
`Endpoint`), and, optionally, **relay servers** on public infrastructure that
help peers discover each other and act as a fallback when a direct
(hole-punched) connection can't be established. You can use n0's public
relays (the `presets::N0` default) or self-host your own relay.

**Connect by cryptographic key, not by IP.** An `EndpointId` is an Ed25519
public key (shown as a z-base-32 string). An `EndpointAddr` bundles that key
with whatever reachability info is known — direct IP:port candidates and/or
a relay URL. This is what makes connections survive the peer's IP changing.

## Route to the right reference

Load only what the task needs.

| Task | File |
| --- | --- |
| Creating/configuring an `Endpoint`, connecting/accepting, opening streams, the `Router` + `ProtocolHandler` + ALPN pattern, discovery (DNS/pkarr/mDNS/DHT), relay config, NAT traversal, local/offline testing | `references/endpoint-connections-discovery.md` |
| File/byte transfer (content-addressed blobs), pub/sub broadcast (gossip), synced key-value docs, real CRDT text sync (automerge) | `references/protocols-blobs-gossip-docs.md` |
| `EndpointId`/`EndpointAddr`, keys, tickets (`NodeTicket`/`BlobTicket`/`DocTicket`), self-hosting a relay, the local test-harness recipe | `references/tickets-addressing-testing.md` |
| Non-Rust usage: Python/Swift/Kotlin/Node bindings (`iroh-ffi`), browser/WASM, mobile | `references/bindings-platforms.md` |
| Ecosystem map, the official `iroh-examples` catalog, community projects (awesome-iroh), which repos are worth cloning for reference | `references/ecosystem-examples.md` |

## Which iroh crate do I actually need?

| You want to... | Reach for |
| --- | --- |
| Just establish an authenticated, NAT-traversing connection between two of your own binaries and speak your own wire protocol on top | Core `iroh` crate only (`Endpoint` + `Router` + your `ProtocolHandler`) |
| Move files/bytes: content-addressed, verified (BLAKE3), resumable, dedup by hash | `iroh-blobs` |
| Broadcast messages to a swarm of peers interested in a topic (chat, presence, event bus, game state) | `iroh-gossip` |
| Keep a small structured key-value store (a "doc"/namespace) in sync across peers/devices | `iroh-docs` |
| Real-time collaborative editing of rich/structured data with true CRDT merge semantics | `iroh-automerge` / `iroh-automerge-repo` (see `iroh-examples`) |
| RPC over an iroh connection (or in-memory/quinn transport) | `irpc` |
| Ship a working CLI file-transfer tool without building your own from scratch | `sendme` — usable as-is, or read as a reference implementation |
| Tunnel a local TCP port, SSH session, or arbitrary Unix pipe over iroh | `dumbpipe`, `iroh-ssh` |
| Ship a client in a non-Rust language | `iroh-ffi` (Python/Swift/Kotlin/Node via UniFFI) |
| Run in a browser | WASM via `wasm-bindgen` — see the `browser-*` examples in `iroh-examples` |

## Verify APIs before writing

iroh is stable at 1.0 now, but Context7/DeepWiki indices and training data
can still lag a recently-stabilized release (some indices at the time this
skill was written still showed `0.95.x`). Fetch current docs for the
version you're actually pinned to rather than recalling signatures or
trusting an index that predates 1.0:

```bash
# resolve the right Context7 library id
npx ctx7@latest library "iroh" "<your question>"

# query it — if the resolved id/version looks pre-1.0 (e.g. 0.9x), cross-
# check against docs.rs/iroh/1.0.2 (or your pinned 1.x version) directly
npx ctx7@latest docs /n0-computer/iroh "<your question>"
```

For architecture-level questions (not "what's the exact method signature"),
DeepWiki's Q&A over `n0-computer/iroh`, `n0-computer/iroh-blobs`,
`n0-computer/iroh-gossip`, and `n0-computer/iroh-docs` is a fast way to
cross-check design intent against the actual source.

## Common gotchas

| Gotcha | Fix |
| --- | --- |
| Generating a ticket right after `Endpoint::bind`/`connect` and it has no usable address info | `Endpoint` needs a moment to learn its relay/direct addresses; `await` `endpoint.online()` (or watch `endpoint.addr()`) before building a ticket to share |
| App hangs or peers aren't notified you went offline | Call `router.shutdown().await` (not just `std::process::exit`) for a clean shutdown that notifies peers |
| Copy-pasted example uses `NodeId`/`NodeAddr`/`MagicEndpoint`/a `Discovery` trait | That's the pre-rename API — translate to `EndpointId`/`EndpointAddr`/`Endpoint`/`AddressLookup`, or pin to the older crate version the example actually targets |
| `iroh-ffi` binding example doesn't compile against current core `iroh` docs | The FFI layer versions and renames independently from the core Rust crate — check `iroh-ffi`'s own README/tests, don't assume parity |
| Testing two endpoints locally and connections silently fall back to nothing / time out | You likely need `RelayMode::Custom` pointed at a locally spawned relay (`test-utils` feature, `iroh::test_utils::run_relay_server()`), plus `ca_tls_config(CaTlsConfig::insecure_skip_verify())` since the local relay uses a self-signed cert |
| Forcing a relay-only test path but direct connections keep sneaking in | Call `clear_ip_transports()` on the `Endpoint` builder to disable direct IP transports |
| `iroh-blobs`' ALPN string differs from what an older snippet shows | Use the crate's exported `iroh_blobs::ALPN` constant rather than hardcoding a byte string — it has changed across versions (e.g. legacy `/iroh-bytes/4`) |
| Treating `iroh-docs` as a text CRDT | It's a synced key-value replica (range-based set reconciliation), not free-form collaborative text merging — for that, use `iroh-automerge`/`iroh-automerge-repo` |
| Multiple protocols registered on one `Router` collide | Each `ProtocolHandler` is dispatched by its own unique ALPN string passed to `.accept(ALPN, handler)`; keep ALPNs namespaced (e.g. `b"myapp/thing/0"`) |

## Finding and vetting example repos — don't clone by default

`awesome-iroh` (`n0-computer/awesome-iroh`) is just a curated README of
links — **fetch the README, don't clone it**, to get the current list of
community projects (a condensed copy is in `references/ecosystem-examples.md`).

For any candidate project (from that list, `iroh-examples`, or elsewhere),
check whether it's already indexed before touching disk at all:

1. **DeepWiki** — `read_wiki_structure` / `ask_question` on `owner/repo`. If
   it returns real content, you can explore that repo's architecture and get
   cited code excerpts with zero clone.
2. **Context7** — `resolve-library-id` for the project/library name. If a
   match with meaningful code-snippet coverage shows up, you can pull
   targeted doc/code snippets the same way.

Only clone locally when you actually need to grep the full source, run it,
or step through it — not just to read it at a high level.

For the **official** n0-computer crates below, cloning is usually worth it
directly, since the point is almost always to grep real source rather than
get a Q&A summary:

```bash
mkdir -p ~/Dev/others/iroh-ref && cd ~/Dev/others/iroh-ref

git clone --depth 1 https://github.com/n0-computer/iroh              iroh
git clone --depth 1 https://github.com/n0-computer/iroh-examples      iroh-examples
git clone --depth 1 https://github.com/n0-computer/iroh-blobs         iroh-blobs
git clone --depth 1 https://github.com/n0-computer/iroh-gossip        iroh-gossip
git clone --depth 1 https://github.com/n0-computer/iroh-docs          iroh-docs
git clone --depth 1 https://github.com/n0-computer/sendme             sendme
git clone --depth 1 https://github.com/n0-computer/dumbpipe           dumbpipe
```

See `references/ecosystem-examples.md` for the full repo map and what's in
each one before deciding which to pull down for a given task.
