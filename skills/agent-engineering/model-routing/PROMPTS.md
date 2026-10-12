# Delegation prompt templates

Fill in the `<...>` parts. Keep each prompt self-contained: workers in other tools do not read CLAUDE.md or AGENTS.md.

## Common block (paste into every implementation prompt)

```
Work in <absolute worktree path>, branch <branch>. Already committed: <task → hash list, plus any API drift since the plan was written>.
Write set: <exact files>. If you need any other file, or an exact-text anchor occurs 0 or 2+ times, STOP and report. Do not improvise.
Run every command in the foreground and wait. Never use background shells, &, nohup or watch modes.
Tests: <exact command>. Typecheck: <exact command>. <Known flakes: names; rerun them alone if they fail.>
Never loosen a test. Test first: write the failing test, record the RED output, fix, record the GREEN output.
Commit with git add <explicit paths> and the message <msg>. No attribution lines. Never push. Do not touch <other worktrees, protected dirs>.
Final output: commit hashes, RED/GREEN output, test counts, the tsc result, every deviation from the plan with its reason, anything left undone.
```

## opencode

```bash
cd <worktree> && opencode run --auto -m opencode/muse-spark-1.3-contributor-free "$(cat prompt.md)" < /dev/null > run.log 2>&1
# Follow-up in the same context:
opencode run --auto -s <session-id> -m opencode/muse-spark-1.3-contributor-free "<follow-up>" < /dev/null
```

Run it as a background job from your harness and get notified when it ends. Within a few minutes, check that `opencode session list` shows the new session; if it does not, kill the run and restart it.

## Claude haiku (executor or test runner)

Add: "Execute exactly as written. Do not re-tier or delegate. If a tool is refused, use another approved tool rather than skipping a step. Keep a per-task RED/GREEN log in <file>."

For regressions: list the known failures and say "rerun each failing file alone once and report whether it passes alone".

## Claude sonnet (review-finding fixes, merges, plan writing)

Give:
- the review file path;
- the per-finding repro;
- the rule "fix test first";
- the known flakes;
- the instruction to resume via SendMessage for the next round. Resuming keeps context and costs a fraction of a new agent.

For plan writing, add:
- an example hand-off plan of the required detail;
- "validate snippets by compiling them in a scratch copy, then revert";
- "list owner decisions with a recommended default".
- an explicit concurrency and crash checklist that the plan must answer, each item with a named test. Replay and mutation sweeps only exercise the plan's own single-request paths. On 2026-10-12, three plans that had been validated by replay still failed review on the same classes of issue:
  - two concurrent requests or writers on the same object;
  - a crash between "mark done" and "persist result";
  - deletion or disable while work is in flight;
  - a re-enable that runs startup recovery over live owners;
  - client-supplied state trusted as server truth;
  - state checked again after every await (epochs).

## codex reviewer (gpt-6.1-sol/high)

```bash
codex exec -s read-only -m gpt-6.1-sol -c model_reasoning_effort=high -o review.md - < prompt.md > review.log 2>&1
```

The prompt includes:
- the history of earlier reviews and their verdicts;
- the fix commits (`git log base..HEAD`);
- the evidence root already ran;
- the decisions to judge;
- the specific regressions to look for;
- "Report only actionable P1/P2. Output: verdict PASS / PASS WITH FIXES / FAIL, then findings with file:line and a fix."
- For the third and final round, say so: under the convergence rule, P1s that remain afterwards become test-first RED items.

## Pitfall: chaining prompts with search-and-replace (root error, 2026-10-11)

Do not make the next task's prompt by running a global `sed s/Task N/Task N+1/g` over the previous one. It also rewrites the "already committed" list, so a commit shows up labelled as the task about to run. A worker could then believe the task is done. This happened twice in one night; both runs were caught and killed before any edit.

Instead:
- generate each prompt from a template with explicit variables (`TASK`, `DONE_LIST`, `EXTRA_RULES`);
- or grep every `(Task N.M)` label before launching;
- always read the first 15 lines of the rendered prompt before you start the run.

## Pitfall: resuming the wrong opencode session (root error, 2026-10-12)

`opencode session list` is global across directories and sorted by recency. When parallel opencode runs go in different worktrees, `head -1` returns whichever ran last, which may belong to another lane. Resuming it from a different cwd starts a second concurrent run on that session.

Always:
- record each run's session id when it starts (from `session list`, matched by its title);
- resume by that explicit id;
- never resume with `head -1`.

## Pitfall: background opencode runs can die mid-task (2026-10-12)

Two of three parallel `opencode run` jobs exited at the same moment with code 144 (killed by a signal) and left uncommitted work. The third survived. A run also stopped silently once, mid-replay.

What to do:
- Always record the session id.
- On any non-zero exit, or a report with no final summary, check `git status` in the worktree and resume with `-s <id>`. Tell it what state it was in and to re-record RED honestly if it was lost.
- Per-task commits keep the loss to one task.

Repeat (2026-10-12): a review prompt derived with `sed` from the previous phase's prompt kept that phase's numbered checklist ("S1 covers…", "S1's slot"). It was caught by reading the rendered prompt and the run was stopped within a minute. Write review checklists fresh for each phase; only copy the location and format lines.

## Pitfall: replay of an edited copy, not the committed doc (2026-10-12)

Twice tonight a plan author "replayed" the doc and then kept editing it. The S5 doc as committed failed to compile (a duplicate declaration) and had hooks after an early return, while the author reported green replays.

Always require replay from `git show HEAD:<doc>` after the commit, and re-commit plus re-replay on any fix. Root can spot-check by extracting one task's code block and compiling it.

## Pitfall: transient "free tier can only be used from within OpenCode" (2026-10-12)

An `opencode run` on the free model exited 0 after this provider error, part-way through a task. A one-word probe right after succeeded. Exit 0 is not success: always read the log tail. On this error, probe with a trivial run, then resume with `-s <id>`.

## Pitfall: opencode ends a plan-writing run before writing (2026-10-12)

The S6 plan run read for a long time, then tried to write a very large doc in a single tool call. The tool rejected the arguments ("Update the arguments and call the tool again"), and the run exited 0 with no file and no commit.

To avoid it, every plan-writing prompt should say: "write the doc in parts (create the file, then append sections); resolve uncertain details with one grep before writing; never leave conditional instructions."

If it happens anyway, resume with `-s <id>` and tell the run to write now.

## Pitfall: hand-written diff patches in plan docs (2026-10-12)

The S8 revision run lost its time trying to make `git apply` patches with correct `@@` hunk headers inside the doc, then stopped mid-replay. While debugging it also edited a product file in the docs-only worktree.

Plan prompts must ask for complete files, or for exact anchor replacements ("this block occurs once; replace it with this block"), never unified diffs. Docs-only lanes must name product files as forbidden, and root checks `git status` after every plan run.

## codex as a writer (2026-10-12)

`codex exec -s workspace-write` cannot write git metadata in a linked worktree: it fails on `index.lock` and `ORIG_HEAD.lock`, even when `writable_roots` includes the repo, so it cannot commit, merge or create replay worktrees. Codex then reports itself blocked; it does not improvise.

For writer tasks that need git, use `-s danger-full-access`, the same trust level as `opencode --auto`, with the usual write-set rules in the prompt. Keep `-s read-only` for reviews.

## gpt-6.1-sol capacity (2026-10-12)

With two sol/xhigh writer runs active, a third sol review died after 111k tokens with "Selected model is at capacity". Keep at most 2 concurrent sol runs. Use gpt-6-luna as the overflow reviewer, and retry sol later for gate reviews.

## Free endpoints drop long runs (2026-10-12)

Long opencode runs on longcat, step-5 and space-bunny, and on mimo once, ended with "ECONNRESET: Connection lost" or "Upstream request failed: Endpoint is unavailable" (ling, twice in a row), and exited 1. Resume with `-s <session id>` and tell the run to continue; otherwise start a fresh run. Find the id with `opencode session list | grep <title>`.
