# Visible background workers with hc (herdr-core)

Use this when the user's config names `hc` as the worker runtime, or when workers started with `opencode`, `codex` or `claude` in the background cannot be listed. `hc` keeps each worker in a persistent terminal the user can list, read, attach to and stop. It is not herdr (the pane multiplexer); `hc --skill` prints its own manual. Checked against hc 0.1.17; run `hc --help` if a flag below is missing.

## Why this exists

A harness only lists background jobs it launched itself. A worker started with `nohup ... &`, or one whose wait is a `until ...; sleep` loop, shows nothing and burns the orchestrator's turn polling. With hc, the worker is a named terminal and the wait is one blocking command.

## Start

```sh
hc run --bg --name lane-a --label lane=lane-a --label task=<task-id> --cwd <worktree> opencode
```

- One terminal per lane, a unique `--name` (`a-z 0-9 - _`, up to 32). Run agents **interactively**, never in a one-shot print mode, so they stay readable and steerable.
- Always `--label task=<activity task id>` when the lane has one. Activity's hc observer (see the kk-tasks ADR `hc-run-observer`) links runs to tasks only through this label.
- Put the first task in the launch when using a template (`hc run reviewer "<task>"`). For a plain agent, `hc wait lane-a` until it is idle, then `hc send lane-a "<brief>"`; a send to a booting agent can be dropped. If a launch reports `first_message.sent` false, read the screen before resending.
- Codex must be started with `--no-daemon`, or its commands run outside hc.
- Set the closing report path in the brief; the worker can also send a short message back with `hc send $HC_TERMINAL_ID "<result>"` when it was started from an hc terminal.

## Wait without polling

| Goal | Command |
|---|---|
| Block until a program exits or an agent finishes its turn | `hc wait lane-a --timeout 86400` |
| Block until a server prints a marker | `hc wait web --output ready` |
| Send a task and block for that turn | `hc send --wait lane-a "<task>"` |
| Next news from any helper (needs an hc parent) | `hc wait --children any` |

Facts checked on this machine:

- `hc wait` returns when the target ends or changes status. The result is JSON (`ended`, `exit_code`, `reason`, `status`).
- `--timeout` defaults to 180 s. On expiry it returns `reason: "timeout"` and the worker keeps running; it is a check-in, not a failure. `--timeout 0` returns immediately and is **not** "wait forever"; use a large number.
- A harness foreground shell call usually ends at about 10 minutes. Run the wait as the harness's **background** job, one per worker, so each worker has a visible entry and the orchestrator is notified when it ends:

```sh
# run_in_background: true
hc wait lane-a --timeout 86400; hc get lane-a
```

- `--children` needs the caller to be an hc terminal. A harness shell is not, and terminals it starts have `parent: null`. Wait on names there, or run the orchestrator itself under `hc run`.
- A coding-agent TUI does not exit after a turn. `wait` ends on idle, done, blocked or error, not on process exit.

## See and manage

```sh
hc ls                     # live workers (add --all for finished)
hc get lane-a             # state, status, cwd, labels, exit code
hc read lane-a --lines 80 # screen plus history
hc attach lane-a          # take over; Ctrl+\ detaches
hc events --label lane=lane-a   # follow changes, one JSON line each
hc interrupt lane-a       # stop the current turn, keep the process
hc kill lane-a; hc rm lane-a    # when the result is accepted
```

- `blocked` means a permission dialog or question needs a person. Read the screen and ask the user; `hc send` refuses unless `--force`, and `--force` is not a way around a permission decision.
- Kill and remove only terminals you started. `hc ls` includes the user's other work.
- Never run `hc server stop` or restart the core unless asked; it affects every terminal.
- `hc rm` deletes the record. Capture the exit code and the report before removing.

## What hc does not do

- It does not tell which tools an agent called or which files it changed. Use the agent CLI's own session log and `git diff`.
- It keeps no history after `rm`. Durable records stay in the register, the intake log and the decision log.
- It has no task concept. Task state stays in `activity` (manage-repo-tasks skill): a worker's exit code or idle status is not a task result. Only a verified outcome moves a task, written with an explicit `activity tasks apply`.
- It does not choose models or concurrency. Keep using `model-routing` and the user's limits.

## Orchestrator routine

1. Start each independent lane with a name, `task=` label and brief ([roles and briefs](roles-and-briefs.md)).
2. For each lane, start one background `hc wait` job. Do not write `until` loops.
3. State the board to the user from `hc ls`: lane, worker, status, last change.
4. On a wait result: read the report and the diff, run the scripted check, decide, then update records. A `blocked` or `error` lane goes to the user or a retry per the brief; do not mark the task done or failed from hc state alone.
5. After acceptance: `hc kill` and `hc rm` the lane's terminal.
6. In reflect ([reflect](reflect.md)), `hc ls` and `hc events` replace guessing which agents are still running; flag a `working` lane with no change for over an hour.
