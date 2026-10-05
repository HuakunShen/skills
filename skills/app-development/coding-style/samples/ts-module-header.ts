// Module-header comments are a hard convention: every source file starts with "what this file owns and where it sits in the architecture",
// in English only, explaining only what the code cannot express.
// From refyard/packages/git-core/src/ports.ts:1-13 (read 2026-10-05, start of file)
/**
 * The private host interface that portable core is allowed to use.
 *
 * This file is the whole point of the architecture: core plans Git commands and
 * parses their output, but it cannot spawn, read, encode, time or cancel anything
 * itself. Those arrive through `GitHostPort`, which only the trusted Node host
 * implements. Nothing here is a public JSON schema — a browser never sees a
 * `GitCommandSpec`, an argv vector, a working directory or an environment.
 */
import type { ObjectFormat } from "@refyard/git-contract";

// ❌ Counterexample (constructed, not repository code): a header comment restating the next line of code - zero information
// // This file imports the ids module and re-export makeId.
// - real files never carry restating header comments; write only what the code cannot express.
