# Scheduling, recovery, and verification

## Scheduled runs

The runner must be safe to invoke from a Codex heartbeat, cron, a CI worker, or a manual command. A six-hour schedule is a cadence, not the deduplication mechanism. Use a 24-hour normal lookback with a small overlap; after an outage, use `recovery_lookback_hours` and the same delivery keys.

Each run should:

1. Acquire a run lease or record that another run is active.
2. Load the latest subscription and route configuration.
3. Discover and normalize candidates.
4. Claim each delivery key before transcript/TTS/download work.
5. Process, upload, assign playlist, and confirm in separate persisted transitions.
6. Release leases and append a run summary.

No-change runs should be quiet. Notify on a new ready episode, a failure requiring action, a login/credential problem, a playlist assignment failure, or a meaningful configuration conflict.

## Recovery rules

| Boundary | Persist before | If the process dies |
| --- | --- | --- |
| Discovery | candidate and source key | rediscover through overlap; deduplicate |
| Transcript | transcript status/hash | retry or keep `login_required`/`missing` |
| Script/TTS | script hash/locator | reuse the script; do not regenerate blindly |
| Download | audio hash/locator | validate temp artifact or restart safely |
| Upload | idempotency key | search destination before retry |
| Playlist | external item ID and expected revision | reconcile membership before append |
| Finalization | destination status and artifact IDs | mark ready only after confirmation |

Bound retries for provider rate limits, transient network errors, and model failures. Do not retry authorization, rights, malformed media, or an invalid playlist forever. A timed-out upload is `unknown`, not `failed`, until the destination has been queried.

## Verification before automatic publishing

Start with dry-run or a private/test playlist. Verify:

- repeated runs create one delivery for one source/route/destination/playlist;
- two concurrent workers cannot both claim it;
- a missing or login-gated transcript is recorded and skipped according to policy;
- direct audio cannot be selected by a summary fallback;
- generated scripts contain no invented facts or internal notes;
- audio MIME, duration, and byte hash are recorded;
- upload retries do not duplicate episodes;
- playlist assignment is confirmed with the current revision;
- Notion, Drive, and Markdown adapters preserve the same logical keys;
- transcript/title prompt-injection strings cannot alter routing or permissions.

Only after these checks pass should automatic publishing be enabled. Keep a `reconcile` operation available for records stuck in `processing`, `uploading`, or `uploaded_unassigned`.
