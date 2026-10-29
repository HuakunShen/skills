# Interactive setup

Use this for a new user, a missing configuration, or an explicit setup change. The conversation should help the user choose; do not make them understand the schema or edit JSON. Existing state and answers already given in the conversation count as answers. Reuse them and ask only about actual gaps.

Use the host's structured question UI when available, otherwise a compact conversational question. Group two or three related questions per round, allow free text, and explain the consequence of each choice. Do not present a long questionnaire. Start with the few questions that affect the decision; follow up only when an answer exposes a real dependency.

## 1. Where should this user's experience live?

Example prompts, adapted to what is already known:

- **Where do you want to keep the two tables?** Recommend Google Sheets for shared cloud access; offer Notion, local files, or an existing document/store. Ask for an existing resource before creating a new one.
- **Who should share the experience?** All AI tools/projects for this user, only this project, or another explicit scope. Ask whether the user works on one device or several if that changes the storage recommendation.

Explain the relevant tradeoff alongside the choice:

- For Sheets/Notion/another cloud store, every intended AI tool needs authorized read/write access through its own supported MCP, connector, or API. Verify current access instead of promising a vendor-wide MCP. One connected tool does not connect all the others.
- For local files, one computer is straightforward; multiple devices need deliberate synchronization and serialized writes. An ignored skill-local file will not sync through Git.
- For configuration, prefer a shared user config across tools or a project config for project-specific learning. Offer the ignored skill-local file as a convenient alternative and explain reinstall/sync limits.

Do not decide only from the default. If the user mainly uses a tool without access to the proposed cloud backend, explain that concrete limitation and offer a reachable option. Let the user choose; retain an existing backend when a connection is temporarily unavailable.

## 2. What resources and constraints govern routing?

Ask the user about the tools/subscriptions they want to use and any hard limits. Discover installed capabilities when possible rather than asking them to enumerate technical model IDs.

Useful compact prompt:

> Which AI tools should participate, and are there models you forbid or a budget you want to protect? For example: free-first, existing subscriptions only, a paid spending cap, or named exclusions. Does any work contain private data that restricts endpoints?

Distinguish examples from actual choices. A mentioned subscription is not proof of worker/API access. Do not trial models while collecting preferences. Record hard bans, authorized budget, data restrictions, concurrency, and preferred tools in policy. Unknown paid allowance does not authorize paid exploration.

## 3. How should it learn?

Offer a short choice with consequences:

- **Balanced starting point:** about 80% established routes / 20% bounded exploration on eligible low-risk tasks, within the authorized budget.
- **Conservative:** established routes; explore only when explicitly requested.
- **Custom:** user-defined allocation, domains, limits, or triggers.

Ask what kinds of work the user does if that is not already apparent. Suggest useful acceptance examples from [domain examples](domain-examples.md), then adapt to their field. Do not require software categories for a media, research, or 3D workflow.

## Save and summarize the decision

After the answers are sufficient:

1. Locate or create the selected ledger and rules collections using the available adapter, preserving existing data. Check their actual headers and locators.
2. Save the complete choice and policy in the selected configuration scope; keep credentials outside it. Use `scripts/state.py init` for a new path or an atomic file update for an authorized change. Validate the completed configuration before routing.
3. Read back with `scripts/state.py resolve`. Check that storage identity and all applicable policy layers match the answers.
4. Give a short summary: backend/scope, the two locations, permitted tools and hard limits, exploration setting, and how to change the choice later.

The user's setup answers authorize the choices they describe. Do not insert another generic approval step before saving them. Ask again only for a real unresolved choice or an action requiring separate authorization.

Each later session loads state and current rules. Ask a targeted question when access, budget, conflicting policy, or a missing capability actually affects the next decision; avoid repeating setup or asking the user to choose a model for every task.
