# Replaceable narration provider adapter

## Separate generation from rendering

The narrated-video pipeline consumes local audio files and measured durations. It does not choose a voice or contact a TTS service during `narration:render`.

Give every provider the same input and output contract:

```text
input:  segment { id, text, target public audio path, language, optional pacing/voice preference }
output: { id, local path, measured duration, provider, voice, model or engine, optional word timestamps }
```

Keep the output keyed by manifest `id`. Preserve metadata locally with the audio, then copy or normalize the accepted file to its ignored `public/narration/audio/...` manifest path. Re-run duration probing after every replacement.

## Selection precedence and safe default

Resolve TTS exactly once for a production run:

1. If the user supplies an adapter, provider, voice, or recording method, use that method strictly. It must produce the input/output contract above. A failed user-supplied route is an error, not permission to change the voice.
2. If the user supplies no method, use **local Kokoro-82M** through HyperFrames media-use. For English technical narration, default to `am_michael`; retain language, voice, speed, and engine in local metadata.
3. If Kokoro is unavailable, surface its installation diagnostic. Do not silently use macOS `say`, HeyGen, ElevenLabs, or `provider:auto`.

The local CLI delegates to a Python/ONNX Kokoro environment. It may require `kokoro-onnx` and `soundfile`, with `HYPERFRAMES_PYTHON` pointing at the chosen virtual environment. Initial model setup is separate from a deterministic render and must be reported. Explicitly cap batch concurrency: every local TTS process loads a model, so cold-start fan-out can exhaust memory.

Use an ignored local adapter configuration or an explicit CLI flag for the selection. Do not put credentials, a provider-specific voice ID, or a shell command string in `script.yaml`. A user adapter must be invoked with fixed argv values and write only its declared output directory.

## Use the HyperFrames media-use audio engine

For a provider-neutral batch, use HyperFrames media-use's audio engine. It accepts `audio_request.json` and returns `audio_meta.json` with one `id`-keyed voice path, duration, and—when available—word timestamps:

```bash
node <MEDIA_USE_SKILL>/audio/scripts/audio.mjs \
  --hyperframes <local-audio-workdir> \
  --request ./audio_request.json \
  --out ./audio_meta.json \
  --only tts \
  --provider kokoro \
  --voice am_michael
```

Set `HYPERFRAMES_TTS_CONCURRENCY=1` for a cold local batch unless the machine has been proven to sustain more. Construct `lines` from the narration manifest's `{ id, text }`; do not use inferred text or slide screenshots as the narration source. `audio_meta.json` returns one id-keyed local path, measured duration, and available words for every accepted line.

Use `--provider kokoro` for the skill default. Do **not** use the engine's `auto` mode as an implicit default: it may prefer authenticated cloud providers. Use `--provider heygen` or `--provider elevenlabs` only when the user explicitly selected that provider and authorized sending narration text to it.

## Provider routes

| Route | Strength | Trade-off | Word timestamps |
| --- | --- | --- | --- |
| HeyGen Starfish | High-quality cloud option; one call can return speech and alignment | User must explicitly choose it and authorize narration-text upload; authentication and usage/billing policy apply | Yes |
| ElevenLabs | Large cloud voice catalog and an established Remotion voiceover integration | Requires an API key; obtain alignment separately when needed | No in the media-use adapter |
| Kokoro-82M | **Skill default**: local, private, offline once installed; multilingual voice families | Model/environment setup and local CPU/RAM cost; align after acceptance when words are absent | Provider-dependent; transcribe when needed |
| Human recording | Best control over emphasis and credibility | Requires recording and review time | Use provider alignment or transcription |

For an explicit quality-first cloud request, audition HeyGen Starfish first. For the no-provider default, use Kokoro without an external call. For an existing approved ElevenLabs voice, retain it and integrate its local files exactly like any other provider output. Keep the provider choice outside the manifest so changing it never changes slide/click semantics.

## Alignment and captions

If the selected provider returns word timestamps, store them alongside the accepted segment and join them by segment ID. Otherwise transcribe the frozen audio after acceptance.

- HyperFrames media-use offers a shared audio engine and local/cloud transcription routes. Its preferred local transcript route can use Parakeet, with Whisper.cpp fallback.
- Remotion can turn an existing transcription into caption data, including with `@remotion/openai-whisper`; its `@remotion/install-whisper-cpp` path is a separate local **transcription** model, not TTS. It requires accepted audio converted to the API's WAV contract before word-level alignment.
- Render captions only from the accepted audio. Keep captions segment-bounded, monotonic, readable at native resolution, and separate from the source narration text when recognition differs.

Use Remotion's `<Audio>` with `staticFile()` and a `Sequence` for placement. Measure file durations before composition registration; `calculateMetadata` is appropriate when a Remotion project derives duration dynamically. This Slidev pipeline may instead retain its compiled frame timeline, as long as both derive from the same accepted local files.

## Voice acceptance criteria

Before batch generation, review representative samples for pronunciation of APIs, identifiers, English/Chinese switching, pauses around code, pace, intelligibility, and absence of mechanical cadence. For dense code, slow or rewrite the sentence; never rely on a high playback rate to force it into a state duration.

After changing provider, voice, model, speed, or script punctuation, treat every affected file as new audio: replace it locally, rerun validation and timeline build, regenerate captions/alignment, render, and inspect the encoded MP4.
