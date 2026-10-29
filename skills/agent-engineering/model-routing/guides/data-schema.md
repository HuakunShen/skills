# Data schema

Keep two logical tables. Existing stores remain valid; do not rewrite their history to fit a new schema. Store dates as ISO 8601 or native dates. A missing measurement is null/blank, not zero.

## Ledger: legacy-compatible base

| Header | Meaning |
|---|---|
| Name | Human-readable task/attempt label |
| Date | Attempt date |
| Project | Project or workload scope |
| Tool | Actual invocation harness |
| Model | Exact model/version and effort where known |
| Task kind | Stable task category |
| Size | Pre-execution S/M/L with scope basis; complexity and risk recorded separately |
| Outcome | pass / pass-after-retry / partial / fail / pending, with necessary qualifier |
| Rework | What was corrected; explicit none or unknown |
| Quality notes | Verification evidence, domain/risk and limitations |
| Duration | Measured elapsed duration, or explicitly unknown |
| Tokens | Measured usage or original unit; never infer money from a subscription label |

For a new structured store, or an authorized additive extension, useful fields are:
`ID`, `Domain`, `Risk`, `Verified`, `Rework rounds`, `Duration seconds`,
`Cost USD`, `Experiment`, and `Evidence`. For usage-enabled workflows also capture
`Session ID`, `Usage scope`, `Token semantics`, input/output/reasoning/cache buckets,
and the source receipt. See [measurement and usage](measurement-and-usage.md).

Use a stable ID per attempt. Keep retries linked to that attempt and distinguish a new attempt from a resume. Record actual values only: a narrative “needed fixes” does not establish an exact number of rounds; total tokens without per-attempt timing do not establish tokens/second. Cost is unknown if the only evidence is “subscription” or “free”.

If an existing backend cannot add columns, put a concise structured summary in Quality notes, for example `domain=frontend; risk=low; verified=browser+accessibility; experiment=candidate-07; evidence=<artifact>`. Do not silently change the header order.

Outcome is the delegated task's verified result. A reviewer correctly finding bugs can pass even when the reviewed implementation fails. Separate tool/environment failures from model-quality failures in notes.

## Rules: legacy-compatible base

| Header | Meaning |
|---|---|
| Name | Task kind, principle title or change title |
| Type | routing / principle / change |
| Date | Effective/recorded date |
| First choice | Preferred model/tool/effort or decision policy |
| Fallback | Allowed next route |
| Never | Scope-specific empirical cautions; hard user bans belong in user policy |
| Details | Rationale, domain/project/risk scope, sample IDs, n, verification, confidence and review date |
| Status | current / provisional / superseded / recorded |

User policy is loaded separately and always bounds empirical rules. Preserve legacy statuses and explanatory values when importing.

## JSONL layout (recommended for local and git-synced stores)

One JSON object per line, appended; never rewrite earlier lines except to supersede a rule. Field names are the headers above in `snake_case` (`task_kind`, `quality_notes`, `first_choice`); readers match names case-insensitively and treat `_` as a space, so `Task kind` and `task_kind` are the same field.

- Give every ledger line a stable `id`; a retry is a new line that references the earlier `id`.
- Write unknown or unmeasured values as `null` or leave the field out. Do not write `0`, `""` or `"unknown"`.
- `tokens` and `duration` keep the tool's original unit as a string unless a measured number is available. Optional structured fields (`session_id`, `usage_scope`, `token_semantics`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `rework_rounds`, `domain`, `risk`, `verified`, `evidence`) can be added per line without changing older lines.
- Keep long reasoning in `quality_notes` or `details`; no quoting rules to get wrong.
- With several devices, give each its own file (`ledger/<device>.jsonl`) so appends never collide; readers concatenate them. CSV remains a fine import/export format for Sheets or a spreadsheet.

See [examples/](../examples/README.md) for `ledger.jsonl` and `rules.jsonl`.

## Write and comparison discipline

- Append ledger attempts idempotently and read back their ID/value.
- For a routing change: append the new version, supersede the prior current version, and append a dated change record. Use transactions when available; otherwise use expected revision/status checks and verify a single current version. Resolve incomplete writes before retrying.
- Preserve source observations. Derived domain/outcome/duration classifications should be labeled inferred with their method.
- Aggregate only comparable records; show denominators and missingness. Do not count ambiguous text as a pass or assume an empty Rework field means no rework.
