# Native Look demo

A tiny AppKit + WKWebView host (`host-macos/main.swift`, one file, no packages) and a static web page
(`web/`, no build) that together show the technique in `../SKILL.md`.

| Command | What it does |
| --- | --- |
| `./verify.sh` | Builds the host; asserts host attributes, backdrop strategy, accent, IPC round trip; writes 6 launcher screenshots (backdrop x appearance) to `.build/shots`. Exit code 1 if a check fails. |
| `./run.sh [--backdrop vibrancy\|glass\|none] [--appearance light\|dark\|system] [--url …]` | Opens the window. `⌘=` `⌘-` `⌘0` zoom. Change system appearance or accent while it runs: the page follows. |
| `./serve.sh` | Plain-browser mode on `localhost:8787`. Use the Lab tab to flip appearance, `macos`, material and zoom by hand. |

Env: `NATIVE_LOOK_BUILD_DIR` moves the build output (default `demo/.build`, ignored by git).

Pages (`?view=`): `launcher` (palette), `settings` (cards, switches, hotkey keycaps), `lab` (live host report and toggles).

## Files

- `web/native.css` - the reusable layer: tokens, derived colours, zoom, OS attributes, hygiene, materials. Copy this.
- `web/app.js` - the page side of the contract: `request()` IPC helper, material strategy choice, browser fallback, Lab.
- `host-macos/main.swift` - transparent web view, native material, document-start attributes, live updates, IPC, zoom, `--eval`, `--screenshot`.

## Reading the result

Open the screenshots and compare `launcher-vibrancy-*`, `launcher-glass-*`, `launcher-none-*`. `none` shows the
`blur`/`solid` fallback. The Lab tab's report lists which features this WebView supports; on the tested macOS 27 build
`-apple-visual-effect supported` is `false` (see `../references/findings.md`).

Requires macOS 13+ to build and run (`NSGlassEffectView` is used only when available, macOS 26+).
