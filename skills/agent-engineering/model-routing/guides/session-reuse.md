# Session reuse (save context on related delegations)

A fresh worker re-reads the repo, the brief and earlier reports. When a later task builds on an earlier one with the same worker, continue that session instead of starting over. Resuming keeps the earlier context cached and costs only the new message.

## Decide per task

| Situation | Action |
|---|---|
| Rework or follow-up of work a worker just did (review findings against its own change, a failed check, a widened write set) | **Resume** that worker with a short message: the new findings, what to change, acceptance. |
| Next task in the same area, same files, same worktree | **Resume**. |
| Re-review of a fix batch by the same reviewer | **Resume is allowed** when the message says "verify each finding F1..Fn, then attack the fixes". It saves the whole re-read. |
| First security/privacy/lifecycle review of a change, or a reviewer whose independence matters | **Fresh session.** A resumed reviewer is anchored on its earlier verdict. Use a fresh one at least for the first round and for the final gate. |
| Unrelated task, different worktree, or the old session is huge or confused | **Fresh session**; hand over a written summary, not the transcript. |
| Resumed session changed model or effort needs | Fresh session; do not silently change them. |

Never resume into a different workspace than the session ran in. Confirm the session id belongs to the right lane first.

## Mechanics

- **Claude subagent:** keep the returned agent id and send a follow-up with `SendMessage` (`to: <agent id>`). A finished agent is resumed that way; do not spawn a duplicate.
- **Codex CLI:** the session id is printed in the run log header (`session id: <uuid>`). Save it next to the lane output. Continue with `codex exec resume <SESSION_ID> -` (prompt on stdin), or `--last` only when exactly one session in that directory can match. `-m` is accepted; check on your installed version whether sandbox and `--add-dir` options are inherited or must be passed again (`codex exec resume --help`) and say so in the local adapter notes.
- **OpenCode:** `opencode run -s <session-id>` (exact) or `-c` (latest); `--fork` branches without changing the original.
- Record in the ledger that the attempt is a **resume** of attempt X, with before/after usage (see measurement-and-usage.md).

## Cost check

Resume when the saved context is a large share of what a fresh worker would read again. If the old session is already near its context limit, a fresh worker with a tight brief is cheaper than a compacted one.

See [lane registry](lane-registry.md) for the shared table, resume-by-name rules and the token baseline.
