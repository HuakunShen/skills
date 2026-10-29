# Learning from real work

## The unit of comparison

Compare a model+version+effort+tool on a domain/task kind, risk, scope and acceptance standard. A strong orchestration model is not necessarily the best video writer, backend implementer or 3D worker. Record prompt/input/tool differences that could explain a result.

Use external benchmarks to select candidates. Your own verified tasks supply workload-specific evidence. “Self-learning” updates the ledger and routing policy; no weight training occurs.

## Bounded exploration

1. Load user restrictions and available budget. If exploration is disabled, follow established routes.
2. Pick an eligible low-risk task and one candidate. Use the same acceptance criteria as the established route.
3. State a time/usage/attempt cap and fallback. Prefer doing useful real work; shadow comparisons consume additional budget and need allowance.
4. Verify output independently enough for its consequences. Record failures, retries, environmental limitations, and missing measurements.
5. Compare with similar established-route attempts. Keep the new rule provisional when evidence is thin.

An 80/20 split is a starting point among eligible assignments, not a scientific optimum. Never spend scarce gate-review quota simply to satisfy a percentage. User limits and privacy win. Exploration itself is optional.

## Metrics

Use several metrics rather than inventing a universal intelligence score:

- Accepted outcome and the check that supports it.
- Rework rounds and human/orchestrator verification effort, when measured.
- Elapsed time to acceptance, including retries; report active vs waiting time separately if available.
- Actual usage/cost and quota impact. “Free” does not mean reliable, private, or available.
- Tool reliability, scope adherence, honesty about incomplete checks.
- Domain-specific quality: accessibility, factual accuracy, test/contract correctness, visual continuity, mesh quality, etc.

Completion time across different tasks is not a controlled model speed benchmark. Missing cost or duration prevents cost/time ranking. Do not calculate tokens/second from approximate multi-run narratives.

## Rule updates and confidence

A rule should state scope, sample count, evidence IDs, verification standard, date/model version and uncertainty. Example:

> Provisional — frontend accessibility fixes, project X, low risk. Candidate B passed 3 comparable tasks with browser checks and no recorded rework. Try it on the next eligible task; retain A as fallback. Evidence: attempts 17, 23, 26.

Three clean attempts support a trial; they do not prove dominance. Expand evidence across representative sizes. Preserve contradictory outcomes, explain changed task conditions, and review rules after model/version/tool changes. Exclude invalid trials with a stated reason, not because the result was inconvenient.

Keep root mistakes and infrastructure failures labeled separately. A candidate that repeatedly fails through an unreliable endpoint may still be impractical even when its successful outputs are good.

## Reporting existing narrative ledgers

Keep original model strings and raw outcomes. Normalize with an auditable mapping. Show per-family and task-role tables, resolved vs unknown outcomes, duration coverage, and rework observability. A documented-rework proxy is not an exact repair count. Provide representative evidence and identify where the data cannot answer “best”.

`scripts/report.py` implements this for an exported ledger: regex aliases for model/task-kind/tool labels, a printable raw-to-normalized mapping, outcome classes (pending gates and tool/environment failures kept apart), known-only rework rates, measurement coverage and thin-sample flags. Its outcome classes are inferred from text; state that when quoting its numbers. See [the worked example](../examples/README.md).

Use observed task performance wording, never a claim to measured general intelligence. Tiny, cherry-picked or non-comparable samples should not produce a confident ranking.
