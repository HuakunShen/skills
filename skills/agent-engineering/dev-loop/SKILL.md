---
name: dev-loop
description: An orchestrator-run development process. The owner drops requests (wishes, bugs, features) into any inbox (Notion, GitHub Projects, a local file); one main agent session records, designs, reviews, slices into parallel lanes, delegates to subagents or other agent CLIs, verifies, merges and reports. Defines the development loop, the docs/ project layout (specs, plans, decisions, research, private references), the 30-minute self-review, and a config file that points to the user's own custom rules and per-stage patches. Use when starting or restructuring a project's workflow, orchestrating multi-task work, setting up docs/ conventions, or when the user mentions wishes, backlog, work register, lanes, or a reflect cron.
---

# Dev loop

The owner states what they want; the main agent turns it into verified, merged work and keeps the record. The process is the point, not the tools: any ticket system, review model, or agent CLI that can be reached will do, including a plain local file.

Use the guides as defaults. The user's own rules, kept wherever they like, **patch** them (section 1).

## 1. Resolve the user's configuration first

At the start of a session, and after the user changes a preference:

1. Run `python3 <skill-folder>/scripts/devloop.py resolve --project <project-root>` (read-only). Without a shell, follow the lookup order in [customization](guides/customization.md).
2. Read the result: the wish **inbox**, the **research store**, the **layout** (where each kind of file lives), the review and reflect settings, and the **instruction sources**.
3. Fetch every source marked `fetch_required` with whatever tool reaches it (Notion MCP, Drive, `aws s3 cp`, `curl`, `gh`). Local files are already inlined. If a source cannot be reached, say so and continue with defaults; do not invent its content.
4. Apply each source at the stages it names. `append` adds to the stage's default guide, `replace` overrides it, `skip` turns the stage off. The newest explicit user instruction beats every file.

No configuration means defaults plus a short setup conversation ([customization](guides/customization.md)): where wishes go, where research lives, which docs paths to use, who reviews, and **which spec, plan, review, TDD and worktree tools the user already uses** (ask; `devloop.py discover` lists what is installed as options). The user's habits win. This skill fixes the loop and its gates, not the tools ([tooling](guides/tooling.md)). Persist the answers before the first delegation. Configuration holds locators and preferences, never credentials.

A new session needs no re-teaching: tools, review rules, constraints, layout and language all live in the config. Session-start order is in [tooling](guides/tooling.md).

## 2. The loop

A picture is in [diagrams](guides/diagrams.md).

```
0 intent -> 1 record -> 2 design -> 3 design review -> 4 slice into lanes
   -> 5 implement -> 6 verify for real -> 7 code review -> 8 merge
   -> 9 deploy -> 10 close out -> 11 reflect (every 30 min) -> back to 0
```

Stage ids for patches: `intent record design design_review slice implement verify code_review merge deploy close_out reflect`. Details and exit gates are in [the loop](guides/loop.md). The shape:

- **Intent and record:** write the request in the owner's words into the inbox and the decision log before acting. A request that exists only in chat is lost at the next context compaction.
- **Design (when new or risky):** look at what exists first, then a plan with goal, non-goals, mechanism, failure modes, limits with numbers, lane breakdown with write sets, test plan. Note where it is weakest.
- **Review is configurable.** Which reviewer, how, how many rounds, and for which risk levels come from the config. See [review](guides/review.md).
- **Lanes:** one branch, one worktree (or shared tree when work is related), one owner, one explicit write set. Independent lanes start together; two writers never share files.
- **Implement:** tests first and watch them fail; for a safeguard, break it once on purpose (negative control).
- **Verify for real:** green tests are not "it works". Say what was not verified.
- **Merge and close out:** local merge, then update register, decisions, follow-ups, backlog and journal in the same session. Push, release and publication stay with the owner unless the config says otherwise.

## 3. Capture every request; one session, many tasks

The owner sends wishes and bugs in chat at any moment. **Before doing anything with a request, append it to the intake log** (verbatim words, kind, size), then triage: small fixes become *patches* in a plain list (no issue needed), big items become *lanes* (branch, worktree, register row, PR if the project uses them). Never lose earlier work to the newest request: the main session stays the coordinator, delegates the new item, and states what is still running. Full rules in [intake](guides/intake.md).


Keep one main session per project that owns all lanes. Delegate each task to a subagent or to another agent CLI (see [roles and briefs](guides/roles-and-briefs.md); choosing models is the job of the `model-routing` skill, which this skill defers to). Agents default to one task at a time; the main agent must start every independent lane at once and keep the queue full. A background count of one is a prompt to look for more parallel work.

## 4. Reflect every 30 minutes

A scheduled self-review stops requests from being lost. It re-reads the register, decision log, backlog index and follow-ups, lists running agents (flagging those silent for over an hour), finds what the owner said that is neither done nor registered, launches independent work, merges finished lanes, updates the files, and answers with one table plus what happens next. Prompt and table in [reflect](guides/reflect.md); set up the schedule with the harness's cron or scheduler.

## 5. Project layout

Tracked docs (`docs/decisions`, `plans`, intake log, `adr`, `backlog`, `research`, `handbook`, the register, review follow-ups, `.journal`) and untracked private material (`references/` possibly symlinked to a cloud drive, `artifacts/`, private tooling) have fixed roles. Paths are overridable. Run `python3 <skill-folder>/scripts/devloop.py scaffold --project <root> --dry-run`, then without `--dry-run`; it never overwrites. Conventions: [project layout](guides/project-layout.md).

## 6. End every reply with what happens next

Continuing, finished, blocked on what, or a choice with a recommendation. The owner should never have to ask "so what now?". Report outcomes faithfully, including what was not run.

## Guides

- [Diagrams](guides/diagrams.md): the loop, the roles and where files live, as Mermaid and ASCII.
- [Tooling](guides/tooling.md): stage contract, choosing the user's own spec/plan/review tools, session-start routine.
- [Intake](guides/intake.md): capture-before-acting, patch vs lane triage, board check, focus stack.
- [The loop](guides/loop.md): stages, entry/exit gates.
- [Project layout](guides/project-layout.md): where files go, tracked vs private, naming.
- [Roles and briefs](guides/roles-and-briefs.md): who does what, worker brief template, standing constraints.
- [Review](guides/review.md): configurable design and code review, round limit, findings handling.
- [Reflect](guides/reflect.md): the periodic self-review.
- [Customization](guides/customization.md): config file, instruction sources, stage patches, setup conversation.
- [Failure modes](guides/failure-modes.md): problems already seen and their fixes.
- Templates in `templates/`, a full config in `examples/config.full.json`.
