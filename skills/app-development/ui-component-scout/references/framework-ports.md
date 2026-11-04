# React / Vue / Svelte / Solid: component and motion compatibility

This Skill's catalog is **React-first**, but site selection must respect target framework. Similar visual names do not imply compatible code or matching APIs. Always inspect the selected component's official source and framework version.

## Port status terminology

| Label | Meaning | Recommendation policy |
|---|---|---|
| `native` | Library documents and distributes this exact framework implementation | Prefer it first |
| `official-port` | Maintainer/official ecosystem publishes a framework-specific implementation | Good choice, still compare parity/version |
| `community-port` | Independent maintainer implemented analogous component | Review license, dependencies, freshness and API differences |
| `needs-port` | No verifiable target implementation | Treat as visual reference; estimate conversion work |
| `unknown` | Docs/index alone do not establish status | Do not claim ready-to-install |

For a component absent from the native framework, “same CSS but different JS” is not enough when it uses complex React hooks, refs, portals, Motion or SSR assumptions.

## Source guidance by framework

### React (primary)

- Existing Kunkun environment: React 19, Tailwind, shadcn/ui, shadcn-studio, WKWebView. Preserve original shadcn design tokens and compatibility with React 19.
- Foundation: [shadcn/ui](https://ui.shadcn.com/), [Kibo UI](https://www.kibo-ui.com/), [assistant-ui](https://www.assistant-ui.com/), [AI Elements](https://ai-sdk.dev/elements/overview), [React Flow](https://reactflow.dev/), [TanStack Table](https://tanstack.com/table/latest).
- Motion: [Animate UI](https://animate-ui.com/), [Motion Primitives](https://motion-primitives.com/), [Eased](https://eased.dev/), [UI Layouts](https://www.ui-layouts.com/).
- Signature: [Cult](https://www.cult-ui.com/), [Kokonut](https://kokonutui.com/), [Fancy](https://www.fancycomponents.dev/).
- Showpiece: [React Bits](https://reactbits.dev/), [Magic UI](https://magicui.design/), [Aceternity](https://ui.aceternity.com/), [Planes](https://useplanes.com/).

### Vue 3 / Nuxt

- Foundation: [shadcn-vue](https://www.shadcn-vue.com/) and its underlying Vue primitives; confirm Nuxt/SSR compatibility.
- Rich component visual: [nxui](https://nxui.geoql.in/docs) is *native Vue* and strong in node diagram, podcast, dashboard table. Never paste its code into a React app without conversion.
- Animation: [Inspira UI](https://docs.inspira-ui.com/docs/en) and [Vue Bits](https://vue-bits.dev/), which shares React Bits visual goals in Vue; registry https://vue-bits.dev/r/registry.json . Its `/llms.txt` was invalid HTML at check time, so use registry/docs.
- [Animate UI Vue](https://animate-ui.com/docs/vue) is an officially documented Vue offering; verify **the exact desired component** exists there. The presence of Vue docs does not guarantee API parity for every React component.

### Svelte 5 / SvelteKit

- Foundation: [shadcn-svelte](https://www.shadcn-svelte.com/); use Svelte runes/state and SSR-safe component construction.
- Signature/animations: [Svelte Bits](https://sveltebits.xyz/) with [registry JSON](https://sveltebits.xyz/r/registry.json), e.g. Dock. `/llms.txt` was 404 at check time.
- Lighter variants: [Ori UI](https://oriui.app/), e.g. Liquid Button; docs may be more relevant than an absent `llms.txt`.
- Graphing: [Svelte Flow](https://svelteflow.dev/) for actual node-edge editor. If working in SvelteKit, confirm browser-only animation initialization is confined to client lifecycle.
- If converting React-only effect: port design tokens and CSS independently; replace hooks/Framer Motion/browser refs with Svelte-native motion primitives and events. Measure actual code cost; prefer available Svelte port.

### SolidJS / SolidStart

- Foundation: [solidcn](https://solidcn.dev/) with [registry](https://solidcn.dev/r/registry.json), using Solid-specific accessibility primitives.
- Signature: [MagicUI Solid](https://axuj.github.io/magicui-solid/) (community port) offers Animated Beam/Bento-style examples; check independent repository activity and license.
- Avoid assuming JSX syntax makes React code compatible: Solid's fine-grained reactivity, cleanup, event handlers and refs differ. React's runtime and hook dependencies should not be introduced just to display a decorative card.
- `solidcn` `/llms.txt` returned HTML SPA at check time; registry and official source are safer.

## Conversion checklist

1. Verify library's official supported frameworks and exact component route.
2. Check version of package, TypeScript, Tailwind, SSR and animation engine.
3. Find the nearest native design-system primitive (dialog, tooltip, combobox, portal, focus manager).
4. Port **appearance/tokens** first and map states/interactions explicitly; do not translate React hooks mechanically.
5. Preserve accessibility and keyboard behavior; test Escape, Arrow navigation, Tab and focus return.
6. Isolate heavy canvas/WebGL work behind client-only lifecycle and reduced-motion fallback.
7. Record `native / official-port / community-port / needs-port / unknown` on each recommendation.
8. Review licensing for the original and the port (both can matter), and do not copy Pro code or claim licensed redistributability.

## Relevant functionality is often framework-independent

Real implementations usually need a core engine/API regardless of UI framework:

- Network policy graph: routing events + node/edge schema; React Flow or Svelte Flow for visualization, not a decorative animated beam.
- Audio: HTMLMediaElement, Media Chrome, WaveSurfer or another verified compatible playback/waveform engine.
- Charts: ECharts, D3, Recharts/Tremor, Visx or framework wrapper as appropriate; validate bundle size and SSR.
- AI chat: transport, streaming, tool results and transcript persistence; changing a Chat component won't build those backend features.
- Computer Use: OS/browser input driver and permissions; demo cursor is merely a front-end demonstration.

Choose functional plumbing separately, then a framework-native presentation layer.
