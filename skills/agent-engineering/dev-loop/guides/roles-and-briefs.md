# Roles and briefs

## Roles

| Role | Does | Never |
|---|---|---|
| Owner | Product, public API, security and permission, licensing, publication, destructive migration, cost decisions; real-machine acceptance; push and release. | Is not asked about routine choices. |
| Orchestrator (main session) | Intake, design tree, decision log, register, slicing, briefs, approval, merge, cleanup, reviewing every worker result with the diff plus a scripted check. | Does not implement large tasks a worker could; does not let a worker write the decision log. |
| Planner | Spec and executable plan. | Does not approve its own plan. |
| Executor | Implements one reviewed plan inside its write set. | Does not design, widen scope, re-tier, delegate, or edit the decision log. |
| Reviewer | Independent verdict on a plan or a change. | Does not edit unless the user configured it to. |

Which model or tool fills each role is decided by the `model-routing` skill and the user's `roles` config. Do not hard-code model names in this skill's output; read them from config.

Workers can be the harness's own subagents, another agent CLI (codex, opencode, others), or a terminal multiplexer session. Prefer whichever the user's config names; a plain CLI run is usually simpler than a TUI. For Claude Code subagents, use a lean agent type with only the tools workers need (`templates/agents/lane-worker.md`) rather than general-purpose; see [token budget](token-budget.md).

When workers must be listable and attachable (several run in the background), start them in named `hc` terminals and wait with `hc wait`; see [hc runtime](hc-runtime.md).

For Codex, follow the [Codex adapter](codex.md); use the TOML worker template only when the host can select custom roles. Otherwise pass its instructions in the brief.

## Delegation rules

- Workers that need parallelism get **disjoint write sets**. Same checkout is fine for unrelated files; use a worktree for complex or overlapping work.
- Worker results are claims. The orchestrator checks `git status`, `git diff` and a scripted check after every task. A result that needs redoing moves that task kind up a tier (record it via `model-routing`).
- Workers report **once**, when finished or blocked, with: commits, logs, checks actually run, what was not run.
- Long-lived workers resume with their session id rather than starting over.
- Put shared discovery in one versioned context manifest and link it from related briefs. Follow the [reuse rules](token-budget.md#reuse-context-before-reading-again); each worker reads the relevant current source, without repeating a repository-wide survey. Resume useful task context for related follow-ups, and pass only the new goal, delta and changed constraints.
- Quota or rate errors are infrastructure, not model failure: follow the user's rotation/fallback rule before changing tier.

## Worker brief template

```text
Goal: <one bounded outcome>
Read first: <plan file + task>, <standing rules file>
Context manifest: <files to read first>, <symbols>, base commit <sha>
Reuse on follow-up: <manifest / prior findings>, last inspected <sha + dirty-state notes>, delta <range / paths>
Worktree / branch: <path / name>
Write set (only these): <exact files, no globs>
Forbidden: <paths, actions>
Test plan: <RED expected failure, GREEN count, negative control, typecheck>
Standing constraints: <copied from the project's constraints list>
Execute exactly as written; do not re-tier or delegate. If a tool is refused, use
another approved tool rather than skipping the step. Run every command in the
foreground or use host-managed jobs with completion tracking. Keep a per-task RED/GREEN log
at <scratch>/<lane>/LOG.md. Stage exact paths when committing.
Use focused searches and avoid overlapping reads; do not load huge unrelated files.
Use host completion notifications or wait APIs rather than sleep-polling.
If blocked or nearing the host/project budget, write a handoff note
at <scratch>/<lane>/HANDOFF.md and report.
Report once, in at most 15 lines, when finished or blocked: commits, logs, not-run list, proposed
decision-log text (the orchestrator numbers it).
```

## Standing constraints (copy into every brief; the project adds its own)

Constraints are config (`constraints`) or an instruction source, so each project edits its own list. Sensible defaults:

- Scratch only under the configured scratch root.
- Wait on a pid or an output file, never a process-name pattern that can match the waiting shell.
- No attribution lines in commits or PRs unless the project wants them; push only when asked.
- Git bans for workers sharing a checkout: no stash, checkout, reset, restore, `add -A`, `add .`, submodule deinit. Stage exact paths. Preserve other people's dirty files. Re-read the log before amending.
- Never print secrets; never use real services in tests; never steal focus or touch the owner's live data.
- Agents report once.
- Cargo.lock (and other generated lockfiles) is always inside every write set when a manifest changes; a worker must not stop over it.
