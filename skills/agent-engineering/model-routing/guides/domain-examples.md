# Domain examples

These are starting categories and acceptance checks, not fixed model assignments. Introduce new domains for the user's actual work and keep labels consistent enough to query later.

| Domain / task kind | Useful acceptance evidence | Sensible bounded trial |
|---|---|---|
| Frontend / UI implementation | Browser interaction, responsive layout, accessibility, visual comparison | One component against an existing design/contract |
| Backend / API implementation | Contract checks, failure paths, authorization, persistence | One endpoint with explicit invariants and fixtures |
| Full-stack / integration | End-to-end user flow plus server/data contracts | A thin vertical slice with a rollback path |
| System design / architecture | Concurrency, lifecycle, failure modes, tradeoffs and independent review | One bounded design alternative, not an entire production rewrite |
| Research / synthesis | Primary-source support, date/coverage, accurate attribution | One source-backed subsection |
| Data / analysis | Grain, missingness, reconciliation, reproducible calculations | One dataset slice with known checks |
| Video / storyboard and edit | Narrative clarity, source accuracy, timing, audio/visual sync, rendered-frame review | One 20–40 second scene |
| Audio / narration | Pronunciation, pacing, intelligibility, source fidelity | Intro and one dense paragraph before a batch |
| 3D / modeling | Silhouette, topology, UVs, scale, render/export requirements | One prop under a polygon/material budget |
| Writing / translation | Audience, tone, terminology, meaning and factual consistency | One representative passage |
| Mechanical / repository changes | Exact scope, repeated transformation consistency, relevant checks | A small representative set before a bulk edit |

For a domain the orchestrator cannot judge directly, define acceptance with the user or a qualified reviewer. Do not turn confidence in code review into assumed expertise in medicine, 3D art, accounting, or another field.
