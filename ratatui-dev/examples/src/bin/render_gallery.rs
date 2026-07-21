//! Renders every scene in `ratatui_gallery::scenes::all()` to a headless `TestBackend`, then
//! exports each resulting buffer to a standalone SVG "terminal screenshot" via `svg_export`.
//! No real terminal, PTY, or display is required — this is why the whole pipeline works in a
//! plain CI/build-script context. Run with: `cargo run --bin render_gallery`.

use ratatui::backend::TestBackend;
use ratatui::Terminal;
use ratatui_gallery::{scenes, svg_export};
use std::fs;
use std::path::Path;

fn main() -> std::io::Result<()> {
    let out_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../assets/svg");
    fs::create_dir_all(&out_dir)?;

    for scene in scenes::all() {
        let backend = TestBackend::new(scene.width, scene.height);
        let mut terminal = Terminal::new(backend).expect("terminal");
        terminal.draw(|f| (scene.draw)(f)).expect("draw");
        let buffer = terminal.backend().buffer();
        let svg = svg_export::buffer_to_svg(buffer, scene.title);
        let path = out_dir.join(format!("{}.svg", scene.id));
        fs::write(&path, svg)?;
        println!("wrote {}", path.display());
    }
    Ok(())
}
