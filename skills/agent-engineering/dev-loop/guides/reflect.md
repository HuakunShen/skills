# Reflect: the periodic self-review

Purpose: stop mid-flight requests from being lost and keep the parallel queue full. Default interval 30 minutes (`reflect.interval_minutes`). Run it with the harness's cron or scheduler inside the main session, so it has the session's context. If no scheduler exists, run it by hand at each natural pause.

## Steps

1. Re-read the register, the decision/discussion log, the backlog index and the follow-ups file.
2. List every running agent and lane; flag any with no activity for over an hour.
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
