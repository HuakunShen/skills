# Lane registry and resume-by-name (shared format)

Added 2026-11-15 after comparing xross-dev and kunkun-v2.1 (about 55% of lanes there are already resumes). The remaining waste is bookkeeping, lost reports, unmeasured fresh-start cost and long sessions, not "always fresh".

## 1. Registry: one table, written by the launcher, never by hand

`<runs-dir>/lanes.jsonl`, one JSON object per lane, rewritten atomically (write temp, `mv`). Fields:

`lane`, `runner` (codex|opencode|claude), `model`, `effort`, `session_id`, `cwd` (worktree), `task`, `write_set`, `status` (running|done|stalled|killed|failed), `kind` (impl|review|gate|audit), `fresh_required` (true for first independent review and final gate), `runs` (count), `started_at`, `ended_at`, `last_report` (path), `tokens_last_run`, `tokens_total`.

The launcher fills `session_id` from the log (`session id: <uuid>` for Codex, `opencode session list` for opencode), parses `tokens used` from the log tail into `tokens_last_run`, and sets `status`. A lane name is unique; relaunching an existing name with a different runner or cwd is refused.

## 2. Resume by lane name

`lane.sh --resume <lane> <followup-file>` (or the project's equivalent) reads model, effort, runner, sandbox flags and cwd from the registry. The caller passes only the new message. It refuses when:
- the registry row is missing, or `session_id` is empty;
- `cwd` no longer exists;
- `fresh_required` is true (say so and tell the orchestrator to start a fresh reviewer);
- the caller asks for a different model (that is a fresh session, per session-reuse.md).

Before the run it archives the previous report as `<lane>.out.<n>` instead of deleting it.

## 3. Short reports

Every brief ends with: final report at most 8 lines (commit or "uncommitted", what changed, tests and results, not verified), written to the result file. The orchestrator reads the result file, not the log. Resume nudges use one layer per message and "stopping after X is a failure".

## 4. Measure the fresh-start cost once

Run one trivial fresh lane (`print the first line of AGENTS.md and stop`) per runner and record its token total in the registry as `baseline_fresh_tokens`. Everything else (digest, FOCUS summary) is judged against that number. Do not claim savings without a before/after pair (same task, resumed lane vs fresh lane, or lane vs live worker).

## 5. Orchestrator-side summaries

After a context compaction the orchestrator re-reads FOCUS.md and WORK-REGISTER and gets skill summaries re-injected. Keep a one-page `FOCUS-digest.md` (areas, status, next step, running lanes) that is enough to continue; read the full file only for the task being touched.

## 6. Live workers (trial only)

`hc run` + `hc send`/`hc wait` (or herdr `agent start`/`agent prompt`) for review-fix-recheck chains. Needs: a per-prompt result file, a hand-off at about 400k tokens, a clean restart path, and visibility in `hc ls`. First independent reviews and final gates stay fresh. Compare against a resumed lane on the same task before adopting.

## 7. Token accounting corrections (2026-11-15)

- Codex's printed `tokens used` is **session-cumulative**, not per run (xross test: 30,947 fresh, then 31,909 and 32,920 after two one-line resumes). Store it as `tokens_session`; `tokens_last_run` is the difference from the previous value; never sum the printed figures.
- The printed figure does not show cached re-sends. Three days of rollout logs (`~/.codex/sessions/**/rollout-*.jsonl`, `token_count` events) gave 3,951M input tokens, 99% cached, and 35% of all input followed an empty `write_stdin` poll of a running command. For real cost read `total_token_usage` (`input_tokens`, `cached_input_tokens`, `output_tokens`) from the rollout file, and record the number of model calls and peak context.
- Fresh-start floor measured: xross luna 30.9k, kunkun terra 28.8k, opencode luna about 25.8k non-cached.
- Brief rule that follows: never poll a running command more often than every 60 s; prefer one blocking call, or end the run and let the orchestrator wait with `hc wait` and resume with the result tail.

## 8. Waiting and hand-off rules agreed with the xross and kunkun orchestrators (2026-11-15)

- **Waiting.** Every lane brief carries: "never poll a running command more often than every 60 s; prefer one blocking foreground call with a long timeout". Both projects added it on 2026-11-15; whether lanes obey it is not yet measured. Check by re-running the rollout statistics (share of input after empty `write_stdin` polls; it was 35%).
- **Split runs only for verification lanes.** A lane that only runs a given script and returns counts may end after starting it; the orchestrator runs the command (`hc run`, `hc wait` costs no model tokens) and resumes with the result tail. Do not split implement lanes: RED-to-GREEN work iterates, so each build would become another resume over the whole context, and cheap models already stop early. Sandboxed tests that break under the hc environment run outside hc.
- **Hand-off between layers, not mid-layer.** At about 200k context, and only after a GREEN checkpoint the orchestrator has committed, start a fresh lane. The hand-off must carry the open-finding list and the exact test commands (lane writes HANDOFF.md, the orchestrator's next-layer brief is built from it). The new registry row gets a new lane name with `parent` set to the old lane. This is a trial, not yet a rule: fresh start costs about 26-31k tokens and loses what the session learned; long resumed sessions cost more per call and showed more stalls in xross (not measured as quality).
- **Reviewers** stay fresh for the first independent review and the final gate.
- **opencode** blocks until a command ends, so no poll pattern was seen there; usage is in `~/.local/share/opencode/opencode.db` and in `opencode run --format json` step-finish parts (not yet analysed).
- Unknown: how Codex quota weights cached input; what starts the `codex-auto-review` sessions (95 in three days in kunkun).
