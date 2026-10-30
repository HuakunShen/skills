# Failure modes already seen

| Symptom | Cause | Do |
|---|---|---|
| Requests vanish after a long run | Held only in chat | Write intent to the inbox/decision log first; run the reflect loop. |
| Orchestrator dove into the newest bug and forgot the other lanes | New request treated as the new focus | Capture to the intake log first, delegate, board check before and after ([intake](intake.md)). |
| Only one background task running | Agents default to one task | Orchestrator starts all independent lanes; reflect step 4. |
| Executor stops mid-plan, plan says X, tree says Y | Plan/reality drift | Executor stops and reports evidence; orchestrator records the deviation and widens the write set deliberately. |
| File edited outside the approved write set | Write-set list built by hand and a path dropped | Build lists from the approval record, compare the count, record in the decision log. |
| Executor self-stops citing a routing table, skips a control when a tool is refused, drops logging after resume | Weak brief | Brief says execute exactly, use another approved tool if refused, keep the per-task log. |
| Worker exits with a half-done long build | It moved the job to a background shell | Brief: run every command in the foreground and wait. |
| Headless CLI worker sits at 0% CPU | Waits on stdin | Give it a closed stdin; confirm a session appears within minutes, else restart. |
| Free-tier worker hits usage limits | Limits are per exit IP or per account | Stagger starts, limit simultaneous runs, rotate or fall back per the user's rule, resume the session rather than restart. |
| Wait loop never ends | Process-name pattern matches its own shell | Wait on a pid or output file. |
| Cleanup script deleted files in the wrong place | `cd` failed, then `rm -rf` ran | `cd <main> \|\| exit 1` first in every chained cleanup. |
| Main checkout broke after removing a worktree | Worktrees share submodule state | Re-initialise submodules and check build outputs after every removal; never deinit in main. |
| Amend rewrote someone else's commit | Several agents commit to one branch | Re-read the log right before amending; prefer a new commit; stage exact paths. |
| Plans keep failing review | Wrong author tier for security, lifecycle or native surfaces | Route per `model-routing`; the review loop is the quality gate, not the author. |
| Passing tests prove nothing | Self-written tests only | Negative controls; independent review. |
| Scratch evidence disappeared | Scratch volume wiped | Keep durable scripts and evidence in the private folder. |
| Built bundle fails to launch after copy | Half-finished build copied | Verify the bundle before copying it anywhere. |
