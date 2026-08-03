---
name: chatgpt-external-chrome
description: Drive a user's logged-in ChatGPT session in external Google Chrome with Codex Computer Use, submit a confirmed non-sensitive question, wait for a stable response, and return only the final answer. Use when the user asks to query ChatGPT through their real Chrome browser, retrieve ChatGPT's response, test browser automation, or investigate copy/download behavior in ChatGPT web UI.
---

# ChatGPT in External Chrome

Use Computer Use directly against `com.google.Chrome`. Do not use the in-app browser. Prefer the Chrome-specific browser connector if it is available; otherwise use Computer Use.

## Open and inspect

1. Initialize the Computer Use runtime, then call `sky.get_app_state({ app: "com.google.Chrome", disableDiff: true })`.
2. If the accessibility tree cannot be read, do not click by guesswork. Ask the user to grant Codex macOS Accessibility and Screen Recording permissions, then retry.
3. If ChatGPT is not logged in, ask the user to complete login manually. Never handle credentials or 2FA.
4. Prefer the existing ChatGPT tab when the user is continuing a task; otherwise create a new tab before navigation.

## Submit a question

1. Before clicking the ChatGPT send button, ask for confirmation of the exact non-sensitive question. Treat external submission as a representational action.
2. Re-read the accessibility tree immediately before each action; element indexes are not stable.
3. Click the ChatGPT text entry area and use `sky.type_text`. Verify the editable value matches the intended question before sending.
4. `sky.set_value` may be rejected for ChatGPT's contenteditable composer. Use click + `type_text` instead.
5. On the verified 2026-07-13 environment, `type_text` dropped Chinese characters. If that recurs, clear the draft with `super+a` then `BackSpace`, use an approved English equivalent, and verify it. Do not send a malformed draft.
6. Click the element labeled `Send prompt`; do not rely on Return.

## Prepare Deep Research without sending

1. Click the composer `Add files and more` (`+`) control, then select `Deep research`.
2. Re-read the tree. Treat the `Deep research` badge in the composer and a `Send prompt` button as the mode-selection success signal.
3. The add-menu items may be omitted from the accessibility tree even when visibly present. In that case, inspect a fresh screenshot and use a coordinate click only for the visible `Deep research` row; immediately re-read the tree to verify the badge.
4. Click the composer, use `sky.type_text` for the approved draft, and verify the entire value in the accessibility tree. On the verified environment, use English if Chinese characters are dropped.
5. If the user asks only to prepare a draft, stop here. Do not click `Send prompt`, press Return, create a research task, or imply that research has started.
6. If the user later requests submission, obtain confirmation of the exact non-sensitive draft immediately before clicking `Send prompt`.

## Wait and extract

1. Poll the current Chrome state every 3–6 seconds.
2. Treat the response as complete only after all are true:
   - `Stop answering` is absent;
   - the normal composer controls have returned;
   - `Copy response` is present; and
   - two successive full accessibility-tree reads are identical.
3. Extract the content beneath `ChatGPT said:` from the last assistant response in the accessibility tree. Do not return sidebar history or the user's prompt as the answer.
4. For ordinary questions, this extraction path is preferred over clipboard access.

## Mermaid diagrams

1. When ChatGPT renders a Mermaid block, inspect the `Code` / `Preview` toggle in the accessibility tree.
2. Activate `Code` and read the displayed Mermaid source. This was verified to expose the complete code as text, with a block-level `Copy` button.
3. Do not infer a diagram's semantics from its rendered preview: the tree exposes it only as an unlabeled SVG image with `graphics-document` / `flowchart-v2` metadata and zoom controls, not a reliable node-and-edge structure.
4. Use screenshot-based visual understanding only when source is unavailable, and label the result as lower confidence.

## Copy and download

- Click `Copy response` only when Markdown formatting or citations are required. Native clipboard permission prompts need the user's confirmation.
- For a completed Deep Research report, inspect the nested `internal://deep-research` iframe in the Chrome accessibility tree. Computer Use was verified to expose its title, headings, text, tables, and cited URLs despite its cross-origin DOM boundary. Extract this tree for reading and summarization.
- For a canonical Markdown artifact, open the report's `Export` menu and click `Export to Markdown`. In verified external Chrome, this automatically downloaded a `.md` file with no native Save dialog. Confirm the Chrome download entry reaches `Done`.
- ChatGPT reuses report names. Select the newest matching file by modification time and move it into the current workspace before reading it. Do not open Typora or another external editor:

  ```bash
  latest_report="$(ls -t "$HOME"/Downloads/deep-research-report*.md | head -n 1)"
  mv "$latest_report" "$PWD/"
  ```

- If the shell cannot list `~/Downloads`, treat that as a macOS Files and Folders permission issue. Ask the user to grant Codex Downloads access; do not claim the export failed.

## Record the run

Record the browser surface used, prompt language, input verification result, completion signals, extraction method, and any copy/download limitation in a local task document. Never include login credentials, private chat history, or unrelated conversation contents.
