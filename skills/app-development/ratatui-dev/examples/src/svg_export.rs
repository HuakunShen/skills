//! Renders a ratatui [`Buffer`] (the cell grid ratatui itself draws into) straight to a
//! self-contained SVG "terminal window" screenshot.
//!
//! Why not record a real terminal and convert the ANSI stream? Because a `Buffer` *is* the
//! ground truth of what ratatui would show — every fg/bg color, modifier and glyph is already
//! resolved, so there's no PTY, no ANSI parsing, no timing/animation-frame guessing involved.
//! Text stays real `<text>` content (not rasterized), so the SVG is greppable/legible to both
//! humans and other AIs, and it renders natively in any Markdown viewer that supports inline SVG.
//!
//! Usage: draw once into a `Terminal<TestBackend>`, then pass `terminal.backend().buffer()` to
//! [`buffer_to_svg`].

use ratatui::buffer::Buffer;
use ratatui::style::{Color, Modifier};

/// Pixel metrics tuned to look like a real monospace terminal at a comfortable reading size.
const FONT_SIZE: f32 = 15.0;
const CHAR_W: f32 = 9.0; // ~0.6 * font-size, typical monospace advance width
const LINE_H: f32 = 20.0;
const PAD: f32 = 14.0; // inner padding around the text grid
const TITLEBAR_H: f32 = 32.0;
const RADIUS: f32 = 12.0;

/// Catppuccin-Mocha–inspired palette. Chosen for a modern, elegant, high-contrast dark look
/// that reads well both on GitHub/dark and light Markdown viewers.
const BG: &str = "#1e1e2e";
const FG_DEFAULT: &str = "#cdd6f4";
const TITLEBAR_BG: &str = "#181825";
const TITLEBAR_TEXT: &str = "#6c7086";

fn named_color_hex(c: Color) -> &'static str {
    match c {
        Color::Reset => FG_DEFAULT,
        Color::Black => "#45475a",
        Color::Red => "#f38ba8",
        Color::Green => "#a6e3a1",
        Color::Yellow => "#f9e2af",
        Color::Blue => "#89b4fa",
        Color::Magenta => "#cba6f7",
        Color::Cyan => "#94e2d5",
        Color::Gray => "#bac2de",
        Color::DarkGray => "#585b70",
        Color::LightRed => "#fab4c5",
        Color::LightGreen => "#c3f5bd",
        Color::LightYellow => "#fcecc4",
        Color::LightBlue => "#b3d1fc",
        Color::LightMagenta => "#ddc6f9",
        Color::LightCyan => "#b8f0e6",
        Color::White => "#f5e0dc",
        _ => FG_DEFAULT,
    }
}

/// Standard xterm 256-color cube/ramp, blended toward hex strings.
fn indexed_color_hex(i: u8) -> String {
    if i < 16 {
        let named = [
            Color::Black,
            Color::Red,
            Color::Green,
            Color::Yellow,
            Color::Blue,
            Color::Magenta,
            Color::Cyan,
            Color::Gray,
            Color::DarkGray,
            Color::LightRed,
            Color::LightGreen,
            Color::LightYellow,
            Color::LightBlue,
            Color::LightMagenta,
            Color::LightCyan,
            Color::White,
        ];
        return named_color_hex(named[i as usize]).to_string();
    }
    if i >= 232 {
        let level = 8 + (i - 232) as u32 * 10;
        return format!("#{level:02x}{level:02x}{level:02x}");
    }
    let i = i - 16;
    let steps = [0u32, 95, 135, 175, 215, 255];
    let r = steps[(i / 36) as usize];
    let g = steps[((i / 6) % 6) as usize];
    let b = steps[(i % 6) as usize];
    format!("#{r:02x}{g:02x}{b:02x}")
}

fn color_hex(c: Color) -> String {
    match c {
        Color::Rgb(r, g, b) => format!("#{r:02x}{g:02x}{b:02x}"),
        Color::Indexed(i) => indexed_color_hex(i),
        other => named_color_hex(other).to_string(),
    }
}

fn escape_xml(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '&' => "&amp;".to_string(),
            '<' => "&lt;".to_string(),
            '>' => "&gt;".to_string(),
            '"' => "&quot;".to_string(),
            _ => c.to_string(),
        })
        .collect()
}

#[derive(Clone, PartialEq)]
struct CellStyle {
    fg: String,
    bg: Option<String>, // None => same as canvas background, no rect needed
    bold: bool,
    italic: bool,
    underline: bool,
    strike: bool,
    dim: bool,
}

fn cell_style(fg: Color, bg: Color, modifier: Modifier) -> CellStyle {
    let reversed = modifier.contains(Modifier::REVERSED);
    let (mut fg, mut bg) = (fg, bg);
    if reversed {
        std::mem::swap(&mut fg, &mut bg);
    }
    let fg_hex = if matches!(fg, Color::Reset) {
        FG_DEFAULT.to_string()
    } else {
        color_hex(fg)
    };
    let bg_hex = if matches!(bg, Color::Reset) {
        None
    } else {
        Some(color_hex(bg))
    };
    CellStyle {
        fg: fg_hex,
        bg: bg_hex,
        bold: modifier.contains(Modifier::BOLD),
        italic: modifier.contains(Modifier::ITALIC),
        underline: modifier.contains(Modifier::UNDERLINED),
        strike: modifier.contains(Modifier::CROSSED_OUT),
        dim: modifier.contains(Modifier::DIM),
    }
}

/// Render a ratatui [`Buffer`] to a complete, self-contained SVG document styled as a small
/// terminal window (rounded corners, macOS-style traffic-light dots, drop shadow, title bar).
pub fn buffer_to_svg(buffer: &Buffer, title: &str) -> String {
    let area = buffer.area;
    let cols = area.width as usize;
    let rows = area.height as usize;

    let grid_w = cols as f32 * CHAR_W;
    let grid_h = rows as f32 * LINE_H;
    let width = grid_w + PAD * 2.0;
    let height = grid_h + PAD * 2.0 + TITLEBAR_H;

    let mut body = String::new();

    for y in 0..rows {
        // --- background rects: group consecutive cells sharing the same effective bg ---
        let mut x = 0usize;
        while x < cols {
            let cell = &buffer[(area.x + x as u16, area.y + y as u16)];
            let style = cell_style(cell.fg, cell.bg, cell.modifier);
            let run_bg = style.bg.clone();
            let start = x;
            x += 1;
            while x < cols {
                let c2 = &buffer[(area.x + x as u16, area.y + y as u16)];
                let s2 = cell_style(c2.fg, c2.bg, c2.modifier);
                if s2.bg != run_bg {
                    break;
                }
                x += 1;
            }
            if let Some(bg) = run_bg {
                let rx = PAD + start as f32 * CHAR_W;
                let ry = TITLEBAR_H + PAD + y as f32 * LINE_H;
                let rw = (x - start) as f32 * CHAR_W;
                body.push_str(&format!(
                    "<rect x=\"{rx:.1}\" y=\"{ry:.1}\" width=\"{rw:.1}\" height=\"{LINE_H:.1}\" fill=\"{bg}\"/>\n"
                ));
            }
        }

        // --- text runs: group consecutive cells sharing fg + modifiers ---
        let mut x = 0usize;
        while x < cols {
            let cell = &buffer[(area.x + x as u16, area.y + y as u16)];
            let style = cell_style(cell.fg, cell.bg, cell.modifier);
            let start = x;
            let mut text = String::new();
            loop {
                let c = &buffer[(area.x + x as u16, area.y + y as u16)];
                let s = cell_style(c.fg, c.bg, c.modifier);
                if s.fg != style.fg
                    || s.bold != style.bold
                    || s.italic != style.italic
                    || s.underline != style.underline
                    || s.strike != style.strike
                    || s.dim != style.dim
                {
                    break;
                }
                let sym = c.symbol();
                text.push_str(if sym.is_empty() { " " } else { sym });
                x += 1;
                if x >= cols {
                    break;
                }
            }
            if !text.trim().is_empty() || text.contains(|c: char| c != ' ') {
                let tx = PAD + start as f32 * CHAR_W;
                let ty = TITLEBAR_H + PAD + y as f32 * LINE_H + LINE_H * 0.74;
                let mut extra = String::new();
                if style.bold {
                    extra.push_str(" font-weight=\"600\"");
                }
                if style.italic {
                    extra.push_str(" font-style=\"italic\"");
                }
                let mut decos = vec![];
                if style.underline {
                    decos.push("underline");
                }
                if style.strike {
                    decos.push("line-through");
                }
                if !decos.is_empty() {
                    extra.push_str(&format!(" text-decoration=\"{}\"", decos.join(" ")));
                }
                let opacity = if style.dim { " opacity=\"0.6\"" } else { "" };
                // Force the run to occupy exactly its grid width regardless of which font a
                // given glyph (braille, box-drawing, emoji, nerd-font icon, CJK) actually falls
                // back to in the viewer — without this, mixed-width fallback fonts silently
                // drift the whole row out of alignment or get clipped by the rounded-corner
                // clip-path.
                let run_cols = text.chars().count();
                let text_len = run_cols as f32 * CHAR_W;
                body.push_str(&format!(
                    "<text x=\"{tx:.1}\" y=\"{ty:.1}\" textLength=\"{text_len:.1}\" lengthAdjust=\"spacingAndGlyphs\" fill=\"{}\"{extra}{opacity} xml:space=\"preserve\">{}</text>\n",
                    style.fg,
                    escape_xml(&text)
                ));
            }
            // else: a whitespace-only run needs no <text> element. `x` was already advanced
            // past it by the inner loop above — do NOT advance it again here (that was the bug:
            // it silently ate the first cell of whatever run came next).
        }
    }

    format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0}" height="{height:.0}" viewBox="0 0 {width:.0} {height:.0}" font-family="'JetBrains Mono','Fira Code',ui-monospace,'SF Mono',Consolas,'DejaVu Sans Mono',monospace" font-size="{FONT_SIZE}">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
    <clipPath id="clip"><rect x="0" y="0" width="{width:.0}" height="{height:.0}" rx="{RADIUS}" ry="{RADIUS}"/></clipPath>
  </defs>
  <g filter="url(#shadow)">
    <rect x="0" y="0" width="{width:.0}" height="{height:.0}" rx="{RADIUS}" ry="{RADIUS}" fill="{BG}"/>
  </g>
  <g clip-path="url(#clip)">
    <rect x="0" y="0" width="{width:.0}" height="{TITLEBAR_H:.0}" fill="{TITLEBAR_BG}"/>
    <circle cx="18" cy="{half_tb:.0}" r="6" fill="#f38ba8"/>
    <circle cx="38" cy="{half_tb:.0}" r="6" fill="#f9e2af"/>
    <circle cx="58" cy="{half_tb:.0}" r="6" fill="#a6e3a1"/>
    <text x="{cx:.0}" y="{ty:.0}" fill="{TITLEBAR_TEXT}" font-size="12.5" text-anchor="middle">{title_esc}</text>
    <rect x="0" y="0" width="{width:.0}" height="{height:.0}" fill="{BG}" fill-opacity="0"/>
    <g>
{body}    </g>
  </g>
</svg>
"##,
        half_tb = TITLEBAR_H / 2.0,
        cx = width / 2.0,
        ty = TITLEBAR_H / 2.0 + 4.5,
        title_esc = escape_xml(title),
    )
}
