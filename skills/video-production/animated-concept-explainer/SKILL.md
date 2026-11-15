---
name: animated-concept-explainer
description: Turn complex technical concepts, software workflows, or design processes into high-engagement motion-graphic explainer videos using animated UI mockups, kinetic visual metaphors, curved cursor interactions, and skeleton-focused typography. Use when the user asks to "explain concepts with animation", make videos with animated UI/cursors, visualize software mechanisms without live screen recordings or boring slide decks, or replicate the sleek dark-canvas SaaS explainer style.
---

# Animated Concept Explainer

Transform abstract software architectures, design methodologies, AI mechanisms, and developer workflows into clear visual explanations.

## Choose a visual style

When the user has not already chosen a style, offer these options and let them choose before storyboarding. The user may also ask to combine specific elements.

1. **Dark interactive UI**: a dark continuous canvas, large simplified UI, physical metaphors, and an expressive cursor. Use the principles below and the existing motion and storyboard references.
2. **Light evidence-flow**: a pale canvas, progressively revealed flowchart cards, highlighted branches, and real screenshots or code as evidence. Read [the style guide and source study](references/light-evidence-flow.md). This style can use headings, dense technical evidence, real footage, and static holds where they help comprehension.

For any chosen style, adapt density, pacing, and motion to the subject. Do not transfer the dark style's fixed visual rules to every style. Add future styles as separately named choices with source-backed examples; distinguish observations from provisional generalizations.

## Dark interactive UI

This style rejects traditional presentation slides, dry bullet points, and uncurated screen recordings. Instead, it places the audience inside a **seamless, mobile-first, continuous digital camera space ("一镜到底")** where simulated product surfaces and physical metaphors enter, interact, and fluidly transition.

---

## Dark Style: Core Principles

### 1. Mobile-First Readability (Assume a 6-Inch Phone Screen)
Most technical explainer videos on YouTube, Bilibili, and X are watched on smartphone screens. If text or diagrams are designed for a 27-inch desktop monitor, they are completely unreadable on a phone.
- **Ban Presentation Chrome**: Never display slide headers, eyebrow category tags, chapter breadcrumbs, or `01 / 20` page numbers. These steal 25% of the viewport and immediately make the video look like a corporate PowerPoint deck.
- **Large, Bold Typography**:
  - Key labels and button text: **Minimum 24px–32px**, font weight 700–800.
  - Code snippets: **Minimum 26px–32px** (monospaced), line-height 1.6.
  - Headlines & Focal Words: **44px–64px**, bold and centered.
- **Thick Skeleton Primitives**: Skeleton placeholder bars must be chunky pills (`height: 16px–24px`, rounded 9999px), not thin hairline wires.
- **Extreme Restraint**: Show only **one primary visual idea** on screen at any moment. Never cram 4–6 small panels side by side; if showing comparison, use 2 massive cards with high contrast.

### 2. The Continuous Canvas ("一镜到底" — Blurring Slide Boundaries)
A true motion graphic explainer **never feels like a slideshow**. The concept of a "slide" is completely dissolved.
- **Shared Persistent Canvas**: The scene lives on a unified dark studio stage (`#0A0B0E`) with soft ambient lighting that persists across the entire timeline.
- **Choreographed Overlapping Transitions**:
  - When Beat A ends, its visual card does not disappear into a hard cut. It smoothly pushes back and drifts out (`scale: 0.88`, `translateX: -120px`, `opacity: 0`).
  - Simultaneously (with an 8–15 frame overlap), Beat B's card slides in from the opposite side (`translateX: 120px ➔ 0`, `scale: 0.94 ➔ 1.0`, `opacity: 0 ➔ 1`).
  - Elements can persist across cuts: an animated cursor, an architectural packet, or a mascot icon can travel continuously from the center of Scene A directly into the UI of Scene B.
- **Camera Depth & Morphing**: Zoom forward into a specific sub-panel to transition to the next topic, or fan out cards in 3D perspective before pulling the next hero card into full focus.

### 3. The Skeleton Rule (3–7 Words Max)
Never display paragraphs of text. Replace 95% of background content with rounded skeleton bars. Keep only **3 to 7 high-impact words** in sharp typography (e.g., `+ Add`, `taste`, `10s–16s`, `Promise Mismatch`). Viewers cannot read text while processing motion.

### 4. Physical & UI Metaphor First
Reify every abstract concept into a tangible UI widget or physical object:
- *Attention / Hook* $\to$ A physical fishing hook dropping from a browser URL bar.
- *Qualitative Metric (Taste, DX, Latency)* $\to$ A vertical level meter / slider with tick marks and glowing needle.
- *Duration Constraints* $\to$ An NLE timeline bar with range brackets and playhead scrubber.
- *Anti-patterns* $\to$ Comparative cards with `✗ Red Error` vs `✓ Green Success`.
- *Automated QA* $\to$ A floating circular inspection loupe scanning across rows.

### 5. Kinetic Eye-Guidance Cursor & Realistic Micro-Interactions (目光导引与拟真微交互)
Interactions must look and feel like an authentic, highly polished software demonstration, not a static presentation:
- **The Cursor as Retinal Anchor**: The audience's eye naturally tracks moving focal points. Never read a code line, reference an architecture block, or explain a UI control while the screen remains static. Move the cursor directly to the token, parameter, or button being discussed.
- **Natural Curved Trajectories**: Use parabolic or quadratic Bezier motion (`cubic-bezier(0.25, 1, 0.5, 1)`) with acceleration and deceleration. Cursors do not travel in robotic straight lines.
- **Physical Micro-Feedback**:
  - *Hover State*: As the cursor approaches a target, the element elevates (`translateY(-2px)`), brightens, or glows.
  - *Click Depression*: When clicked, the cursor squishes (`scale: 0.88`), the button compresses (`scale: 0.96`), and an expanding translucent ripple expands outward.
  - *Timeline / Scrubber Drag*: When explaining durations or progress, simulate dragging a timeline playhead or slider thumb, showing live frame scrub or counter updates.
  - *Code Token Hover*: When explaining code, the cursor hovers over a function or parameter to reveal an authentic, beautifully styled TypeScript tooltip (e.g., `(method) format(code: string): Promise<string>`).

### 6. Show the Collision, Don't Preach the Collision (直观因果与灾难还原)
Never lecture about an abstract problem on a static slide. If explaining an architectural flaw (e.g., out-of-order responses, race conditions, memory leaks, unhandled disconnections):
- **Step 1: Animate the Real Disaster**:
  - Show the packets or events actually travelling across threads/boundaries.
  - When Request A (slow, 200ms) and Request B (fast, 10ms) leave, show Request B racing ahead and returning first.
  - Show the naive Host thread popping the *first* awaiting Promise resolver for Request B's payload.
  - **Flash the Consequence**: Show the code editor or UI violently breaking in red: `TypeError: Cannot read properties of boolean (reading 'split')`. The audience must instantly see the disaster unfold before their eyes.
- **Step 2: Animate the Resolution (The "Aha!" Moment)**:
  - Stamp each packet with a glowing correlation badge: `[ID: 41]` and `[ID: 42]`.
  - Show the `Map<id, Promise>` lookup table. When `[ID: 42]` returns, a laser line connects directly to slot 42, resolving the correct Promise cleanly while slot 41 continues waiting.
  - The mechanism is understood in 3 seconds of animation without needing a computer science degree.

### 7. Industry Benchmark Contrast (行业标杆对比法则)
Whenever introducing a modern abstraction (like kkRPC, tRPC, or custom proxies), contrast it against the established industry standard developers already know (such as **JSON-RPC 2.0**, REST, or raw postMessage):
- **Side-by-Side Architectural Split**:
  - Display the traditional JSON-RPC envelope: `{"jsonrpc": "2.0", "id": 1, "method": "formatCode", "params": [...]}`.
  - Highlight the real-world friction:
    1. *String-based dispatch*: Typos like `"fomatCode"` pass compilation and crash at runtime.
    2. *Pure JSON limits*: Cannot pass callback functions (`(progress) => ...` throws `DOMException`); cannot transfer zero-copy `ArrayBuffer` without costly stringification.
    3. *Manual boilerplate*: Hundreds of lines of route registration vs 1 typed Proxy line (`await api.format(code)`).
- This establishes deep technical credibility and grounds the innovation in familiar developer experience.

---

## Detailed References

Before implementing or scripting scenes, read the relevant guide:

- Read [references/ui-motion-grammar.md](references/ui-motion-grammar.md) for mobile scaling ratios, Bezier trajectory math, and continuous transition formulas.
- Read [references/visual-metaphors.md](references/visual-metaphors.md) for translating software concepts into physical/UI metaphors.
- Read [references/storyboard-and-scripting.md](references/storyboard-and-scripting.md) for scripting pacing, the 5-act explainer arc, and presenter cue annotations.
- Read [references/remotion-primitives.md](references/remotion-primitives.md) for Remotion component architecture and frame-driven transitions.

---

## Dark Style: Pre-Render Quality Checklist

- [ ] **Mobile-First Test**: Preview the video scaled down to 360px wide (smartphone simulation). Can every label, code line, and button be read instantly without squinting?
- [ ] **No Slide Chrome**: Are there any presentation headers, slide titles, eyebrow tags, or page counters? If yes, remove them completely.
- [ ] **Continuous Transition Check**: Does any transition between narration segments use a jarring hard cut? If yes, apply choreographed push/pull, zoom-through, or element carry-over.
- [ ] **3–7 Words Rule**: Does any frame contain more than 7 real readable words? If yes, convert background text to thick skeleton pills.
- [ ] **No Static Stalls**: Does any visual hold completely still for more than 3.5 seconds? If yes, add a secondary motion (cursor drift, subtle camera scale, or playhead sweep).
- [ ] **Eye-Guidance Cursor**: Does the scene use an active cursor or focal beam to guide the viewer's gaze to the exact token, button, or control being spoken about?
- [ ] **Visual Causality / Disaster Demonstration**: If an architectural bug or race condition is described, is the collision/type error actually animated on screen rather than just spoken about?
- [ ] **Industry Benchmark Contrast**: If introducing an abstraction, is it contrasted with familiar industry standards (e.g. JSON-RPC 2.0)?
