---
name: building-codebase-curriculum
description: >-
  Use when someone wants to learn, re-learn, or teach a codebase that already
  works but whose implementation they do not understand — a project written
  mostly by an AI agent whose author only knows the direction and not the
  mechanics, onboarding onto a large unfamiliar repo, or a request to turn a
  finished project into runnable step-by-step lessons, a tutorial, a curriculum,
  or "explain how this thing actually works" documentation that stays true to
  the real source.
---

# Building a curriculum out of a codebase that already works

A working codebase is the answer key. This turns it back into the exercise —
lessons that are **runnable**, and that quote the **real source** they teach.

**Core principle: a lesson is not done until its example has actually been run
and its real output pasted in.** Everything else in this skill exists to protect
that one rule from erosion under parallelism and time pressure.

**Second principle: the orchestrator verifies; it never trusts a subagent's
report.** Subagents reliably report success they did not achieve, and reliably
report failures that belong to someone else's file.

## Pick the mode first

| | **Reference mode** | **Reconstruction mode** |
|---|---|---|
| Question it answers | "What techniques does this codebase use, and why these?" | "How would I build this from nothing?" |
| Ordering axis | By topic; lessons are independent | By dependency; step N needs step N-1 |
| One unit is | A standalone runnable example + doc | A self-contained runnable checkpoint + doc showing the delta from the previous step |
| Fan-out | Full parallel — all lessons at once | **Pipelined in waves** (see below) |
| Best for | Mature repo, many distinct techniques | A system with a clear build-up story (a renderer, a compiler, a database, a protocol stack) |

Both modes run the same six phases. When both fit, ask the user — do not guess.

## The phases

### 0. Explore before proposing

Survey with cheap commands, not by reading everything: dependency manifests
aggregated across packages, lines of code per module, entry points, existing
docs/ADRs. You are looking for what is *teachable and unusual*, not a file
listing.

**Look for the fan-out points** — the places where one contract has N
implementations (one protocol, three frontends; one interface, four backends;
one plugin, three runtimes). Those are where the architecture's central bet
actually pays off, they are the hardest thing to reconstruct from reading alone,
and each one is a natural cluster of lessons. A curriculum organized around the
fan-outs teaches the design; one organized around directories teaches the
filesystem.

### 1. Propose, then get confirmation — mandatory

Present a candidate topic/step list with a one-line "why this one is worth a
lesson" each, and **stop for the user's decision**. Selection is where the
human's judgment is worth the most and yours is worth the least. Use
`AskUserQuestion` for: which topics, mode, where the curriculum lives, and
**what language the prose should be in** (often not English).

Never skip to writing because the list "seems obvious."

### 2. Scaffold — and prove the run command works BEFORE dispatching

Create the shared skeleton, then **actually run a hello-world through it**. If
fourteen agents are dispatched against a run command that turns out not to work,
you get fourteen broken lessons.

Detect the toolchain rather than assuming:

| Stack | Per-lesson unit | Run command |
|---|---|---|
| Rust | `examples/NN_slug.rs` in a workspace member | `cargo run -p <crate> --example NN_slug` |
| Node/TS | `steps/NN-slug/main.ts` in the workspace | `pnpm tsx steps/NN-slug/main.ts`, or a test runner |
| Python | `lessons/NN_slug.py` | `uv run lessons/NN_slug.py` |
| Go | `cmd/NN-slug/main.go` | `go run ./cmd/NN-slug` |

Pin every dependency the whole curriculum needs into the shared manifest **now**,
matching the versions the real repo already resolves. This is what makes rule
"no subagent edits the shared manifest" enforceable.

### 3. Write the contract file

Drop a `RULES.md` beside the curriculum: the exact doc section order, the
example constraints, the verbatim-quote-and-link format, the shared-file
prohibition, and the prose language. See `rules-template.md` in this skill
directory — adapt it, don't invent a new one.

This file is the reason independently written lessons read as one curriculum
instead of N unrelated tutorials. Every subagent is told to read it in full
first.

### 4. Dispatch

**Reference mode:** one subagent per lesson, all in parallel. Each brief is
self-contained and names: the files to create, 2–4 **real source anchors**
(`path:line`) to read first, what the example must demonstrate, and the exact
run command.

**Reconstruction mode:** do NOT fan out freely — step N+1's author must match
step N's actual code. Either pipeline it (each agent receives the finished
previous step), or write the full interface spec for every step up front and
fan out against that. Say which you did.

Derive step order from the **dependency structure, not git history**. The git
history of an AI-written project records "what got fixed when," which is not a
teaching order.

### 5. Verify yourself — the part that is always skipped

Re-run every example yourself. Run the crate/project-wide check yourself. Read
the docs against `RULES.md`. Only then report done.

## Failure modes seen in real runs

These are observed, not hypothetical — from a 14-lesson parallel build.

| What happens | Counter |
|---|---|
| Agent reports "the project-wide check fails" — it is someone else's half-written file | Tell agents to check **only their own target**; orchestrator owns the final full check |
| Agent wants a new dependency and edits the shared manifest mid-flight, breaking a sibling | Forbid it in `RULES.md`; agent must **report** the need instead |
| Agent writes plausible output instead of running the thing | The one rule to restate in every brief; verify by re-running |
| Agent codes against remembered API, not the pinned version (wrong module path, renamed item) | Brief says: verify against the locked version / vendored source, not memory |
| Agent trusts a paraphrased signature in its brief over the real code | State in the brief: **the real source is authority, the brief may be wrong** |
| Two agents pick the same lesson number | Numbers are assigned in the plan, never inferred from `ls` |
| Reconstruction step teaches a toy and implies it is the real thing | Each step doc lists what the teaching version **omits** (error handling, edge cases, perf) and links the production file |

## Red flags — stop

- About to dispatch without having run one example end-to-end yourself
- About to write lessons without the user confirming the topic list
- About to paste output you did not capture from a real run
- Reporting "all done" having only read subagent summaries
- Deriving reconstruction order from `git log`

## Keeping it alive

A curriculum built once rots into a snapshot. Leave behind a small
project-specific maintenance skill that says when a change deserves a new lesson
vs. an edit to an existing one, and re-states the "real captured output" rule.
