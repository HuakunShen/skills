# Use-case directory and standout component notes

**2026-11-04 curation:** 25 components personally highlighted by HK from Animate UI/Cult UI/Kokonut UI/React Bits plus 26 from additional web research (Fancy, UI Layouts, Eased, Kibo, Planes). Those are **samples, not a claim to have browsed every component**. Search all 2,661 machine-indexed descriptions with the bundled selector for a broader list.

Ratings are intentionally absent: real visual quality cannot be inferred from Markdown alone. `user-visual` means HK saw and selected an example; `official-docs` means only docs were examined; `browser-visual` / `browser-interaction` refer to separately recorded agent observation at that time. See `references/curated.json` for per-entry evidence, scenario IDs, motion policy and Chinese note.

## Scenario router — pick a functional backbone and optional flair

| Scenario | Backbone / functional baseline | Expressive candidate | Default motion |
|---|---|---|---|
| Kunkun AI chat and streaming code | AI Elements, assistant-ui, shadcn, Streamdown | Kokonut Context Meter, Citations, Scroll Index; Eased Composer/Thinking Bar | State changes subtle, code immediately selectable |
| Kunkun command palette / hotkey hints | shadcn Command, real shortcut handler | Animate UI Combobox/Dropdown; Cult Apple Keyboard, Eased Kbd | Keyboard instant, popover subtle |
| Computer Use recorded tutorial | DOM actions + recorder/timeline | Eased Demo Cursor/Click Ripple; Cult Cursor as illustration | Playback-only; no false real input |
| KKTasks Agent Observer | real session trace + grouped table and events | Kokonut Agent Lanes; Eased Group-by Morph List (Pro), Run Console (Pro) | Functional state only; avoid per-token row morph |
| KKnet nested policy / active-route graph | React Flow/Svelte Flow + routing policy engine | React Flow Animated SVG Edge, nxui Node Diagram style, Cult Circuit Board for hero | Active edge subtle, truthful to route |
| Xross Device Fabric feature description | real device graph/data model | Magic UI Animated Beam, Cult Circuit Board | Hero expressive; operational graph restrained |
| ListenFlow podcast and chapters | HTMLAudioElement, Media Chrome/WaveSurfer, actual timestamps | Kokonut Synced Transcript/Now Playing, nxui Podcast Player | Functional lyric/word highlight |
| Xross Loom recording and editing | media transport, timeline model, transcoding/export | Kibo Video Player, Kokonut Clip Trimmer, UI Layouts Range Slider | Functional draggable trim UI |
| Data and metrics dashboards | TanStack Table, Shadcn Studio, Tremor/ECharts | Kokonut Activity Terrain (3D count map), Cult Analytics Chart | Static table fallback always |
| Developer code/file viewer | real source/document model and tree | UI Layouts Tree Code Viewer; Animate UI Code Block **for demo only** | No progressive reveal in production code editor |
| Dark SaaS marketing hero | accessible HTML, SEO, responsive static base | React Bits Crystalized Ball/Laser Flow; Aceternity Liquid Glass; Kokonut Ink Background | Cinematic once, static/reduced fallback |
| Brand-signature feature cards | normal Card, CSS tokens | Cult Cutout/Folded/Organic, Fancy Media Between Text | Can be static with unique shape |
| Svelte app UI | shadcn-svelte, Ori UI | Svelte Bits Dock / hero effects | Subtle in app, expressive on landing |
| Vue/Nuxt rich visuals | shadcn-vue, Inspira, nxui | Vue Bits effects, nxui node/podcast demos | Context-dependent |
| Solid marketing | solidcn core | MagicUI Solid Animated Beam | Isolate community-port effect |

## HK's selected examples: practical judgment by component

### Animate UI — everyday components with animation

| Component | What it looks/acts like | Best fit | When to skip/limit animation |
|---|---|---|---|
| [Code Block](https://animate-ui.com/docs/primitives/animate-ui/code-block) | Code incrementally appears with typing-style reveal; attractive in demo walkthroughs | AI generating code preview, product tour, tutorial | Never delay reading/copying pre-existing source; provide Skip/Show all |
| [Combobox](https://animate-ui.com/docs/primitives/base-ui/combobox) | Animated input/menu surface while options open/filter | Model/provider selection, command palette, plugin picker | Keep Enter/Escape/Arrow immediate, virtualize large option lists |
| [Dropdown Menu](https://animate-ui.com/docs/primitives/base-ui/dropdown-menu) | Smooth dropdown arrival and dismissal, retains normal UI shape | Toolbar, task actions and item overflow | Fast repeated keyboard actions should not wait for exit animation |

### Cult UI — independent, unusual designs

| Component | Distinctive idea | Applicable product/role |
|---|---|---|
| [Cutout Card](https://www.cult-ui.com/docs/components/cutout-card) | Missing/cut section of card border gives unusual composition even while still | Product feature tiles, custom branding; **no animation required** |
| [Folded Card](https://www.cult-ui.com/docs/components/folded-card) | Folded-paper corner and layered visual | Kunkun plugin marketplace, file/template gallery |
| [Organic Card](https://www.cult-ui.com/docs/components/organic-card) | Organic edge/shape, distinct from standard rectangles | Brand/storytelling, not compact admin table |
| [Gateway SVG Illustration](https://www.cult-ui.com/docs/components/gateway-svg-illustration) | Flows converge into central node, visually expresses connection/shortcut concept | Hotkey explanation or integration hub; **does not capture hotkey itself** |
| [Illustration Cursor](https://www.cult-ui.com/docs/components/illustration-cursor) | Decorative labeled cursor for collaboration-like demos | Xross remote-control concept; use Eased Demo Cursor for actual scripted DOM demo |
| [Apple Keyboard](https://www.cult-ui.com/docs/components/apple-keyboard) | Full recognizable keyboard visual | Kunkun quick shortcut tutorial and keyboard hints |
| [Loading Carousel](https://www.cult-ui.com/docs/components/loading-carousel) | Animated step/card presentation during loading | Demo gallery, onboarding, image slideshow, loading-tips card |
| [Circuit Board](https://www.cult-ui.com/docs/components/circuit-board) | Glowing circuit traces and network of features | Xross Device Fabric illustrations; **not** policy traversal engine |

### Kokonut UI — AI, media, analytics and interesting motion

| Component | Distinctive idea | Applicable product/role |
|---|---|---|
| [Ink Background](https://kokonutui.com/docs/backgrounds/ink-background) | Hover breaks up text/ink like smoke | Showpiece hero; WebGL/static fallback, low-end mobile caution |
| [Now Playing / Liquid Glass Card](https://kokonutui.com/docs/cards/liquid-glass-card) | Vinyl/audio-themed player card with strong identity | ListenFlow audio shell; wire real audio state |
| [Activity Terrain](https://kokonutui.com/docs/cards/activity-terrain) | 3D grid of daily-count bars that looks like terrain | KKTasks user activity; keep accessible table/CSV fallback |
| [Receipt Printer](https://kokonutui.com/docs/cards/receipt-printer) | Completed data printed line by line as receipt | One-shot billing summary/completion celebration; export remains instant |
| [Scroll Index](https://kokonutui.com/docs/navigation/scroll-index) | Floating/indexed scroll navigation for long content | AI chat checkpoint/turn list, research document anchors |
| [Loader](https://kokonutui.com/docs/inputs/loader) | Refined progress/thinking indicator | Agent state, file upload; stop when work finishes |
| [AI Context Meter](https://kokonutui.com/docs/ai/ai-context-meter) | Visual context-window capacity/usage inspection | Kunkun chat context; source actual counted tokens |
| [AI Inline Citations](https://kokonutui.com/docs/ai/ai-citations) | Citation anchors and related source UI | Research chat/ListenFlow notes; link actual evidence |
| [AI Agent Lanes](https://kokonutui.com/docs/ai/ai-agent-lanes) | Parallel agents and merges as interleaved workflow lanes | KKTasks multi-agent observer; map to real trace graph |
| [Clip Trimmer](https://kokonutui.com/docs/media/clip-trimmer) | Film-strip timeline and in/out trim handles | Loom recording UX; export/codec implementation separate |
| [Synced Transcript](https://kokonutui.com/docs/media/synced-transcript) | Playback cursor highlights transcript words/phrases | ListenFlow podcast, live caption, video text scrubbing; requires timestamps |

### React Bits — deliberate wow moments

| Component | Distinctive idea | Applicable product/role |
|---|---|---|
| [Crystalized Ball](https://reactbits.dev/animations/crystalized-ball) | Striking 3D/shader object | Homepage or isolated demo panel, not every app view |
| [Electric Border](https://reactbits.dev/animations/electric-border) | Border energized like electrical flow | Highlight current agent thinking or CTA, **not** all chat bubbles |
| [Laser Flow](https://reactbits.dev/animations/laser-flow) | Cinematic light beam across layout | Hero or landing-feature reveal with reduced-motion fallback |

## Additional-site examples: 26 focused discoveries

### Fancy Components — experimental content and cursor physics

| Component | Why it stands out | Practical caution |
|---|---|---|
| [Media Between Text](https://www.fancycomponents.dev/docs/components/blocks/media-between-text) | Media parts large editorial typography on interaction | Use to tell a brand story, not in data forms |
| [Cursor Attractor & Gravity](https://www.fancycomponents.dev/docs/components/physics/cursor-attractor-and-gravity) | Physics objects respond to cursor attraction/repulsion | High-cost showpiece, not real device graph |
| [Pixel Trail](https://www.fancycomponents.dev/docs/components/background/pixel-trail) | Cursor leaves pixelated art trail | On hover-capable demo section only |
| [Image Trail](https://www.fancycomponents.dev/docs/components/image/image-trail) | Cursor movement produces media succession | Gallery/portfolio; do not conceal important actions |
| [Text Cursor Proximity](https://www.fancycomponents.dev/docs/components/text/text-cursor-proximity) | Typography morphs with cursor distance | Decorative heading; remain readable without pointer |

### UI Layouts — transition mechanics for a working app

| Component | Why it stands out | Practical caution |
|---|---|---|
| [Linear Modal](https://www.ui-layouts.com/components/linear-modal) | Card visually grows into a detail modal, preserving spatial origin | Accessible focus/escape/scroll lock still essential |
| [Tree Code Viewer](https://www.ui-layouts.com/components/tree-code-viewer) | File tree + source pane as one polished unit | Source files/data state remain yours |
| [Progressive Carousel](https://www.ui-layouts.com/components/progressive-carousel) | Strong visual slideshow progression | Pause/manual controls, swipe and accessible labels |
| [Range Slider](https://www.ui-layouts.com/components/range-slider) | Visually coherent numerical slider | Avoid motion affecting precise drag |
| [Mac Genie](https://www.ui-layouts.com/components/mac-genie) | macOS-style window/dock transformation | Showcase for Kunkun; test WKWebView performance |

### Eased UI — polished microinteraction and AI app affordances

| Component | Why it stands out | Tier at checked date | Practical caution |
|---|---|---|---|
| [Demo Cursor](https://eased.dev/components/demo-cursor) | Scripts mouse movement/click/drag toward actual DOM demo targets | Free | Does not provide OS-level remote input |
| [Click Ripple](https://eased.dev/components/click-ripple) | Brief click feedback showing impact point | Free | Add to tutorial/recording, not every real click |
| [Kbd](https://eased.dev/components/kbd) | Keyboard keycap appears to press on actual event | Free | Keep real keyboard handler independent |
| [Thinking Bar](https://eased.dev/components/thinking-bar) | Reasoning/thinking status smooth transition with elapsed time | Free | Never fabricate reasoning/timing |
| [Composer](https://eased.dev/components/composer) | Auto-growing prompt area and Send/Stop morph | Free | Keep cursor and input focus stable |
| [Agent Orb](https://eased.dev/components/agent-orb) | Voice/agent status sphere with alive feel | Free | Continuous motion needs throttling |
| [Group-by Morph List](https://eased.dev/components/group-by-list) | Rows migrate as grouping changes | **Pro** | Big data + virtualization may require replacement |
| [Agent Run Console](https://eased.dev/components/agent-run-console) | Detailed agent run, steps and inspector layout | **Pro** | Visual module, not prebuilt agent instrumentation |
| [Live Activity Pill](https://eased.dev/components/activity-pill) | Compact task state island that changes shape/size | **Pro** | True status events, keyboard/accessibility |

### Kibo UI — domain components with actual function

| Component | Why it stands out | Practical caution |
|---|---|---|
| [Video Player](https://www.kibo-ui.com/components/video-player) | Uses media-chrome style media controls; Play→Pause seen in earlier browser test | Need real media source, seeking, captions, buffering |
| [Gantt](https://www.kibo-ui.com/components/gantt) | Task scheduling timeline with adjustable bars | Date math, keyboard drag and large dataset test |
| [Kanban](https://www.kibo-ui.com/components/kanban) | Drag/drop task cards across columns | KKTasks Observer v1 is read-only; may not need edit UX |
| [Tree](https://www.kibo-ui.com/components/tree) | Accessible nested hierarchy navigation | File/policy tree; selection model and depth |
| [Editor](https://www.kibo-ui.com/components/editor) | Tiptap/slash-command rich text | Sanitization, persistence and licensing/deps |

### Planes — strong visual personality, commercial caution

| Component | Why it stands out | Practical caution |
|---|---|---|
| [Retro Music Player](https://useplanes.com/components/retro-music-player) | Tactile retro music-player shell | Pro in earlier check; playback and branding separate |
| [AI Chat](https://useplanes.com/components/ai-chat) | Visually finished chat concept | Check component-tier license; use as design reference if gated |

## Decision examples that prevent common mistakes

1. **“My AI chat is too plain.”** Use robust chat structure, bring in Eased Composer/Thinking Bar plus Kokonut Citations/Context Meter; optionally single Electric Border while tool running. Don't add shader backgrounds to every message.
2. **“Animated code blocks are beautiful.”** Use Animate UI Code Block for *newly generated examples or a demo tutorial*. For existing source and tool output, render instantly, syntax-highlight, allow selection/copy without waiting. Add a `Show all` path.
3. **“I want a real-time flowing network policy graph.”** Use React Flow engine, custom edge as active packet path, nested groups and actual tracer events. A Cult Circuit Board or Magic Beam is useful on a marketing page but not a replacement for routing logic.
4. **“I want my app to demonstrate Computer Use automatically.”** Eased Demo Cursor for staged DOM actions, Click Ripple for explanation, Cult Illustration Cursor as visual language; the actual computer-control protocol belongs to Xross and remains separate.
5. **“Make the KKTasks dashboard more creative.”** Keep high-density tables readable; use one status island and truthful Agent Lanes; reserve big morph transitions for grouping mode changes, not on every event arrival.
6. **“Give ListenFlow a premium audio experience.”** Combine actual audio element/timestamps/waveform infrastructure with Kokonut Now Playing, Synced Transcript and Kibo controls. A beautiful card is not an audio engine.
7. **“I need the same design in Vue/Svelte/Solid.”** Search native/official ports first; see [framework-ports.md](framework-ports.md), and don't silently convert React-heavy hooks/animation into other framework code.

## Evidence and maintenance

- These notes encode decisions from the 2026-11-04 research. They're **not a fresh automated page-by-page visual audit**.
- To extend: append to `curated.json` with name, library, URL, scenarios, role, motion, tier where known, evidence, and one sentence on *why it is distinctive*. Update a source profile and validate the index.
- Never manufacture an example page URL; locate it from the official gallery. Check price/license and current install recipe when selected for a real project.
