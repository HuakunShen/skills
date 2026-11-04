---
name: ui-component-scout
description: Use when finding, comparing, evaluating, or integrating beautiful UI components, shadcn registries, animated React primitives, AI-chat interfaces, distinctive cards, tables, graph visuals, media players, and their Vue/Svelte/Solid ports. Provides scenario-based discovery, an offline component yellow-pages index, official llms.txt and Context7 verification, optional browser demonstration inspection, motion/quality triage, and implementation advice. Trigger for requests to improve an existing site's visual polish, search design libraries, pick a component for a use case, or build a reusable catalog.
---

# UI Component Scout — Design-focused Component Yellow Pages

Find components for a **real product task**, not just by a name or animation keyword. Prefer credible implementation and design-system coherence over novelty. This Skill ships **no images or video**. Use live browser inspection only when tools and user authorization allow it; summarize observations in text.

## Core workflow

1. **Establish context.** Identify framework and version (React 19, Vue 3/Nuxt, Svelte 5/SvelteKit, Solid), existing primitives (shadcn/Radix/Base UI/React Aria), Tailwind version, app surface (core dashboard vs landing), functionality, license constraints, and whether code may be modified. If working in a repo, inspect only relevant `package.json`, `components.json`, theme tokens and existing UI.
2. **Split three requirements.** Distinguish (a) functional engine — actual agent trace, playback, data graph, search/keyboard semantics; (b) visible interaction — menu motion, state transitions, hover; and (c) signature branding — unusual cards, backgrounds, hero visuals. A decorative mock component is not its underlying data engine.
3. **Choose use case and motion role.** Read [scenarios-and-highlights.md](references/scenarios-and-highlights.md) for intent-based routing; read [motion-and-quality.md](references/motion-and-quality.md) for when **not** to animate. Default high-frequency app UI to original shadcn design with no/subtle motion.
4. **Search bundled catalog first.** Use `node scripts/search_catalog.mjs --query "agent status" --framework react --limit 12` or look up [curated.json](references/curated.json) before [catalog.jsonl](references/catalog.jsonl). Offline index: **2,661 official-description records from 16 sources**, plus a **51-record human/browsed curation overlay**. The five additionally researched websites are represented primarily in the overlay; this is not a fully crawled live database.
5. **Go to the original source.** Open precise vendor pages and inspect the actual API/installation notes. Follow [discovery-protocol.md](references/discovery-protocol.md) for live search, registry, `llms.txt`, `llms-full.txt`, GitHub and Context7. **Do not treat HTTP 200 containing an HTML SPA fallback as a valid `llms.txt`.** Check fresh version and price/license for selected components, not only a site-wide badge.
6. **Visual verification when available.** If the user explicitly provided a browser/environment, honor that choice. Otherwise prefer connected browser skill/tools when authorized. Review actual demo, dark/light, focus, hover, open/close, keyboard, mobile layout, and reduced motion; record steps and date **in text**. If browser unavailable, say “documentation only — visual interaction not verified.” Never claim a static image proves animation quality.
7. **Compare and recommend.** Return 3–5 options across complementary roles with: official link, specific component, use case, native/official port/community port, evidence level, motion decision, dependencies, performance/a11y caveats, license tier, and a suggested integration. Separate what was **observed** from what docs **claim**.
8. **Implement only if requested.** A request to “find” or “compare” authorizes read-only research, not package installs, Git changes, Site edits or payments. Implementation requires a user request to build/change. Do not run unknown install shell scripts directly from a vendor page.

## Directory of references

| Need | Read this |
|---|---|
| Which UI site suits which product? What are its docs, API, `llms.txt`, Context7 ID, paid caveats? | [source-directory.md](references/source-directory.md) |
| Search syntax, valid `llms.txt` detection, Context7 resolution, registry, Github search, actual browser QA | [discovery-protocol.md](references/discovery-protocol.md) |
| 51 curated standout examples + product-specific suggestions for Kunkun, Xross, KKnet, KKTasks, ListenFlow, JetSpeedy | [scenarios-and-highlights.md](references/scenarios-and-highlights.md) |
| When a combobox should animate vs when code, chat, data and live tables must stay immediate | [motion-and-quality.md](references/motion-and-quality.md) |
| React/Vue/Svelte/Solid original, official port, community port, conversion and license constraints | [framework-ports.md](references/framework-ports.md) |
| Machine-readable complete component inventory (JSONL) | [catalog.jsonl](references/catalog.jsonl) |
| Human-selected/browsed examples; includes evidence and Chinese use notes; no images | [curated.json](references/curated.json) |

Load only necessary references for the current query. Do not dump the full index into context: use the search script and inspect targeted records.

## Offline search

From this Skill directory:

```bash
node scripts/search_catalog.mjs --query "AI citations" --framework react --limit 10
node scripts/search_catalog.mjs --query "animated edge network" --limit 12 --json
node scripts/search_catalog.mjs --query "podcast player" --framework vue --limit 10
node scripts/search_catalog.mjs --scenario "hotkey-onboarding" --limit 10
node scripts/search_catalog.mjs --query "agent run console" --curated-only --limit 5
node scripts/check_llms.mjs --url https://animate-ui.com/llms.txt
node scripts/validate_catalog.mjs
node --test tests/*.test.mjs
```

Search flags: `--query` (free text), `--scenario` (curation scenario ID), `--framework` (`react|vue|svelte|solid`), `--role` (`foundation|animated-primitive|signature-design|showpiece`), `--curated-only`, `--limit` (1–100), `--json`. Default text display prints the official URL, framework, tier, provenance and a concise description. `check_llms.mjs` requires network access and checks status, MIME and Markdown body without executing third-party content.

Search results are **candidates, not guaranteed compatibilities**. Curated entries may have visual evidence from HK's own browsing; preserve `evidence=user-visual` without calling it an agent-tested result. A catalog item marked `free-or-unverified` is **not known to be free**.

## Component choice rules

- **Foundation:** use shadcn/ui, assistant-ui/AI Elements, Kibo, real media engine, React Flow/Svelte Flow, TanStack Table as needed. Keep the original product's tokens, typography and keyboard semantics.
- **Animated primitives:** try Animate UI, Motion Primitives, Eased, UI Layouts for state continuity; a polished popover does not justify animation on every row/filter.
- **Distinctive blocks:** Cult UI, Kokonut, Fancy for cutout/folded/organic cards, hotkey art, demo cursor, synchronized transcript, status lanes.
- **Wow moments:** React Bits, Aceternity, Magic UI, Planes for hero/onboarding/marketing, not every chat message or permanent dashboard panel.
- **Real media/graph capabilities:** don't claim that a beautiful component includes audio decoding, video export, graph routing, agent instrumentation, genuine computer-control or accurate AI token accounting.
- **Ports:** never copy React-only JSX into Vue/Svelte/Solid unmodified. Verify the precise native library or port and code version; see [framework-ports.md](references/framework-ports.md).
- **Policy and proof:** distinguish `official-docs`, `user-visual`, `browser-visual`, `browser-interaction`, `source-reviewed` and `integrated-tested`. The last two require inspecting code and testing in the target app.
- **Safe fallbacks:** if no network, Context7, browser or trusted vendor page is available, work from bundled indexed descriptions with visible “snapshot only / needs verification” labels. Do not bypass auth, robots, license or paywall.

## Desired answer shape

1. One-line design judgment — e.g. “keep Kunkun's shadcn shell; introduce motion only for changing agent states.”
2. Ranked 3–5 **specific components**, direct demo/docs links; tag role, framework/port status, evidence level, free/Pro/unknown.
3. Explain **what should animate and what should not**, including `prefers-reduced-motion`, keyboard focus, dense-data performance and accessibility.
4. Give a plausible composition of foundation + optional polish and a conservative alternative, plus implementation prerequisites.
5. State when source has not been visually inspected, or `llms.txt`/Context7 was unavailable.

For research-only tasks stop here. If implementation is requested, read site-specific installation instructions and inspect the app before making targeted changes; verify build, keyboard and visual behavior afterward.

## Index provenance

Snapshot date: **2026-11-04**. Raw index data came from official website documents/registries in the accompanying research project. The curation overlay includes HK's selected Animate UI/Cult UI/Kokonut UI/React Bits components and further site inspection. Entries and displayed prices may change; always verify before installation. No image files, embedded screenshots or screenshot URLs are included in this Skill.
