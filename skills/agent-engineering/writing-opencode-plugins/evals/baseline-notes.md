# Baseline Notes: writing-opencode-plugins

## Eval 1

- Prompt summary: custom tool wraps shell script and injects env vars
- Missing or weak behavior: The no-skill baseline used `node:child_process` spawn instead of OpenCode/Bun shell patterns from docs, omitted optional isolated `opencode run --print-logs --format json` integration tests, did not discuss source authority or observed third-party patterns, and only lightly covered secret handling.
- Useful baseline behavior: The no-skill baseline produced a plausible plugin with `@opencode-ai/plugin`, `tool.schema`, `shell.env`, and JSON output.

## Eval 2

- Prompt summary: risky message transform and direct promptAsync review
- Missing or weak behavior: The no-skill baseline did not prefer file/config primitives before transforms, did not mention shared dispatch gate patterns from observed third-party implementations, did not separate official docs from observed plugin internals, and did not call out testing requirements for duplicate injection.
- Useful baseline behavior: The no-skill baseline warned against experimental transforms and direct `promptAsync`, recommended guards/idempotency, and suggested `chat.message` or `event` hooks.
