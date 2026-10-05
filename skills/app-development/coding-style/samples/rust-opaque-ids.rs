// Newtype IDs: validated at construction, generated in batches by macro.
// From xross-interop-lab/impl/crates/interop-contract/src/ids.rs:1-60 (read 2026-10-05).
// Note: this is xross-interop-lab - the only observed Rust repo with extensive Chinese comments (the contract layer follows the design docs' language);
// Rust comments everywhere else are English. Comment strings below are translated from the Chinese originals.
//! Opaque local identifier newtypes (docs/05 §1).
//!
//! All public IDs are unguessable local opaque strings: they carry no path/token/remote address.
//! Shape constraint: `[A-Za-z0-9._-]{1,64}` and must not start with `.`. Production values come from a runtime CSPRNG;
//! this crate only validates shape (readable values like `ofr_demo` are for fixtures only).

use serde::{Deserialize, Serialize};
use std::fmt;

macro_rules! opaque_id {
    ($(#[$doc:meta])* $name:ident) => {
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(String);

        impl $name {
            /// Shape check: 1..=64 chars, `[A-Za-z0-9._-]`, must not start with `.` (blocks `..` / hidden semantics).
            fn validate(s: &str) -> Result<(), &'static str> {
                if s.is_empty() || s.len() > 64 {
                    return Err("ID length must be in 1..=64");
                }
                if s.starts_with('.') {
                    return Err("ID must not start with .");
                }
                if !s
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
                {
                    return Err("ID allows only [A-Za-z0-9._-]");
                }
                Ok(())
            }
        }

        impl TryFrom<String> for $name {
            type Error = &'static str;
            fn try_from(s: String) -> Result<Self, Self::Error> {
                Self::validate(&s)?;
                Ok(Self(s))
            }
        }

        impl<'a> TryFrom<&'a str> for $name {
            type Error = &'static str;
            fn try_from(s: &'a str) -> Result<Self, Self::Error> {
                Self::validate(s)?;
                Ok(Self(s.to_string()))
            }
        }

        impl AsRef<str> for $name {
            fn as_ref(&self) -> &str {
                &self.0
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str(&self.0)
            }
        }
    };
}
