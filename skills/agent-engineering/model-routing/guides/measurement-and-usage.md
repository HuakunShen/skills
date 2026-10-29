# Task size, usage and timing

## Describe size before execution

Use the user's scale, or this adaptable rubric. Record the reason, not just the letter. Do not turn these examples into fixed file-count or time thresholds across domains.

| Size | Scope and acceptance burden | Examples |
|---|---|---|
| S | One bounded output with few dependencies and a short acceptance check | One UI correction; translate one passage; repair one isolated test; one video graphic |
| M | Several connected changes or artifacts with integration checks | Endpoint plus persistence/tests; a user flow across frontend/backend; a narrated video section |
| L | Multiple subsystems, uncertain requirements, migration or broad acceptance | Lifecycle redesign; cross-platform feature; a complete research-backed video or 3D scene |

Record complexity/uncertainty, risk, scope unit and verification standard separately. A one-file security fix can be small in scope and high in risk. An easy bulk rename can be large in volume. State the orchestrator's estimate before assignment; preserve it after the result. If the user changes scope, record the change rather than relabeling a slow task as large after the fact.

Compare domain + task kind + size + complexity/risk + acceptance + model/version/effort/provider/harness. S/M/L is a coarse grouping, not proof of comparable work. Show n and missing coverage. Do not divide duration by an ordinal size score as if sizes had a fixed numeric ratio.

## Obtain a real tool receipt

Use supported native APIs/exports first and record the installed version. Tool formats can change; inspect actual fields before parsing or summing.

- **Codex:** structured `codex exec --json` events can include `turn.completed` usage. Local rollout `token_count` events can expose cumulative `total_token_usage` and `last_token_usage`. Keep the last applicable cumulative receipt or exact turn deltas; summing every cumulative event double-counts. Cached input is generally a subset of input and reasoning output a subset of output in these receipts. Preserve raw field names and semantics.
- **OpenCode:** inspect `opencode stats --help` and the session/API commands supported by the installed version. Aggregate stats help with broad workload analysis; they are not a receipt for one delegated task. Per-assistant records can expose model/provider/effort, time, tokens and cost. Some persisted formats report uncached input, cache read/write, visible output and reasoning as separate buckets. Do not apply Codex's inclusive accounting to a format with exclusive buckets.
- **Agents View / ccusage / Tokscale:** useful local usage readers when available. Verify date range, included clients, schema support, archived sessions, model aliases and missing/unpriced rows. Avoid summing their totals together: they may read the same underlying sessions. A session health/completion score is not the task's independently verified acceptance.
- **Other harnesses:** retain the native usage receipt and its definition. When usage is unavailable, store unknown and the reason. Never estimate token counts from text length as if measured.

For a fresh worker, capture the session ID and final usage. For a reused worker, snapshot usage immediately before and after the assignment, or select only its task-specific turns. Keep own-session and descendant usage separate, then roll up once using explicit lineage. Failed retries are costs too. Exclude unrelated simultaneous work. Preserve the source receipt outside the public skill; reference it from the ledger.

## Store without breaking existing tables

Keep the base `Size`, `Duration` and `Tokens` columns. Record actual structured data in `Quality notes` if no additive columns are authorized, for example:

```text
size=M; size_basis=endpoint+persistence+failure-path checks; complexity=medium;
session=<id>; usage_scope=task_delta; source=<receipt>;
input_total=...; output_total=...; reasoning_subset=...; cache_read_subset=...;
elapsed_s=...; active_request_s=unknown; rework_rounds=...;
cost_actual_usd=unknown; cost_api_equivalent_usd=...; pricing_date=YYYY-MM-DD
```

Those field names illustrate **inclusive** accounting. For an exclusive-bucket source use `input_uncached`, `cache_read`, `cache_write`, `output_visible`, `reasoning`, with `token_semantics=exclusive`. Store only fields actually measured. Optional native columns may hold these values; do not reorder legacy headers or invent historical values.

## Keep three timing measures distinct

1. **Time to accepted result:** task start through independent acceptance, including tool calls, retries and review. Useful for routing value; not model throughput.
2. **End-to-end output rate:** task-attributed output tokens / the stated elapsed interval. Includes waiting/tools unless excluded; label the denominator explicitly. Input/cache token processing must not be called generated tokens.
3. **Generation throughput:** generated output tokens / measured generation interval. Requires request/stream timing with a documented start/end definition. First-token latency, queueing, prompt processing, tool time and interleaving need separate treatment. A session's created/updated timestamps cannot establish this rate.

Show median/p90 and sample count only for like-for-like records. Different tokenizers, output lengths, reasoning effort, caching, hardware/provider and concurrent load still affect comparisons. More tokens or higher tokens/second does not establish better accepted quality.

## Distinguish money from equivalent value

Keep actual metered charge, subscription/quota consumption, and API-equivalent valuation separate. A local `$0` for a free endpoint is not proof of zero subscription cost, and an unpriced model must not be treated as free. Apply dated, matching provider/version/tier prices to exclusive billable categories once. Cache input uses its cache rate; reasoning included in output is not added twice. Note unknown extra charges.

An API-equivalent figure answers “what this measured usage would cost at this tariff.” It does not prove that the user would otherwise buy exactly that usage, nor that free routing caused a matching cash saving. A Standard-tier comparison of Contributor usage also changes data terms; label it as a separate counterfactual.

## Optional local receipt helper

`scripts/usage.py` reads metadata only. It supports the observed Codex rollout
cumulative counters and OpenCode `session_message` / `session_v2` schema; a
different version may need another adapter. It opens SQLite read-only, does not
invoke a model, and does not export prompts or write a remote table.

```sh
python3 <skill>/scripts/usage.py codex --path <task-rollout.jsonl> > before.json
python3 <skill>/scripts/usage.py opencode --db <opencode.db> --session <exact-id> > before.json
# Run the authorized task, then repeat the same selected command into after.json.
python3 <skill>/scripts/usage.py diff before.json after.json > task-usage.json
```

Use one matching source per pair. Ensure no unrelated work ran in that session
between snapshots. Store the delta/source with the ledger row, read it back, and
roll up child sessions once if the task owns them. Snapshot times describe the
measurement interval, not active generation time. The helper's model list covers
the whole session; it cannot attribute a mixed-model delta to a single model.
