# UI library directory: where to look first

**Catalog checked 2026-11-04**. This is a usable yellow pages of libraries, not an endorsement of every example. “LLMS valid” means the research checked Markdown/text rather than a 200-HTML SPA shell. “Context7 ID” means the exact index ID was resolved then; unknown ≠ unavailable. Recheck current official docs and per-component license/tier before copying code.

## Routing by intent

| Need | First places to browse | Why |
|---|---|---|
| Professional React/shadcn **foundation** | [shadcn/ui](https://ui.shadcn.com/), [Shadcn Studio](https://shadcnstudio.com/), [Kibo UI](https://www.kibo-ui.com/) | Real menus, forms, trees, data structures, functional media controls |
| Beautiful **animated primitives** | [Animate UI](https://animate-ui.com/), [Motion Primitives](https://motion-primitives.com/), [Eased UI](https://eased.dev/), [UI Layouts](https://www.ui-layouts.com/) | Polished open/close, morph, overlays, selected-state transitions |
| **AI chat / assistant / agent sessions** | [SmoothUI](https://smoothui.dev/), [Kokonut UI](https://kokonutui.com/), [Eased UI](https://eased.dev/), [assistant-ui](https://www.assistant-ui.com/), [AI Elements](https://ai-sdk.dev/elements/overview) | Agent lanes, thinking states, citations, prompt composers, tool statuses; Streamdown for streaming source code |
| **Unusual cards, branded variants** | [Cult UI](https://www.cult-ui.com/), [Fancy Components](https://www.fancycomponents.dev/) | Cutout/Folded/Organic, tactile media and cursor interactions |
| **Landing wow, shader, cinematic hero** | [React Bits](https://reactbits.dev/), [Aceternity UI](https://ui.aceternity.com/), [Magic UI](https://magicui.design/), [Planes](https://useplanes.com/) | Electric Border, laser, crystalized ball, beams, liquid glass |
| **Data table, nested groups, large dashboard** | [Shadcn Studio](https://shadcnstudio.com/), [Kibo UI](https://www.kibo-ui.com/), [TanStack Table](https://tanstack.com/table/latest), [Tremor](https://www.tremor.so/) | Real data semantics and controls, not just animations |
| **Editable graph/flow/network** | [React Flow](https://reactflow.dev/), [React Flow UI](https://reactflow.dev/ui), [Svelte Flow](https://svelteflow.dev/), [nxui](https://nxui.geoql.in/docs) | Graph engine + animated edges; nxui is particularly good as Vue visual reference |
| **Audio/video/transcript** | [Kibo UI](https://www.kibo-ui.com/), [Kokonut UI](https://kokonutui.com/), [nxui](https://nxui.geoql.in/docs), [WaveSurfer.js](https://wavesurfer.xyz/), [Video.js](https://videojs.org/) | Actual player transport, timeline/trimmer UI, podcast appearance |
| **Vue/Nuxt** | [Inspira UI](https://docs.inspira-ui.com/docs/en), [Vue Bits](https://vue-bits.dev/), [nxui](https://nxui.geoql.in/docs), [shadcn-vue](https://www.shadcn-vue.com/) | Native/ported Vue code |
| **Svelte/SvelteKit** | [Svelte Bits](https://sveltebits.xyz/), [Ori UI](https://oriui.app/), [shadcn-svelte](https://www.shadcn-svelte.com/) | Svelte-native alternative instead of React copy-paste |
| **Solid** | [solidcn](https://solidcn.dev/), [MagicUI Solid](https://axuj.github.io/magicui-solid/) | Solid-specific primitives or community showpiece ports |

## Catalog and documentation matrix

Counts below are **rows in the bundled 2026-11-04 snapshot**, not current official site totals; a site can have more entries than a partial machine-readable index. For libraries absent from the 2,661 raw rows, standout examples live in `curated.json`.

| Source | Primary framework | Offline rows | llms.txt status (at check) | Resolved Context7 ID |
|---|---|---:|---|---|
| [React Bits](https://reactbits.dev/) | React | 447 | [valid](https://www.reactbits.dev/llms.txt) | `/davidhdev/react-bits` |
| [nxui](https://nxui.geoql.in/docs) | Vue | 366 | [valid](https://nxui.geoql.in/llms.txt) | unknown |
| [Aceternity UI](https://ui.aceternity.com/) | React | 323 | [valid](https://ui.aceternity.com/llms.txt) | `/websites/ui_aceternity` |
| [SmoothUI](https://smoothui.dev/) | React | 214 | [valid](https://smoothui.dev/llms.txt) | `/educlopez/smoothui` |
| [Vue Bits](https://vue-bits.dev/) | Vue | 201 | `/llms.txt` **HTML SPA, invalid** | `/websites/vue-bits_dev` |
| [Svelte Bits](https://sveltebits.xyz/) | Svelte | 164 | `/llms.txt` 404 | unknown |
| [Inspira UI](https://docs.inspira-ui.com/docs/en) | Vue | 155 | [valid at inspira-ui.com](https://inspira-ui.com/llms.txt) | `/unovue/inspira-ui` |
| [Shadcn Studio](https://shadcnstudio.com/) | React | 146 | [valid](https://shadcnstudio.com/llms.txt) | `/websites/shadcnstudio` |
| [Cult UI](https://www.cult-ui.com/) | React | 134 | [valid](https://www.cult-ui.com/llms.txt) | unknown |
| [Animate UI](https://animate-ui.com/) | React + Vue | 131 | [valid](https://animate-ui.com/llms.txt) | `/imskyleen/animate-ui` |
| [Kokonut UI](https://kokonutui.com/) | React | 112 | [valid](https://kokonutui.com/llms.txt) | `/websites/kokonutui` |
| [Magic UI](https://magicui.design/) | React | 79 | [valid](https://magicui.design/llms.txt) | `/magicuidesign/magicui` |
| [shadcn-svelte](https://www.shadcn-svelte.com/) | Svelte | 66 | [valid](https://www.shadcn-svelte.com/llms.txt) | unknown |
| [shadcn-vue](https://www.shadcn-vue.com/) | Vue | 64 | [valid](https://www.shadcn-vue.com/llms.txt) | unknown |
| [solidcn](https://solidcn.dev/) | Solid | 44 | `/llms.txt` **HTML SPA, invalid** | unknown |
| [shadcn-ui Expansions](https://github.com/BelkacemYerfa/shadcn-ui-expansions) | React | 15 | not checked | unknown |
| [Fancy Components](https://www.fancycomponents.dev/) | React | curated only | [valid](https://www.fancycomponents.dev/llms.txt) | `/danielpetho/fancy` |
| [UI Layouts](https://www.ui-layouts.com/) | React | curated only | [valid](https://www.ui-layouts.com/llms.txt) | `/ui-layouts/uilayouts` |
| [Eased UI](https://eased.dev/) | React | curated only | [valid](https://eased.dev/llms.txt) | `/easedui/ui` |
| [Kibo UI](https://www.kibo-ui.com/) | React | curated only | not verified | unknown |
| [Planes](https://useplanes.com/) | React | curated only | [valid](https://useplanes.com/llms.txt) | unknown |
| [Motion Primitives](https://motion-primitives.com/) | React | no raw snapshot | fetch returned 403, unverified | `/ibelick/motion-primitives` |
| [Ori UI](https://oriui.app/) | Svelte | no raw snapshot | `/llms.txt` 404 | unknown |
| [MagicUI Solid](https://axuj.github.io/magicui-solid/) | Solid | no raw snapshot | `/llms.txt` 404 | unknown |

## What each site is really good at

### 1. Animate UI — consistent motion on normal UI, not merely landing tricks

- Homepage/docs: https://animate-ui.com/docs ; machine docs: https://animate-ui.com/llms.txt ; Context7: `/imskyleen/animate-ui`. React components span Radix/Base UI/React Aria primitives, with official [Vue section](https://animate-ui.com/docs/vue).
- Standouts: [Code Block](https://animate-ui.com/docs/primitives/animate-ui/code-block) progressively reveals code; [Combobox](https://animate-ui.com/docs/primitives/base-ui/combobox) has a controlled open/close feel; [Dropdown Menu](https://animate-ui.com/docs/primitives/base-ui/dropdown-menu) animates the layer; also inspect tabs, dialogs, accordions and notifications in the catalog.
- Choose for: Kunkun menus and Agent UI state transitions with **subtle** motion. Avoid forced character-by-character reveal on a static source viewer: text selection/copy/screen-reader access must work immediately.
- Cost/port: check individual registry and peer dependency instructions; do not infer all React variants exist on Vue.

### 2. Cult UI — a collection of unique standalone ideas

- Docs: https://www.cult-ui.com/docs ; [llms.txt](https://www.cult-ui.com/llms.txt); Context7 **not verified**.
- Identity: one-off, often non-typical independent samples; many are more like *inspiration pieces* than a complete interchangeable component system.
- Standouts: [Cutout Card](https://www.cult-ui.com/docs/components/cutout-card), [Folded Card](https://www.cult-ui.com/docs/components/folded-card), [Organic Card](https://www.cult-ui.com/docs/components/organic-card); [Apple Keyboard](https://www.cult-ui.com/docs/components/apple-keyboard); [Gateway SVG](https://www.cult-ui.com/docs/components/gateway-svg-illustration); [Illustration Cursor](https://www.cult-ui.com/docs/components/illustration-cursor); [Loading Carousel](https://www.cult-ui.com/docs/components/loading-carousel); [Circuit Board](https://www.cult-ui.com/docs/components/circuit-board).
- Choose for: distinctive onboarding, plugin-marketplace tiles, feature explanations and demo imagery. Circuit Board is an **illustration**, not a network-route graph renderer.

### 3. Kokonut UI — expressive app, AI and media experiences

- Docs: https://kokonutui.com/ ; [llms.txt](https://kokonutui.com/llms.txt), [setup](https://kokonutui.com/setup.md); Context7 `/websites/kokonutui`.
- Standouts: [AI Context Meter](https://kokonutui.com/docs/ai/ai-context-meter), [AI Citations](https://kokonutui.com/docs/ai/ai-citations), [AI Agent Lanes](https://kokonutui.com/docs/ai/ai-agent-lanes), [Scroll Index](https://kokonutui.com/docs/navigation/scroll-index), [Activity Terrain](https://kokonutui.com/docs/cards/activity-terrain), [Synced Transcript](https://kokonutui.com/docs/media/synced-transcript), [Clip Trimmer](https://kokonutui.com/docs/media/clip-trimmer), [Status Island](https://kokonutui.com/docs/navigation/status-island), [Liquid Glass/Now Playing](https://kokonutui.com/docs/cards/liquid-glass-card).
- Choose for: chat, agent monitoring, podcast UI, visual metrics. Validate real timestamps, token values and events. Some entries may be Pro/paid: inspect exact page.

### 4. React Bits — hero-grade animation and artistic graphics

- Docs: https://reactbits.dev/ ; [llms.txt](https://www.reactbits.dev/llms.txt); Context7 `/davidhdev/react-bits`.
- Signature: [Crystalized Ball](https://reactbits.dev/animations/crystalized-ball), [Electric Border](https://reactbits.dev/animations/electric-border), [Laser Flow](https://reactbits.dev/animations/laser-flow). Browse text, background, animations, components and shader categories.
- Choose for: wow moment, feature demo and landing hero; limit GPU/heavy animations in a WKWebView dashboard. Machine list can include paid entries; do not treat each as free.
- Ports: Vue Bits and Svelte Bits are separate codebases; refer to [framework-ports.md](framework-ports.md).

### 5. Aceternity UI — marketing drama, layered patterns, high-fidelity blocks

- Docs: https://ui.aceternity.com/components ; [llms.txt](https://ui.aceternity.com/llms.txt), [component API](https://ui.aceternity.com/api/components); Context7 `/websites/ui_aceternity`.
- Standouts: [Liquid Glass](https://ui.aceternity.com/components/liquid-glass), Grid/Dots backgrounds, hero/spotlight effects, hover cards, 3D treatments, landing sections.
- Choose for: JetSpeedy/Kunkun marketing. Verify interactive effects in dark theme, cost of blur/filter/3D and responsive/mobile fallback.

### 6. Magic UI — elegant developer/SaaS storytelling

- Docs: https://magicui.design/ ; [llms.txt](https://magicui.design/llms.txt); Context7 `/magicuidesign/magicui`.
- Standout: [Animated Beam](https://magicui.design/docs/components/animated-beam) visually connects an icon cluster; Bento, shine, text effects and decorative lines.
- Choose for: plugin/API ecosystem, integration feature hero. A beam illustrates a topology; use React Flow for *actual* editable nested policies.

### 7. Motion Primitives — refined functional microinteractions

- Docs: https://motion-primitives.com/ ; [official GitHub](https://github.com/ibelick/motion-primitives); Context7 `/ibelick/motion-primitives`. `llms.txt` blocked when checked (403).
- Standouts: Morphing Dialog and shared-element-like transitions, text/interaction primitives.
- Choose for: polished details and continuity. For unavailable machine docs, source inspection is preferable to guessing behavior.

### 8. SmoothUI — cohesive animated AI Chat and app UI

- Docs: https://smoothui.dev/ ; [llms.txt](https://smoothui.dev/llms.txt), [component JSON](https://smoothui.dev/llms-components.json), [official Skill](https://skills.smoothui.dev/); Context7 `/educlopez/smoothui`.
- Standouts: [Chat Template](https://smoothui.dev/docs/templates/chat), animated tasks, interactive cards and thoughtful status layouts.
- Choose for: higher-level Kunkun AI chat patterns. Assess whether copying whole template conflicts with existing app runtime and code structure.

### 9. Shadcn Studio — polished business blocks and dashboards

- Docs: https://shadcnstudio.com/ ; [llms.txt](https://shadcnstudio.com/llms.txt), [MCP](https://shadcnstudio.com/mcp); Context7 `/websites/shadcnstudio`.
- Standout: [DataTable Grouping](https://shadcnstudio.com/blocks/datatable/datatable-grouping), grouped/nested rows, dense charts, card layouts, navigation and dashboards.
- Choose for: KKTasks, Refyard, internal tools. **Free/Pro differs by block**, and full site has more items than the raw snapshot; confirm subscription license before copying.

### 10. Fancy Components — playful physicality and typography

- Docs: https://www.fancycomponents.dev/components ; [llms.txt](https://www.fancycomponents.dev/llms.txt), [installation/registry](https://www.fancycomponents.dev/docs/installation); Context7 `/danielpetho/fancy`.
- Standouts: [Media Between Text](https://www.fancycomponents.dev/docs/components/blocks/media-between-text), [Cursor Attractor & Gravity](https://www.fancycomponents.dev/docs/components/physics/cursor-attractor-and-gravity), [Pixel Trail](https://www.fancycomponents.dev/docs/components/background/pixel-trail), Image Trail and Cursor Proximity type.
- Choose for: creative editorial marketing / small showcase interactions. Treat Matter.js simulations as presentational, not data/physics engine needed elsewhere.

### 11. UI Layouts — app-ready animated transitions

- Docs: https://www.ui-layouts.com/components ; [llms.txt](https://www.ui-layouts.com/llms.txt), [full](https://www.ui-layouts.com/llms-full.txt), [MCP](https://www.ui-layouts.com/mcp); Context7 `/ui-layouts/uilayouts`.
- Standouts: [Linear Modal](https://www.ui-layouts.com/components/linear-modal), [Tree Code Viewer](https://www.ui-layouts.com/components/tree-code-viewer), [Progressive Carousel](https://www.ui-layouts.com/components/progressive-carousel), [Range Slider](https://www.ui-layouts.com/components/range-slider), [Mac Genie](https://www.ui-layouts.com/components/mac-genie).
- Choose for: workbench/dense interfaces that need spatial continuity, drawers, media carousels. Check Pro components separately.

### 12. Eased UI — very polished shadcn-like microanimation

- Docs: https://eased.dev/components ; [llms.txt](https://eased.dev/llms.txt), [registry](https://eased.dev/r/registry.json), [MCP guide](https://eased.dev/docs/ai-mcp); Context7 `/easedui/ui` (previously flagged low index reputation, so cross-check official source).
- Standouts: [Demo Cursor](https://eased.dev/components/demo-cursor) for staged clicks/drags, [Click Ripple](https://eased.dev/components/click-ripple), [Kbd](https://eased.dev/components/kbd), [Composer](https://eased.dev/components/composer), [Thinking Bar](https://eased.dev/components/thinking-bar), [Agent Orb](https://eased.dev/components/agent-orb), [Group-by Morph List](https://eased.dev/components/group-by-list), [Agent Run Console](https://eased.dev/components/agent-run-console).
- Site showed **107** components (70 Free/37 Pro) on 2026-11-04. Group-by Morph List, Agent Run Console and Live Activity Pill were **Pro** then. Check current per-component tier.

### 13. Kibo UI — enhanced functional building blocks

- Docs: https://www.kibo-ui.com/components ; [setup](https://www.kibo-ui.com/docs/setup); `llms.txt` and Context7 ID **not verified**.
- Standouts: [Video Player](https://www.kibo-ui.com/components/video-player) based on media-chrome controls, [Gantt](https://www.kibo-ui.com/components/gantt), [Kanban](https://www.kibo-ui.com/components/kanban), [Tree](https://www.kibo-ui.com/components/tree), [Editor](https://www.kibo-ui.com/components/editor).
- Choose for: actual app UI and media playback; test keyboard, real media source and state persistence. Official gallery showed 41 Components in the checked snapshot.

### 14. Planes — ready-made high-style showpieces, mostly commercial

- Docs: https://useplanes.com/components ; [llms.txt](https://useplanes.com/llms.txt), [full](https://useplanes.com/llms-full.txt), [MCP](https://useplanes.com/components/mcp); Context7 unverified.
- Standouts: [Retro Music Player](https://useplanes.com/components/retro-music-player), [AI Chat](https://useplanes.com/components/ai-chat), shaders and brand-grade product UI.
- On 2026-11-04, official machine list yielded **174** entries: **10 Free / 164 Pro**. Treat as design references unless component purchase/license is confirmed. A beautiful player shell does not implement an audio backend.

### 15. nxui — striking Vue dashboards, media and node visuals

- Docs: https://nxui.geoql.in/docs ; [llms.txt](https://nxui.geoql.in/llms.txt), [full](https://nxui.geoql.in/llms-full.txt); Context7 unverified.
- Standouts: [Node Diagram](https://nxui.geoql.in/docs/components/node-diagram), [Podcast Player](https://nxui.geoql.in/docs/components/podcast-player), [Data Table](https://nxui.geoql.in/docs/dashboard/data-table). Dark, attractive, information-rich.
- Choose for: Vue interfaces or Kunkun/KKnet visual reference. Does **not** by itself supply editable React nested policy engine.

### 16. Inspira UI — Vue/Nuxt animated landing primitives

- Docs: https://docs.inspira-ui.com/docs/en ; [llms.txt](https://inspira-ui.com/llms.txt); Context7 `/unovue/inspira-ui`.
- Standouts: [Card Stack](https://docs.inspira-ui.com/docs/en/components/cards/card-stack), text transitions, backgrounds and animated navigation.
- Choose for: Vue marketing/onboarding; scrolling story stack is inappropriate for live task logs.

### 17. Vue Bits — maintained Vue counterpart of React Bits

- Docs: https://vue-bits.dev/ ; [registry](https://vue-bits.dev/r/registry.json); Context7 `/websites/vue-bits_dev`. `/llms.txt` was **HTML SPA**, so don't parse as documentation.
- Identity: Vue-targeted versions of many React Bits style components. Need exact page/compatibility check; a similarly named component may differ in implementation.

### 18. Svelte Bits — Svelte counterpart of React Bits

- Docs: https://sveltebits.xyz/ ; [registry](https://sveltebits.xyz/r/registry.json). `/llms.txt` 404, Context7 unverified.
- Standouts: [Dock](https://sveltebits.xyz/components/dock), strong animation and Svelte 5-oriented effects. Check movement/SSR/hydration behavior in SvelteKit.

### 19. Ori UI — restrained Svelte embellishment

- Docs: https://oriui.app/ ; [Liquid Button](https://oriui.app/components/liquid-button). `/llms.txt` 404, Context7 unverified.
- Identity: lighter shadcn-svelte-adjacent interactive samples, better for Svelte app visual polish than flashy landing-only effects.

### 20. shadcn-svelte, shadcn-vue, solidcn — framework foundations

- [shadcn-svelte](https://www.shadcn-svelte.com/) [llms.txt](https://www.shadcn-svelte.com/llms.txt): Svelte foundational primitives; preserve local token conventions.
- [shadcn-vue](https://www.shadcn-vue.com/) [llms.txt](https://www.shadcn-vue.com/llms.txt): Vue/Reka UI foundation and accessible composition.
- [solidcn](https://solidcn.dev/) [registry](https://solidcn.dev/r/registry.json): Solid basics with Kobalte/Corvu patterns. `llms.txt` was HTML SPA. They aren't a source of wow-effect hero by themselves.

### 21. MagicUI Solid — community Solid port

- [Docs](https://axuj.github.io/magicui-solid/); examples include Animated Beam/Bento; `llms.txt` 404 and Context7 unverified.
- Choose for: Solid marketing features after checking repo maintenance, matching dependencies and license. It is not the official React Magic UI package.

### 22. 21st.dev, React Flow UI and domain-specific engines

- [21st.dev](https://21st.dev/) is a **discovery/community marketplace**, not one uniform framework with guaranteed code/license quality. Validate each creator's item.
- [React Flow UI](https://reactflow.dev/ui): animated edge and node patterns on top of [@xyflow/react](https://reactflow.dev/). Prefer for functional KKnet graph; real routing and fallback traversal remain app logic.
- [Svelte Flow](https://svelteflow.dev/): Svelte node/edge graph toolkit.
- [TanStack Table](https://tanstack.com/table/latest), [Tremor](https://www.tremor.so/), [WaveSurfer.js](https://wavesurfer.xyz/), [Video.js](https://videojs.org/): **functional** building blocks. Add ornamental components only after data/performance/keyboard behavior is correct.
- [assistant-ui](https://www.assistant-ui.com/) and [AI Elements](https://ai-sdk.dev/elements/overview): AI chat structure and interaction patterns. Agent Status can represent working/waiting/done/failed using real events. On 2026-11-04, assistant-ui's [llms.txt](https://www.assistant-ui.com/llms.txt) and Context7 `/assistant-ui/assistant-ui` returned docs in a forward test; still inspect current source/peer dependencies.
- [Streamdown](https://streamdown.ai/docs/usage): Markdown streaming and source-code rendering; [code blocks](https://streamdown.ai/docs/code-blocks), [llms.txt](https://streamdown.ai/llms.txt), Context7 `/vercel/streamdown` were readable in a forward test on 2026-11-04. This is a **functional code renderer**, not a cinematic typewriter component. Keep incomplete Markdown/code fences visible as actual tokens arrive, and let the user copy visible content.

## Interpreting the directory

- An index count is not “number of installable free components.”
- `llms.txt` is not an API stability guarantee or visual review. Validate actual content, not just status code.
- `Context7 ID unknown` is a discovery opportunity: call `resolve-library-id` with the official project name.
- When selection truly matters, compare **at least one functional baseline** and one creative candidate. Avoid treating all libraries as interchangeable shadcn variants.
