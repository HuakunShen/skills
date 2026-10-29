# Worked example

A small, invented ledger that shows one full learning cycle: record attempts, read the report, change one rule. Projects and tasks are fictional; the failure patterns come from real use.

| File | Purpose |
|---|---|
| [ledger.jsonl](ledger.jsonl) | 15 attempts, one JSON object per line, including messy model labels, a tool failure, a pending gate and an unverified model identity |
| [rules.jsonl](rules.jsonl) | Rules before and after the change, with a superseded row and a change record |
| [ledger.csv](ledger.csv), [rules.csv](rules.csv) | The same data as spreadsheet exports (legacy 12-column and 8-column layout); the report gives identical output for either format |
| [aliases.json](aliases.json) | Auditable regex mapping from raw labels to canonical model and task-kind names |

## 1. Read the raw ledger

Real ledgers drift. Here the same model appears as `deepseek-v4.1-flash-free`, `DeepSeek V4.1 Flash (free)` and `opencode/deepseek-v4.1-flash-free`. One outcome says `pass (pending review)`. One row says the harness did not report which model served it. Preserve these raw values; normalize at report time.

## 2. Report by model

```sh
python3 scripts/report.py examples/ledger.jsonl --aliases examples/aliases.json
```

Without `--aliases` the three deepseek labels split into three thin rows. Add `--mapping` to print every raw → normalized value so the mapping can be checked.

The report applies the skill's evidence rules:

- `pass (pending review)` counts as **pending**, not accepted.
- The 2026-10-02 hang counts as **infra** because its notes say "tool failure"; it does not count against the model.
- The row whose served model is unknown is listed as `(unverified) …`, apart from the verified reviewer.
- Groups with fewer than 3 resolved rows are marked **thin**.

## 3. Report by model and task kind

```sh
python3 scripts/report.py examples/ledger.jsonl --aliases examples/aliases.json --by model,task_kind
```

A per-model rate mixes easy and hard work. Split by task kind before drawing a conclusion:

| model | task kind | resolved | accept | rework |
|---|---|---|---|---|
| deepseek-v4.1-flash-free | scoped bug fix (non-security) | 4 | 75% | 25% |
| sonnet/medium | scoped bug fix (non-security) | 2 (thin) | 100% | 0% |
| muse-spark-1.3-free | plan writing | 1 (thin) | 0% | 100% |
| sonnet/high | plan writing | 1 (thin) | 100% (after retry) | 100% |

## 4. Turn the evidence into a rule

For scoped non-security bug fixes, three bounded exploration tasks (e1–e3) passed with the same acceptance as the established sonnet route. A fourth was partial: the worker missed a sibling caller. That led to a prompt change rather than a rejection.

[rules.csv](rules.csv) records the outcome:

- The old sonnet/medium row becomes `superseded`.
- A new deepseek row becomes `provisional`. Sonnet/medium stays as the fallback, and the row carries a review trigger.
- A `change` row cites the ledger rows it relied on.

Plan writing stays with sonnet/high plus independent review. The single muse failure is thin evidence, but it was severe (9 P1 findings) and its own tests had passed. That is why "self-written tests are not evidence" is a principle, not a ranking.

## 5. What this example cannot show

Four resolved tasks do not prove deepseek is better than sonnet at bug fixes. They justify trying it on more eligible low-risk tasks while keeping a proven fallback. Durations are not comparable across these tasks, and free-tier token counts were not measured. Read every rate together with its denominator and coverage.
