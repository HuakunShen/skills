//! Every scene in the gallery: one `fn(&mut Frame)` per built-in or third-party widget/technique,
//! plus a combined "dashboard" hero scene. `render_gallery` (src/bin/render_gallery.rs) draws
//! each into a `TestBackend` of the given size and exports it to SVG via `svg_export`.

use ratatui::layout::{Alignment, Constraint, Flex, Layout, Margin, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::symbols;
use ratatui::text::{Line, Span, Text};
use ratatui::widgets::{
    Bar, BarChart, BarGroup, Block, BorderType, Cell, Clear, Gauge, LineGauge, List, ListItem,
    ListState, Padding, Paragraph, Row, Scrollbar, ScrollbarOrientation, ScrollbarState,
    Sparkline, Table, TableState, Tabs, Wrap,
};
use ratatui::widgets::canvas::{Canvas, Line as CanvasLine, Points};
use ratatui::widgets::{Axis, Chart, Dataset, GraphType};
use ratatui::Frame;

use crate::theme::THEME;

pub struct Scene {
    pub id: &'static str,
    pub title: &'static str,
    pub width: u16,
    pub height: u16,
    pub draw: fn(&mut Frame),
}

pub fn all() -> Vec<Scene> {
    vec![
        Scene { id: "block_borders", title: "Block border styles", width: 78, height: 16, draw: block_borders },
        Scene { id: "list_selection", title: "List — selection + icons", width: 46, height: 16, draw: list_selection },
        Scene { id: "table_styling", title: "Table — header + row styling", width: 70, height: 14, draw: table_styling },
        Scene { id: "tabs_bar", title: "Tabs — icons + highlight", width: 60, height: 6, draw: tabs_bar },
        Scene { id: "meters", title: "Gauge, LineGauge, Sparkline", width: 60, height: 12, draw: meters },
        Scene { id: "bar_chart", title: "BarChart", width: 60, height: 16, draw: bar_chart },
        Scene { id: "line_chart", title: "Chart — line + scatter", width: 70, height: 20, draw: line_chart },
        Scene { id: "canvas_radar", title: "Canvas — braille scatter", width: 50, height: 22, draw: canvas_radar },
        Scene { id: "paragraph_wrap", title: "Paragraph — styled spans + wrap", width: 60, height: 12, draw: paragraph_wrap },
        Scene { id: "scrollbar", title: "Scrollbar", width: 40, height: 14, draw: scrollbar_demo },
        Scene { id: "popup_modal", title: "Centered popup / modal", width: 60, height: 18, draw: popup_modal },
        Scene { id: "spinner", title: "throbber-widgets-tui spinner", width: 40, height: 6, draw: spinner_demo },
        Scene { id: "big_text", title: "tui-big-text banner", width: 60, height: 10, draw: big_text_demo },
        Scene { id: "tree", title: "tui-tree-widget", width: 44, height: 16, draw: tree_demo },
        Scene { id: "dashboard", title: "Dashboard — combined hero shot", width: 96, height: 30, draw: dashboard },
    ]
}

fn styled_block(title: &str, border: BorderType, border_color: ratatui::style::Color) -> Block<'static> {
    Block::bordered()
        .border_type(border)
        .border_style(Style::new().fg(border_color))
        .title(Span::styled(format!(" {title} "), Style::new().fg(THEME.text).add_modifier(Modifier::BOLD)))
        .title_alignment(Alignment::Left)
        .style(Style::new().bg(THEME.base))
}

// ---------------------------------------------------------------------------------------------
fn block_borders(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let cols = Layout::horizontal([Constraint::Ratio(1, 2); 2]).split(area);
    let left = Layout::vertical([Constraint::Ratio(1, 2); 2]).split(cols[0]);
    let right = Layout::vertical([Constraint::Ratio(1, 2); 2]).split(cols[1]);

    let specs: [(&str, BorderType, ratatui::style::Color, &str); 4] = [
        ("Plain — base panels", BorderType::Plain, THEME.surface2, "Default panel chrome"),
        ("Rounded — soft default", BorderType::Rounded, THEME.blue, "Most apps default every\npanel to Rounded for a\nuniformly soft look."),
        ("Double — reserved for modals", BorderType::Double, THEME.accent, "A distinct border type\nsignals \"this is a dialog\",\nnot just another panel."),
        ("Thick — focused / active", BorderType::Thick, THEME.green, "Swap Plain→Thick when a\npanel gains focus instead\nof only recoloring it."),
    ];
    let areas = [left[0], right[0], left[1], right[1]];
    for (area, (title, border, color, body)) in areas.into_iter().zip(specs) {
        let block = styled_block(title, border, color);
        let inner = block.inner(area);
        f.render_widget(block, area);
        f.render_widget(
            Paragraph::new(body).style(Style::new().fg(THEME.subtext)).wrap(Wrap { trim: true }),
            inner.inner(Margin::new(1, 0)),
        );
    }
}

// ---------------------------------------------------------------------------------------------
fn list_selection(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let block = styled_block("Files", BorderType::Rounded, THEME.surface2);
    let items = [
        // Plain single-width Unicode symbols rather than Nerd Font glyphs or emoji: Nerd Font
        // icons only render inside a terminal configured with a patched font (tofu boxes
        // elsewhere), and double-width emoji glyphs need correct wide-character cell accounting
        // that many simple buffer->image renderers (this one included) don't special-case — a
        // portable reference SVG is better served by narrow symbols every monospace font ships.
        ("▪", "README.md", THEME.text),
        ("▸", "src/", THEME.blue),
        ("●", "main.rs", THEME.yellow),
        ("●", "svg_export.rs", THEME.yellow),
        ("◆", "Cargo.toml", THEME.peach),
        ("○", ".git/", THEME.subtext),
        ("□", "assets/", THEME.green),
    ];
    let list_items: Vec<ListItem> = items
        .iter()
        .map(|(icon, name, color)| {
            ListItem::new(Line::from(vec![
                Span::styled(format!("{icon} "), Style::new().fg(*color)),
                Span::styled(*name, Style::new().fg(THEME.text)),
            ]))
        })
        .collect();
    let list = List::new(list_items)
        .block(block)
        .highlight_symbol("▸ ")
        .highlight_style(Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD));
    let mut state = ListState::default();
    state.select(Some(2));
    f.render_stateful_widget(list, area, &mut state);
}

// ---------------------------------------------------------------------------------------------
fn table_styling(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let header = Row::new(vec![
        Cell::from("Name\ntype: text"),
        Cell::from("Status\ntype: enum"),
        Cell::from("Latency\ntype: f64"),
    ])
    .style(Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD))
    .height(2);

    let rows_data = [
        ("api-gateway", "healthy", "12ms", THEME.green),
        ("auth-service", "healthy", "8ms", THEME.green),
        ("billing-worker", "degraded", "340ms", THEME.yellow),
        ("search-index", "down", "—", THEME.red),
        ("cache-node-1", "healthy", "1ms", THEME.green),
    ];
    let rows: Vec<Row> = rows_data
        .iter()
        .enumerate()
        .map(|(i, (name, status, latency, color))| {
            let bg = if i % 2 == 0 { THEME.base } else { THEME.surface0 };
            Row::new(vec![
                Cell::from(*name).style(Style::new().fg(THEME.text)),
                Cell::from(*status).style(Style::new().fg(*color).add_modifier(Modifier::BOLD)),
                Cell::from(*latency).style(Style::new().fg(THEME.subtext)),
            ])
            .style(Style::new().bg(bg))
        })
        .collect();

    let table = Table::new(rows, [Constraint::Length(16), Constraint::Length(12), Constraint::Length(10)])
        .header(header)
        .block(styled_block("Services", BorderType::Rounded, THEME.surface2))
        .row_highlight_style(Style::new().bg(THEME.surface1).add_modifier(Modifier::BOLD))
        .highlight_symbol("▸ ");
    let mut state = TableState::default();
    state.select(Some(2));
    f.render_stateful_widget(table, area, &mut state);
}

// ---------------------------------------------------------------------------------------------
fn tabs_bar(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let titles = ["▸ Overview", "◆ Metrics", "▪ Logs", "⚙ Settings"];
    let tabs = Tabs::new(titles.map(|t| Span::styled(t, Style::new().fg(THEME.subtext))))
        .block(styled_block("", BorderType::Rounded, THEME.surface2))
        .highlight_style(Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD))
        .select(1)
        .divider(Span::styled(" │ ", Style::new().fg(THEME.surface2)))
        .padding(" ", " ");
    f.render_widget(tabs, area);
}

// ---------------------------------------------------------------------------------------------
fn meters(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let rows = Layout::vertical([Constraint::Length(3), Constraint::Length(3), Constraint::Length(3), Constraint::Min(0)])
        .split(area);

    let gauge = Gauge::default()
        .block(styled_block("CPU", BorderType::Rounded, THEME.surface2))
        .gauge_style(Style::new().fg(THEME.green).bg(THEME.surface0))
        .label(Span::styled("62%", Style::new().fg(THEME.text).add_modifier(Modifier::BOLD)))
        .ratio(0.62);
    f.render_widget(gauge, rows[0]);

    let line_gauge = LineGauge::default()
        .block(styled_block("Memory", BorderType::Rounded, THEME.surface2))
        .filled_style(Style::new().fg(THEME.yellow))
        .unfilled_style(Style::new().fg(THEME.surface1))
        .filled_symbol("━")
        .unfilled_symbol("─")
        .ratio(0.81)
        .label(Span::styled("81% · 12.9/16 GiB", Style::new().fg(THEME.subtext)));
    f.render_widget(line_gauge, rows[1]);

    let data: Vec<u64> = vec![2, 4, 3, 6, 9, 7, 8, 12, 10, 14, 11, 9, 13, 15, 12, 10, 8, 6, 9, 11];
    let sparkline = Sparkline::default()
        .block(styled_block("Requests / sec", BorderType::Rounded, THEME.surface2))
        .data(&data)
        .style(Style::new().fg(THEME.blue));
    f.render_widget(sparkline, rows[2]);
}

// ---------------------------------------------------------------------------------------------
fn bar_chart(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let data = [("Mon", 42u64), ("Tue", 58), ("Wed", 31), ("Thu", 67), ("Fri", 74), ("Sat", 22), ("Sun", 18)];
    let colors = [THEME.blue, THEME.teal, THEME.green, THEME.yellow, THEME.peach, THEME.pink, THEME.accent];
    let bars: Vec<Bar> = data
        .iter()
        .zip(colors)
        .map(|((label, value), color)| {
            Bar::default()
                .label(Line::from(*label))
                .value(*value)
                .text_value(value.to_string())
                .style(Style::new().fg(color))
                .value_style(Style::new().fg(THEME.base).bg(color).add_modifier(Modifier::BOLD))
        })
        .collect();
    let chart = BarChart::default()
        .block(styled_block("Deploys this week", BorderType::Rounded, THEME.surface2))
        .data(BarGroup::new(bars))
        .bar_width(7)
        .bar_gap(2);
    f.render_widget(chart, area);
}

// ---------------------------------------------------------------------------------------------
fn line_chart(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let p95: Vec<(f64, f64)> = (0..30).map(|i| (i as f64, 40.0 + 20.0 * (i as f64 * 0.35).sin() + i as f64 * 0.4)).collect();
    let p50: Vec<(f64, f64)> = (0..30).map(|i| (i as f64, 18.0 + 6.0 * (i as f64 * 0.5).cos())).collect();

    let datasets = vec![
        Dataset::default()
            .name("p95")
            .marker(symbols::Marker::Braille)
            .graph_type(GraphType::Line)
            .style(Style::new().fg(THEME.peach))
            .data(&p95),
        Dataset::default()
            .name("p50")
            .marker(symbols::Marker::Braille)
            .graph_type(GraphType::Line)
            .style(Style::new().fg(THEME.teal))
            .data(&p50),
    ];
    let chart = Chart::new(datasets)
        .block(styled_block("Latency (ms) — last 30 min", BorderType::Rounded, THEME.surface2))
        .x_axis(
            Axis::default()
                .style(Style::new().fg(THEME.surface2))
                .bounds([0.0, 29.0])
                .labels(["0m", "15m", "30m"].map(|l| Span::styled(l, Style::new().fg(THEME.subtext)))),
        )
        .y_axis(
            Axis::default()
                .style(Style::new().fg(THEME.surface2))
                .bounds([0.0, 90.0])
                .labels(["0", "45", "90"].map(|l| Span::styled(l, Style::new().fg(THEME.subtext)))),
        )
        .legend_position(Some(ratatui::widgets::LegendPosition::TopRight));
    f.render_widget(chart, area);
}

// ---------------------------------------------------------------------------------------------
fn canvas_radar(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let points: Vec<(f64, f64)> = (0..40)
        .map(|i| {
            let t = i as f64 * 0.9;
            let r = 6.0 + 3.0 * (t * 0.7).sin();
            (r * t.cos(), r * t.sin())
        })
        .collect();
    let canvas = Canvas::default()
        .block(styled_block("Canvas — braille scatter", BorderType::Rounded, THEME.surface2))
        .marker(symbols::Marker::Braille)
        .x_bounds([-12.0, 12.0])
        .y_bounds([-12.0, 12.0])
        .paint(move |ctx| {
            ctx.draw(&Points { coords: &points, color: THEME.teal });
            ctx.draw(&CanvasLine { x1: -12.0, y1: 0.0, x2: 12.0, y2: 0.0, color: THEME.surface2 });
            ctx.draw(&CanvasLine { x1: 0.0, y1: -12.0, x2: 0.0, y2: 12.0, color: THEME.surface2 });
            ctx.print(-11.5, 11.0, Line::from(Span::styled("origin-centered polar spiral", Style::new().fg(THEME.subtext))));
        });
    f.render_widget(canvas, area);
}

// ---------------------------------------------------------------------------------------------
fn paragraph_wrap(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let text = Text::from(vec![
        Line::from(vec![
            Span::styled("Deploy ", Style::new().fg(THEME.text)),
            Span::styled("#4821", Style::new().fg(THEME.accent).add_modifier(Modifier::BOLD)),
            Span::styled(" finished ", Style::new().fg(THEME.text)),
            Span::styled("successfully", Style::new().fg(THEME.green).add_modifier(Modifier::BOLD)),
            Span::styled(".", Style::new().fg(THEME.text)),
        ]),
        Line::from(""),
        Line::from(Span::styled(
            "Compose long-form status text from styled spans instead of one flat string — each \
             span carries its own color/weight, and Paragraph wraps the whole Line as a unit.",
            Style::new().fg(THEME.subtext),
        )),
        Line::from(""),
        Line::from(vec![
            Span::styled("⚠ ", Style::new().fg(THEME.yellow)),
            Span::styled("2 warnings", Style::new().fg(THEME.yellow)),
            Span::styled("  ", Style::new()),
            Span::styled("✗ ", Style::new().fg(THEME.red)),
            Span::styled("0 errors", Style::new().fg(THEME.red)),
        ]),
    ]);
    let p = Paragraph::new(text)
        .block(styled_block("Build log", BorderType::Rounded, THEME.surface2).padding(Padding::horizontal(1)))
        .wrap(Wrap { trim: true });
    f.render_widget(p, area);
}

// ---------------------------------------------------------------------------------------------
fn scrollbar_demo(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let block = styled_block("Changelog", BorderType::Rounded, THEME.surface2);
    let inner = block.inner(area);
    f.render_widget(block, area);
    let lines: Vec<Line> = (1..=40)
        .map(|i| Line::from(Span::styled(format!("v0.{i}.0 — routine maintenance release"), Style::new().fg(THEME.subtext))))
        .collect();
    let total = lines.len();
    f.render_widget(Paragraph::new(lines).scroll((14, 0)), inner);

    let mut sb_state = ScrollbarState::new(total).position(14);
    let scrollbar = Scrollbar::new(ScrollbarOrientation::VerticalRight)
        .symbols(symbols::scrollbar::Set { track: " ", thumb: "█", begin: "▲", end: "▼" })
        .style(Style::new().fg(THEME.accent));
    f.render_stateful_widget(scrollbar, area.inner(Margin { vertical: 1, horizontal: 0 }), &mut sb_state);
}

// ---------------------------------------------------------------------------------------------
fn popup_modal(f: &mut Frame) {
    let area = f.area();
    // dimmed base layout behind the modal
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let base = styled_block("Deploy pipeline", BorderType::Rounded, THEME.surface1);
    let inner = base.inner(area);
    f.render_widget(base, area);
    let ghost_lines: Vec<Line> = (0..inner.height)
        .map(|i| Line::from(Span::styled(format!("stage-{i:02} ......... queued"), Style::new().fg(THEME.surface2))))
        .collect();
    f.render_widget(Paragraph::new(ghost_lines), inner);

    // centered popup, double border to visually distinguish it from a regular panel
    let popup = center(area, Constraint::Percentage(60), Constraint::Length(7));
    f.render_widget(Clear, popup);
    let popup_block = Block::bordered()
        .border_type(BorderType::Double)
        .border_style(Style::new().fg(THEME.accent))
        .title(Span::styled(" Confirm ", Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD)))
        .style(Style::new().bg(THEME.surface0));
    let popup_inner = popup_block.inner(popup);
    f.render_widget(popup_block, popup);
    let msg = Paragraph::new(vec![
        Line::from(Span::styled("Deploy build #4821 to production?", Style::new().fg(THEME.text))),
        Line::from(""),
        Line::from(vec![
            Span::styled(" Y ", Style::new().fg(THEME.base).bg(THEME.green).add_modifier(Modifier::BOLD)),
            Span::raw("  confirm    "),
            Span::styled(" N ", Style::new().fg(THEME.base).bg(THEME.red).add_modifier(Modifier::BOLD)),
            Span::raw("  cancel"),
        ]),
    ])
    .alignment(Alignment::Center)
    .wrap(Wrap { trim: true });
    f.render_widget(msg, popup_inner);
}

fn center(area: Rect, h: Constraint, v: Constraint) -> Rect {
    let [area] = Layout::horizontal([h]).flex(Flex::Center).areas(area);
    let [area] = Layout::vertical([v]).flex(Flex::Center).areas(area);
    area
}

// ---------------------------------------------------------------------------------------------
fn spinner_demo(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let block = styled_block("Syncing…", BorderType::Rounded, THEME.surface2);
    let inner = block.inner(area);
    f.render_widget(block, area);
    let throbber = throbber_widgets_tui::Throbber::default()
        .label("Fetching 1,204 objects")
        .style(Style::new().fg(THEME.subtext))
        .throbber_style(Style::new().fg(THEME.teal).add_modifier(Modifier::BOLD))
        .throbber_set(throbber_widgets_tui::BRAILLE_SIX)
        .use_type(throbber_widgets_tui::WhichUse::Spin);
    let mut state = throbber_widgets_tui::ThrobberState::default();
    for _ in 0..5 {
        state.calc_next();
    }
    f.render_stateful_widget(throbber, inner, &mut state);
}

// ---------------------------------------------------------------------------------------------
fn big_text_demo(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);
    let big = tui_big_text::BigTextBuilder::default()
        .pixel_size(tui_big_text::PixelSize::Quadrant)
        .style(Style::new().fg(THEME.accent))
        .lines(vec![Line::from("RATATUI")])
        .build();
    f.render_widget(big, area);
}

// ---------------------------------------------------------------------------------------------
fn tree_demo(f: &mut Frame) {
    use tui_tree_widget::{Tree, TreeItem, TreeState};
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);

    let items = vec![
        TreeItem::new(
            "src",
            "src/",
            vec![
                TreeItem::new_leaf("main", "main.rs"),
                TreeItem::new_leaf("svg", "svg_export.rs"),
                TreeItem::new(
                    "scenes",
                    "scenes/",
                    vec![TreeItem::new_leaf("widgets", "widgets.rs"), TreeItem::new_leaf("theme", "theme.rs")],
                )
                .unwrap(),
            ],
        )
        .unwrap(),
        TreeItem::new_leaf("cargo", "Cargo.toml"),
        TreeItem::new_leaf("readme", "README.md"),
    ];

    let mut state = TreeState::default();
    state.open(vec!["src"]);
    state.select(vec!["src", "scenes"]);

    let tree = Tree::new(&items)
        .unwrap()
        .block(styled_block("Project tree", BorderType::Rounded, THEME.surface2))
        .highlight_style(Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD))
        .highlight_symbol("▸ ");
    f.render_stateful_widget(tree, area, &mut state);
}

// ---------------------------------------------------------------------------------------------
fn dashboard(f: &mut Frame) {
    let area = f.area();
    f.render_widget(ratatui::widgets::Block::default().style(Style::new().bg(THEME.base)), area);

    let outer = Layout::vertical([Constraint::Length(3), Constraint::Min(0), Constraint::Length(1)])
        .split(area);

    // header / tabs
    let titles = ["▸ Overview", "◆ Metrics", "▪ Logs", "● Alerts"];
    let tabs = Tabs::new(titles.map(|t| Span::styled(t, Style::new().fg(THEME.subtext))))
        .block(Block::bordered().border_type(BorderType::Rounded).border_style(Style::new().fg(THEME.surface2)))
        .highlight_style(Style::new().fg(THEME.base).bg(THEME.accent).add_modifier(Modifier::BOLD))
        .select(1)
        .divider(Span::styled("│", Style::new().fg(THEME.surface2)))
        .padding(" ", " ");
    f.render_widget(tabs, outer[0]);

    let body = Layout::horizontal([Constraint::Percentage(38), Constraint::Percentage(62)]).split(outer[1]);
    let left = Layout::vertical([Constraint::Length(3), Constraint::Length(3), Constraint::Min(0)]).split(body[0]);
    let right = Layout::vertical([Constraint::Percentage(55), Constraint::Percentage(45)]).split(body[1]);

    f.render_widget(
        Gauge::default()
            .block(styled_block("CPU", BorderType::Rounded, THEME.surface2))
            .gauge_style(Style::new().fg(THEME.green).bg(THEME.surface0))
            .label(Span::styled("47%", Style::new().fg(THEME.text).add_modifier(Modifier::BOLD)))
            .ratio(0.47),
        left[0],
    );
    f.render_widget(
        LineGauge::default()
            .block(styled_block("Memory", BorderType::Rounded, THEME.surface2))
            .filled_style(Style::new().fg(THEME.peach))
            .unfilled_style(Style::new().fg(THEME.surface1))
            .filled_symbol("━")
            .unfilled_symbol("─")
            .ratio(0.68),
        left[1],
    );

    let services = [
        ("api-gateway", THEME.green, "●"),
        ("auth-service", THEME.green, "●"),
        ("billing-worker", THEME.yellow, "●"),
        ("search-index", THEME.red, "●"),
        ("cache-node-1", THEME.green, "●"),
        ("cache-node-2", THEME.green, "●"),
    ];
    let list_items: Vec<ListItem> = services
        .iter()
        .map(|(name, color, dot)| {
            ListItem::new(Line::from(vec![
                Span::styled(format!("{dot} "), Style::new().fg(*color)),
                Span::styled(*name, Style::new().fg(THEME.text)),
            ]))
        })
        .collect();
    f.render_widget(
        List::new(list_items)
            .block(styled_block("Services", BorderType::Rounded, THEME.surface2))
            .highlight_symbol("▸ ")
            .highlight_style(Style::new().bg(THEME.surface1).add_modifier(Modifier::BOLD)),
        left[2],
    );

    let p95: Vec<(f64, f64)> = (0..30).map(|i| (i as f64, 40.0 + 20.0 * (i as f64 * 0.35).sin() + i as f64 * 0.3)).collect();
    let p50: Vec<(f64, f64)> = (0..30).map(|i| (i as f64, 16.0 + 5.0 * (i as f64 * 0.5).cos())).collect();
    let datasets = vec![
        Dataset::default().name("p95").marker(symbols::Marker::Braille).graph_type(GraphType::Line).style(Style::new().fg(THEME.peach)).data(&p95),
        Dataset::default().name("p50").marker(symbols::Marker::Braille).graph_type(GraphType::Line).style(Style::new().fg(THEME.teal)).data(&p50),
    ];
    let chart = Chart::new(datasets)
        .block(styled_block("Latency (ms)", BorderType::Rounded, THEME.surface2))
        .x_axis(Axis::default().style(Style::new().fg(THEME.surface2)).bounds([0.0, 29.0]))
        .y_axis(Axis::default().style(Style::new().fg(THEME.surface2)).bounds([0.0, 90.0]).labels(["0", "45", "90"].map(|l| Span::styled(l, Style::new().fg(THEME.subtext)))))
        .legend_position(Some(ratatui::widgets::LegendPosition::TopRight));
    f.render_widget(chart, right[0]);

    let data: Vec<u64> = vec![4, 8, 6, 12, 18, 14, 16, 24, 20, 28, 22, 18, 26, 30, 24, 20, 16, 12, 18, 22, 26, 30, 28, 24];
    f.render_widget(
        Sparkline::default()
            .block(styled_block("Requests / sec", BorderType::Rounded, THEME.surface2))
            .data(&data)
            .style(Style::new().fg(THEME.blue)),
        right[1],
    );

    let help = Line::from(vec![
        Span::styled(" q ", Style::new().fg(THEME.base).bg(THEME.subtext)),
        Span::styled(" quit  ", Style::new().fg(THEME.subtext)),
        Span::styled(" tab ", Style::new().fg(THEME.base).bg(THEME.subtext)),
        Span::styled(" switch  ", Style::new().fg(THEME.subtext)),
        Span::styled(" r ", Style::new().fg(THEME.base).bg(THEME.subtext)),
        Span::styled(" refresh", Style::new().fg(THEME.subtext)),
    ]);
    f.render_widget(Paragraph::new(help), outer[2]);
}
