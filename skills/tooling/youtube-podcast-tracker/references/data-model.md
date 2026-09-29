# Portable data model

The model describes the logical records. A persistence adapter may represent them as Notion pages, Google Sheet rows, Drive files, SQLite rows, or sections in one Markdown file. Keep the field names stable even when the backend's column names differ.

## Records

### Subscription

| Field | Meaning |
| --- | --- |
| `subscription_id` | Stable local ID; never use the display name as the key. |
| `provider` | `youtube`, `bilibili`, or another supported discovery provider. |
| `channel_id` | Provider-stable channel/user ID when available. |
| `channel_url` | Canonical public channel URL. |
| `enabled` | Whether discovery runs for this source. |
| `lookback_hours` | Normal scan window; default can be 24. |
| `recovery_lookback_hours` | Wider window used after a failed or delayed run. |
| `default_route_id` | Route used when no higher-priority rule matches. |
| `notes` | Human-maintained context; may hold exact source-specific route conditions when the persistence backend has no structured route field; never credentials. |

### RouteRule

| Field | Meaning |
| --- | --- |
| `route_id` | Stable route name plus a version when its behavior changes. |
| `priority` | Lower numbers run first; ties are invalid or require an explicit tiebreaker. |
| `match` | Provider/channel/video ID/tag/title predicates. Keep it declarative. |
| `action` | `summary_podcast`, `audio_only`, or `skip`. |
| `destination_id` | Logical publisher account/configuration, not a secret. |
| `playlist_id` | Stable destination playlist ID; prefer IDs over names. |
| `language` | Output language for summary/script generation. |
| `max_duration_minutes` | Target ceiling for generated audio, not permission to distort the source. |
| `rights_policy` | `private_use`, `allowlisted_license`, `review_required`, or another explicit policy. |
| `enabled` | Whether the rule is active. |

### VideoRecord

| Field | Meaning |
| --- | --- |
| `source_key` | `provider:video_id`, for example `youtube:-XWSJM-Ue-o` or `bilibili:BV...`. |
| `video_id` | Immutable provider video ID. |
| `channel_id` | Provider-stable source ID. |
| `title` | Metadata snapshot; not a deduplication key. |
| `canonical_url` | URL used for later reconciliation. |
| `published_at` | Provider publication time in UTC when available. |
| `discovered_at` | Time this run first saw the item. |
| `duration_seconds` | Provider-reported duration, if available. |
| `transcript_status` | `available`, `missing`, `login_required`, `unusable`, or `not_requested`. |
| `transcript_locator` | Optional local/remote reference; do not put secrets in it. |
| `metadata_hash` | Optional hash of the normalized source metadata. |

### DeliveryRecord

| Field | Meaning |
| --- | --- |
| `delivery_key` | `source_key:route_id:destination_id:playlist_id`; this is the idempotency boundary. |
| `route_id` | Route selected for this delivery. |
| `status` | See the state machine below. |
| `script_hash` / `audio_hash` | Hashes of generated or downloaded artifacts. |
| `script_locator` / `audio_locator` | Where the durable artifact can be found. |
| `external_item_id` | Destination episode/item ID. |
| `external_url` | Destination URL when one exists. |
| `attempts` | Bounded retry count. |
| `lease_owner` / `lease_expires_at` | Optional concurrency guard. |
| `last_error` | Redacted, actionable error summary. |
| `created_at` / `updated_at` | UTC timestamps. |

### RunRecord

Store `run_id`, `started_at`, `completed_at`, query window, source count, candidate count, delivered count, skipped count, failed count, and a redacted error summary. This makes a no-change run distinguishable from a scheduler that never ran.

## State machine

```text
discovered → classified → waiting_transcript → ready → processing
                                      │             │
                                      └─────────────┘
processing → uploading → published
processing → awaiting_approval → ready
processing → uploaded_unassigned
any active state → skipped | failed
```

`waiting_transcript` is appropriate when a provider says captions need login or may appear later; use `skipped` when the configured policy says not to retry. `uploaded_unassigned` is not `published` until playlist assignment and destination confirmation succeed.

## Backend mappings

- **Notion:** one database for `Subscription`, one for `DeliveryRecord`/`VideoRecord`, and page content for the script. Make `source_key` and `delivery_key` visible unique fields; use relations only as a convenience.
- **Google Drive:** a Google Sheet is the table-like option; a canonical JSON/Markdown state file in a dedicated folder is the simpler option. Use revision/ETag checks and reject conflicting writes.
- **Local Markdown:** keep a human-readable summary plus a machine-readable fenced JSON block or pipe-delimited table. Write a temporary file, flush/fsync, and atomically rename; use a file lock for concurrent runs.

Do not dual-write in the first version. Select one authoritative store per installation and make migrations an explicit later operation.
