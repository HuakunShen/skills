# Token budget

Reduce unnecessary context and calls while preserving accepted results. Task size,
cache behavior, reasoning/output, retries and handoffs all affect total cost.
A large context is evidence to investigate, not proof that restarting is cheaper.

## Measure by host

- **Codex:** follow the [Codex adapter](codex.md). Use `model-routing/scripts/usage.py
  codex --path <rollout>` snapshots and `diff`; aggregate task-owned parent/child
  sessions once. Do not apply Claude cache settings or savings to Codex.
- **Claude Code:** `model-routing/scripts/claude_usage.py --day <YYYY-MM-DD>` reads
  local transcripts for main/subagent usage, startup context and cache behavior.
  Its input-equivalent weighting is not model-specific money or subscription quota.
- **Other workers:** use their native receipts through `model-routing`.

Compare accepted-task cost, quality and elapsed time on the same task, base commit,
model, effort and acceptance checks. Include coordination, rereads and retries.
Repeat when variation matters. Day-to-day totals and per-call context medians are
workload-dependent; they cannot isolate an optimization.

## Default choices

1. Give each worker a bounded context manifest: plan, files, symbols, write set,
   base commit, constraints and checks. A wiki provides navigation; live code governs.
2. Reuse a worker for related follow-ups when its context is still useful. Use a
   fresh brief for unrelated work or independent review. Fork only when parent
   history is needed and the host supports it.
3. Keep project-configurable checkpoint budgets. Handoff on budget pressure,
   unrelated accumulated history or a natural milestone; do not enforce a universal
   150k-token restart threshold. Account for the next worker's rereads and mistakes.
4. Batch small related fixes. Choose enough parallelism to make progress within
   spending and concurrency limits, not a new worker for every tiny request.
5. Use focused searches and avoid redundant reads. Read small relevant files as a
   unit; inspect large files selectively. One tool call is not always one model
   call: hosts can batch or execute calls in parallel.
6. Use host completion notifications or wait APIs; avoid repeated sleep-poll turns.
   The orchestrator still inspects relevant source/diffs to verify worker claims.
7. Choose model and effort through the user's routing policy. A cheaper model only
   saves overall when quality and retry cost remain acceptable.
8. Run reflect preflight outside the model when an external scheduler is available;
   an LLM cron that invokes the script still incurs its initial model call.

## Reuse context before reading again

Before a new planning, implementation or review pass, check what the current
session or task manifest already establishes. Reuse useful evidence and navigation;
load only the stage guides and source needed for the next decision. Do not repeat
a repository survey or reload every guide for each feature or follow-up.

- **Keep one common manifest for related work.** Record relevant paths and symbols,
  shared contracts and decisions, inspected commit, any relevant uncommitted state,
  completed checks and unresolved questions. Link existing plans and review records
  instead of copying them into every brief. Update the affected entries as work
  progresses; the manifest need not reproduce source code or become another wiki.
- **Read the delta first.** Compare the last inspected version with the current
  commit and working-tree changes, including relevant new files. Read changed
  sections and the callers, contracts, configuration or dependencies they affect.
  Expand when the evidence is incomplete. An unchanged file may need reinspection
  when its assumptions change elsewhere.
- **Reuse only what is available and current.** A path in a brief does not mean a
  fresh worker has read it. New workers read the relevant source once; continuing
  workers reuse retained context. Reopen affected material after changes, missing
  history, compaction that lost needed detail, or an uncertain baseline. Summaries
  and old test results do not establish current behavior.
- **Batch by shared context and readiness.** Plan related features together and
  review coherent increments. Sharing a repository alone is insufficient. Split
  at an independently deliverable change, a risk boundary needing focused review,
  unrelated context, or when waiting would delay ready work. Finish reviewing a
  shared interface before dependent work starts. Keep per-feature acceptance and
  integration checks explicit; batching must not hide unreviewed changes.

For example, features A and B using the same authorization contract share its
design and review. Their workers read their own code and the relevant contract;
an unrelated UI copy fix proceeds separately. A later contract change reopens the
affected assumptions and integration checks for both A and B.

## Claude-specific template and historical evidence

`templates/agents/lane-worker.md` is a Claude Code template; its tool allowlist,
`model: sonnet` and `maxTurns: 150` are configurable example choices, not cross-host
requirements. A turn cap is not a token limit, and handoff before a hard stop is
not guaranteed. In the session tested, newly added roles required a new session.

On 2026-10-30, 197 Claude workers accounted for about 83% of the recorded
input-token-equivalent usage. Median first-call context was 79k; some workers grew
to about 560k. These are observations, not causal savings estimates. The earlier
21% Opus share used a common token weighting; it was not a model-priced cost share.

A 2026-10-31 trivial-task test in one CLI session measured 43.9k startup context
for general-purpose versus 10.3k for lane-worker. A separate desktop run measured
64.0k for general-purpose; desktop lane-worker was not tested. Tool count alone
does not explain the difference because system instructions also changed.
Replaying assumed fixed context reductions suggested savings, but did not measure
real task performance, retries or quota. Do not present those projections as
proven savings or transfer them to Codex.

For Claude workers with long gaps, optionally evaluate `subagentPromptCacheTtl:
"1h"` against 5m. Longer cache writes cost more; break-even depends on reuse.
Neither the prior rough estimate nor API tariff ratios establish subscription savings.

## Brief additions

```text
Context manifest: plan <path>, read first <files>, symbols <names>, base <sha>.
Use focused reads and host completion mechanisms. Preserve project constraints.
Checkpoint budget: <user-selected, or none>. At handoff record changed files,
current commit, completed checks, remaining work and active job identifiers.
Report concisely; include blockers and checks not run.
```
