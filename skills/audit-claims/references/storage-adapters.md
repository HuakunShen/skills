# 存储无关的数据模型与展示适配

## 目录

1. 选择真源、工作快照和展示位置
2. 逻辑实体与关系
3. 后端映射建议
4. 适配器最小契约
5. 增量同步与限流
6. Notion 可浏览工作区
7. 媒体和保留策略

## 1. 选择真源、工作快照和展示位置

数据格式不是这个 skill 的业务逻辑。先确定 schema、身份、版本、证据链和任务状态，再把它们映射到用户选择的后端。

启动时在 `config/storage-selection.md` 集中确认：

- 哪个后端是真源：JSONL（默认）、SQLite、Postgres、Notion、Google Sheets、Obsidian/纯 Markdown 或 custom？
- 计算时是否需要本地 JSONL 工作快照；哪些数据可以下载到本机？
- 用户希望在哪里浏览全文、表格、关系和报告？可以与真源不同。
- 现有目标文件夹、vault、页面/数据库、spreadsheet 或 SQL 连接 profile 是什么？不猜 ID，不保存密码。
- 是否双向编辑、如何处理用户手改、谁拥有某个字段、哪些字段不能覆盖？
- 文本是否由 Git 跟踪；媒体存储位置、保留/清理策略与同步要求？

在 `config/storage-policy.json` 添加 `canonical_backend`、`working_format`、`presentation_backend`、`target_references`、`field_mapping`、`conflict_policy`、`media` 和 `retention`。字段可以扩展现有本地适配器配置。一个实体版本在一轮处理中只认一个真源；不得让同一行的 Notion 与 JSONL 同时互相覆盖。

本包提供 JSONL/SQLite 的**本地参考实现**。其他后端遵循本协议，由用户已授权的 connector、已有代码或 AI 在该项目中编写的适配器实现；未完成适配或未验证写入时不能宣称已保存到外部系统。不要为适配器自动申请新订阅、建立新账号或公开共享。

## 2. 逻辑实体与关系

不论后端都保留逻辑 ID，不能把可变标题、Sheet 行号、Notion page ID 或 Markdown 文件名当唯一业务身份。

| 实体 | 逻辑主键 | 主要关系和内容 |
| --- | --- | --- |
| Run | run_id | subject、范围/截止、模型/存储策略版本、预算、数据快照 |
| Subject | subject_id | 人/机构、账号别名；避免同名混淆 |
| Source | source_id | 属于 Run；URL、发表日期、原始/规范全文、哈希和获取状态 |
| MediaAsset | media_id | 属于 Source；路径/URI、哈希、音频时长、转录关联、保留/删除状态 |
| Occurrence | occurrence_id | Source → Claim；原话、上下文、说话人、时间戳/段落 |
| Claim | claim_id | Subject → 多个 Occurrence；类型、可验证性、状态、版本/family |
| CriteriaVersion | criteria_id/version | Claim；冻结规则、期限/条件、定义哈希 |
| Evidence | evidence_id | 多对多关联 Claim；URL/本地资料、摘录/数值、时间及版本 |
| SourceAccess | access_id | Task/Claim；所有查询/访问/失败，不限被采用来源 |
| Review | vote_id/review_id | Claim 或 ReportSnapshot；模型、输入/规则哈希、原判断/分数/依据 |
| Decision | decision_id | 多个 Review；共识/裁判/用户裁决、异议及采用理由 |
| Task | task_id | Run、输入/输出、依赖、状态、attempt、幂等键和费用 |
| CostEvent | cost_event_id | Task/model；usage、估计/实际/未知和修订 |
| ReportSnapshot | report_id | Run/冻结数据；确定性指标、模型分布、最终报告、限制 |
| Stance（可选） | stance_id | Subject/议题/时期；原话、认可程度、平台覆盖与局限 |
| StanceTransition（可选） | transition_id | 前后快照；变化类型、条件/对象、解释和证据 |
| RubricReview（可选） | review_id + dimension_id | 固定 rubric、0–10 或 null、支持案例/反例及裁判 |

共同字段按需包括 `schema_version`、`record_version`、`content_hash`、`created_at`、`updated_at`、`supersedes_id`、`run_id`。后端映射另存 provider_record_id、provider_version/etag、last_synced_hash。保留多对多关系，不把多个来源拼成一个无法解析的自由文本字段。

可选纵向/主观实体的详细字段见 longitudinal-analysis.md；本地 SQL helper 的固定核心表不自动增加这些表。它们可保留为关联的纵向账本/报告快照文件，或由所选后端适配器显式扩展实体映射并验证写回，不能把未导入的记录说成已经存在 SQL 中。

## 3. 后端映射建议

以下是建议的数据映射，不是已实现或已连接的远程服务：

| 后端 | 推荐映射 | 处理重点 |
| --- | --- | --- |
| JSONL | 每实体一份账本；正文 Markdown；关系用逻辑 ID | 单协调者、原子写入、版本快照、可直接 Git 审查 |
| SQLite | 对应表、索引、JSON payload 与事务；全文可文件引用 | 单写者、备份/完整性、导出可审阅 JSONL，媒体不入 blob |
| Postgres | 对应关系表、外键与必要 JSONB；事务/版本比较 | 参数化 SQL、最小权限连接、迁移、幂等 upsert、变更审计 |
| Notion | 按实体建数据库/数据源，关系字段连源文、观点、证据和评审；长文本放页面内容 | 逻辑 ID 属性、provider ID 映射、分段全文、增量队列、关系回读和内容哈希 |
| Google Sheets | 每实体一个 tab，ID 列和独立关系 tab；长文本可另存文档并链接 | 行号会变；用 ID 查找，不靠位置；批量写、公式注入防护、长度/配额检查 |
| Obsidian/Markdown | 每条记录独立 Markdown，YAML 属性存稳定 ID/版本；正文放证据/分析，链接表达关系 | 独立索引、文件改名映射、关系检查、媒体位置/附件策略 |
| Custom | 实现同样的 ID、版本、遍历、读写、关系和导出契约 | 明确不支持的能力并提供可恢复替代方案 |

不要把长 transcript 塞进一个 SQL 名称列、单个 Sheet 单元格或一个 Notion 属性。定义正文位置、片段顺序/父来源、完整性哈希，使全文能浏览、检索和重组。量大时用页面分段/子页或文档附件，保留明确目录，不静默截断。

## 4. 适配器最小契约

宿主或 AI 编写的适配器至少实现：

```text
describe_capabilities() → transactions, conditional_write, bulk, limits, text/media support
list_records(entity, cursor, filters) → records + next_cursor
get_record(entity, logical_id) → canonical payload + backend revision
upsert_record(entity, logical_id, payload, expected_revision, idempotency_key)
append_revision(entity, logical_id, revision_payload)
write_body(source_id, ordered_segments, expected_content_hash)
resolve_links(logical_ids) → observed provider references
export_snapshot(run_id, version) → bounded canonical working records + manifest/hash
verify_write(logical_id, expected_hash) → saved version/URL
```

非事务后端采用 outbox + 单写者 + 写后校验：先完整保存本地不可变操作，再按幂等键执行，核对远端 ID/哈希，再推进 checkpoint。权限和版本冲突是阻塞状态，不能删版本条件强行覆盖。出现用户改动先读新版本，保留双方变更，按已约定字段所有权合并。

如为了使用本包脚本导出 JSONL，明确它是**有版本的工作快照**。处理完成后把变更与依赖/哈希通过适配器增量写回真源，再回读验证；不能因为本地生成报告就声称 Notion/Sheets 已更新。远端写回失败仍保留本地结果与未同步队列，报告准确位置和状态。

## 5. 增量同步与限流

保存 `sync/entity-map.jsonl`（逻辑 ID ↔ provider ID）和 `sync/outbox.jsonl`（operation_id、实体、版本、payload_hash、依赖、attempt、status、next_retry_at）。先建父实体，再建关系；所有查询分页完成。对失败写入先查是否已生效再重试，避免同一观点出现两个页面。

只同步哈希变化的记录，合并小更新，按当前 API 能力选批量大小。尊重 Retry-After，指数退避加抖动，限制并发和次数；把阻塞时间存为下次调度时刻，不长时间卡死对话。无响应的创建请求不盲目再创建，先用逻辑 ID/已保存 provider ID 对账。失败、访问受限和内容截断都保留状态。

**核验于 2026-11-26 的 Notion 官方说明**：连接请求预算按套餐区分，Business/Enterprise 为 600/min，其他为 180/min；数据源查询另有限制，且工作区共享限额也会生效。官方要求处理 429/529 与 Retry-After。付费不意味着无限调用；运行时重新核实所用 API/连接的当前规则。[Notion request limits](https://developers.notion.com/reference/request-limits)

Google Sheets 的当前请求配额和退避说明见 [官方使用限制](https://developers.google.com/workspace/sheets/api/limits)。不要把不同 provider、MCP 与 REST API 的配额混为同一限制。

本段设计可用于先批量完成计算再逐步同步显示。若用户指定远端为唯一真源，必须按快照版本写回并验证后才把该轮标完成；镜像同步可以单独 pending，但报告必须说明。

## 6. Notion 可浏览工作区

可以把 Notion 作为用户选定的真源，也可以作为展示层；它不是默认必需品。建议建立一个审计主页，包含：

- **Sources**：每期一页，可读 transcript、源 URL、发表时间、缺失/转录质量与关联观点。
- **Claims**：按 Pending/Resolved/Disputed/Unscorable 看板与表格，点开可看原话、规则与历史。
- **Evidence**：来源、相关时间、采用数值/摘录、支持/反证关系，可回跳多个 claims。
- **Reviews & Decisions**：各模型独立判断、分歧、裁判理由、用户决定，保留初始版本。
- **Reports**：审计总览、客观指标、模型间评分散点/范围、最终判断、成本和覆盖缺口。

正文与关系是用户实际可读的内容，不只是后台 ID。实现时使用当前工具实际返回的数据库/数据源 schema 和页面 ID，先验证少量导入、长正文与关系回读，再排队全量同步。不要在本次创建 skill 时直接创建用户的 Notion 数据库；实际审计用户选择目标后再执行。

## 7. 媒体与保留

无论真源放何处，媒体单独按 storage.md 管理；Notion/Sheet/SQL/Markdown 记录来源、URI、哈希、转录版本和保留状态。用户可选择本地、挂载网盘、对象存储或不长期保留。现有同步文件夹不等于已成功云同步，签名下载 URL 不是永久身份。

Git 只跟踪用户选择的文字/配置/快照，媒体与敏感凭据忽略；公开仓库还需遵守私有资料的现有访问范围。删除或移动媒体后保留 tombstone，不能破坏从结论到原话和来源的追溯。
