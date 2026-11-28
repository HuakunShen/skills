# 数据契约 v1

## 目录

1. 运行目录与所有权
2. 来源与规范化
3. 观点、出现记录和证据
4. 冻结规则与状态
5. 覆盖、成本与导出
6. 插件/服务适配边界

## 1. 运行目录与所有权

每次审计单独目录，默认在项目的 claim-audits/<subject>/<run-id>/，不将以下文件散放项目根目录。默认以 UTF-8 JSONL 为真源，一行一个完整对象；SQLite 模式则数据库是真源，JSONL 是显式导出的工作快照/交换格式。每轮只指定一个真源，不并发双写。无注释、NaN 或末尾逗号。schema_version=1。标识符稳定且不依赖排序位置；使用平台原 ID 或规范 URL/正文身份的哈希，不能用易变标题作唯一标识。

| 路径 | 用途 | 写者 |
| --- | --- | --- |
| run.json | 对象、范围、时区、截止模式、方法/模型配置、语义配置哈希 | 协调者 |
| config/ | 模型/存储/阶段执行问卷、冻结模型策略、rubric、预算许可和报告样式 | 协调者按用户选择 |
| sources.jsonl | 全部已发现来源及获取状态，含失败和排除项 | 协调者 |
| raw/ | 取得的原始文本/字幕；不可静默覆盖 | 获取协调者 |
| sources/ | 每篇规范化 Markdown、front matter 和定位 | 规范化协调者 |
| plan.json、tasks.jsonl | 提取计划及任务队列/状态/哈希/依赖 | 协调者 |
| work/batches/ | 带边界和输入指纹的批次 payload | 协调者 |
| work/results/ | 每个 worker/attempt 独占结果；先临时文件再原子重命名 | 对应 worker |
| occurrences.jsonl | 每次真实出现的原话、上下文、说话人及定位 | 协调者合并 |
| claims.jsonl | 去重后的当前 canonical claim 及裁定 | 协调者合并 |
| criteria/、history/ | 不变的规则快照、历史 claim/verdict 版本 | 协调者 |
| evidence.jsonl | 证据及反证、时间和来源关系 | 协调者合并 |
| source_access.jsonl | 每次查询/访问的 URL、时间、状态、失败、定位、采用或排除理由 | 协调者合并 |
| media_assets.jsonl | 媒体路径/URI、哈希、大小、保留策略、同步状态、删除记录 | 协调者 |
| media | 被忽略的本地媒体目录或指向用户指定同步盘的符号链接 | 获取协调者 |
| state/audit.sqlite | 可选 SQL 真源及事务历史；不含媒体字节 | 单数据库协调者 |
| reviews/facts/、reviews/reports/ | 各指定模型独立判断与初始分数，不覆盖 | 对应 reviewer |
| reviews/decisions/ | 共识验收、裁判与用户决定、证据绑定 | 协调者 |
| longitudinal/ | 按议题与时期保存的立场快照、转变记录和覆盖解释 | 协调者合并 |
| handoff/outbound/、handoff/inbound/ | 自包含外部任务包和未经改写的返回资料 | 导出/接收协调者 |
| handoff/receipts.jsonl | 外部执行者、版本/覆盖/证据验收与恢复动作 | 协调者 |
| coverage.json | 全语料与提取覆盖、复核缺口 | 协调者 |
| cost-plan.json、costs.jsonl | 分阶段报价、许可、usage/估计/账单事件 | 协调者合并 |
| events.jsonl、progress.md | 机器事件与人类可读恢复说明 | 协调者 |
| reports/ | Markdown/HTML 报告、metrics.json、报告数据快照、可选 SVG、派生 CSV | 协调者 |

主账本只允许一个协调者；多 agent 使用私有 shard。一次原子重命名不是跨文件数据库事务：先保存不可变结果，再更新 task 的路径/哈希，恢复时对账。不要把半个 JSON 行视为成功，不自动删除损坏记录；保留取证副本。

SQLite 模式使用 assets/storage.sql 与 audit_storage.py 的事务导入/快照导出，具体表/文件映射以 storage.md 为准。源文本可保留在文件系统，SQL 保存引用与原始 JSON payload。给 Git 的文本快照包含证据与决策；音频、运行中数据库、WAL/SHM、密钥不跟踪。media 符号链接本身也要被忽略；已跟踪媒体要单独处理，脚本不自动提交、推送、上传或删除。

## 2. 来源与规范化

目录 `sources.jsonl` 最小字段：

```json
{"source_id":"src_001","title":"示例标题","source_url":"https://example.org/item/1","published_at":"2025-03-01T12:00:00+08:00","content_path":"sources/src_001.md","status":"ready","content_hash":"64-character-sha256","language":"zh"}
```

status=`ready|pending|failed|skipped|truncated`。获取失败保留原元数据与 error/retry 信息；日期未知留 null，由 planner 排除并报告。真实时间未知时只记录日期精度，不猜时间。scope 按发表时间筛选；如发表时间早于用户范围，即使其中预测到期日在范围内也不自动纳入。

本地规范化 manifest（相对路径以 manifest 所在目录为基准）：

```json
{"source_id":"src_001","title":"示例标题","source_url":"https://example.org/item/1","published_at":"2025-03-01","language":"zh","path":"downloads/001.vtt","format":"vtt","transcript_method":"platform_captions"}
```

支持 txt/md/srt/vtt/json。JSON 可为 `{text,segments?}`、`[{text,start,duration}]` 或转录示例的 `{response:{text,...}}` 包装。不识别时失败，不当作零观点。多语言 language 可保存字符串或列表；无需翻译才能分析，翻译不能替换原句。

Markdown front matter 保存 source_id/title/source_url/published_at/language/transcript_method/raw_hash，可选 `description_origin`（`manifest|info_json`）、`description_locator_id`、`description_sha256`；非空简介作为正文末尾的独立 paragraph 定位段（标注 Uploader description），manifest 可直接给出 `description`，或以 `info_json` 指向相对 manifest 的 yt-dlp info.json，`normalize_sources.py` 读取其 `description` 字段，正文保留 cue/paragraph 编号。可选透传 `media_duration_seconds`、`transcription`（转录引擎/模型/VAD 等对象）与 `quality_flags`（合并自动检测的 `stt_tail_hallucination` / `stt_repeated_cue_hallucination` / `stt_duration_overflow`），明细诊断写入 `sources/<id>.locators.json`。source_url 本地来源可为 null。具体字段以 normalizer 的结果为准；不以文件名中的日期推断发表日期。source_id 用字母数字下划线连字符，不允许路径穿越。

切片需增加 parent_source_id、segment_index、start/end 原文位置和 overlap 范围；片段 ID 不算新一期。覆盖统计按 parent_source_id 回卷，逐片段证明并集覆盖父文本。相同自动字幕滚动片段可去技术重叠，但原始字幕保持不动，并保留原 cue 映射；真实重复表达不能误删。

## 3. 观点、出现记录和证据

在 assets/audit.schema.json 的 `$defs` 中选择 claim、occurrence、evidence、coverage 验证单条对象。它允许扩展字段；字段含义不能任意变化。schema 只保证结构，不保证语义真实。

### Occurrence

每次出现至少保存 occurrence_id、claim_id、source_id、speaker、original_quote、context_before/context_after、locator、endorsement、language。

locator 包含 kind=`timestamp|paragraph|character|page`、start、end；单位和字符编码定义可扩展，时间用相对原媒体的秒数，不是切片内部秒数。自动转录无时间戳时使用段落，不伪造视频秒数。引用要在 raw 或规范化文本中找回；必要时 raw_locator、normalized_locator 同时保存。

endorsement=`endorsed|quoted|rejected|mocked|unclear`；转述别人的断言不自动算主讲人的。`mocked` 表示说话者以讽刺、挖苦或反讽方式复述传闻（如把“据消息人士透露”拿来取笑），本人并不认可；它与 `rejected` 一样不进入个人分数，也不计入个人误报或传闻扣分。引用包含的可观察事实（如“某人曾说 X”）可以另建一条关于引述准确性的 claim。

### Claim

每行一个 canonical claim（跨语料重复归并）；至少保存：

- 身份：claim_id、subject_id、occurrence_ids、text、domain、claim_type。
- 归属：empirical、endorsement、attribution_confidence=`high|medium|low`。
- 两条轴：quantifiability、verifiability；含糊和偏好不能混为一类。
- 出处与可查证度：可选 `citation_status`（`primary_cited|secondary_cited|uncited_specific|uncited_vague`，或 null）与 `citation_text`（说话者使用的原始出处短语，无则 null）；缺省视为未标注（旧账本兼容）。合并时非法枚举直接报错。
- 来源层级：可选 `cited_source_tier`（`authoritative_primary|reputable_media|low_credibility_or_rumor|unnamed_insider|none`，或 null）。它是 claim 级字段，计分只读 claim 上的值；occurrence 上可同样标注，作为该原话的副本。缺省视为未标注，非法值直接报错。
- 可检验性：accountability_eligible（有原文支持的清晰可操作规则）、criteria。
- 状态：lifecycle、reason、due_for_assessment、outcome、resolved_at、next_check_at。
- 预测难度与时间：可选 `difficulty`（`trivial|moderate|hard|non_consensus`）、`difficulty_score`（1–5）、`difficulty_rationale`（事前评估理由）、`first_stated_at`、`target_date`；带期限预测须满足 `window_end > first_stated_at`，脚本据此计算 `lead_time_days`。
- 概率：evaluation_mode=`categorical|probabilistic|none`、probability、probability_origin=`explicit|inferred|none`、event_occurred。
- 证据：evidence_ids、evidence_quality、review_state=`unreviewed|accepted|needs_review`。
- 验收：正式 resolved 记录关联 acceptance={decision_path,decision_sha256,policy_hash}。adopt_verdict.py 复算已保存票/裁判决定，并将原记录、证据绑定与决定保存后才写入。

字段枚举见 schema。原始 certainty_text 独立保存，不能把“可能”“我非常确定”自动变为 0.6/0.99。可记录模型推断概率用于探索，但 origin=inferred 不进入正式 Brier。

同目标/条件/期限的重复是一个 claim 多个 occurrences。实质修订用新 claim_id + supersedes/family_id 保存；不能把每次重申同一到期预测当独立实验。短期/长期、不同条件、不同对象不能误合并。记录归并理由与复核。

### Evidence

保存 evidence_id、source_url 或 local_path、title、publisher、retrieved_at、published_at（可未知）、available_at（用于 as-of）、observation_start/end、relation=`supports|contradicts|context`、claim_ids、excerpt/structured_data、source_family、方法和变换。不可用/截断说明必须保留。

同一统计机构的多家转载用同一 source_family；不能伪造独立性。动态页面/修订数据记录快照哈希与版本。保存访问允许的最少必要摘录与结构化数值，不因为审计就全量转存受限资料。

### 访问日志与媒体

source_access 每项记录 access_id、task_id/source_id、request_kind、query、url 或 local_path、attempted_at、outcome（成功/失败/访问受限/截断）、adopted、evidence_ids、capture_refs/引用位置/获取版本、排除理由。最终没采用和搜索无结果同样记录。可用的网页工具只返回部分内容时如实标记，不能声称看了全文。查询日志不含访问令牌、cookie 或秘密参数。

media_assets 记录 media_id、source_id、path/URI、sha256、size_bytes、duration_seconds、storage_mode、retention、transcription_version/文本关联和同步状态。外部目录只表示用户指定位置；未经实际确认不能标 synced。删除后留原路径/哈希、删除时间/原因/授权记录和文本版本，不能让音频消失而账本毫无记录。文件系统允许符号链接仅用于明确配置的媒体位置，不能拿来源提供的任意路径绕开文本/结果路径限制。

## 4. 冻结规则与状态

criteria 为 null 或：

```json
{"version":"1","frozen_at":"2026-11-25T09:00:00+08:00","definition":{"target":"示例机构的项目发布","predicate":"截止时刻前已公开提供正式版本","window_start":"2025-01-01T00:00:00+08:00","window_end":"2025-12-31T23:59:59+08:00","timezone":"Asia/Singapore","condition":"unconditional","resolution_basis":"explicit","interpretation_notes":[]},"sha256":"对 definition 规范 JSON 的 SHA-256"}
```

规范 JSON：Python `json.dumps(definition, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`，再 SHA-256。definition 可扩展数值阈值、单位、容差、基线/复权口径、触发时间、资料发布日期/版本要求。保留原期限用词；若推断规则，resolution_basis=interpretation，并写理由和歧义。

冻结版本保存在 criteria/；任何变更另建版本，不为改善评分改阈值。旧判定留 history/，新报告引用新版本。原 speaker 后续撤回与审计者修正是不同事件。

pending 不到期/等待条件时 due_for_assessment=false；到期但数据未发布为 awaiting_evidence 且 due=true；事实存在明确规则通常立即 due；unscorable 不进入到期核验分母。resolved 必须有规则、证据与 resolved_at；categorical 的 outcome 为 supported/contradicted/mixed/indeterminate，probabilistic 的 outcome 可 null，但 event_occurred 必须布尔值。仅有概率措辞的预测不进入分类正确率。

evidence_quality={directness,independence,traceability}，各值 0/0.5/1，附可扩展 rationale。它衡量本次证据，不是被评人的道德/能力。review_state=accepted 代表按风险规定完成复核，可由同一 agent 的独立检查轮次完成，不强制人类逐条批准。

## 5. 覆盖、费用和导出

coverage.json：

```json
{"schema_version":1,"eligible_sources":100,"acquired_sources":90,"extracted_sources":85,"inventory_complete":true,"unresolved_review_issues":0,"sampling":"census"}
```

eligible 是范围内应处理的父来源数；acquired 为取得完整可用文本数；extracted 为**完整提取**且审查 coverage 通过的父来源数。取不到、缺日期、目录分页不全要另列原因。获取率=acquired/eligible；提取覆盖=extracted/eligible，不用取得数做分母掩盖漏项。inventory_complete=false 不计算综合分。

默认自定义综合指数门槛由 score_claims.py 执行；不满足返回 null + 阻塞理由。评分脚本不自动联网核验，不把结构验证误当质量证明。看 methodology.md 理解阈值和重复样本限制。

costs.jsonl 为事件账本，重复 cost_event_id 只能计一次。金额币种明确、usage 原样保存；估计和实际不能相加双算同一请求，更新使用 supersedes_event_id。见 budgeting.md。

可使用 `score_claims.py --csv PATH` 输出扁平观点表；数组/对象编码为 JSON 字符串。CSV 不包含全部关系，JSONL 为可恢复的真源。不要将 API key、cookie、签名链接凭证写入 manifest/报告。

## 6. 未来插件/服务接口

保留四个可替换边界：SourceProvider（list/fetch）、Transcriber、EvidenceProvider（query/fetch）、ModelRouter。它们由宿主提供，技能定义输入输出和审计契约，不在此包实现特定行情服务。

宿主可将相同记录导入 SQLite/Postgres，或通过 Kunkun 的任务与模型服务执行；此时保持稳定 ID、版本、任务幂等、单写者/事务与成本事件。不要让当前本地使用依赖未来服务。
