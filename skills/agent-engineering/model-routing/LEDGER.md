# Ledger location

Experience belongs in the backend selected by persistent configuration, not in this pointer file. Read [SKILL.md](SKILL.md) and [state and storage](guides/state-and-storage.md).

Keep a ledger and a rules table. Google Sheets is the default for new users when available; Notion, documents, and local files are supported explicit choices. Never create a second store because an existing connection is unavailable.

Older tracked content is recoverable through Git history. Preserve uncommitted historical rows before replacing a legacy pointer or migrating a store.
