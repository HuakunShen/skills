// thiserror errors in the contract layer: every #[error] is a complete sentence, and the error itself is wire data.
// From xross-dev/crates/contract/xross-transfer-contract/src/protocol.rs:356-370 (read 2026-10-05).
// Note the derive list: the error is Serialize + Deserialize + Clone + PartialEq at once -
// in the contract layer, errors are types that cross the wire; consumers branch on variants, never parse messages.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize, thiserror::Error)]
pub enum OfferRejection {
    #[error("an offer must name what it is sending")]
    EmptyName,
    #[error("the name exceeds {max_bytes} bytes (got {actual_bytes})")]
    NameTooLong {
        max_bytes: usize,
        actual_bytes: usize,
    },
    #[error("that is a path or an escape sequence, not a name")]
    NameIsNotAName,
    #[error("a file is one blob and a tree is a hash sequence; this offer crosses them")]
    FormatDoesNotMatchPayload,
}

// ❌ Counterexample (constructed, not repository code):
// #[error("invalid")]              // no informative label
// #[error("{0}")]                  // passing a string through is letting consumers parse messages
