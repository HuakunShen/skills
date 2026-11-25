# 相关现成 skills 与取舍

核查日期：2026-11-26。以下是阅读公开 SKILL.md、项目说明与可获取许可证后的设计参考，不代表已安装、运行或验证第三方效果。本包没有复制这些项目的代码或正文。以后选依赖时重新核查版本、许可证、实际可用工具与预算。

## 事实核查

| 候选与一手文件 | 已观察到的能力 | 对本任务的取舍 | 许可证核查 |
| --- | --- | --- | --- |
| [petar-nauka/fact-check-skill](https://github.com/petar-nauka/fact-check-skill/blob/main/SKILL.md) | 分类 claim、逐条 evidence ledger、来源独立性、JSON schema 与 HTML 卡片 | 最适合参考短文核验与证据展示；没有看到本方案完整的多年语料/到期预测/严格多模型验收链 | [MIT](https://github.com/petar-nauka/fact-check-skill/blob/main/LICENSE) 已读 |
| [akitaonrails/my-skills · fact-check](https://github.com/akitaonrails/my-skills/blob/master/fact-check/SKILL.md) | 廉价 headless CLI checker、分组逐条查一手来源、结构化结果与成本日志 | 很接近低成本分工；原场景是文章发表前审阅，不能直接替代人物长期档案 | 本次未在所查根目录/skill 文档确认明确许可证；不默认可复制分发 |
| [scdenney/open-science-skills · fact-check](https://github.com/scdenney/open-science-skills/blob/main/plugin/skills/fact-check/SKILL.md) | 逐篇本地 Markdown 来源、引文预检、覆盖检查与原文片段支持 | 适合参考“有链接”和“来源支持此说法”的区别；范围是已整理资料中的论文核查 | [CC BY-NC 4.0](https://github.com/scdenney/open-science-skills/blob/main/LICENSE) 已读 |
| [conorbronsdon/fact-check](https://github.com/conorbronsdon/fact-check/blob/main/README.md) | 文章发布前提取并核验事实，附命题表、来源与辅助提取/引语脚本 | 轻量短文用例；项目明确不判断预测或意见，不能替代本技能的分类与预测流程 | 本次未成功读取 LICENSE；仅作为公开方法参考 |

## 预测与多模型

| 候选与一手文件 | 已观察到的能力 | 对本任务的取舍 | 许可证核查 |
| --- | --- | --- | --- |
| [LucioLiu/track-record](https://huggingface.co/datasets/LucioLiu/track-record/blob/main/SKILL.zh-CN.md) | agent 自己预测的 Markdown 台账、可观察触发器、到期复核、独立上下文结算 | 适合参考 pending 的责任人/复查纪律；排除不可观察观点，且不自带统计后端，不适合直接分析第三方全部观点 | [项目说明](https://huggingface.co/datasets/LucioLiu/track-record) 声明 PolyForm Noncommercial 1.0.0；LICENSE 正文未成功复核 |
| [microsoft/vscode-team-kit · council-plan](https://github.com/microsoft/vscode-team-kit/blob/main/model-council/skills/council-plan/SKILL.md) | 同任务独立提案、综合共识/分歧、可选匿名二轮讨论 | 用于工程规划；借鉴首轮隔离，保留本技能的用户选模型策略，不照搬固定模型组合 | [MIT](https://github.com/microsoft/vscode-team-kit/blob/main/LICENSE.txt) 已读 |
| [antonbabenko/deliberation](https://github.com/antonbabenko/deliberation/blob/master/plugins/deliberation/skills/deliberation/SKILL.md) | MCP 加 skill，多 provider 意见、blind vote、arbiter、可配置循环/日志与配置指纹 | 可作为未来宿主调用适配层；必须显式启用需要的持久化，不把 provider 失败降级等同本技能的全员一致验收 | [MIT](https://github.com/antonbabenko/deliberation/blob/master/LICENSE) 已读 |

Track Record 同作者提供 [GitLab 仓库](https://gitlab.com/LucioLiu/track-record)，本次实际读取的是其 Hugging Face 镜像。路径或许可证有变化时以当前仓库文件为准。

## 本技能保留的设计决定

本次检索到的候选各覆盖一个局部；没有据此认定存在一个已验证、可直接替代完整需求的包。今后是否组合采用，先对照以下约束：

1. 全部实质观点都保留。不可检验的经验断言影响 accountability；普通偏好不当错误。不能用“只选可核验观点”的筛选方式隐藏分母。
2. 事实核查保存实际证据与访问记录；模型结论或另一模型答案不是事实来源。文章作者自述的证据只证明他说过什么，并不自动证明内容为真。
3. 主动查支持与反证。可参考 adversarial 搜索减少确认偏差，但不预设对象不可信、不以语气激烈代替事实反驳。
4. 原始独立意见、后续讨论、裁判结论分层保存。讨论后的一致不能冒充独立首轮一致；缺席模型不能悄悄移出分母。
5. 每次只调用用户选择的名单。外部工具的 ask-all、自动预设 panel、自动 fallback 需要映射到本轮已授权策略，不能直接沿用默认值。
6. 到期必复查状态；证据不足仍然是证据不足，不为清空 pending 强行判成功/失败。不得替被审计者补概率或事后延长期限。
7. 持久化选项必须实际开启并验证。进程内 session、控制台摘要、短期缓存不能替代可恢复任务记录和完整证据。
8. 本地试用与未来产品化是不同的依赖选择。需要复制或集成第三方材料时先看明确许可证与适用范围；本包目前仅保留链接和独立比较。

要复用第三方组件时，先用与本包相同的合成语料跑一个受控试验，比较漏提、错误归属、证据完整性、到期/未到期状态和实际成本。上述项目功能是文档观察，不能当成实测准确率。
