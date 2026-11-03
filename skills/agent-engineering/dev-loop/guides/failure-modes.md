# Failure modes already seen

| Symptom | Cause | Do |
|---|---|---|
| Requests vanish after a long run | Held only in chat | Write intent to the inbox/decision log first; run the reflect loop. |
| Orchestrator dove into the newest bug and forgot the other lanes | New request treated as the new focus | Capture to the intake log first, delegate, board check before and after ([intake](intake.md)). |
| Quota drains in a day with mostly subagents | Every worker inherits all tools and MCP servers, runs hundreds of calls, grows to 500k context, sleep-polls, and re-writes its cache after 5-minute idles | Measure, then apply [token budget](token-budget.md): lean worker agent, capped life with handoff, manifests, no polling. |
| Only one background task running | Agents default to one task | Orchestrator starts all independent lanes; reflect step 4. |
| Executor stops mid-plan, plan says X, tree says Y | Plan/reality drift | Executor stops and reports evidence; orchestrator records the deviation and widens the write set deliberately. |
| File edited outside the approved write set | Write-set list built by hand and a path dropped | Build lists from the approval record, compare the count, record in the decision log. |
| Executor self-stops citing a routing table, skips a control when a tool is refused, drops logging after resume | Weak brief | Brief says execute exactly, use another approved tool if refused, keep the per-task log. |
| Worker exits with a half-done long build | It moved the job to a background shell | Brief: run every command in the foreground and wait. |
| Headless CLI worker sits at 0% CPU | Waits on stdin | Give it a closed stdin; confirm a session appears within minutes, else restart. |
| Free-tier worker hits usage limits | Limits are per exit IP or per account | Stagger starts, limit simultaneous runs, rotate or fall back per the user's rule, resume the session rather than restart. |
| Five workers run but none shows in the harness task list; the orchestrator polls with `until`/`sleep` | Workers were backgrounded inside a shell command, so the harness does not track them | Start each in a named `hc` terminal and wait with one background `hc wait <name> --timeout <large>` per worker ([hc runtime](hc-runtime.md)). `--timeout 0` does not mean forever. |
| Wait loop never ends | Process-name pattern matches its own shell | Wait on a pid or output file. |
| Cleanup script deleted files in the wrong place | `cd` failed, then `rm -rf` ran | `cd <main> \|\| exit 1` first in every chained cleanup. |
| Main checkout broke after removing a worktree | Worktrees share submodule state | Re-initialise submodules and check build outputs after every removal; never deinit in main. |
| Amend rewrote someone else's commit | Several agents commit to one branch | Re-read the log right before amending; prefer a new commit; stage exact paths. |
| Plans keep failing review | Wrong author tier for security, lifecycle or native surfaces | Route per `model-routing`; the review loop is the quality gate, not the author. |
| Passing tests prove nothing | Self-written tests only | Negative controls; independent review. |
| Scratch evidence disappeared | Scratch volume wiped | Keep durable scripts and evidence in the private folder. |
| Built bundle fails to launch after copy | Half-finished build copied | Verify the bundle before copying it anywhere. |
| The orchestrator reports "waiting" with one lane live while a ready queue exists | Blocked was judged for the whole project, and `hc ls` was counted unfiltered | Count only your labelled lanes each turn, refill from a ready-queue file, judge blocked per task. |
| A stale `mkdir` cargo lock stalled every lane for hours | A killed lane never released it | Before waiting on the lock, check whether any cargo/rustc process exists; if none, remove it. |
| A lane stops on "outside the write set" for a file the change must touch | The plan listed too few files | Authorise the named file and resume the same session (`opencode run -c`); do not wait. |
| A worker's mock host passes while the real host breaks | The test only drove a hand-made mock | Require one test through the real counterpart (e.g. the real framed host), and a negative control. |
| Review of a lifecycle change finds a new P1 every round | Each fix adds a path nobody attacked | Budget 3-5 Sol rounds for lifecycle/security diffs; send each finding verbatim back to the author session; merge only on "no findings" plus a green re-run. |
