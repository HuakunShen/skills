# Local assets and Git boundary

## Keep production binaries local

Place recorded or TTS narration under an ignored project-local path such as:

```gitignore
public/narration/audio/
narration/generated/states/
dist/narrated-slides.mp4
```

Do not commit MP3, WAV, AIFF, TTS source files, captured PNGs, MP4s, or temporary exports by default. Track the manifest text and file names, not the private audio content. Keep a private backup or approved asset store outside the repository if the audio needs to survive cleanups or be shared.

Before generating production media, prove the audio path is ignored:

```bash
git check-ignore -v public/narration/audio/s001-c000.mp3
git ls-files public/narration/audio
```

The first command should name the ignore rule; the second should print nothing. An ignore rule does not remove a file that was already tracked.

Before a source commit, inspect the exact staging boundary:

```bash
git diff --check
git diff --cached --name-only
git ls-files public/narration/audio
```

Do not use broad `git add .` after media generation. Stage source paths explicitly.

If an audio or video binary is already staged, unstage it and keep the local file. If it was committed, stop and tell the user the commit scope and whether it was pushed; do not rewrite shared or remote history without explicit authorization.

## Make audio paths safe to load

Manifest audio paths are relative to `public/`. Validate both forms before probing or serving:

1. Reject absolute paths, `..` traversal, and lexical candidates outside `public/`.
2. Resolve the candidate and its parent with `realpath`; reject a symlink that resolves outside `public/`.
3. Pass the resolved path to `ffprobe` using a fixed argument list, never a shell string.

This protects both the compiler and the renderer from reading arbitrary local files through a manifest edit.

## Keep source and generated timing distinguishable

`script.yaml` is human-authored source. Timeline JSON is generated from source plus measured local audio. Do not edit the JSON manually, and do not use stale JSON after changing audio. A clean clone can run source tests and build the visual deck, but must fail clearly for commands that require absent private audio.
