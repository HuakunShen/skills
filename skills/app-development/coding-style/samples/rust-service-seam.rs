//! The module header is the architecture statement: the reusable core is a crate, not a module.
//! From xross-dev/crates/contract/xross-service-host/src/lib.rs:1-12 (read 2026-10-05).
//! This is the Rust shape of the "split core logic into a library" preference - linking the same service crate
//! into a daemon / standalone bin / mobile app is a build decision, not a rewrite.
//! The seam a service is written against.
//!
//! A service names this crate and nothing else. It never names `xross-fabric`,
//! `iroh` or `tonic`, which is what lets the same service crate be linked into
//! the daemon, run as its own binary, or embedded in a native app — that is a
//! build decision, not a rewrite. See docs/adr/0001-process-boundaries.md.
//!
//! It is also why a service compiles in seconds: the iroh, quinn and rustls tree
//! is most of this workspace's build time and nothing here pulls it in.

mod operation;
