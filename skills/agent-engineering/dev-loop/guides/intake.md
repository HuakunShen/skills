# Intake: never lose a request

The owner talks to the orchestrator all day: a new feature, a bug, a small tweak. Each one must be recorded the moment it is said, without turning every item into a GitHub issue. The failure to prevent: the orchestrator dives into the newest request and forgets what was already in flight.

## 1. Capture before acting (hard rule)

When a message contains a request, **the first action of that turn is appending a row to the intake log** (`layout.intake`, default `docs/plans/INTAKE.md`): next `W-###` id, date, the owner's words (verbatim, shortened), kind (`bug | feature | chore | question`), size, status `captured`. Only then triage. One message with three requests is three rows. A request that is only in chat is lost at the next compaction.

Also do this when the request arrives mid-task, mid-review, or while a long run is in progress. Capture takes seconds and is never skipped for urgency.

## 2. Triage by size: not everything is an issue

| Size | Test | Where it lives | Closing it |
|---|---|---|---|
| **patch** | Small fix or tweak, one area, obvious cause, no design, low risk | The intake row plus an entry in `docs/backlog/PATCHES.md` (a plain list). No issue, no branch. | Batch several patches into one worker brief or fold into the next lane touching those files; mark each row `done` with the commit. |
| **lane** | New feature, needs design, touches several areas, risky, or long-running | Own row in the register: branch, worktree, owner, write set. A plan file if designed. PR when the project uses PRs. | Merge per the loop; row `done` with the merge commit. |
| **question** | Owner asks for information or a decision | Answer it; log it only if it changes plans. | `done` with the answer pointer. |

Promote a patch to a lane when it grows, when two patches conflict, or when the owner says it matters. An external tracker issue (GitHub, Notion) is created only for lane-sized items, or when `inbox` config says everything mirrors there. Early in a project most work is patches; that keeps the tracker small.

## 3. The orchestrator coordinates; it does not dive

- A new bug or feature never pulls the main session into doing the work itself. Capture it, triage it, then **delegate** it as a lane or fold it into the next patch batch. The main session keeps its job: the whole board.
- If a task truly needs the main session's hands (for example a one-line fix), do it only after the board check below, and write the result back to the log.
- Start independent new work in parallel with what is already running. Do not pause other lanes to focus on the new item unless the owner asked for that explicitly.

## 4. Board check on every interruption

Before starting work on a new request, and again when finishing it, take 10 seconds:

1. Read the register's **In flight** table and the intake rows that are not `done`.
2. Say in one line what is running and where each stands.
3. Confirm the new item has a status that is not `captured` (it has a lane, is in a patch batch, or is answered).

A **focus stack** in the register records "currently doing X, interrupted from Y, return to Y when X done" whenever the main session itself changes tasks. Pop it when finished.

## 5. Reflect closes the loop

The reflect step lists every intake row that is not terminal and every register lane with no activity. Rows still `captured` after one interval are bugs in the process: triage them immediately. Rows `lane:` or `patch-batch` with no matching live lane or batch entry are lost work: restart them.

## 6. Reply with the board

After capturing and triaging, tell the owner what you did in a few lines: "Logged W-014 (bug, patch) and W-015 (feature, new lane). Still running: lane A, lane B. Next: ...". The owner should see that the earlier items are still alive.

## Mirroring

If the config's `inbox` is Notion, GitHub Projects, or another tracker, mirror intake rows there only at the granularity the user wants (default: lanes and questions the owner asked to track). The repo log stays the working record.
