# Delegation briefs

Adapt to the task and tool. Supply the context the worker can actually access; a worker in another harness may not inherit the orchestrator's instructions or credentials.

## Execution

```text
Task: <one bounded outcome>
Inputs: <accessible sources, artifacts, or workspace>
Scope: <what may be changed and what needs a decision>
Size before execution: <S/M/L + concrete scope basis; complexity/risk separately>
Acceptance: <observable checks and expected result>
Constraints: <user policy relevant to this task, data limits, budget, deadline>
Report: artifact/location; checks actually performed; outcome; deviations;
        elapsed time, exact session/turn ID and measured token buckets/source;
        rework rounds; unresolved issues.
For a resumed worker: capture usage before/after this assignment; report the delta.
```

For code, include repository/worktree identity and applicable checks. For writing, include audience, factual sources and editorial criteria. For visual work, include dimensions/style and concrete review criteria. For a remote worker, pass the required policy explicitly.

## Independent review

```text
Review <artifact> against <acceptance criteria>.
Context: <requirements, known constraints, prior evidence>.
Reproduce or substantiate actionable issues. Distinguish verified findings,
uncertainty, and environment limits. Return a verdict, evidence locations,
and the smallest useful correction. Do not edit unless authorized.
```

## Bounded exploration

```text
Candidate trial: <model/provider/tool/effort>.
Comparable task class: <domain, task kind, size, risk>.
Allowed inputs/actions: <scope and data permissions>.
Budget/stop: <time, usage/cost, attempts>.
Acceptance: <same standard as the established route>.
Capture: model identity, output, verified outcome, rework, measured time/usage.
Fallback: <proven route if the bounded trial does not pass>.
```

Follow the installed tool's documented foreground/background and resume APIs. Never reuse a session solely because it is the newest in a global list. Preserve exact session IDs and workspace ownership. Avoid command generation through unescaped string interpolation; use argv or safe quoting.
