# Delegation ledger — moved out of this repo

The ledger lives in one shared store so all machines read and write the same rows.
See SKILL.md §5 for backends, schema, and first-run setup.

- Default: Notion database named **Model Routing Ledger** (look it up by name).
- Equivalent alternative: a Google Sheets spreadsheet with the same name and columns.
- Do NOT append rows to this file. Git history of this file preserves the old table.
