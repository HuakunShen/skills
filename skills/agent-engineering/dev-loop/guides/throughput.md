# Throughput: finish verified work, not keep agents busy

Owner decision 2026-11-16. This guide replaces the earlier "keep at least 5 (or 6) lanes live" rule. The goal is the most **verified** user-visible work per week, per quota and per owner minute. Busy agents, commit counts and lane counts are not the goal.

Why it changed: a lane-count floor made the orchestrator invent low-value tasks to fill slots, rebuild the ready queue again and again (kunkun had 30 READY-QUEUE files in five days), and a Stop hook kept pushing for more lanes after the real queue was empty. Large status files were also re-read on every session start and after every compaction.

## 1. Concurrency is a ceiling, never a floor

Start a lane only when all of these hold:

- a ready task with written acceptance criteria and no open owner decision;
- a write set that does not overlap a running lane;
- a free build slot if it builds (Swift and Rust: one heavy build per writable build directory; start with one heavy slot per machine and raise it only after measuring);
- review capacity for its result, and quota left after the reserve (section 6).

No minimum lane count. Zero running lanes is a valid state when nothing meets the bar; say so in one line and stop. Never create a task to fill a slot. Never start a read-only audit only to refill a queue: rebuild the queue at most once per day, by updating one queue file, not by writing a new one.

## 2. Close before you open

When a lane finishes, the order is: verify, integrate, record. Starting the next lane comes after that. Near an integration point or a milestone, start fewer new lanes and spend the capacity on verification, installed-app checks and closing gates. Work that is written but not verified is a liability, not progress.

## 3. Keep the orchestrator thin

- At session start and after a compaction read one digest of at most about 5 KB (areas, honest status, next step, running lanes, owner decisions). Read a full status, backlog or focus file only for the task you are about to touch, and only the section you need.
- The orchestrator reads diffs, test summaries and result files. It does not read source broadly, run long suites itself, or keep worker logs in its context.
- Track at most about 6 open areas at once. More than that and older work is forgotten; park the rest in the queue file.

## 4. One worker per area, resumed

- Related tasks in one area (implement, fix, re-verify, the next layer) go to the same worker or session, resumed, not a fresh worker each step. Fresh workers are for independent reviews, unrelated work, or a worker past its context budget (it writes a hand-off file first).
- Plan, implementation and review may use different models: hand off through files (plan, review report, decision entry), never by switching the model of a running session, which throws away its cache.

## 5. Briefs and results

A brief carries: task id, base commit, write set, files and symbols to read first, acceptance checks with exact commands, what is out of scope, and when to stop. A result returns at most about 10 lines:

- commit or "uncommitted", changed files;
- the commit the tests ran on, each command with its exit code and counts;
- findings and blockers;
- what was not verified;
- path to the full log (never the log itself).

## 6. Stop loops early, keep a reserve

- Same error fingerprint twice with no new evidence: stop, write down the current hypothesis, and change it or escalate (stronger model, the owner, a different approach). Do not re-run the same command hoping for a different result.
- Review rounds follow the project's tiering; if a review keeps finding new low-severity items, the gate needs an exit rule, not a more expensive reviewer.
- Keep about 20% of each subscription's quota for independent reviews, hard debugging and release gates. Look at each provider's own remaining quota; do not compare percentages across providers.

## 7. Batch the expensive checks

- Per patch: typecheck plus focused tests of the touched area, early.
- Per batch of 3 to 5 related tasks: one integration run at a fixed commit (callers, contracts, failure paths), owned by one integration owner.
- Per merge or release: the full suite once on frozen sources. Never rerun a full suite per lane. Security, permission, protocol and data-loss negative tests are never deferred to the batch.
- Cache build helpers by a source fingerprint instead of skipping them unconditionally; a skip flag that hides a stale helper is a false green.

## 8. Status has five levels

Record each feature as implemented, unit-verified, integration-verified, device or installed-app verified, release-ready. "Done" in a report names the level. Source-only work stays source-only until a higher level is shown.

## 9. Measure without a long experiment

No week-long A/B is required. For each verified task record: model and effort, token delta for that task (session delta, not session totals), review and fix rounds, wall-clock minutes, and the status level reached. Review the numbers when choosing routes (`model-routing`); change a rule when two or three comparable tasks point the same way.
