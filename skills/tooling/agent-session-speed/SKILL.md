---
name: agent-session-speed
description: Use when the user asks how fast their AI coding agent is, wants token-per-second (tps) throughput, time-to-first-token (TTFT) latency, or per-model/per-day speed stats from local session logs — e.g. "analyze my codex speed", "how many tokens per second does my agent run at", "which model streams faster", "analyze zcode/opencode/dsh session performance". Parses OpenAI Codex rollout JSONL, ZCode db.sqlite, OpenCode db.sqlite, and DSH (DeepSeek Harness) session.v4.jsonl.zstd. Not for API-benchmark load testing or web perf.
license: MIT
compatibility: Node 22.5+ / Bun 1.1+ / Deno 2.2+ (built-in sqlite and zstd, zero dependencies)
metadata:
  author: Huakun Shen
  domain: ai-agent-session-analytics
  tags:
    - codex
    - zcode
    - opencode
    - agent-sessions
    - throughput
    - tokens-per-second
    - ttft
    - telemetry
    - sqlite
    - jsonl
---

# Agent session speed (token throughput & TTFT)

Measure how fast an AI coding agent actually runs, from the session logs it
already wrote to disk: tokens-per-second distribution, time-to-first-token
(TTFT), per-model and per-day breakdowns. No instrumentation, no API calls —
the logs are the data source.

## Supported agents

| Agent    | Log source                                                          | Granularity |
|----------|---------------------------------------------------------------------|-------------|
| codex    | `~/.codex/sessions/**/*.jsonl` (+ `~/.codex/archived_sessions/`)     | per turn (JSONL events) |
| zcode    | `~/.zcode/cli/db/db.sqlite` (`model_usage`, `turn_usage` tables)     | per model request **and** per turn |
| opencode | `~/.local/share/opencode/opencode.db` (`session_message` JSON blobs) | per assistant message |
| dsh      | `~/.dsh/sessions/*/*/session-*/session.v4.jsonl.zstd`                | per model response (stream timeline) **and** per turn |

ZCode and dsh have the best data: zcode's `model_usage.duration_ms` is a
single model API call, and dsh records the full streaming chunk timeline per
response — both give true pure model speed. Codex has no per-request timing —
only whole-turn duration — so its "pure speed" is proxied by single-response
turns (see methodology).

## Quick start

```bash
node scripts/analyze_session_speed.ts --agent zcode
bun  scripts/analyze_session_speed.ts --agent dsh
deno run --allow-read --allow-env scripts/analyze_session_speed.ts --agent opencode
# CSV detail (deno also needs --allow-write for --out-csv):
node scripts/analyze_session_speed.ts --agent codex --out-csv turns.csv
```

Custom sources: `--sessions-dir DIR` (codex, repeatable), `--db PATH`
(zcode/opencode sqlite). `--min-gen-ms N` (default 200) drops rows whose
post-TTFT window is suspiciously short.

Output: median/p10/p25/p75/p90/p99 tps, aggregate tps, TTFT median/p90, per
model, per day, optional per-row CSV.

## Methodology

`tps = output_tokens / generation_seconds`, where `generation = duration − TTFT`.

Read these caveats before interpreting numbers:

- **Tool time dilutes turns.** An agent turn alternates model responses with
  shell/tool calls. ZCode's request-level rows avoid this (pure API-call
  duration); Codex does not — split its turns into single-response
  (≈ pure decode speed) vs multi-response (end-to-end, a lower bound).
  Weighted aggregate is the honest "what did I actually wait for" number.
- **TTFT** is prompt upload + queueing before the first token. For opencode
  rows the window necessarily includes TTFT (message-level timestamps); its
  "duration" is the whole message, so tps there is slightly understated.
- **Reasoning tokens** are usually included in output tokens — check the
  format (codex `output_tokens` includes reasoning; zcode reports
  `reasoning_tokens` separately; opencode has both).
- **Filter degenerate rows**: records with `duration ≈ TTFT` produce absurd
  tps (10k+). Exclude >500 tps and generation windows under `--min-gen-ms`.
- **Unfinished work is unmeasurable**: interrupted turns (codex turns without
  `task_complete`, zcode rows with `status != 'completed'`) are counted to
  stderr and skipped.
- Prefer **median over mean**, report p10/p90 — the distribution is skewed by
  short responses and stalls.

## Format reference

### Codex rollout JSONL (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`)

One JSON object per line. Events the parser needs:

- `session_meta` — once per file: `originator`, initial `model`.
- `turn_context` — once per turn: `turn_id`, `model` (models can switch
  mid-session; attribute per turn, not per file).
- `token_usage_record` — one per model response: `usage` (this response),
  `turn_token_usage.output_tokens` (cumulative for the turn — use this),
  `thread_token_usage.input_tokens` (final context size).
- `event_msg` payloads `task_started` / `task_complete` — `duration_ms`,
  `time_to_first_token_ms`. Response count per `turn_id` distinguishes
  single- from multi-response turns.

### ZCode `~/.zcode/cli/db/db.sqlite` (epoch-ms timestamps, read-only open)

- `model_usage` — one row per model API request: `started_at`, `duration_ms`,
  `time_to_first_token_ms`, `input/output/reasoning/cache_*_tokens`,
  `model_id`, `provider_id`, `query_source` (`main_turn`, `workflow_child`,
  `subagent`, plus housekeeping like `session_title`/`compact`),
  `status` (`completed`/`error`/`cancelled`). Open with `{readOnly: true}` —
  the db is live (WAL) while ZCode runs.
- `turn_usage` — per-turn aggregates: same timing fields plus
  `model_request_count`, `tool_call_count`. Join `model_usage` per
  `(session_id, turn_id)` to attribute a dominant model.

### OpenCode `~/.local/share/opencode/opencode.db`

`session_message` rows with `type='assistant'` carry a JSON `data` blob:
`tokens {input, output, reasoning, cacheRead, cacheWrite, ...}`,
`time {created, completed}` (epoch ms), `model {id, providerID}`,
`agent`. Duration = `completed − created` (message-level, includes TTFT);
per-content-part timestamps exist but the schema varies — don't rely on them.

### DSH (DeepSeek Harness) `~/.dsh/sessions/<workspace>/session-*/session.v4.jsonl.zstd`

One zstd-compressed JSONL per session; the file is a **concatenation of
multiple zstd frames** (append-style writes) — split on the magic bytes
`28 B5 2F FD` and decode per frame (see cross-runtime notes). Events (one
JSON object per line, `type` field, epoch-ms `time`):

- `session` — header: `version` (v4 expected), `id`.
- `step/start` / `step/end` — `{turn, step}` boundaries; step start ≈ model
  request start.
- `assistant/message` — one per model response: `data.usage`
  `{inputTokens, outputTokens, reasoningTokens, cacheReadTokens}`,
  `data.message.source {kind, provider, model}` (model label as
  `provider/model` — dsh routes one model to many providers),
  `data.stream[]` chunk timeline (`.time`, or `.time0` + per-chunk `.dt`).
  The min→max stream timestamps are the pure streaming window: tps =
  `outputTokens / (tN − t0)`, TTFT ≈ `t0 − stepStart` (includes prompt
  assembly). Non-streamed responses land in one chunk — window ≈ 0, not
  measurable, filter them out.
- `turn/start` / `turn/end` — turn boundaries; `end.reason.kind ===
  "completed"` distinguishes finished turns; attribute the dominant model by
  output tokens.

## Porting to another agent

The methodology is agent-independent; only the parser changes:

1. Find its session logs on disk (Claude Code: `~/.claude/projects/`;
   Gemini CLI: `~/.gemini/tmp/` — verify against the current version; both
   were empty/absent on the author's machine).
2. Identify per-response **token usage** and **timing** events. If the format
   only logs streaming deltas, reconstruct duration from timestamp spans
   between first and last output event.
3. Add `parse<Agent>()` returning the `Row` schema
   (`agent, level, model, day, outTokens, inputTokens, reasoningTokens,
   steps, durMs, ttftMs, genMs, tps`), wire it into `main()`'s agent switch,
   and extend the table above.

If the agent logs no timing at all, tps is not recoverable from history —
say so instead of approximating from file mtimes.

## Cross-runtime notes

- SQLite is accessed via built-ins: `node:sqlite` (`DatabaseSync`,
  `{readOnly: true}`) on Node and Deno, `bun:sqlite` (`Database`,
  `{readonly: true}`) on Bun — auto-detected via dynamic import with a
  non-literal specifier so each runtime only loads what it has.
- Module specifiers are built at runtime (`"node:" + "sqlite"`) because
  TypeScript can't type the other runtimes' modules and static imports would
  fail to resolve where a module is absent.
- Zstd for dsh sessions: `node:zlib.zstdDecompressSync` on Node and Deno,
  `Bun.zstdDecompressSync` on Bun. Multi-frame files are split on the magic
  bytes and decoded frame by frame: Node/Bun transparently decode concatenated
  frames, but Deno's `node:zlib` stops after the first frame and its
  `DecompressionStream` has no `"zstd"` format — frame-splitting gives
  identical output on all three.
- Deno sandbox: `--allow-read` always; `--allow-env` (reads `HOME`);
  `--allow-write` only for `--out-csv`.
