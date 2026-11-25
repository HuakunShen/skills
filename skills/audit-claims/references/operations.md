# 批量处理、断点续跑与多 Agent 操作

## 目录

1. [固定阶段](#固定阶段)
2. [建立运行目录](#建立运行目录)
3. [准备来源清单](#准备来源清单)
4. [生成批次](#生成批次)
5. [提交结果与恢复](#提交结果与恢复)
6. [单 Agent 与多 Agent](#单-agent-与多-agent)
7. [边界与完整性](#边界与完整性)

## 固定阶段

先确定整个分析范围，再列全清单，再批量获取文本，再批量提取，再核验与评分。不要以“下载一个、提取一个、上网核验一个、再下载下一个”的循环取代这个流程。

允许将获取工作分批并行，但开始提取前应固定本轮语料快照：每个范围内来源都已准备好，或明确标为失败、缺失、跳过、截断。把失败数计入覆盖率，不以成功下载的子集冒充全部历史。先保存原始文本；规范化、去重后的文本应另存，保留映射。

`audit_run.py` 只处理本地账本、哈希、批次与任务状态；它不下载网页、不调用模型、不查询行情，也不替代分析 Agent。Python 3.9+；`zoneinfo` 需要系统 IANA 时区数据库，缺失时安装 `tzdata`。其余功能使用 Python 标准库。

## 建立运行目录

从 skill 目录执行，或把脚本路径换成绝对路径：

```bash
python3 scripts/audit_run.py init \
  --run ./runs/example-2026-11-25 \
  --subject 'Example speaker' \
  --start 2021-11-25 --end 2026-11-25 \
  --as-of 2026-11-25 --timezone Asia/Singapore \
  --cutoff-mode retrospective
```

日期范围按指定时区的发布日期**两端包含**；历史日期的 `--as-of YYYY-MM-DD` 表示当地当天最后一个微秒，**当日**日期 `--as-of YYYY-MM-DD` 自动钳制为当前墙钟时刻（避免因 23:59:59 超前而触发未来截点报错）。精确时刻须包含 UTC offset，例如 `2026-11-25T12:00:00+08:00`；拒绝没有时区的 datetime。精确截止时刻当天、只有日期而没有发布时间的来源不擅自假定早于截止时刻，标为 `publication_time_unknown_at_cutoff`。

`cutoff_mode=retrospective` 表示以固定的结果截止日回溯核验，可使用后来发布的证据说明截止日前发生的事实；`knowledge_as_of` 则要求证据本身在截止时刻已公开可得。脚本只记录该策略，核验 Agent 必须执行。

初始化创建 `run.json`、`sources.jsonl`、`tasks.jsonl`、`claims.jsonl`、`evidence.jsonl`、`events.jsonl`、`progress.md`，以及 `sources/`、`work/batches/`、`work/results/`、`reports/`。

配置哈希包含 `schema_version`、`subject`、`scope`、`cutoff_mode`、`rules`、`models`。在首次规划前固定规则和模型策略；使用 `audit_run.py bind-policy --run <RUN>` 自动把冻结后的 `model-policy.json` 指纹与规则写入 `run.json` 并刷新 `config_hash`。已有计划后如需在保留已提取主张的情况下用新截点重新评估 `pending` 预测，使用 `audit_run.py assess --run <RUN> --as-of <ISO>` 开启新评估轮次。`execution`、价格、预算授权和进度不进入语义配置哈希，可单独更新并留痕。默认 `execution={"mode":"auto","max_workers":4}`。

## 准备来源清单

`sources.jsonl` 每行一个来源。所有路径相对 run 目录且不得逃出该目录：

```json
{"source_id":"source-001","title":"Example talk","source_url":"https://example.test/talk","published_at":"2025-03-01T10:00:00+08:00","content_path":"sources/source-001.md","status":"ready"}
```

必填稳定 `source_id`；以同一来源的原始 URL/平台 ID 为依据，不能因为标题变化重建身份。`ready` 才进入提取；其他状态：`pending`、`failed`、`skipped`、`truncated`。未知状态不当作成功。`published_at` 接受 ISO 日期或带 offset 的 datetime；日期未知列入排除项，要求后续人工确认。

可添加 `content_hash`（SHA-256 hex 或 `sha256:` 前缀），脚本会核对真实文件；可添加 `estimated_tokens`，必须是正整数，应来自实际 tokenizer。其他来源、语言、获取方式、转录质量、主体身份等字段原样保留在批次载荷中。不要在清单或源文件写 API key。

原始文本本来缺少、质量差或只是片段，与“讲话者说了不可验证的话”不同；前者是数据覆盖问题，不能当作讲话者的不可信证据。

## 生成批次

```bash
python3 scripts/audit_run.py plan-batches \
  --run ./runs/example-2026-11-25 --token-budget 60000 --max-items 10
```

`--token-budget` 是**可用输入预算**，调用者必须先扣除系统指令、工具结果、输出、跨文档引用和上下文安全余量。`--max-items` 可设为 10、50 或其他正整数，但不能覆盖 token 限制。单批提取可能输出比输入更细的结构化数据，需预留足够输出空间，防止模型输出截断。

没有真实 tokenizer 计数时，脚本剥离 frontmatter 与定位标记后，以分脚本字节估算 `ceil(ascii_bytes/4) + non_ascii_bytes + 128`（避免中英文和字幕标记导致的过度膨胀）。仍须按实际宿主上下文容量和输出限制控制批次，不能把估算当作模型调用成功的保证。

超预算来源进入 `plan.json.needs_segmentation`，不会被默默截断。先运行 `audit_run.py segment --run <RUN> --source-id <ID> --token-budget <N> --overlap-units 2` 在单位边界确定性切片（记录 `parent_source_id`、起止 unit、重叠与 100% 覆盖证明），再运行 `audit_run.py plan-batches --append` 将新切片或新增就绪来源追加纳入批次。

`plan.json` 保存总体清单数、范围内数量、可用来源数、实际入批数、排除原因和待切片清单；`work/batches/*.json` 是固定的批次载荷，记录源文件位置及真实内容哈希。重复同一命令保留已完成任务；追加新来源使用 `normalize_sources.py --append` 与 `plan-batches --append`。

完成批量提取后，运行确定性合并与统计胶水命令，避免手工重写账本：
- `audit_run.py merge-extraction --run <RUN>`：合并已完成 shard，机械验证每条 `original_quote` 存在于对应源文件及 locator 区间内，未命中者标 `needs_review`。
- `audit_run.py freeze-criteria --run <RUN> --claim-id <ID> --definition <JSON> [--difficulty trivial|moderate|hard|non_consensus] [--difficulty-score 1..5] [--difficulty-rationale "..."]`：生成规范 SHA-256 与服务端冻结时间戳并保存 `criteria/<sha>.json`，强制校验预测 `window_end > first_stated_at / published_at` 并在查结果前可选冻结难度评级。
- `adopt_verdict.py set-evidence-quality --run <RUN> --claim-id <ID> --directness <0|0.5|1> --independence <0|0.5|1> --traceability <0|0.5|1>`：在 `adopt` 之前写入证据质量评分，无需手工编辑 `claims.jsonl`。
- `adopt_verdict.py mark-trigger-unmet --run <RUN> --claim-id <ID> --evidence-ids <EID...>`：冻结规则并查证后若条件预测触发器未满足，关联触发证据并记录 `lifecycle="pending"`、`due_for_assessment=false`、`reason="trigger_unmet"`（保留历史快照）。
- `audit_run.py coverage --run <RUN>`：从 `sources.jsonl`、`plan.json`、`tasks.jsonl` 确定性回卷父来源统计并生成 `coverage.json`。
- `audit_run.py handoff-export` / `handoff-import`：打包/校验外部 AI 任务包并写 `handoff/receipts.jsonl`。
- `audit_run.py report-hashes --run <RUN> [--subject-id <SUBJECT>]`：在写入 `reviews/reports/*.json` 前输出精确 `data_hash` 与 `rubric_hash`。
- `audit_run.py build-report-data --run <RUN> [--subject-id <SUBJECT>]`：组装 `reports/report-data.json`（多说话人运行可按 `--subject-id` 过滤，案例卡保留 `speaker` / `subject_id` / `endorsement` / `difficulty` / `lead_time_days`）。

## 提交结果与恢复

先保存调度记录，再启动工作：

```bash
python3 scripts/audit_run.py checkpoint --run ./runs/example-2026-11-25 \
  --task-id extract_EXACT_ID_FROM_TASKS --status running
```

Worker 在 `work/results/` 写自己的独立 JSON 文件；从任务载荷复制真实身份和哈希，不得猜值：

```json
{
  "task_id": "extract_EXACT_ID_FROM_TASKS",
  "input_fingerprint": "EXACT_FINGERPRINT_FROM_TASK",
  "complete": true,
  "processed_source_ids": ["source-001"],
  "claims": []
}
```

`processed_source_ids` 必须恰好覆盖该批次全部来源；`claims=[]` 可以表示认真分析后没有观点，但不能表示尚未分析。输出被截断、来源遗漏或失败时，`complete` 不得设为 true。`claims` 的结构、原话和分类须按数据契约另行检查。

```bash
python3 scripts/audit_run.py checkpoint --run ./runs/example-2026-11-25 \
  --task-id extract_EXACT_ID_FROM_TASKS --status completed \
  --result work/results/result-001.json
python3 scripts/audit_run.py validate --run ./runs/example-2026-11-25
python3 scripts/audit_run.py status --run ./runs/example-2026-11-25
```

每次 checkpoint 会验证输入仍未改变、保存结果哈希并更新进度。已完成结果不能覆盖；修正应新建任务/新 run 并引用旧版本。失败任务可明确改回 pending/running，不能把失败直接当作成功。`running` 遗留表示中断后待检查，恢复时先看已有输出，避免重复调用收费服务。`attempts` 只在进入 running 时递增。

临近 context 压力时，先保存当前私有结果分片，记录已完成和未完成来源/观点、证据与假设、成本状态、下一步动作。用 checkpoint 的 `--note` 写入任务与事件日志，或另存 `handoff.md`；不要把唯一的交接说明只写进会被自动重建的 `progress.md`。新上下文读 `run.json` → `progress.md` → `tasks.jsonl` → 当前批次载荷/结果；不要重新装入全部语料。

## 单 Agent 与多 Agent

单 Agent 使用同一任务队列，顺序处理 pending 项，每个边界立即落盘。多 Agent 使用一个协调者：协调者负责确定范围、批次分配、合并与最终评分；Workers 只读输入和冻结规则，只写独立结果分片。禁止多个 Worker 追加同一个 `claims.jsonl`、`tasks.jsonl` 或成本文件。

提取完成后，协调者可追加 `stage=verify`、`adjudicate` 等任务，每个任务保留稳定 `task_id`、`payload_path`、`input_fingerprint`、`payload_hash`、`dependencies`、`status`、`attempts`、`result_path`。非提取任务必须在冻结载荷后把该文件原始字节的 SHA-256 hex 存为 `payload_hash`；后续 checkpoint 会验证，不能只保留一个可复用的规则标识符。它们也可用 checkpoint；非提取任务结果至少有 `task_id`、`input_fingerprint`、`complete:true`。核验语义、证据字段与规则版本由协调者按数据契约检查。

只在依赖已 completed 后启动下游任务。对简单数据查找使用廉价且能联网的 Worker；提取/分类用中档模型；复杂歧义升级复核；最终汇总再按需要提高模型档次。实际模型名称由本机可用工具配置，不把模型别名当作 API ID，不为了并行虚构不存在的子 Agent 功能。

## 边界与完整性

`validate` 检查配置/文件哈希、任务状态与依赖、结果覆盖及部分引用一致性；返回 `valid:true` 只代表账本完整性，不代表语料已全部处理，更不代表核验结论正确。查看 warnings、覆盖缺口、未完成任务、争议和未评分样本后再出报告。

脚本用同目录临时文件、fsync、原子替换保存规范文件，用 OS 锁拒绝第二个协调进程；进程退出后锁自动释放。各文件之间不是数据库事务；中断后以规范账本和结果哈希恢复，`progress.md` 是可重建摘要，事件日志用于追踪。Worker 文件应先完整写好再提交 checkpoint。

需要改变范围、正文、分类规则或批次时，保留旧 run；不要修改旧哈希使检查强行通过。可复用内容哈希一致的原始文件与已核验事实，但新报告必须明确关联的新范围、截止日、规则版本和复用条件。
