# Project layout

Paths below are defaults; the config's `layout` map overrides any of them. `devloop.py scaffold` creates them and never overwrites.

```
<repo>/
  docs/
    decisions/   YYYY-MM-DD-<slug>.md   numbered owner decisions plus the discussion behind them
    plans/       YYYY-MM-DD-<slug>.md   goal, mechanism, lanes, tests
    plans/WORK-REGISTER.md              lanes in flight, focus stack, owed work, recently merged, versions in production
    plans/INTAKE.md                     every owner request, one row each, with status; append-only
    adr/         NNNN-<slug>.md         architecture decisions; 0000-about-decision-records.md is the index
    backlog/     INDEX.md, PATCHES.md   owed work with why it is waiting; PATCHES.md is the plain list of small fixes
    research/    YYYY-MM-DD-<slug>.md   evidence: audits, experiments, review-finding audits
    handbook/    NN-<topic>.md          stable how-it-works pages; the development loop page for this repo
    review-followups.md                 P2+ findings and residuals from reviews
  .journal/      YYYY-MM-DD-HHMM.md     what was considered and why it lost; written before major commits
  references/    NOT TRACKED            reference material; may be a symlink to a cloud drive folder
  artifacts/     NOT TRACKED            build outputs, captures, evidence too big or private for git
  .repo-local/   NOT TRACKED            private tooling, approvals, private plan stores
```

## What goes where

| Kind | Home | Why |
|---|---|---|
| Wishes, expectations, "make this later" | the **inbox** (Notion DB, GitHub Projects, or `docs/backlog/INDEX.md`) | The owner adds them from any chat; it decides what happens next. |
| Discussions, concept pictures, long research | the **research store** (cloud drive folder, usually reached through `references/`) | Big and private; does not belong in git. |
| What was decided, and why | `docs/decisions/` | Append-only, numbered; survives compaction. |
| How we will build it | `docs/plans/`, `docs/adr/` | Written before building; reviewed. |
| Every request the owner made in chat | `INTAKE.md` | Captured before acting; nothing is forgotten. |
| What is happening now | `WORK-REGISTER.md` | Read first after any compaction. |
| Evidence a claim rests on | `docs/research/` (public-safe) or `references/` (private) | Research is evidence, not authority; owner decisions are authority. |
| Residual risk | `review-followups.md` | P2+ and round-limit leftovers. |
| Durable rules for how to work | agent memory or the instruction sources | Not task state. |

## Rules

- **Private material stays out of git.** `references/`, `artifacts/` and private tooling are ignored. Tracked plans are public-safe: no personal absolute paths, no research text copied from private sources.
- **Decision log and register are append-friendly.** On merge conflict keep both sides. Number decisions consecutively; take max+1 right before committing.
- **Scratch is not in the repo.** Use one scratch root outside the working tree (per-lane subfolders), never the system temp dir if the user has set another. Move useful evidence to a durable private folder, since scratch volumes get wiped.
- **A ticket system is a mirror, not the truth.** The inbox holds wishes; once accepted, the register and decision log are the working record. Mirror status back to the inbox if the owner wants to see it there.
- **A GitHub Projects or issue tracker is an equally good inbox.** Nothing in the loop depends on Notion. Configure `inbox.kind` and let the agent use the matching connector or CLI.
