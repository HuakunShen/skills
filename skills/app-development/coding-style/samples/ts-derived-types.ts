// Types derived from values: single source of truth (excerpted from ListenFlow and refyard, read 2026-10-05)
//
// Technique: write each literal set once (inside an `as const` value) and derive types with `typeof`;
// lock cross-table consistency with exhaustive Records or Equal/Expect type-level assertions.

// ─── 2a. as const list → derived union ───
// From ListenFlow/packages/listenflow-core/src/codes.ts:150-164
// Original comment: union derived from the list, so they cannot disagree
] as const;

export type ListenFlowInputCode = (typeof LISTENFLOW_INPUT_CODES)[number];

// Object-shaped counterpart (from the pattern in kunkun-services/apps/api/src/errors.ts:9-50):
// export const ErrorCodes = { UNAUTHORIZED: "unauthorized", /* ... */ } as const;
// export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];

// ─── 2b. Exhaustive Record: adding a code without its status fails to compile ───
// From ListenFlow/packages/listenflow-core/src/errors.ts:36-58
/**
 * One table, so a code cannot mean 404 in one route and 400 in another.
 *
 * 404 is for a thing of the user's we could not find, 409 for a thing that exists but is
 * in the wrong state, 413 for material that is too big, and 400 for everything the caller
 * simply got wrong.
 */
const STATUS_BY_CODE: Record<ListenFlowInputCode, ListenFlowInputStatus> = {
	platform_config_invalid: 400,
	platform_config_conflict: 409,
	provider_unknown: 400,
	language_unknown: 400,
	preset_not_found: 404,
	scope_invalid: 400,

	credential_not_found: 404,
	voice_not_found: 404,
	source_not_found: 404,
	item_not_found: 404,
	platform_funding_disabled: 409,
	generation_snapshot_invalid: 409,
	idempotency_conflict: 409,
	// 503 with Retry-After semantics: the pause is temporary and operator-lifted, so
	// the status says "try later", not "your request was wrong".
	capacity_paused: 503,
	drive_not_connected: 409,
	drive_reauth_required: 409,
	drive_oauth_failed: 400,
	drive_file_missing: 404,
	drive_archive_failed: 409,
};

// ─── 2c. Type-level proof (Equal/Expect): the schema table and the operation list must match key for key ───
// From refyard/packages/git-contract/src/operations.ts:652-701
export type MutationKind = (typeof OPERATION_TARGET_LIST)[number][0];

/** Target kinds one operation accepts, preserved as literals for type-level pairing. */
export type TargetKindsOf<K extends MutationKind> = Extract<
  (typeof OPERATION_TARGET_LIST)[number],
  readonly [K, ...unknown[]]
>[1];

/** Mapped form of `OPERATION_SCHEMAS`, for `z.infer` lookups by kind. */
export type OperationFor<K extends MutationKind> = z.infer<
  (typeof OPERATION_SCHEMAS)[K]
>;

export type MutationOperation = {
  [K in MutationKind]: OperationFor<K>;
}[MutationKind];

/**
 * Compile-time proof that the schema object and the target list describe the same
 * set of operations. `Equal` is the standard invariance check; if a kind is added
 * to one and not the other, this line stops compiling.
 */
type Equal<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2
    ? true
    : false;
type Expect<T extends true> = T;
export type _SchemasMatchTargetList = Expect<
  Equal<keyof typeof OPERATION_SCHEMAS, MutationKind>
>;
/** The documented union has exactly 45 members; a list edit that changes that stops compiling. */
export type _MutationCount = Expect<
  Equal<(typeof OPERATION_TARGET_LIST)["length"], 45>
>;

// ❌ Counterexample (constructed, not repository code): hand-writing the same literal set twice lets it silently drift
// type Kind = "abortRebase" | "dropCommit";
// const SCHEMAS = { dropCommit: ... };  // forgot abortRebase - the compiler says nothing
// ✅ Correct: the zod schema's key set is locked by the Equal assertion above; missing one key stops compilation
