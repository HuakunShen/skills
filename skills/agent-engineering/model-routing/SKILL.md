---
name: model-routing
description: >-
  Choose the cheapest AI model and tool that can reliably do a delegated task, write the
  delegation prompt it needs, verify the result, and record the outcome so the routing
  improves over time. USE THIS SKILL before spawning any subagent, worker, reviewer or
  external coding agent (Claude Code Agent tool, opencode run, codex exec, or any other
  CLI agent), when splitting work into parallel workers, when a delegated task failed or
  needed rework, and when the user asks which model to use. It covers Claude models
  (Haiku, Sonnet, Opus, only inside Claude tools) and non-Claude models (opencode's free
  models, OpenAI models through codex), so it still works in harnesses with no Claude
  models. Trigger words: subagent, delegate, worker, which model, model tier, haiku,
  sonnet, opus, opencode, codex, sol review, parallel agents, quota, cheaper model.
---

# Model routing

Use the cheapest model that will get the task right on the first try, verify every result yourself, and log the outcome so these rules keep improving. The evidence behind each rule is in [LEDGER.md](LEDGER.md); prompt templates are in [PROMPTS.md](PROMPTS.md).

The owner's standing rule is to save quota. Do not reach for the strongest model by default. Move a kind of task up a tier only after a cheaper tier failed at it, and down a tier after it keeps passing easily.

## 1. Which models exist in which tool

| Model | Available in | Cost | Notes |
|---|---|---|---|
| Claude Haiku 5.5 (`haiku`) | Claude Code / Claude Agent SDK only | low quota | Agent tool `model: "haiku"` |
| Claude Sonnet 5.5 (`sonnet`) | Claude Code / Agent SDK only | medium quota | `model: "sonnet"`, `effort: medium/high` |
| Claude Opus 5.5 (`opus`) | Claude Code / Agent SDK only | high quota | reserve; see §3 |
| opencode `opencode/muse-spark-1.3-contributor-free` ("Muse Spark 1.3 Free") | opencode CLI (any harness with a shell) | free | owner rates it about Sonnet/high for execution; reads images accurately (verified 2026-10-12 on a settings screenshot) |
| gpt-6.1-sol, reasoning effort high | codex CLI (`codex exec`), any harness with a shell | OpenAI quota | independent reviewer; read-only |

If the current harness has no Claude models (Codex, opencode, Cursor, another CLI), the Claude rows do not exist. Map the tiers like this:
- **Cheap/mechanical:** opencode free model.
- **Execution of a full plan:** opencode free model.
- **Judgment fixes and plan writing:** the harness's mid-tier model, or opencode with a stricter prompt and an independent review.
- **Review:** codex gpt-6.1-sol, read-only.

Add a row whenever a new model or tool is tried, and record it in the ledger.

### Tool preferences (how each tool wants to be driven)

- **Claude Code Agent tool**
  - Runs in the background by default.
  - The final report comes back as a message.
  - Resume the same agent with SendMessage, which keeps its context and makes a follow-up fix cheap.
  - Run at most 2 Claude subagents at once (owner quota rule).
- **opencode**
  - Command: `opencode run --auto -m opencode/muse-spark-1.3-contributor-free "<prompt>" < /dev/null`.
  - `< /dev/null` is mandatory. Without it the run can hang forever with 0% CPU.
  - `--auto` is needed for writes.
  - Run it from the target worktree.
  - Continue a session with `-s <id>`; list ids with `opencode session list`. Continuing is cheap and keeps the context, so use it for follow-ups.
  - Several opencode runs can go in parallel in different worktrees.
  - It does not read CLAUDE.md or AGENTS.md, so the prompt must be self-contained.
  - Long commands must run in the foreground, or they die when `run` exits.
  - If the owner's OpenCode desktop app holds port 49374, the CLI can fail. Never kill the owner's app; fall back to another tier.
- **codex**
  - Command: `codex exec -s read-only -m gpt-6.1-sol -c model_reasoning_effort=high -o out.md - < prompt.md`.
  - Use it for reviews only. It is read-only and reproduces bugs in memory.
  - Typical review: 10–25 minutes.

## 2. Routing table (current rules)

| Task kind | First choice | Fallback | Never |
|---|---|---|---|
| Run tests/regressions, collect logs, triage failures (rerun alone) | haiku | opencode | opus |
| Status, Notion or table updates; rule-driven doc sweeps over a named file set | haiku or opencode | sonnet | opus |
| Execute a reviewed plan whose code and tests are given verbatim, any task size | opencode | haiku (cheap tasks), sonnet | opus |
| Implement review findings or convergence RED items: test first, judgment, small write set | opencode (good evidence 2026-10-11) | sonnet/high | — |
| Fix races, lifecycle or concurrency findings with a deadlock risk | sonnet/high | opus/medium after sonnet fails twice | haiku |
| Merge a finished branch with many conflicts | sonnet/high | — | haiku |
| Root-cause a small bug from a symptom (stack, unhandled rejection) | opencode | sonnet/medium | — |
| Write a spec plus a full-code hand-off plan | sonnet/high, with a sol review loop as the quality gate | opus only if sonnet fails the same review twice | opencode for security, lifecycle or native-integration plans |
| New security or permission design | opus/medium, then sol review | — | haiku, opencode |
| Independent milestone or plan review | codex gpt-6.1-sol/high | — | the model that wrote the code |
| Visual/UI comparison from screenshots (read images, capture with Playwright, write proposal) | opencode | sonnet/medium | — |
| Quick lookups, single grep, reading one file | do it yourself | — | any subagent |

Effort defaults to medium; raise it only when correctness is hard.

## 3. Hard-won rules

1. **Passing self-written tests is not evidence.** A plan or an implementation needs an independent review (sol) when it touches security, lifecycle, privacy or native integration.
2. **Plans are where models differ most.**
   - First-pass security or lifecycle plans fail sol review on every tier: opencode had 9–17 P1s, and opus also had 7–13.
   - So write plans with sonnet/high and let the review loop converge. Opus does not save review rounds.
3. **Execution is where cheap models shine.** With complete code in the plan, haiku and opencode produce byte-identical results with no rework.
4. **Verify every delegated result as root before integrating it:**
   - `git status` / `git diff --stat`, to confirm the write set;
   - rerun the focused tests yourself;
   - typecheck;
   - read every test expectation that was changed, to confirm nothing was loosened.
5. **A cheaper tier failing is data.** Log it, move that task kind up one tier, and note why.
6. **Parallelise.** Idle slots are waste.
   - opencode is free, so run several in separate worktrees.
   - Keep at most 2 Claude subagents at a time.
   - Run reviews (codex) concurrently with implementation of other lanes.
   - Never run two full regressions at once in the same checkout, and never merge into a checkout while a regression runs there.

## 4. Prompt rules per model (details in PROMPTS.md)

- **Every prompt**
  - absolute worktree path and branch;
  - the exact write set, and "STOP and report if you need another file";
  - foreground commands only;
  - exact test and typecheck commands;
  - commit with explicit paths, no attribution lines, never push;
  - the final report format, with RED and GREEN output, counts and deviations.
- **haiku**
  - add "Execute exactly as written. Do not re-tier or delegate. If a tool is refused, use another approved tool rather than skipping a step.";
  - require a per-task RED/GREEN log. Without that, it self-stops, skips negative controls or drops logging.
- **opencode**
  - the prompt must be fully self-contained;
  - `< /dev/null`;
  - "never use background shells";
  - name the plan sections to read;
  - list the already-committed tasks and any API drift since the plan was written.
- **sonnet**
  - give the reviewer findings file and the "fix test first, record RED/GREEN" rule;
  - list the known flakes, so it does not chase them.
- **Reviewers (sol)**
  - give the history of earlier reviews, the fix commits, and the evidence root already ran;
  - name the specific regressions to look for;
  - ask for "verdict PASS / PASS WITH FIXES / FAIL, findings with file:line and a fix", P1/P2 only.

## 5. Recording and self-evolution (do this every time)

After each delegated task is verified, append one row to LEDGER.md:

`| date | project | tool | model/effort | task kind | size | outcome | rework | quality notes | duration | tokens |`

- **outcome:** `pass`, `pass-after-retry`, `partial` or `fail`.
- **rework:** what the next round or the review had to fix.
- **quality:** review findings per kLOC if known, test discipline, whether it stayed in the write set, and honesty about gaps.

Then, at least once per session in which you delegated:
1. Re-read the ledger rows for each task kind.
2. If a tier passed 3 or more times in a row with no rework, try the next cheaper tier on the next instance of that kind.
3. If a tier failed or needed redo, move that kind up a tier.
4. Update the routing table in §2 and add a dated line to the change log below, with the reason. Keep the table the single source of truth.

## Change log

- 2026-10-08: initial owner tiers (haiku simple, sonnet moderate, opus complex).
- 2026-10-10: root over-tiered to opus. Frozen-contract work moves to sonnet; logs, setup and status work move to haiku.
- 2026-10-10: opencode free adopted. First mechanical, then rated by the owner as about Sonnet/high for execution.
- 2026-10-11: opencode plan writing for security and native surfaces failed sol review, so those plans moved to Claude. Then quota pressure, plus the fact that opus plans also failed their first review, moved plan writing to sonnet/high and execution to opencode first. Max 2 Claude subagents.
- 2026-10-11 (evening): opencode passed judgment work, not only verbatim execution:
  - PM12 RED-2/3/4: it designed the tests itself, stayed in scope, and correctly stopped on a gap outside its write set;
  - a root-cause bug fix.

  Review-finding fixes and small root-causing now go to opencode first. haiku proved reliable for full regressions with triage and for Notion sync. This skill was created as the global record.
