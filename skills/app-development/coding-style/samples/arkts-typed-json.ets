// ArkTS: take "TypeScript without any" seriously - hand-written typed JSON tree + fail-closed decoder.
// From ListenFlow/apps/harmony/entry/src/main/ets/domain/Contracts.ets:1-29 (read 2026-10-05).
// The restricted dialect does not lower type discipline; patterns make up for it. The wire contract is imported
// from the shared TS package (packages/listenflow-contracts doubles as an hvigor module) - no fourth hand-written copy.
/**
 * ArkTS contracts and the JSON boundary (P8-T02, spec 12 §2/§7).
 *
 * ArkTS is NOT an arbitrary TypeScript runtime: there is no `any`, no dynamic
 * property access and no structural duck-typing at the boundary. This file is
 * therefore the ONE place where wire JSON becomes domain values:
 *
 *   1. a hand-written JSON parser builds a typed [JsonValue] tree (no
 *      JSON.parse into untyped objects, no `as` casts papering over shapes);
 *   2. explicit decoders validate every field they read and return a
 *      [DecodeResult] carrying a PATHED error instead of silently defaulting —
 *      a missing or mistyped field is a refusal, never a guess;
 *   3. encoders turn domain values back into [JsonValue] with the exact TS wire
 *      field names, so the golden subset/forbidden comparisons see the same
 *      shapes the TypeScript suite sees;
 *   4. [canonicalJson] gives a deterministic, key-sorted rendering used by the
 *      purity check.
 */

// ─── the typed JSON model ───

export enum JsonKind {
  object = 'object',
  array = 'array',
  string = 'string',
  number = 'number',
  boolean = 'boolean',
  null = 'null'
}
