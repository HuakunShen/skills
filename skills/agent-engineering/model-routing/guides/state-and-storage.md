# State and storage

## Deterministic discovery

The helper `scripts/state.py` reads JSON configuration without writing or contacting a service. Selection precedence is:

1. `--config <path>`, otherwise `MODEL_ROUTING_CONFIG`.
2. Nearest `.model-routing/config.json` at/above the requested project root.
3. `${XDG_CONFIG_HOME:-~/.config}/model-routing/config.json`.
4. `<skill-folder>/.local/config.json`.

An explicit missing/invalid path is an error, never permission to fall back. With no configuration the helper returns `configured: false`; ask only for information needed to bootstrap the chosen backend. Do not create a second cloud store before looking for an existing selection.

The highest-priority configuration chooses storage as one unit. The helper returns policy layers from existing lower-priority configurations as well, so a project store does not hide the user's bans or budgets. Read them before dispatch; hard bans/data restrictions are cumulative unless the user explicitly changes them. Resolve contradictory explicit policies with the user. Policy-file paths are relative to their configuration file.

Example (illustrative; do not use the example IDs):

```json
{
  "version": 1,
  "scope": "user",
  "storage": {
    "backend": "google_sheets",
    "ledger": {"uri": "https://docs.google.com/spreadsheets/d/EXAMPLE_ID/edit", "table": "Model Routing Ledger"},
    "rules": {"uri": "https://docs.google.com/spreadsheets/d/EXAMPLE_ID/edit", "table": "Model Routing Rules"}
  },
  "policy": {
    "free_first": true,
    "denied_models": [],
    "preferred_tools": [],
    "exploration": {"enabled": true, "fraction": 0.2, "extra_cost_usd": 0, "risk": ["low"]}
  },
  "policy_files": []
}
```

Initialize only a user-selected path, without overwriting an existing configuration:

```bash
python3 <skill-folder>/scripts/state.py init --output <path> --backend google_sheets \
  --ledger-uri <sheet-url> --ledger-table "Model Routing Ledger" \
  --rules-uri <sheet-url> --rules-table "Model Routing Rules"
```

Stable resource IDs/URLs belong in user state. Keep provider credentials in the tool's credential store. Record the model/tool IDs the user permits in policy only when needed; discover currently available candidates separately.

## Portability and scope

- **Multiple tools on one machine:** point them at the same user config or `MODEL_ROUTING_CONFIG`. A shared installed skill folder can also share its ignored local file.
- **Multiple devices:** sync the config, and use a shared remote data store or synchronized local data. An ignored file is not transported by Git; it is not a synchronization mechanism.
- **Project-specific learning:** use project configuration and record project/domain scope in rules. It may deliberately reference a separate project ledger; do not confuse it with the global ledger.
- **Skill reinstall/copy:** user config survives upgrades better than files under a replaceable installation. Treat skill-local state as optional convenience, not the only recovery source.

## Backend contract

Keep two logical collections with the schemas in [data schema](data-schema.md). The adapter needs: locate, read relevant rows, append idempotently, supersede rules, and verify writes. Use existing MCPs, connectors, APIs, or filesystem tools; no particular vendor is mandatory.

| Backend | Locators and access |
|---|---|
| Google Sheets (default) | File `Model Routing`; ledger and rules tabs. Cache its stable URL/ID in state; validate title, tab names and headers before writing. |
| Notion | Separate ledger/rules database or data-source URLs/IDs. Use bounded filtered queries. Respect service and connector quotas; honor retry-after on throttling and report a persistent access limit. |
| Google Docs / other documents | Explicit document and two structured sections/tables. Keep stable record IDs; use supported revision/concurrency controls before replacing content. |
| Google Drive | Drive is the container: specify the actual Sheet, Doc, CSV, JSONL, or other file plus its parser and write mechanism. |
| Local files | Two CSV/JSONL files or two SQLite tables at explicit paths. Lock/serialize writes and replace atomically when rewriting a file. |
| Other store | Record a concrete locator and available adapter. Confirm the operations above work before relying on it. |

For remote stores, remind the user to ensure **every intended AI tool** has the necessary read/write MCP, connector, or API access. One tool's connector is not automatically portable. Verify current official/community MCP availability at setup rather than baking a changing claim about a vendor into the skill.

For local storage, remind the user about multi-device synchronization and concurrent-write conflicts. A single computer can keep the files locally or inside its project. Multiple computers need one synchronized location or an explicitly managed sync process.

## Migrating an existing store

Select one canonical backend. Preserve originals, copy both tables, reconcile headers/counts/sample records and dates, then update configuration after successful reads. Keep legacy backup locators labeled as backups. Do not dual-write or switch because a service is temporarily unavailable. Resolve an actual missing/deleted target before creating a replacement.
