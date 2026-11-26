#!/usr/bin/env python3
"""Render an escaped, standalone HTML audit dashboard and exact inline-SVG radar.

Python 3.9+ stdlib. No JavaScript, CDN, browser, network or model calls.
The renderer checks presentation consistency; it does not certify input facts.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit

import _common as common
import model_panel as panel
import score_claims as scoring

ROOT = Path(__file__).resolve().parent.parent
THEME = {
    "light": {"background": "#F8FAFC", "surface": "#FFFFFF", "foreground": "#0F172A", "muted": "#64748B", "border": "#E2E8F0", "accent": "#4F46E5", "subtle": "#F1F5F9"},
    "dark": {"background": "#0B0F19", "surface": "#111827", "foreground": "#F8FAFC", "muted": "#94A3B8", "border": "#263248", "accent": "#818CF8", "subtle": "#1E293B"},
    "radius": 10, "font": "system",
}
FONT = {"system": 'ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif', "sans": 'Arial,"Noto Sans CJK SC","Microsoft YaHei",sans-serif'}
COLORS = ("#3B82F6", "#10B981", "#F59E0B", "#EC4899", "#06B6D4")
STATUS_TONES = {"supported": "ok", "contradicted": "negative", "mixed": "warn", "pending": "info", "indeterminate": "violet", "not_checked": "muted"}
RELATION_TONES = {"continuity": "ok", "genuine_change": "accent", "not_comparable": "warn", "contradiction": "negative", "unclear": "muted"}

VIZ = {
    "supported": "#10B981",
    "supported_dark": "#059669",
    "mixed": "#F59E0B",
    "mixed_dark": "#D97706",
    "contradicted": "#F43F5E",
    "contradicted_dark": "#E11D48",
    "pending": "#38BDF8",
    "other": "#94A3B8",
    "indigo": "#4F46E5",
    "violet": "#7C3AED",
    "teal": "#0D9488",
    "sky": "#0EA5E9",
}

SRC_CITATION_KEYS = ("primary_cited", "secondary_cited", "uncited_specific", "uncited_vague")
SRC_CITATION_COLORS = {
    "primary_cited": "#10B981",
    "secondary_cited": "#0EA5E9",
    "uncited_specific": "#F59E0B",
    "uncited_vague": "#F43F5E",
}
DIFF_TIER_COLORS = {
    "trivial": ("#34D399", "#059669"),
    "moderate": ("#60A5FA", "#2563EB"),
    "hard": ("#FBBF24", "#D97706"),
    "non_consensus": ("#A78BFA", "#7C3AED"),
    "unrated": ("#94A3B8", "#64748B"),
}

I18N = {
    "zh": {
        "html_lang": "zh-CN",
        "brand_sub": "/ 研究报告",
        "static_note": "静态报告 · 可离线阅读",
        "nav_title": "报告目录",
        "side_note": "事实核验与表达评价分开。<br>保留原话、分歧与未知。",
        "nav": [("overview", "报告总览"), ("model-panel", "表达评价"), ("longitudinal", "跨期观点"), ("cases", "核验案例"), ("explorer", "全部主张"), ("coverage", "覆盖与成本"), ("sources", "材料与引用")],
        "objective_badge": "客观事实核查 · 证据支撑",
        "subjective_badge": "主观评分 · 归属模型",
        "fact_group": "事实可信度（客观核查）",
        "fact_group_note": "仅统计已采纳裁决的事实型主张，不含预测",
        "pred_group": "预测准确率与难度加权（客观核查 + 事前难度）",
        "pred_group_note": "难度与提前量加权仅作用于已裁决预测；难度为事前主观评级",
        "factual_honesty": "事实诚信分",
        "factual_honesty_note": "证伪扣分重，无据证伪扣分更重；部分支持（混淆）扣分较轻",
        "contradiction_rate": "证伪率",
        "contradiction_note": "已证伪 / 事实型已裁决",
        "misinfo_rate": "无据传谣率",
        "misinfo_note": "证伪且无出处 / 事实型已裁决",
        "diff_adj_score": "难度加权预测分",
        "diff_adj_note": "权重 trivial 0.5 · moderate 1 · hard 2 · non-consensus 3",
        "lead_weighted": "提前量加权支持率",
        "lead_weighted_note": "权重 log2(1 + 提前天数/30)",
        "dated_unit": "条带期限预测",
        "overconfidence": "高确信度差距",
        "overconfidence_note": "整体支持率减去高确信度支持率；正值表示高确信度表述更不准",
        "credibility_legacy": "本次 metrics.json 不含事实可信度或难度加权字段（旧版运行）；用当前脚本重算后即可显示。",
        "backfire_group": "翻车与引用来源（客观核查）",
        "backfire_group_note": "翻车率 = 被证伪 / 可裁定；<10% 绿，10–25% 黄，>25% 红",
        "backfire_rate": "翻车率",
        "backfire_note": "被证伪 / 可裁定事实与预测",
        "prediction_backfire_rate": "预测翻车率",
        "prediction_backfire_note": "仅预测类：被证伪 / 可裁定预测",
        "source_quality": "引用来源可信度",
        "source_quality_note": "按所引来源层级加权：一手 1.0 · 主流媒体 0.75 · 低可信/传闻 0.25 · 匿名内幕 0.1 · 未引 0",
        "channel_group": "YouTube 频道互动健康度",
        "channel_group_note": "yt-dlp info.json 的启发式基准，不是真实性裁决",
        "channel_subs": "订阅者",
        "channel_v2s": "订阅—播放比",
        "channel_like": "点赞/播放",
        "channel_comment": "评论/播放",
        "channel_engagement": "互动率",
        "channel_avg": "逐片均值",
        "channel_flags": "异常标记",
        "channel_videos": "视频样本",
        "channel_benchmark": "基准",
        "channel_status": {"below": "低于基准", "within": "基准内", "above": "高于基准"},
        "channel_flag_labels": {"normal": "正常", "ghost_subscribers": "疑似僵尸或买粉订阅（订阅—播放比 < 1%）",
                                "bot_view_inflation": "疑似刷播放（点赞/播放 < 0.3%）",
                                "engagement_spike": "互动异常偏高（点赞/播放 > 20%）", "insufficient_data": "数据不足"},
        "tl_green": "绿灯", "tl_yellow": "黄灯", "tl_red": "红灯",
        "traffic_legend": "交通灯：正向指标 绿 ≥80% · 黄 60–79.9% · 红 <60%；错误率 绿 <5% · 黄 5–15% · 红 >15%",
        "subjective_models": "评分模型",
        "subjective_avg_multi": "多模型时每维显示平均值（见“平均”列）",
        "subjective_avg_single": "仅一个模型评分，无跨模型平均",
        "subjective_judge": "裁判",
        "subjective_unrecorded": "未记录评级模型",
        "difficulty_raters": "难度评级模型",
        "list_sep": "、",
        "explorer_title": "全部主张检索",
        "explorer_desc": "包含待结算、未核验、证伪与部分支持的全部主张；可离线搜索并按结论或无据情况筛选。",
        "explorer_search": "搜索主张、原话、理由或编号…",
        "explorer_all": "全部",
        "explorer_unsub": "无据主张",
        "explorer_count": "显示 {n} / {total} 条",
        "explorer_empty": "没有匹配的主张",
        "explorer_details": "原话与判定理由",
        "th_claim": "主张", "th_verdict": "结论", "th_lifecycle": "阶段", "th_citation": "出处", "th_lead": "提前量",
        "lifecycle_labels": {"pending": "待结算", "ready": "待核验", "awaiting_evidence": "待证据", "resolved": "已结算", "unscorable": "不可核验", "disputed": "有争议"},
        "nav_long": [("overview", "报告总览"), ("longitudinal", "观点时间线"), ("model-panel", "表达评价"), ("coverage", "范围与限制"), ("sources", "材料与引用")],
        "status": {"supported": "支持", "contradicted": "证据反驳", "mixed": "部分支持", "pending": "待结算", "indeterminate": "无法判定", "not_checked": "未核验"},
        "relations": {"continuity": "持续主张", "genuine_change": "立场更新", "not_comparable": "不可直接比较", "contradiction": "存在冲突", "unclear": "解释不足"},
        "no_fact_check_title": "未执行事实核验",
        "no_fact_check_body": "此视图分析观点随时间的变化；未核验的断言不计为错误，缺失指标不记作零。",
        "strict_support": "严格支持率", "strict_support_note": "已裁定的分类断言",
        "accountability": "可检验性", "accountability_note": "有清晰判定规则的实证观点",
        "adjudication_cov": "裁定覆盖", "adjudication_cov_note": "已到期且完成核验的观点",
        "brier_label": "概率校准 · Brier", "brier_note": "越低越好，仅明确概率",
        "pred_vs_fact": "预测 vs 事实分项",
        "pred_rate": "预测兑现率", "fact_rate": "事实支持率",
        "family_weighted": "按主题簇加权", "families_unit": "个主题簇",
        "scm_detail": "分类结果明细",
        "scm_label": "支持 / 反驳 / 部分 (N={n})",
        "binary_acc_label": "二元支持率 S/(S+C)",
        "evidence_quality_label": "证据质量均值",
        "lifecycle_dist": "生命周期分布",
        "lifecycle_fmt": "待结算={pending} · 待补证={awaiting} · 争议={disputed} · 无法判定={indet}",
        "domain_breakdown": "分领域统计",
        "difficulty_title": "预测难度分层",
        "difficulty_non_trivial": "非平凡预测支持率",
        "difficulty_tiers": {"trivial": "平凡 / 近确定", "moderate": "中等", "hard": "较难", "non_consensus": "反共识 / 高难", "unrated": "未评级"},
        "difficulty_tiers_short": {"trivial": "平凡", "moderate": "中等", "hard": "较难", "non_consensus": "反共识", "unrated": "未评级"},
        "th_tier": "难度等级", "th_claims": "预测数", "th_mean_score": "均分(1–5)",
        "horizon_title": "预测提前期分布",
        "horizon_mean_lead": "平均提前期", "horizon_median_lead": "中位提前期", "horizon_supported_lead": "命中平均提前期",
        "th_horizon": "提前期区间", "th_avg_lead": "平均天数",
        "horizon_buckets": {"le_30d": "≤30天", "31_90d": "31–90天", "91_180d": "91–180天", "181_365d": "181–365天", "gt_365d": ">365天"},
        "verdict_chart_title": "裁定结果堆叠分布",
        "verdict_chart_desc": "按断言类型与预测难度比较支持、部分支持与证据反驳构成",
        "verdict_group_types": "总计与断言类型",
        "verdict_group_difficulty": "按预测难度分层",
        "overall_label": "全部已裁定",
        "claim_types": {"factual": "事实陈述", "prediction": "未来预测", "causal": "因果断言", "hypothetical": "假设情形", "preference": "偏好表达", "value_judgment": "价值判断"},
        "other_unsplit": "非支持(未细分)",
        "diff_chart_title": "预测难度 vs. 严格支持率",
        "diff_chart_desc": "展示从平凡到反共识预测的准确率走势与 95% Wilson 置信区间",
        "diff_nontrivial_ref": "非平凡均值",
        "diff_trend_legend": "准确率走势",
        "diff_ci_legend": "95% Wilson 区间",
        "sourcing_title": "出处与可查证度",
        "sourcing_desc": "每条已采纳实证断言的引用方式：一手可定位出处、二手或模糊出处、无出处的具体数字（张口就来）、无出处的含糊断言",
        "sourcing_chart_title": "出处构成（按已标注断言）",
        "sourcing_chart_desc": "堆叠条按已标注断言的出处类别分段；未标注断言不计入分段，单独列示",
        "sourcing_cats": {"primary_cited": "一手出处", "secondary_cited": "二手/模糊出处", "uncited_specific": "无出处·具体数字", "uncited_vague": "无出处·含糊", "untagged": "未标注"},
        "sourcing_citation_rate": "引用率",
        "sourcing_primary_rate": "一手引用率",
        "sourcing_unsub_rate": "张口就来率",
        "sourcing_checkable_rate": "可查证率",
        "sourcing_legacy": "本次运行未标注出处（旧版账本），出处指标不可计算",
        "sourcing_th_group": "范围",
        "sourcing_th_tagged": "已标注",
        "sourcing_th_untagged": "未标注率",
        "horizon_hist_title": "预测提前期直方图与命中率叠加",
        "horizon_hist_desc": "柱高为各区间预测数（按裁定结果堆叠），折线为严格支持率",
        "horizon_axis_count": "预测数量",
        "horizon_axis_rate": "严格支持率",
        "horizon_pending_other": "待结算/其他",
        "horizon_avg_prefix": "均",
        "boxplot_title": "提前期分布箱线图（支持 vs. 反驳/部分支持）",
        "boxplot_desc": "对比支持预测与反驳/部分支持预测的提前期分布（最小、Q1、中位、Q3、最大与均值）",
        "boxplot_supported": "支持（命中）",
        "boxplot_not_supported": "反驳 / 部分支持",
        "boxplot_all": "全部带日期预测",
        "boxplot_empty": "提前期箱线图需至少 3 条带提前期的预测样本（当前可用：{n} 条）。",
        "boxplot_legend_whisker": "最小–最大",
        "boxplot_legend_iqr": "Q1–Q3 四分位",
        "boxplot_legend_median": "中位数",
        "boxplot_legend_mean": "均值",
        "boxplot_stat_med": "中位",
        "boxplot_stat_mean": "均值",
        "boxplot_axis_days": "提前期（天）",
        "synthetic_banner": "<strong>合成演示数据</strong><span>人物、原话、核验案例与模型分数均为手工构造；未调用真实模型，也不代表真实人物。</span>",
        "mean_legend": "可用评分均值",
        "radar_title": "{n}维表达与可审计性雷达",
        "radar_desc": "零到十分；细线为各模型，渐变粗线为可用评分均值，标签下方徽章为各维均值。缺失值或 n<2 轴保留断点。精确数据见报告表格。",
        "radar_synth_desc": "手工合成演示，未调用真实模型。",
        "radar_synth_foot": "合成演示数据 · 未调用真实模型",
        "date_unknown": "日期未提供",
        "composite_withheld": "综合分暂不发布",
        "composite_blockers_prefix": "综合分暂缓原因：",
        "summary_label": "阅读结论",
        "default_scope_note": "本报告只涵盖已列明的材料和日期范围。",
        "as_of_prefix": "截止",
        "topics_title": "按主题追踪观点",
        "topics_desc": "先核对目标、条件和时间，再判断是连续主张、真实更新还是尚待解释的冲突。",
        "topics_count": "{n} 个主题",
        "panel_title": "表达与可审计性",
        "panel_desc": "独立阅读同一材料，使用同一量表，保留各模型判断与分歧。",
        "panel_badge": "{n} 维 · 0–10",
        "cases_title": "可复查的案例",
        "cases_desc": "原始断言、判定理由与证据一起展示。",
        "coverage_title": "覆盖、费用与限制",
        "coverage_card": "材料覆盖",
        "cost_card": "运行成本",
        "sources_title": "材料与引用",
        "sources_desc": "图表、观点节点和评分依据均可回到这里；材料不足不会自动变成负面结论。",
        "not_provided": "未提供",
        "unknown_cost": "未知 / 未核对",
        "open_source": "打开原始材料 ↗",
        "local_source": "本地或合成材料 · 无公开链接",
        "footer_synth": "手工合成演示 · 无真实模型调用",
        "footer_real": "本页面只格式化已提供的审计结果，不独立证明事实真伪。",
        "panel_empty": "<strong>未进行多模型表达评价</strong>没有评分就不绘制雷达，不以缺失资料代替零分。",
        "panel_note_h": "同一份材料，不同判断",
        "panel_note_p": "评价表达方式与可审计性。事实支持率与 Brier 单独呈现，不混入这个雷达。",
        "panel_completed": "独立完成的评价",
        "panel_models_unit": "模型",
        "panel_max_sd": "分歧最大的维度",
        "panel_insufficient": "样本不足",
        "panel_missing_note": "{n} 个维度存在缺失评分。null 保留缺口；n < 2 时不计算样本方差且不连成多边形。",
        "table_caption": "精确数据 · 统一 0–10 量表；Judge 不参与均值与方差",
        "th_dim": "评价维度", "th_mean": "均值", "th_var": "样本方差", "th_sd": "SD", "th_range": "最小–最大", "th_judge": "Judge",
        "panel_footer": "方差采用 ddof = 1。这里描述模型之间的分歧，不是真实可信度的置信区间；共享训练数据也可能带来共同错误。",
        "expand_rationale": "展开评分依据",
        "support_mat": "支持材料", "counter_mat": "反例材料",
        "judge_review": "Judge 复核", "judge_note": "单列，不计入统计",
        "judge_unrun": "Judge：未完成或未请求；未据此改变独立模型的原始评分。",
        "topic_nodes": "{n} 个节点",
        "topic_interp": "跨期解读：",
        "topic_unexplained": "尚未完成解释。",
        "topics_empty": "尚未提供跨期观点记录。",
    },
    "en": {
        "html_lang": "en",
        "brand_sub": "/ Audit Report",
        "static_note": "Static report · Offline readable",
        "nav_title": "REPORT CONTENTS",
        "side_note": "Fact checks and expression quality are separate.<br>Quotes, dissent, and unknowns preserved.",
        "nav": [("overview", "Overview"), ("model-panel", "Expression"), ("longitudinal", "Longitudinal"), ("cases", "Cases"), ("explorer", "All Claims"), ("coverage", "Coverage & Cost"), ("sources", "Sources")],
        "objective_badge": "Objective fact-check · evidence-backed",
        "subjective_badge": "Subjective rating · model-attributed",
        "fact_group": "Factual credibility (objective check)",
        "fact_group_note": "Adjudicated factual claims only; predictions excluded",
        "pred_group": "Forecast accuracy & difficulty weighting (objective check + ex-ante difficulty)",
        "pred_group_note": "Difficulty and lead-time weights apply to adjudicated predictions; difficulty is an ex-ante subjective rating",
        "factual_honesty": "Factual honesty score",
        "factual_honesty_note": "Contradictions cost points; uncited contradictions cost more; mixed verdicts (conflation) cost less",
        "contradiction_rate": "Contradiction rate",
        "contradiction_note": "contradicted / adjudicated factual",
        "misinfo_rate": "Misinformation rate",
        "misinfo_note": "contradicted with no citation / adjudicated factual",
        "diff_adj_score": "Difficulty-adjusted score",
        "diff_adj_note": "weights trivial 0.5 · moderate 1 · hard 2 · non-consensus 3",
        "lead_weighted": "Lead-time weighted support",
        "lead_weighted_note": "weight log2(1 + lead days / 30)",
        "dated_unit": "dated predictions",
        "overconfidence": "High-certainty gap",
        "overconfidence_note": "overall support minus high-certainty support; positive means high-certainty wording is less accurate",
        "credibility_legacy": "This metrics.json predates factual credibility and difficulty-weighted fields; recompute it with the current scripts to display them.",
        "backfire_group": "Backfire & sourcing (objective check)",
        "backfire_group_note": "Backfire rate = contradicted / adjudicated; <10% green, 10–25% amber, >25% red",
        "backfire_rate": "Backfire rate",
        "backfire_note": "contradicted / adjudicated facts and predictions",
        "prediction_backfire_rate": "Prediction backfire rate",
        "prediction_backfire_note": "predictions only: contradicted / adjudicated predictions",
        "source_quality": "Cited-source quality",
        "source_quality_note": "weighted by cited source tier: primary 1.0 · reputable media 0.75 · low-credibility/rumor 0.25 · unnamed insider 0.1 · none 0",
        "channel_group": "YouTube channel engagement health",
        "channel_group_note": "heuristic benchmarks from yt-dlp info.json, not an authenticity verdict",
        "channel_subs": "Subscribers",
        "channel_v2s": "Views-to-subscribers",
        "channel_like": "Likes per view",
        "channel_comment": "Comments per view",
        "channel_engagement": "Engagement rate",
        "channel_avg": "Per-video averages",
        "channel_flags": "Anomaly flags",
        "channel_videos": "videos sampled",
        "channel_benchmark": "benchmark",
        "channel_status": {"below": "below benchmark", "within": "within benchmark", "above": "above benchmark"},
        "channel_flag_labels": {"normal": "Normal", "ghost_subscribers": "Possible ghost or bought subscribers (views/subscribers < 1%)",
                                "bot_view_inflation": "Possible view inflation (likes/views < 0.3%)",
                                "engagement_spike": "Unusually high engagement (likes/views > 20%)", "insufficient_data": "Insufficient data"},
        "tl_green": "Green", "tl_yellow": "Amber", "tl_red": "Red",
        "traffic_legend": "Traffic lights: higher-is-better green ≥80% · amber 60–79.9% · red <60%; error rates green <5% · amber 5–15% · red >15%",
        "subjective_models": "Scoring models",
        "subjective_avg_multi": "Per-dimension average shown when several models scored (see Mean column)",
        "subjective_avg_single": "Single model scored; no cross-model average",
        "subjective_judge": "Judge",
        "subjective_unrecorded": "rater not recorded",
        "difficulty_raters": "Difficulty raters",
        "list_sep": ", ",
        "explorer_title": "All claims explorer",
        "explorer_desc": "Every claim, including pending, unchecked, contradicted and mixed ones; search offline and filter by verdict or unsubstantiated status.",
        "explorer_search": "Search claim, quote, rationale or ID…",
        "explorer_all": "All",
        "explorer_unsub": "Unsubstantiated",
        "explorer_count": "Showing {n} of {total}",
        "explorer_empty": "No matching claims",
        "explorer_details": "Quote & rationale",
        "th_claim": "Claim", "th_verdict": "Verdict", "th_lifecycle": "Stage", "th_citation": "Sourcing", "th_lead": "Lead time",
        "lifecycle_labels": {"pending": "Pending", "ready": "Ready", "awaiting_evidence": "Awaiting evidence", "resolved": "Resolved", "unscorable": "Unscorable", "disputed": "Disputed"},
        "nav_long": [("overview", "Overview"), ("longitudinal", "Timeline"), ("model-panel", "Expression"), ("coverage", "Scope & Limits"), ("sources", "Sources")],
        "status": {"supported": "Supported", "contradicted": "Contradicted", "mixed": "Mixed", "pending": "Pending", "indeterminate": "Indeterminate", "not_checked": "Not checked"},
        "relations": {"continuity": "Continuity", "genuine_change": "Genuine update", "not_comparable": "Not comparable", "contradiction": "Conflict", "unclear": "Unclear"},
        "no_fact_check_title": "Fact checking not performed",
        "no_fact_check_body": "This view analyzes stance evolution over time; unchecked claims are not scored as false.",
        "strict_support": "Strict Support Rate", "strict_support_note": "Adjudicated categorical claims",
        "accountability": "Operationalizability", "accountability_note": "Empirical claims with frozen criteria",
        "adjudication_cov": "Adjudication Coverage", "adjudication_cov_note": "Due claims with accepted verdicts",
        "brier_label": "Calibration · Brier", "brier_note": "Lower is better; explicit probabilities only",
        "pred_vs_fact": "Predictions vs. Factual Claims",
        "pred_rate": "Prediction Support Rate", "fact_rate": "Factual Support Rate",
        "family_weighted": "Family-weighted", "families_unit": "families",
        "scm_detail": "Categorical Outcome Breakdown",
        "scm_label": "S / C / M (N={n})",
        "binary_acc_label": "Binary S/(S+C)",
        "evidence_quality_label": "Evidence quality",
        "lifecycle_dist": "Lifecycle Distribution",
        "lifecycle_fmt": "pending={pending} · awaiting={awaiting} · disputed={disputed} · indet={indet}",
        "domain_breakdown": "By Domain",
        "difficulty_title": "Prediction Difficulty Breakdown",
        "difficulty_non_trivial": "Non-trivial prediction support rate",
        "difficulty_tiers": {"trivial": "Trivial / Near-certain", "moderate": "Moderate", "hard": "Hard", "non_consensus": "Non-consensus", "unrated": "Unrated"},
        "difficulty_tiers_short": {"trivial": "Trivial", "moderate": "Moderate", "hard": "Hard", "non_consensus": "Non-consensus", "unrated": "Unrated"},
        "th_tier": "Difficulty Tier", "th_claims": "Predictions", "th_mean_score": "Mean (1–5)",
        "horizon_title": "Prediction Lead-Time / Horizon",
        "horizon_mean_lead": "Mean lead time", "horizon_median_lead": "Median lead time", "horizon_supported_lead": "Supported mean lead",
        "th_horizon": "Horizon Bucket", "th_avg_lead": "Avg Lead (d)",
        "horizon_buckets": {"le_30d": "≤30d", "31_90d": "31–90d", "91_180d": "91–180d", "181_365d": "181–365d", "gt_365d": ">365d"},
        "verdict_chart_title": "Stacked Verdict Breakdown",
        "verdict_chart_desc": "Supported, mixed, and contradicted shares across claim types and prediction difficulty tiers",
        "verdict_group_types": "Overall & Claim Types",
        "verdict_group_difficulty": "By Prediction Difficulty Tier",
        "overall_label": "All Adjudicated",
        "claim_types": {"factual": "Factual", "prediction": "Prediction", "causal": "Causal", "hypothetical": "Hypothetical", "preference": "Preference", "value_judgment": "Value judgment"},
        "other_unsplit": "Other (non-supported)",
        "diff_chart_title": "Prediction Difficulty vs. Accuracy",
        "diff_chart_desc": "Accuracy progression from trivial to non-consensus predictions with 95% Wilson CIs",
        "diff_nontrivial_ref": "Non-trivial",
        "diff_trend_legend": "Accuracy trend",
        "diff_ci_legend": "95% Wilson CI",
        "sourcing_title": "Sourcing Rigor & Checkability",
        "sourcing_desc": "How each endorsed empirical claim is sourced: locatable primary source, secondary or vague third-party citation, uncited concrete figure (\"just saying it\"), or uncited vague assertion",
        "sourcing_chart_title": "Sourcing Mix (tagged claims)",
        "sourcing_chart_desc": "Stacked bars split tagged claims by citation category; untagged claims are excluded from the bar and reported separately",
        "sourcing_cats": {"primary_cited": "Primary cited", "secondary_cited": "Secondary / vague cite", "uncited_specific": "Uncited · specific", "uncited_vague": "Uncited · vague", "untagged": "Untagged"},
        "sourcing_citation_rate": "Citation rate",
        "sourcing_primary_rate": "Primary citation rate",
        "sourcing_unsub_rate": "Unsubstantiated rate",
        "sourcing_checkable_rate": "Checkable rate",
        "sourcing_legacy": "No citation tags in this run (legacy ledger); sourcing metrics are not computable",
        "sourcing_th_group": "Scope",
        "sourcing_th_tagged": "Tagged",
        "sourcing_th_untagged": "Untagged share",
        "horizon_hist_title": "Lead-Time Horizon Histogram & Accuracy Overlay",
        "horizon_hist_desc": "Bar height shows prediction count stacked by outcome; line overlay shows strict support rate",
        "horizon_axis_count": "Predictions",
        "horizon_axis_rate": "Support Rate",
        "horizon_pending_other": "Pending / Other",
        "horizon_avg_prefix": "avg",
        "boxplot_title": "Lead-Time Distribution Box Plot (Supported vs. Contradicted/Mixed)",
        "boxplot_desc": "Compares lead-time days (min, Q1, median, Q3, max, and mean) for supported vs. contradicted/mixed predictions",
        "boxplot_supported": "Supported",
        "boxplot_not_supported": "Contradicted / Mixed",
        "boxplot_all": "All Dated",
        "boxplot_empty": "Lead-time box plot requires at least 3 dated predictions (available: {n}).",
        "boxplot_legend_whisker": "Min–Max",
        "boxplot_legend_iqr": "Q1–Q3 IQR",
        "boxplot_legend_median": "Median",
        "boxplot_legend_mean": "Mean",
        "boxplot_stat_med": "Med",
        "boxplot_stat_mean": "Mean",
        "boxplot_axis_days": "Lead Time (days)",
        "synthetic_banner": "<strong>Synthetic Demo Data</strong><span>Subject, quotes, evidence and scores are manually constructed; no real models were called.</span>",
        "mean_legend": "Available Mean",
        "radar_title": "{n}-Dimension Expression & Auditability Radar",
        "radar_desc": "0 to 10 scale; thin lines are models, gradient line is available mean with per-axis score badges. Missing or n<2 axes remain disconnected.",
        "radar_synth_desc": "Manual synthetic demonstration.",
        "radar_synth_foot": "Synthetic demo data · No real model calls",
        "date_unknown": "Date unknown",
        "composite_withheld": "Composite withheld",
        "composite_blockers_prefix": "Composite blockers: ",
        "summary_label": "Key Findings",
        "default_scope_note": "This report covers only the listed sources and date range.",
        "as_of_prefix": "As of",
        "topics_title": "Stances by Topic",
        "topics_desc": "Check target, conditions and dates before judging continuity, genuine updates or unexplained conflicts.",
        "topics_count": "{n} topics",
        "panel_title": "Expression & Auditability",
        "panel_desc": "Models read the same frozen material independently under the same rubric.",
        "panel_badge": "{n} dims · 0–10",
        "cases_title": "Auditable Cases",
        "cases_desc": "Original quotes, adjudication rationale and evidence presented together.",
        "coverage_title": "Coverage, Costs & Limitations",
        "coverage_card": "Material Coverage",
        "cost_card": "Run Costs",
        "sources_title": "Sources & Citations",
        "sources_desc": "Charts, timeline entries and scores link back here; missing material never counts against the speaker.",
        "not_provided": "Not provided",
        "unknown_cost": "Unknown / unverified",
        "open_source": "Open source ↗",
        "local_source": "Local or synthetic source · No public URL",
        "footer_synth": "Manual synthetic demo · No real model calls",
        "footer_real": "This page formats provided audit outputs and does not independently certify truth.",
        "panel_empty": "<strong>No multi-model expression evaluation</strong>Missing ratings leave gaps rather than zero scores.",
        "panel_note_h": "Same material, independent ratings",
        "panel_note_p": "Evaluates communication rigor separately from fact-check accuracy and Brier scores.",
        "panel_completed": "Independent completed reviews",
        "panel_models_unit": "models",
        "panel_max_sd": "Highest disagreement",
        "panel_insufficient": "Insufficient n",
        "panel_missing_note": "{n} dimensions have missing ratings. Null stays blank; axes with n < 2 omit sample variance and polygon edges.",
        "table_caption": "Exact values · 0–10 rubric scale; Judge excluded from panel mean & SD",
        "th_dim": "Dimension", "th_mean": "Mean", "th_var": "Variance", "th_sd": "SD", "th_range": "Min–Max", "th_judge": "Judge",
        "panel_footer": "Sample variance uses ddof = 1. Spread describes inter-model disagreement, not confidence intervals.",
        "expand_rationale": "Show rationales",
        "support_mat": "Supporting", "counter_mat": "Counter",
        "judge_review": "Judge Review", "judge_note": "Separate from panel stats",
        "judge_unrun": "Judge: not completed or not requested; independent model scores remain unchanged.",
        "topic_nodes": "{n} entries",
        "topic_interp": "Longitudinal assessment: ",
        "topic_unexplained": "Assessment pending.",
        "topics_empty": "No longitudinal topic records provided.",
    },
}


def load_json(path):
    return common.read_json(path)


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Unsafe source URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source URLs must be credential-free HTTP(S) URLs")
    return value


def finite(value):
    return common.finite_number(value)


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be nonempty text")
    return value


def count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a nonnegative integer")
    return value


def _date_sort_key(raw):
    m = re.match(r"^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", str(raw))
    if m:
        return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), str(raw))
    return (9999, 99, 99, str(raw))


def validate_theme(theme=None):
    result = copy.deepcopy(THEME)
    if theme is None:
        return result
    if not isinstance(theme, dict) or set(theme) - set(THEME):
        raise ValueError("Unknown theme token")
    for mode in ("light", "dark"):
        if mode not in theme:
            continue
        if not isinstance(theme[mode], dict) or set(theme[mode]) - set(THEME[mode]):
            raise ValueError("Unknown color token")
        for key, value in theme[mode].items():
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError("Theme colors must be six-digit hexadecimal tokens")
            result[mode][key] = value
    if "radius" in theme:
        if type(theme["radius"]) is not int or not 0 <= theme["radius"] <= 16:
            raise ValueError("Theme radius must be an integer from 0 to 16")
        result["radius"] = theme["radius"]
    if "font" in theme:
        if theme["font"] not in FONT:
            raise ValueError("Theme font must be system or sans")
        result["font"] = theme["font"]
    return result


def ratio_check(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an explicit ratio")
    n, d, v = value.get("numerator"), value.get("denominator"), value.get("value")
    count(n, name + ".numerator"); count(d, name + ".denominator")
    if n > d or (d == 0 and v is not None) or (d and (not finite(v) or not math.isclose(v, n / d, abs_tol=1e-8))):
        raise ValueError(name + " does not match its numerator and denominator")


def validate_report(data, rubric=None):
    panel.canonical(data)
    if not isinstance(data, dict):
        raise ValueError("Report input must be an object")
    if data.get("schema_version") != 1 or type(data.get("synthetic")) is not bool:
        raise ValueError("Expected schema_version=1 and an explicit synthetic flag")
    report = data.get("report")
    if not isinstance(report, dict):
        raise ValueError("report metadata required")
    for key in ("title", "subject", "period_start", "period_end", "as_of", "generated_at"):
        text(report.get(key), "report." + key)
    if not isinstance(report.get("summary", []), list):
        raise ValueError("report.summary must be a list")
    sources = data.get("sources") or []
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    source_ids = set()
    for source in sources:
        sid = text(source.get("id"), "source.id")
        if sid in source_ids:
            raise ValueError("Duplicate source id")
        source_ids.add(sid)
        text(source.get("title"), "source.title")
        safe_url(source.get("url"))
    def references(ids):
        if not isinstance(ids, list) or any(not isinstance(x, str) or x not in source_ids for x in ids):
            raise ValueError("Citation references an unknown source/evidence id")
    rubric = rubric if rubric is not None else data.get("rubric") or load_json(ROOT / "assets/evaluation-rubric.json")
    dims = rubric.get("dimensions", [])
    if not isinstance(dims, list) or not 5 <= len(dims) <= 10 or rubric.get("scale") != {"min": 0, "max": 10}:
        raise ValueError("Radar requires 5–10 rubric dimensions on a 0–10 scale")
    dimension_ids = [text(d.get("id"), "dimension.id") for d in dims]
    if len(set(dimension_ids)) != len(dimension_ids):
        raise ValueError("Rubric dimension IDs must be unique")
    for dimension in dims:
        text(dimension.get("label"), "dimension.label")
    rubric_hash = hashlib.sha256(panel.canonical(rubric).encode("utf-8")).hexdigest()
    stats = None
    p = data.get("panel")
    if p is not None:
        if not isinstance(p, dict) or not isinstance(p.get("reviews"), list):
            raise ValueError("Invalid model panel")
        stats = panel.summarize(p["policy"], p["reviews"])
        if stats["rubric_hash"] is not None and stats["rubric_hash"] != rubric_hash:
            raise ValueError("Review rubric hash does not match the rendered rubric")
        if stats["data_hash"] is not None and stats["data_hash"] != data.get("data_hash"):
            raise ValueError("Report and model reviews refer to different frozen data")
        if stats["score_scale"] is not None and stats["score_scale"] != {"min": 0, "max": 10}:
            raise ValueError("Radar review scores must use the 0–10 rubric scale")
        for review in p["reviews"]:
            if set(review["scores"]) != set(dimension_ids):
                raise ValueError("Score dimensions must exactly match the rubric; use explicit null for missing scores")
            if review["status"] == "completed":
                validate_rationales(review, references, dimension_ids)
        judge = p.get("judge")
        if judge:
            if not isinstance(judge, dict):
                raise ValueError("Judge must be an object")
            if judge.get("status") not in {"completed", "not_requested", "pending", "abstained"}:
                raise ValueError("Unknown judge status")
            if judge.get("status") != "completed" and any(v is not None for v in (judge.get("scores") or {}).values()):
                raise ValueError("An unfinished judge cannot publish numeric scores")
            if judge.get("status") == "completed":
                if judge.get("model_id") != p["policy"]["report"].get("judge_model_id") or not judge.get("model_id"):
                    raise ValueError("Report judge must be the explicitly selected judge model")
                text(judge.get("summary"), "judge.summary")
                references(judge.get("evidence_ids", []))
                if judge.get("scores") is not None:
                    if judge.get("data_hash") != data.get("data_hash") or judge.get("rubric_hash") != rubric_hash or judge.get("score_scale") != {"min": 0, "max": 10}:
                        raise ValueError("Judge scores must bind the same data, rubric and score scale")
                    if set(judge["scores"]) != set(dimension_ids):
                        raise ValueError("Judge score dimensions must exactly match the rubric")
                    for value in judge["scores"].values():
                        if value is not None and (not finite(value) or not 0 <= value <= 10):
                            raise ValueError("Judge score outside 0–10")
                    validate_rationales(judge, references, dimension_ids)
    metrics = data.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be a scoring output object or null")
        for key in ("strict_support_rate", "accountability", "adjudication_coverage", "source_availability", "extraction_coverage"):
            if key in metrics:
                ratio_check(metrics[key], key)
        brier = metrics.get("brier")
        if brier is not None:
            count(brier.get("n"), "brier.n")
            v = brier.get("value")
            if (brier["n"] == 0 and v is not None) or (brier["n"] > 0 and (not finite(v) or not 0 <= v <= 1)):
                raise ValueError("Invalid Brier mean/sample size")
        if "categorical_counts" in metrics:
            numbers = metrics["categorical_counts"]
            for value in numbers.values():
                count(value, "categorical count")
            if sum(numbers.values()) != metrics.get("categorical_n"):
                raise ValueError("Categorical counts do not match categorical_n")
    for topic in data.get("topics") or []:
        text(topic.get("id"), "topic.id"); text(topic.get("label"), "topic.label")
        for entry in topic.get("entries") or []:
            for key in ("id", "date", "stance", "claim", "quote"):
                text(entry.get(key), "timeline." + key)
            references(entry.get("source_ids", [])); references(entry.get("evidence_ids", []))
            if entry.get("status", "not_checked") not in STATUS_TONES:
                raise ValueError("Unknown timeline verification status")
            if entry.get("transition") and entry["transition"].get("kind") not in RELATION_TONES:
                raise ValueError("Unknown longitudinal relation")
    for case in data.get("cases") or []:
        for key in ("title", "claim", "assessment"):
            text(case.get(key), "case." + key)
        references(case.get("evidence_ids", []))
        if case.get("status", "not_checked") not in STATUS_TONES:
            raise ValueError("Unknown case status")
    coverage = data.get("coverage")
    if coverage:
        for key in ("eligible_sources", "acquired_sources", "extracted_sources"):
            count(coverage.get(key), key)
        if not coverage["extracted_sources"] <= coverage["acquired_sources"] <= coverage["eligible_sources"]:
            raise ValueError("Coverage counts must satisfy extracted ≤ acquired ≤ eligible")
        if metrics:
            for name, numerator in (("source_availability", "acquired_sources"), ("extraction_coverage", "extracted_sources")):
                if name in metrics and (metrics[name]["numerator"] != coverage[numerator] or metrics[name]["denominator"] != coverage["eligible_sources"]):
                    raise ValueError(name + " must use the same frozen coverage counts and eligible_sources denominator")
    for key, value in (data.get("costs") or {}).items():
        if key.endswith("_usd") and value is not None and (not finite(value) or value < 0):
            raise ValueError("Cost amounts must be nonnegative or null")
    return {"stats": stats, "rubric": rubric, "rubric_hash": rubric_hash}


def validate_rationales(review, references, dimension_ids):
    rationales = review.get("rationales", {})
    for dimension in dimension_ids:
        value = review["scores"].get(dimension)
        rationale = rationales.get(dimension)
        if not isinstance(rationale, dict):
            raise ValueError("Every scored or missing dimension requires a rationale record")
        references(rationale.get("supporting_evidence_ids", [])); references(rationale.get("counter_evidence_ids", []))
        if value is None:
            text(rationale.get("missing_reason"), "null score missing_reason")
        else:
            text(rationale.get("rationale"), "dimension rationale")
            if not rationale.get("supporting_evidence_ids") and not rationale.get("counter_evidence_ids"):
                raise ValueError("A numeric rating needs at least one traceable supporting or counter example")


def fmt(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def percent(ratio):
    return "—" if ratio is None or ratio.get("value") is None else f'{ratio["value"] * 100:.1f}%'


def model_name(data, model_id):
    model = next(m for m in data["panel"]["policy"]["selected_models"] if m["id"] == model_id)
    return model.get("display_name") or model_id


def citation_links(data, ids):
    index = {s["id"]: i + 1 for i, s in enumerate(data.get("sources") or [])}
    return " ".join(f'<a class="citation" href="#source-{index[sid]}" aria-label="{esc(sid)}">{esc(sid)}</a>' for sid in ids)


def badge(label, tone="muted"):
    return f'<span class="badge {tone}">{esc(label)}</span>'


def _score_tier(value):
    if value is None:
        return "na"
    if value >= 7.5:
        return "high"
    if value >= 6.0:
        return "mid"
    if value >= 4.0:
        return "warn"
    return "low"


def plot_series(values, color, width, css_class="", counts=None, planned_n=None, cx=330, cy=224, radius=132, fill=None, stroke=None, draw_wedges=False):
    coordinates = []
    for i, value in enumerate(values):
        if value is None:
            coordinates.append(None)
        else:
            angle = -math.pi / 2 + i * math.tau / len(values)
            coordinates.append((cx + radius * value / 10 * math.cos(angle), cy + radius * value / 10 * math.sin(angle)))
    parts = []
    stroke_paint = stroke or color
    # Break polygon lines on missing values OR sparse mean axes (n < 2 when planned_n >= 2).
    has_sparse = counts is not None and planned_n is not None and planned_n >= 2 and any(c < 2 for c in counts)
    if all(p is not None for p in coordinates) and not has_sparse:
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in coordinates)
        poly_fill = fill if fill is not None else "none"
        fill_attr = f'fill="{poly_fill}"' if poly_fill != "none" else 'fill="none"'
        parts.append(f'<polygon class="{css_class}" points="{points}" {fill_attr} stroke="{stroke_paint}" stroke-width="{width}" stroke-linejoin="round"/>')
    else:
        for i, point in enumerate(coordinates):
            nxt_idx = (i + 1) % len(values)
            following = coordinates[nxt_idx]
            sparse_edge = has_sparse and (counts[i] < 2 or counts[nxt_idx] < 2)
            if point is not None and following is not None and not sparse_edge:
                if draw_wedges and fill:
                    wpts = f"{cx:.3f},{cy:.3f} {point[0]:.3f},{point[1]:.3f} {following[0]:.3f},{following[1]:.3f}"
                    parts.append(f'<polygon class="mean-wedge" points="{wpts}" fill="{fill}" stroke="none"/>')
                parts.append(f'<path class="{css_class}" d="M {point[0]:.3f} {point[1]:.3f} L {following[0]:.3f} {following[1]:.3f}" fill="none" stroke="{stroke_paint}" stroke-width="{width}" stroke-linecap="round"/>')
    for i, point in enumerate(coordinates):
        if point is not None:
            is_sparse = has_sparse and counts[i] < planned_n
            if is_sparse:
                parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="4.0" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="2 1.5"/>')
            elif width > 2:
                parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="4.0" fill="{color}" stroke="#FFFFFF" stroke-width="1.6"/>')
            else:
                parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="2.4" fill="{color}"/>')
    return "".join(parts)


DEFAULT_EN_DIM_LABELS = {
    "source_transparency": "Source Transparency",
    "fact_interpretation_separation": "Fact vs. Interpretation",
    "prediction_operationality": "Prediction Operationality",
    "uncertainty_expression": "Uncertainty Expression",
    "correction_transparency": "Correction Transparency",
    "counterargument_engagement": "Counterargument Engagement",
    "stance_change_explanation": "Stance Change Explanation",
    "argument_clarity": "Argument Clarity",
}

DEFAULT_EN_DIM_DESCRIPTIONS = {
    "source_transparency": "Evaluates how clearly the speaker states the source, date, method, and evidentiary boundaries of their claims.",
    "fact_interpretation_separation": "Evaluates whether readers can distinguish observations, quotations, inferences, causal explanations, and value judgments.",
    "prediction_operationality": "Evaluates whether predictions specify an intelligible target, condition, timeframe, and outcome criterion at publication time.",
    "uncertainty_expression": "Evaluates how clearly the speaker communicates known limitations, assumptions, alternative scenarios, and update conditions.",
    "correction_transparency": "Evaluates whether prior statements, updated statements, dates, reasons, and downstream impacts are clearly preserved.",
    "counterargument_engagement": "Evaluates how the speaker understands and addresses relevant counterexamples, counterevidence, and objections.",
    "stance_change_explanation": "Evaluates whether prior and current stances and reasons for changing or holding steady are explained.",
    "argument_clarity": "Evaluates whether readers can identify claims, reasons, key definitions, reasoning steps, and scope boundaries.",
}


def dim_label(dimension, lang="zh"):
    if lang == "en":
        if isinstance(dimension.get("label_en"), str) and dimension["label_en"].strip():
            return dimension["label_en"]
        fallback = DEFAULT_EN_DIM_LABELS.get(dimension.get("id"))
        if fallback:
            return fallback
    return dimension["label"]


def dim_description(dimension, lang="zh"):
    if lang == "en":
        if isinstance(dimension.get("description_en"), str) and dimension["description_en"].strip():
            return dimension["description_en"]
        fallback = DEFAULT_EN_DIM_DESCRIPTIONS.get(dimension.get("id"))
        if fallback:
            return fallback
    return dimension.get("description") or ""


def _text_units(value):
    return sum(2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1 for ch in value)


def wrap_svg_text(label, max_units):
    if " " in label:
        lines, current, width = [], "", 0
        for word in label.split():
            w_units = _text_units(word)
            if current and width + 1 + w_units <= max_units:
                current += " " + word
                width += 1 + w_units
            elif not current and w_units <= max_units:
                current, width = word, w_units
            else:
                if current:
                    lines.append(current)
                    current, width = "", 0
                if w_units <= max_units:
                    current, width = word, w_units
                else:
                    for char in word:
                        units = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
                        if width + units > max_units and current:
                            lines.append(current)
                            current, width = "", 0
                        current += char
                        width += units
        if current:
            lines.append(current)
        return lines
    lines, current, width = [], "", 0
    for char in label:
        units = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if width + units > max_units and current:
            lines.append(current)
            current, width = "", 0
        current += char
        width += units
    if current:
        lines.append(current)
    return lines


def svg_label(label, x, y, anchor, score=None, count_n=None, planned_n=None, max_width=660):
    lines = wrap_svg_text(label, 16)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:-1] + "…"
    line_step = 18
    text_y = y - 8 if score is not None or count_n is not None else y
    parts = [f'<text class="label" text-anchor="{anchor}" dominant-baseline="middle" x="{x:.3f}" y="{text_y:.3f}"><title>{esc(label)}</title>']
    for i, line in enumerate(lines):
        parts.append(f'<tspan x="{x:.3f}" y="{text_y+(i-(len(lines)-1)/2)*line_step:.3f}">{esc(line)}</tspan>')
    parts.append('</text>')
    if score is not None or count_n is not None:
        last_line_y = text_y + ((len(lines) - 1) / 2) * line_step
        badge_y = last_line_y + 18
        is_sparse = count_n is not None and planned_n is not None and planned_n >= 2 and count_n < planned_n
        badge_text = "—" if score is None else (f"{score:.1f}*" if is_sparse else f"{score:.1f}")
        tier = _score_tier(score)
        pill_w = 38 if len(badge_text) <= 4 else 44
        pill_h = 17
        if anchor == "start":
            rx = x
        elif anchor == "end":
            rx = x - pill_w
        else:
            rx = x - pill_w / 2
        rx = max(6.0, min(max_width - pill_w - 6.0, rx))
        tip = f"{label}: {badge_text}" + (f" (n={count_n}/{planned_n})" if count_n is not None and planned_n is not None else "")
        parts.append(
            f'<g class="score-badge tier-{tier}"><title>{esc(tip)}</title>'
            f'<rect x="{rx:.1f}" y="{badge_y - pill_h/2:.1f}" width="{pill_w}" height="{pill_h}" rx="8.5"/>'
            f'<text x="{rx + pill_w/2:.1f}" y="{badge_y + 0.5:.1f}" text-anchor="middle" dominant-baseline="middle">{esc(badge_text)}</text></g>'
        )
    return "".join(parts)


def render_radar(data, theme=None, rubric=None, standalone=False, lang="zh"):
    t = I18N[lang]
    prepared = validate_report(data, rubric)
    theme = validate_theme(theme)
    stats, dims = prepared["stats"], prepared["rubric"]["dimensions"]
    fg, muted, border = (theme["light"][k] for k in ("foreground", "muted", "border"))
    dark = theme["dark"]
    n = len(dims)
    dimension_ids = [d["id"] for d in dims]
    w, cx, cy, radius = 660, 330, 224, 130
    legend, chart_height, footer_y = [], 448, 437
    mean_color = VIZ["indigo"]
    if standalone and stats:
        items = [(model_name(data, review["model_id"]), COLORS[i % len(COLORS)], 1.7, "model")
                 for i, review in enumerate(data["panel"]["reviews"]) if review["status"] == "completed"]
        items.append((t["mean_legend"], "url(#radar-mean-stroke)", 3.0, "mean"))
        y = 446
        for offset in range(0, len(items), 2):
            row = items[offset:offset + 2]
            row_lines = [wrap_svg_text(item[0], 38) for item in row]
            for column, ((label, color, width, kind), lines) in enumerate(zip(row, row_lines)):
                x = 40 + column * 310
                legend.append(f'<g class="radar-legend"><title>{esc(label)}</title><line class="{kind}" x1="{x}" y1="{y}" x2="{x+22}" y2="{y}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
                for line_index, line in enumerate(lines):
                    legend.append(f'<text x="{x+31}" y="{y+line_index*16}" dominant-baseline="middle" font-size="12">{esc(line)}</text>')
                legend.append('</g>')
            y += max(len(lines) for lines in row_lines) * 16 + 12
        footer_y = y + 4
        chart_height = footer_y + 15 if data["synthetic"] else y + 5
    svg_style = (
        f'text{{font-family:{FONT[theme["font"]]};fill:{muted}}}'
        f'.radar-bg{{fill:{theme["light"]["surface"]}}}'
        f'.grid{{fill:none;stroke:{border};stroke-width:1}}'
        f'.grid-band{{fill:#EEF2FF;fill-opacity:.38;stroke:{border};stroke-width:1}}'
        f'.axis{{stroke:{border};stroke-width:1;stroke-dasharray:3 3}}'
        f'.ring-num{{font-size:10px;fill:{muted};font-weight:500}}'
        f'.label{{font-size:13px;font-weight:550;fill:{fg}}}'
        f'.model{{opacity:.80}}'
        f'.mean-wedge{{opacity:.85}}'
        f'.score-badge text{{font-size:10.5px;font-weight:700;font-variant-numeric:tabular-nums}}'
        f'.score-badge.tier-high rect{{fill:#ECFDF5;stroke:#A7F3D0;stroke-width:1}}.score-badge.tier-high text{{fill:#059669}}'
        f'.score-badge.tier-mid rect{{fill:#EEF2FF;stroke:#C7D2FE;stroke-width:1}}.score-badge.tier-mid text{{fill:#4F46E5}}'
        f'.score-badge.tier-warn rect{{fill:#FFFBEB;stroke:#FDE68A;stroke-width:1}}.score-badge.tier-warn text{{fill:#D97706}}'
        f'.score-badge.tier-low rect{{fill:#FFF1F2;stroke:#FECDD3;stroke-width:1}}.score-badge.tier-low text{{fill:#E11D48}}'
        f'.score-badge.tier-na rect{{fill:#F1F5F9;stroke:#CBD5E1;stroke-width:1}}.score-badge.tier-na text{{fill:#64748B}}'
        f'@media(prefers-color-scheme:dark){{text{{fill:{dark["muted"]}}}'
        f'.radar-bg{{fill:{dark["surface"]}}}.grid,.axis{{stroke:{dark["border"]}}}'
        f'.grid-band{{fill:#1E1B4B;fill-opacity:.42;stroke:{dark["border"]}}}'
        f'.label{{fill:{dark["foreground"]}}}'
        f'.score-badge.tier-high rect{{fill:#052E24;stroke:#065F46}}.score-badge.tier-high text{{fill:#34D399}}'
        f'.score-badge.tier-mid rect{{fill:#1E1B4B;stroke:#3730A3}}.score-badge.tier-mid text{{fill:#818CF8}}'
        f'.score-badge.tier-warn rect{{fill:#352004;stroke:#92400E}}.score-badge.tier-warn text{{fill:#FBBF24}}'
        f'.score-badge.tier-low rect{{fill:#380D17;stroke:#9F1239}}.score-badge.tier-low text{{fill:#F87171}}'
        f'.score-badge.tier-na rect{{fill:#1E293B;stroke:#334155}}.score-badge.tier-na text{{fill:#94A3B8}}}}'
    )
    defs = (
        '<defs>'
        '<linearGradient id="radar-mean-fill" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#4F46E5" stop-opacity="0.28"/>'
        '<stop offset="52%" stop-color="#7C3AED" stop-opacity="0.22"/>'
        '<stop offset="100%" stop-color="#0D9488" stop-opacity="0.26"/>'
        '</linearGradient>'
        '<linearGradient id="radar-mean-stroke" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#4F46E5"/>'
        '<stop offset="52%" stop-color="#7C3AED"/>'
        '<stop offset="100%" stop-color="#0D9488"/>'
        '</linearGradient>'
        '</defs>'
    )
    desc = t["radar_desc"] + (" " + t["radar_synth_desc"] if data["synthetic"] else "")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {chart_height}" role="img" aria-labelledby="radar-chart-title radar-chart-desc"><title id="radar-chart-title">{esc(t["radar_title"].format(n=n))}</title><desc id="radar-chart-desc">{esc(desc)}</desc><style>{svg_style}</style>{defs}<rect class="radar-bg" width="{w}" height="{chart_height}"/>']
    for level in (10, 8, 6, 4, 2):
        points = " ".join(f'{cx+radius*level/10*math.cos(-math.pi/2+i*math.tau/n):.3f},{cy+radius*level/10*math.sin(-math.pi/2+i*math.tau/n):.3f}' for i in range(n))
        ring_cls = "grid-band" if level in (10, 6) else "grid"
        parts.append(f'<polygon class="{ring_cls}" points="{points}"/>')
    for level in (2, 4, 6, 8, 10):
        parts.append(f'<text class="ring-num" x="{cx + 5}" y="{cy-radius*level/10+4:.3f}">{level}</text>')
    planned_n = len(stats["planned_models"]) if stats else None
    for i, dimension in enumerate(dims):
        angle = -math.pi / 2 + i * math.tau / n
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        x, y = cx + radius * cos_a, cy + radius * sin_a
        lx = cx + 158 * cos_a
        ly = cy + 162 * sin_a
        if sin_a < -0.85:
            ly -= 14
        elif sin_a > 0.85:
            ly += 2
        anchor = "middle" if abs(cos_a) < 0.1 else "start" if cos_a > 0 else "end"
        dim_stat = stats["metrics"].get(dimension["id"], {}) if stats else None
        dim_mean = dim_stat.get("mean") if dim_stat is not None else None
        dim_n = dim_stat.get("n") if dim_stat is not None else None
        parts.append(f'<line class="axis" x1="{cx}" y1="{cy}" x2="{x:.3f}" y2="{y:.3f}"/>' + svg_label(dim_label(dimension, lang), lx, ly, anchor, score=dim_mean, count_n=dim_n, planned_n=planned_n, max_width=w))
    if stats:
        for i, review in enumerate(data["panel"]["reviews"]):
            if review["status"] == "completed":
                parts.append(plot_series([review["scores"].get(k) for k in dimension_ids], COLORS[i % len(COLORS)], 1.55, "model", cx=cx, cy=cy, radius=radius))
        counts = [stats["metrics"].get(k, {}).get("n", 0) for k in dimension_ids]
        parts.append(plot_series(
            [stats["metrics"].get(k, {}).get("mean") for k in dimension_ids],
            mean_color, 3.0, "mean", counts=counts, planned_n=planned_n,
            cx=cx, cy=cy, radius=radius, fill="url(#radar-mean-fill)", stroke="url(#radar-mean-stroke)", draw_wedges=True,
        ))
    parts.extend(legend)
    if data["synthetic"]:
        parts.append(f'<text x="{cx}" y="{footer_y}" text-anchor="middle" font-size="11">{esc(t["radar_synth_foot"])}</text>')
    parts.append('</svg>')
    return "".join(parts)


def _nice_axis_ticks(max_val, target_ticks=5, integer_only=False):
    if max_val <= 0:
        return (4, [0, 1, 2, 3, 4]) if integer_only else (100.0, [0, 25, 50, 75, 100])
    if integer_only:
        if max_val <= 4:
            top = max(4, int(math.ceil(max_val)))
            return top, list(range(0, top + 1))
        raw = max_val / max(1, target_ticks - 1)
        mag = 10 ** int(math.floor(math.log10(raw)))
        step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
        step = max(1, int(step))
        top = int(math.ceil(max_val / step) * step)
        return top, list(range(0, top + 1, step))
    raw = max_val / max(1, target_ticks - 1)
    mag = 10 ** int(math.floor(math.log10(raw)))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    top = math.ceil(max_val / step) * step
    ticks = []
    cur = 0.0
    while cur <= top + step * 1e-6:
        ticks.append(round(cur, 4))
        cur += step
    return top, ticks


def _percentile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    idx = (n - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return float(sorted_vals[lo])
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _five_num_summary(values):
    vals = sorted(float(v) for v in values if finite(v) and v >= 0)
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": vals[0],
        "q1": _percentile(vals, 0.25),
        "median": _percentile(vals, 0.50),
        "q3": _percentile(vals, 0.75),
        "max": vals[-1],
        "mean": sum(vals) / len(vals),
        "values": vals,
    }


def _extract_verdict_counts(sub):
    if not isinstance(sub, dict):
        return None
    cc = sub.get("categorical_counts")
    if isinstance(cc, dict):
        s = int(cc.get("supported") or 0)
        m = int(cc.get("mixed") or 0)
        c = int(cc.get("contradicted") or 0)
        total = s + m + c
        if total > 0:
            return {"supported": s, "mixed": m, "contradicted": c, "other": 0, "total": total}
    sr = sub.get("strict_support_rate")
    if isinstance(sr, dict) and (sr.get("denominator") or 0) > 0:
        s = int(sr.get("numerator") or 0)
        total = int(sr.get("denominator") or 0)
        return {"supported": s, "mixed": 0, "contradicted": 0, "other": max(0, total - s), "total": total}
    return None


def render_verdict_breakdown_svg(metrics, lang="zh"):
    t = I18N[lang]
    if not isinstance(metrics, dict):
        return ""
    groups = []
    type_rows = []
    overall = _extract_verdict_counts(metrics)
    if overall:
        type_rows.append((t["overall_label"], overall))
    by_type = metrics.get("by_claim_type") or {}
    seen_types = []
    for ctype in ("factual", "prediction"):
        if ctype in by_type:
            seen_types.append(ctype)
    for ctype in sorted(by_type):
        if ctype not in seen_types:
            seen_types.append(ctype)
    for ctype in seen_types:
        counts = _extract_verdict_counts(by_type.get(ctype))
        if counts:
            label = t["claim_types"].get(ctype, ctype)
            type_rows.append((label, counts))
    if type_rows:
        groups.append((t["verdict_group_types"], type_rows))

    pdiff = metrics.get("prediction_difficulty") or {}
    diff_tiers = pdiff.get("by_tier") or {}
    diff_rows = []
    for tier_key in ("trivial", "moderate", "hard", "non_consensus", "unrated"):
        counts = _extract_verdict_counts(diff_tiers.get(tier_key))
        if counts:
            label = t["difficulty_tiers_short"].get(tier_key, tier_key)
            diff_rows.append((label, counts))
    if diff_rows:
        groups.append((t["verdict_group_difficulty"], diff_rows))

    if not groups:
        return ""

    has_other = any(c["other"] > 0 for _, rows in groups for _, c in rows)
    w = 720
    bar_x, bar_w, bar_h = 178, 354, 22
    row_step = 34
    y = 42
    parts = []
    clip_defs = []
    clip_idx = 0

    for g_idx, (group_title, rows) in enumerate(groups):
        if g_idx > 0:
            y += 10
            parts.append(f'<line class="viz-divider" x1="14" y1="{y - 8}" x2="{w - 14}" y2="{y - 8}"/>')
            y += 8
        parts.append(f'<text class="viz-group-label" x="14" y="{y}">{esc(group_title)}</text>')
        y += 18
        for label, counts in rows:
            total = counts["total"]
            s, m, c, o = counts["supported"], counts["mixed"], counts["contradicted"], counts["other"]
            s_pct = s / total * 100
            clip_id = f"vb-clip-{clip_idx}"
            clip_idx += 1
            clip_defs.append(f'<clipPath id="{clip_id}"><rect x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>')
            tip_parts = [f"{label} (n={total}): {t['status']['supported']} {s} ({s_pct:.1f}%)"]
            if m or c or not o:
                tip_parts.append(f"{t['status']['mixed']} {m} ({m/total*100:.1f}%)")
                tip_parts.append(f"{t['status']['contradicted']} {c} ({c/total*100:.1f}%)")
            if o:
                tip_parts.append(f"{t['other_unsplit']} {o} ({o/total*100:.1f}%)")
            row_svg = [f'<g><title>{esc(" · ".join(tip_parts))}</title>']
            row_svg.append(f'<text class="viz-row-label" x="{bar_x - 10}" y="{y + bar_h/2 + 0.5:.1f}" text-anchor="end" dominant-baseline="middle">{esc(label)} <tspan class="viz-n-sub">(n={total})</tspan></text>')
            row_svg.append(f'<rect class="viz-track" x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="5"/>')
            segs = [
                (s, VIZ["supported"], f"{s/total*100:.0f}%"),
                (m, VIZ["mixed"], f"{m/total*100:.0f}%"),
                (c, VIZ["contradicted"], f"{c/total*100:.0f}%"),
                (o, VIZ["other"], f"{o/total*100:.0f}%"),
            ]
            row_svg.append(f'<g clip-path="url(#{clip_id})">')
            cur_x = float(bar_x)
            for seg_val, color, pct_txt in segs:
                if seg_val <= 0:
                    continue
                seg_w = bar_w * seg_val / total
                row_svg.append(f'<rect x="{cur_x:.2f}" y="{y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}"/>')
                if seg_w >= 40:
                    row_svg.append(f'<text class="viz-bar-pct" x="{cur_x + seg_w/2:.2f}" y="{y + bar_h/2 + 0.5:.1f}" text-anchor="middle" dominant-baseline="middle">{esc(pct_txt)}</text>')
                cur_x += seg_w
            row_svg.append('</g>')
            # Right-hand numeric readout
            detail = f"{s}/{m}/{c}" if o == 0 else f"{s}/{total}"
            row_svg.append(
                f'<text class="viz-stat-val" x="{bar_x + bar_w + 12}" y="{y + bar_h/2 + 0.5:.1f}" dominant-baseline="middle">'
                f'{s_pct:.1f}% <tspan class="viz-stat-sub">({esc(detail)})</tspan></text>'
            )
            row_svg.append('</g>')
            parts.append("".join(row_svg))
            y += row_step

    height = y + 10
    legend_items = [
        (t["status"]["supported"], VIZ["supported"]),
        (t["status"]["mixed"], VIZ["mixed"]),
        (t["status"]["contradicted"], VIZ["contradicted"]),
    ]
    if has_other:
        legend_items.append((t["other_unsplit"], VIZ["other"]))
    lx = 14
    legend_svg = []
    for lbl, col in legend_items:
        legend_svg.append(f'<rect x="{lx}" y="11" width="11" height="11" rx="3" fill="{col}"/><text class="viz-legend-text" x="{lx + 16}" y="17" dominant-baseline="middle">{esc(lbl)}</text>')
        lx += 28 + _text_units(lbl) * 7.2
    header_hint = "S / M / C" if not has_other else "S / N"
    legend_svg.append(f'<text class="viz-legend-text" x="{w - 14}" y="17" text-anchor="end" dominant-baseline="middle">{esc(header_hint)}</text>')
    return (
        f'<svg class="viz-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {height}" role="img" aria-labelledby="vb-title vb-desc">'
        f'<title id="vb-title">{esc(t["verdict_chart_title"])}</title>'
        f'<desc id="vb-desc">{esc(t["verdict_chart_desc"])}</desc>'
        f'<defs>{"".join(clip_defs)}</defs>'
        f'{"".join(legend_svg)}{"".join(parts)}</svg>'
    )


def render_difficulty_accuracy_svg(metrics, lang="zh"):
    t = I18N[lang]
    pdiff = (metrics or {}).get("prediction_difficulty") or {}
    diff_tiers = pdiff.get("by_tier") or {}
    if not pdiff.get("rated_n") or not diff_tiers:
        return ""
    tiers = ["trivial", "moderate", "hard", "non_consensus"]
    unrated_sub = diff_tiers.get("unrated") or {}
    if (unrated_sub.get("strict_support_rate") or {}).get("denominator"):
        tiers.append("unrated")

    w, h = 680, 316
    left, right, top, bottom = 58, 650, 48, 232
    plot_w, plot_h = right - left, bottom - top
    slot_w = plot_w / len(tiers)
    bar_w = min(74.0, slot_w * 0.48)

    defs = ['<defs>']
    for tk in tiers:
        c_top, c_bot = DIFF_TIER_COLORS.get(tk, ("#94A3B8", "#64748B"))
        defs.append(f'<linearGradient id="diff-grad-{tk}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{c_top}"/><stop offset="100%" stop-color="{c_bot}"/></linearGradient>')
    defs.append('</defs>')

    parts = []
    # Horizontal gridlines at 0..100%
    for pct in (0, 25, 50, 75, 100):
        gy = bottom - plot_h * pct / 100
        cls = "viz-axis-base" if pct == 0 else "viz-grid"
        parts.append(f'<line class="{cls}" x1="{left}" y1="{gy:.2f}" x2="{right}" y2="{gy:.2f}"/>')
        parts.append(f'<text class="viz-axis-tick" x="{left - 8}" y="{gy + 0.5:.2f}" text-anchor="end" dominant-baseline="middle">{pct}%</text>')

    # Non-trivial reference line
    nt_sr = pdiff.get("non_trivial_strict_support_rate") or {}
    nt_val = nt_sr.get("value")
    if nt_val is not None and nt_sr.get("denominator"):
        nt_y = bottom - plot_h * nt_val
        parts.append(f'<line class="viz-ref-line" x1="{left}" y1="{nt_y:.2f}" x2="{right}" y2="{nt_y:.2f}"/>')
        ref_lbl = f'{t["diff_nontrivial_ref"]} {nt_val * 100:.1f}%'
        pill_w = max(84, _text_units(ref_lbl) * 6.8 + 14)
        parts.append(
            f'<g class="viz-ref-pill"><rect x="{right - pill_w:.1f}" y="{nt_y - 19:.1f}" width="{pill_w:.1f}" height="17" rx="4"/>'
            f'<text x="{right - pill_w / 2:.1f}" y="{nt_y - 10:.1f}" text-anchor="middle" dominant-baseline="middle">{esc(ref_lbl)}</text></g>'
        )

    trend_pts = []
    has_ci = False
    for idx, tk in enumerate(tiers):
        cx = left + (idx + 0.5) * slot_w
        sub = diff_tiers.get(tk) or {}
        sr = sub.get("strict_support_rate") or {}
        denom = int(sr.get("denominator") or 0)
        num = int(sr.get("numerator") or 0)
        val = sr.get("value")
        total_claims = int(sub.get("total_canonical_claims") or 0)
        mean_score = sub.get("mean_difficulty_score")
        tier_label = t["difficulty_tiers_short"].get(tk, tk)
        full_label = t["difficulty_tiers"].get(tk, tk)
        bx = cx - bar_w / 2

        if denom > 0 and val is not None:
            bh = max(2.0, plot_h * val)
            by = bottom - bh
            ci = sr.get("ci_95")
            tip = f"{full_label}: {val*100:.1f}% ({num}/{denom})"
            if ci:
                tip += f" · 95% Wilson [{ci['low']*100:.1f}%, {ci['high']*100:.1f}%]"
            parts.append(f'<g><title>{esc(tip)}</title><rect x="{bx:.2f}" y="{by:.2f}" width="{bar_w:.2f}" height="{bh:.2f}" rx="6" fill="url(#diff-grad-{tk})"/>')
            label_top_y = by - 10
            if ci and finite(ci.get("low")) and finite(ci.get("high")):
                has_ci = True
                ci_hi_y = bottom - plot_h * max(0.0, min(1.0, ci["high"]))
                ci_lo_y = bottom - plot_h * max(0.0, min(1.0, ci["low"]))
                parts.append(
                    f'<line class="viz-ci" x1="{cx:.2f}" y1="{ci_hi_y:.2f}" x2="{cx:.2f}" y2="{ci_lo_y:.2f}"/>'
                    f'<line class="viz-ci" x1="{cx - 5:.2f}" y1="{ci_hi_y:.2f}" x2="{cx + 5:.2f}" y2="{ci_hi_y:.2f}"/>'
                    f'<line class="viz-ci" x1="{cx - 5:.2f}" y1="{ci_lo_y:.2f}" x2="{cx + 5:.2f}" y2="{ci_lo_y:.2f}"/>'
                )
                label_top_y = min(label_top_y, ci_hi_y - 8)
            label_top_y = max(top - 4, label_top_y)
            parts.append(f'<text class="viz-bar-val" x="{cx:.2f}" y="{label_top_y - 9:.2f}" text-anchor="middle">{val*100:.1f}%</text>')
            parts.append(f'<text class="viz-bar-sub" x="{cx:.2f}" y="{label_top_y + 3:.2f}" text-anchor="middle">({num}/{denom})</text></g>')
            if tk != "unrated":
                trend_pts.append((cx, by))
        else:
            parts.append(
                f'<g><title>{esc(full_label)}: n=0</title>'
                f'<rect class="viz-empty-bar" x="{bx:.2f}" y="{bottom - 20:.2f}" width="{bar_w:.2f}" height="20" rx="4"/>'
                f'<text class="viz-bar-sub" x="{cx:.2f}" y="{bottom - 28:.2f}" text-anchor="middle">n=0</text></g>'
            )

        parts.append(f'<text class="viz-x-label" x="{cx:.2f}" y="{bottom + 20}" text-anchor="middle">{esc(tier_label)}</text>')
        sub_bits = []
        if total_claims:
            sub_bits.append(f"n={total_claims}")
        if mean_score is not None:
            sub_bits.append(f"{mean_score:.1f}/5")
        if sub_bits:
            parts.append(f'<text class="viz-x-sub" x="{cx:.2f}" y="{bottom + 36}" text-anchor="middle">{esc(" · ".join(sub_bits))}</text>')

    if len(trend_pts) >= 2:
        pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in trend_pts)
        parts.append(f'<polyline class="viz-trend-line" points="{pts_str}" fill="none"/>')
        for x, y in trend_pts:
            parts.append(f'<circle class="viz-trend-dot" cx="{x:.2f}" cy="{y:.2f}" r="4.2"/>')

    # Legend at bottom
    leg_y = h - 16
    leg_items = []
    if len(trend_pts) >= 2:
        leg_items.append(f'<line class="viz-trend-line" x1="58" y1="{leg_y}" x2="82" y2="{leg_y}"/><circle class="viz-trend-dot" cx="70" cy="{leg_y}" r="3.4"/><text class="viz-legend-text" x="88" y="{leg_y + 0.5}" dominant-baseline="middle">{esc(t["diff_trend_legend"])}</text>')
    if has_ci:
        cx_leg = 228 if len(trend_pts) >= 2 else 58
        leg_items.append(f'<line class="viz-ci" x1="{cx_leg}" y1="{leg_y - 5}" x2="{cx_leg}" y2="{leg_y + 5}"/><line class="viz-ci" x1="{cx_leg - 4}" y1="{leg_y - 5}" x2="{cx_leg + 4}" y2="{leg_y - 5}"/><line class="viz-ci" x1="{cx_leg - 4}" y1="{leg_y + 5}" x2="{cx_leg + 4}" y2="{leg_y + 5}"/><text class="viz-legend-text" x="{cx_leg + 10}" y="{leg_y + 0.5}" dominant-baseline="middle">{esc(t["diff_ci_legend"])}</text>')

    return (
        f'<svg class="viz-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="diff-chart-title diff-chart-desc">'
        f'<title id="diff-chart-title">{esc(t["diff_chart_title"])}</title>'
        f'<desc id="diff-chart-desc">{esc(t["diff_chart_desc"])}</desc>'
        f'{"".join(defs)}{"".join(parts)}{"".join(leg_items)}</svg>'
    )


def _sourcing_rows(m, t):
    rows = []
    overall = m.get("sourcing_rigor") or {}
    if overall.get("tagged_n"):
        rows.append((t["overall_label"], overall))
    by_type = m.get("by_claim_type") or {}
    ordered = [k for k in ("factual", "prediction") if k in by_type] + sorted(k for k in by_type if k not in ("factual", "prediction"))
    for ctype in ordered:
        sr = (by_type.get(ctype) or {}).get("sourcing_rigor") or {}
        if sr.get("tagged_n"):
            rows.append((t["claim_types"].get(ctype, ctype), sr))
    return rows


def render_sourcing_rigor_svg(rows, lang="zh"):
    t = I18N[lang]
    if not rows:
        return ""
    w = 720
    bar_x, bar_w, bar_h = 178, 354, 22
    row_step = 34
    y = 42
    parts = []
    clip_defs = []
    for idx, (label, sr) in enumerate(rows):
        counts = sr["counts"]
        tagged = sr["tagged_n"]
        clip_id = f"sr-clip-{idx}"
        clip_defs.append(f'<clipPath id="{clip_id}"><rect x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>')
        tip_parts = [f"{label} (n={tagged})"]
        tip_parts += [f'{t["sourcing_cats"][k]} {counts[k]} ({counts[k] / tagged * 100:.1f}%)' for k in SRC_CITATION_KEYS]
        if counts["untagged"]:
            tip_parts.append(f'{t["sourcing_cats"]["untagged"]} {counts["untagged"]}')
        row_svg = [f'<g><title>{esc(" · ".join(tip_parts))}</title>']
        row_svg.append(f'<text class="viz-row-label" x="{bar_x - 10}" y="{y + bar_h / 2 + 0.5:.1f}" text-anchor="end" dominant-baseline="middle">{esc(label)} <tspan class="viz-n-sub">(n={tagged})</tspan></text>')
        row_svg.append(f'<rect class="viz-track" x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" rx="5"/>')
        row_svg.append(f'<g clip-path="url(#{clip_id})">')
        cur_x = float(bar_x)
        for key in SRC_CITATION_KEYS:
            seg_val = counts[key]
            if seg_val <= 0:
                continue
            seg_w = bar_w * seg_val / tagged
            row_svg.append(f'<rect x="{cur_x:.2f}" y="{y}" width="{seg_w:.2f}" height="{bar_h}" fill="{SRC_CITATION_COLORS[key]}"/>')
            if seg_w >= 40:
                row_svg.append(f'<text class="viz-bar-pct" x="{cur_x + seg_w / 2:.2f}" y="{y + bar_h / 2 + 0.5:.1f}" text-anchor="middle" dominant-baseline="middle">{seg_val / tagged * 100:.0f}%</text>')
            cur_x += seg_w
        row_svg.append('</g>')
        cite = sr.get("citation_rate") or {}
        cite_txt = percent(cite)
        row_svg.append(
            f'<text class="viz-stat-val" x="{bar_x + bar_w + 12}" y="{y + bar_h / 2 + 0.5:.1f}" dominant-baseline="middle">'
            f'{esc(cite_txt)} <tspan class="viz-stat-sub">({cite.get("numerator", 0)}/{tagged})</tspan></text>'
        )
        row_svg.append('</g>')
        parts.append("".join(row_svg))
        y += row_step

    height = y + 40
    legend_svg = []
    lx = 14
    for key in SRC_CITATION_KEYS:
        lbl = t["sourcing_cats"][key]
        legend_svg.append(f'<rect x="{lx}" y="11" width="11" height="11" rx="3" fill="{SRC_CITATION_COLORS[key]}"/><text class="viz-legend-text" x="{lx + 16}" y="17" dominant-baseline="middle">{esc(lbl)}</text>')
        lx += 28 + _text_units(lbl) * 7.2
    return (
        f'<svg class="viz-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {height}" role="img" aria-labelledby="sr-title sr-desc">'
        f'<title id="sr-title">{esc(t["sourcing_chart_title"])}</title>'
        f'<desc id="sr-desc">{esc(t["sourcing_chart_desc"])}</desc>'
        f'<defs>{"".join(clip_defs)}</defs>'
        f'{"".join(legend_svg)}{"".join(parts)}</svg>'
    )


def render_sourcing_rigor_section(m, lang="zh"):
    t = I18N[lang]
    overall = m.get("sourcing_rigor")
    if not overall or not overall.get("population_n"):
        return ""
    if not overall.get("tagged_n"):
        return (
            f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["sourcing_title"])}</h3>'
            f'<div class="card-header-sub">{esc(t["sourcing_desc"])}</div></div>'
            f'<p>{esc(t["sourcing_legacy"])}</p></div>'
        )
    chips = [
        f'<span class="kpi-chip chip-teal">{esc(t["sourcing_citation_rate"])}: {esc(percent(overall.get("citation_rate")))}</span>',
        f'<span class="kpi-chip chip-emerald">{esc(t["sourcing_primary_rate"])}: {esc(percent(overall.get("primary_citation_rate")))}</span>',
        f'<span class="kpi-chip chip-rose">{esc(t["sourcing_unsub_rate"])}: {esc(percent(overall.get("unsubstantiated_rate")))}</span>',
        f'<span class="kpi-chip chip-sky">{esc(t["sourcing_checkable_rate"])}: {esc(percent(overall.get("checkable_rate")))}</span>',
    ]
    svg = render_sourcing_rigor_svg(_sourcing_rows(m, t), lang=lang)
    tbl_rows = []
    for label, sr in [(t["overall_label"], overall)] + [
        (t["claim_types"].get(ct, ct), (m.get("by_claim_type") or {}).get(ct, {}).get("sourcing_rigor") or {})
        for ct in sorted((m.get("by_claim_type") or {}))
    ]:
        if not sr.get("tagged_n"):
            continue
        c = sr["counts"]
        tbl_rows.append(
            f'<tr><td>{esc(label)}</td><td>{sr["tagged_n"]}</td>'
            f'<td>{esc(percent(sr.get("primary_citation_rate")))}</td>'
            f'<td>{esc(percent(sr.get("shares", {}).get("secondary_cited")))}</td>'
            f'<td>{esc(percent(sr.get("shares", {}).get("uncited_specific")))}</td>'
            f'<td>{esc(percent(sr.get("shares", {}).get("uncited_vague")))}</td>'
            f'<td>{esc(percent(sr.get("unsubstantiated_rate")))}</td>'
            f'<td>{esc(percent(sr.get("checkable_rate")))}</td>'
            f'<td>{esc(percent(sr.get("untagged_share")))} ({c["untagged"]})</td></tr>'
        )
    return (
        f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["sourcing_title"])}</h3>'
        f'<div class="card-header-sub">{esc(t["sourcing_desc"])}</div></div>'
        f'<div class="kpi-chips">{"".join(chips)}</div>'
        f'<div class="viz-block"><div class="viz-subhead"><h4>{esc(t["sourcing_chart_title"])}</h4>'
        f'<span>{esc(t["sourcing_chart_desc"])}</span></div>{svg}</div>'
        f'<div class="table-wrap"><table><thead><tr><th>{esc(t["sourcing_th_group"])}</th><th>{esc(t["sourcing_th_tagged"])}</th>'
        f'<th>{esc(t["sourcing_primary_rate"])}</th><th>{esc(t["sourcing_cats"]["secondary_cited"])}</th>'
        f'<th>{esc(t["sourcing_cats"]["uncited_specific"])}</th><th>{esc(t["sourcing_cats"]["uncited_vague"])}</th>'
        f'<th>{esc(t["sourcing_unsub_rate"])}</th><th>{esc(t["sourcing_checkable_rate"])}</th>'
        f'<th>{esc(t["sourcing_th_untagged"])}</th></tr></thead>'
        f'<tbody>{"".join(tbl_rows)}</tbody></table></div></div>'
    )


def render_horizon_histogram_svg(phor, lang="zh"):
    t = I18N[lang]
    hbuckets = (phor or {}).get("buckets") or {}
    if not (phor or {}).get("dated_n") or not hbuckets:
        return ""
    order = ("le_30d", "31_90d", "91_180d", "181_365d", "gt_365d")
    counts_list = [int((hbuckets.get(k) or {}).get("count") or 0) for k in order]
    max_count = max(counts_list) if counts_list else 0
    if max_count <= 0:
        return ""
    y_max, y_ticks = _nice_axis_ticks(max_count, target_ticks=5, integer_only=True)
    any_cat_split = any(isinstance((hbuckets.get(k) or {}).get("categorical_counts"), dict) for k in order)

    w, h = 680, 326
    left, right, top, bottom = 54, 622, 54, 240
    plot_w, plot_h = right - left, bottom - top
    slot_w = plot_w / len(order)
    bar_w = min(68.0, slot_w * 0.52)

    defs = [
        '<defs>',
        '<linearGradient id="hor-grad-single" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#38BDF8"/><stop offset="100%" stop-color="#4F46E5"/></linearGradient>',
    ]
    parts = []
    # Left Y-axis (count) gridlines & ticks
    for tick in y_ticks:
        gy = bottom - plot_h * tick / y_max
        cls = "viz-axis-base" if tick == 0 else "viz-grid"
        parts.append(f'<line class="{cls}" x1="{left}" y1="{gy:.2f}" x2="{right}" y2="{gy:.2f}"/>')
        parts.append(f'<text class="viz-axis-tick" x="{left - 8}" y="{gy + 0.5:.2f}" text-anchor="end" dominant-baseline="middle">{tick}</text>')
    # Right Y-axis (accuracy 0-100%)
    for pct in (0, 25, 50, 75, 100):
        gy = bottom - plot_h * pct / 100
        parts.append(f'<text class="viz-axis-tick viz-axis-rate" x="{right + 8}" y="{gy + 0.5:.2f}" text-anchor="start" dominant-baseline="middle">{pct}%</text>')
    # Axis titles
    parts.append(f'<text class="viz-axis-title" x="{left}" y="{top - 14}" text-anchor="start">{esc(t["horizon_axis_count"])}</text>')
    parts.append(f'<text class="viz-axis-title viz-axis-rate" x="{right}" y="{top - 14}" text-anchor="end">{esc(t["horizon_axis_rate"])}</text>')

    acc_pts = []
    for idx, bkey in enumerate(order):
        cx = left + (idx + 0.5) * slot_w
        bdata = hbuckets.get(bkey) or {}
        cnt = int(bdata.get("count") or 0)
        sr = bdata.get("strict_support_rate") or {}
        sr_val = sr.get("value")
        sr_den = int(sr.get("denominator") or 0)
        sr_num = int(sr.get("numerator") or 0)
        blabel = t["horizon_buckets"].get(bkey, bkey)
        avg_d = bdata.get("mean_lead_time_days")
        bx = cx - bar_w / 2

        if cnt > 0:
            total_bh = max(3.0, plot_h * cnt / y_max)
            top_y = bottom - total_bh
            clip_id = f"hor-clip-{idx}"
            defs.append(f'<clipPath id="{clip_id}"><rect x="{bx:.2f}" y="{top_y:.2f}" width="{bar_w:.2f}" height="{total_bh:.2f}" rx="5"/></clipPath>')
            tip = f"{blabel}: n={cnt}"
            if sr_den and sr_val is not None:
                tip += f" · {t['strict_support']}: {sr_val*100:.1f}% ({sr_num}/{sr_den})"
            if avg_d is not None:
                tip += f" · {t['horizon_avg_prefix']} {avg_d:.1f}d"
            parts.append(f'<g><title>{esc(tip)}</title><g clip-path="url(#{clip_id})">')
            cc = bdata.get("categorical_counts")
            if isinstance(cc, dict) and sum(int(cc.get(k) or 0) for k in ("supported", "mixed", "contradicted")) > 0:
                s = int(cc.get("supported") or 0)
                m = int(cc.get("mixed") or 0)
                c = int(cc.get("contradicted") or 0)
                rem = max(0, cnt - s - m - c)
                cur_bottom = float(bottom)
                for seg_n, col in ((s, VIZ["supported"]), (m, VIZ["mixed"]), (c, VIZ["contradicted"]), (rem, VIZ["pending"])):
                    if seg_n <= 0:
                        continue
                    seg_h = total_bh * seg_n / cnt
                    parts.append(f'<rect x="{bx:.2f}" y="{cur_bottom - seg_h:.2f}" width="{bar_w:.2f}" height="{seg_h + 0.5:.2f}" fill="{col}"/>')
                    cur_bottom -= seg_h
            else:
                parts.append(f'<rect x="{bx:.2f}" y="{top_y:.2f}" width="{bar_w:.2f}" height="{total_bh:.2f}" fill="url(#hor-grad-single)"/>')
            parts.append('</g>')
            # Count label cleanly inside top of bar if tall enough, else above bar
            if total_bh >= 22:
                parts.append(f'<text class="viz-bar-pct" x="{cx:.2f}" y="{bottom - 10:.2f}" text-anchor="middle">n={cnt}</text>')
            else:
                parts.append(f'<text class="viz-bar-sub" x="{cx:.2f}" y="{top_y - 6:.2f}" text-anchor="middle">n={cnt}</text>')
            parts.append('</g>')
        else:
            parts.append(f'<rect class="viz-empty-bar" x="{bx:.2f}" y="{bottom - 10:.2f}" width="{bar_w:.2f}" height="10" rx="3"/><text class="viz-bar-sub" x="{cx:.2f}" y="{bottom - 15:.2f}" text-anchor="middle">0</text>')

        if sr_den > 0 and sr_val is not None:
            ay = bottom - plot_h * sr_val
            acc_pts.append((cx, ay, sr_val, sr_num, sr_den, blabel))

        parts.append(f'<text class="viz-x-label" x="{cx:.2f}" y="{bottom + 20}" text-anchor="middle">{esc(blabel)}</text>')
        if avg_d is not None:
            parts.append(f'<text class="viz-x-sub" x="{cx:.2f}" y="{bottom + 36}" text-anchor="middle">{esc(t["horizon_avg_prefix"])} {avg_d:.0f}d</text>')

    defs.append('</defs>')

    # Accuracy overlay polyline + floating pills
    if acc_pts:
        if len(acc_pts) >= 2:
            pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y, *_ in acc_pts)
            parts.append(f'<polyline class="viz-acc-line" points="{pts_str}" fill="none"/>')
        for x, y, val, num, den, blabel in acc_pts:
            pill_y = y - 16 if y > top + 20 else y + 18
            pill_txt = f"{val*100:.0f}%"
            pw = 38 if len(pill_txt) <= 3 else 44
            parts.append(
                f'<g><title>{esc(blabel)}: {val*100:.1f}% ({num}/{den})</title>'
                f'<circle class="viz-acc-dot" cx="{x:.2f}" cy="{y:.2f}" r="4.8"/>'
                f'<rect class="viz-acc-pill-bg" x="{x - pw/2:.1f}" y="{pill_y - 9:.1f}" width="{pw}" height="17" rx="8.5"/>'
                f'<text class="viz-acc-pill-text" x="{x:.1f}" y="{pill_y + 0.5:.1f}" text-anchor="middle" dominant-baseline="middle">{esc(pill_txt)}</text></g>'
            )

    # Top legend
    leg_items = []
    if any_cat_split:
        leg_items.extend([
            ("rect", t["status"]["supported"], VIZ["supported"]),
            ("rect", t["status"]["mixed"], VIZ["mixed"]),
            ("rect", t["status"]["contradicted"], VIZ["contradicted"]),
            ("rect", t["horizon_pending_other"], VIZ["pending"]),
        ])
    else:
        leg_items.append(("rect", t["horizon_axis_count"], "#4F46E5"))
    leg_items.append(("line", t["horizon_axis_rate"], VIZ["indigo"]))
    lx = left
    leg_svg = []
    for kind, lbl, col in leg_items:
        if kind == "rect":
            leg_svg.append(f'<rect x="{lx:.1f}" y="11" width="10" height="10" rx="2.5" fill="{col}"/><text class="viz-legend-text" x="{lx + 15:.1f}" y="16.5" dominant-baseline="middle">{esc(lbl)}</text>')
            lx += 26 + _text_units(lbl) * 6.8
        else:
            leg_svg.append(f'<line class="viz-acc-line" x1="{lx:.1f}" y1="16" x2="{lx + 18:.1f}" y2="16"/><circle class="viz-acc-dot" cx="{lx + 9:.1f}" cy="16" r="3.4"/><text class="viz-legend-text" x="{lx + 24:.1f}" y="16.5" dominant-baseline="middle">{esc(lbl)}</text>')
            lx += 34 + _text_units(lbl) * 6.8

    return (
        f'<svg class="viz-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="hor-hist-title hor-hist-desc">'
        f'<title id="hor-hist-title">{esc(t["horizon_hist_title"])}</title>'
        f'<desc id="hor-hist-desc">{esc(t["horizon_hist_desc"])}</desc>'
        f'{"".join(defs)}{"".join(leg_svg)}{"".join(parts)}</svg>'
    )


def render_horizon_boxplot_html(data, lang="zh"):
    t = I18N[lang]
    cases = data.get("cases") or []
    supported_vals, not_supported_vals, all_vals = [], [], []
    for case in cases:
        lt = case.get("lead_time_days")
        if not finite(lt) or lt < 0:
            continue
        ctype = case.get("claim_type")
        if ctype is not None and ctype != "prediction":
            continue
        val = float(lt)
        all_vals.append(val)
        st = case.get("status")
        if st == "supported":
            supported_vals.append(val)
        elif st in {"contradicted", "mixed"}:
            not_supported_vals.append(val)

    # Also allow optional precomputed distributions on metrics.prediction_horizon if cases are absent
    if len(all_vals) < 3:
        phor = (data.get("metrics") or {}).get("prediction_horizon") or {}
        by_out = phor.get("lead_time_samples") or {}
        if isinstance(by_out, dict):
            s_extra = [float(v) for v in (by_out.get("supported") or []) if finite(v) and v >= 0]
            ns_extra = [float(v) for v in (by_out.get("not_supported") or []) if finite(v) and v >= 0]
            all_extra = [float(v) for v in (by_out.get("all") or []) if finite(v) and v >= 0] or (s_extra + ns_extra)
            if len(all_extra) >= 3:
                supported_vals, not_supported_vals, all_vals = s_extra, ns_extra, all_extra

    if len(all_vals) < 3:
        return f'<div class="chart-empty">{esc(t["boxplot_empty"].format(n=len(all_vals)))}</div>'

    rows = [
        (t["boxplot_supported"], _five_num_summary(supported_vals), VIZ["supported"], VIZ["supported_dark"]),
        (t["boxplot_not_supported"], _five_num_summary(not_supported_vals), VIZ["contradicted"], VIZ["contradicted_dark"]),
        (t["boxplot_all"], _five_num_summary(all_vals), VIZ["indigo"], VIZ["violet"]),
    ]
    max_val = max(all_vals)
    x_max, x_ticks = _nice_axis_ticks(max(max_val, 10.0), target_ticks=5, integer_only=False)

    w = 720
    left, right = 158, 536
    plot_w = right - left
    top = 34
    row_h = 54
    bottom = top + len(rows) * row_h
    height = bottom + 64

    def sx(v):
        return left + plot_w * (v / x_max)

    parts = []
    # Vertical gridlines + X-axis ticks
    for tick in x_ticks:
        gx = sx(tick)
        cls = "viz-axis-base" if tick == 0 else "viz-grid"
        parts.append(f'<line class="{cls}" x1="{gx:.2f}" y1="{top - 6}" x2="{gx:.2f}" y2="{bottom}"/>')
        parts.append(f'<text class="viz-axis-tick" x="{gx:.2f}" y="{bottom + 15}" text-anchor="middle">{tick:g}d</text>')
    parts.append(f'<line class="viz-axis-base" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>')
    parts.append(f'<text class="viz-axis-title" x="{(left + right)/2:.1f}" y="{bottom + 32}" text-anchor="middle">{esc(t["boxplot_axis_days"])}</text>')

    for idx, (label, stat, fill_col, stroke_col) in enumerate(rows):
        cy = top + idx * row_h + row_h / 2
        n_val = stat["n"] if stat else 0
        parts.append(f'<text class="viz-row-label" x="{left - 12}" y="{cy - 5:.1f}" text-anchor="end" dominant-baseline="middle">{esc(label)}</text>')
        parts.append(f'<text class="viz-n-sub" x="{left - 12}" y="{cy + 10:.1f}" text-anchor="end" dominant-baseline="middle">n = {n_val}</text>')
        if stat is None:
            parts.append(f'<line class="viz-empty-track" x1="{left}" y1="{cy:.1f}" x2="{right}" y2="{cy:.1f}"/>')
            parts.append(f'<text class="viz-bar-sub" x="{right + 12}" y="{cy:.1f}" dominant-baseline="middle">—</text>')
            continue

        x_min, x_q1, x_med, x_q3, x_max_v, x_mean = (sx(stat[k]) for k in ("min", "q1", "median", "q3", "max", "mean"))
        box_w = max(3.0, x_q3 - x_q1)
        box_x = x_q1 if x_q3 - x_q1 >= 3.0 else x_q1 - 1.5
        tip = (
            f"{label} (n={n_val}): min={stat['min']:.0f}d, Q1={stat['q1']:.0f}d, "
            f"median={stat['median']:.0f}d, Q3={stat['q3']:.0f}d, max={stat['max']:.0f}d, mean={stat['mean']:.1f}d"
        )
        g = [f'<g><title>{esc(tip)}</title>']
        # Whiskers & caps
        g.append(f'<line x1="{x_min:.2f}" y1="{cy:.1f}" x2="{x_max_v:.2f}" y2="{cy:.1f}" stroke="{stroke_col}" stroke-width="1.8"/>')
        g.append(f'<line x1="{x_min:.2f}" y1="{cy - 7:.1f}" x2="{x_min:.2f}" y2="{cy + 7:.1f}" stroke="{stroke_col}" stroke-width="1.8"/>')
        g.append(f'<line x1="{x_max_v:.2f}" y1="{cy - 7:.1f}" x2="{x_max_v:.2f}" y2="{cy + 7:.1f}" stroke="{stroke_col}" stroke-width="1.8"/>')
        # IQR box
        g.append(f'<rect x="{box_x:.2f}" y="{cy - 13:.1f}" width="{box_w:.2f}" height="26" rx="4" fill="{fill_col}" fill-opacity="0.24" stroke="{stroke_col}" stroke-width="2"/>')
        # Individual points (if <= 50)
        if len(stat["values"]) <= 50:
            for pi, pv in enumerate(stat["values"]):
                px = sx(pv)
                py = cy + (((pi % 5) - 2) * 3.2)
                g.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="2.2" fill="{stroke_col}" fill-opacity="0.45"/>')
        # Median line
        g.append(f'<line x1="{x_med:.2f}" y1="{cy - 13:.1f}" x2="{x_med:.2f}" y2="{cy + 13:.1f}" stroke="{stroke_col}" stroke-width="3.2" stroke-linecap="round"/>')
        # Mean diamond marker
        dm = f"{x_mean:.2f},{cy - 5.5:.2f} {x_mean + 5.5:.2f},{cy:.2f} {x_mean:.2f},{cy + 5.5:.2f} {x_mean - 5.5:.2f},{cy:.2f}"
        g.append(f'<polygon class="viz-mean-diamond" points="{dm}" fill="{VIZ["mixed"]}" stroke="#FFFFFF" stroke-width="1.4"/>')
        # Right numeric summary
        g.append(
            f'<text class="viz-stat-val" x="{right + 12}" y="{cy - 6:.1f}" dominant-baseline="middle">'
            f'{esc(t["boxplot_stat_med"])} {stat["median"]:.0f}d · {esc(t["boxplot_stat_mean"])} {stat["mean"]:.0f}d</text>'
        )
        g.append(
            f'<text class="viz-stat-sub" x="{right + 12}" y="{cy + 10:.1f}" dominant-baseline="middle">'
            f'IQR {stat["q1"]:.0f}–{stat["q3"]:.0f}d · [{stat["min"]:.0f}, {stat["max"]:.0f}]</text>'
        )
        g.append('</g>')
        parts.append("".join(g))

    # Legend at bottom
    ly = height - 14
    lx = left
    legend_parts = []
    # Whisker
    legend_parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx + 18}" y2="{ly}" stroke="#64748B" stroke-width="1.8"/><line x1="{lx}" y1="{ly - 4}" x2="{lx}" y2="{ly + 4}" stroke="#64748B" stroke-width="1.8"/><line x1="{lx + 18}" y1="{ly - 4}" x2="{lx + 18}" y2="{ly + 4}" stroke="#64748B" stroke-width="1.8"/><text class="viz-legend-text" x="{lx + 24}" y="{ly + 0.5}" dominant-baseline="middle">{esc(t["boxplot_legend_whisker"])}</text>')
    lx += 36 + _text_units(t["boxplot_legend_whisker"]) * 6.8
    # Box
    legend_parts.append(f'<rect x="{lx:.1f}" y="{ly - 5}" width="16" height="10" rx="2" fill="#10B981" fill-opacity="0.24" stroke="#059669" stroke-width="1.6"/><text class="viz-legend-text" x="{lx + 22:.1f}" y="{ly + 0.5}" dominant-baseline="middle">{esc(t["boxplot_legend_iqr"])}</text>')
    lx += 34 + _text_units(t["boxplot_legend_iqr"]) * 6.8
    # Median
    legend_parts.append(f'<line x1="{lx:.1f}" y1="{ly - 6}" x2="{lx:.1f}" y2="{ly + 6}" stroke="#0F172A" stroke-width="3" class="viz-leg-med"/><text class="viz-legend-text" x="{lx + 8:.1f}" y="{ly + 0.5}" dominant-baseline="middle">{esc(t["boxplot_legend_median"])}</text>')
    lx += 20 + _text_units(t["boxplot_legend_median"]) * 6.8
    # Mean diamond
    dm_l = f"{lx + 5:.1f},{ly - 5:.1f} {lx + 10:.1f},{ly:.1f} {lx + 5:.1f},{ly + 5:.1f} {lx:.1f},{ly:.1f}"
    legend_parts.append(f'<polygon points="{dm_l}" fill="#F59E0B" stroke="#FFFFFF" stroke-width="1.2"/><text class="viz-legend-text" x="{lx + 16:.1f}" y="{ly + 0.5}" dominant-baseline="middle">{esc(t["boxplot_legend_mean"])}</text>')

    return (
        f'<svg class="viz-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {height}" role="img" aria-labelledby="bp-title bp-desc">'
        f'<title id="bp-title">{esc(t["boxplot_title"])}</title>'
        f'<desc id="bp-desc">{esc(t["boxplot_desc"])}</desc>'
        f'{"".join(parts)}{"".join(legend_parts)}</svg>'
    )


CSS = r'''
:root{--emerald:#059669;--emerald-bg:#ECFDF5;--emerald-bd:#A7F3D0;--amber:#B45309;--amber-bg:#FFFBEB;--amber-bd:#FDE68A;--rose:#BE123C;--rose-bg:#FFF1F2;--rose-bd:#FECDD3;--sky:#0369A1;--sky-bg:#F0F9FF;--sky-bd:#BAE6FD;--indigo:#4F46E5;--indigo-bg:#EEF2FF;--indigo-bd:#C7D2FE;--violet:#6D28D9;--violet-bg:#F5F3FF;--violet-bd:#DDD6FE;--teal:#0F766E;--teal-bg:#F0FDFA;--teal-bd:#99F6E4}
@media(prefers-color-scheme:dark){:root{--emerald:#34D399;--emerald-bg:#052E24;--emerald-bd:#065F46;--amber:#FBBF24;--amber-bg:#352004;--amber-bd:#92400E;--rose:#F87171;--rose-bg:#380D17;--rose-bd:#9F1239;--sky:#38BDF8;--sky-bg:#082F49;--sky-bd:#075985;--indigo:#818CF8;--indigo-bg:#1E1B4B;--indigo-bd:#3730A3;--violet:#A78BFA;--violet-bg:#2E1065;--violet-bd:#5B21B6;--teal:#2DD4BF;--teal-bg:#042F2E;--teal-bd:#115E59}}
*{box-sizing:border-box}h1,h2,h3,.stance,.reason-meta,.metadata,.synthetic,.topic-index,.judge-label,.badge,.top-meta{overflow-wrap:anywhere;min-width:0}.legend-item{max-width:100%;overflow-wrap:anywhere}html{scroll-behavior:auto;scroll-padding-top:24px}body{margin:0;background:var(--background);color:var(--foreground);font-family:var(--font);font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:4px}p{margin:0 0 10px;overflow-wrap:anywhere}ul{padding-left:19px;margin:8px 0}li{margin:5px 0;overflow-wrap:anywhere}.shell{max-width:1280px;margin:0 auto;padding:24px 32px 56px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 20px;border-bottom:1px solid var(--border);margin-bottom:30px;font-size:12px;color:var(--muted)}.brand{display:flex;gap:10px;align-items:center;font-weight:700;color:var(--foreground);letter-spacing:.055em}.mark{display:grid;place-items:center;width:27px;height:27px;border:0;border-radius:7px;font-size:14px;color:#fff;background:linear-gradient(135deg,#4F46E5,#0D9488);box-shadow:0 2px 6px rgba(79,70,229,.28)}.top-meta{font-size:11px;text-align:right}.layout{display:grid;grid-template-columns:160px minmax(0,1fr);gap:32px}.sidebar{position:sticky;top:24px;align-self:start;font-size:12px}.nav-title{font-size:11px;letter-spacing:.10em;color:var(--muted);margin:0 0 12px;font-weight:650}.sidebar a{display:block;color:var(--muted);padding:8px 11px;margin:2px 0;border-radius:7px;transition:background .15s,color .15s}.sidebar a:hover{background:var(--subtle);color:var(--foreground);text-decoration:none}.sidebar a:first-of-type{color:var(--indigo);background:var(--indigo-bg);font-weight:650}.sidebar .side-note{margin:27px 10px 0;color:var(--muted);font-size:11px;line-height:1.8}.content{min-width:0}.eyebrow{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:var(--indigo);letter-spacing:.06em;margin-bottom:8px;padding:2px 8px;border-radius:999px;background:var(--indigo-bg);border:1px solid var(--indigo-bd)}h1{font-size:28px;line-height:1.35;letter-spacing:-.035em;margin:0 0 10px;font-weight:700}h2{font-size:18px;letter-spacing:-.02em;line-height:1.4;margin:0;font-weight:680}h3{font-size:14px;margin:0 0 4px;font-weight:650}.subtitle{font-size:13px;color:var(--muted);max-width:78ch}.metadata{display:flex;flex-wrap:wrap;gap:7px 14px;color:var(--muted);font-size:11px;margin:14px 0 23px;align-items:center}.badge{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:600;line-height:1.5;white-space:normal;color:var(--muted);background:var(--subtle)}.badge.accent{color:var(--indigo);background:var(--indigo-bg);border-color:var(--indigo-bd)}.badge.ok{color:var(--emerald);background:var(--emerald-bg);border-color:var(--emerald-bd)}.badge.negative{color:var(--rose);background:var(--rose-bg);border-color:var(--rose-bd)}.badge.warn{color:var(--amber);background:var(--amber-bg);border-color:var(--amber-bd)}.badge.info{color:var(--sky);background:var(--sky-bg);border-color:var(--sky-bd)}.badge.violet{color:var(--violet);background:var(--violet-bg);border-color:var(--violet-bd)}@media(prefers-color-scheme:dark){.badge.negative{color:#F87171}}.synthetic{display:flex;gap:8px;align-items:baseline;padding:11px 14px;border:1px solid var(--amber-bd);background:var(--amber-bg);border-radius:var(--radius);margin:18px 0;font-size:11.5px;color:var(--amber)}.synthetic strong{color:var(--amber);font-weight:700}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}.metric{min-width:0;border:1px solid var(--border);border-top:3px solid var(--indigo);border-radius:var(--radius);background:var(--surface);padding:16px 16px 14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}.metric.metric-emerald{border-top-color:#10B981}.metric.metric-emerald .metric-value{color:var(--emerald)}.metric.metric-indigo{border-top-color:#4F46E5}.metric.metric-indigo .metric-value{color:var(--indigo)}.metric.metric-teal{border-top-color:#14B8A6}.metric.metric-teal .metric-value{color:var(--teal)}.metric.metric-violet{border-top-color:#8B5CF6}.metric.metric-violet .metric-value{color:var(--violet)}.metric-label{color:var(--muted);font-size:11px;font-weight:600}.metric-value{font-size:28px;font-weight:700;letter-spacing:-.04em;line-height:1.2;margin:8px 0;font-variant-numeric:tabular-nums}.metric-note{font-size:11px;color:var(--muted);line-height:1.55}.disclosures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:18px}.section{margin-top:30px;scroll-margin-top:24px}.section-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:13px}.section-description{font-size:11.5px;color:var(--muted);margin-top:4px}.card{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,.04)}.card-header{padding:16px 20px 0}.card-header-sub{font-size:11.5px;color:var(--muted);margin-top:3px}.card-content{padding:16px 20px}.card-footer{border-top:1px solid var(--border);padding:12px 20px;font-size:11px;color:var(--muted);background:var(--subtle)}.viz-card{margin-bottom:18px}.viz-wrap{padding:14px 18px 16px}.viz-block{border-bottom:1px solid var(--border);padding:14px 18px 16px}.viz-block:last-child{border-bottom:0}.viz-subhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:8px}.viz-subhead h4{margin:0;font-size:13px;font-weight:650;color:var(--foreground)}.viz-subhead span{font-size:11px;color:var(--muted)}.viz-svg{display:block;width:100%;height:auto;max-width:740px;margin:0 auto}.viz-svg text{font-family:var(--font)}.viz-group-label{font-size:11px;font-weight:700;letter-spacing:.04em;fill:var(--indigo);text-transform:uppercase}.viz-divider{stroke:var(--border);stroke-width:1}.viz-row-label{font-size:12px;font-weight:600;fill:var(--foreground)}.viz-n-sub{font-size:10.5px;font-weight:500;fill:var(--muted)}.viz-track{fill:var(--subtle)}.viz-bar-pct{font-size:11px;font-weight:700;fill:#FFFFFF}.viz-stat-val{font-size:11.5px;font-weight:650;fill:var(--foreground);font-variant-numeric:tabular-nums}.viz-stat-sub{font-size:10.5px;font-weight:500;fill:var(--muted);font-variant-numeric:tabular-nums}.viz-legend-text{font-size:11px;fill:var(--muted);font-weight:550}.viz-grid{stroke:var(--border);stroke-width:1;stroke-dasharray:3 3}.viz-axis-base{stroke:var(--border);stroke-width:1.4}.viz-axis-tick{font-size:10.5px;fill:var(--muted);font-variant-numeric:tabular-nums}.viz-axis-title{font-size:10.5px;font-weight:650;fill:var(--muted)}.viz-axis-rate{fill:var(--indigo)}.viz-ref-line{stroke:var(--teal);stroke-width:1.6;stroke-dasharray:5 4}.viz-ref-pill rect{fill:var(--teal-bg);stroke:var(--teal-bd);stroke-width:1}.viz-ref-pill text{font-size:10px;font-weight:700;fill:var(--teal)}.viz-ci{stroke:var(--foreground);stroke-width:1.5;opacity:.65}.viz-bar-val{font-size:12px;font-weight:700;fill:var(--foreground);font-variant-numeric:tabular-nums}.viz-bar-sub{font-size:10.5px;fill:var(--muted);font-variant-numeric:tabular-nums}.viz-empty-bar{fill:var(--subtle);stroke:var(--border);stroke-width:1.2;stroke-dasharray:3 2}.viz-empty-track{stroke:var(--border);stroke-width:1.4;stroke-dasharray:4 3}.viz-x-label{font-size:12px;font-weight:650;fill:var(--foreground)}.viz-x-sub{font-size:10.5px;fill:var(--muted);font-variant-numeric:tabular-nums}.viz-trend-line{stroke:var(--indigo);stroke-width:2.2;stroke-dasharray:5 3}.viz-trend-dot{fill:var(--surface);stroke:var(--indigo);stroke-width:2.4}.viz-acc-line{stroke:var(--indigo);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}.viz-acc-dot{fill:var(--indigo);stroke:var(--surface);stroke-width:2}.viz-acc-pill-bg{fill:var(--indigo-bg);stroke:var(--indigo-bd);stroke-width:1}.viz-acc-pill-text{font-size:10.5px;font-weight:700;fill:var(--indigo);font-variant-numeric:tabular-nums}.viz-leg-med{stroke:var(--foreground)}.kpi-chips{display:flex;flex-wrap:wrap;gap:8px;padding:12px 20px 4px}.kpi-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:11.5px;font-weight:600;background:var(--subtle);border:1px solid var(--border);color:var(--foreground);font-variant-numeric:tabular-nums}.kpi-chip.chip-indigo{background:var(--indigo-bg);border-color:var(--indigo-bd);color:var(--indigo)}.kpi-chip.chip-emerald{background:var(--emerald-bg);border-color:var(--emerald-bd);color:var(--emerald)}.kpi-chip.chip-teal{background:var(--teal-bg);border-color:var(--teal-bd);color:var(--teal)}.chip-sky{background:var(--sky-bg);border-color:var(--sky-bd);color:var(--sky)}.chip-amber{background:var(--amber-bg);border-color:var(--amber-bd);color:var(--amber)}.chip-rose{background:var(--rose-bg);border-color:var(--rose-bd);color:var(--rose)}.chart-empty{padding:12px 14px;border:1px dashed var(--border);border-radius:8px;background:var(--subtle);color:var(--muted);font-size:12px;text-align:center}.summary{font-size:13px;line-height:1.9}.summary .summary-label{display:block;font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--indigo);margin-bottom:9px}.radar-layout{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(210px,1fr);align-items:center}.radar-wrap{padding:10px 0 0;min-width:0}.radar-wrap svg{display:block;width:100%;height:auto}.radar-note{padding:20px 22px 20px 4px;font-size:12px;color:var(--muted)}.legend{display:flex;gap:9px 17px;flex-wrap:wrap;font-size:11px;margin:5px 20px 17px;color:var(--muted)}.legend-item{display:flex;align-items:center;gap:7px}.legend-line{width:18px;border-top:2.5px solid;flex:0 0 auto;border-radius:2px}.legend-line.mean-line{height:3px;border-top:0;background:linear-gradient(90deg,#4F46E5,#7C3AED,#0D9488)}.mini-stat{border-top:1px solid var(--border);padding-top:12px;margin-top:14px}.mini-stat strong{display:block;font-size:20px;color:var(--indigo);font-weight:700;margin:3px 0;font-variant-numeric:tabular-nums}.table-wrap{overflow:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:12px;min-width:650px}caption{text-align:left;color:var(--muted);padding:12px 20px 8px;font-size:11.5px;font-weight:550}th,td{border-bottom:1px solid var(--border);padding:11px 12px;text-align:right;vertical-align:top;font-variant-numeric:tabular-nums}th{font-weight:600;color:var(--muted);background:var(--subtle);font-size:11px}th:first-child,td:first-child{text-align:left;min-width:148px;padding-left:20px}th:last-child,td:last-child{padding-right:20px}tbody tr:last-child td{border-bottom:0}.mean-cell{font-weight:700;color:var(--indigo)}.dim-label{display:block;color:var(--foreground);font-weight:600}.n-note{color:var(--muted);font-size:11px;margin-top:2px}details{border-top:1px solid var(--border)}summary{cursor:pointer;padding:12px 20px;font-size:12px;font-weight:600;list-style-position:inside;overflow-wrap:anywhere}summary:hover{background:var(--subtle)}.reason-content{padding:0 20px 15px}.reason-row{padding:12px 0;border-top:1px solid var(--border);font-size:12px}.reason-row:first-child{border-top:0}.reason-meta{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:11px;margin-bottom:5px}.citation{display:inline-flex;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;border:1px solid var(--indigo-bd);border-radius:5px;padding:0 6px;line-height:1.7;margin:2px 3px 2px 0;background:var(--indigo-bg);color:var(--indigo);white-space:nowrap}.judge{display:grid;grid-template-columns:110px minmax(0,1fr);gap:15px;padding:17px 20px;border-top:1px solid var(--border);background:var(--violet-bg)}.judge-label{font-size:11px;font-weight:700;color:var(--violet)}.judge-note{font-size:11px;color:var(--muted);margin-top:3px}.judge p{font-size:12px;margin:0 0 6px}.topic{margin-bottom:16px}.topic-header{display:flex;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--border)}.topic-header p{font-size:11.5px;color:var(--muted);margin:5px 0 0;max-width:65ch}.topic-index{font-size:11px;color:var(--indigo);font-weight:600;font-variant-numeric:tabular-nums}.timeline{padding:6px 20px 12px}.entry{display:grid;grid-template-columns:90px minmax(0,1fr);gap:18px;padding:20px 0 0}.entry-date{font-size:11px;color:var(--muted);padding-top:2px;font-variant-numeric:tabular-nums}.entry-body{position:relative;border-left:2px solid var(--border);padding:0 0 20px 20px;min-width:0}.entry:last-child .entry-body{padding-bottom:4px}.entry-body:before{content:"";position:absolute;left:-6px;top:6px;width:10px;height:10px;border:2px solid var(--surface);border-radius:50%;background:var(--muted)}.entry-body.dot-ok:before{background:#10B981}.entry-body.dot-negative:before{background:#F43F5E}.entry-body.dot-warn:before{background:#F59E0B}.entry-body.dot-info:before{background:#0EA5E9}.entry-body.dot-violet:before{background:#8B5CF6}.entry-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.stance{font-size:12.5px;font-weight:650}.entry-claim{font-size:11.5px;color:var(--muted);margin:5px 0 10px}.quote{margin:0;padding:10px 12px;border:1px solid var(--border);border-left:3px solid var(--indigo);border-radius:6px;background:var(--subtle);font-size:12px;line-height:1.8;overflow-wrap:anywhere}.entry-context{font-size:11px;color:var(--muted);margin:8px 0 5px}.transition{padding:11px 0 0;font-size:11px;color:var(--muted);line-height:1.8}.transition .badge{margin:0 5px 4px 0}.topic-assessment{padding:12px 20px;border-top:1px solid var(--border);font-size:11.5px;color:var(--muted);background:var(--subtle)}.topic-assessment strong{color:var(--foreground);font-weight:600}.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.case{padding:17px 18px;border-left:3px solid var(--border)}.case.case-ok{border-left-color:#10B981}.case.case-negative{border-left-color:#F43F5E}.case.case-warn{border-left-color:#F59E0B}.case.case-info{border-left-color:#0EA5E9}.case.case-violet{border-left-color:#8B5CF6}.case-top{display:flex;justify-content:space-between;gap:10px;margin-bottom:10px}.case p{font-size:12px}.case .case-claim{color:var(--muted);font-size:11.5px}.dual-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.key-values{margin:0}.kv{display:flex;justify-content:space-between;gap:18px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}.kv:first-child{padding-top:0}.kv:last-child{border-bottom:0}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}.footnotes{font-size:11px;color:var(--muted);line-height:1.85}.sources{display:grid;grid-template-columns:1fr 1fr;gap:0 22px;padding:5px 20px}.source{padding:14px 0;border-bottom:1px solid var(--border);scroll-margin-top:24px;min-width:0}.source-title{font-size:12px;font-weight:600;margin:3px 0 5px;overflow-wrap:anywhere}.source-meta{font-size:11px;color:var(--muted);overflow-wrap:anywhere}.source-excerpt{font-size:11px;color:var(--muted);margin:7px 0 0;line-height:1.8}.footer{margin-top:30px;padding-top:15px;border-top:1px solid var(--border);color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}.hash{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.empty{padding:22px 20px;color:var(--muted);font-size:12px}.empty strong{display:block;color:var(--foreground);font-weight:600;margin-bottom:5px}.numeric{font-variant-numeric:tabular-nums}@media(max-width:1050px){.layout{grid-template-columns:124px minmax(0,1fr);gap:24px}.shell{padding:20px 24px 45px}.radar-layout{grid-template-columns:1fr}.radar-note{padding:5px 20px 18px}.mini-stat{display:inline-block;border:0;padding:0;margin:0 25px 0 0}.radar-note>p{margin-bottom:12px}.radar-wrap{max-width:660px;margin:auto;width:100%}}@media(max-width:760px){.radar-wrap .label{font-size:16px}.shell{padding:18px 16px 36px}.layout{display:block}.sidebar{position:static;margin-bottom:24px;display:flex;gap:4px;overflow:auto}.sidebar a{flex:0 0 auto;padding:7px 9px;font-size:11px}.sidebar .nav-title,.sidebar .side-note{display:none}.topbar{margin-bottom:16px;padding-bottom:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.disclosures{grid-template-columns:1fr}.metric{padding:14px}.metric-value{font-size:25px}h1{font-size:25px}.section{margin-top:24px}.card-content,.card-header,.viz-wrap,.viz-block{padding-left:14px;padding-right:14px}.kpi-chips{padding-left:14px;padding-right:14px}.radar-note{padding:5px 16px 18px}.cases,.dual-grid,.sources{grid-template-columns:1fr}.topic-header{padding:16px}.timeline{padding:0 16px 12px}.entry{grid-template-columns:63px minmax(0,1fr);gap:10px}.entry-body{padding-left:14px}.entry-top{display:block}.entry-top .badge{margin-top:6px}.quote{font-size:11px;padding:9px 10px}.judge{grid-template-columns:1fr;gap:8px;padding:15px 16px}.judge-label,.judge-note{display:inline}.judge-note{margin-left:8px}.synthetic{display:block}.sources{padding:2px 16px}.source:last-child{border:0}}@media print{body{background:#fff;color:#0f172a}.shell{max-width:none;padding:0}.layout{display:block}.sidebar{display:none}.card,.metric,.entry,.case{break-inside:avoid;box-shadow:none}.section{break-inside:auto}.table-wrap{overflow:visible}a{color:inherit}.topbar{margin-top:0}.footer{font-size:10px}}
[hidden]{display:none !important}
.tl{display:inline-block;flex:0 0 auto;width:.62em;height:.62em;border-radius:50%;margin-right:.45em;vertical-align:middle;background:var(--muted)}
.tl-green{background:var(--emerald)}
.tl-yellow{background:var(--amber)}
.tl-red{background:var(--rose)}
.metric.tl-green{border-top-color:var(--emerald)}
.metric.tl-yellow{border-top-color:var(--amber)}
.metric.tl-red{border-top-color:var(--rose)}
.metric-neutral{border-top-color:var(--border)}
.metric .metric-label{display:flex;align-items:center;min-width:0}
.subhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:20px 0 10px}
.subhead h3{margin:0;font-size:15px}
.subhead span,.traffic-legend{color:var(--muted);font-size:12px;overflow-wrap:anywhere}
.attr-row{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:10px 0;font-size:13px;min-width:0;overflow-wrap:anywhere}
.attr-block{margin:12px 0 14px;padding:10px 12px;border:1px dashed var(--violet-bd);border-radius:var(--radius);background:var(--violet-bg)}
.attr-models{margin:6px 0 4px;padding-left:18px;font-size:13px;overflow-wrap:anywhere}
.explorer-controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;min-width:0}
.explorer-controls input[type=search]{flex:1 1 240px;min-width:0;max-width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);color:inherit;font:inherit}
.filter-group{display:flex;flex-wrap:wrap;gap:6px}
.filter-group button{border:1px solid var(--border);border-radius:999px;padding:4px 11px;background:var(--subtle);color:var(--muted);font:inherit;font-size:12px;cursor:pointer}
.filter-group button[aria-pressed=true]{color:var(--indigo);background:var(--indigo-bg);border-color:var(--indigo-bd)}
.claim-cell{overflow-wrap:anywhere;min-width:0}
.explorer-empty{color:var(--muted);text-align:center;padding:16px 0}
.explorer table td details{margin-top:4px}

'''


def theme_css(theme):
    values = ";".join(f"--{k}:{v}" for k, v in theme["light"].items())
    dark = ";".join(f"--{k}:{v}" for k, v in theme["dark"].items())
    return f':root{{{values};--radius:{theme["radius"]}px;--font:{FONT[theme["font"]]};color-scheme:light dark}}@media(prefers-color-scheme:dark){{:root{{{dark}}}}}'


def _ci_text(ratio_obj):
    ci = (ratio_obj or {}).get("ci_95")
    if not ci:
        return ""
    return f" · 95% Wilson [{ci['low']*100:.1f}%, {ci['high']*100:.1f}%]"


TRAFFIC_TONE = {"green": "ok", "yellow": "warn", "red": "negative"}
UNSUBSTANTIATED_CITATIONS = {"uncited_specific", "uncited_vague"}


def light_dot(light, t):
    if not light:
        return ""
    label = t["tl_" + light]
    return f'<span class="tl tl-{light}" role="img" aria-label="{esc(label)}" title="{esc(label)}"></span>'


def rate_badge(ratio_obj, t, *, error_rate=False):
    light = scoring.traffic_light((ratio_obj or {}).get("value"), error_rate=error_rate)
    return badge(percent(ratio_obj), TRAFFIC_TONE[light] if light else "muted")


def _model_label(data, model_id):
    models = ((data.get("panel") or {}).get("policy") or {}).get("selected_models") or []
    model = next((m for m in models if m.get("id") == model_id), None) or {}
    name = model.get("display_name") or model_id
    return f'{name} · {model["api_model"]}' if model.get("api_model") else name


def _rater_text(data, rated, t):
    parts = [f'{t["subjective_unrecorded"] if mid == "unrecorded" else _model_label(data, mid)} ({n})' for mid, n in rated.items()]
    return t["list_sep"].join(parts) if parts else t["not_provided"]


def credibility_block(m, t):
    fc, da = m.get("factual_credibility"), m.get("difficulty_adjusted")
    if not fc and not da:
        return f'<div class="card empty">{esc(t["credibility_legacy"])}</div>'
    blocks = []
    if fc:
        honesty = (fc.get("factual_honesty_score") or {}).get("value")
        honesty_light = scoring.traffic_light(honesty, scale=100)
        contra, misinfo = fc.get("contradiction_rate") or {}, fc.get("misinformation_rate") or {}
        cards = [
            (t["factual_honesty"], "—" if honesty is None else f"{honesty:.1f}", f'/ 100 · {t["factual_honesty_note"]}', honesty_light),
            (t["contradiction_rate"], percent(contra), f'{contra.get("numerator", 0)} / {contra.get("denominator", 0)} · {t["contradiction_note"]}', contra.get("traffic_light")),
            (t["misinfo_rate"], percent(misinfo), f'{misinfo.get("numerator", 0)} / {misinfo.get("denominator", 0)} · {t["misinfo_note"]}', misinfo.get("traffic_light")),
        ]
        blocks.append((t["fact_group"], t["fact_group_note"], cards))
    if da:
        dscore = (da.get("difficulty_adjusted_score") or {}).get("value")
        lead = da.get("lead_time_weighted_support_rate") or {}
        gap = (da.get("overconfidence_gap") or {}).get("value")
        cards = [
            (t["diff_adj_score"], "—" if dscore is None else f"{dscore:.1f}", f'/ 100 · n = {da.get("weighted_n", 0)} · {t["diff_adj_note"]}', scoring.traffic_light(dscore, scale=100)),
            (t["lead_weighted"], percent(lead), f'{lead.get("dated_n", 0)} {t["dated_unit"]} · {t["lead_weighted_note"]}', scoring.traffic_light(lead.get("value"))),
            (t["overconfidence"], "—" if gap is None else f"{gap * 100:+.1f} pp", t["overconfidence_note"], None),
        ]
        blocks.append((t["pred_group"], t["pred_group_note"], cards))
    html_out = ""
    for title, note, cards in blocks:
        tiles = "".join(
            f'<div class="metric metric-neutral{" tl-" + light if light else ""}"><div class="metric-label">{light_dot(light, t)}{esc(label)}</div>'
            f'<div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(detail)}</div></div>'
            for label, value, detail, light in cards
        )
        html_out += f'<div class="subhead"><h3>{esc(title)}</h3><span>{esc(note)}</span></div><div class="metrics">{tiles}</div>'
    return html_out


def _metric_tiles(cards, t):
    return "".join(
        f'<div class="metric metric-neutral{" tl-" + light if light else ""}"><div class="metric-label">{light_dot(light, t)}{esc(label)}</div>'
        f'<div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(detail)}</div></div>'
        for label, value, detail, light in cards
    )


def backfire_block(m, t):
    """翻车率 and cited-source quality; both are null-safe for legacy metrics.json files."""
    rate, pred_rate, sq = m.get("backfire_rate"), m.get("prediction_backfire_rate"), m.get("source_quality_score")
    if not rate and not pred_rate and not sq:
        return ""
    cards = []
    if rate:
        cards.append((t["backfire_rate"], percent(rate), f'{rate.get("numerator", 0)} / {rate.get("denominator", 0)}{_ci_text(rate)} · {t["backfire_note"]}', rate.get("traffic_light")))
    if pred_rate:
        cards.append((t["prediction_backfire_rate"], percent(pred_rate), f'{pred_rate.get("numerator", 0)} / {pred_rate.get("denominator", 0)} · {t["prediction_backfire_note"]}', pred_rate.get("traffic_light")))
    if sq:
        score = sq.get("value")
        cards.append((t["source_quality"], "—" if score is None else f"{score:.1f}",
                      f'/ 100 · n = {sq.get("tagged_n", 0)} / {sq.get("population_n", 0)} · {t["source_quality_note"]}',
                      sq.get("traffic_light")))
    return (f'<div class="subhead"><h3>{esc(t["backfire_group"])}</h3><span>{esc(t["backfire_group_note"])}</span></div>'
            f'<div class="metrics">{_metric_tiles(cards, t)}</div>')


def channel_health_section(m, lang="zh"):
    """YouTube channel engagement health from yt-dlp info.json (metrics.json channel_stats); empty when absent."""
    t = I18N[lang]
    ch = m.get("channel_stats")
    if not ch:
        return ""

    def bench(key):
        obj = ch.get(key) or {}
        low, high = obj.get("benchmark") or [None, None]
        status = t["channel_status"].get(obj.get("status"), "")
        detail = f'{t["channel_benchmark"]} {low * 100:g}–{high * 100:g}%' + (f' · {status}' if status else "")
        return detail

    cards = [
        (t["channel_subs"], "—" if ch.get("subscribers") is None else f'{ch["subscribers"]:,.0f}', f'{t["channel_videos"]}: {ch.get("video_n", 0)}', None),
        (t["channel_v2s"], percent(ch.get("views_to_subscribers_ratio")), bench("views_to_subscribers_ratio"), None),
        (t["channel_like"], percent(ch.get("like_to_view_ratio")), bench("like_to_view_ratio"), None),
        (t["channel_comment"], percent(ch.get("comment_to_view_ratio")), bench("comment_to_view_ratio"), None),
        (t["channel_engagement"], percent(ch.get("engagement_rate")), bench("engagement_rate"), None),
    ]
    flag_chips = "".join(
        f'<span class="kpi-chip {"chip-emerald" if flag == "normal" else "chip-rose"}">{esc(t["channel_flag_labels"].get(flag, flag))}</span>'
        for flag in ch.get("anomaly_flags") or []
    )
    avg_rows = [(t["channel_avg"] + " · " + k, ch.get(src)) for k, src in (
        ("avg_views", "avg_views"), ("median_views", "median_views"), ("avg_likes", "avg_likes"), ("avg_comments", "avg_comments"))]
    avg_html = "".join(f'<tr><td>{esc(label)}</td><td>{"—" if value is None else f"{value:,.1f}"}</td></tr>' for label, value in avg_rows)
    return (
        f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["channel_group"])}</h3>'
        f'<div class="card-header-sub">{esc(t["channel_group_note"])}</div></div>'
        f'<div class="kpi-chips"><span class="kpi-chip chip-sky">{esc(t["channel_flags"])}</span>{flag_chips}</div>'
        f'<div class="metrics">{_metric_tiles(cards, t)}</div>'
        f'<div class="table-wrap"><table><tbody>{avg_html}</tbody></table></div></div>'
    )


def subjective_attribution_html(data, prepared, t):
    p = data["panel"]
    dims = [d["id"] for d in prepared["rubric"]["dimensions"]]
    attr = panel.subjective_attribution(p["policy"], p["reviews"], dims, judge=p.get("judge"))
    rows = next(iter(attr.values()))["rubric_models"] if attr else []
    items = []
    for row in rows:
        role = f' · {t["subjective_judge"]}' if row["role"] == "judge" else ""
        status = "" if row["status"] == "completed" else f' · {row["status"]}'
        identity = f'{row["display_name"]} · {row["provider"]}/{row["api_model"]}' if row.get("api_model") else row["display_name"]
        items.append(f'<li>{esc(identity)}{esc(role)}{esc(status)}</li>')
    multi = any(v["average_score"] is not None for v in attr.values())
    note = t["subjective_avg_multi"] if multi else t["subjective_avg_single"]
    return (f'<div class="attr-block"><div class="attr-row">{badge(t["subjective_badge"], "violet")}<strong>{esc(t["subjective_models"])}</strong></div>'
            f'<ul class="attr-models">{"".join(items)}</ul><p class="source-meta">{esc(note)}</p></div>')


def render_explorer(data, t):
    cases = data.get("cases") or []
    if not cases:
        return ""
    rows = []
    for case in cases:
        st_key = case.get("status", "not_checked")
        citation = case.get("citation_status")
        unsub = "1" if citation in UNSUBSTANTIATED_CITATIONS else "0"
        search = " ".join(str(x) for x in (case.get("id"), case.get("claim"), case.get("original_quote"),
                                            case.get("assessment"), case.get("difficulty_rationale"), case.get("speaker")) if x)
        diff = case.get("difficulty")
        lead = f'{case["lead_time_days"]:g}d' if case.get("lead_time_days") is not None else "—"
        quote = f'<blockquote class="quote">“{esc(case["original_quote"])}”</blockquote>' if isinstance(case.get("original_quote"), str) and case["original_quote"].strip() else ""
        rows.append(
            f'<tr data-status="{esc(st_key)}" data-unsub="{unsub}" data-search="{esc(search.lower())}">'
            f'<td class="hash">{esc(case["id"])}</td>'
            f'<td><div class="claim-cell">{esc(case["claim"])}</div>'
            f'<details><summary>{esc(t["explorer_details"])}</summary>{quote}<p>{esc(case.get("assessment") or "")}</p>'
            f'{citation_links(data, case.get("evidence_ids") or [])}</details></td>'
            f'<td>{badge(t["status"].get(st_key, st_key), STATUS_TONES.get(st_key, "muted"))}</td>'
            f'<td>{esc(t["lifecycle_labels"].get(case.get("lifecycle"), case.get("lifecycle") or "—"))}</td>'
            f'<td>{esc(t["difficulty_tiers"].get(diff, diff) if diff else "—")}</td>'
            f'<td>{esc(t["sourcing_cats"].get(citation or "untagged", "—"))}</td>'
            f'<td>{esc(lead)}</td></tr>'
        )
    filters = [("all", t["explorer_all"]), ("contradicted", t["status"]["contradicted"]), ("mixed", t["status"]["mixed"]),
               ("supported", t["status"]["supported"]), ("pending", t["status"]["pending"]), ("unsubstantiated", t["explorer_unsub"])]
    buttons = "".join(
        f'<button type="button" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">{esc(label)}</button>'
        for key, label in filters
    )
    return (
        f'<section id="explorer" class="section"><div class="section-heading"><div><h2>{esc(t["explorer_title"])}</h2>'
        f'<p class="section-description">{esc(t["explorer_desc"])}</p></div></div>'
        f'<div class="card explorer" data-template="{esc(t["explorer_count"])}">'
        f'<div class="explorer-controls"><input type="search" aria-label="{esc(t["explorer_search"])}" placeholder="{esc(t["explorer_search"])}">'
        f'<div class="filter-group">{buttons}</div></div>'
        f'<p class="source-meta" data-count>{esc(t["explorer_count"].format(n=len(rows), total=len(rows)))}</p>'
        f'<div class="table-wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">{esc(t["th_claim"])}</th>'
        f'<th scope="col">{esc(t["th_verdict"])}</th><th scope="col">{esc(t["th_lifecycle"])}</th>'
        f'<th scope="col">{esc(t["th_tier"])}</th><th scope="col">{esc(t["th_citation"])}</th>'
        f'<th scope="col">{esc(t["th_lead"])}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'<p class="explorer-empty" data-empty hidden>{esc(t["explorer_empty"])}</p></div>{EXPLORER_JS}</section>'
    )


EXPLORER_JS = """<script>
(function () {
  var box = document.getElementById("explorer").querySelector(".explorer");
  var search = box.querySelector("input[type=search]");
  var buttons = box.querySelectorAll("[data-filter]");
  var rows = box.querySelectorAll("tbody tr");
  var count = box.querySelector("[data-count]");
  var empty = box.querySelector("[data-empty]");
  var active = "all";
  function matches(row) {
    var pass = active === "all" || (active === "unsubstantiated"
      ? row.getAttribute("data-unsub") === "1" : row.getAttribute("data-status") === active);
    var q = search.value.trim().toLowerCase();
    return pass && (!q || row.getAttribute("data-search").indexOf(q) !== -1);
  }
  function apply() {
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {
      var on = matches(rows[i]);
      rows[i].hidden = !on;
      if (on) shown++;
    }
    count.textContent = box.getAttribute("data-template").replace("{n}", shown).replace("{total}", rows.length);
    empty.hidden = shown !== 0;
  }
  search.addEventListener("input", apply);
  for (var b = 0; b < buttons.length; b++) {
    buttons[b].addEventListener("click", function (event) {
      active = event.currentTarget.getAttribute("data-filter");
      for (var k = 0; k < buttons.length; k++) {
        buttons[k].setAttribute("aria-pressed", buttons[k] === event.currentTarget ? "true" : "false");
      }
      apply();
    });
  }
  apply();
})();
</script>"""


def objective_metrics(data, lang="zh"):
    t = I18N[lang]
    m = data.get("metrics")
    if m is None:
        return f'<div class="card empty"><strong>{esc(t["no_fact_check_title"])}</strong>{esc(t["no_fact_check_body"])}</div>'
    cards = []
    for label, key, note, tone_cls in (
        (t["strict_support"], "strict_support_rate", t["strict_support_note"], "metric-emerald"),
        (t["accountability"], "accountability", t["accountability_note"], "metric-indigo"),
        (t["adjudication_cov"], "adjudication_coverage", t["adjudication_cov_note"], "metric-teal"),
    ):
        r = m.get(key)
        detail = f'{r["numerator"]} / {r["denominator"]}{_ci_text(r)} · {note}' if r else t["not_provided"]
        cards.append((label, percent(r), detail, tone_cls, scoring.traffic_light(r.get("value")) if r else None))
    b = m.get("brier")
    b_note = f'n = {b["n"]}{" (BSS=" + fmt(b.get("brier_skill_score"), 3) + ")" if b.get("brier_skill_score") is not None else ""} · {t["brier_note"]}' if b else t["not_provided"]
    cards.append((t["brier_label"], fmt(b.get("value"), 3) if b else "—", b_note, "metric-violet", None))
    html_out = f'<div class="attr-row">{badge(t["objective_badge"], "ok")}<span class="traffic-legend">{esc(t["traffic_legend"])}</span></div>'
    html_out += '<div class="metrics">' + "".join(
        f'<div class="metric {tone_cls}{" tl-" + light if light else ""}"><div class="metric-label">{light_dot(light, t)}{esc(label)}</div><div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(note)}</div></div>'
        for label, value, note, tone_cls, light in cards
    ) + '</div>'
    html_out += credibility_block(m, t)
    html_out += backfire_block(m, t)

    # Mandatory methodology disclosures: prediction vs factual split, S/C/M, lifecycle, evidence quality, domains.
    disclosures = []
    by_type = m.get("by_claim_type") or {}
    if by_type:
        type_rows = []
        for ctype in ("prediction", "factual"):
            sub = by_type.get(ctype)
            if sub and sub.get("strict_support_rate"):
                sr = sub["strict_support_rate"]
                label = t["pred_rate"] if ctype == "prediction" else t["fact_rate"]
                type_rows.append(f'<div class="kv"><dt>{esc(label)}</dt><dd>{esc(percent(sr))} ({sr["numerator"]}/{sr["denominator"]})</dd></div>')
        fam = m.get("family_metrics") or {}
        if fam.get("family_weighted_strict_support_rate") is not None:
            type_rows.append(f'<div class="kv"><dt>{esc(t["family_weighted"])}</dt><dd>{fam["family_weighted_strict_support_rate"]*100:.1f}% ({fam["family_count"]} {esc(t["families_unit"])})</dd></div>')
        if type_rows:
            disclosures.append(f'<div class="card"><div class="card-header"><h3>{esc(t["pred_vs_fact"])}</h3></div><div class="card-content"><dl class="key-values">{"".join(type_rows)}</dl></div></div>')
    cc = m.get("categorical_counts") or {}
    lc = m.get("lifecycle_counts") or {}
    eq = m.get("evidence_quality") or {}
    scm_rows = []
    if cc:
        bin_acc = m.get("binary_accuracy_excluding_mixed")
        scm_rows.append(f'<div class="kv"><dt>{esc(t["scm_label"].format(n=m.get("categorical_n", 0)))}</dt><dd><span style="color:var(--emerald)">{cc.get("supported", 0)}</span> / <span style="color:var(--rose)">{cc.get("contradicted", 0)}</span> / <span style="color:var(--amber)">{cc.get("mixed", 0)}</span></dd></div>')
        if bin_acc:
            scm_rows.append(f'<div class="kv"><dt>{esc(t["binary_acc_label"])}</dt><dd>{esc(percent(bin_acc))} ({bin_acc["numerator"]}/{bin_acc["denominator"]})</dd></div>')
    if eq:
        scm_rows.append(f'<div class="kv"><dt>{esc(t["evidence_quality_label"])}</dt><dd>{fmt(eq.get("mean"), 3)} (n={eq.get("assessed_n", 0)}/{eq.get("expected_n", 0)})</dd></div>')
    if lc:
        lc_txt = t["lifecycle_fmt"].format(
            pending=lc.get("pending", 0), awaiting=lc.get("awaiting_evidence", 0),
            disputed=lc.get("disputed", 0), indet=m.get("indeterminate_resolved_n", 0),
        )
        scm_rows.append(f'<div class="kv"><dt>{esc(t["lifecycle_dist"])}</dt><dd>{esc(lc_txt)}</dd></div>')
    if scm_rows:
        disclosures.append(f'<div class="card"><div class="card-header"><h3>{esc(t["scm_detail"])}</h3></div><div class="card-content"><dl class="key-values">{"".join(scm_rows)}</dl></div></div>')
    if disclosures:
        html_out += '<div class="disclosures">' + "".join(disclosures) + '</div>'

    # Stacked Verdict Breakdown Bar Chart (claim types + difficulty tiers)
    verdict_svg = render_verdict_breakdown_svg(m, lang=lang)
    if verdict_svg:
        html_out += (
            f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["verdict_chart_title"])}</h3>'
            f'<div class="card-header-sub">{esc(t["verdict_chart_desc"])}</div></div>'
            f'<div class="viz-wrap">{verdict_svg}</div></div>'
        )

    by_domain = m.get("by_domain") or {}
    if len(by_domain) > 1:
        d_rows = "".join(
            f'<tr><td>{esc(dom)}</td><td>{rate_badge(sub.get("strict_support_rate"), t)}</td>'
            f'<td>{(sub.get("strict_support_rate") or {}).get("numerator",0)}/{(sub.get("strict_support_rate") or {}).get("denominator",0)}</td>'
            f'<td>{esc(percent(sub.get("accountability")))}</td></tr>'
            for dom, sub in by_domain.items()
        )
        html_out += f'<div class="card" style="margin-bottom:20px"><div class="table-wrap"><table><thead><tr><th>{esc(t["domain_breakdown"])}</th><th>{esc(t["strict_support"])}</th><th>S/N</th><th>{esc(t["accountability"])}</th></tr></thead><tbody>{d_rows}</tbody></table></div></div>'

    pdiff = m.get("prediction_difficulty") or {}
    diff_tiers = pdiff.get("by_tier") or {}
    if pdiff.get("rated_n") and diff_tiers:
        nt_sr = pdiff.get("non_trivial_strict_support_rate") or {}
        nt_caption = f'{t["difficulty_non_trivial"]}: {percent(nt_sr)} ({nt_sr.get("numerator", 0)}/{nt_sr.get("denominator", 0)})' if nt_sr.get("denominator") else t["difficulty_title"]
        diff_rows = []
        for tier_key in ("trivial", "moderate", "hard", "non_consensus", "unrated"):
            sub = diff_tiers.get(tier_key)
            if not sub:
                continue
            sr = sub.get("strict_support_rate") or {}
            tier_label = t["difficulty_tiers"].get(tier_key, tier_key)
            mean_s = fmt(sub.get("mean_difficulty_score"), 2) if sub.get("mean_difficulty_score") is not None else "—"
            diff_rows.append(
                f'<tr><td>{esc(tier_label)}</td><td>{sub.get("total_canonical_claims", 0)}</td>'
                f'<td>{rate_badge(sr, t)}</td><td>{sr.get("numerator", 0)}/{sr.get("denominator", 0)}</td>'
                f'<td>{esc(mean_s)}</td></tr>'
            )
        diff_svg = render_difficulty_accuracy_svg(m, lang=lang)
        attr_line = (f'<div class="attr-row">{badge(t["subjective_badge"], "violet")}<span>{esc(t["difficulty_raters"])}: '
                     f'{esc(_rater_text(data, pdiff.get("rated_by_model_id") or {}, t))}</span></div>')
        if diff_rows:
            chart_part = f'<div class="viz-block">{diff_svg}</div>' if diff_svg else ""
            html_out += (
                f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["diff_chart_title"])}</h3>'
                f'<div class="card-header-sub">{esc(t["diff_chart_desc"])}</div></div>'
                f'{attr_line}{chart_part}<div class="table-wrap"><table>'
                f'<caption>{esc(t["difficulty_title"])} · {esc(nt_caption)}</caption>'
                f'<thead><tr><th>{esc(t["th_tier"])}</th><th>{esc(t["th_claims"])}</th>'
                f'<th>{esc(t["strict_support"])}</th><th>S/N</th><th>{esc(t["th_mean_score"])}</th></tr></thead>'
                f'<tbody>{"".join(diff_rows)}</tbody></table></div></div>'
            )

    phor = m.get("prediction_horizon") or {}
    hbuckets = phor.get("buckets") or {}
    if phor.get("dated_n") and hbuckets:
        lead_parts = [
            f'{t["horizon_mean_lead"]}: {fmt(phor.get("mean_lead_time_days"), 1)}d',
            f'{t["horizon_median_lead"]}: {fmt(phor.get("median_lead_time_days"), 1)}d',
        ]
        chips = [
            f'<span class="kpi-chip chip-indigo">{esc(t["horizon_mean_lead"])}: {fmt(phor.get("mean_lead_time_days"), 1)}d</span>',
            f'<span class="kpi-chip chip-teal">{esc(t["horizon_median_lead"])}: {fmt(phor.get("median_lead_time_days"), 1)}d</span>',
        ]
        if phor.get("supported_mean_lead_time_days") is not None:
            lead_parts.append(f'{t["horizon_supported_lead"]}: {fmt(phor.get("supported_mean_lead_time_days"), 1)}d')
            chips.append(f'<span class="kpi-chip chip-emerald">{esc(t["horizon_supported_lead"])}: {fmt(phor.get("supported_mean_lead_time_days"), 1)}d</span>')
        h_rows = []
        for bkey in ("le_30d", "31_90d", "91_180d", "181_365d", "gt_365d"):
            bdata = hbuckets.get(bkey)
            if not bdata or not bdata.get("count"):
                continue
            sr = bdata.get("strict_support_rate") or {}
            blabel = t["horizon_buckets"].get(bkey, bkey)
            avg_d = f'{bdata["mean_lead_time_days"]:.1f}d' if bdata.get("mean_lead_time_days") is not None else "—"
            h_rows.append(
                f'<tr><td>{esc(blabel)}</td><td>{bdata["count"]}</td>'
                f'<td>{rate_badge(sr, t)}</td><td>{sr.get("numerator", 0)}/{sr.get("denominator", 0)}</td>'
                f'<td>{esc(avg_d)}</td></tr>'
            )
        hist_svg = render_horizon_histogram_svg(phor, lang=lang)
        box_html = render_horizon_boxplot_html(data, lang=lang)
        if h_rows:
            hist_block = (
                f'<div class="viz-block"><div class="viz-subhead"><h4>{esc(t["horizon_hist_title"])}</h4>'
                f'<span>{esc(t["horizon_hist_desc"])}</span></div>{hist_svg}</div>'
            ) if hist_svg else ""
            box_block = (
                f'<div class="viz-block"><div class="viz-subhead"><h4>{esc(t["boxplot_title"])}</h4>'
                f'<span>{esc(t["boxplot_desc"])}</span></div>{box_html}</div>'
            ) if box_html else ""
            html_out += (
                f'<div class="card viz-card"><div class="card-header"><h3>{esc(t["horizon_title"])}</h3></div>'
                f'<div class="kpi-chips">{"".join(chips)}</div>'
                f'{hist_block}{box_block}<div class="table-wrap"><table>'
                f'<caption>{esc(t["horizon_title"])} · {esc(" · ".join(lead_parts))}</caption>'
                f'<thead><tr><th>{esc(t["th_horizon"])}</th><th>{esc(t["th_claims"])}</th>'
                f'<th>{esc(t["strict_support"])}</th><th>S/N</th><th>{esc(t["th_avg_lead"])}</th></tr></thead>'
                f'<tbody>{"".join(h_rows)}</tbody></table></div></div>'
            )
    html_out += render_sourcing_rigor_section(m, lang=lang)
    html_out += channel_health_section(m, lang=lang)
    return html_out


def render_panel(data, prepared, theme, lang="zh", expand_details=False):
    t = I18N[lang]
    stats = prepared["stats"]
    if stats is None:
        return f'<div class="card empty">{t["panel_empty"]}</div>'
    p, dims = data["panel"], prepared["rubric"]["dimensions"]
    completed = [r for r in p["reviews"] if r["status"] == "completed"]
    rows = []
    for dim in dims:
        key = dim["id"]
        m = stats["metrics"].get(key, {"n": 0, "mean": None, "sample_variance": None, "sd": None, "min": None, "max": None})
        cells = "".join(f'<td>{fmt(next((r for r in p["reviews"] if r["model_id"] == model), {}).get("scores", {}).get(key),1)}</td>' for model in stats["planned_models"])
        judge_record = p.get("judge") or {}
        judge_score = (judge_record.get("scores") or {}) if judge_record.get("status") == "completed" else {}
        rows.append(f'<tr><td><span class="dim-label" title="{esc(dim_description(dim, lang))}">{esc(dim_label(dim, lang))}</span><span class="n-note">n = {m["n"]} / {len(stats["planned_models"])}</span></td>{cells}<td class="mean-cell">{fmt(m["mean"])}</td><td>{fmt(m["sample_variance"])}</td><td>{fmt(m["sd"])}</td><td>{fmt(m["min"],1)}–{fmt(m["max"],1)}</td><td>{fmt(judge_score.get(key),1)}</td></tr>')
    heads = "".join(f'<th scope="col">{esc(model_name(data,m))}</th>' for m in stats["planned_models"])
    legends = "".join(f'<span class="legend-item"><i class="legend-line" style="border-color:{COLORS[i % len(COLORS)]}"></i>{esc(model_name(data,r["model_id"]))}</span>' for i, r in enumerate(p["reviews"]) if r["status"] == "completed")
    high_disagreement = max(((key, value) for key, value in stats["metrics"].items() if value["sd"] is not None), key=lambda pair: pair[1]["sd"], default=(None, {}))
    label_map = {d["id"]: dim_label(d, lang) for d in dims}
    missing_axes = sum(stats["metrics"].get(k, {}).get("n", 0) < len(stats["planned_models"]) for k in [d["id"] for d in dims])
    body = f'<div class="card"><div class="radar-layout"><div class="radar-wrap">{render_radar(data,theme,prepared["rubric"],lang=lang)}</div><div class="radar-note"><h3>{esc(t["panel_note_h"])}</h3><p>{esc(t["panel_note_p"])}</p><div class="mini-stat"><span>{esc(t["panel_completed"])}</span><strong>{len(completed)} <span style="font-size:12px;font-weight:400">/ {len(stats["planned_models"])} {esc(t["panel_models_unit"])}</span></strong></div><div class="mini-stat"><span>{esc(t["panel_max_sd"])}</span><strong style="font-size:14px">{esc(label_map.get(high_disagreement[0], t["panel_insufficient"]))}</strong><span>SD {fmt(high_disagreement[1].get("sd"))}</span></div><p style="margin-top:15px">{esc(t["panel_missing_note"].format(n=missing_axes))}</p></div></div><div class="legend">{legends}<span class="legend-item"><i class="legend-line mean-line"></i>{esc(t["mean_legend"])}</span></div>{subjective_attribution_html(data, prepared, t)}<div class="table-wrap"><table><caption>{esc(t["table_caption"])}</caption><thead><tr><th scope="col">{esc(t["th_dim"])}</th>{heads}<th scope="col">{esc(t["th_mean"])}</th><th scope="col">{esc(t["th_var"])}</th><th scope="col">{esc(t["th_sd"])}</th><th scope="col">{esc(t["th_range"])}</th><th scope="col">{esc(t["th_judge"])}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="card-footer">{esc(t["panel_footer"])}</div>'
    open_attr = " open" if expand_details else ""
    for dim in dims:
        key = dim["id"]
        reasons = []
        judge_record = p.get("judge") or {}
        scored_judge = [judge_record] if judge_record.get("status") == "completed" and judge_record.get("scores") is not None else []
        for review in p["reviews"] + scored_judge:
            if review["status"] != "completed":
                reasons.append(f'<div class="reason-row"><div class="reason-meta"><span>{esc(model_name(data,review["model_id"]))}</span><span>{esc(review["status"])}</span></div><p>{esc(review.get("note") or review.get("missing_reason") or review["status"])}</p></div>')
                continue
            explanation = review["rationales"][key]
            value = review["scores"].get(key)
            reason = explanation.get("rationale") if value is not None else explanation["missing_reason"]
            supporting = citation_links(data, explanation.get("supporting_evidence_ids", []))
            counter = citation_links(data, explanation.get("counter_evidence_ids", []))
            reasons.append(f'<div class="reason-row"><div class="reason-meta"><span>{esc(model_name(data,review["model_id"]))}{" · Judge" if review is judge_record else ""}</span><span>{fmt(value,1)} / 10</span></div><p>{esc(reason)}</p><span class="source-meta">{esc(t["support_mat"])} </span>{supporting or "—"} <span class="source-meta">{esc(t["counter_mat"])} </span>{counter or "—"}</div>')
        body += f'<details{open_attr}><summary>{esc(dim_label(dim, lang))} · {esc(t["expand_rationale"])}</summary><div class="reason-content">{"".join(reasons)}</div></details>'
    judge = p.get("judge")
    if judge and judge.get("status") == "completed":
        body += f'<div class="judge"><div><div class="judge-label">{esc(t["judge_review"])}</div><div class="judge-note">{esc(t["judge_note"])}</div></div><div><p>{esc(judge["summary"])}</p>{citation_links(data,judge.get("evidence_ids",[]))}</div></div>'
    else:
        body += f'<div class="card-footer">{esc(t["judge_unrun"])}</div>'
    return body + '</div>'


def render_topics(data, lang="zh"):
    t = I18N[lang]
    parts = []
    for index, topic in enumerate(data.get("topics") or [], 1):
        entries = []
        for entry in sorted(topic.get("entries") or [], key=lambda x: _date_sort_key(x["date"])):
            st_key = entry.get("status", "not_checked")
            status, tone = t["status"][st_key], STATUS_TONES[st_key]
            transition = entry.get("transition")
            explanation = ''
            if transition:
                kind = transition["kind"]
                label = transition.get("label") or t["relations"][kind]
                explanation = f'<div class="transition">{badge(label, RELATION_TONES[kind])}{esc(transition.get("explanation", ""))}</div>'
            entries.append(f'<div class="entry"><div class="entry-date">{esc(entry["date"])}</div><div class="entry-body dot-{tone}"><div class="entry-top"><span class="stance">{esc(entry["stance"])}</span>{badge(status,tone)}</div><p class="entry-claim">{esc(entry["claim"])}</p><blockquote class="quote">“{esc(entry["quote"])}”</blockquote><p class="entry-context">{esc(entry.get("context", ""))}</p>{citation_links(data,entry.get("source_ids",[]))}{citation_links(data,entry.get("evidence_ids",[]))}{explanation}</div></div>')
        parts.append(f'<article class="card topic" id="topic-{index}"><header class="topic-header"><div><h3>{esc(topic["label"])}</h3><p>{esc(topic.get("summary",""))}</p></div><span class="topic-index">{index:02d} / {esc(t["topic_nodes"].format(n=len(topic.get("entries") or [])))}</span></header><div class="timeline">{"".join(entries)}</div><div class="topic-assessment"><strong>{esc(t["topic_interp"])}</strong>{esc(topic.get("assessment") or t["topic_unexplained"])}</div></article>')
    return "".join(parts) or f'<div class="card empty">{esc(t["topics_empty"])}</div>'


def render_report(data, view="full", theme=None, rubric=None, lang="zh", expand_details=False):
    if view not in {"full", "longitudinal"}:
        raise ValueError("Unknown report view")
    if lang not in I18N:
        raise ValueError("Unsupported report language: " + str(lang))
    t = I18N[lang]
    prepared = validate_report(data, rubric)
    theme = validate_theme(theme)
    r = data["report"]
    synthetic = f'<div class="synthetic">{t["synthetic_banner"]}</div>' if data["synthetic"] else ''
    nav = t["nav_long"] if view == "longitudinal" else t["nav"]
    navigation = ''.join(f'<a href="#{a}">{esc(b)}</a>' for a, b in nav)
    comp = (data.get("metrics") or {}).get("composite") or {}
    comp_badge = badge(t["composite_withheld"]) if data.get("metrics") and comp.get("value") is None else ""
    overview = f'<section id="overview"><div class="eyebrow">{"LONGITUDINAL REVIEW" if view=="longitudinal" else "CLAIM & CREDIBILITY AUDIT"}</div><h1>{esc(r["title"] if view=="full" else r.get("longitudinal_title") or r["title"])}</h1><p class="subtitle">{esc(r.get("subtitle", ""))}</p><div class="metadata"><span>{esc(r["subject"])}</span><span>{esc(r["period_start"])} — {esc(r["period_end"])}</span><span>{esc(t["as_of_prefix"])} {esc(r["as_of"])}</span>{comp_badge}</div>{synthetic}{objective_metrics(data, lang=lang) if view=="full" else ""}<div class="card"><div class="card-content summary"><span class="summary-label">{esc(t["summary_label"])}</span>{"".join(f"<p>{esc(line)}</p>" for line in r.get("summary") or [])}</div><div class="card-footer">{esc(r.get("scope_note") or t["default_scope_note"])}</div></div></section>'
    topics = f'<section id="longitudinal" class="section"><div class="section-heading"><div><h2>{esc(t["topics_title"])}</h2><p class="section-description">{esc(t["topics_desc"])}</p></div>{badge(t["topics_count"].format(n=len(data.get("topics") or [])))}</div>{render_topics(data, lang=lang)}</section>'
    model = f'<section id="model-panel" class="section"><div class="section-heading"><div><h2>{esc(t["panel_title"])}</h2><p class="section-description">{esc(t["panel_desc"])}</p></div>{badge(t["panel_badge"].format(n=len(prepared["rubric"]["dimensions"])))}</div>{render_panel(data,prepared,theme,lang=lang,expand_details=expand_details)}</section>'
    diff_badge_tones = {"trivial": "ok", "moderate": "info", "hard": "warn", "non_consensus": "violet"}
    cases = []
    for case in data.get("cases") or []:
        if not case.get("notable", True):
            continue
        st_key = case.get("status", "not_checked")
        status, tone = t["status"][st_key], STATUS_TONES[st_key]
        quote_html = f'<blockquote class="quote">“{esc(case["original_quote"])}”</blockquote>' if isinstance(case.get("original_quote"), str) and case["original_quote"].strip() else ""
        badges = [badge(status, tone)]
        if case.get("difficulty"):
            d_label = t["difficulty_tiers"].get(case["difficulty"], case["difficulty"])
            if case.get("difficulty_score") is not None:
                d_label = f"{d_label} ({case['difficulty_score']}/5)"
            badges.append(badge(d_label, diff_badge_tones.get(case["difficulty"], "muted")))
        if case.get("lead_time_days") is not None:
            badges.append(badge(f'{case["lead_time_days"]:g}d', "accent"))
        meta_bits = []
        if case.get("speaker"):
            meta_bits.append(str(case["speaker"]))
        if case.get("endorsement"):
            meta_bits.append(str(case["endorsement"]))
        if case.get("notes"):
            meta_bits.append(str(case["notes"]))
        diff_rat_html = f'<p class="source-meta">{esc(case["difficulty_rationale"])}</p>' if isinstance(case.get("difficulty_rationale"), str) and case["difficulty_rationale"].strip() else ""
        cases.append(f'<article class="card case case-{tone}"><div class="case-top"><h3>{esc(case["title"])}</h3><div>{" ".join(badges)}</div></div><p class="case-claim">{esc(case["claim"])}</p>{quote_html}<p>{esc(case["assessment"])}</p>{diff_rat_html}{citation_links(data,case.get("evidence_ids") or [])}<p class="source-meta">{esc(" · ".join(meta_bits))}</p></article>')
    case_section = f'<section id="cases" class="section"><div class="section-heading"><div><h2>{esc(t["cases_title"])}</h2><p class="section-description">{esc(t["cases_desc"])}</p></div></div><div class="cases">'+''.join(cases)+'</div></section>' if cases and view == "full" else ''
    c = data.get("coverage") or {}
    cost = data.get("costs") or {}
    coverage_rows = [(t["coverage_card"] + " (eligible)", c.get("eligible_sources")), ("acquired", c.get("acquired_sources")), ("extracted", c.get("extracted_sources"))]
    if lang == "zh":
        coverage_rows = [("范围内来源", c.get("eligible_sources")), ("已取得完整材料", c.get("acquired_sources")), ("已完成提取", c.get("extracted_sources"))]
    cost_rows = [("Estimated", cost.get("estimated_usd")), ("Observed", cost.get("observed_usd")), ("Budget cap", cost.get("budget_usd"))]
    if lang == "zh":
        cost_rows = [("规划估算", cost.get("estimated_usd")), ("已核对费用", cost.get("observed_usd")), ("预算上限", cost.get("budget_usd"))]
    coverage_body = ''.join(f'<div class="kv"><dt>{esc(label)}</dt><dd>{value if value is not None else esc(t["not_provided"])}</dd></div>' for label, value in coverage_rows)
    cost_body = ''.join(f'<div class="kv"><dt>{esc(label)}</dt><dd>{"USD "+fmt(value) if value is not None else esc(t["unknown_cost"])}</dd></div>' for label, value in cost_rows)
    notes = (c.get("notes") or []) + (cost.get("notes") or []) + (data.get("limitations") or [])
    if comp.get("blockers"):
        notes = [f"{t['composite_blockers_prefix']}{', '.join(comp['blockers'])}"] + notes
    coverage = f'<section id="coverage" class="section"><div class="section-heading"><h2>{esc(t["coverage_title"])}</h2></div><div class="dual-grid"><div class="card"><div class="card-header"><h3>{esc(t["coverage_card"])}</h3></div><div class="card-content"><dl class="key-values">{coverage_body}</dl></div></div><div class="card"><div class="card-header"><h3>{esc(t["cost_card"])}</h3></div><div class="card-content"><dl class="key-values">{cost_body}</dl></div></div></div><div class="footnotes"><ul>{"".join(f"<li>{esc(note)}</li>" for note in notes)}</ul></div></section>'
    sources = []
    for i, source in enumerate(data.get("sources") or [], 1):
        url = safe_url(source.get("url"))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(t["open_source"])}</a>' if url else esc(t["local_source"])
        pub = source.get("published_at") or t["date_unknown"]
        loc = source.get("locator") or ""
        sources.append(f'<article class="source" id="source-{i}"><span class="source-meta hash">{esc(source["id"])}</span><div class="source-title">{esc(source["title"])}</div><div class="source-meta">{esc(pub)}{" · " + esc(loc) if loc else ""}</div><div class="source-meta">{link}</div><p class="source-excerpt">{esc(source.get("excerpt") or "")}</p></article>')
    source_section = f'<section id="sources" class="section"><div class="section-heading"><div><h2>{esc(t["sources_title"])}</h2><p class="section-description">{esc(t["sources_desc"])}</p></div></div><div class="card sources">'+''.join(sources)+'</div></section>'
    order = topics + model if view == "longitudinal" else model + topics
    explorer = render_explorer(data, t) if view == "full" else ""
    if view == "longitudinal" and data.get("metrics") is None:
        overview += objective_metrics(data, lang=lang)
    body = f'<div class="shell"><header class="topbar"><div class="brand"><span class="mark">✓</span> CLAIM AUDIT <span style="font-weight:400;letter-spacing:0;color:var(--muted)">{esc(t["brand_sub"])}</span></div><div class="top-meta">{esc(r["generated_at"])}<br>{esc(t["static_note"])}</div></header><div class="layout"><aside class="sidebar"><div class="nav-title">{esc(t["nav_title"])}</div>{navigation}<div class="side-note">{t["side_note"]}</div></aside><main class="content">{overview}{order}{case_section}{explorer}{coverage}{source_section}<footer class="footer"><span>{esc(t["footer_synth"] if data["synthetic"] else t["footer_real"])}</span><span class="hash">{esc(prepared["rubric_hash"][:12])} · {esc(str(data.get("data_hash") or t["not_provided"])[:12])}</span></footer></main></div></div>'
    return f'<!DOCTYPE html><html lang="{t["html_lang"]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>{esc(r["title"])}</title><style>{theme_css(theme)}{CSS}</style></head><body>{body}</body></html>'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--view", choices=["full", "longitudinal"], default="full")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--expand-rationales", action="store_true", help="Render rationale <details> expanded (useful for print/PDF)")
    parser.add_argument("--theme-json")
    parser.add_argument("--rubric")
    parser.add_argument("--radar-out")
    args = parser.parse_args(argv)
    try:
        protected = {Path(p).resolve() for p in (args.input, args.theme_json, args.rubric) if p}
        protected.add((ROOT / "assets/evaluation-rubric.json").resolve())
        destinations = [Path(args.out).resolve()] + ([Path(args.radar_out).resolve()] if args.radar_out else [])
        if len(set(destinations)) != len(destinations) or any(p in protected for p in destinations):
            raise ValueError("Output cannot overwrite inputs or another output")
        data = load_json(args.input)
        theme = load_json(args.theme_json) if args.theme_json else None
        rubric = load_json(args.rubric) if args.rubric else None
        page = render_report(data, args.view, theme, rubric, lang=args.lang, expand_details=args.expand_rationales)
        radar = render_radar(data, theme, rubric, standalone=True, lang=args.lang) if args.radar_out else None
        panel.atomic_text(Path(args.out), page)
        if radar is not None:
            panel.atomic_text(Path(args.radar_out), radar)
        print(json.dumps({"html": str(Path(args.out).resolve()), "radar": str(Path(args.radar_out).resolve()) if args.radar_out else None}, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
