import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

const CHATGPT_HOSTS = new Set(["chatgpt.com", "chat.openai.com"]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ParsedChatGPTUrl = {
  conversationId: string;
  host: string;
};

export type JsonRpcRequest = {
  id: number;
  method: string;
  params: Record<string, unknown>;
};

export type JsonRpcNotification = {
  method: string;
  params: Record<string, unknown>;
};

export function parseConversationId(value: string): string {
  if (!UUID_PATTERN.test(value)) {
    throw new Error(`Invalid conversation UUID: ${value}`);
  }
  return value;
}

export function parseChatGPTUrl(input: string): ParsedChatGPTUrl {
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new Error("ChatGPT conversation URL is not a valid URL");
  }

  const host = url.hostname.toLowerCase();
  if (!CHATGPT_HOSTS.has(host)) {
    throw new Error("ChatGPT conversation URL must use chatgpt.com or chat.openai.com");
  }

  const segments = url.pathname.split("/").filter(Boolean);
  const conversationMarker = segments.lastIndexOf("c");
  const rawConversationId = segments[conversationMarker + 1];
  if (conversationMarker < 0 || !rawConversationId) {
    throw new Error("ChatGPT conversation URL is missing /c/<conversation-id>");
  }

  return {
    conversationId: parseConversationId(rawConversationId),
    host,
  };
}

export function buildRpcRequest(
  id: number,
  method: string,
  params: Record<string, unknown> = {},
): JsonRpcRequest {
  return { id, method, params };
}

export function buildRpcNotification(
  method: string,
  params: Record<string, unknown> = {},
): JsonRpcNotification {
  return { method, params };
}

type SpawnProcess = (...args: any[]) => any;

export type LocalAppServerOptions = {
  binary?: string;
  cwd?: string;
  timeoutMs?: number;
  spawnProcess?: SpawnProcess;
};

function jsonRpcError(message: string, stderr: string): Error {
  const detail = stderr.trim();
  return new Error(detail ? `${message}: ${detail}` : message);
}

/**
 * Read a locally persisted Codex thread through the public app-server protocol.
 * This intentionally does not call ChatGPT Web endpoints.
 */
export async function readLocalCodexThread(
  threadId: string,
  options: LocalAppServerOptions = {},
): Promise<Record<string, unknown>> {
  const validThreadId = parseConversationId(threadId);
  const command = options.binary ?? "codex";
  const spawnProcess = options.spawnProcess ?? (spawn as unknown as SpawnProcess);
  const timeoutMs = options.timeoutMs ?? 15_000;
  const child = spawnProcess(command, ["app-server", "--listen", "stdio://"], {
    cwd: options.cwd,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = createInterface({ input: child.stdout });
  const pending = new Map<number, { resolve: (value: any) => void; reject: (error: Error) => void }>();
  let nextRequestId = 1;
  let stderr = "";
  let settled = false;

  child.stderr.on("data", (chunk: Buffer | string) => {
    stderr += chunk.toString();
  });

  const rejectPending = (error: Error) => {
    for (const request of pending.values()) request.reject(error);
    pending.clear();
  };

  lines.on("line", (line: string) => {
    if (!line.trim()) return;
    let message: any;
    try {
      message = JSON.parse(line);
    } catch {
      rejectPending(jsonRpcError("Codex app-server returned invalid JSON", stderr));
      return;
    }
    if (typeof message.id !== "number") return;
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) {
      request.reject(new Error(`${message.error.message ?? "JSON-RPC error"}`));
    } else {
      request.resolve(message.result ?? {});
    }
  });

  child.once("error", (error: Error) => rejectPending(error));
  child.once("exit", (code: number | null, signal: string | null) => {
    if (settled) return;
    rejectPending(
      jsonRpcError(
        `Codex app-server exited before responding (code=${code ?? "null"}, signal=${signal ?? "null"})`,
        stderr,
      ),
    );
  });

  const send = (message: JsonRpcRequest | JsonRpcNotification) => {
    child.stdin.write(`${JSON.stringify(message)}\n`);
  };

  const request = (method: string, params: Record<string, unknown>) => {
    const id = nextRequestId++;
    send(buildRpcRequest(id, method, params));
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(jsonRpcError(`Timed out waiting for app-server method ${method}`, stderr));
      }, timeoutMs);
      pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
    });
  };

  try {
    await request("initialize", {
      clientInfo: { name: "chatgpt-thread-reader-poc", version: "0.1.0" },
      capabilities: { experimentalApi: true },
    });
    send(buildRpcNotification("initialized"));
    return await request("thread/read", {
      threadId: validThreadId,
      includeTurns: true,
    });
  } finally {
    settled = true;
    lines.close();
    rejectPending(new Error("Codex app-server reader closed"));
    child.kill();
  }
}

type CliArgs = {
  mode: "parse" | "app-server";
  url?: string;
  id?: string;
  binary?: string;
};

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = { mode: "parse" };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--mode") {
      const mode = argv[++index];
      if (mode !== "parse" && mode !== "app-server") throw new Error(`Unknown mode: ${mode}`);
      args.mode = mode;
    } else if (value === "--url") {
      args.url = argv[++index];
    } else if (value === "--id") {
      args.id = argv[++index];
    } else if (value === "--codex-bin") {
      args.binary = argv[++index];
    } else if (value === "--help" || value === "-h") {
      console.log(
        "Usage: node --experimental-strip-types scripts/read-chatgpt-thread.ts " +
          "--mode parse|app-server (--url URL | --id UUID)",
      );
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  return args;
}

export async function main(argv = process.argv.slice(2)): Promise<void> {
  const args = parseArgs(argv);
  const parsed = args.url ? parseChatGPTUrl(args.url) : undefined;
  const conversationId = parsed?.conversationId ?? (args.id ? parseConversationId(args.id) : undefined);
  if (!conversationId) throw new Error("Provide --url or --id");

  if (args.mode === "parse") {
    console.log(JSON.stringify({ sourceUrl: args.url ?? null, conversationId, host: parsed?.host ?? null }, null, 2));
    return;
  }

  const result = await readLocalCodexThread(conversationId, { binary: args.binary });
  console.log(
    JSON.stringify(
      { sourceUrl: args.url ?? null, conversationId, host: parsed?.host ?? null, source: "codex-app-server", result },
      null,
      2,
    ),
  );
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main().catch((error: Error) => {
    console.error(JSON.stringify({ error: error.message }, null, 2));
    process.exitCode = 1;
  });
}
