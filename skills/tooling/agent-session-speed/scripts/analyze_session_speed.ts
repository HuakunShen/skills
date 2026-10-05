// Measure token throughput (tps) and TTFT from AI coding-agent session logs.
//
// Run with any of (no dependencies, built-in sqlite/zstd only):
//   node analyze_session_speed.ts --agent codex
//   bun  analyze_session_speed.ts --agent zcode
//   deno run --allow-read --allow-env analyze_session_speed.ts --agent dsh
//
// Node 22.5+/Deno 2.2+ use node:sqlite + node:zlib; Bun uses bun:sqlite +
// Bun.zstdDecompressSync (auto-detected).

type SqlRow = Record<string, unknown>;

interface SqlDb {
  all(sql: string, params?: unknown[]): SqlRow[];
  close(): void;
}

interface Row {
  agent: string;
  level: "request" | "turn"; // request = one model API call (~pure speed); turn = whole agent turn
  model: string;
  day: string;
  outTokens: number;
  inputTokens: number;
  reasoningTokens: number;
  steps: number; // model responses within the turn
  durMs: number;
  ttftMs: number;
  genMs: number; // durMs - ttftMs
  tps: number | null;
}

const DEGENERATE_TPS = 500; // tps above this means duration≈TTFT records, not real speed

// ---------- sqlite across runtimes ----------

async function openSqlite(path: string): Promise<SqlDb> {
  // Non-literal specifiers keep runtimes from statically resolving modules the
  // current one lacks (TS can't type them either — that is intentional).
  try {
    const nodeSqlite = "node:" + "sqlite";
    const mod: any = await import(/* @vite-ignore */ nodeSqlite);
    const db = new mod.DatabaseSync(path, { readOnly: true });
    return {
      all: (sql, params = []) => db.prepare(sql).all(...params) as SqlRow[],
      close: () => db.close(),
    };
  } catch {
    const bunSqlite = "bun" + ":sqlite";
    const mod: any = await import(bunSqlite);
    const db = new mod.Database(path, { readonly: true });
    return {
      all: (sql, params = []) => db.query(sql).all(...params) as SqlRow[],
      close: () => db.close(),
    };
  }
}

// ---------- helpers ----------

// Zstandard decompression from built-ins: node:zlib on Node and Deno,
// Bun.zstdDecompressSync on Bun. Session logs concatenate multiple zstd frames
// (append-style writes); runtimes disagree on concatenated frames (Node/Bun
// decode them all, Deno stops after the first), so frames are split on the
// magic bytes and decoded one by one — identical behavior everywhere.
const ZSTD_MAGIC = new Uint8Array([0x28, 0xb5, 0x2f, 0xfd]);

function indexOfBytes(haystack: Uint8Array, needle: Uint8Array, from: number): number {
  outer: for (let i = from; i <= haystack.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (haystack[i + j] !== needle[j]) continue outer;
    }
    return i;
  }
  return -1;
}

async function zstdDecompressAll(data: Uint8Array): Promise<Uint8Array> {
  let decompressSync: (b: Uint8Array) => Uint8Array;
  const bun = (globalThis as any).Bun;
  if (bun?.zstdDecompressSync) {
    decompressSync = bun.zstdDecompressSync.bind(bun);
  } else {
    const nodeZlib = "node:" + "zlib";
    const mod: any = await import(/* @vite-ignore */ nodeZlib);
    decompressSync = mod.zstdDecompressSync;
  }
  const frames: Uint8Array[] = [];
  let start = indexOfBytes(data, ZSTD_MAGIC, 0);
  if (start === -1) throw new Error("no zstd frames found");
  while (start !== -1) {
    const next = indexOfBytes(data, ZSTD_MAGIC, start + ZSTD_MAGIC.length);
    frames.push(data.subarray(start, next === -1 ? data.length : next));
    start = next;
  }
  const parts: Uint8Array[] = [];
  let failed = 0;
  for (const frame of frames) {
    try {
      parts.push(decompressSync(frame));
    } catch {
      failed += 1; // false-positive magic inside compressed data
    }
  }
  if (parts.length === 0) throw new Error("zstd: no frame decoded");
  if (failed > 0) console.error(`warning: ${failed}/${frames.length} zstd frames failed to decode`);
  let total = 0;
  for (const p of parts) total += p.length;
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

function dayOf(epochMs: number): string {
  return new Date(epochMs).toISOString().slice(0, 10);
}

function pct(sorted: number[], p: number): number {
  const k = (sorted.length - 1) * p;
  const f = Math.floor(k);
  const c = Math.min(f + 1, sorted.length - 1);
  return sorted[f] + (sorted[c] - sorted[f]) * (k - f);
}

function num(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0) || 0;
}

function makeRow(partial: Omit<Row, "genMs" | "tps">): Row {
  const genMs = Math.max(partial.durMs - partial.ttftMs, 0);
  return {
    ...partial,
    genMs,
    tps: genMs > 0 ? partial.outTokens / (genMs / 1000) : null,
  };
}

function filterValid(rows: Row[], minGenMs: number): { ok: Row[]; excludedShort: number; excludedFast: number; excludedEmpty: number } {
  let excludedShort = 0;
  let excludedFast = 0;
  let excludedEmpty = 0;
  const ok: Row[] = [];
  for (const r of rows) {
    if (r.outTokens <= 0) {
      excludedEmpty += 1;
    } else if (r.genMs < minGenMs) {
      excludedShort += 1; // window too small to measure (often non-streamed responses)
    } else if (r.tps === null || r.tps > DEGENERATE_TPS) {
      excludedFast += 1; // implausible speed: broken timing, not a fast model
    } else {
      ok.push(r);
    }
  }
  return { ok, excludedShort, excludedFast, excludedEmpty };
}

function summarize(rows: Row[], label: string, minGenMs: number): void {
  const { ok, excludedShort, excludedFast, excludedEmpty } = filterValid(rows, minGenMs);
  if (ok.length === 0) {
    console.log(`\n== ${label}: no data ==`);
    return;
  }
  const v = ok.map((r) => r.tps as number).sort((a, b) => a - b);
  const ttfts = ok.map((r) => r.ttftMs).filter((t) => t > 0).sort((a, b) => a - b);
  const totOut = ok.reduce((s, r) => s + r.outTokens, 0);
  const totS = ok.reduce((s, r) => s + r.genMs, 0) / 1000;
  console.log(`\n== ${label} ==`);
  console.log(
    `rows: ${ok.length} (excluded: ${excludedEmpty} no-usage, ${excludedShort} window<${minGenMs}ms, ` +
      `${excludedFast} tps>${DEGENERATE_TPS})   total output tokens: ${totOut.toLocaleString()}   ` +
      `total gen time: ${Math.round(totS).toLocaleString()}s`,
  );
  const f = (x: number) => x.toFixed(1);
  console.log(
    `median tps: ${f(pct(v, 0.5))}   p10: ${f(pct(v, 0.1))}   p25: ${f(pct(v, 0.25))}   ` +
      `p75: ${f(pct(v, 0.75))}   p90: ${f(pct(v, 0.9))}   p99: ${f(pct(v, 0.99))}`,
  );
  if (totS > 0) console.log(`aggregate (tokens/time): ${f(totOut / totS)} tps`);
  if (ttfts.length > 0) {
    console.log(`TTFT median: ${Math.round(pct(ttfts, 0.5))}ms   p90: ${Math.round(pct(ttfts, 0.9))}ms`);
  }
}

function byModel(rows: Row[], minGenMs: number): void {
  const { ok } = filterValid(rows, minGenMs);
  const groups = new Map<string, number[]>();
  for (const r of ok) {
    const key = `${r.model}  [${r.level}]`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(r.tps as number);
  }
  console.log("\n== by model ==")
  for (const [model, tpsList] of [...groups.entries()].sort()) {
    const v = tpsList.sort((a, b) => a - b);
    console.log(
      `${model.padEnd(40)} n=${String(v.length).padStart(5)}  ` +
        `median=${pct(v, 0.5).toFixed(1).padStart(6)}  p90=${pct(v, 0.9).toFixed(1).padStart(6)} tps`,
    );
  }
}

function byDay(rows: Row[], minGenMs: number): void {
  const { ok } = filterValid(rows, minGenMs);
  const groups = new Map<string, number[]>();
  for (const r of ok) {
    if (!groups.has(r.day)) groups.set(r.day, []);
    groups.get(r.day)!.push(r.tps as number);
  }
  if (groups.size === 0) return;
  console.log("\n== daily median tps (pure-speed rows) ==")
  for (const [day, tpsList] of [...groups.entries()].sort()) {
    const v = tpsList.sort((a, b) => a - b);
    console.log(
      `${day}: n=${String(v.length).padStart(4)}  median=${pct(v, 0.5).toFixed(1).padStart(6)}  ` +
        `p90=${pct(v, 0.9).toFixed(1).padStart(6)}`,
    );
  }
}

// ---------- parsers ----------

// Codex rollout JSONL: one JSON object per line. Key events:
//   session_meta (originator, initial model), turn_context (per-turn model),
//   token_usage_record (per model response; turn_token_usage.output_tokens
//   includes reasoning tokens), event_msg/task_complete (duration_ms covers the
//   whole turn incl. tool execution; time_to_first_token_ms is the first
//   response's latency). tps from multi-response turns is a lower bound
//   diluted by tool time — single-response turns approximate pure decode speed.
async function parseCodex(sessionsDirs: string[]): Promise<Row[]> {
  const { readdirSync, readFileSync, existsSync } = await import("node:fs");
  const { join } = await import("node:path");
  const files: string[] = [];
  for (const dir of sessionsDirs) {
    const root = dir.replace(/^~/, process.env.HOME ?? "~");
    if (!existsSync(root)) {
      console.error(`warning: sessions dir not found: ${root}`);
      continue;
    }
    const stack = [root];
    while (stack.length > 0) {
      const d = stack.pop()!;
      for (const e of readdirSync(d, { withFileTypes: true })) {
        const p = join(d, e.name);
        if (e.isDirectory()) stack.push(p);
        else if (e.name.endsWith(".jsonl")) files.push(p);
      }
    }
  }
  const archived = join(process.env.HOME ?? "", ".codex/archived_sessions");
  if (existsSync(archived)) {
    const stack = [archived];
    while (stack.length > 0) {
      const d = stack.pop()!;
      for (const e of readdirSync(d, { withFileTypes: true })) {
        const p = join(d, e.name);
        if (e.isDirectory()) stack.push(p);
        else if (e.name.endsWith(".jsonl")) files.push(p);
      }
    }
  }
  console.error(`session files: ${files.length}`);

  const rows: Row[] = [];
  let interrupted = 0;
  for (const fp of files) {
    const lastModel = { value: "unknown" };
    type Ev = { steps: number; out: number | null; inLast: number; dur: number | null; ttft: number | null; model: string | null };
    const events = new Map<string, Ev>();
    const ev = (tid: string): Ev => {
      if (!events.has(tid)) {
        events.set(tid, { steps: 0, out: null, inLast: 0, dur: null, ttft: null, model: null });
      }
      return events.get(tid)!;
    };
    let content: string;
    try {
      content = readFileSync(fp, "utf8");
    } catch {
      continue;
    }
    for (const line of content.split("\n")) {
      if (line.length === 0) continue;
      let rec: any;
      try {
        rec = JSON.parse(line);
      } catch {
        continue;
      }
      const t: string = rec.type ?? "";
      const p: any = rec.payload ?? {};
      if (t === "session_meta") {
        if (p.model) lastModel.value = p.model;
      } else if (t === "turn_context") {
        if (p.model) lastModel.value = p.model;
        if (p.turn_id) ev(p.turn_id).model = p.model;
      } else if (t === "token_usage_record") {
        if (!p.turn_id) continue;
        const e = ev(p.turn_id);
        e.steps += 1;
        const turnOut = p.turn_token_usage?.output_tokens;
        if (typeof turnOut === "number" && turnOut > 0) e.out = turnOut;
        const threadIn = p.thread_token_usage?.input_tokens;
        if (typeof threadIn === "number" && threadIn > 0) e.inLast = threadIn;
      } else if (t === "event_msg" && p.type === "task_complete" && p.turn_id) {
        const e = ev(p.turn_id);
        e.dur = typeof p.duration_ms === "number" ? p.duration_ms : null;
        e.ttft = typeof p.time_to_first_token_ms === "number" ? p.time_to_first_token_ms : 0;
      }
    }
    if (events.size === 0) continue;
    for (const e of events.values()) {
      if (e.out === null) continue;
      if (e.dur === null) {
        interrupted += 1; // task_started but no task_complete
        continue;
      }
      rows.push(
        makeRow({
          agent: "codex",
          level: "turn",
          model: e.model ?? lastModel.value,
          day: (() => {
            const m = fp.match(/rollout-(\d{4}-\d{2}-\d{2})/);
            return m ? m[1] : "";
          })(),
          outTokens: e.out,
          inputTokens: e.inLast,
          reasoningTokens: 0,
          steps: e.steps,
          durMs: e.dur,
          ttftMs: e.ttft ?? 0,
        }),
      );
    }
  }
  console.error(`turns: ${rows.length}, interrupted (no task_complete): ${interrupted}`);
  return rows;
}

// ZCode sqlite (read-only): model_usage has one row per model API request with
// exact started_at/duration_ms/time_to_first_token_ms (epoch ms) and token
// breakdown — pure model speed, no tool dilution. turn_usage aggregates per
// turn end-to-end. query_source distinguishes main_turn / workflow_child /
// subagent / housekeeping (title, compact, verification).
async function parseZcode(dbPath: string): Promise<Row[]> {
  const { existsSync } = await import("node:fs");
  if (!existsSync(dbPath)) throw new Error(`zcode db not found: ${dbPath}`);
  const db = await openSqlite(dbPath);
  const rows: Row[] = [];
  const reqs = db.all(
    `SELECT model_id, started_at, duration_ms, time_to_first_token_ms,
            input_tokens, output_tokens, reasoning_tokens, query_source
     FROM model_usage WHERE status='completed'`,
  );
  for (const r of reqs) {
    const dur = num(r.duration_ms);
    const ttft = num(r.time_to_first_token_ms);
    rows.push(
      makeRow({
        agent: "zcode",
        level: "request",
        model: String(r.model_id ?? "unknown"),
        day: dayOf(num(r.started_at)),
        outTokens: num(r.output_tokens),
        inputTokens: num(r.input_tokens),
        reasoningTokens: num(r.reasoning_tokens),
        steps: 1,
        durMs: dur,
        ttftMs: ttft,
      }),
    );
  }
  const turns = db.all(
    `SELECT t.started_at, t.duration_ms, t.time_to_first_token_ms, t.model_request_count,
            t.input_tokens, t.output_tokens, t.reasoning_tokens,
            (SELECT m.model_id FROM model_usage m
             WHERE m.session_id = t.session_id AND m.turn_id = t.turn_id
             GROUP BY m.model_id ORDER BY SUM(m.output_tokens) DESC LIMIT 1) AS model_id
     FROM turn_usage t WHERE t.status='completed'`,
  );
  for (const t of turns) {
    rows.push(
      makeRow({
        agent: "zcode",
        level: "turn",
        model: String(t.model_id ?? "(multi)"),
        day: dayOf(num(t.started_at)),
        outTokens: num(t.output_tokens),
        inputTokens: num(t.input_tokens),
        reasoningTokens: num(t.reasoning_tokens),
        steps: num(t.model_request_count),
        durMs: num(t.duration_ms),
        ttftMs: num(t.time_to_first_token_ms),
      }),
    );
  }
  db.close();
  console.error(`zcode: ${reqs.length} model requests, ${turns.length} turns`);
  return rows;
}

// OpenCode sqlite: session_message rows of type='assistant' carry a JSON
// `data` blob with tokens {input, output, reasoning, ...} and time
// {created, completed} (epoch ms). One row per assistant reply ≈ one model
// response; duration is message-level, so TTFT is included in the window.
async function parseOpencode(dbPath: string): Promise<Row[]> {
  const { existsSync } = await import("node:fs");
  if (!existsSync(dbPath)) throw new Error(`opencode db not found: ${dbPath}`);
  const db = await openSqlite(dbPath);
  const msgs = db.all(
    `SELECT data, time_created FROM session_message WHERE type='assistant'`,
  );
  const rows: Row[] = [];
  for (const m of msgs) {
    let d: any;
    try {
      d = JSON.parse(String(m.data));
    } catch {
      continue;
    }
    const created = num(d?.time?.created ?? m.time_created);
    const completed = num(d?.time?.completed);
    const tokens = d?.tokens ?? {};
    rows.push(
      makeRow({
        agent: "opencode",
        level: "request",
        model: String(d?.model?.id ?? "unknown"),
        day: dayOf(created),
        outTokens: num(tokens.output),
        inputTokens: num(tokens.input),
        reasoningTokens: num(tokens.reasoning),
        steps: 1,
        durMs: completed - created,
        ttftMs: 0, // per-part timestamps exist but schema varies; treat window as incl. TTFT
      }),
    );
  }
  db.close();
  console.error(`opencode: ${msgs.length} assistant messages`);
  return rows;
}

// DSH (DeepSeek Harness) native session logs: one zstd-compressed JSONL per
// session at ~/.dsh/sessions/<workspace-slug>/session-*/session.v4.jsonl.zstd.
// One JSON object per line with a `type` field:
//   session           header: version (v4 expected)
//   step/start|end    {turn, step} boundaries; time marks the model-request start
//   assistant/message per model response: data.usage {inputTokens, outputTokens,
//                     reasoningTokens, cacheReadTokens}, data.source
//                     {provider, model}, data.stream[] chunk timeline — each
//                     entry has .time or absolute .time0 (+ per-chunk .dt);
//                     t0→tN is the pure streaming window (no tool time)
//   turn/start|end    turn boundaries; end.reason.kind tells completion
// TTFT here is approximate: first stream chunk − step/start (includes prompt
// assembly). Model label is "provider/model" because dsh routes to many
// providers.
async function parseDsh(sessionsDir: string): Promise<Row[]> {
  const { readdirSync, readFileSync, existsSync } = await import("node:fs");
  const { join } = await import("node:path");
  const root = sessionsDir.replace(/^~/, process.env.HOME ?? "~");
  if (!existsSync(root)) throw new Error(`dsh sessions dir not found: ${root}`);
  const files: string[] = [];
  const stack = [root];
  while (stack.length > 0) {
    const d = stack.pop()!;
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) stack.push(p);
      else if (e.name === "session.v4.jsonl.zstd" || e.name === "session.v4.jsonl") files.push(p);
    }
  }
  console.error(`dsh session files: ${files.length}`);

  const rows: Row[] = [];
  let skippedVersions = 0;
  for (const fp of files) {
    let content: string;
    try {
      if (fp.endsWith(".zstd")) {
        content = new TextDecoder().decode(await zstdDecompressAll(readFileSync(fp)));
      } else {
        content = readFileSync(fp, "utf8");
      }
    } catch (err) {
      console.error(`warning: failed to read ${fp}: ${err instanceof Error ? err.message : err}`);
      continue;
    }
    const stepStart = new Map<string, number>(); // "turn:step" -> start time
    const turnStart = new Map<number, number>();
    const turnMsgs = new Map<number, { model: string; out: number }[]>();
    const turnEnds = new Map<number, { time: number; completed: boolean }>();
    const turnFirstChunk = new Map<number, number>();
    const events: any[] = [];
    for (const line of content.split("\n")) {
      if (line.length === 0) continue;
      try {
        events.push(JSON.parse(line));
      } catch {
        /* skip malformed line */
      }
    }
    const header = events.find((e) => e.type === "session");
    if (!header || header.version !== 4) {
      skippedVersions += 1;
      continue;
    }
    const sessionId = String(header.id ?? "");

    const requestRows: Row[] = [];
    for (const e of events) {
      const t: string = e.type ?? "";
      const time = num(e.time);
      if (t === "step/start") {
        stepStart.set(`${e.data.turn}:${e.data.step}`, time);
      } else if (t === "turn/start") {
        turnStart.set(e.data.turn, time);
      } else if (t === "assistant/message") {
        const d = e.data ?? {};
        const turn = num(d.turn);
        const usage = d.usage ?? {};
        const stream: any[] = Array.isArray(d.stream) ? d.stream : [];
        let t0 = Infinity;
        let tN = 0;
        for (const s of stream) {
          // chunk entries carry absolute .time; tool-call-chunks carry .time0
          // plus per-chunk .dt offsets — take the last one as the entry end.
          let start = typeof s.time === "number" ? s.time : typeof s.time0 === "number" ? s.time0 : 0;
          let end = start;
          if (Array.isArray(s.dt) && s.dt.length > 0) end = start + s.dt[s.dt.length - 1];
          if (start > 0 && start < t0) t0 = start;
          if (end > tN) tN = end;
        }
        if (t0 === Infinity) t0 = time; // no stream recorded; fall back to message time
        if (tN < t0) tN = t0;
        const src = d.message?.source ?? d.source ?? {};
        if (src.kind && src.kind !== "model") continue; // synthetic, not a model response
        const model = `${src.provider ?? "?"}/${src.model ?? "?"}`;
        if (!turnMsgs.has(turn)) turnMsgs.set(turn, []);
        turnMsgs.get(turn)!.push({ model, out: num(usage.outputTokens) });
        const first = turnFirstChunk.get(turn);
        if (first === undefined || t0 < first) turnFirstChunk.set(turn, t0);
        const stepT0 = stepStart.get(`${turn}:${num(d.step)}`) ?? time;
        requestRows.push(
          makeRow({
            agent: "dsh",
            level: "request",
            model,
            day: dayOf(time),
            outTokens: num(usage.outputTokens),
            inputTokens: num(usage.inputTokens),
            reasoningTokens: num(usage.reasoningTokens),
            steps: 1,
            durMs: tN - stepT0,
            ttftMs: Math.max(t0 - stepT0, 0),
          }),
        );
      } else if (t === "turn/end") {
        turnEnds.set(e.data.turn, { time, completed: e.data.reason?.kind === "completed" });
      }
    }

    rows.push(...requestRows);
    for (const [turn, end] of turnEnds) {
      if (!end.completed) continue; // interrupted turns understate duration
      const start = turnStart.get(turn);
      if (start === undefined) continue;
      const msgs = turnMsgs.get(turn) ?? [];
      const outTotal = msgs.reduce((s, m) => s + m.out, 0);
      const dominant = msgs
        .reduce((acc, m) => {
          acc.set(m.model, (acc.get(m.model) ?? 0) + m.out);
          return acc;
        }, new Map<string, number>())
      ;
      const model = [...dominant.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "(none)";
      const firstChunk = turnFirstChunk.get(turn) ?? start;
      rows.push(
        makeRow({
          agent: "dsh",
          level: "turn",
          model,
          day: dayOf(start),
          outTokens: outTotal,
          inputTokens: 0,
          reasoningTokens: 0,
          steps: msgs.length,
          durMs: end.time - start,
          ttftMs: Math.max(firstChunk - start, 0),
        }),
      );
    }
    void sessionId;
  }
  if (skippedVersions > 0) console.error(`skipped ${skippedVersions} sessions with unexpected format version`);
  console.error(`dsh rows: ${rows.length}`);
  return rows;
}

// ---------- CLI ----------

interface Args {
  agent: string;
  sessionsDir: string[];
  db?: string;
  minGenMs: number;
  outCsv?: string;
}

function parseArgs(): Args {
  const argv = process.argv.slice(2);
  const args: Args = { agent: "codex", sessionsDir: [], minGenMs: 200 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--agent") args.agent = argv[++i] ?? args.agent;
    else if (a === "--sessions-dir") args.sessionsDir.push(argv[++i] ?? "");
    else if (a === "--db") args.db = argv[++i];
    else if (a === "--min-gen-ms") args.minGenMs = Number(argv[++i] ?? 200);
    else if (a === "--out-csv") args.outCsv = argv[++i];
    else if (a === "--help" || a === "-h") {
      console.log(
        "Usage: analyze_session_speed.ts --agent codex|zcode|opencode|dsh [--sessions-dir DIR ...] " +
          "[--db PATH] [--min-gen-ms N] [--out-csv FILE]",
      );
      process.exit(0);
    }
  }
  return args;
}

async function writeCsv(rows: Row[], path: string): Promise<void> {
  const { writeFileSync } = await import("node:fs");
  const cols = Object.keys(rows[0]) as (keyof Row)[];
  const esc = (v: unknown) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [cols.join(",")];
  for (const r of rows) lines.push(cols.map((c) => esc(r[c])).join(","));
  writeFileSync(path, lines.join("\n") + "\n");
  console.error(`per-row CSV: ${path}`);
}

async function main(): Promise<number> {
  const args = parseArgs();
  const home = process.env.HOME ?? "";
  let rows: Row[] = [];
  if (args.agent === "codex") {
    const dirs = args.sessionsDir.length > 0 ? args.sessionsDir : [`${home}/.codex/sessions`];
    rows = await parseCodex(dirs);
  } else if (args.agent === "zcode") {
    rows = await parseZcode(args.db ?? `${home}/.zcode/cli/db/db.sqlite`);
  } else if (args.agent === "opencode") {
    rows = await parseOpencode(args.db ?? `${home}/.local/share/opencode/opencode.db`);
  } else if (args.agent === "dsh") {
    const dirs = args.sessionsDir.length > 0 ? args.sessionsDir : [`${home}/.dsh/sessions`];
    rows = await parseDsh(dirs[0]);
  } else {
    console.error(`unsupported agent: ${args.agent} (supported: codex, zcode, opencode, dsh)`);
    return 1;
  }
  if (rows.length === 0) {
    console.error("no completed rows with token usage found");
    return 1;
  }
  rows.sort((a, b) => b.outTokens - a.outTokens);

  const { minGenMs } = args;
  const speed = rows.filter((r) => (args.agent === "codex" ? r.level === "turn" && r.steps === 1 : r.level === "request"));
  const turns = rows.filter((r) => r.level === "turn");

  const speedLabel =
    args.agent === "codex"
      ? "PURE-SPEED proxy: single-response turns (~model speed, no tool gaps)"
      : "PURE MODEL SPEED (request-level, no tool time)";
  summarize(speed, speedLabel, minGenMs);
  summarize(turns, "END-TO-END TURNS (agent loop, incl. tool time)", minGenMs);
  byModel(speed, minGenMs);
  byDay(speed, minGenMs);

  if (args.outCsv) await writeCsv(rows, args.outCsv);
  return 0;
}

await main();
