//! A single semantic `Theme` struct threaded through every scene, rather than calling
//! `Color::Rgb(...)` ad hoc in render code. This mirrors the pattern found in gitui
//! (`SharedTheme`), bottom (swappable Nord/Gruvbox presets) and television (17 TOML palettes) —
//! see `reference/aesthetics.md`. Palette: Catppuccin Mocha.

use ratatui::style::Color;

pub struct Theme {
    pub base: Color,
    pub surface0: Color,
    pub surface1: Color,
    pub surface2: Color,
    pub text: Color,
    pub subtext: Color,
    pub accent: Color,   // mauve
    pub blue: Color,
    pub green: Color,
    pub yellow: Color,
    pub peach: Color,
    pub red: Color,
    pub teal: Color,
    pub pink: Color,
}

pub const THEME: Theme = Theme {
    base: Color::Rgb(0x1e, 0x1e, 0x2e),
    surface0: Color::Rgb(0x31, 0x32, 0x44),
    surface1: Color::Rgb(0x45, 0x47, 0x5a),
    surface2: Color::Rgb(0x58, 0x5b, 0x70),
    text: Color::Rgb(0xcd, 0xd6, 0xf4),
    subtext: Color::Rgb(0xa6, 0xad, 0xc8),
    accent: Color::Rgb(0xcb, 0xa6, 0xf7),
    blue: Color::Rgb(0x89, 0xb4, 0xfa),
    green: Color::Rgb(0xa6, 0xe3, 0xa1),
    yellow: Color::Rgb(0xf9, 0xe2, 0xaf),
    peach: Color::Rgb(0xfa, 0xb3, 0x87),
    red: Color::Rgb(0xf3, 0x8b, 0xa8),
    teal: Color::Rgb(0x94, 0xe2, 0xd5),
    pink: Color::Rgb(0xf5, 0xc2, 0xe7),
};
