# Narrated Slidev MP4 QA contract

## Source and pipeline checks

Run the repository's focused narration tests and the normal Slidev production build. Then run the complete local pipeline in this order:

```text
validate -> build timeline -> capture states -> render -> inspect
```

The completed capture set must have exactly one 1920x1080 PNG for every unique `(page, click)` state in the compiled timeline, with no missing, extra, or diverging public mirror files.

The final inspector must fail closed unless the MP4 has:

- exactly one H.264 video stream and one AAC audio stream;
- 1920x1080 video at 30 FPS;
- total duration within a documented tolerance of the compiled frame duration;
- no malformed or missing duration/stream metadata.

## Native-resolution visual review

Inspect encoded MP4 frames, not just source PNGs. Check all of the following:

- the opening state;
- a same-slide click after the crossfade has settled;
- a slide-to-slide transition;
- every explicit silent state;
- every dense code, table, or diagram state;
- every `v-mark` / Rough Notation state after the capture resize-and-settle path;
- the final state.

Reject clipping, unexpected overlap, invisible or mis-scaled code, stale click content, duplicate-state bleed after a settled transition, shifted annotations, wrong slide numbers, black frames, or controller UI in a capture.

## Audio and semantic review

Listen to opening, same-slide, slide-boundary, silent, and final sections. Confirm the accepted audio starts after its configured visual transition and lead-in, ends before the following advance, and says the narration text assigned to the visible state. Do not treat codec metadata as proof of semantic A/V alignment.

## Handoff

State the exact local MP4 path, actual duration, metadata-check result, visual samples reviewed, and the distinction between tracked source and ignored local assets. Report source commits separately; never imply that private audio or rendered video was committed or uploaded.
