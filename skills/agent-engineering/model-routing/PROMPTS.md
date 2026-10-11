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
