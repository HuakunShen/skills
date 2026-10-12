---
name: webview-native-look
description: Use when a web UI hosted in an embedded WebView (WKWebView in an AppKit/Swift shell, Tauri, Electron) must look and behave like a native macOS app - real vibrancy / Liquid Glass materials, system accent colour, light/dark and OS-generation-aware styling, UI zoom, no "web page" tells (selection, scrollbars, overscroll), and a typed host bridge. Includes a runnable AppKit + WKWebView demo that verifies the technique, and a measured note on what does NOT work (the private -apple-visual-effect CSS property).
---

# WebView Native Look

Make a web UI feel native by splitting the job: **the native host paints materials, window
chrome, appearance, accent and OS version; the web layer paints content from a small token
set and removes every "this is a web page" tell.** Neither side imitates the other.

Complements `native-desktop-styling` (cross-platform component adaptation for macOS / WinUI /
GNOME). This skill is the macOS WebView mechanics underneath: how the host and page cooperate.

## Start here: run the demo

```bash
cd demo && ./verify.sh      # builds the Swift host, asserts the contract, writes screenshots
./run.sh                    # opens the demo window (add --backdrop glass | vibrancy | none)
./serve.sh                  # same page in a plain browser; Lab tab drives the host attributes by hand
```

`verify.sh` needs only Xcode command line tools. It must be run from a logged-in macOS session
(it launches a real window and uses `screencapture -l`). Read screenshots before claiming a
visual result: PASS lines prove the contract, not the look.

## The host contract (what the shell gives the page)

Set at document start (before first paint) on `<html>`; update live on appearance/accent change.

| Channel | Meaning | CSS/JS use |
| --- | --- | --- |
| `macos="27"` | OS major version | `:root[macos="26"] { --radius-window: 26px }` |
| `dark` | appearance | base colours switch; derived colours follow |
| `backdrop="vibrancy\|glass\|none"` | which native material sits behind the page | decides `glass` strategy |
| `--color-system-accent` | user's accent colour | `--accent: var(--color-system-accent, fallback)` |
| `--zoom` | UI scale | every size token is `round(calc(N * 1px * var(--zoom)), 1px)` |
| `ipcRequest` message handler | request/response RPC | `{id, method, data}` out, `window.__nativeHost.resolve(id, result, error)` back |

Full Swift/JS code and pitfalls: [references/host-contract.md](references/host-contract.md).

## The web layer (what the page does)

Everything is in `demo/web/native.css`; copy it as the starting point.

1. **Few base colours, derived scale.** Define `--bg --bg-secondary --fg --selection --accent`; derive
   alpha steps with relative colour syntax: `--fg-10: rgb(from var(--fg) r g b / 10%)`. A theme change is
   then a handful of variables.
2. **One zoom variable.** `--spx: calc(1px * var(--zoom))`; all sizes use `round(calc(N * var(--spx)), 1px)`.
3. **OS generation by attribute**, never by JS sniffing.
4. **WebView hygiene.** `user-select:none`, `cursor:default`, hidden scrollbars, `overscroll-behavior:none`,
   `overflow:hidden` on the body, `appearance:none` on controls; opt text back in only for
   `input`, `textarea`, `[data-selectable]`.
5. **Hairlines.** `--hairline: 0.5px` under `@media (resolution >= 2x)`.
6. **No first-paint animation.** `:root:not(.transitions-ready) * { transition:none }`; add the class after two `requestAnimationFrame`s.
7. **Materials by strategy** (`glass` attribute): `native` (host paints, page stays clear or lightly veiled) >
   `blur` (backdrop-filter) > `solid`. Honour `prefers-reduced-transparency`.

CSS recipes with the reasoning and browser-support floor: [references/css-recipes.md](references/css-recipes.md).

## Materials: what actually works (measured)

Tested on macOS 27.0 (26A428), Swift 6.4, a stock third-party WKWebView:

- **Works, reliable:** `NSVisualEffectView` behind a transparent WKWebView, and `NSGlassEffectView`
  (macOS 26+, Liquid Glass) with the web view as its `contentView`. Make the web view transparent with
  `setValue(false, forKey: "drawsBackground")` plus `underPageBackgroundColor = .clear`, window `isOpaque = false`, `backgroundColor = .clear`.
- **Does not work:** the private CSS property `-apple-visual-effect: -apple-system-glass-material`.
  `CSS.supports` is false for every value, even `none`; no public WKPreferences feature enables it;
  `UseSystemAppearance` does not either. A shipping launcher's CSS contains the property, but its
  native code only toggles unrelated experimental features, so treat the property as unavailable and
  feature-detect with `CSS.supports` if you want to use it opportunistically. Do not build on it.
- **Fallback chain:** `native` -> `blur` (backdrop-filter, blurs only what the page paints) -> `solid`.
- `glass` and `vibrancy` look different: in light mode the glass tint is noticeably darker. Pick per
  surface and look at screenshots in both appearances.

Evidence and probe commands: [references/findings.md](references/findings.md).

## Workflow for adopting this in an app

1. Add the host contract to the existing shell (do not rewrite it): transparent web view, backdrop view,
   document-start script, update on appearance/accent notifications, zoom menu items.
2. Introduce `native.css` tokens beside the existing design tokens; map existing variable names to the base set.
3. Replace opaque backgrounds on sidebars, palettes and cards with the strategy-aware classes.
4. Add a verification: attribute assertions (`--eval`) plus screenshots of each backdrop x appearance.
5. Keep a plain-browser path working so the UI can still be developed and tested without the host.

## Do not

- Copy another app's fonts, images, copy or code. Study its *techniques* (token structure, attribute
  strategy, hygiene rules) and re-implement them. Measure colours/radii from your own captures.
- Depend on private WebKit API for visuals the user must see. KVC `drawsBackground` is long-lived but
  private: guard it with `responds(to:)`, and keep the page legible if it silently fails.
- Sniff the platform in JS or the user-agent (the WKWebView UA says `Mac OS X 10_15_7` on every macOS).
- Animate on first paint, or leave text selectable/scrollbars visible by default.

## Other hosts (unverified here, same contract)

Tauri: `window-vibrancy` crate for the material, `initialization_script` for the attributes.
Electron: `BrowserWindow({ vibrancy, transparent: true })`, `webContents.executeJavaScript` or a preload.
Windows: Mica/Acrylic via the host; reuse the same `glass` strategy attribute. These mappings were
not run in this repo; verify before relying on them.
