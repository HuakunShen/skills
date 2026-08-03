---
name: slidev-narrated-video
description: Turn a Slidev Markdown/Vue deck into a locally rendered, audio-synchronized MP4 by compiling a validated per-(page, click) narration manifest, capturing deterministic 1920x1080 slide states with Playwright, assembling them with Remotion, and verifying the result. Use when a developer deck needs both live click-synchronized playback and a reproducible narrated video, or when recording, re-recording, capturing, rendering, or QAing a Slidev narration pipeline.
---

# Slidev narrated video

Build a replaceable-per-state narration pipeline. Keep Slidev as the source of visual states, use audio duration as the timing authority, and render static captures offline. This workflow deliberately does not promise pixel-exact replay of arbitrary browser animation between click states.

Use the active Slidev skill for deck authoring and the active Remotion skill for framework-specific implementation. This skill owns the bridge between them.

## Choose the route

Use this skill when the final deliverable is a deterministic local MP4 built from an existing or new Slidev deck and segmented narration.

- Use a continuous-take Slidev recording workflow when the presenter will narrate one human take and repair it in post.
- Use a general technical-explainer workflow when the deck is only one part of a broader narrative or research product.
- Use this workflow when audio must be replaceable by slide/click state, video must be reproducible, or the same manifest must drive live autoplay and offline rendering.

## Establish the source boundary first

Before editing, record the worktree state and build the visual deck. Preserve unrelated changes.

Treat the following as different classes of source:

| Class | Track in Git | Purpose |
| --- | --- | --- |
| Slidev Markdown/Vue/CSS, manifest schema, scripts, tests, documentation | Yes | Reproducible pipeline source |
| `narration/script.yaml` and optional generated timeline JSON | Usually | Reviewable narration mapping and deterministic timing contract |
| TTS/recorded audio, state PNGs, MP4s, temporary exports | No by default | Local production inputs and regenerable artifacts |

Read [references/asset-and-git-boundary.md](references/asset-and-git-boundary.md) before provisioning audio, generating media, staging changes, or recovering from an accidental binary stage.

Use a project-local, ignored directory such as `public/narration/audio/` for production audio. The files may be served to both Slidev and Remotion, but must not enter Git merely because they sit under `public/`.

## Define one canonical manifest

Keep slide content in `slides.md` and narration in `narration/script.yaml`. Do not hand-edit generated timeline JSON.

Use one manifest segment per visible `(page, click)` state. `click: 0` means the initial state of a 1-based Slidev page. Every represented slide begins at click zero; later clicks are unique and strictly increasing. Model a no-speech state explicitly with `silentMs`, rather than omitting it.

```yaml
version: 1
defaults: { transitionMs: 300, leadInMs: 100, tailMs: 150 }
slides:
  - page: 3
    segments:
      - id: channel-intro
        click: 0
        text: "The channel owns pending calls and response dispatch."
        audio: narration/audio/s003-c000.mp3
      - id: channel-pause
        click: 1
        text: ""
        silentMs: 700
```

Require and test these invariants:

- stable, globally unique segment IDs;
- exactly one of `audio` and `silentMs` for every segment;
- integer non-negative timing values and integer compiled frame counts;
- required, auditable `text`, even when speech is produced outside the repository;
- audio paths relative to `public/`, lexically inside it, and still inside it after `realpath` resolution; reject symlink escapes;
- actual audio durations measured with `ffprobe`, not estimated from text;
- contiguous timeline entries: each start frame equals the preceding start plus duration.

Compile milliseconds with one documented rounding function, for example `Math.round(milliseconds / 1000 * fps)`. Store derived `transitionFrames`, `leadInFrames`, `audioFrames`, `tailFrames`, `startFrame`, `durationInFrames`, and the generated state-image path. The total composition duration must equal the final entry end frame exactly.

## Keep narration generation replaceable

Never couple a specific TTS provider—or an operating-system voice—to `narration:render`. The provider adapter accepts manifest `id` and `text`, produces one frozen local audio file per narrated segment, and optionally returns word timestamps. The compiler then probes the accepted files and builds the timeline exactly as it would for a human recording.

Read [references/tts-provider-adapter.md](references/tts-provider-adapter.md) before generating, replacing, or evaluating narration. It routes the HyperFrames media-use audio engine and Remotion caption support without requiring the final video renderer to become a TTS client.

Resolve the narration method in this exact order:

1. **User-provided method wins.** If the user names a provider, voice, recording workflow, local model, or adapter, use that method exactly. Validate its segment-keyed local output; do not silently fall back to another provider.
2. **No method supplied uses the skill default.** Generate locally with HyperFrames Kokoro-82M, using `am_michael` for English technical narration at a measured, reviewable pace. Invoke the media-use audio engine with `--provider kokoro`, never `provider:auto`; `auto` can choose a cloud service merely because credentials are present.
3. **If the default is unavailable, stop with its setup diagnostic.** Do not silently substitute macOS `say`, a cloud provider, or a different voice. The user can then provide a method or explicitly authorize a different route.

Keep selection outside `script.yaml`: it changes the sound production, never the slide/click semantics. For a project implementation, represent it as an ignored local adapter configuration with a named provider and bounded options; pass arguments as an argv array, never an interpolated shell command.

Use this acceptance loop:

1. Resolve the user-provided method or the explicit local default; record provider, voice, engine/model, language, and pace locally.
2. Synthesize two or three representative segments: opening, dense technical explanation, and closing.
3. Listen before batch generation. Revise script punctuation, pacing, pronunciation, or voice selection rather than speeding up dense speech later.
4. Generate the approved per-segment audio outside the render command; normalize it to the project's audio contract and retain provider/voice/model metadata locally.
5. Store the accepted files at the manifest paths, validate and rebuild the timeline, then render. Regenerate captions or word alignment only after accepting replacement audio.

Keep audio production outputs in an ignored local asset directory. Commit the provider-agnostic manifest and, when useful, a schema for local generation metadata—not credentials, raw audio, or provider responses.

## Build the three adapters

### Live Slidev playback

Use Slidev public navigation APIs only. Keep the playback state machine framework-light and test it independently from Vue.

- Require an explicit **Start narration** user gesture before the first `HTMLAudioElement.play()`; never attempt autoplay on page load.
- Start the segment for the current `(page, click)` state, then advance only after its audio/silence and tail are complete.
- Cancel pending callbacks, ignore stale `ended` events, and stop audio on manual navigation, pause, or restart.
- Hide the controller during automated capture through an explicit capture query parameter.

### Playwright state capture

Render one screenshot for every unique `(page, click)` state referenced by the compiled timeline.

1. Start Slidev as a child process on loopback only (`127.0.0.1`), choose a free port, and always stop it in `finally`.
2. Create a fresh page for each state. Navigate directly to its slide, wait for fonts and the target slide, then replay exactly its click count.
3. Wait for the documented visual-settle budget. Move the pointer away, dispatch `resize`, and wait again before screenshotting. Rough Notation markers otherwise can measure before Slidev's fitted 1920x1080 canvas reaches its final scale.
4. Capture exactly 1920x1080 PNGs. Write canonical and `public/` mirror copies atomically, verify their dimensions and byte equality, and reject unexpected or missing filenames.

Do not render the live Slidev app inside Remotion. A separate browser page for each state prevents navigation history, animations, and controller state from leaking across captures.

### Offline Remotion assembly

Use the compiled timeline as the sole composition input.

- Place the captured state image in a sequence bounded by its compiled duration.
- Crossfade from the previous image during `transitionFrames`; place audio after transition and lead-in.
- Render narration audio and slide images using public/static asset paths only.
- Validate runtime props before composing and reject a timeline whose duration does not match the registered composition.
- Keep the renderer deterministic: no render-time network calls, clocks, random values, or live Slidev execution.

Remotion composes supplied audio with `<Audio>`, `staticFile()`, and frame-bounded sequences; use it to place accepted speech, measure composition metadata, and render captions. Do not treat it as a speech-quality model. Its Web Audio support is suitable for procedural tones or signals, not narration generation.

## Make re-recording local and cheap

Treat audio as timing authority once accepted. Freeze the chosen per-state files and regenerate timing from their measured durations.

| Change | Required work |
| --- | --- |
| Narration text, audio file, silence, or timing only | Re-provision audio; validate; rebuild timeline; render; inspect |
| Slide Markdown, CSS, fonts, images, click mapping, annotations, or any visible state | Validate; rebuild; recapture all referenced states; render; inspect |
| Remotion-only layout/crossfade styling | Render from existing captures; inspect |
| A Slidev production build may remove `dist/` media | Build first, then render the final MP4 again |

Do not regenerate TTS implicitly from the render command. Keep generation or recording separate from the deterministic render path.

## Test the boundary, not local leftovers

Test the manifest/compiler, playback state machine, capture helpers, Remotion timeline validation, and media inspector.

Make tests pass in a clean clone without production narration. Generate tiny temporary WAV fixtures inside the test, clean them up, and never depend on a committed MP3 or a developer's local audio directory. Test path traversal and symlink escape rejection explicitly.

Expose commands with a deliberate order:

```text
narration:validate  # schema, semantic rules, local audio presence and probing; no generated write
narration:build     # regenerate timeline
narration:capture   # rebuild visual state PNGs
narration:render    # assemble MP4 from timeline, captures, and local audio
narration:inspect   # ffprobe-based contract check
narration:video     # validate -> build -> capture -> render -> inspect
```

Run the deck's ordinary production build before the full-video command. Keep validation non-mutating so it is safe in CI and preflight checks.

## Finish with a real release gate

Read [references/qa-contract.md](references/qa-contract.md) before declaring a video complete.

At minimum, run narration tests, the Slidev production build, and the full local pipeline. Then inspect encoded—not merely source—frames at native resolution: first segment, settled same-slide click, slide boundary, explicit silence, dense code or diagram, every Rough marker state, and final segment. Listen to the relevant transitions and confirm spoken text belongs to the state that is visible.

Report the local output path, duration, codecs, dimensions, frame rate, test/build results, and which large artifacts remain ignored. Never stage production audio, captured PNGs, or MP4s as part of the source change.
