# Baseline Notes: injecting-agent-behavior

## Eval 1

- Prompt summary: package commands, skills, and a review subagent
- Missing or weak behavior: Recommended project-scoped config and valid skill frontmatter, but used `prompt` where OpenCode command config expects `template`, did not distinguish config `template` from markdown command bodies, used a singular `.opencode/agent/review.md` path instead of documented `.opencode/agents/`, did not explain `subtask` as the command-level option for forcing a subagent invocation, and showed a valid skill example without calling out that skill `name` must match the directory and use lowercase hyphen separators.
- Useful baseline behavior: Identified the right packaging primitives for commands, skills, and a review subagent, kept behavior project-scoped, and used `$ARGUMENTS` usefully for command argument handling.

## Eval 2

- Prompt summary: choose between commands, skills.paths, instructions, and transforms
- Missing or weak behavior: Did not discuss command, skill, and agent priority tests; did not mention idempotency tests for transforms; and treated `config.instructions` as available without clearly labeling it as observed/plugin-config behavior rather than a core file-based primitive.
- Useful baseline behavior: Correctly separated `instructions` for always-on context, `skills.paths` for discoverable skills, commands for opt-in workflows, and `chat.message` for dynamic injection.
