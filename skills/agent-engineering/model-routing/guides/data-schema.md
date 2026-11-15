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

## JSONL ledger (recommended for local and git-synced stores)

One JSON object per ledger line, appended; preserve earlier attempts. Field names are the headers above in `snake_case` (`task_kind`, `quality_notes`, `first_choice`); readers match names case-insensitively and treat `_` as a space, so `Task kind` and `task_kind` are the same field.

- Give every ledger line a stable `id`; a retry is a new line that references the earlier `id`.
- Write unknown or unmeasured values as `null` or leave the field out. Do not write `0`, `""` or `"unknown"`.
- `tokens` and `duration` keep the tool's original unit as a string unless a measured number is available. Optional structured fields (`session_id`, `usage_scope`, `token_semantics`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `rework_rounds`, `domain`, `risk`, `verified`, `evidence`) can be added per line without changing older lines.
- Keep long reasoning in `quality_notes` or `details`; no quoting rules to get wrong.
- With several devices, serialize and reconcile edits to the project `ledger.jsonl`; Git does not coordinate live writers. Elsewhere, per-device files are an option if the reader is explicitly given all files. CSV remains a fine import/export format for Sheets or a spreadsheet.

See [examples/](../examples/README.md) for `ledger.jsonl` and `rules.jsonl`.

## Markdown rules (recommended for new local stores)

Use one section per rule with a stable ID, type, status, date, scope, first choice, fallback, constraints, rationale, evidence IDs, sample count and review trigger where applicable. Mark unknowns as such. Keep superseded durable rules and dated change notes so the history and evidence remain readable; expired temporary overrides are removed as specified below. Markdown rules are read by the agent, not parsed by the ledger report. Existing JSONL and spreadsheet rules remain supported.

```markdown
## Scoped bug fixes (route-bugfix-v1)
- Type: routing; status: provisional; date: 2026-01-01
- Scope: this project, low-risk bug fixes
- First choice: model A; fallback: model B
- Evidence: attempts a1, a2, a3; n=3; review after five more attempts
- Rationale: all three passed the same independent checks.
```

## Temporary overrides

When the user requests a time-limited preference, add a separate section to the relevant project `rules.md` (or the selected global rules if the user explicitly chooses global scope). Do not edit or supersede the underlying durable rules. Record a unique ID, scope, preference, reason, start and end as ISO 8601 timestamps with UTC offsets, and any explicit constraints. For relative requests such as “five hours”, obtain the current time and the user's timezone, calculate the exact end, and show both times when confirming the change. If a duration, start, or timezone cannot be determined reliably, ask rather than invent it.

```markdown
## Temporary override: use model A (temp-use-model-a-20260101)
- Scope: this project
- Start: 2026-01-01T09:00:00-05:00
- End: 2026-01-01T14:00:00-05:00
- Preference: prefer model A for eligible tasks
- Reason: use remaining quota before reset
```

An override applies from start inclusive until end exclusive. Before every routing decision compare absolute instants, including offsets, against a trustworthy current clock. Future rules are inactive; an end at or before now is expired. An active override only changes the requested preference in its scope: it cannot authorize a forbidden model, endpoint, expenditure, or data disclosure, or waive an acceptance gate. A newer explicit user instruction can change a hard restriction when it clearly says so. If active temporary overrides conflict, apply the latest explicit instruction; ask if their order or intended scope cannot be determined.

On the next rules read, remove each expired temporary override section from the rules file, without altering other sections or durable rules. Re-read and verify the removal, using the backend's concurrency controls or an atomic update with revision checking; if the file changed concurrently, re-read and reassess before retrying. Do not apply an expired rule even if cleanup fails; report the failure and keep the rest of the rules. Do not delete a rule with missing, malformed, ambiguous, or inverted timestamps: leave it inactive and ask for clarification. If the clock is unavailable, do not assume the rule is active or expired; report that its validity cannot be determined. Expiry cleanup is separate from durable rule history; Git history, if any, remains governed by the repository's normal workflow.

For existing non-Markdown stores, use a separately identifiable temporary record with equivalent fields and remove only that record on expiry using the backend's supported safe update mechanism. Do not convert or migrate the store solely for an override.

## Write and comparison discipline

- Append ledger attempts idempotently and read back their ID/value.
- For a routing change: append the new version, supersede the prior current version, and append a dated change record. Use transactions when available; otherwise use expected revision/status checks and verify a single current version. Resolve incomplete writes before retrying.
- Preserve source observations. Derived domain/outcome/duration classifications should be labeled inferred with their method.
- Aggregate only comparable records; show denominators and missingness. Do not count ambiguous text as a pass or assume an empty Rework field means no rework.
