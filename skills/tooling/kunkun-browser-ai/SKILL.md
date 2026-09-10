---
name: kunkun-browser-ai
description: Use when a task needs Kunkun's local Browser AI queue, CLI/Electron browser host, ChatGPT/Gemini/NotebookLM automation, browser-generated images/files, artifact downloads, or a decision between the official ChatGPT browser path and Kunkun MCP. Also use when diagnosing provider UI drift, worker pairing, completion detection, or browser-session boundaries.
license: MIT
compatibility: Requires a local Kunkun checkout and either the CLI host or Electron host; provider tasks require a paired MV3 browser extension and an already logged-in browser session.
metadata:
  author: Huakun Shen
  domain: browser-ai
  tags:
    - kunkun
    - browser-ai
    - chatgpt
    - gemini
    - notebooklm
    - mcp
    - artifacts
---

# Kunkun Browser AI

Use Kunkun as the cross-provider, CLI/Electron-capable browser automation
surface. Keep the official ChatGPT browser extension as an optional ChatGPT-only
fast path; it is not a public Kunkun MCP transport and must not become a hidden
dependency.

## Choose the control lane first

| Need | Preferred lane |
| --- | --- |
| One-off ChatGPT question or direct ChatGPT side-panel task | ChatGPT Web/official ChatGPT extension; choose top-level **Chat**, not Work |
| ChatGPT/Gemini/NotebookLM queue, multiple questions, continuation, image/file generation, artifact materialization | Kunkun Browser AI MCP |
| CLI/Electron/headless workflow, permissions, durable recovery, or cross-provider automation | Kunkun Browser AI MCP |
| Login, CAPTCHA, unknown UI drift, or a provider action not represented by Kunkun | Computer Use fallback |
| Generic browser control | Use Kunkun Browser Control only when `tools/list` or host status proves it exists; do not invent `/mcp/browser-control` before it is implemented and live-verified |

Complexity is not a reason to switch to ChatGPT Work. Work is the user's
explicitly more expensive/token-consuming lane. For difficult research/design
inside ChatGPT Web, stay on top-level **Chat** and choose the strongest model
and highest effort visibly available there.

## Resolve the local host

Resolve the checkout in this order:

1. `KUNKUN_REPO` when set;
2. the nearest workspace ancestor containing `apps/cli/src/cli.ts`;
3. `~/Dev/kunkun`.

Prefer the Electron app for daily use when it is already installed and its
Browser AI worker status is `Connected`. Use the CLI host for headless/CI work
or when Electron is intentionally not running:

```sh
kunkun_repo="${KUNKUN_REPO:-$HOME/Dev/kunkun}"
cd "$kunkun_repo/apps/cli"
bun src/cli.ts serve --db "${KUNKUN_BROWSER_AI_DB_PATH:-$HOME/kunkun.db}" --port "${KUNKUN_PORT:-9559}"
```

Reuse an existing host on port 9559; do not start a second host against the
same database. The provider caller surface is:

```text
http://127.0.0.1:9559/mcp/browser-ai
```

The browser worker URL is separate from the MCP URL:

```text
ws://127.0.0.1:9559/rpc?browserExtension=1&token=<browser-worker-token>
```

The token and database/profile must belong to the same host. Never type caller
tokens, worker tokens, provider credentials, cookies, or API keys through
Computer Use; ask the user to paste a worker URL into the extension Options page
when pairing is required.

## Kunkun Browser AI MCP loop

Use the advertised tools, not guessed names:

1. `initialize` and `tools/list`.
2. Submit with `browser_ai_submit` or `browser_ai_submit_batch` using
   `provider`, `mode`, `prompt`, and a unique `clientRequestId`.
3. Omit `parentJobId` for a new topic. Use an owned successful parent only for
   a same-provider continuation.
4. Poll `browser_ai_wait` with bounded waits (at most 60 seconds per call).
5. On `succeeded`, call `browser_ai_read_result`.
6. For images/files, require a non-empty artifact reference, then use
   `browser_ai_materialize_artifact` and the authenticated Kunkun download URL.

Do not use `curl`/`wget` on raw provider URLs. They may require browser cookies
or a one-shot blob URL. Kunkun's host owns the artifact and uses Node
`fs/promises` at the host boundary; Bun is only the local script runner.

## Completion and artifact evidence

Do not treat a spinner disappearing, a filename, or one DOM mutation as proof.

- Text is complete only after the job-marked answer is stable across polls and
  the provider has no generating indicator.
- Images are complete only after a loaded job-owned image is uploaded and the
  artifact is committed.
- Files are complete only after a provider download/export action succeeds,
  bytes are uploaded and committed with filename/content type/length, and the
  caller can materialize or download the owned artifact.

Keep evidence tiers separate: provider card visible, browser download event,
Kunkun artifact commit, materialized local file, and MIME/OOXML verification.
For Markdown returned as text, use `browser_ai_export_text`; it creates a real
managed text file but does not convert a provider code block into DOCX/PPTX.

## UI drift and general browser control

Provider drift is unavoidable. Keep provider-specific selectors and completion
semantics in small adapters. Prefer, in order:

1. semantic DOM roles/labels and narrow typed snapshots;
2. stable job markers, response ownership, and bounded readiness checks;
3. typed accessibility/ref data for closed shadow DOM or unavailable DOM
   controls;
4. screenshots only when the tree/DOM cannot answer a visual question;
5. `needs_manual` for login, permission, CAPTCHA, or exhausted provider drift.

Do not expose HTML dumps, cookies, raw Chrome tab IDs, debugger sockets, or local
Downloads paths across MCP. A future generic Browser Control MCP should use
opaque tab handles, selected-tab/group ownership, a host-side session lease,
bounded actions, and a separate worker/fault domain from the provider queue.

## Official ChatGPT extension boundary

The official ChatGPT Chrome extension is useful for ChatGPT-only direct browser
work and may adapt to ChatGPT UI changes faster than a third-party DOM adapter.
The installed extension's native host/side-panel/WebMCP integration is an
OpenAI app boundary, not a documented local MCP API for Kunkun. Use it as a
fast path when the user asks for direct ChatGPT UI work; use Kunkun for
cross-provider, artifact-aware, headless, or durable workflows.

Do not let the two controllers drive the same tab concurrently when both use
Chrome debugger access. If Kunkun's generic Browser Control MCP is unavailable,
fall back to the official ChatGPT path or Computer Use rather than claiming
that Kunkun can invoke the official extension internally.

## Report format

For a live run, report:

- host surface: Electron or CLI, host URL, and database/profile identity without
  revealing tokens;
- provider, mode, prompt order, new/continued conversation semantics;
- job IDs, terminal statuses, completion signals, and any recovery boundary;
- artifact filename, MIME, byte length, materialized path/resource, and local
  verification when available;
- remaining login, permission, provider-drift, or download evidence gaps.
