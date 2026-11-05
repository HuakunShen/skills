# Subscription Quota and Rate Limit Windows

## Micro Task Tokens vs Macro Subscription Quota

Model routing operates across two distinct dimensions of cost and capacity:

1. **Task Token Receipt (Micro):** How many input, cache-read, reasoning, and output tokens a single delegated task consumed. Measured per session via `usage.py` and logged in `ledger.jsonl`.
2. **Subscription Quota & Rate Limits (Macro):** How much of the user's rolling 5-hour and 7-day/weekly quota pools remain before the account is throttled or hard-capped. Measured via `quota.py`.

Knowing subscription capacity allows an orchestrator to make optimal pool routing decisions before assigning work.

---

## 1. Provider Quota Discovery Mechanisms

Rather than parsing browser sessions or reverse-engineering web cookies, modern harnesses expose structured CLI/server interfaces that query their provider using existing logged-in credentials.

### Antigravity (`agy`)
* **Mechanism:** Direct CLI query with JSON output.
* **Command:**
  ```sh
  agy -p "/usage" --output-format json
  ```
* **Quota Pool Structure:**
  Antigravity divides quota into independent pools:
  - **Gemini Models:** Shares a weekly limit and a 5-hour limit across Gemini Flash and Gemini Pro.
  - **Claude and GPT models:** Shares a weekly limit and a 5-hour limit across Claude Opus, Claude Sonnet, and GPT-OSS.
  - **Gemini 4 Argon:** Dedicated weekly limit for Argon models.
* **Orchestrator Advantage:**
  Because the Gemini pool and the 3P (Claude + GPT) pool are completely separate, an orchestrator can fail over between pools seamlessly: when the Gemini 5-hour limit approaches exhaustion, switch to Claude/GPT models (or vice versa), without waiting for the reset window.

### OpenAI Codex (`codex`)
* **Mechanism:** Local App Server JSON-RPC communication (patterned after `vorssaint/vorssaint-utils`).
* **Command:**
  ```sh
  codex -c features.plugins=false app-server
  ```
* **Protocol:**
  1. Stdin handshake:
     ```json
     {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "model-routing", "title": "Model Routing", "version": "1.0.0"}, "capabilities": null}}
     {"method": "initialized", "params": {}}
     ```
  2. Query rate limits:
     ```json
     {"id": 2, "method": "account/rateLimits/read", "params": {}}
     ```
* **Response structure:**
  `rateLimitsByLimitId.codex.primary` and `secondary` contain `usedPercent`, `windowDurationMins`, and `resetsAt`.
  - Window type is identified by `windowDurationMins` (e.g. `300` = 5h, `10080` = 7d).
  - Multi-account inspection is supported by passing `CODEX_HOME=<path>`.

### Anthropic Claude Code (`claude`)
* **Mechanism:** CLI internal control protocol (patterned after `vorssaint/vorssaint-utils`).
* **Command:**
  ```sh
  claude --print --input-format stream-json --output-format stream-json --verbose \
    --no-session-persistence --tools "" --strict-mcp-config \
    --mcp-config '{"mcpServers":{}}' --setting-sources "" --settings '{"disableAllHooks":true}'
  ```
* **Protocol:**
  Send control requests over stdin:
  ```json
  {"type": "control_request", "request_id": "initialize", "request": {"subtype": "initialize"}}
  {"type": "control_request", "request_id": "usage", "request": {"subtype": "get_usage", "skip_behaviors": true}}
  ```
* **Response structure:**
  `rate_limits` contains:
  - `five_hour`: 5-hour rolling limit (`utilization`, `resets_at`).
  - `seven_day`: 7-day total limit.
  - `seven_day_opus`: Dedicated Opus weekly limit.
  - `seven_day_sonnet`: Dedicated Sonnet weekly limit.
* **Local Fallback:**
  If the CLI is offline or unauthenticated, read the local sampling file on macOS:
  `~/Library/Application Support/Claude/plan-usage-history.json` (`u.fh` for 5h, `u.sd` for 7d, `u.so` for Opus, `u.sn` for Sonnet).
* **Multi-Account:**
  Controlled via `CLAUDE_CONFIG_DIR=<path>`.

---

## 2. Standardized `QuotaWindow` Data Schema

All provider outputs are normalized by `scripts/quota.py` into a uniform schema:

| Field | Type | Description |
|---|---|---|
| `provider` | string | `"antigravity" \| "codex" \| "claude"` |
| `account_id` | string \| null | Account profile identifier or config directory name |
| `model_group` | string | Model pool name (e.g. `"Gemini Models"`, `"Claude and GPT models"`, `"codex"`) |
| `window_name` | string | Human-readable label (e.g. `"Five Hour Limit Remaining"`) |
| `window_id` | string | Normalized identifier (`"5h"`, `"weekly"`, `"seven_day_opus"`) |
| `window_minutes` | int \| null | Duration of window in minutes (300 for 5h, 10080 for 7d) |
| `used_percent` | float | Percentage of limit consumed (0.0 to 100.0) |
| `remaining_percent` | float | Percentage of limit remaining (100.0 - used_percent) |
| `resets_at` | string \| null | ISO 8601 UTC timestamp of window reset |
| `observed_at` | string | ISO 8601 UTC timestamp when receipt was captured |
| `source` | string | `"cli" \| "local_file"` |

---

## 3. CLI Quota Helper (`scripts/quota.py`)

`scripts/quota.py` runs with Python standard library only:

```sh
# Query Antigravity live quota
python3 <skill>/scripts/quota.py agy

# Query Codex rate limits (optionally for a specific account directory)
python3 <skill>/scripts/quota.py codex [--codex-home ~/.codex-work]

# Query Claude Code rate limits (with automatic fallback to local history)
python3 <skill>/scripts/quota.py claude [--claude-config-dir ~/.claude-personal]

# Query all installed providers and print a formatted summary table
python3 <skill>/scripts/quota.py all --format table
```

Example table output:
```text
Provider    | Group / Account | Window          | Used % | Remaining % | Resets At            | Source
------------+-----------------+-----------------+--------+-------------+----------------------+-------
antigravity | Gemini Models   | Five Hour Limit | 1.32%  | 98.68%      | 2026-11-06T00:05:58Z | cli   
antigravity | Claude and GPT  | Five Hour Limit | 0.0%   | 100.0%      | 2026-11-06T00:30:12Z | cli   
codex       | codex (work)    | Primary (5h)    | 15.4%  | 84.6%       | 2026-11-06T00:00:00Z | cli   
claude      | claude          | Five Hour Limit | 22.5%  | 77.5%       | 2026-11-06T00:30:00Z | cli   
```

---

## 4. Orchestrator Routing Strategy

1. **Pre-Dispatch Pool Inspection:**
   Before scheduling a batch of tasks or assigning a long-running execution lane, inspect remaining 5-hour and weekly capacity across active providers.
2. **Dual-Pool Antigravity Switching:**
   In Antigravity sessions, when `Gemini Models` 5-hour limit drops below 10%, route non-Gemini tasks to `Claude and GPT models` pool (or vice versa) to sustain uninterrupted throughput.
3. **Multi-Account Quota Rotation:**
   When Codex or Claude personal quota reaches a threshold, target alternate accounts via `CODEX_HOME` or `CLAUDE_CONFIG_DIR`.
4. **Free Tier Offloading:**
   When paid/subscription pools approach 5-hour limits, divert mechanical, test-running, or non-sensitive implementation tasks to zero-retention free models (e.g. OpenCode DeepSeek / GLM) with automatic IP rotation.
