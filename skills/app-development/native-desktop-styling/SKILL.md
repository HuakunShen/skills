---
name: native-desktop-styling
description: Use when adapting an existing desktop UI to distinct macOS, Windows WinUI/Fluent, and Linux desktop styles, especially when platform themes only change colors and corner radii. Relevant to Tauri/Electron webviews, shared Svelte/React/shadcn components, Tailwind, and equivalent native frontends.
---

# Native Desktop Styling

Make the same product feel at home on each platform through hierarchy, control
anatomy, spacing and interaction feedback. Preserve business logic and shared
accessible primitives. This is a visual adaptation, not a framework migration.

## Establish the target

Read the existing shell, startup flow, shared controls, theme persistence,
stylesheet entry points and native window configuration. Identify actual host
OS separately from the selected visual style. Select a Linux reference explicitly:
GNOME/libadwaita and KDE/Breeze are different targets; GNOME is a useful initial
choice when the user has no preference, not a universal Linux standard.

Use existing approval and references. If concepts are requested, compare the
same screen, data, viewport and theme across platforms. Generated concepts guide
hierarchy; correct their text, icons, disabled states and window controls during
implementation. Do not invent product features to match an image.

## Platform contract

| Surface | macOS | Windows / WinUI | Linux / GNOME |
| --- | --- | --- | --- |
| Shell | Unified compact toolbar; split view | Native title area; page heading and command actions | Header bar with centered title; larger controls |
| Navigation | Compact grouped source list | Roomier rows; vertical selection indicator | Solid sidebar; rounded selection rows; symbolic icons |
| Forms | Compact controls; aligned horizontal labels where appropriate | Labels above fields; clear content groups | Generous fields and grouped preferences |
| Contents | Dense rows; file/folder symbols | Clear primary/secondary text; square selection controls | Comfortable rows; sturdy symbolic controls |
| Materials | Quiet separators; restrained translucent chrome | Flat layered surfaces; subtle control strokes | Solid surfaces; modest raised controls |

Adapt these patterns to the product. Respect brand/accent preferences and user
accessibility density; avoid tying the density preference to one OS.

## Keep responsibility local

- Global CSS owns semantic colors, font stacks and material tokens, including
  matching light/dark overrides. Components own geometry and platform classes.
- Prefer Tailwind platform variants in existing shadcn components. Add small
  presentation components for genuinely different header or form structures.
  Keep callbacks, state, keyboard behavior and accessible semantics shared.
- Reuse relevant navigation and controls across startup, workspace, settings and
  menus. Preserve intentionally different navigation flows; share primitives
  rather than inventing navigation. A root style attribute reaches portals too.
- Keep owned baseline styles below utilities in explicit CSS layers. Unlayered
  CSS outranks layered utilities, regardless of selector specificity.

For Tailwind 4 implementation examples, cascade diagnosis, host detection and
responsive geometry, read [the implementation reference](references/implementation.md).

## Verify the rendered result

Exercise manual style selection, saved preferences, automatic host selection,
light/dark/system modes, density, focus, disabled states, startup/cancel, selection,
menus, hidden sidebar, hidden panels, resizing and zoom. Add behavior tests for
new preference/detection rules; use screenshots and measured DOM geometry for
visual layout, rather than tests that merely search for class strings.

Check the compiled utility rules and computed styles. Measure that removing a
panel gives its sibling the full available width, and that narrow SVG wrappers
retain nonzero height. Capture comparable actual screenshots and run relevant
type checks/builds. Rebuild the embedded frontend before a native shell build,
then launch the exact generated application. Report browser simulation separately
from native OS validation, especially fonts, caption placement and drag regions.
