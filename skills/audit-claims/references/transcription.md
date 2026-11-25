# 转录与成本控制 / Transcription and cost control

目录：输入选择 · 估算与授权 · 示例脚本 · 输出与续跑 · 模型差异 · 质量检查 · 参考来源。

## 输入选择

1. 优先使用用户已有的文本、字幕及允许访问的 transcript；保存原始版本，不把平台自动字幕当成已校对原文。使用 `yt-dlp` 下载 YouTube 自动字幕时，优先选择 `--sub-format srt`（直接输出干净的单行无滚动 cue）；若保存 `.vtt`，规范化时传入 `normalize_sources.py --clean-youtube-vtt` 清理行内时间戳标签与双行滚动重复。
2. 文本缺失时，先列出音频清单、语言、总时长和预期精度。比较已安装的本地模型与获准使用的云端服务。根据口音、混合语言、专有名词、数字与否定词，选取有代表性的短片段测试；样本转录若收费，也先取得授权。
3. 本地运行没有云 API 账单，但应估计设备资源和耗时；不要未经授权下载几十 GB 模型或安装大型依赖。
4. 使用任意本地或云端 STT 均可；将结果转换为统一源文本格式。下面的 OpenAI 示例是可替换的工具，不是分析方法的依赖。

## 估算与授权

对**每次新分析**重新盘点缺少字幕的音频，排除已转录缓存，计算：

`预计 STT 成本 = 待转录分钟数 × 当前每分钟价格`

按 token 收费的模型若只有分钟近似报价，应标明是估算；保存官方原价、价格来源、核验日期、币种和换算假设。不要把 API 订阅与对话订阅视为同一个免费额度。完整分析还要估算提取、核验搜索、复核和报告的成本；本示例仅核算 STT。

向用户展示媒体数量、独立音频数量、总分钟数、模型、价格依据、基准估算、缓冲后估算、预算上限和云端上传范围。用户确认后开始收费请求。只有明确的“不要在意费用，直接跑”或等价授权，才可以使用 cost waiver；仍记录用户原话及适用范围。已有授权覆盖当前操作时不要重复询问。若用户另设硬预算，waiver 不会自动取消该预算。

每完成一个文件更新已用估算、剩余估算与最终投影。默认超出初始估算的 `max(初始估算 × 25%, USD 1.00)` 时告警并暂停后续收费请求，等待修订授权；相对阈值是初始估算的 25%，绝对阈值为 1 美元，与整体审计的默认策略一致。明确 waiver 可允许偏差告警后继续；硬预算一旦超限仍暂停。可以在估算阶段配置这些阈值。退款、税项、汇率和供应商最终账单不在此估算内。

## 示例脚本

`scripts/transcribe_openai.py` 使用 Python 3.10+ 标准库，不依赖 OpenAI SDK。可选的 `ffprobe` 用于读取真实时长。它接收本地音频，不负责从平台下载媒体。

清单是 JSONL，每行一份音频；相对路径以清单目录为基准：

```jsonl
{"id":"episode-001","path":"audio/episode-001.mp3","duration_seconds":1800,"language":["zh","en"],"source_url":"https://example.org/episode-001"}
{"id":"episode-002-part-01","path":"audio/episode-002-part-01.m4a","duration_seconds":600,"language":"zh"}
```

`duration_seconds` 必须是已知正数；使用 `--probe-duration` 时以 ffprobe 实测代替清单值。`language` 可省略，表示自动检测；推荐模型可以接收多个语言提示。分片的父源 ID、起始偏移、重叠区间另外保留在媒体清单里，归一化时换算回原视频时间。

先通过供应商当前文档确认模型和价格。下面的环境变量由用户或 agent 在验证后填入；脚本不内置固定单价：

```bash
python3 scripts/transcribe_openai.py estimate \
  --manifest /absolute/run/audio.jsonl \
  --model gpt-transcribe \
  --usd-per-minute "$STT_USD_PER_MINUTE" \
  --price-source "$STT_PRICE_SOURCE_URL" \
  --price-checked-at "$STT_PRICE_CHECKED_AT" \
  --budget-usd 10 \
  --output /absolute/run/stt-estimate.json
```

`STT_PRICE_CHECKED_AT` 使用 `YYYY-MM-DD`。`estimate` 不发网络请求，也不需要 API key；输出成本摘要和完整 JSON 计划。默认增加 30% 估算缓冲，报价有效期 24 小时，并拒绝超过 7 天的价格核验记录。可使用 `--valid-hours` 和 `--safety-multiplier` 调整已讨论的计划。过期后重新核验和估算，不要偷偷修改已批准的价格。原有授权仍覆盖相同范围、预算和可接受偏差时直接沿用，不需要重新取得一次笼统许可；只有超出授权范围或触发实际费用偏差条件时才询问用户。

用户已经审阅并批准这份计划后，将 key 配置在运行进程的 `OPENAI_API_KEY` 环境变量里，不要写入清单、代码或日志；然后执行：

```bash
python3 scripts/transcribe_openai.py run \
  --approve-estimate /absolute/run/stt-estimate.json \
  --approval-note '用户已批准此估算和 10 美元上限；记录对应的对话日期与范围' \
  --state-dir /absolute/run/stt
```

用户确实明确免除费用确认时，以 `--cost-waiver /absolute/run/stt-estimate.json` 替代 `--approve-estimate`，并在 `--approval-note` 中记录真实授权。这不是 agent 为省事自行添加的参数；也不是平台级扣款许可机制。无硬预算的 waiver 计划可在 `estimate` 时省略 `--budget-usd`，有预算则始终保留。

计划 SHA-256 绑定模型、参数、价格、预算、文件哈希和清单哈希；执行时重新检查。修改文件、清单、单价或参数需要新估算。哈希提供一致性检查，不证明用户授权；授权依据仍是实际对话。脚本不支持自定义 API host，凭据仅发送给官方 HTTPS endpoint，拒绝重定向。

## 输出与续跑

输出位于 `--state-dir`：

| 路径 | 内容 |
| --- | --- |
| `responses/<request_key>.json` | 原始 JSON 响应、供应商 request ID、保存时间；可能包含敏感原文 |
| `items/<request_key>.json` | 请求状态、音频身份、usage、费用估算、输出哈希 |
| `events.jsonl` | 授权、请求开始、完成或不确定结果的追加事件 |
| `cost-summary.json` | 完成量、剩余量、投影成本与 `actual_usd: null` |

向归一化脚本传递 `responses/*.json` 中的 `response` 对象，或先取出该对象。外层字段记录运行元数据。普通 JSON 不一定含词级时间戳；缺失时保留段落定位，不推算虚假的时间戳。

恢复使用**同一个 state directory**和仍有效的已批准计划，已成功且哈希一致的请求直接复用。相同音频与请求参数只调用一次，重复来源记录为 aliases。不要换一个空目录“重试”，否则失去付费请求去重记录。过期计划可以重新估算，并在已有或更新授权范围内仍使用原 state directory。

请求发出前落盘 `submitting`。网络超时、进程中断或 HTTP 错误会留下待核对状态，脚本不自动重试。若完整响应已落盘而状态更新前崩溃，可恢复响应；若无完整响应，应先查供应商 usage/request ID、现有输出和事件，再记录核对结果。这个示例不提供自动清除不确定状态或自动重试按钮。若人工核对后确实需要再次付费，应保留原状态与事件，先从剩余预算中扣除已发生或仍可能发生的费用，再为重试建立独立、获准的计划；不能通过删状态文件或换目录来假装没有发生过请求。没有确认的失败请求不能当成零成本。强制终止留下 `.run.lock` 时，先确认原进程已经停止，再移除过期锁；不要并行运行两个写入同一目录的实例。

费用字段明确区分估算与账单。API 返回 duration usage 时，以实际处理时长重算**估算**；只有 token usage 时保存 tokens，但此通用分钟报价示例不能据此算出精确费用。`actual_usd` 始终为 null，最终账单需另行核对。预算是基于已知价格和时长的请求调度防线，不能保证供应商实际扣费绝不超过金额；需严格财务上限时，也设置供应商账户级限额。

## 模型差异与大文件

截至 2026-11-25 的官方说明：[文件转录指南](https://developers.openai.com/api/docs/guides/speech-to-text)推荐 `gpt-transcribe`，其语言提示参数为 `languages`；旧模型使用 `language`。脚本自动映射常见模型，未知型号需先核验官方接口再显式传入 `--language-field`，不能只猜型号。

[API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create/)说明各模型的输出能力不同；脚本默认使用 JSON。确有词/段时间戳需求时，需选择支持的模型或外部对齐工具。本示例的 `--timestamps word segment --response-format verbose_json` 仅允许兼容的 `whisper-1`；普通 `gpt-transcribe` 示例不会声称输出词级时间戳。官方文档已将上述旧一代模型标为弃用并列出 2027-02-26 关闭计划，运行时重新确认可用性，避免为一个时间戳功能选用即将停用的依赖。

官方指南列出上传大小上限 25 MB；脚本保守使用 25,000,000 字节，超出便在任何收费调用之前退出。先压缩或分片，尽量在停顿处切分；若使用短重叠，保存全局偏移并在合并文本时去重。时长估算要包含重叠部分，不能漏算。下载、切片与转录均可以批量编排；该参考脚本有意按清单逐个发送收费请求，以便即时检查预算和保存状态。大规模并发可由外部调度器实现，但必须共用原子预算预留和同等请求去重机制。

## 质量检查

抽检数字、日期、单位、专有名词、否定词与说话人归属。对混合语言、方言、多人重叠以及低质量录音增加抽检。不确定片段保留原文和定位，使用 `transcript_uncertain` 标记；不要让 STT 错字变成说话人的错误。静音或空转录不作为观点；对返回文本异常短的长录音检查是否截断。把转录模型、运行时间、原始音频哈希和质量标记写入源文件元数据。

## 参考来源

接口核验日期：2026-11-25；价格须每次运行重新确认。

- [OpenAI 文件转录指南](https://developers.openai.com/api/docs/guides/speech-to-text)：模型选择、语言提示、文件大小、格式与时间戳。
- [Create transcription API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create/)：请求与响应字段、duration/token usage。
- [GPT-Transcribe 模型页](https://developers.openai.com/api/docs/models/gpt-transcribe)：当前模型能力及按分钟价格。核验时页面列出 USD 0.0045/分钟；这是有日期的参考值，不是脚本默认值或未来报价。
- [OpenAI 价格](https://developers.openai.com/api/docs/pricing)、[弃用计划](https://developers.openai.com/api/docs/deprecations)：开始新分析前重新确认。
