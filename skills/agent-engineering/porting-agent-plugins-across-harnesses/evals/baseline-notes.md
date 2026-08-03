# Baseline Notes: porting-agent-plugins-across-harnesses

## Eval 1

- Prompt summary: port OpenCode commands, skills, MCP config, and custom tool
- Missing or weak behavior: did not require clean-session acceptance tests for each adapter, did not explicitly refuse unsupported parity claims, and treated Claude Code/Codex mappings at a high level without requiring a capability matrix result per feature.
- Useful baseline behavior: recommended shared core plus thin adapters, command/skill/MCP/tool concept mapping, and MCP as a portability boundary.
- Expected improved behavior: require verified capability decisions per feature, explicit omissions for unsupported parity, and adapter-level clean-session tests.

## Eval 2

- Prompt summary: design OpenCode-first package for future Claude Code, Codex, and Gemini
- Missing or weak behavior: risked overbuilding a generic plugin runtime, did not emphasize starting with only core plus current adapter, and did not require negative tests for missing capabilities.
- Useful baseline behavior: recommended a portable runtime and host adapters with abstract capabilities; noted that core should not import host APIs and the OpenCode adapter should be built first.
- Expected improved behavior: start with portable core plus the current adapter, defer generic runtimes, and add negative tests for missing capabilities.
