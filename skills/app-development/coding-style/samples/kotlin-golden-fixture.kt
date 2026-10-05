// Cross-language golden fixture: one hash-annotated test dataset adjudicates TS/Swift/Kotlin/ArkTS - four platforms.
// From ListenFlow/apps/android/core/domain/src/main/kotlin/sh/kunkun/mobile/core/domain/
// PlaybackReducer.kt:10-38 (read 2026-10-05).
// Companion discipline: pure reducer (no clock/network/storage; nowMs injected via context); platform semantic
// differences pinned with explicit constants + comments; comments reference task IDs and specs - parity work is tracked and traceable.
package sh.kunkun.mobile.core.domain

/**
 * Kotlin port of the TypeScript playback reducer (P4-T05,
 * `packages/listenflow-domain/src/playback-reducer.ts`; iOS parity in P6-T02)
 * — the shared cross-language playback contract (REQ-043).
 *
 * Pure: `reducePlayback(state, event, context)` folds one driver event into
 * the next state plus an ORDERED list of effects. The golden fixture file is
 * hash-identical (1dd03571…) to the TypeScript and Swift suites'; the JSON
 * wire shapes here (`jsonObject` / decode) match the TS field names field for
 * field, so the same `expectedEffects` / `expectedStateSubset` data decides
 * all three languages.
 *
 * Invariants pinned by the fixtures (identical to the TS suite):
 * 1. Urgent audio preempts ONLY after the resume snapshot is durably saved:
 *    CLAIM_GRANTED → PERSIST → SNAPSHOT_SAVED → PAUSE → MEDIA_PAUSED corrects
 *    the position → AUTO_MARKER_SAVED → PLAY. SNAPSHOT_FAILED aborts.
 * 2. Restore after urgent audio is guarded by everything in the snapshot;
 *    any drift degrades to SHOW_RETURN_ACTION. MEDIA_STOPPED is a real stop,
 *    never play_completed.
 * 3. eventId is the identity of ONE automatic speech: local TTS first and
 *    cloud audio later for the SAME eventId never speaks twice (AC-P7-T02-01).
 */
object PlaybackReducer {
    const val PREPARE_BUDGET_MS: Long = 2000
    /** JavaScript's Number.MAX_SAFE_INTEGER — the TS "no expiry" lane marker. */
    const val MAX_SAFE_INTEGER: Long = 9_007_199_254_740_991L
}
