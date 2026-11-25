# 存储、媒体保留与本地参考适配器

## 目录

1. [先选择存储与保留策略](#先选择存储与保留策略)
2. [本地参考初始化](#本地参考初始化)
3. [媒体路径与挂载盘](#媒体路径与挂载盘)
4. [Git 边界](#git-边界)
5. [SQLite 参考适配器](#sqlite-参考适配器)
6. [访问与媒体账本](#访问与媒体账本)
7. [恢复、迁移和限制](#恢复迁移和限制)

## 先选择存储与保留策略

将**逻辑数据契约、规范数据源、临时工作格式和查看界面**分开。JSONL 是默认选项，不是平台要求。用户可以选择 SQLite、Postgres、Notion 关联数据库、Google Sheets 分表、Obsidian 纯 Markdown 或自定义后端。已有后端优先复用；用对应连接器、用户提供的适配器或 AI 适配步骤完成映射，见 [storage-adapters.md](storage-adapters.md)。本文件及 `audit_storage.py` 仅提供 JSONL/SQLite 的本地参考实现，没有实现其他平台的访问接口。

在大量下载前，记录以下选择，已明确的偏好不要反复询问：

| 决策 | 记录内容 | 未指定时 |
| --- | --- | --- |
| 规范后端 | canonical_backend；jsonl/sqlite/postgres/notion/sheets/obsidian/custom | JSONL |
| 工作格式 | working_format；现有确定性脚本读取的有界快照 | JSONL，不改变规范后端 |
| 展示界面 | presentation_backend；例如 Notion 表、Sheets、Obsidian 或报告 | 可选 |
| 原始媒体位置 | 本地目录、用户提供的已挂载盘路径、指定对象存储 URI | 本地 run/media |
| 原始媒体保留 | 一直保留；或转录验收后按明确授权处理 | 保留 |
| 文本版本记录 | 是否用 Git 记录文本、规则、证据和快照 | 可选，不自动操作 Git |
| 同步与访问范围 | 用户选择的云盘/仓库及可访问者 | 不自动上传或分享 |

同时估算文本与媒体容量；不要在未经选择的云端复制敏感内容。无需为了保存少量本地文本阻塞工作，但外部同步、付费存储、大规模媒体下载和删除应符合已给授权。保留策略与费用许可是不同决策。

## 本地参考初始化

```bash
python3 scripts/audit_storage.py init --run ./runs/example --backend jsonl
# 若用户选择 SQLite 作为本地规范后端：
python3 scripts/audit_storage.py init --run ./runs/example --backend sqlite
```

这是两个**替代示例**；不能对已选择 JSONL 的同一个 run 直接切成 SQLite。`config/storage-policy.json` 和 `config/storage-selection.md` 已存在时保留原内容；不同选择需要明确的迁移步骤，不静默覆盖。

策略记录 `canonical_backend`、`working_format`、`presentation_backend`、`local_reference_adapter`，以及媒体保留和 Git 边界。为兼容本地命令还记录 `backend`/`source_of_truth`。在本地参考初始化中这些均与所选规范后端一致；外部适配器须保持语义一致，不创建两个互相竞争的主数据源。

`--backend notion` 等值会明确报告该参考脚本没有对应接口，转向用户选定的连接器/AI 适配器；这不表示 skill 的逻辑契约只支持两种后端。任何后端都可以导出有界 JSONL 工作快照供现有批处理脚本使用，再按版本与稳定 ID 回写。

默认创建本地媒体目录和 run 内 `.gitignore`。没有网络调用、上传、Git add/commit/push 或删除媒体的命令。

## 媒体路径与挂载盘

明确选择外部目录时：

```bash
python3 scripts/audit_storage.py init --run ./runs/example \
  --backend jsonl --media-root /absolute/path/to/already-mounted-drive/audit-media \
  --link-media
```

路径必须已存在且为目录。`--link-media` 可选；使用时建立 `run/media` 符号链接，不复制目录内容，不自动遍历或读取媒体。链接名冲突时停止，保留原文件/目录。Windows 无符号链接权限时，省略该选项并直接使用已记录的外部路径；脚本不会改用复制大量媒体作为隐式降级。

该目录可以是用户已经挂载的 Google Drive、其他云盘、外接盘或本地目录。**路径可访问和符号链接成立不证明云端同步完成**；参考脚本不会验证云盘上传、配额或远端副本。没有用户提供的有效路径时，不猜挂载点，不触发登录或上传。

只有明确配置的媒体目录允许通过这种方式位于 run 外；文本规范化 manifest 的输入仍必须位于其 manifest 所在目录之下。转录 JSON/文本可以放在相应输入目录后规范化，或把 manifest 放在文本归档的共同父目录。不要为绕过路径检查而批量解引用媒体链接。

保留媒体是默认行为。将来用户授权清理时，应先核对转录文件、来源身份、内容哈希、所需时间戳与抽样质量，再保存删除记录；媒体缺失不能删掉它的资产记录。当前参考 helper **不提供删除功能**。

## Git 边界

适合版本记录的内容包括 SKILL 配置、JSONL/CSV/Markdown、冻结规则、证据索引、小型文本摘录、报告与 SQL 导出的文本快照。大型音视频保存在独立媒体目录或用户指定存储，**媒体目录的符号链接本身也忽略**。

本地 `.gitignore` 排除 `/media`、常见音视频扩展名（兼顾大小写）、SQLite 数据库及其 journal/WAL/SHM、临时/缓存目录、`.env` 等秘密文件。SQLite 二进制数据库默认不进入 Git；它的可比较版本是导出的文本快照。规则只写进 run 的 `.gitignore`，不改上层仓库配置。

```bash
python3 scripts/audit_storage.py check --run ./runs/example
```

位于 Git 仓库时，检查器通过 `git ls-files` 找到已经跟踪的媒体/数据库/秘密文件，并通过 `git check-ignore --no-index` 检验代表性路径。新加 `.gitignore` 不会解除已有跟踪：发现这种情况返回失败并列出路径，交给用户/协调者处理；脚本不修改 Git 索引，也不删除文件。

外部媒体目录如果仍位于同一个 Git 仓库内，检查其已有跟踪及所属位置的忽略规则。run 内规则不能保护位于 run 之外的目录，需要目录所属者明确设置规则。没有 Git 或尚未建立仓库时说明检查范围，不能声称已完成 Git 防护验证。

## SQLite 参考适配器

逻辑实体保留完整 JSON payload；关系 ID 不依赖行号。`assets/storage.sql` 只是通用关系模型的 SQLite 实例，不要求其他后端照搬 SQL 存储形式。

| 表 | 输入/导出文件 | 主键字段 | 参考外键 |
| --- | --- | --- | --- |
| sources | sources.jsonl | source_id | — |
| claims | claims.jsonl | claim_id | — |
| occurrences | occurrences.jsonl | occurrence_id | source_id、claim_id |
| evidence | evidence.jsonl | evidence_id | 证据关联数组完整保留；由审计层验证 |
| review_votes | review_votes.jsonl | vote_id | claim_id（若提供） |
| decisions | decisions.jsonl | decision_id | claim_id（若提供） |
| tasks | tasks.jsonl | task_id | 依赖数组由任务层验证 |
| cost_events | costs.jsonl | cost_event_id | — |
| source_access | source_access.jsonl | access_id | source_id（若提供） |
| media_assets | media_assets.jsonl | media_id | source_id（若提供） |

所有表保存 `id`、`schema_version`、完整 `payload_json`；缺少 schema_version 的旧记录以内部列值 1 兼容，导出时保留原对象，不强行改写其字段。已知关系用延迟外键保证事务提交时一致。SQL 不保存媒体字节；文本来源、证据文件、冻结规则和原始媒体仍是各自的文件/URI。

```bash
python3 scripts/audit_storage.py import-jsonl --run ./runs/example
python3 scripts/audit_storage.py export-jsonl --run ./runs/example \
  --out ./snapshots/example-2026-11-25-v1
```

默认数据库为 `state/audit.sqlite`。可用 `--database state/another.sqlite` 选择 run 内数据库；只接受 `.sqlite`/`.sqlite3`/`.db`，不借此改写 run 外的任意文件。

导入前解析并检查全部存在的输入账本，重复 ID 或非有限数值会失败。**存在的账本文件替换对应表；未出现的账本保持原表；明确空文件会清空该表。** 全部替换位于同一事务，外键失败回滚已改的表。不要把不完整的分片当作完整账本导入；先由协调者合并为完整表快照。

导出在一个只读事务中读取一致快照，写入全新目录。已有目录拒绝覆盖；保存每个 JSONL 的数量、SHA-256 和整体快照哈希。导出不解引用媒体路径，不复制音视频，也不把访问密钥放进快照。

JSONL 作为规范后端时，SQLite 只是可选的查询副本。SQLite 作为规范后端时，先导出一致工作快照，运行现有 JSONL 工具，再由唯一协调者事务导入审核后的修改。原始文本、证据/裁决文件与规则快照必须一并保留，SQL/JSONL 表导出不等于完整 run 归档。

## 访问与媒体账本

每次搜索/抓取尝试立刻记录 `source_access`，失败也记录，不只保留最终成功 URL：

```json
{"access_id":"access_001","source_id":null,"request_kind":"fetch","url":"https://example.org/result","attempted_at":"2026-11-25T12:00:00+08:00","outcome":"success","capture_refs":["evidence/result.txt"],"claim_ids":["claim_001"]}
```

搜索工具没有返回可保存的请求 URL 时，记录 `request_kind=search`、实际 query、工具/提供者与返回引用；URL 可为 null，不能编造。保留重试关系、HTTP/工具状态、错误类别、抓取时间、证据版本/哈希和可获取性。敏感 cookie、API key、签名 URL 凭证不写入 Git 文本；保留稳定资源地址及必要的脱敏访问记录。

媒体资产记录路径或 URI、内容哈希、容量、保留策略、相关转录哈希及删除历史：

```json
{"media_id":"media_001","source_id":"source_001","path_or_uri":"media/source_001.m4a","sha256":"64-character-hex","size_bytes":12345,"retention":"keep","transcription_hash":null,"deletion_history":[]}
```

只有实际计算过才填写 sha256/转录哈希；未知用 null，不能填示例值。保留最后已知位置、存储提供者、同步/可访问状态及验证时间。删除历史记录授权、时间、原因和删除前身份，资产行继续存在。访问日志和媒体资产元数据可映射到任何用户选择的后端。

## 恢复、迁移和限制

所有规范写入由一个协调者执行；本地 helper 复用运行目录锁，SQLite 自身提供事务。外部连接器需要自己的版本前提、冲突检测、分页/限速和幂等处理，不能用该本地锁冒充跨服务锁。

本地 SQL helper 不代替远端后端适配器，不检测未受协调的外部数据库编辑，也不自动把 JSONL、SQL 和云端同时保持为可写主数据源。迁移时固定旧版本、导出/校验记录数与哈希、回读目标，再明确切换 canonical_backend；旧记录保留到验证完成。

建议将活跃 SQLite 文件保留在本地，并同步不可变文本快照；不要通过文件同步服务并发编辑同一数据库。挂载盘暂不可用时先报告路径状态，保留账本和媒体资产记录，不能自动删记录、重新付费下载或静默换位置。
