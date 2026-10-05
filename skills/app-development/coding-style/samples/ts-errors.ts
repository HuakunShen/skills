// Error handling: closed error-code table + code-carrying Error class + structured guards
// (excerpted from refyard / kunkun / kunkun-services, read 2026-10-05)

// ─── 1. Closed code set: as const + a doc comment per code ───
// From refyard/packages/git-contract/src/errors.ts:13-62 (PROBLEM_CODES excerpt)
export const PROBLEM_CODES = [
  /** No usable bearer, or the session expired. Pair again. */
  "Unauthenticated",
  /** Authenticated, but this actor or scope may not touch the resource. */
  "Forbidden",
  /** Unknown resource, operation or path. */
  "NotFound",
  /** The request itself is malformed: shape, unknown key, bad field type. */
  "InvalidRequest",
  /** The state moved since the snapshot the request was planned against. */
  "StaleSnapshot",
  /** Git exited non-zero. Diagnostics are included, but not a guessed cause. */
  "GitCommandFailed",
  /** Git stopped on a state a human must resolve (conflict, hook failure, external process). */
  "NeedsAttention",
  /** Git may have changed things, but the outcome could not be confirmed. Never auto-retried. */
  "UncertainOutcome",
  /** A deadline elapsed. Timeout is not rollback. */
  "Timeout",
  /** The operation was cancelled while queued. A running mutation is never relabelled this way. */
  "Cancelled",
  /** A defect in this service. Includes a correlation id, not a stack trace. */
  "InternalError",
] as const;

export const problemCodeSchema = z.enum(PROBLEM_CODES).meta({
  id: "ProblemCode",
  description:
    "Closed set of failure codes. Clients branch on these, not on message text.",
});

// ─── 2. Code-carrying Error class ───
// From kunkun/packages/core/src/permission-broker/errors.ts:1-33 (full file)
/**
 * Code-carrying errors shared by broker policy, protocol, and host adapters.
 */

export const PERMISSION_BROKER_ERROR_CODES = [
  "PLUGIN_RUNTIME_UNAVAILABLE",
  "PLUGIN_RUNTIME_UNSUPPORTED",
  "BROKER_RUNTIME_INCOMPATIBLE",
  "BROKER_PROTOCOL_INVALID",
  "BROKER_TIMEOUT",
  "BROKER_UNAVAILABLE",
  "POLICY_INVALID",
  "POLICY_COMMIT_FAILED",
  "ADAPTER_UNAVAILABLE",
  "PERMISSION_DENIED",
] as const;

export type PermissionBrokerErrorCode = (typeof PERMISSION_BROKER_ERROR_CODES)[number];

export class PermissionBrokerError extends Error {
  readonly code: PermissionBrokerErrorCode;
  readonly context: Readonly<Record<string, string | number | boolean>> | undefined;

  constructor(
    code: PermissionBrokerErrorCode,
    message: string,
    context?: Readonly<Record<string, string | number | boolean>>,
  ) {
    super(message);
    this.name = "PermissionBrokerError";
    this.code = code;
    this.context = context;
  }
}

// ─── 3. Structured guards, not instanceof (instanceof breaks after serialization) ───
// From kunkun-services/apps/api/src/errors.ts:102-113
export function isApiError(error: unknown): error is ApiError {
	return (
		error instanceof ApiError ||
		(typeof error === "object" &&
			error !== null &&
			"code" in error &&
			"status" in error &&
			"message" in error &&
			typeof (error as { code: unknown }).code === "string" &&
			typeof (error as { status: unknown }).status === "number" &&
			typeof (error as { message: unknown }).message === "string")
	);
}

// ─── Consumers: branch on code, never on message text ───
// refyard errors.ts:66-67 comment: "Clients branch on these, not on message text"
// kunkun-services errors.ts:68-69:"A stable code. Branch on this, never on `message`"

// ❌ Counterexample (constructed, not repository code):
// throw new Error("something failed");
// catch (e) { if ((e as Error).message.includes("failed")) { /* ... */ } }
// - message is for humans, not an API; it breaks the moment wording changes
//
// ❌ Counterexample (constructed, not repository code): stuffing an object that may hold sensitive values into error context
// catch (e) { throw new AppError("X_FAILED", "failed", { request: req }) }  // req carries a token
