# ListenFlow REST audio delivery

Use this reference when an eligible video should be uploaded as its original audio, or when a transcript-backed summary is submitted through ListenFlow's REST API. The REST API supports external audio bytes even when the connected ListenFlow MCP tools do not expose a binary-audio upload operation.

## Credentials and base URL

- Read `LISTENFLOW_API_KEY` from the runtime environment (this installation keeps it in a local `.env`). Never print it, place it in a URL, persist it in Notion/Drive/Markdown, or include it in logs. Do not enable `curl -v` or shell tracing around authenticated requests.
- The current Kunkun Services production worker uses `https://api.listenflow.kunkun.sh` as `PUBLIC_API_ORIGIN` and its production route (`apps/api/wrangler.jsonc`). Older HTTP API docs still name `https://api.kunkun.sh`; the production config says that hostname is served by a legacy backend, so treat the live production config/OpenAPI as authoritative over stale docs. Permit an explicit `LISTENFLOW_API_BASE` override only when the user or deployment config identifies another host.
- Current key purposes in the implementation: `assistant` grants `add`, `read`, and `settings`; `extension` grants `add` and `read`. Audio item creation/upload requires `add`, and item polling requires `read`. Playlist mutations require `manage`, which the current `assistant` purpose does not grant.

## Audio upload contract

The API implementation and worker tests establish this flow:

1. Create an inert audio item with `POST /api/v1/listenflow/items`, JSON `{"kind":"audio","title":"...","includeInFeed":true}`, an `Authorization: Bearer …` header, and a stable `Idempotency-Key`. The response is HTTP 202 and includes `item.id` plus `uploadRequired: true`.
2. Send the audio file itself (not multipart and not base64) with `PUT /api/v1/listenflow/items/{id}/audio`. Include its accepted audio `Content-Type` and exact `Content-Length`; regular-file uploads with `curl --data-binary @file` preserve a known body length. The implementation streams bytes to storage.
3. Poll `GET /api/v1/listenflow/items/{id}` and confirm it is ready. Reconcile a timeout against the existing item before retrying; do not create a second item or assume a timed-out PUT failed.

For a YouTube audio-only route, download an audio-only format and extract M4A when available, for example `yt-dlp --format 'bestaudio[ext=m4a]/bestaudio' --extract-audio --audio-format m4a --output '<temp>/%(id)s.%(ext)s' '<video-url>'`. Verify the resulting duration, codec, byte size, and MIME before upload; M4A/AAC is `audio/mp4` and is accepted by the current API.

Example, with the key already loaded into the environment and the response handled without logging authorization headers:

```sh
BASE="${LISTENFLOW_API_BASE:-https://api.listenflow.kunkun.sh}"
KEY="${LISTENFLOW_API_KEY:?LISTENFLOW_API_KEY is required}"

curl --fail-with-body --silent --show-error \
  -X POST "$BASE/api/v1/listenflow/items" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: youtube:<channel-id>:<video-id>:audio:v1' \
  --data '{"kind":"audio","title":"<video title>","includeInFeed":true}'

BYTES=$(wc -c < "$AUDIO_FILE" | tr -d '[:space:]')
curl --fail-with-body --silent --show-error \
  -X PUT "$BASE/api/v1/listenflow/items/$ITEM_ID/audio" \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: audio/mpeg' \
  -H "Content-Length: $BYTES" \
  --data-binary "@$AUDIO_FILE"
```

Parse the create response to obtain `item.id`; do not copy a placeholder into a request. For MP3 use `audio/mpeg`. Other accepted content types in the current implementation include `audio/mp4`, `audio/m4a`, `audio/x-m4a`, WAV variants, `audio/aac`, `audio/ogg`, and `audio/opus`. Set the MIME type to match the actual encoded file.

The current implementation cap is 100 MiB (`100 * 1024 * 1024` bytes; documented for Free/Pro). Recheck the deployment's OpenAPI/plan when limits may differ. Reject or recompress anything at/over the applicable cap before calling the API. Keep some headroom rather than targeting the exact limit.

If an audio file is oversized, use ffmpeg to create a speech-oriented mono MP3, then inspect the new file's size, duration, and codec before upload:

```sh
ffmpeg -nostdin -i "$AUDIO_FILE" -vn \
  -c:a libmp3lame -ac 1 -ar 44100 -b:a 96k "$COMPRESSED_FILE"
```

96 kbit/s mono is a reasonable spoken-word fallback, not a universal fidelity rule. Re-encoding is lossy, so keep the original until the upload is confirmed. The final uploaded artifact—not the original—gets the `audio_hash` and MIME metadata in the delivery record.

## Feed, playlist, and summary behavior

- Set `includeInFeed: true` when the item should appear in the user's private ListenFlow podcast feed. This is distinct from assigning an item to a named playlist.
- The current REST `AddItemBodySchema` does not accept `playlistId`. Playlist entry replacement uses `/api/v1/listenflow/playlists/{playlistId}/entries` with an expected revision and a `manage`-scoped principal. Do not claim a REST audio item was added to a named playlist using an assistant key; record `uploaded_unassigned` and use an explicitly authorized management-capable app flow if playlist assignment is required.
- For transcript-backed summaries, use the normal `source`/`presetId` item path and a stable idempotency key. A transcript source is text, not an audio upload.
- Do not send both `url` and transcript `source` in one summary request. In production, supplying both selected the URL-ingestion route (`sourceType: "url"`) and the fetched page text replaced the caption transcript. For a transcript summary, send cleaned text in `source`, omit `url`, and keep the canonical video URL in the tracker record/custom prompt. Before continuing, verify the returned `sourceType` is `text` and the item source begins with the cleaned captions; if a URL-routed item was created by mistake, stop/cancel if possible and hide a ready item from the private feed rather than treating it as a valid delivery.
- When the REST key cannot manage playlists but the user's authenticated ListenFlow UI exposes per-item playlist assignment, use the item’s **More actions → Add to Playlist** menu, select the configured playlist, then verify the item appears on that playlist’s detail page before recording `Ready`. Playlist assignment does not publish the item publicly.

## Diagnose 401/403 without leaking the key

Compare the authenticated API request with a harmless unauthenticated `GET /openapi.json` on the same deployment. Inspect only status, content type, and a sanitized JSON `error` code; never dump the key, auth headers, or an unfiltered response body.

If both the authenticated API request and unauthenticated public OpenAPI request return the same non-JSON Cloudflare 403, the request is being blocked at the edge before the app's key-auth response can be identified. This result does not prove the key is invalid or valid. Do not rotate the key or repeat POST/PUT calls on that evidence.

When the user's browser can open the JSON OpenAPI document but a script gets Cloudflare 403, compare the network route and request headers before concluding the host is down. Use only the already-configured browser/system proxy; do not invent a proxy, change network settings, or expose the key. In this installation, direct Python requests and proxied requests with Python's default user agent got 403, while the existing Surge HTTP proxy plus a standard Chrome user agent returned JSON 200 for both OpenAPI and authenticated usage. After changing the route, verify with read-only GETs before any POST/PUT.

The app's REST production host and a connected MCP integration can temporarily point at different deployments. In this installation, the new item was `ready` on `api.listenflow.kunkun.sh` and visible in the ListenFlow web queue, while the connected MCP item's `get_item`/search returned no result and `api.kunkun.sh` returned 404 for that ID. If REST GET says `ready` but MCP lookup is empty, confirm the deployed host and the signed-in app queue before retrying; never create a duplicate to compensate for a stale/different connector.
