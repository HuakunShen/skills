---
name: harmonyos-app-patterns
description: >-
  Working patterns for building real HarmonyOS NEXT / OpenHarmony apps in ArkTS +
  ArkUI, extracted from a shipping production app (a Clash proxy client with a Go
  native core). Covers the whole stack: bottom navbar / tab shells, adaptive
  breakpoints, Navigation + NavPathStack routing, theme colour and dark mode
  (ThemeControl / CustomTheme / setColorMode), background blur and material,
  multi-language switching (i18n.System.setAppPreferredLanguage) and the resource
  qualifier system, app-wide animation-speed settings, transitions, gestures,
  haptics, state management (V1 vs V2), preferences / RDB / file persistence,
  LazyForEach data sources, background keep-alive (backgroundTaskManager continuous
  tasks), VpnExtensionAbility, notifications and Live View, PiP, service widgets
  (服务卡片), WebView bridging, and the native layer — NAPI, threadsafe functions,
  cross-compiling Go/C++ for OHOS, the libX.so type-shim packaging trick, and
  cross-process IPC. USE THIS SKILL whenever the task touches HarmonyOS,
  OpenHarmony, 鸿蒙, ArkTS, ArkUI, .ets files, DevEco Studio, hvigor/hvigorw, ohpm,
  module.json5, oh-package.json5, HAP/HAR/HSP, UIAbility, or any HarmonyOS Kit
  (@kit.ArkUI, @kit.AbilityKit, @kit.NetworkKit, …) — including when the user only
  describes a feature ("底部导航栏", "多语言", "深色模式", "主题色", "背景模糊",
  "动画速度", "后台保活", "调用 so 库", "NAPI 绑定") without naming the platform.
  HarmonyOS open-source examples are scarce, so prefer these verified patterns over
  improvising from Android/iOS/web habits.
---

# HarmonyOS app patterns

Field-tested patterns from a shipping HarmonyOS NEXT app: ArkTS + ArkUI front end,
multi-module (HAP + HAR), Go proxy core reached through NAPI, VPN extension, service
widgets, four locales, and a user-facing appearance system.

**Baseline:** stage model, `compatibleSdkVersion 5.0.5(17)` → `targetSdkVersion 6.0.0(20)`,
`deviceTypes: [phone, tablet, 2in1]`.

## Read this first

**Before writing your first `.ets` file, load the `arkts-grammar-standards` skill.** ArkTS
is not TypeScript — it forbids computed property names, array-destructuring declarations,
`prototype` access, dot-access on `Record`/index-signature types, structural typing, and
`any`. This skill teaches *architecture*; that one teaches what the compiler will accept.
Use `arkts-error-fixes` when a build fails and `arkts-runtime-fix` for crashes.

The single most common trap: **object literals need string-literal keys and bracket
access.**

```ets
const M: Record<string, number> = { ['sm']: 1, ['md']: 2 }   // ✓ ArkTS
const M: Record<string, number> = { sm: 1, md: 2 }           // ✗ rejected
M['sm']                                                       // ✓
M.sm                                                          // ✗ rejected
{ [SomeEnum.A]: x }                                           // ✗ computed key, rejected
```

Three further facts shape everything else. Getting them wrong produces code that compiles
and then misbehaves.

1. **Pick a state model and stay in it.** The source app is **ArkTS state V1**
   (`@State`/`@Prop`/`@Link`/`@Provide`/`@Consume`/`@StorageLink`) with essentially zero V2.
   Mixing V1 and V2 in one tree breaks the links between them silently. For new projects
   prefer **V2** (`@ComponentV2`/`@Local`/`@Param`/`@ObservedV2`+`@Trace`) — it fixes the
   deep-mutation and `Map` blind spots V1 works around with clone hacks. See
   `references/state-and-data.md` before writing a component.

2. **One persisted config object is the spine.** A single `UIConfig` class holds theme,
   dark mode, animation speed, blur, haptics, tab style, and language; it is registered once
   via `PersistentStorage.persistProp('uiConfig', …)` and read everywhere as
   `@StorageLink('uiConfig')`. Nearly every user-facing appearance feature is a field on it
   plus a helper that reads it. Design that object first.

3. **`null` is a first-class "off" value.** `animateTo(null, cb)`, `.transition(null)`,
   `.clickEffect(null)` all mean "no animation". That's what lets a global
   animation-speed setting be one early return in a helper rather than a branch at every
   call site.

## Route to the right reference

Load only what the task needs.

| Task | File |
|---|---|
| Bottom navbar, tab bar, floating pill bar, adaptive breakpoints, safe area, `Navigation`/`NavPathStack` routing, page scaffold, collapsing title | `references/ui-shell-navigation.md` |
| Theme/accent colour, `ThemeControl`/`CustomTheme`/`WithTheme`, dark mode, `color.json` conventions, blur & material, app icons | `references/theming-appearance.md` |
| Multi-language switching, locale tags, resource qualifier folders, `$r` vs resolved string, format placeholders, adding a string | `references/i18n-resources.md` |
| Animation-speed setting, curves, transitions, `geometryTransition`, sheets/dialogs/menus/popups, list performance, symbol effects, haptics & sound, `@Extend`/`@Styles` | `references/animation-interaction.md` |
| State V1 vs V2, `AppStorage`, event bus, preferences/RDB/files, `BaseDataSource<T>` for `LazyForEach`, HTTP/`rcp` networking | `references/state-and-data.md` |
| UIAbility lifecycle, background keep-alive, VPN, notifications & Live View, PiP, backup, permissions, service widgets | `references/background-abilities-widgets.md` |
| NAPI, threadsafe functions, promises from native, CMake, cross-compiling Go for OHOS, the `libX.so` shim, HAR packaging, cross-process IPC | `references/native-ffi-napi.md` |
| Embedding `Web`, `WebMessagePort` bridging, serving bundled assets, theme/language into a page | `references/webview-bridge.md` |
| Module layout, `build-profile.json5`, `module.json5`, kits, linting, build & `hdc` commands | `references/project-setup.md` |
| **ArkTS syntax legality — what the compiler accepts** | skill `arkts-grammar-standards` (load first) |
| A build error you don't recognise | skill `arkts-error-fixes` |
| Crash / 闪退 / white screen at runtime | skill `arkts-runtime-fix` |

## Verify APIs before writing them

HarmonyOS APIs moved considerably between API 12 and API 20, and training data is thin and
often stale. **Fetch current docs rather than recalling signatures** — particularly for
`ThemeControl`/`CustomTheme`, material and blur enums, Live View, PiP, background task
modes, and anything in `@kit.NetworkKit`.

```bash
npx ctx7@latest library "HarmonyOS" "<your question>"
npx ctx7@latest docs /websites/developer_huawei_consumer_cn_doc_harmonyos-guides "<your question>"
```

Two compile-time allies worth leaning on: `$r('sys.symbol.*')` names are validated at build
time, so a wrong glyph fails the build rather than rendering blank; and `canIUse('SystemCapability.…')`
guards capability-scoped APIs at runtime. Use both.

## What this codebase does not demonstrate

Be honest about the gaps rather than inventing an implementation:

- **Graded immersive material (沉浸光感材质/等级)** — not present. The app has a blur
  on/off boolean with hardcoded values. `references/theming-appearance.md` sketches the
  `backgroundEffect` approach, but verify the current enums against docs.
- **Runtime dynamic app icons** — only a static `layered_image.json`. Icon *switching* is a
  separate API; look it up.
- **The theme engine itself** — `Xb_ChangeThemeColor` / `Xb_ColorModeManager` live in an
  un-checked-out submodule. The reference gives the real `ThemeControl` / `setColorMode`
  implementation instead of the opaque wrapper.
- **App enumeration** — HarmonyOS gates it behind a privileged permission, so the app builds
  its per-app list from system-share ingestion, a community database, and manual entry.
- Also absent: `PageTransition`, custom Navigation transitions, `keyframeAnimateTo`,
  `AttributeModifier`, `stateStyles`, `bindContentCover`, `SideBarContainer`, HDS/`@hadss`
  components, `pasteboard`, plural resources.

## Learn from its bugs too

The references flag real defects in the source app because they are the failure modes an AI
is most likely to reproduce. The recurring ones:

- **Scrim/blur flags set on open but not reset on every dismissal path** → app stuck blurred.
- **Hardcoded durations inside animation helpers** → the user's speed setting silently ignored.
- **`http.createHttp()` without `destroy()` in a `finally`** → one leak per call.
- **`"EOF"` as a socket frame delimiter + a single fixed-size read** → corruption and silent
  truncation. Length-prefix instead.
- **Ordinal-coupled RPC enums duplicated in two languages** → inserting a member reroutes
  every later call.
- **`requestPermissionsFromUser` result ignored** → "dialog shown" mistaken for "granted".
- **Empty `onConfigurationUpdate`** → stale colour mode forever.
- **`.d.ts` declarations that don't match the native exports** → garbage across the FFI seam.
- **Committed signing credentials** in `build-profile.json5`. Never do this; if you forked
  this repo, rotate them.

When you touch code near one of these, fix it rather than matching the surrounding style.

## Working in this repo specifically

- `git submodule update --init` first, or a few dozen `Xb_*` symbols won't resolve.
- Native artifacts under `proxy_core/libs/<abi>/` are prebuilt and committed; only
  `arm64-v8a` is present although `abiFilters` also lists `x86_64`.
- `.ts` files skip the ArkTS linter (`code-linter.json5` matches `**/*.ets` only) — that's
  where `any` and object spread live.
