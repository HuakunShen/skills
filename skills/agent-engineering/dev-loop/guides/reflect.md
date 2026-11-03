# Reflect: the periodic self-review

Purpose: stop mid-flight requests from being lost and keep the parallel queue full. Default interval 30 minutes (`reflect.interval_minutes`). Run it with the harness's cron or scheduler inside the main session, so it has the session's context. If no scheduler exists, run it by hand at each natural pause.

## Cheap preflight first

Every reflect run inside the main session re-sends the orchestrator's whole context, so most runs should not reach the model. Schedule this instead, and wake the orchestrator only when it prints `"wake": true`:

```sh
python3 <skill-folder>/scripts/devloop.py preflight --project <root> --state <scratch>/preflight.digest --stale-hours 1
```

It reads the intake log (rows not `done`, `dropped` or `merged-into`), `git worktree list` (dirty state, hours since the last commit) and the register's modification time, and compares a digest with the previous run. It wakes for untriaged `captured` rows, lanes with no commit for the stale threshold, or any change. Running agents that the harness tracks still notify the orchestrator on their own; the preflight does not need to watch them.

## Steps (when the preflight wakes the orchestrator, or at a natural pause)

1. Re-read the register, the decision/discussion log, the backlog index and the follow-ups file.
2. List every running agent and lane; flag any with no activity for over an hour. If workers run under `hc`, use `hc ls` and `hc get` ([hc runtime](hc-runtime.md)).
3. List every intake row that is not terminal (`captured`, or `lane:`/`patch-batch` with no live lane or batch). Compare against what the owner has said in chat: find requests with no row at all and add them. See [intake](intake.md).
4. Find independent work that can start now and start it; keep the queue non-empty. Respect the user's concurrency limits.
5. Merge finished lanes; update the register, logs and backlog; clean up worktrees and scratch.
6. Report (language per `language`/`reflect.language`).

## Report table

| Section | Content |
|---|---|
| Running | lane, executor, last activity |
| Finished | what merged, what was verified, what was not |
| Newly started | lane and why it is independent |
| Owed and forgotten | requests found unregistered, now registered |
| Needs the owner | decisions with a recommendation |
| Next | what happens in the next interval |

Keep it short. If nothing changed, say so in one line.

## Cron prompt (adapt the paths)

```text
Reflect on this project. Read <register>, <decision log>, <backlog index> and
<follow-ups>. List running agents and flag any silent for over 1 hour. Find things
the owner asked for that are neither done nor registered. Start every independent
piece of work that can run in parallel now. Merge finished lanes and update the
files. Reply with the table: running, finished, newly started, owed and forgotten,
needs the owner, then what happens next.
```

The `reflect` instruction source can replace this prompt or add steps (for example "mirror status back to the Notion inbox").
