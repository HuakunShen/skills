// ❌ All constructed counterexamples (not repository code) - none of these would pass review in Huakun's repos,
// nor his self-built gate scripts (check-boundaries / enforce-runtime-layering).
// Compiled from explicit bans in the repos' AGENTS.md files and grep verification (0 hits in hand-written code).

// ─── 1. Type escape hatches (grep-verified: 0 occurrences in refyard's hand-written code) ───
// @ts-ignore
// @ts-expect-error
const user = response.body as unknown as User;
function handle(value: any) { return value.foo; }
// eslint-disable-next-line @typescript-eslint/no-explicit-any

// ─── 2. Hand-writing the same literal set twice (caught by Equal/Expect assertions) ───
// type ErrorCode = "unauthorized" | "forbidden";
// const errorCodes = ["unauthorized", "forbidden"];  // drifts with no compile error

// ─── 3. Asserting external input directly inside a handler (the boundary must go through schema) ───
app.post("/items", (req, res) => {
  const body = req.body as CreateItemRequest;  // unknown keys are bugs; strictObject should reject them
  // ...
});

// ─── 4. Branching on message text ───
try {
  // ...
} catch (e) {
  if ((e as Error).message.includes("not found")) {
    // breaks the moment wording changes; branch on the closed code table instead
  }
}

// ─── 5. A portable package importing host APIs (check-boundaries fails outright) ───
import { Buffer } from "node:buffer";       // forbidden inside packages/git-core
import { ipcMain } from "electron";          // forbidden in the portable layer - enforce-runtime-layering lint failure

// ─── 6. Internal packages with build scripts / importing dist inside the workspace / cross-package relative paths ───
// packages/git-core/package.json:
//   "scripts": { "build": "tsc -p tsconfig.json" }   // internal packages need no build
// apps/cli/src/x.ts:
//   import { plan } from "../../packages/git-core/src/plan/status.js";  // must import by package name

// ─── 7. Scattered versions / floating latest ───
// packages/git-core/package.json: "zod": "^4.6.5"   // versions live in exactly one place: the catalog

// ─── 8. Spreading optional fields straight through in repos with exactOptionalPropertyTypes ───
// return { ...parsed.data };  // ghost undefined leaks into the type layer
