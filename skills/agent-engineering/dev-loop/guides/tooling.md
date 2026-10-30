# Tooling: the workflow is fixed, the tools are the user's

This skill defines **what each stage must produce and when it may exit**. It does not choose the spec, plan, review or TDD tool. The user's habits win: if they already use OpenSpec, superpowers, spec-kit, a Notion template or plain markdown, that tool does the stage and this skill supplies the surrounding loop, the records and the gates.

## Stage contract (tool-agnostic)

| Stage | Must produce | Exit gate | Typical tools (examples only) |
|---|---|---|---|
| intent | Intake row per request | No row left at `captured` | any |
| design | Spec or design with goal, non-goals, mechanism, failure modes, limits, weakest point | Owner-only decisions resolved | OpenSpec, spec-kit, superpowers brainstorming, plain `docs/plans` |
| plan (inside design/slice) | Executable plan: tasks, write sets, tests, order | A fresh executor could run it verbatim | superpowers writing-plans, OpenSpec tasks, plain markdown |
| design_review | Independent verdict + findings handled | No open P1 | codex/other CLI, review skill, another model |
| slice | Lanes with briefs and disjoint write sets | Register updated | worktree skill, `git worktree`, a multiplexer |
| implement | Commits on the lane branch with RED/GREEN log | Negative control shown | TDD skill, executing-plans, any agent CLI |
| verify | Evidence of real behavior + not-run list | Claims match evidence | project test commands |
| code_review | Verdict + findings handled | No open P0/P1 or round limit reached | as design_review |
| merge / close_out | Merged branch, updated records | Register, decisions, follow-ups current | git, gh |

A tool fits a stage when it produces the stage's artifact and respects its gate. If a tool's own workflow adds steps (for example OpenSpec's propose/apply/archive), keep them; map them onto the contract and record the mapping in `stage_tools`.

## Choosing, never imposing

1. **Ask first.** During setup, and whenever a stage has no tool yet, ask: "Which spec or plan system do you use for designs? Which for review? Any TDD or worktree helper?" Accept "none, plain markdown".
2. **Look, then confirm.** `python3 <skill-folder>/scripts/devloop.py discover` lists installed skills and CLIs whose names suggest a spec, plan, review, TDD, worktree or orchestration role, plus common CLIs on PATH. It is detection by name only. Present what you found as options; the user picks. Do not adopt a tool because it happens to be installed, and never uninstall or reconfigure one.
3. **Record the choice** in `stage_tools` so no future session has to ask:

```json
"stage_tools": {
  "design":        {"kind": "cli",   "name": "openspec", "notes": "propose -> apply -> archive; change store at .repo-local/..."},
  "plan":          {"kind": "skill", "name": "superpowers:writing-plans"},
  "design_review": {"kind": "cli",   "name": "codex", "notes": "read-only, high effort"},
  "implement":     {"kind": "skill", "name": "superpowers:test-driven-development"}
}
```

   `kind` is free (`skill`, `cli`, `mcp`, `doc`, `manual`); `name` is how to invoke it; `notes` carries the approval, storage or command details. Anything longer goes in an instruction source.
4. **Use the tool, keep the records.** The tool's artifacts live where the tool puts them; the register, intake log and decision log still point to them (a plan path, a change id, an approval id). Repo-side files stay the way a new session finds its bearings.
5. **If the chosen tool is missing** on this machine, say so and fall back to plain markdown plans for that stage. Do not silently switch tools.

## A new session must not need re-teaching

At the start of every session the orchestrator does this, in order:

1. `devloop.py resolve` and fetch remote instruction sources ([customization](customization.md)).
2. Read the register, the intake log (non-terminal rows), the decision log tail and the follow-ups.
3. Read `stage_tools`; if a stage that is about to run has none, ask once and save.
4. State the board in a few lines: what is running, what is owed, what is next.

Everything the user would otherwise explain again (tools, review rules, constraints, layout, language) lives in the config and its instruction sources. When the user teaches a new habit in chat, write it to the config or the right source before continuing.
