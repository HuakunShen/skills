---
name: model-routing
description: Choose models and tools for delegated work, compare them on real tasks, and improve routing from verified outcomes. Use before delegating, when choosing a model or effort level, after rework, or when reviewing model cost and quality.
---

# Model routing

Use the least expensive available model/tool combination that can meet the task's acceptance criteria. Optimize the total cost of an accepted result: usage, elapsed time, verification, and rework. A slower free model can be a good choice for unattended work; a costly retry can erase a cheap first attempt.

This works with any orchestrator that can invoke workers: Claude Code, Codex, OpenCode, a cloud agent, another CLI, or an API workflow. The orchestrator owns acceptance. Do not assume that a model, effort level, subscription, or tool is available merely because an example names it.

## 1. Resume the user's state first

At the start of every session, and after the user changes a preference:

1. Resolve the persistent configuration. If shell access is available, run `python3 <skill-folder>/scripts/state.py resolve --project <project-root>`. Otherwise use the same lookup order in [state and storage](guides/state-and-storage.md).
2. Read the selected storage location, all returned policy layers and referenced policy files, and the user's current routing/principle rules. Load user restrictions before choosing or trying models.
3. Report the selected scope/backend briefly when setting it up or when it changes. Reuse it throughout the session.

Configuration contains locators and preferences, never API keys. A skill is reusable instructions; its state lives in files or a database the next agent can read. An ignored `.local/config.json` inside this skill is supported, but copies/installations do not share that file automatically. Prefer a common user configuration for multiple tools, or a project configuration for project-specific learning.

Newest explicit user instructions govern. Honor banned models, allowed tools, privacy restrictions, spending limits, concurrency limits, and exploration opt-outs. Learned recommendations cannot override them. Keep global hard restrictions when using project rules; ask only when actual user policies conflict. Do not interpret an illustrative example as a new ban.

If there is no configuration, run a short interactive setup using [setup conversation](guides/interactive-setup.md). Ask about storage/scope, available tools and user constraints, then exploration preferences. Offer sensible defaults, accept free-text answers, and ask only for missing information. Persist the answers before the first delegation. Existing users resume their saved setup; they do not repeat the questionnaire each session.

If the selected store cannot be accessed, explain the access problem and retain the selection. Do not silently create another ledger. Recommend Google Sheets to new users when accessible; Notion, documents, or local files are equally valid explicit choices.

## 2. Describe the task before choosing

Record a short routing brief:

- **Domain and task kind:** e.g. frontend/accessibility, backend/data migration, system design, video/storyboard, 3D/retopology. Allow new labels.
- **Acceptance:** observable output and checks; who verifies it.
- **Risk and data:** consequences of error, sensitivity, reversibility, permitted endpoints.
- **Size and deadline:** before execution assign S/M/L (or the user's scale), explain concrete scope and acceptance burden, and record latency requirements. Rate complexity/risk separately; do not infer size from how long the chosen model later took.
- **Resources:** available tools/models/efforts, remaining budget, and required capabilities such as images or code execution.

Domain examples and acceptance checks are in [domain examples](guides/domain-examples.md). Reuse stable labels within a project so experiences can be compared.

## 3. Choose from evidence and allowed capabilities

Discover the installed tool/provider's current model list or tool metadata. Separate model, version, effort, provider, and harness. A subscription in one product does not imply API or CLI access in another. Keep exact invocation details in the user's configuration or the tool's own instructions, not in a universal model ranking.

Read relevant current rules and comparable ledger records: same task kind/domain, similar risk/size, project context, model version, effort, and verification standard. Start with scoped queries rather than reading the whole history before every task.

Prefer the cheapest allowed candidate with enough evidence to satisfy acceptance. With little evidence, mark the choice provisional, use a bounded task, and arrange a check appropriate to its risk. A public leaderboard is a useful prior; it does not establish the best model for this user's workload.

Use [tool adapters](guides/tool-adapters.md) for invocation boundaries and [PROMPTS.md](PROMPTS.md) for task briefs. For endpoints that may use inputs for training, send only data the user permits; public source still needs a secrets/private-context check.

## 4. Explore within the user's budget

Exploration discovers better choices; exploitation uses the best supported current choice.

When the user permits exploration, a useful starting setting is **80% established routing / 20% bounded exploration** among eligible low-risk assignments. Treat this as a configurable task allocation, not a required quota or a reason to duplicate every task. Respect exploration, cost, latency, and endpoint restrictions first.

Try one candidate on a small real task with explicit acceptance. Keep a proven fallback. Charge retries and duplicate trials to the exploration budget. Paid extra trials require an authorized budget; never test a banned model. Avoid experiments on irreversible production actions or required independent acceptance gates.

A new release, stale evidence, a changed domain, or repeated rework is a reason to reconsider a route. Distinguish model limitations from transport failures, tool misuse, bad briefs, and environment failures. Follow the bounded comparison procedure in [learning and evaluation](guides/learning-and-evaluation.md).

## 5. Delegate, verify, record

Give the worker the task, inputs, boundaries, acceptance checks, and report format. Keep tool-specific commands in adapters. Resume a suitable existing worker when that preserves relevant context cheaply; confirm its session/workspace identity.

Verify the resulting artifact against acceptance. Self-written tests and a worker's claim alone do not establish correctness. Choose independent review when consequences warrant it, and follow the user's existing review rules.

Write one ledger record after verification, including partial/failed outcomes. Do not turn unknown measurements into zeros or guesses. Preserve older records and use a stable record ID or idempotency marker to avoid duplicate writes. Read back the write.

When exposed by the tool, collect session/turn IDs and measured input, output, reasoning, cache-read/write usage with the task record. For a resumed session use a before/after usage delta or the exact task's turns; do not charge its entire previous history again. Follow [measurement and usage](guides/measurement-and-usage.md) for tool receipts, S/M/L comparisons, token accounting, and timing. Total session tokens divided by elapsed task time is an end-to-end rate, not pure model generation speed.

Keep **two logical tables**, regardless of backend:

- **Ledger:** individual attempts, observations, outcomes, time/usage, rework, and verification evidence.
- **Rules:** current routing, durable principles, and dated changes with their evidence and scope.

The existing 12 ledger columns and 8 rules columns remain supported. Recommended structured fields and migration guidance are in [data schema](guides/data-schema.md).

## 6. Turn experience into scoped rules

At the end of a session with verified attempts, summarize what changed for each relevant domain/task kind. Compare accepted outcomes, rework, verification burden, availability, elapsed time, and cost. Preserve unknowns and workload differences.

To see which models suit which task kinds, export the ledger with its header row (CSV, JSONL, or a Sheets values export) and run `python3 <skill-folder>/scripts/report.py <export> --by model,task_kind`. Add `--aliases <file>` to merge drifting labels and `--mapping` to audit the merge. The report keeps pending gates, tool failures and unverified model identities out of acceptance rates, and marks thin groups. [Worked example](examples/README.md) walks one cycle from ledger to rule change.

Three clean comparable attempts can justify a **provisional** cheaper-route trial; they are not a universal proof. Promote a candidate only when the observed result meets the user's quality and resource requirements. Record sample IDs, sample count, date, context, and confidence. Keep previous rules as superseded history and add a change row explaining the revision.

Review stale rules after model/tool changes. User constraints are policy; empirical routing is a hypothesis that can change. Do not turn one impressive failure or success into a global model ranking.

Here “self-learning” means updating persistent experience and routing rules. It does not train model weights or guarantee autonomous improvement. The loop is: **load policy → route → execute → verify → record → revise**.
