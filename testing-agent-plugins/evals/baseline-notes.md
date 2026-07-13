# Baseline Notes: testing-agent-plugins

## Eval 1

- Prompt summary: tests for command, custom tool, shell.env hook, and message transform
- Missing or weak behavior:
- Did not require isolated temp config homes or isolated temp config directories.
- Did not explicitly mark real harness tests as optional.
- Did not mention marker strings for discovery.
- Did not include static audits for forbidden patterns.
- Useful baseline behavior:
- Covered config/tool/shell.env/message-transform unit tests, discovery, integration, and safety tests.

## Eval 2

- Prompt summary: tests for background-agent orchestration plugin
- Missing or weak behavior:
- Did not explicitly require FIFO or concurrency slot release tests.
- Did not require atomic locks for team-style claims.
- Did not include mailbox ack, broadcast, or payload-limit tests.
- Did not require spawn limits.
- Did not cover duplicate notification races across idle, error, and completion edges.
- Useful baseline behavior:
- Covered lifecycle transitions, cancellation races, retry policy, parent notification assertions, claim conflicts, chaos tests, and E2E scenarios.
