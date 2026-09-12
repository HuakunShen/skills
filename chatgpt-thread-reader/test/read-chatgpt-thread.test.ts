import test from "node:test";
import assert from "node:assert/strict";

import { parseChatGPTUrl } from "../scripts/read-chatgpt-thread.ts";

test("parses the conversation UUID from a ChatGPT GPT URL", () => {
  const parsed = parseChatGPTUrl(
    "https://chatgpt.com/g/g-p-6a560710c85881919aba64090acc7fb2/c/6aa54672-a870-83ec-87f9-e044b5c3e1f2",
  );

  assert.deepEqual(parsed, {
    conversationId: "6aa54672-a870-83ec-87f9-e044b5c3e1f2",
    host: "chatgpt.com",
  });
});

test("rejects non-ChatGPT conversation URLs", () => {
  assert.throws(
    () => parseChatGPTUrl("https://example.com/c/6aa54672-a870-83ec-87f9-e044b5c3e1f2"),
    /ChatGPT conversation URL/,
  );
});
