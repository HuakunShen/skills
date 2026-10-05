// unsafe at FFI boundaries: every unsafe fn carries a # Safety section stating caller obligations; errors crossing the boundary become a closed enum.
// From xross-dev/crates/contract/xross-capability-port/src/lib.rs:105-130 (read 2026-10-05).
// This crate is the FFI contract layer where unsafe is concentrated; pure-logic/contract/crypto crates are all #![forbid(unsafe_code)].
    pub fn borrowing(bytes: &[u8]) -> Self {
        Self {
            ptr: bytes.as_ptr(),
            len: bytes.len(),
        }
    }

    /// Copy into an owned `Vec`.
    ///
    /// # Safety
    ///
    /// `ptr` must be valid for `len` bytes, or `len` must be zero. The caller is
    /// asserting the borrow described above still holds.
    pub unsafe fn to_vec(self) -> Vec<u8> {
        if self.len == 0 || self.ptr.is_null() {
            return Vec::new();
        }
        unsafe { std::slice::from_raw_parts(self.ptr, self.len) }.to_vec()
    }
}

/// How a native operation ended.
///
/// A small closed set rather than a passthrough of the platform's own error, so
/// that a capability cannot smuggle a platform string into a place a peer reads.
/// The *message* travels separately and is the capability's business.
