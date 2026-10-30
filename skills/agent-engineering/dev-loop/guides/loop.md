# The loop

Each stage lists what it takes in, what it does, and its exit gate. Skip a stage only when the exit gate is already true (a bug with a known cause needs no design). A user instruction source can patch any stage by id.

## intent
- **First action of the turn:** append the request to the intake log, one row per request ([intake](intake.md)). Triage it as patch, lane or question, and run the board check so nothing in flight is forgotten.
- **Do:** capture what was asked in the owner's words. Classify statements as fact, requirement, example, assumption or proposal. References and screenshots are evidence, not approval.
- **Exit:** every request in the message has an intake row with a non-`captured` status.

## record
- **Do:** append numbered owner decisions and the discussion that led to them to the decision log; add or update the lane in the register; add owed work to the backlog with *why it is waiting*.
- **Exit:** after a context compaction, reading the register alone tells you what is in flight.
- Memory is for durable rules about how to work, not for tasks. "I'll remember" means write a file.

## design
- **Do:** (1) look first: this tree, any predecessor or reference project (read-only), upstream; name the paths. Copy at the largest unit that works. (2) plan file: goal, non-goals, mechanism, data/wire shape, failure modes, limits with numbers, lane breakdown with write sets and machines, test plan, where the design is weakest. (3) ADR when a boundary, wire format, trust decision or default changes. (4) Mechanisms not built yet are still designed; "not thought about" is not acceptable.
- **Facts are your job, decisions are the owner's.** Read code and run experiments yourself; ask only about product behavior, public API, security or permission, licensing, destructive migration, data egress or cost. Batch questions with a recommended answer.
- **Exit:** no unresolved owner-only decision; delegated decisions are noted for the decision log.

## design_review
- **Do:** anything later work is written against (boundary, wire, security, phase plan) gets an independent review before it is built. See [review](review.md).
- **Exit:** latest verdict has no open P1; residual findings are in the follow-ups file.

## slice
- **Do:** one lane = one branch + worktree + owner + write set. Decide which lanes are independent and start them together; related tasks may share a worktree. Write the brief ([roles and briefs](roles-and-briefs.md)). Choose executor tiers via `model-routing`.
- **Exit:** every lane has a written brief and a disjoint or ordered write set; the register lists it.

## implement
- Tests first, watch them fail for the right reason, then pass. Negative control for safeguards: mutate the product code, the new test must fail, restore.
- Never branch on error message text; use typed codes. Close what you open on every exit path. Generated code is regenerated, never hand-merged.
- Journal entry before a major commit: what was considered and why it lost.
- A write outside the approved write set is a plan revision, not worker discretion: stop, report, widen deliberately, record it.

## verify
- Run the thing where it matters: real machines for hardware facts, real clicks for UI, real services only if the owner allowed it. Use a private state dir; never touch the owner's live data. State what was not verified.
- A self-written test passing is not evidence for a plan or for security work.

## code_review
- Review a coherent batch, not every patch. Risky and default-on changes get an independent reviewer; low-risk changes are verified and merged. See [review](review.md).
- **Round limit:** after the configured number of rounds (default 3) merge unless there is a P0 or a regression; write the residuals down.

## merge
- Local merge into the integration branch. Nothing is pushed, released or published until the owner says (unless config grants it). Re-read the log before any commit or amend, since other agents commit concurrently. Keep both sides when merging register, decision-log and follow-up files; renumber a colliding decision or ADR.
- After a risky merge, compile before the next lane builds on it.

## deploy
- Only as the config and owner allow. Record version ids and a rollback id. Verify built artifacts before copying them anywhere.

## close_out
- Same session: register (lane to merged), decision log, follow-ups, backlog rows with reasons, journal, ADR and plan result notes. Delete scratch and build output you made; remove finished worktrees, then check the main checkout is intact.

## reflect
- Every 30 minutes (configurable). See [reflect](reflect.md).
