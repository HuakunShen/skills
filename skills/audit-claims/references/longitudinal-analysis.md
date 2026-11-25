# 跨平台、跨时期的观点变化与主观多维评价

## 目录

1. 分析模式与范围
2. 批量建档与可比性
3. 变化的分类
4. 推荐记录契约
5. 八维评分与独立评审
6. 输出与展示契约

## 1. 分析模式与范围

默认全面报告包括 `fact_check`、`stance_evolution`、`qualitative_review` 三模块，以事实核验为首位；用户可选择其中子集。唯一机器配置真源是 `run.json.rules.analysis_modules`，仍使用同一 sources/occurrences、覆盖、模型策略、成本与恢复契约。`analysis_mode` 如用于展示，只能从该模块列表派生，不独立配置。仅选择纵向/主观模块时可以分析价值立场、解释和修正，不必为了完成报告强行制造可量化预测。

在读取结果前固定对象、账号归属、5–10 年中的具体发表日期范围、平台（如 YouTube/X/blog）、语言、主题集合、时期划分、`as_of` 和抽样方法。用户已有范围优先；缺省沿用主技能最近五年的规则。先盘点全范围，再分批获取与提取；用年/半年等固定时期，不围绕已知争议临时挑窗口。

纯纵向报告要明确“根据已取得原文观察到的立场与表达”。被评人自述“新证据让我改变看法”只能证明他说过这段解释；未经外部核验，不能写成新证据已经成立。展示层把事实前提标为 `not_checked`，canonical claim 仍沿用既有未核验状态，不新增 supported/contradicted 裁决，也不把未核验事实的准确率填 0。

## 2. 批量建档与可比性

1. 先批量提取全部相关观点，再按中性主题与命题归组。建立 `topic_id` 与 `proposition_id`：例如“是否支持在条件 C 下采取政策 P”，不要用“错误政策支持者”这样的评价作分类标签。主题词变更保留别名和版本，不能只检索最后时期的用词。
2. 每次表态连接 occurrence：原话、上下文、说话人、语言、源 URL、时间戳/段落。保留发表时间、确有依据的原发言时间与日期精度；后来引用早年原话时，不能把转载日期当作立场改变日期。时间顺序不明则保留区间或未定关系，不猜具体日期。
3. 分开记 `position=support|oppose|mixed|conditional|neutral|unclear` 与 `endorsement=endorsed|quoted|rejected|unclear`。引用者不自动继承被引用者的立场；“反对某个论证”不自动等于支持相反政策。转发、点赞、沉默或没谈及该主题，单独记录行为，不推断本人立场。
4. 匹配主题后逐项对齐对象、定义、条件、适用时间/预测期限、讨论范围与论述类型（经验事实/价值选择/策略建议）。同一个词不保证同一命题；政策细节变化、不同对象或“短期反对/长期支持”可同时合理存在。
5. 跨平台转载和相同事件重申保留各次 occurrence，但归入同一表达/事件家族；不把十条重复帖当十次独立证据。保留长期没有表态、删除、字幕缺失、私密和平台检索受限的时间段。
6. 对候选转变搜索前后上下文、中间桥接表态、本人解释、反例与纠错；记录所查范围及失败。未找到解释仅写“在已检索材料中未找到”，不宣称从未解释，不推断动机。
7. 保存 `主题 × 时期 × 平台` 覆盖矩阵：发现/符合范围/取得/完整提取的父来源数、独立表态家族数、缺失原因；目录总量未知填 null。显示各格分母，避免用一个高产平台掩盖另一个平台缺口。

先报告观察到的材料，再讨论变化。需要跨期比较时同时给出原始构成与可比主题/平台子集；不同年份主题或平台占比大幅变化时，不将总分变化直接解释为本人质量变化。不因少数精彩或争议片段概括十年；稀疏时期标“材料不足”，没有表态不填 neutral。

## 3. 变化的分类

`relation` 描述两组表态的关系；`reason_tags` 描述可并存的原因，两者分开。例如真实变化可以同时是基于新证据且解释充分的修正。

| relation | 判定条件 | 不应推出的结论 |
| --- | --- | --- |
| `continuity` | 同一可比命题的立场一致，或细化而未改变方向 | 长期不变自动更可信 |
| `genuine_change` | 本人明确认可的可比命题出现实质方向/条件变化 | 改观点就是错误、欺骗或逻辑矛盾 |
| `not_comparable` | 目标、定义、情境或期限不同，无法按同一命题比较 | 挑相反句子拼成“反转” |
| `contradiction` | 归属清晰且同一命题、条件和适用时期无法同时成立，或明确历史自述与原话冲突 | 仅凭两时期偏好不同就判自相矛盾 |
| `unclear` | 原话、归属、时序或可比性不足，合理替代解释未排除 | 用模型直觉补成明确变化 |

`reason_tags` 可用 `context_changed|target_changed|definition_changed|time_horizon_changed|new_evidence|explained_revision|unexplained_revision|historical_self_misreport`；没有足够材料时空数组并注明原因。分别保存作者解释和分析者解释；`new_evidence` 附理由核验状态，不能仅凭该标签证明其证据真实。

**边界例：**“2018 年支持 P、2024 年反对 P”先记 genuine_change；“支持 A 的 P、反对 B 的 P”先检查对象差异；“成本低于 X 才支持 P”与成本上升后的反对通常是条件应用；“新研究改变了我的判断”是可观察的解释，研究质量仍需核验；明确说“我从未支持 P”，却有本人无条件支持 P 的可定位原话，才构成候选历史自述矛盾。价值立场的内容是否符合评审者偏好，不影响表达质量评分。

## 4. 推荐记录契约

以下是纵向扩展的逻辑实体建议；JSONL/数据库映射由运行的存储策略决定，不声称现有全部 helper 已自动创建这些表。保持稳定 ID、schema_version=1、输入哈希与版本；worker 写独立结果，协调者合并。使用 `longitudinal/stances.jsonl`、`longitudinal/transitions.jsonl` 与 `reports/longitudinal.json`，不要改变 claims/occurrences 的既有含义。

### Stance：一次有定位的表态

```json
{
  "schema_version": 1, "stance_id": "st_001", "subject_id": "subject_1",
  "topic_id": "topic_p", "proposition_id": "prop_p_under_c", "proposition": "在条件 C 下支持 P",
  "claim_ids": ["cl_001"], "occurrence_ids": ["occ_001"], "source_id": "src_001", "platform": "youtube",
  "published_at": "2020-03-01", "uttered_at": null, "date_precision": "day",
  "position": "conditional", "endorsement": "endorsed", "attribution_confidence": "high",
  "explicit_position": true, "context": {"target": "P", "condition": "C", "time_horizon": null, "scope": "所讨论地区", "definitions": {}, "discourse_type": "normative"},
  "family_id": "family_p_2020", "interpretation_notes": [], "input_hash": "snapshot-sha256", "review_state": "unreviewed"
}
```

`occurrence_ids` 必须解析到原话、前后文和 locator；翻译仅为附加展示，不替换原句。`discourse_type=empirical|normative|strategic|mixed|unclear`；`explicit_position=false` 表示分析者推断，附依据与替代解释，不混称直接表态。归属不清和纯引述可以存档，但不进入本人明确支持/反对的统计。`uttered_at` 未知为 null，不能自动复制发表时间。

### Transition：两组表态之间的比较

```json
{
  "schema_version": 1, "transition_id": "tr_001", "subject_id": "subject_1", "topic_id": "topic_p",
  "from_stance_ids": ["st_001"], "to_stance_ids": ["st_002"], "observed_between": {"start": "2020-03-01", "end": "2024-04-01"},
  "comparability": {"same_proposition": true, "same_target": true, "same_condition": true, "same_definition": true, "same_time_horizon": true},
  "relation": "genuine_change", "reason_tags": ["new_evidence", "explained_revision"],
  "speaker_explanation_occurrence_ids": ["occ_002"], "analyst_explanation": "本人说明改变了判断，并给出理由。",
  "reason_verification": "not_checked", "evidence_ids": [], "counterexample_occurrence_ids": [],
  "alternatives": [], "limitations": ["两次表态之间的全部材料尚未取得。"], "as_of": "2026-11-25",
  "input_hash": "snapshot-sha256", "method_version": "1.0.0", "review_state": "unreviewed"
}
```

可比性字段为 true/false/null；null 表示不知道，不是 false。`observed_between` 是两次可定位观察之间的区间，不是精确改变日。`reason_verification=not_checked|supported|contradicted|indeterminate|not_applicable` 只评价所述改变理由；若填已核验标签，必须关联正式事实裁定和证据，不能绕过事实验收。反例为空时在 limitations 记录搜索范围与未找到，不能伪造反例。

保留原始提案、替代解释、复核人/模型和决定；修订追加版本或 supersedes，不覆盖旧结论。对低归属置信度、只有摘要、讽刺/引用有歧义的候选，先标 needs_review。存在合理未排除解释时不要输出确定的 contradiction。

## 5. 八维评分与独立评审

使用 [evaluation-rubric.json](../assets/evaluation-rubric.json) 中的八个 0–10 维度与 0/5/10 行为锚点。它们是透明的主观评估规范，未宣称经过心理测量验证。0 是有证据的低端行为，不是没找到资料；10 也不能由一次表现良好或没有发现反例推出。中间值按相邻锚点解释，默认整数，不创造小数精度。

每个分数保存适用语料/时期/主题、理由、案例、反例、反例搜索范围和限制；证据必须与该维度相关。对每维主动寻找支持和反例，说明两者如何影响分数；支持案例指支持该评分的材料，可能是低质量行为，不能误解为只保留赞扬。未找到反例如实记录搜索范围，不虚构；材料只覆盖一个时期时，只给该时期的观察，不包装成十年总分。

没有足够可评分材料、没有相关机会或不适用时 `score=null`，同时给 `missing_reason=insufficient_material|no_relevant_opportunity|not_applicable`。没有预测则预测可操作性为 null；没有可观察纠错机会则更新纠错透明度为 null；没有可比跨期变化/解释机会则跨期立场解释为 null。未发现错误、异议或观点变化本身，不足以给这些维度 10。

“引用依据清晰度”评价**被评人如何交代自己的依据**，不评价本次核验者搜到的证据质量；后者仍在客观审计区域。准确率、Brier、可检验性、样本数、覆盖率和证据质量来自账本，不加入这八维主观雷达。不同政治/价值立场使用相同锚点；不按与评审者立场接近程度加减分。

冻结相同数据快照、主题/时期规则、rubric JSON 的规范哈希与评分范围，只向配置中选定的报告模型派发。各模型独立首轮，不展示他人分数；事实前提有争议时标出并退回核验，不能在主观报告中私自改事实。每份报告按 consensus-statistics.md 的 review 契约保存八个 ID 的 `scores`；用 `rationales[dimension_id]` 保存逐维依据，采用下节的展示契约。

每维报告有效 n、planned_n、各模型原分、mean、median、sample variance、SD、min/max/range；null 不补零。judge 的最终分数与理由另列，保留少数意见与原始报告。少数人为选定且相关的模型只能提供描述性分歧，不从三模型分数生成真实性的置信区间；纵向变化也不以模型票数替代证据。

## 6. 输出与展示契约

`reports/longitudinal.json` 推荐保存 `schema_version, subject_id, analysis_modules, scope, as_of, data_hash, method_version, coverage, topics, stance_ids, transition_ids, limitations`；其中 analysis_modules 是本次 run 配置的冻结副本，不作为另一配置入口。每个 topic 给中性命题定义、各期/各平台覆盖、表态时间线、变化分类、作者解释、分析者替代解释，以及可点开的原话和事实证据。报告需将“未说过”“未找到”“无法判断”分别表述。

展示层可将上述实体投影为 `topics:[{id,label,summary,assessment,entries:[{id,date,stance,claim,quote,context,status,transition:{kind,label,explanation},source_ids,evidence_ids}]}]`；`sources:[{id,title,url,kind,published_at,locator,excerpt}]` 统一索引引用。entry 关联 stance/transition 原 ID；`quote` 从 occurrence 读取，日期不确定与原话/译文标签仍可见。展示模型不回写主账本。

将八维分数以 `panel.reviews` 保存既有 review 字段（同 `data_hash/rubric_hash`、`score_scale:{min:0,max:10}`、`scores`、status、independent）；同一 `panel` 关联实际 policy 和 sealed 状态，judge 另列。每个 review/judge 的 `rationales[dimension_id]={rationale,supporting_evidence_ids:[],counter_evidence_ids:[],missing_reason:null}` 与分数一一对应。此处两个 evidence_ids 数组指展示层 sources 的统一引用 ID，可引用原话或核验证据，不要求纯纵向材料伪造事实 evidence 记录。

数值分必须有理由及至少一个可定位的支持/反例来源 ID；null 必须有 missing_reason。建议在 rationale 项扩展 `case_occurrence_ids,counterexample_occurrence_ids,counterexample_search,limitations`，支持回溯 canonical 账本。缺失理由按本节前述枚举填写；没有找到反例时保留空数组与搜索说明。每轴展示各模型理由、原话与反例，不能只有雷达数字。

纯纵向模式的客观核验区显示“本次未执行”；null 在表和图中显示 N/A/材料不足，不画成原点，不连线暗示完整雷达面积。任何演示分数和虚构示例数据须带 `synthetic=true` 并在图表/报告显著注明，不将其作为真实对象的评分或核验结果。

交付摘要应先说范围与可支持的发现，再展示事实核验（如执行）、主题时间线、八维评分、分歧与限制。默认不合成主观总分；如用户指定权重，提前冻结，说明缺失维度处理并保留分项，不将其称为客观可信度。恢复时加载同一快照/方法/模型策略，继续未完成主题或维度；不重新定义主题来迎合已有结论。
