# Review

How review works is configuration, not doctrine. The config's `review` block and any `design_review` / `code_review` instruction sources decide the rest.

## What the config can say

```json
"review": {
  "design": {"when": "new or risky design", "tool": "codex", "model": "<reviewer model>",
             "effort": "high", "command": ["codex","exec","-s","read-only","-m","{model}","-"],
             "prompt_file": "prompts/design-review.md"},
  "code":   {"when": "security, lifecycle, default-on, new auth surface", "tool": "...", "model": "..."},
  "round_limit": 3,
  "reviewer_may_edit": false
}
```

Everything is optional. Missing `tool` and `model` means: ask the user once, or use the strongest available model in a *fresh* context (not the one that wrote the work). Commands are argv lists with `{model}`, `{prompt}`, `{out}` placeholders; never build them by string interpolation. An instruction source can hold the whole reviewer procedure instead.

## Defaults when the user says nothing

1. **Independence.** The reviewer is not the author's session. Prefer a different model or tool.
2. **When.** Design review before anything later is built on a boundary, wire format, trust decision or phase plan. Code review for a coherent batch with security, lifecycle, default-on or new-auth surface. Low-risk changes: verify and merge.
3. **Prompt.** Name the commit range or plan, the files, the threat model or constraints, what is already settled by the owner, what you want judged, and "do not endorse a recommendation just because an earlier round made it". The reviewer must be able to read the tree.
4. **Verdict format.** PASS / PASS WITH FIXES / FAIL with P0-P3 findings, each with file:line and evidence.
5. **Handling findings.** Verify each at file:line yourself. Fix P0/P1. Record P2+ in the follow-ups file. A fix touching two sections gets its own check, since defects hide in the composition.
6. **Round limit.** After the limit, merge unless there is a P0 or regression; write residuals down. Re-review a fix only when it changes a security, permission or lifecycle claim.
7. **Output is evidence.** Keep every review output file; run long reviews detached with output in the scratch root and retry if the reviewer is at capacity.
8. **Audit the reviewer occasionally.** Write a short research note on which findings held up; tune rounds and scope from it.

## Plans

A plan meant for a cheaper executor should be executable verbatim: facts tied to files read at a named commit, tests with expected failures, exact code or verified find/replace anchors, negative controls, exact write-set block, a verified/unverified section, and a review-rounds table mapping each finding to its change. Reviewers check executability (anchors exist, signatures match, write sets disjoint, controls prove the stated property).
