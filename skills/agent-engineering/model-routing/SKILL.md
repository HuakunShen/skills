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

## 2. Routing table (current rules)

| Task kind | First choice | Fallback | Never |
|---|---|---|---|
| Run tests/regressions, collect logs, triage failures (rerun alone) | haiku | opencode | opus |
| Status, Notion or table updates; rule-driven doc sweeps over a named file set | haiku or opencode | sonnet | opus |
| Execute a reviewed plan whose code and tests are given verbatim, any task size | opencode | haiku (cheap tasks), sonnet; Codex sol/medium after repeated endpoint failure, then sol/high review for lifecycle | opus |
| Implement review findings or convergence RED items: test first, judgment, small write set | opencode (good evidence 2026-10-11) | sonnet/high | — |
| Fix races, lifecycle or concurrency findings with a deadlock risk | sonnet/high | opus/medium after sonnet fails twice | haiku |
| Merge a finished branch with many conflicts | sonnet/high | — | haiku |
| Root-cause a small bug from a symptom (stack, unhandled rejection) | opencode (Muse/xhigh first for Go traces; MiMo trial needs review) | sonnet/medium | — |
| Write a spec plus a full-code hand-off plan | sonnet/high, with a sol review loop as the quality gate | opus only if sonnet fails the same review twice | opencode for security, lifecycle or native-integration plans |
| New security or permission design | opus/medium, then sol review | — | haiku, opencode |
| Independent milestone or plan review | codex gpt-6.1-sol/high | — | the model that wrote the code |
| Visual/UI comparison from screenshots (read images, capture with Playwright, write proposal) | opencode | sonnet/medium | — |
| Quick lookups, single grep, reading one file | do it yourself | — | any subagent |
| Private multi-receipt runtime/provenance judgement | main agent; gpt-6.1-sol/medium if delegated | Luna for locating paths only | cheap verdict-only audit |

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

All machines share ONE ledger that lives outside this repo, so every machine reads and writes the same rows. Never create a second store, and never fall back to a local file without the user explicitly choosing it.

Supported backends (pick one per user, then every machine uses it):

- **Notion** (default): a database named exactly `Model Routing Ledger`.
- **Google Sheets** (equivalent): a spreadsheet named exactly `Model Routing Ledger` whose first row is the column headers below.

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

First-run bootstrap (once per user, before the first record or review):

1. If a Notion connection exists, search it for a database named `Model Routing Ledger`. Found → use it (look it up by name every session; never hard-code its id, it differs per workspace).
2. Connected but not found → create it with the schema above, then use it. Tell the user you created it.
3. No Notion connection → ask the user to connect Notion, or to use Google Sheets instead (then create the spreadsheet with the header row above and use it). If their tools need a spreadsheet id, ask once and reuse it.
4. Record each verified delegation as one row right away; do not batch.

Then, at least once per session in which you delegated:
1. Read the ledger rows for each task kind (filter by Task kind, newest first).
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
- 2026-10-12 (Xross): Muse Spark/xhigh produced five synthetic public-schema fixtures in ~1 minute with no rework; independent JSON/IP-range checks passed. Keep free models first for mechanical execution. Xross is currently private, so this trial sent no repository source; private lifecycle and contract integration remained in internal workers. One success is insufficient to demote those task kinds.
- 2026-10-13 (Xross): OpenCode standalone tool cwd can differ from the CLI subprocess cwd. Supply an absolute task directory in the prompt and explicit workdir/paths for every tool; verify tool logs before declaring private-source isolation. Preserve nonzero CLI exit status even when a written research artifact independently verifies; do not label the whole run green from final prose.

- 2026-10-13 (Xross locator verification): before claiming a predecessor or named file is absent, stat the explicit path and account for ignored reference directories. Before quoting chunk/buffer sizes, read the defining constant and distinguish hash chunks, transport blocks and stream item payloads. A bounded Luna audit needed both corrections; retain root verification, do not promote its inferred facts from prose alone.

- 2026-10-13 (Xross SDK preparation): bounded internal Luna/medium export/install/typecheck tasks verified without source edits; keep private-source isolation and root reruns. Do not promote static consumer preparation to live RPC acceptance. Pass an explicit non-reserved shell result variable in delegation commands.

- 2026-10-13 (Xross CU preparation): keep private locator work on internal Luna and security/native attribution on Sol; tree review rejected expiry renewal from receipt+mtime without bearer binding. Current routing tiers retained: disposable Create-bound proof and source-backed global IPC gate checks were required, so no demotion from this round.

## Owner rule (2026-10-13, evening)
Outsource first. Send work to free opencode models, or to gpt-6.1-sol as writer or reviewer. Use Claude subagents only after free models fail, for example after two failures on the same task. Up to 4 Claude subagents may run when necessary.

- 2026-10-13 (Xross native preparation): a Sol6.1/medium copy/adaptation required three lifecycle P1 fixes and a runtime-only historical-size correction before Root headless PASS. Treat native cleanup/publication as judgment work even when copying an existing fixture. Keep Sonnet/high first where available; if private-source isolation and unavailable Claude require an internal Sol execution fallback, use high on the next native lifecycle adaptation, with an independent tree review and Root runtime. Do not substitute static PASS for runtime or GUI acceptance.

- 2026-10-14 (Xross retained artifact lookup): treat fixture qualification as judgment, not a filename lookup. The cheap locator found matching Linux files but Root inferred they were Mac fixtures; real host execution failed ENOEXEC. Future native artifact qualification is done by the main integration agent with `file`, runtime target and original producer receipt, even after a cheap path lookup. Hash equality/source equality alone is insufficient. The §2 quick-lookup/main-agent rule remains authoritative; no private source may be sent to free endpoints.

- 2026-10-14: Xross Luna route lookup conflated import preflight and a scoped nativeAcceptance=false with actual T2 PASS; Root corrected against terminal13/4 reports. Keep locating cheap, move private cross-record provenance judgement to main/Sol medium. Internal Sol6.1 builds and bounded test execution passed; private-source data restrictions remain unchanged.

- 2026-10-12 (kknet): parallel free-model cohort used sanitized source snapshots: Muse review106s + exact source edit127s passed source-only Root checks; Step553s and MiMo401s supplied useful analysis but proposed unproven or contradicted conclusions. Prefer the stronger free Muse/xhigh for the next comparable Go trace, retain independent review, and do not infer a global ranking from one cohort. CLI v2.0.26 standalone Muse403 resolved by exact-session standard-CLI retry; no paid fallback. Original runtime qualification remains pending.

- 2026-10-13 (kknet development): Muse authored a bounded Go observer after an exact-session recovery; Root fixed two parser details and ran real25/26 controls. A later reviewed implementation task hit two standard-CLI403s with zero edits; sol/medium fallback plus independent sol/high review kept development moving. Review found1P1/1P2 and Root corrected them before actual29 controls and originalS02PASS after a separate source-proven loopback fixture admission. Keep free first; endpoint failure is availability data, not a model ranking. Native times/tokens unmeasured. OpenCode v1 permission assumptions failed a harmless shell probe in one MiMo lane; enforce and verify current project permissions before future execution claims.

- 2026-10-13 (kknet route-C): standard CLI Muse/xhigh evidence task and independent Ling crate-doc task both returned provider.auth403 without output (4.12s/2.47s). This is endpoint availability evidence, not comparative model quality. Keep free-first execution; after this shared availability failure continue finite sol/medium implementation plus sol/high private-lifecycle review, preserving actual tests and no served-model/timing inference.

- 2026-10-13 (kknet owned engine): shared standard free-endpoint failures remain availability fallback evidence. Finite sol/medium authored SDK/admission/actor; sol/high caught a requested-stop terminal classification P2, fixed with RED/GREEN. Root actual same3MiB Service body4/negative2 proves continued execution after request expiry/drop, separate from source review. Luna/xhigh fixture and named-doc trials required oracle/cleanup/attribution rework; keep independent lifecycle gates and cheaper document first with exact source labels, not broad automatic tier escalation. Times/tokens unmeasured; keep free-first routing.

- 2026-10-13 (kknet canonical IPC): sol/medium control/backend and daemon, Luna/xhigh bounded CLI completed finite writes under documented free-endpoint auth fallback. Independent sol/high caught wrapped-first-cause and foreign-operation-binding P2s, both corrected with actual RED/GREEN; Root full-check exposed omitted shared contract corpus (test-only correction). Keep free-first; keep identity/lifecycle review gates for both native implementers rather than treating a focused green as integration completeness. Durations/tokens unmeasured.

- 2026-10-13 (kknet active-core daemon shutdown): finite sol/medium observer plus sol/high source review required a runtime-driven strategy correction: Docker logs corrupt binary receipts; live attach with strict terminal80, natural EOF and true child join then passed actual TLS/REALITY idle-core SIGTERM. A Root one-line listener retry error-class bridge retained limits and was separately reviewed. Keep free-first availability fallback and independent lifecycle review; source/mechanism green alone did not qualify observation strategy. Native model duration/tokens unmeasured.

- 2026-10-13 (kknet restart and revision audit): finite sol/medium executor with sol/high lifecycle review completed same-daemon restart after Root tightened CLI refusal specificity. Root actual two profiles/eight bodies/two stale requests passed, separate from eight mechanism controls. Source audit caught cross-owner secret-ref restrictions and CLI summary/error visibility limits before revision implementation; keep exact source/observation labels and independent lifecycle gates. Free-first fallback availability is unchanged; native times/tokens unmeasured.

- 2026-10-13 (kknet revision execution): sol/medium finite executor correctly reported an observable-CLI boundary before inventing CandidateSummary counts; Root narrowed attribution while preserving public DTO and real traffic gates. Independent sol/high review and Root nine controls plus twelve actual bodies on two profiles passed. Keep source-derived private expectations explicitly unobserved and original budgets; no need higher tier for this bounded correction. Native times/tokens unmeasured; free endpoint fallback unchanged.

- 2026-10-13 (kknet canonical crash recovery): sol/medium author with sol/high source gate passed Root eight mechanisms and actual two-profile SIG9/recovery controls. Exact abnormal DTO retained and successful request joins are separate from source review. A finite product audit exposed live-probe state teardown and DIRECT/internal-network gaps; next work is concrete selected-node publication and explicit loopback egress, rather than multiplying equivalent harnesses. Keep free-first auth fallback and independent privacy/lifecycle gates; native times/tokens unmeasured.

- 2026-10-13 (kknet selected-node product slice): Luna/xhigh implemented the frozen inspect/selected-claim CLI with six Root IPC controls and independent sol/high source PASS; sol/high authored a narrow original-budget review decoder with independent Luna review and Root eight controls. Keep cheaper bounded execution with independent identity/accounting review; do not infer comparative tier quality from helper vs CLI tasks. Final Control commit still has a confirmed request-deadline P2 under repair, so whole feature is not accepted. Corrected loopback plan closes a fixture-feature P2; static image tooling may run in parallel, actual image/runtime waits on immutable public-root inputs and source gates. Free auth fallback remains availability data; durations/tokens unmeasured.

- 2026-10-13 (kknet final-node acceptance): finite sol/medium Control and Luna/xhigh CLI needed independent sol/high deadline/output-scope P2 repairs with meaningful RED/GREEN. Root current1.85 whole check667/707/16 and frozenlab1426P1manualBLOCKED0F52hashes pass their exact source gates. Keep independent original-request/lifecycle review for both native implementers; focused green did not catch lock-wait or unscoped output. Initial static image builder11 controls remain sourceFAIL2P2 pending unified repair; not an accepted image. Free-first auth availability fallback unchanged; timings/tokens unmeasured.

- 2026-10-13 (kknet loopback prerequisites): bounded Luna/xhigh generator, image tooling and endpoint RPC continued actual product implementation under the existing free-auth availability fallback. Independent sol/high review caught builder worker-path/process-ownership and generator guard P2s; Root caught a missed discovery count during real outside-sandbox304 tests. Task1 sol/medium SDK passed its separate50-source gate. Keep independent source/lifecycle review for both implementers and record dependency/sandbox failures separately; no broad tier ranking from differing scopes. Strict SDK Task23 currently has a newly confirmed cached-readiness invalidation P2 under repair, not an accepted runtime. Durations/tokens unmeasured; free-first preference unchanged.

- 2026-10-13 (kknet loopback assembly): retain free-first routing, with prior endpoint403/401 evidence and no auth retries. Native Sol author/reviewer capacity errors used bounded Luna/xhigh overflow: exact marker repair and finite template/settlement gates passed Root checks. Finite source gates did not catch actual Docker omitted nil fields or trailing template lines; require actual integration observations at these seams, not a model tier escalation based solely on untested source PASS. Harness generated documents now use an independent contracts parser after real invalid-enum failure. No duration/token ranking or three-clean-pass downgrade is supported by this batch.

- 2026-10-13 (kknet actual loopback gate): Luna/xhigh CA recipe execution needed one ordering P2 repair; separate Luna artifact rejoin plus Root actual checks qualified four synthetic bodies/three credential/two marker refusals. Keep execution and artifact review separate, retain source-pass versus runtime-pass distinction, and require directory traversal plus nonroot reads in image audits. Sanitized CLI audit needed a Root timeline correction: newest verified accepted104 staging takes precedence over later-positioned historical v2 refusal paragraphs. No three-consecutive-clean same-kind outcomes justify down-tiering yet.

- 2026-10-13 (kknet real subscription): bounded Luna/xhigh execution plus separate review delivered a first actual fresh104-node publication/production-loopback HTTP and verifiedHTTPS pass. Root fixed cross-module API assumptions and early owner registration; reviewer privacy/path findings were useful but a later completed-child P1 was contradicted by full source and actual no-network reproduction, explicitly withdrawn. Keep free-first under existing endpoint-auth fallback; use available sol/high for the next substantial lifecycle gate when capacity returns, and require full code spans plus reproduction for overflow-review allegations. No global tier ranking or clean-three-pass downgrade; native times/tokens unmeasured.
