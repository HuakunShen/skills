# Replaceable narration provider adapter

## Separate generation from rendering

The narrated-video pipeline consumes local audio files and measured durations. It does not choose a voice or contact a TTS service during `narration:render`.

Give every provider the same input and output contract:

```text
input:  segment { id, text, target public audio path, language, optional pacing/voice preference }
output: { id, local path, measured duration, provider, voice, model or engine, optional word timestamps }
```

Keep the output keyed by manifest `id`. Preserve metadata locally with the audio, then copy or normalize the accepted file to its ignored `public/narration/audio/...` manifest path. Re-run duration probing after every replacement.

## Use the HyperFrames media-use audio engine

For a provider-neutral batch, use HyperFrames media-use's audio engine. It accepts `audio_request.json` and returns `audio_meta.json` with one `id`-keyed voice path, duration, and—when available—word timestamps:

```bash
node <MEDIA_USE_SKILL>/audio/scripts/audio.mjs \
  --request ./audio_request.json \
  --out ./audio_meta.json \
  --only tts
```

Construct `lines` from the narration manifest's `{ id, text }`; do not use inferred text or slide screenshots as the narration source. Run the media-use provider preflight before any external call. If sign-in, API billing, or an unavailable local model changes the route, surface that choice instead of silently downgrading voice quality.

## Provider routes

| Route | Strength | Trade-off | Word timestamps |
| --- | --- | --- | --- |
| HeyGen Starfish | Highest-quality default in the media-use path; one call can return speech and alignment | Requires authenticated HeyGen access; usage/billing policy applies | Yes |
| ElevenLabs | Large cloud voice catalog and an established Remotion voiceover integration | Requires an API key; obtain alignment separately when needed | No in the media-use adapter |
| Kokoro-82M | Local, private, offline once installed; multilingual voice families | Lower ceiling than chosen cloud voices; no native words | No |
| Human recording | Best control over emphasis and credibility | Requires recording and review time | Use provider alignment or transcription |

For a quality-first technical explainer, audition HeyGen Starfish first. For privacy/offline iteration, audition Kokoro. For an existing approved ElevenLabs voice, retain it and integrate its local files exactly like any other provider output. Keep the provider choice outside the manifest so changing it never changes slide/click semantics.

## Alignment and captions

If the selected provider returns word timestamps, store them alongside the accepted segment and join them by segment ID. Otherwise transcribe the frozen audio after acceptance.

- HyperFrames media-use offers a shared audio engine and local/cloud transcription routes.
- Remotion can turn an existing transcription into caption data, including with `@remotion/openai-whisper`; its Whisper.cpp path is a local alternative.
- Render captions only from the accepted audio. Keep captions segment-bounded, monotonic, readable at native resolution, and separate from the source narration text when recognition differs.

Use Remotion's `<Audio>` with `staticFile()` and a `Sequence` for placement. Measure file durations before composition registration; `calculateMetadata` is appropriate when a Remotion project derives duration dynamically. This Slidev pipeline may instead retain its compiled frame timeline, as long as both derive from the same accepted local files.

## Voice acceptance criteria

Before batch generation, review representative samples for pronunciation of APIs, identifiers, English/Chinese switching, pauses around code, pace, intelligibility, and absence of mechanical cadence. For dense code, slow or rewrite the sentence; never rely on a high playback rate to force it into a state duration.

After changing provider, voice, model, speed, or script punctuation, treat every affected file as new audio: replace it locally, rerun validation and timeline build, regenerate captions/alignment, render, and inspect the encoded MP4.
