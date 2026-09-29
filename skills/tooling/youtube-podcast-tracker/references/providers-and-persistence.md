# Provider and persistence adapters

The core runner should depend on small contracts rather than product-specific calls.

## Discovery contract

```text
list_recent_videos(subscription, window) -> VideoCandidate[]
get_metadata(candidate) -> VideoRecord
get_transcript(video, credentials?) -> TranscriptResult
download_audio(video, constraints) -> LocalArtifact
```

Every candidate must return a stable provider ID, canonical URL, title, publication time when available, duration when available, and a provider-specific reason when transcript access is unavailable.

### YouTube

`yt-dlp` can enumerate a channel handle or URL with a flat playlist pass, then resolve individual video metadata. Use the immutable video ID for `source_key`. For transcript work, request only subtitle files with `--skip-download`; do not download the video. Auto captions are usable only when the user accepts them and the language is suitable.

### Bilibili

`yt-dlp` can enumerate a `space.bilibili.com/<uid>` page and resolve individual videos to BV/AV IDs, metadata, duration, and media formats. Subtitle access is provider/account dependent: a public probe may expose only `danmaku`, while ordinary subtitles can report “only available when logged in.” Treat this as `login_required`, and retry only with an authorized cookie/session supplied by the user. `danmaku` is not a spoken transcript and must not be summarized as one.

When the user has logged into Bilibili in Chrome and authorized local Keychain access, `yt-dlp --cookies-from-browser chrome --list-subs <video-url>` can expose AI subtitle tracks such as `ai-zh` (SRT) alongside `danmaku`. Treat `ai-zh` as machine-generated subtitles, record that provenance, and retrieve only the subtitle file with `--skip-download --write-subs --sub-langs ai-zh --sub-format srt`. Do not export or persist the browser cookies. On macOS, cookie extraction can pause while the OS asks permission to read Chrome's Keychain item.

Do not assume channel listing fields such as title or upload date are populated in a flat pass. Resolve each video before applying the lookback window. Preserve the BV/AV ID even if the display title changes.

## Publisher contract

```text
find_by_idempotency_key(key) -> ExternalItem | None
create_summary(source_or_script, metadata, key) -> ExternalItem
create_audio(audio_artifact, metadata, key) -> ExternalItem
assign_playlist(item_id, playlist_id, expected_revision?) -> PlaylistReceipt
get_status(item_id) -> ExternalStatus
```

### ListenFlow MCP

Use the connected ListenFlow tools when they are available. `source` means raw material that ListenFlow rewrites; `script` means narration-ready text; `audio` means an item created for an external audio upload. Pass a stable idempotency key and include the source URL in metadata. Poll the item until it is ready or failed, then reconcile the result before retrying.

### ListenFlow REST

The REST adapter is optional. In the Kunkun Services implementation inspected for this skill, `POST /api/v1/listenflow/items` accepts summary inputs and `kind: "audio"`; audio upload is a separate raw-byte `PUT`. Read [listenflow-rest-audio.md](listenflow-rest-audio.md) for the tested request sequence, media constraints, key scopes, and troubleshooting.

- `GET /api/v1/listenflow/items/:id` to poll; `GET /api/v1/listenflow/items/:id/source` can return the source and spoken script when the authenticated API exposes it.
- Playlist operations use `/api/v1/listenflow/playlists`; replacing entries is revision-guarded. Do not silently append against a stale revision. The current assistant API-key purpose does not grant playlist-management scope, and the REST item-create schema has no `playlistId` field.

The exact base URL, Bearer key, scopes, and credential storage are installation-specific. Keep them in a secret manager or environment, never in a state record or prompt.

### Other destinations

Map another podcast service to the same publisher contract. If it cannot provide idempotency or playlist confirmation, keep a local receipt and stop after an ambiguous response until reconciliation is possible.

## Persistence contract

```text
get_subscription_records() -> Subscription[]
find_delivery(delivery_key) -> DeliveryRecord | None
claim_delivery(delivery_key, lease) -> ClaimResult
upsert_video(video_record) -> None
upsert_delivery(delivery_record) -> None
append_run(run_record) -> None
```

- **Notion:** create a subscriptions database and a deliveries database. Store the script in the delivery page body, not in a small title field. Upsert by `delivery_key` and keep the ListenFlow item ID, status, source URL, transcript status, and playlist ID visible.
- **Google Drive:** use a Google Sheet when the user wants filters and table views; use a canonical Markdown/JSON file when they want portability. Use Drive revision checks and keep scripts as linked Docs or files when they are long.
- **Local Markdown:** use one canonical file with a human summary and machine-readable records. Use a lock and atomic replacement; do not let two scheduled runs rewrite the same file concurrently.

The adapter may add backend-specific views, but it must not rename the logical keys or store secrets.
