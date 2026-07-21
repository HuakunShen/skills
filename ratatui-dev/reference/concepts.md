# Core concepts

## Immediate-mode rendering

Ratatui has no retained widget tree and no diffing to think about. Every tick you:

1. Look at your own app state (a plain struct you own).
2. Call `terminal.draw(|frame| ui(frame, &app))`.
3. Inside that closure, construct widgets fresh (`List::new(...)`, `Gauge::default()...`) and
   `frame.render_widget(widget, area)` them into rectangular regions of the frame.
4. Ratatui diffs the resulting cell buffer against the previous frame internally and writes only
   the changed cells to the real terminal. You never touch that diffing — just redraw everything
   every frame from current state. This is what makes the mental model simple: if the UI looks
   wrong, it's because `ui(frame, &app)` computed the wrong thing from `app`, not because some
   stale widget wasn't invalidated.

Widgets are consumed by value when rendered (`Widget::render(self, area, buf)`) — construct them
right before rendering, don't try to keep them around across frames. State that *does* need to
persist across frames (list selection index, scroll offset, text-input cursor) lives in a
separate `*State` struct you own (`ListState`, `TableState`, `ScrollbarState`, or your own) and is
passed to `frame.render_stateful_widget(widget, area, &mut state)`.

## `Buffer` and `Cell`

The `Buffer` is the ground truth of what will be drawn: a `Rect area` plus a flat array of
`Cell`s, each with a `symbol` (the grapheme to display), `fg`/`bg` `Color`, and a `Modifier`
bitflags (`BOLD`, `ITALIC`, `UNDERLINED`, `DIM`, `CROSSED_OUT`, `REVERSED`, ...). Custom widgets
that need pixel-perfect control implement `Widget`/`StatefulWidget` and write directly into
buffer cells (`buf[(x, y)].set_symbol(...).set_fg(...)`) — see `reference/showcase-apps.md` §4
for real examples (bottom's `PipeGauge`, csvlens's spreadsheet grid). This skill's own SVG export
harness (`reference/svg-export.md`) works by reading a `Buffer` after a single `TestBackend`
render — it's the same data every widget ultimately produces.

## Layout: `Rect`, `Constraint`, `Flex`

```rust
use ratatui::layout::{Constraint, Direction, Flex, Layout};

let [header, body, footer] = Layout::vertical([
    Constraint::Length(3),   // fixed height
    Constraint::Min(0),      // takes remaining space
    Constraint::Length(1),
])
.areas(frame.area());

let [sidebar, main] = Layout::horizontal([
    Constraint::Percentage(30),
    Constraint::Fill(1),     // proportional remainder
])
.areas(body);
```

Constraint kinds: `Length(n)` (fixed cells), `Percentage(n)`, `Ratio(a, b)`, `Min(n)` /
`Max(n)` (bounds, absorbs remaining space), `Fill(weight)` (proportional remainder, preferred
over `Min(0)` in newer code for multiple flexible panes). Layout solves these with the same
cassowary constraint algorithm taskwarrior-tui borrows for its own table column widths (see
`reference/showcase-apps.md` §4) — it degrades gracefully rather than panicking when constraints
overconstrain a small terminal.

`Flex` controls how leftover space is distributed when constraints don't fill the area exactly —
`Flex::Legacy` (default), `Flex::Start`, `Flex::Center`, `Flex::End`, `Flex::SpaceBetween`,
`Flex::SpaceAround`. `Flex::Center` is the modern way to center a fixed-size popup:

```rust
fn center(area: Rect, h: Constraint, v: Constraint) -> Rect {
    let [area] = Layout::horizontal([h]).flex(Flex::Center).areas(area);
    let [area] = Layout::vertical([v]).flex(Flex::Center).areas(area);
    area
}
// center(frame.area(), Constraint::Percentage(60), Constraint::Length(7))
```

Always wrap outer layouts in `.margin(1)` (or inset specific widgets with
`area.inner(Margin::new(h, v))`) rather than letting borders touch the terminal edge or each
other — see `reference/aesthetics.md` §14 for why (scrollbar thumbs colliding with border corner
glyphs is the recurring bug this avoids).

## `Frame`, `Terminal`, backends

`Terminal<B: Backend>` owns the screen and double-buffers frames. `Backend` is the abstraction
over the actual I/O: `CrosstermBackend` (near-universal — 17/22 showcase apps use crossterm
directly, the rest transitively via `ratatui::crossterm`), `TermionBackend`, `TermwizBackend`,
and — critical for this skill's own tooling — `TestBackend`, which renders into an in-memory
`Buffer` with no real terminal/PTY at all. `TestBackend` is normally used for widget snapshot
tests; this skill also (ab)uses it to generate the SVG screenshots in `assets/svg/` headlessly.
See `examples/src/bin/render_gallery.rs`.

## Terminal setup / teardown — and panic safety

```rust
use ratatui::crossterm::{
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};

fn init_terminal() -> color_eyre::Result<Terminal<impl Backend>> {
    enable_raw_mode()?;
    execute!(std::io::stdout(), EnterAlternateScreen)?;
    Ok(Terminal::new(CrosstermBackend::new(std::io::stdout()))?)
}

fn restore_terminal() -> color_eyre::Result<()> {
    disable_raw_mode()?;
    execute!(std::io::stdout(), LeaveAlternateScreen)?;
    Ok(())
}
```

**The most common real-world bug class in the wild is a panic that skips `restore_terminal`**,
leaving the user's shell stuck in raw mode / the alternate screen — invisible input, garbled
prompt, "the tool broke my terminal". Fix it once, globally, with a panic hook installed *before*
`init_terminal`:

```rust
fn install_panic_hook() {
    let original = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let _ = restore_terminal(); // best-effort; terminal may already be restored
        original(info);
    }));
}
```

`color-eyre::install()` does this for you (plus pretty backtraces) and is why it appears in
~4 showcase apps specifically paired with `human-panic`. Always call
`install_panic_hook()`/`color_eyre::install()` first thing in `main`, before entering raw mode.

## The render loop, minimally

```rust
color_eyre::install()?;
let mut terminal = init_terminal()?;
let mut app = App::default();

let tick_rate = Duration::from_millis(250);
let mut last_tick = Instant::now();
while !app.should_quit {
    terminal.draw(|f| ui::draw(f, &app))?;
    let timeout = tick_rate.saturating_sub(last_tick.elapsed());
    if crossterm::event::poll(timeout)? {
        if let Event::Key(key) = crossterm::event::read()? {
            if key.kind == KeyEventKind::Press {
                app.handle_key(key);
            }
        }
    }
    if last_tick.elapsed() >= tick_rate {
        app.tick();
        last_tick = Instant::now();
    }
}
restore_terminal()?;
```

Filtering on `KeyEventKind::Press` matters on Windows and in terminals with the Kitty keyboard
protocol enabled — without it, key-release events double-fire every keypress. For richer
architectures (background threads, tokio), see `reference/showcase-apps.md` §2.
