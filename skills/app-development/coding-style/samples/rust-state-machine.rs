// State machine: data-carrying discriminated enum + Result<Self> transition methods - illegal transitions are errors, not panics.
// From localsend-rs/src/core/transfer.rs:44-62 (read 2026-10-05).
pub fn accept(self, session_id: SessionId) -> Result<Self> {
    match self {
        Self::WaitingForAcceptance { sender, files, .. } => Ok(Self::Transferring {
            session_id,
            sender: sender.alias,
            files,
            completed: HashSet::new(),
        }),
        _ => Err(LocalSendError::invalid_state(
            "Cannot accept transfer from current state",
        )),
    }
}

/// Reject the transfer
