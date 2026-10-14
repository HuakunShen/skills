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

Use the cheapest model that will get the task right on the first try, verify every result yourself, and log the outcome so these rules keep improving. The evidence behind each rule is a single shared ledger (a Notion database named **Model Routing Ledger** by default, or a user-chosen equivalent — see §5 for backends and setup); prompt templates are in [PROMPTS.md](PROMPTS.md).

The owner's standing rule is to save quota. Do not reach for the strongest model by default. Move a kind of task up a tier only after a cheaper tier failed at it, and down a tier after it keeps passing easily.

## 1. Which models exist in which tool

| Model | Available in | Cost | Notes |
|---|---|---|---|
| Claude Haiku 5.5 (`haiku`) | Claude Code / Claude Agent SDK only | low quota | Agent tool `model: "haiku"` |
| Claude Sonnet 5.5 (`sonnet`) | Claude Code / Agent SDK only | medium quota | `model: "sonnet"`, `effort: medium/high` |
| Claude Opus 5.5 (`opus`) | Claude Code / Agent SDK only | high quota | reserve; see §3 |
| opencode `opencode/muse-spark-1.3-contributor-free` ("Muse Spark 1.3 Free") | opencode CLI (any harness with a shell) | free | owner rates it about Sonnet/high for execution; reads images accurately (verified 2026-10-12 on a settings screenshot) |
| gpt-6.1-sol, reasoning effort high | codex CLI (`codex exec`), any harness with a shell | OpenAI quota | independent reviewer; read-only |
| gpt-6.1-sol, efforts low…xhigh | codex CLI, `-s workspace-write` for writes | OpenAI quota | trial as implementer/plan writer from 2026-10-12 (medium first) |
| gpt-6-astra, efforts up to xhigh | codex CLI | OpenAI quota, **very expensive** | strongest OpenAI model here. Owner rule 2026-10-13 (tightened same day): avoid entirely unless the owner asks; codex quota is limited |
| gpt-6-luna, efforts low…max | codex CLI | OpenAI quota | trial as implementer/plan writer from 2026-10-12 (xhigh first) |
| opencode `space-bunny-free` (`#max`) | opencode | free | anonymous, suspected MiniMax M3.1; 1M ctx, images; owner uses it as a benchmark model |
| opencode `ling-3.1-flash-free` | opencode | free | no variants; AA index ≈ GLM-5.3 Flash; TS/Rust daily coding |
| opencode `mimo-v2.6-flash-free` | opencode | free | no variants; ≈ DeepSeek V4.1 Flash; coding |
| opencode `longcat-2.5-preview-free` | opencode | free | no variants; long multi-tool agent runs |
| opencode `step-5-preview-free` (`#high`) | opencode | free | StepFun, mostly self-reported coding scores |
| opencode `nemotron-3-ultra-free` | opencode | free | no variants; benchmarks disagree; light tasks only until tested |

Not used: `nemotron-3.5-lightning-free` (AA index 13, too weak), `exo-free` (deprecated), `ling-3.0-flash-fin-free` (finance-tuned).
Variants: pass `-m provider/model#variant`; probe with a bogus variant to see "Variant unavailable". Use the highest variant for free models: muse-spark `#xhigh` (no max), space-bunny `#max`, step-5 `#high`.
Data: Zen's free endpoints may use prompts and outputs for training during the free period. Only send code that is or will be open source (Kunkun is). Never send secrets.

If the current harness has no Claude models (Codex, opencode, Cursor, another CLI), the Claude rows do not exist. Map the tiers like this:
- **Cheap/mechanical:** opencode free model.
- **Execution of a full plan:** opencode free model.
- **Judgment fixes and plan writing:** the harness's mid-tier model, or opencode with a stricter prompt and an independent review.
- **Review:** codex gpt-6.1-sol, read-only.

### Reviewer benchmark (2026-10-12, S8 plan round 2, reference = sol/high's 11 findings: 4 P1 + 7 P2)

| Reviewer | Overlap with sol | Own findings | Notes |
|---|---|---|---|
| gpt-6.1-sol/high | reference | 4 P1 + 7 P2 | gate reviewer |
| gpt-6-luna/xhigh | (not on S8) | — | on SH1 and V7 it found real P1s that sol's own replay missed; good overflow reviewer |
| muse-spark `#xhigh` | ~7/11 | 6 P1 + 7 P2 | best free reviewer; slight over-severity; usable as a second gate opinion |
| step-5 `#high` | ~4/11 | 11 P2 | finds real doc/code mismatches (dead code, wrong line numbers) but rates everything P2 and missed the MCP/OAuth P1s |
| longcat-2.5 | ~2/11 | 1 P1 + 4 P2 | some unique valid points; wrongly declared egress complete — do not use alone |
| space-bunny, ling-3.1, mimo | no result | — | endpoint/rate-limit failures on long read-only reviews; retry later |

Rule: for a plan review, use sol (gate) plus muse as the free second opinion. Free endpoints drop long runs often (ling: 3 "Endpoint unavailable" failures in one day), so do not depend on one free model for a gate.

Owner rule (2026-10-13): codex quota is limited. Use gpt-6.1-sol mainly for gate reviews; prefer opencode free models (muse) and Claude sonnet/opus for writing. Do not use gpt-6-astra.

Owner rule (2026-10-12): hard design and architecture work goes to the strongest models only: gpt-6.1-sol (default), gpt-6-astra (only for exceptionally important design; too expensive otherwise), muse-spark #xhigh, opus high/xhigh, optionally space-bunny #max. Do not assign it to gpt-6-luna (weaker; extra data point at most).

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
  - If the owner's OpenCode desktop app holds port 49374, do not infer that the CLI is unusable. The installed CLI documents `opencode run --standalone` (verified 2026-10-14), which creates a private server; use it for a fresh isolated task instead of `--server`/attaching to the owner's service. Never kill the owner's app. If an actual standalone attempt fails, fall back to another tier.
  - For task-owned CLI scratch/logs, explicitly put `TMPDIR`, `TMP`, `TEMP` and `XDG_DATA_HOME`/`XDG_CACHE_HOME`/`XDG_STATE_HOME` on the external task directory when isolation is needed; preserve required session data only for the active task, and never clean shared owner app data. Public-only input rules still apply.
- **codex**
  - Command: `codex exec -s read-only -m gpt-6.1-sol -c model_reasoning_effort=high -o out.md - < prompt.md`.
  - Use it for reviews only. It is read-only and reproduces bugs in memory.
  - Typical review: 10–25 minutes.

## 2. Routing table (lives in the rules store, not here)

The current tiers live in the shared rules store (§5 bootstrap finds it by name: Notion database or Sheets tab **Model Routing Rules**). Read rows with `Type=routing`, `Status=current` before every delegation; that table is the single source of truth, not this file.

Update protocol (data goes to the store, this file stays unchanged):

1. Insert a new `routing` row with the new First choice / Fallback / Never and the reason in Details.
2. Mark the old row for that task kind `Status=superseded` (never edit or delete history).
3. Insert a `change` row with today's date describing what changed and why.

Effort defaults to medium; raise it only when correctness is hard.

## 3. Hard-won rules

Durable principles live in the rules store as rows with `Type=principle`, `Status=current` (same store as §2). Read them when they matter for the task; add a new one when experience earns it, supersede (never edit) when one stops being true. The standing ones at migration time: independent review for security/lifecycle/privacy/native work; plans differ most between tiers, execution differs least; verify every delegated result yourself (`git status`, rerun tests, typecheck, read changed expectations); a cheaper tier failing is data, move up; parallelise (free opencode runs in separate worktrees, at most 2 Claude subagents, never two regressions in one checkout).

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

All machines share ONE ledger that lives outside this repo, so every machine reads and writes the same rows. Never create a second store, and never fall back to a local file without the user explicitly choosing it.

Supported backends (pick one per user, then every machine uses it):

- **Notion** (default): a database named exactly `Model Routing Ledger`.
- **Google Sheets** (equivalent): a spreadsheet named exactly `Model Routing Ledger` whose first row is the column headers below. The rules store (§2) is a second tab named `Model Routing Rules`.

Schema (same columns in both backends):

| Column | Notion type | Sheets column | Content |
|---|---|---|---|
| Name | title | A | `{date} · {project} · {model} · {first ~50 chars of task kind}` |
| Date | date | B | `YYYY-MM-DD` |
| Project | text | C | short project key |
| Tool | text | D | `claude`, `opencode`, `codex`, … |
| Model | text | E | model/effort, e.g. `sonnet/high` |
| Task kind | text | F | what was delegated |
| Size | text | G | commits, files, lines — whatever measures the task |
| Outcome | text | H | `pass`, `pass-after-retry`, `partial` or `fail`, with a parenthesised qualifier when needed (e.g. `pass (pending sol)`) |
| Rework | text | I | what the next round or the review had to fix |
| Quality notes | text | J | review findings per kLOC if known, test discipline, whether it stayed in the write set, honesty about gaps |
| Duration | text | K | wall-clock |
| Tokens | text | L | subagent tokens when reported |

First-run bootstrap (once per user, before the first record or review — sets up BOTH stores, `Model Routing Ledger` and `Model Routing Rules` with the routing/principle/change schema from §2):

1. If a Notion connection exists, search it for databases named `Model Routing Ledger` and `Model Routing Rules`. Found → use them (look them up by name every session; never hard-code ids, they differ per workspace).
2. Connected but a store is missing → create it with the schema above (ledger) or the §2 schema (rules: `Name` title; `Type`, `Date`, `First choice`, `Fallback`, `Never`, `Details`, `Status` text), then use it. Tell the user you created it.
3. No Notion connection → ask the user to connect Notion, or to use Google Sheets instead (then create the spreadsheet with the header row above and use it). If their tools need a spreadsheet id, ask once and reuse it.
4. Record each verified delegation as one row right away; do not batch.

Then, at least once per session in which you delegated:
1. Read the ledger rows for each task kind (filter by Task kind, newest first).
2. If a tier passed 3 or more times in a row with no rework, try the next cheaper tier on the next instance of that kind.
3. If a tier failed or needed redo, move that kind up a tier.
4. Update the rules store per §2 and add a `change` row with the reason, instead of editing this file. The file stays stable; the stores evolve.
