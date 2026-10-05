// Discriminated unions are the default modeling tool (excerpted from kunkun / refyard / logic-foundry, read 2026-10-05)
//
// All multi-shape data - events, operations, state machines, RPC messages - becomes a union with a literal
// discriminant field (kind/type). Shared envelopes are factored into `as const` object spreads; without a schema,
// mutually exclusive optional fields are enforced with `?: never`.

// ─── Schema version (valibot): envelope reuse + variant ───
// From kunkun/packages/ai-protocol/src/events.ts:26-75
const envelope = {
	protocolVersion: ProtocolVersionV1Schema,
	requestId: v.pipe(v.string(), v.minLength(1)),
	sequence: v.pipe(v.number(), v.integer(), v.minValue(1)),
} as const;

export const AiStreamEventV1Schema = v.variant("type", [
	v.strictObject({ ...envelope, type: v.literal("start") }),
	v.strictObject({ ...envelope, type: v.literal("text-delta"), delta: v.string() }),
	v.strictObject({ ...envelope, type: v.literal("reasoning-delta"), delta: v.string() }),
	v.strictObject({
		...envelope,
		type: v.literal("tool-call"),
		toolCallId: v.string(),
		toolName: v.string(),
		input: v.unknown(),
	}),
	v.strictObject({
		...envelope,
		type: v.literal("tool-result"),
		toolCallId: v.string(),
		toolName: v.string(),
		output: v.unknown(),
		isError: v.optional(v.boolean()),
	}),
	v.strictObject({ ...envelope, type: v.literal("usage"), usage: AiUsageV1Schema }),
	v.strictObject({
		...envelope,
		type: v.literal("finish"),
		finishReason: AiFinishReasonSchema,
		usage: v.optional(AiUsageV1Schema),
	}),
	v.strictObject({ ...envelope, type: v.literal("error"), error: AiProtocolErrorPayloadSchema }),
	v.strictObject({ ...envelope, type: v.literal("abort") }),
]);
export type AiStreamEventV1 = Readonly<v.InferOutput<typeof AiStreamEventV1Schema>>;

/**
 * Distributes over the union. A bare `Omit<Union, K>` collapses to the intersection of the
 * members' keys, which would erase `delta`, `error`, `usage`, and every other variant field.
 */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

/**
 * What a host execution port yields. The executor — not the provider adapter — stamps
 * the envelope, which is why the port's events are envelope-free.
 */
export type AiStreamEventBodyV1 = DistributiveOmit<AiStreamEventV1, "protocolVersion" | "requestId" | "sequence">;

// ─── Schema version (zod): confirmation semantics for destructive operations ───
// From refyard/packages/git-contract/src/operations.ts:560-570
// const confirmedField = z.literal(true)   // confirmation must be an explicit true, not truthy
abortRebase: z
  .strictObject({
    kind: z.literal("abortRebase"),
    confirmed: confirmedField,
  })
  .meta({
    id: "AbortRebaseOperation",
    description:
      "Abort the rebase in progress and restore the branch to where the rebase started. When Git cannot restore it, the diagnostic is reported and nothing is reset.",
  }),

// ─── Plain-type version (zero-dependency repo): mutually exclusive fields enforced with `?: never` ───
// From logic-foundry/packages/document/src/model.ts:1-9
export interface Point { x: number; y: number }
export type Rotation = 0 | 90 | 180 | 270;
export type PrimitiveGateKind = 'INPUT' | 'OUTPUT' | 'CONST0' | 'CONST1' | 'NAND' | 'NOT' | 'AND' | 'OR' | 'NOR' | 'XOR' | 'XNOR' | 'MUX' | 'DFF';
export interface ComponentBase { id: string; at: Point; rotation: Rotation; label?: string }
export interface PrimitiveComponent extends ComponentBase { kind: PrimitiveGateKind; definitionId?: never; definitionVersion?: never }
export interface ModuleInstance extends ComponentBase { kind: 'MODULE'; definitionId: string; definitionVersion: number }
export type Component = PrimitiveComponent | ModuleInstance
export type Endpoint = { type: 'pin'; component: string; pin: string } | { type: 'junction'; junction: string };

// ❌ Counterexample (constructed, not repository code): boolean flag combos + an optional grab-bag expressing mutually exclusive shapes
// interface Event { isStart: boolean; isDelta: boolean; delta?: string; error?: string; }
// - callers can construct the illegal state isStart && isDelta; the compiler does not care
