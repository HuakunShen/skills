// Domain errors in a reusable library crate: #[non_exhaustive] + #[from] to absorb source errors + per-domain section banners.
// From localsend-rs/src/error.rs:1-30 (read 2026-10-05; the full enum has six sections - I/O / Network /
// Protocol / Transfer / Auth / HTTP Status - 2-5 variants each; only the first two are shown here).
// The localsend-rs library itself uses zero anyhow - anyhow appears only in src/cli/commands/*, src/tui/, src/main.rs.
use thiserror::Error;

/// Errors that can occur when using LocalSend
#[derive(Error, Debug)]
#[non_exhaustive]
pub enum LocalSendError {
    // ============================================================================
    // I/O and System Errors
    // ============================================================================
    #[error("IO error: {source}")]
    Io {
        #[from]
        source: std::io::Error,
    },

    #[error("Serde JSON error: {source}")]
    Serde {
        #[from]
        source: serde_json::Error,
    },

    // ============================================================================
    // Network Errors
    // ============================================================================
    #[error("HTTP client error: {source}")]
    Reqwest {
        #[from]
        source: reqwest::Error,
    },
}
