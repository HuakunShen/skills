# `RULES.md` template

Copy this into the curriculum directory of the target repo and fill in the
`<angle brackets>`. Every subagent is instructed to read it in full before
writing anything. Delete the sections that genuinely do not apply — but delete
them deliberately, not by forgetting.

---

```markdown
# Rules for adding or updating a <lesson|step>

This file is the contract every <lesson|step> follows. It exists so that
independently written units read as one curriculum instead of N tutorials
stapled together.

## What one unit is

One <lesson|step> = exactly these deliverables, numbered `NN` (two digits,
matching the table in `README.md`):

- `<examples/NN_slug.ext>` — a runnable, self-contained entry point.
  `<RUN COMMAND>` must finish on its own — no external service, no real network
  call, no waiting on a human — and print output that *demonstrates* the
  concept, not just that it compiled.
- `<docs/NN-slug.md>` — the doc, in the fixed structure below.
- Anything only this unit needs. If two units would need the same *new* shared
  file, that is a sign it belongs in the scaffold — do not let two units fight
  over one file.

The slug must be identical between the example and the doc filenames, and must
match the slug already used for that number in `README.md`. Never invent a new
number; a genuinely new topic takes the next unused one.

## Doc structure

Every doc has these sections, in this order. Do not skip one; write
"N/A — because X" if it truly does not apply.

### `## Why` (why this exists)

2-4 sentences: the general problem this solves, and *specifically* why this
project needs it. Not "this is a popular library" — the actual failure mode it
avoids here. Ground it in something real: a source comment, an ADR, a bug it
prevents.

### `## Why this <library|approach>, and not the standard one`

Required whenever the subject is a third-party dependency. Name at least one
concrete alternative **by name** and say what it specifically cannot do, or what
it costs to get right by hand. Vague ("more popular") is unacceptable; concrete
("it has no async-aware API, so calling it from a task would block the whole
worker thread") is. If the project's own source explains the choice in a
comment, quote it.

### `## How <PROJECT> uses it`

1-3 short snippets (≤20 lines each), **copied verbatim** from the real
repository — never paraphrased, never retyped from memory — each followed by a
link to its source in this exact form:

`[path/to/file.ext:45](<RELATIVE PREFIX>path/to/file.ext#L45)`

For a range, link the first line and give the range in prose.

### `## Trade-offs`

3-5 bullets, concrete. Not "flexible" or "powerful." What it costs (build time,
indirection, one more concept to hold, a footgun) and what it buys back.

### `## Run it`

The exact command, followed by **real, captured** output. Run it yourself before
writing this section. Never invent plausible-looking output. Trim long output to
a representative 5-20 lines and say that you trimmed it.

### `## Sources`

Every repository file referenced anywhere in the doc, as links. The "go read the
real thing" list.

### `## Also worth knowing` (optional)

Cut it if empty. Only for a genuine gotcha or a trade-off the maintainers
recorded that is too tangential for `Why` but too important to drop.

## Reconstruction mode — two extra required sections

### `## What changed since step NN-1`

The delta, as a diff or a precise prose description. A reader who did the
previous step must be able to see exactly what this step adds.

### `## What this step leaves out`

What the real implementation does that this teaching version does not — error
handling, edge cases, performance work, platform quirks — with a link to the
production file. Without this, a reader finishes believing they understand
something they have only seen a toy version of.

## Example code

- Heavily commented and teaching-oriented. Assume a competent programmer who is
  new to *this* codebase, not new to programming.
- Self-contained: does not import another unit's example.
- Mirrors the real project's naming and shapes rather than generic tutorial
  boilerplate. An error type here should look like the project's real error
  types, not a textbook `MyError`.
- No network beyond loopback, no dependency on a running external service, no
  manual interaction.
- **Verify by actually running it**, and paste the real output into `Run it`. A
  unit is not done until this has been run once by whoever wrote it.

## Shared files — do not edit

`<list the scaffold files: manifest, build config, shared entry, README>` are
shared scaffolding, already populated with every dependency the whole curriculum
needs, pinned to the versions this repository already resolves.

Do not add a dependency or edit these to solve one unit's problem. If you
genuinely believe something is missing, **say so in your report instead of
editing** — these files are written in parallel by other agents, and a silent
edit can break a sibling unit.

## Verify only your own unit

Run the check for *your* target only. A project-wide check may fail because
another unit is mid-write; that is not your failure to fix or report as broken.
The orchestrator owns the final project-wide verification.

## The real source is the authority

If your brief paraphrases a signature, a type, or a flow and the real code
disagrees, **the real code wins** — and say so in your report. Likewise, code
against the *pinned* version of a dependency (check the lockfile or the vendored
source), not against the API you remember.

## Language

Doc prose is <LANGUAGE>. Code and code comments are <LANGUAGE>, matching this
repository's own convention.
```
