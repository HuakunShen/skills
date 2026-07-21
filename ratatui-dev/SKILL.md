---
name: ratatui-dev
description: >-
  Build good-looking, feature-rich terminal user interfaces (TUIs) in Rust with ratatui
  (https://ratatui.rs) and crossterm. Covers layout (Constraint/Flex), every built-in widget
  (Block, List, Table, Tabs, Gauge, LineGauge, Sparkline, BarChart, Chart, Canvas, Calendar,
  Paragraph, Scrollbar), third-party widget crates (tui-textarea, tui-tree-widget,
  throbber-widgets-tui, tui-big-text, ratatui-image, tui-scrollview, and more), event-loop
  architecture (sync poll, mpsc-channel, tokio async/Elm-style), and — most importantly —
  concrete aesthetic techniques (theme structs, rounded/double/thick borders, gradient gauges,
  centered popups, styled tables, spinners, icons) mined from 22 real-world showcase apps
  (gitui, bottom, joshuto, television, taskwarrior-tui, csvlens, oxker, dua, trippy, xplr...).
  Includes a runnable cargo example gallery and pre-rendered SVG screenshots of every widget so
  you can see exactly what each pattern looks like before writing code. USE THIS SKILL whenever
  the task involves ratatui, tui-rs, building a Rust terminal UI/TUI, a CLI dashboard, a
  terminal-based tool with panels/widgets/keybindings, or improving the look of an existing
  ratatui app.
---

# Ratatui TUI development

Ratatui is an **immediate-mode** terminal UI library: every frame you redraw the whole screen
from your app state into a `Buffer` of styled cells; there is no retained widget tree, no
diffing you write yourself. This skill is about building TUIs that are both correct and
genuinely good-looking — most of the value here is aesthetic and architectural judgment mined
from real, polished apps, not just API syntax.

## Look before you build

`assets/svg/*.svg` are pre-rendered screenshots of every technique this skill teaches —
generated headlessly (no real terminal needed) straight from ratatui's own cell buffer, so the
colors/borders/layout are pixel-accurate, not an artist's impression. **Open the relevant SVG
before writing the equivalent code** — Markdown viewers render them inline, and the SVG itself
is real, readable `<text>` (not a raster image), so you can read it directly as text too.

| Preview | What it shows |
|---|---|
| `assets/svg/dashboard.svg` | The hero shot — tabs, gauge, line-gauge, service list, chart, sparkline, help bar composed into one polished screen. Start here. |
| `assets/svg/block_borders.svg` | Plain vs Rounded vs Double vs Thick borders and when to use each |
| `assets/svg/list_selection.svg`, `table_styling.svg`, `tabs_bar.svg` | Selection highlighting, header/row styling, icon+highlight tabs |
| `assets/svg/meters.svg`, `bar_chart.svg`, `line_chart.svg`, `canvas_radar.svg` | Gauge/LineGauge/Sparkline, BarChart, Chart, Canvas |
| `assets/svg/paragraph_wrap.svg`, `scrollbar.svg`, `popup_modal.svg` | Styled-span text, scrollbars, centered modal dialogs |
| `assets/svg/spinner.svg`, `big_text.svg`, `tree.svg` | Third-party widgets: throbber-widgets-tui, tui-big-text, tui-tree-widget |

The cargo project that generated them is `examples/` — it actually builds and runs
(`cargo run --bin render_gallery`), so treat it as ground truth, not illustrative pseudocode.
See `reference/svg-export.md` to regenerate after editing a scene, or add a new one.

## Route to the right reference

| Task | File |
|---|---|
| Layout system, `Rect`/`Constraint`/`Flex`, the render loop, `Buffer`/`Cell`, backends, terminal setup/teardown, panic handling | `reference/concepts.md` |
| Any built-in widget: `Block`, `List`, `Table`, `Tabs`, `Gauge`, `LineGauge`, `Sparkline`, `BarChart`, `Chart`, `Canvas`, `Calendar`, `Paragraph`, `Scrollbar` — API + styling options + pitfalls | `reference/widgets-builtin.md` |
| Third-party widget crates — text input, trees, images, spinners, big text, menus, scrollviews — what exists and when to reach for it instead of hand-rolling | `reference/widgets-third-party.md` |
| **Making it look good**: theme structs, border-type conventions, gradient/segmented gauges, popup centering + `Clear`, conditional/layered styling, table alternating rows, status bars, spinners, sub-cell-precision bars | `reference/aesthetics.md` |
| Structuring the app: sync poll loop vs mpsc-thread vs tokio/Elm `Action` reducer; which real apps use which; notable hand-built custom widgets | `reference/showcase-apps.md` |
| How the SVG screenshot pipeline works, regenerating after a change, adding a new demo scene | `reference/svg-export.md` |

## The five things to get right before anything else

1. **Never call `Color::Rgb(...)` ad hoc in render code.** Define a `Theme` struct with semantic
   fields once (`accent`, `border`, `border_focused`, `danger`...) and thread it everywhere. See
   `reference/aesthetics.md` §1 and `examples/src/theme.rs` for a working Catppuccin-based one.
2. **Default every panel to `BorderType::Rounded`; reserve a different border type (`Double` or
   `Thick`) exclusively for modals/focus.** A flat wall of identical square-cornered boxes is the
   #1 visual tell of an unpolished TUI.
3. **Restore the terminal on panic, not just on clean exit.** A crash that leaves the user's
   shell in raw mode / the alternate screen is the most common "this tool feels broken" bug.
   Use `color-eyre`'s panic hook (installed before `Terminal::new`) or an explicit
   `std::panic::set_hook` that calls `disable_raw_mode()` / `LeaveAlternateScreen` first. See
   `reference/concepts.md`.
4. **Pick your event-loop shape deliberately** (`reference/showcase-apps.md` §2) — a synchronous
   poll loop is the right default for a small tool; reach for the tokio/Action-reducer shape only
   once you're genuinely doing concurrent I/O (network, subprocess, filesystem watch) alongside
   rendering.
5. **`unicode-width` before you truncate/pad anything.** Any column/cell width math done in raw
   `char` counts breaks on wide (CJK) or zero-width (emoji, combining) characters. This is the
   #1 real-world crate dependency across the 22 showcase apps studied (see
   `reference/showcase-apps.md` §1) for exactly this reason.

## Reference apps on disk

Cleaned (git history and binary assets stripped), source-only copies of 21 real ratatui apps —
gitui, bottom, joshuto, xplr, taskwarrior-tui, television, oxker, csvlens, gpg-tui, binsider,
rainfrog, slumber, chess-tui, minesweep-rs, scope-tui, twozero48, dua, oatmeal, openapi-tui,
bandwhich, trippy — live alongside this skill at `~/Dev/others/ratatui-apps/` for direct
grepping/reading when `reference/showcase-apps.md`'s excerpts aren't enough context. Each
subfolder is a snapshot, not a live git clone — re-clone the relevant URL (listed in
`reference/showcase-apps.md`) if you need full history or intend to send a PR upstream.
