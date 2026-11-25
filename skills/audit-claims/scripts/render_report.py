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

ROOT = Path(__file__).resolve().parent.parent
THEME = {
    "light": {"background": "#FAFAFA", "surface": "#FFFFFF", "foreground": "#18181B", "muted": "#71717A", "border": "#E4E4E7", "accent": "#2563EB", "subtle": "#F4F4F5"},
    "dark": {"background": "#101113", "surface": "#18191C", "foreground": "#F4F4F5", "muted": "#A1A1AA", "border": "#303137", "accent": "#7DA8FF", "subtle": "#222328"},
    "radius": 8, "font": "system",
}
FONT = {"system": 'ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif', "sans": 'Arial,"Noto Sans CJK SC","Microsoft YaHei",sans-serif'}
COLORS = ("#64748B", "#3B82F6", "#0F766E", "#8B5CF6", "#B45309")
STATUS_TONES = {"supported": "ok", "contradicted": "negative", "mixed": "muted", "pending": "muted", "indeterminate": "muted", "not_checked": "muted"}
RELATION_TONES = {"continuity": "muted", "genuine_change": "accent", "not_comparable": "muted", "contradiction": "muted", "unclear": "muted"}

I18N = {
    "zh": {
        "html_lang": "zh-CN",
        "brand_sub": "/ 研究报告",
        "static_note": "静态报告 · 可离线阅读",
        "nav_title": "REPORT CONTENTS",
        "side_note": "事实核验与表达评价分开。<br>保留原话、分歧与未知。",
        "nav": [("overview", "报告总览"), ("model-panel", "表达评价"), ("longitudinal", "跨期观点"), ("cases", "核验案例"), ("coverage", "覆盖与成本"), ("sources", "材料与引用")],
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
        "scm_detail": "分类结果明细",
        "lifecycle_dist": "生命周期分布",
        "domain_breakdown": "分领域统计",
        "difficulty_title": "预测难度分层",
        "difficulty_non_trivial": "非平凡预测支持率",
        "difficulty_tiers": {"trivial": "平凡 / 近确定", "moderate": "中等", "hard": "较难", "non_consensus": "反共识 / 高难", "unrated": "未评级"},
        "th_tier": "难度等级", "th_claims": "预测数", "th_mean_score": "均分(1–5)",
        "horizon_title": "预测提前期分布",
        "horizon_mean_lead": "平均提前期", "horizon_median_lead": "中位提前期", "horizon_supported_lead": "命中平均提前期",
        "th_horizon": "提前期区间", "th_avg_lead": "平均天数",
        "horizon_buckets": {"le_30d": "≤30天", "31_90d": "31–90天", "91_180d": "91–180天", "181_365d": "181–365天", "gt_365d": ">365天"},
        "synthetic_banner": "<strong>合成演示数据</strong><span>人物、原话、核验案例与模型分数均为手工构造；未调用真实模型，也不代表真实人物。</span>",
        "mean_legend": "可用评分均值",
        "radar_title": "{n}维表达与可审计性雷达",
        "radar_desc": "零到十分；细线为各模型，粗线为可用评分均值。缺失值或 n<2 轴保留断点。精确数据见报告表格。",
        "radar_synth_desc": "手工合成演示，未调用真实模型。",
        "radar_synth_foot": "合成演示数据 · 未调用真实模型",
        "date_unknown": "日期未提供",
        "composite_withheld": "综合分暂不发布",
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
        "nav": [("overview", "Overview"), ("model-panel", "Expression"), ("longitudinal", "Longitudinal"), ("cases", "Cases"), ("coverage", "Coverage & Cost"), ("sources", "Sources")],
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
        "scm_detail": "Categorical Outcome Breakdown",
        "lifecycle_dist": "Lifecycle Distribution",
        "domain_breakdown": "By Domain",
        "difficulty_title": "Prediction Difficulty Breakdown",
        "difficulty_non_trivial": "Non-trivial prediction support rate",
        "difficulty_tiers": {"trivial": "Trivial / Near-certain", "moderate": "Moderate", "hard": "Hard", "non_consensus": "Non-consensus", "unrated": "Unrated"},
        "th_tier": "Difficulty Tier", "th_claims": "Predictions", "th_mean_score": "Mean (1–5)",
        "horizon_title": "Prediction Lead-Time / Horizon",
        "horizon_mean_lead": "Mean lead time", "horizon_median_lead": "Median lead time", "horizon_supported_lead": "Supported mean lead",
        "th_horizon": "Horizon Bucket", "th_avg_lead": "Avg Lead (d)",
        "horizon_buckets": {"le_30d": "≤30d", "31_90d": "31–90d", "91_180d": "91–180d", "181_365d": "181–365d", "gt_365d": ">365d"},
        "synthetic_banner": "<strong>Synthetic Demo Data</strong><span>Subject, quotes, evidence and scores are manually constructed; no real models were called.</span>",
        "mean_legend": "Available Mean",
        "radar_title": "{n}-Dimension Expression & Auditability Radar",
        "radar_desc": "0 to 10 scale; thin lines are models, thick line is available mean. Missing or n<2 axes remain disconnected.",
        "radar_synth_desc": "Manual synthetic demonstration.",
        "radar_synth_foot": "Synthetic demo data · No real model calls",
        "date_unknown": "Date unknown",
        "composite_withheld": "Composite withheld",
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


def plot_series(values, color, width, css_class="", counts=None, planned_n=None):
    coordinates = []
    for i, value in enumerate(values):
        if value is None:
            coordinates.append(None)
        else:
            angle = -math.pi / 2 + i * math.tau / len(values)
            coordinates.append((310 + 137 * value / 10 * math.cos(angle), 210 + 137 * value / 10 * math.sin(angle)))
    parts = []
    # Break polygon lines on missing values OR sparse mean axes (n < 2 when planned_n >= 2).
    has_sparse = counts is not None and planned_n is not None and planned_n >= 2 and any(c < 2 for c in counts)
    if all(p is not None for p in coordinates) and not has_sparse:
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in coordinates)
        parts.append(f'<polygon class="{css_class}" points="{points}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')
    else:
        for i, point in enumerate(coordinates):
            nxt_idx = (i + 1) % len(values)
            following = coordinates[nxt_idx]
            sparse_edge = has_sparse and (counts[i] < 2 or counts[nxt_idx] < 2)
            if point is not None and following is not None and not sparse_edge:
                parts.append(f'<path class="{css_class}" d="M {point[0]:.3f} {point[1]:.3f} L {following[0]:.3f} {following[1]:.3f}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    for i, point in enumerate(coordinates):
        if point is not None:
            is_sparse = has_sparse and counts[i] < planned_n
            if is_sparse:
                parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="3.4" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="2 1.5"/>')
            else:
                parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="{2.8 if width > 2 else 1.9}" fill="{color}"/>')
    return "".join(parts)


def dim_label(dimension, lang="zh"):
    if lang == "en" and isinstance(dimension.get("label_en"), str) and dimension["label_en"].strip():
        return dimension["label_en"]
    return dimension["label"]


def dim_description(dimension, lang="zh"):
    if lang == "en" and isinstance(dimension.get("description_en"), str) and dimension["description_en"].strip():
        return dimension["description_en"]
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


def svg_label(label, x, y, anchor):
    lines = wrap_svg_text(label, 16)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:-1] + "…"
    parts = [f'<text class="label" text-anchor="{anchor}" dominant-baseline="middle" x="{x:.3f}" y="{y:.3f}"><title>{esc(label)}</title>']
    for i, line in enumerate(lines):
        parts.append(f'<tspan x="{x:.3f}" y="{y+(i-(len(lines)-1)/2)*20:.3f}">{esc(line)}</tspan>')
    return "".join(parts) + '</text>'


def render_radar(data, theme=None, rubric=None, standalone=False, lang="zh"):
    t = I18N[lang]
    prepared = validate_report(data, rubric)
    theme = validate_theme(theme)
    stats, dims = prepared["stats"], prepared["rubric"]["dimensions"]
    fg, muted, border = (theme["light"][k] for k in ("foreground", "muted", "border"))
    dark = theme["dark"]
    n = len(dims)
    dimension_ids = [d["id"] for d in dims]
    legend, chart_height, footer_y = [], 420, 411
    if standalone and stats:
        items = [(model_name(data, review["model_id"]), COLORS[i % len(COLORS)], 1.35, "model")
                 for i, review in enumerate(data["panel"]["reviews"]) if review["status"] == "completed"]
        items.append((t["mean_legend"], fg, 2.8, "mean"))
        y = 416
        for offset in range(0, len(items), 2):
            row = items[offset:offset + 2]
            row_lines = [wrap_svg_text(item[0], 38) for item in row]
            for column, ((label, color, width, kind), lines) in enumerate(zip(row, row_lines)):
                x = 40 + column * 290
                legend.append(f'<g class="radar-legend"><title>{esc(label)}</title><line class="{kind}" x1="{x}" y1="{y}" x2="{x+19}" y2="{y}" stroke="{color}" stroke-width="{width}"/>')
                for line_index, line in enumerate(lines):
                    legend.append(f'<text x="{x+28}" y="{y+line_index*16}" dominant-baseline="middle" font-size="12">{esc(line)}</text>')
                legend.append('</g>')
            y += max(len(lines) for lines in row_lines) * 16 + 12
        footer_y = y + 4
        chart_height = footer_y + 15 if data["synthetic"] else y + 5
    svg_style = (
        f'text{{font-family:{FONT[theme["font"]]};fill:{muted}}}'
        f'.radar-bg{{fill:{theme["light"]["surface"]}}}'
        f'.grid{{fill:none;stroke:{border};stroke-width:1}}.axis{{stroke:{border};stroke-width:1}}'
        f'.label{{font-size:14px}}.mean{{stroke:{fg}}}circle.mean[fill="{fg}"]{{fill:{fg}}}.model{{opacity:.70}}'
        f'@media(prefers-color-scheme:dark){{text{{fill:{dark["muted"]}}}'
        f'.grid,.axis{{stroke:{dark["border"]}}}.mean{{stroke:{dark["foreground"]}}}'
        f'circle.mean[fill="{fg}"]{{fill:{dark["foreground"]}}}.radar-bg{{fill:{dark["surface"]}}}}}'
    )
    desc = t["radar_desc"] + (" " + t["radar_synth_desc"] if data["synthetic"] else "")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 {chart_height}" role="img" aria-labelledby="radar-chart-title radar-chart-desc"><title id="radar-chart-title">{esc(t["radar_title"].format(n=n))}</title><desc id="radar-chart-desc">{esc(desc)}</desc><style>{svg_style}</style><rect class="radar-bg" width="620" height="{chart_height}"/>']
    for level in (2, 4, 6, 8, 10):
        points = " ".join(f'{310+137*level/10*math.cos(-math.pi/2+i*math.tau/n):.3f},{210+137*level/10*math.sin(-math.pi/2+i*math.tau/n):.3f}' for i in range(n))
        parts.append(f'<polygon class="grid" points="{points}"/><text x="316" y="{210-137*level/10+4:.3f}" font-size="10">{level}</text>')
    for i, dimension in enumerate(dims):
        angle = -math.pi / 2 + i * math.tau / n
        x, y = 310 + 137 * math.cos(angle), 210 + 137 * math.sin(angle)
        lx, ly = 310 + 164 * math.cos(angle), 210 + 164 * math.sin(angle)
        anchor = "middle" if abs(math.cos(angle)) < 0.1 else "start" if math.cos(angle) > 0 else "end"
        parts.append(f'<line class="axis" x1="310" y1="210" x2="{x:.3f}" y2="{y:.3f}"/>' + svg_label(dim_label(dimension, lang), lx, ly, anchor))
    if stats:
        for i, review in enumerate(data["panel"]["reviews"]):
            if review["status"] == "completed":
                parts.append(plot_series([review["scores"].get(k) for k in dimension_ids], COLORS[i % len(COLORS)], 1.35, "model"))
        counts = [stats["metrics"].get(k, {}).get("n", 0) for k in dimension_ids]
        planned_n = len(stats["planned_models"])
        parts.append(plot_series([stats["metrics"].get(k, {}).get("mean") for k in dimension_ids], fg, 2.8, "mean", counts=counts, planned_n=planned_n))
    parts.extend(legend)
    if data["synthetic"]:
        parts.append(f'<text x="310" y="{footer_y}" text-anchor="middle" font-size="11">{esc(t["radar_synth_foot"])}</text>')
    parts.append('</svg>')
    return "".join(parts)


CSS = r'''
*{box-sizing:border-box}h1,h2,h3,.stance,.reason-meta,.metadata,.synthetic,.topic-index,.judge-label,.badge,.top-meta{overflow-wrap:anywhere;min-width:0}.legend-item{max-width:100%;overflow-wrap:anywhere}html{scroll-behavior:auto;scroll-padding-top:24px}body{margin:0;background:var(--background);color:var(--foreground);font-family:var(--font);font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:4px}p{margin:0 0 10px;overflow-wrap:anywhere}ul{padding-left:19px;margin:8px 0}li{margin:5px 0;overflow-wrap:anywhere}.shell{max-width:1280px;margin:0 auto;padding:24px 32px 56px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 20px;border-bottom:1px solid var(--border);margin-bottom:30px;font-size:12px;color:var(--muted)}.brand{display:flex;gap:9px;align-items:center;font-weight:650;color:var(--foreground);letter-spacing:.055em}.mark{display:grid;place-items:center;width:25px;height:25px;border:1px solid var(--border);border-radius:6px;font-size:14px}.top-meta{font-size:11px;text-align:right}.layout{display:grid;grid-template-columns:156px minmax(0,1fr);gap:32px}.sidebar{position:sticky;top:24px;align-self:start;font-size:12px}.nav-title{font-size:11px;letter-spacing:.10em;color:var(--muted);margin:0 0 12px;font-weight:650}.sidebar a{display:block;color:var(--muted);padding:8px 10px;margin:2px 0;border-radius:6px}.sidebar a:first-of-type{color:var(--foreground);background:var(--subtle);font-weight:600}.sidebar .side-note{margin:27px 10px 0;color:var(--muted);font-size:11px;line-height:1.8}.content{min-width:0}.eyebrow{font-size:11px;font-weight:600;color:var(--muted);letter-spacing:.04em;margin-bottom:8px}h1{font-size:28px;line-height:1.35;letter-spacing:-.035em;margin:0 0 10px;font-weight:680}h2{font-size:17px;letter-spacing:-.02em;line-height:1.4;margin:0;font-weight:650}h3{font-size:14px;margin:0 0 5px;font-weight:650}.subtitle{font-size:13px;color:var(--muted);max-width:78ch}.metadata{display:flex;flex-wrap:wrap;gap:7px 14px;color:var(--muted);font-size:11px;margin:14px 0 23px}.badge{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border);border-radius:5px;padding:2px 7px;font-size:11px;font-weight:550;line-height:1.5;white-space:normal;color:var(--muted);background:var(--surface)}.badge.accent{color:var(--accent)}.badge.ok{color:var(--foreground)}.badge.negative{color:#BE414B}@media(prefers-color-scheme:dark){.badge.negative{color:#F87171}}.synthetic{display:flex;gap:8px;align-items:baseline;padding:10px 13px;border:1px solid var(--border);background:var(--surface);border-radius:var(--radius);margin:18px 0;font-size:11px;color:var(--muted)}.synthetic strong{color:var(--foreground);font-weight:600}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}.metric{min-width:0;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:16px 16px 14px}.metric-label{color:var(--muted);font-size:11px}.metric-value{font-size:28px;font-weight:650;letter-spacing:-.04em;line-height:1.2;margin:8px 0;font-variant-numeric:tabular-nums}.metric-note{font-size:11px;color:var(--muted);line-height:1.55}.disclosures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:20px}.section{margin-top:28px;scroll-margin-top:24px}.section-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:13px}.section-description{font-size:11px;color:var(--muted);margin-top:5px}.card{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:hidden}.card-header{padding:18px 20px 0}.card-content{padding:18px 20px}.card-footer{border-top:1px solid var(--border);padding:12px 20px;font-size:11px;color:var(--muted)}.summary{font-size:13px;line-height:1.9}.summary .summary-label{display:block;font-size:11px;font-weight:650;letter-spacing:.08em;color:var(--muted);margin-bottom:9px}.radar-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(210px,1fr);align-items:center}.radar-wrap{padding:12px 0 0;min-width:0}.radar-wrap svg{display:block;width:100%;height:auto}.radar-note{padding:20px 22px 20px 4px;font-size:12px;color:var(--muted)}.legend{display:flex;gap:9px 17px;flex-wrap:wrap;font-size:11px;margin:5px 20px 17px;color:var(--muted)}.legend-item{display:flex;align-items:center;gap:7px}.legend-line{width:18px;border-top:2px solid;flex:0 0 auto}.legend-line.mean-line{border-top:3px solid var(--foreground)}.mini-stat{border-top:1px solid var(--border);padding-top:12px;margin-top:14px}.mini-stat strong{display:block;font-size:20px;color:var(--foreground);font-weight:600;margin:3px 0;font-variant-numeric:tabular-nums}.table-wrap{overflow:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:12px;min-width:650px}caption{text-align:left;color:var(--muted);padding:12px 20px 8px;font-size:11px}th,td{border-bottom:1px solid var(--border);padding:11px 12px;text-align:right;vertical-align:top;font-variant-numeric:tabular-nums}th{font-weight:550;color:var(--muted);background:var(--subtle);font-size:11px}th:first-child,td:first-child{text-align:left;min-width:148px;padding-left:20px}th:last-child,td:last-child{padding-right:20px}tbody tr:last-child td{border-bottom:0}.mean-cell{font-weight:650;color:var(--foreground)}.dim-label{display:block;color:var(--foreground);font-weight:550}.n-note{color:var(--muted);font-size:11px;margin-top:2px}details{border-top:1px solid var(--border)}summary{cursor:pointer;padding:12px 20px;font-size:12px;font-weight:550;list-style-position:inside;overflow-wrap:anywhere}.reason-content{padding:0 20px 15px}.reason-row{padding:12px 0;border-top:1px solid var(--border);font-size:12px}.reason-row:first-child{border-top:0}.reason-meta{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:11px;margin-bottom:5px}.citation{display:inline-flex;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;border:1px solid var(--border);border-radius:4px;padding:0 5px;line-height:1.7;margin:2px 3px 2px 0;background:var(--surface);white-space:nowrap}.judge{display:grid;grid-template-columns:110px minmax(0,1fr);gap:15px;padding:17px 20px;border-top:1px solid var(--border);background:var(--subtle)}.judge-label{font-size:11px;font-weight:600}.judge-note{font-size:11px;color:var(--muted);margin-top:3px}.judge p{font-size:12px;margin:0 0 6px}.topic{margin-bottom:16px}.topic-header{display:flex;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--border)}.topic-header p{font-size:11px;color:var(--muted);margin:5px 0 0;max-width:65ch}.topic-index{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.timeline{padding:6px 20px 12px}.entry{display:grid;grid-template-columns:90px minmax(0,1fr);gap:18px;padding:20px 0 0}.entry-date{font-size:11px;color:var(--muted);padding-top:2px;font-variant-numeric:tabular-nums}.entry-body{position:relative;border-left:1px solid var(--border);padding:0 0 20px 20px;min-width:0}.entry:last-child .entry-body{padding-bottom:4px}.entry-body:before{content:"";position:absolute;left:-4px;top:7px;width:7px;height:7px;border:1px solid var(--border);border-radius:50%;background:var(--surface)}.entry-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.stance{font-size:12px;font-weight:600}.entry-claim{font-size:11px;color:var(--muted);margin:5px 0 10px}.quote{margin:0;padding:10px 12px;border:1px solid var(--border);border-radius:6px;background:var(--background);font-size:12px;line-height:1.8;overflow-wrap:anywhere}.entry-context{font-size:11px;color:var(--muted);margin:8px 0 5px}.transition{padding:11px 0 0;font-size:11px;color:var(--muted);line-height:1.8}.transition .badge{margin:0 5px 4px 0}.topic-assessment{padding:12px 20px;border-top:1px solid var(--border);font-size:11px;color:var(--muted);background:var(--background)}.topic-assessment strong{color:var(--foreground);font-weight:550}.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.case{padding:17px 18px}.case-top{display:flex;justify-content:space-between;gap:10px;margin-bottom:10px}.case p{font-size:12px}.case .case-claim{color:var(--muted);font-size:11px}.dual-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.key-values{margin:0}.kv{display:flex;justify-content:space-between;gap:18px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}.kv:first-child{padding-top:0}.kv:last-child{border-bottom:0}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:550;text-align:right;font-variant-numeric:tabular-nums}.footnotes{font-size:11px;color:var(--muted);line-height:1.85}.sources{display:grid;grid-template-columns:1fr 1fr;gap:0 22px;padding:5px 20px}.source{padding:14px 0;border-bottom:1px solid var(--border);scroll-margin-top:24px;min-width:0}.source-title{font-size:12px;font-weight:550;margin:3px 0 5px;overflow-wrap:anywhere}.source-meta{font-size:11px;color:var(--muted);overflow-wrap:anywhere}.source-excerpt{font-size:11px;color:var(--muted);margin:7px 0 0;line-height:1.8}.footer{margin-top:30px;padding-top:15px;border-top:1px solid var(--border);color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}.hash{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.empty{padding:22px 20px;color:var(--muted);font-size:12px}.empty strong{display:block;color:var(--foreground);font-weight:550;margin-bottom:5px}.numeric{font-variant-numeric:tabular-nums}@media(max-width:1050px){.layout{grid-template-columns:120px minmax(0,1fr);gap:24px}.shell{padding:20px 24px 45px}.radar-layout{grid-template-columns:1fr}.radar-note{padding:5px 20px 18px}.mini-stat{display:inline-block;border:0;padding:0;margin:0 25px 0 0}.radar-note>p{margin-bottom:12px}.radar-wrap{max-width:620px;margin:auto;width:100%}}@media(max-width:760px){.radar-wrap .label{font-size:18px}.shell{padding:18px 16px 36px}.layout{display:block}.sidebar{position:static;margin-bottom:24px;display:flex;gap:4px;overflow:auto}.sidebar a{flex:0 0 auto;padding:7px 9px;font-size:11px}.sidebar .nav-title,.sidebar .side-note{display:none}.topbar{margin-bottom:16px;padding-bottom:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.disclosures{grid-template-columns:1fr}.metric{padding:14px}.metric-value{font-size:26px}h1{font-size:25px}.section{margin-top:24px}.card-content,.card-header{padding-left:16px;padding-right:16px}.radar-note{padding:5px 16px 18px}.cases,.dual-grid,.sources{grid-template-columns:1fr}.topic-header{padding:16px}.timeline{padding:0 16px 12px}.entry{grid-template-columns:63px minmax(0,1fr);gap:10px}.entry-body{padding-left:14px}.entry-top{display:block}.entry-top .badge{margin-top:6px}.quote{font-size:11px;padding:9px 10px}.judge{grid-template-columns:1fr;gap:8px;padding:15px 16px}.judge-label,.judge-note{display:inline}.judge-note{margin-left:8px}.synthetic{display:block}.sources{padding:2px 16px}.source:last-child{border:0}}@media print{body{background:#fff;color:#18181b}.shell{max-width:none;padding:0}.layout{display:block}.sidebar{display:none}.card,.metric,.entry,.case{break-inside:avoid}.section{break-inside:auto}.table-wrap{overflow:visible}a{color:inherit}.topbar{margin-top:0}.footer{font-size:10px}}
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


def objective_metrics(data, lang="zh"):
    t = I18N[lang]
    m = data.get("metrics")
    if m is None:
        return f'<div class="card empty"><strong>{esc(t["no_fact_check_title"])}</strong>{esc(t["no_fact_check_body"])}</div>'
    cards = []
    for label, key, note in ((t["strict_support"], "strict_support_rate", t["strict_support_note"]),
                             (t["accountability"], "accountability", t["accountability_note"]),
                             (t["adjudication_cov"], "adjudication_coverage", t["adjudication_cov_note"])):
        r = m.get(key)
        detail = f'{r["numerator"]} / {r["denominator"]}{_ci_text(r)} · {note}' if r else t["not_provided"]
        cards.append((label, percent(r), detail))
    b = m.get("brier")
    b_note = f'n = {b["n"]}{" (BSS=" + fmt(b.get("brier_skill_score"), 3) + ")" if b.get("brier_skill_score") is not None else ""} · {t["brier_note"]}' if b else t["not_provided"]
    cards.append((t["brier_label"], fmt(b.get("value"), 3) if b else "—", b_note))
    html_out = '<div class="metrics">' + "".join(f'<div class="metric"><div class="metric-label">{esc(label)}</div><div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(note)}</div></div>' for label, value, note in cards) + '</div>'

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
            type_rows.append(f'<div class="kv"><dt>Family-weighted</dt><dd>{fam["family_weighted_strict_support_rate"]*100:.1f}% ({fam["family_count"]} families)</dd></div>')
        if type_rows:
            disclosures.append(f'<div class="card"><div class="card-header"><h3>{esc(t["pred_vs_fact"])}</h3></div><div class="card-content"><dl class="key-values">{"".join(type_rows)}</dl></div></div>')
    cc = m.get("categorical_counts") or {}
    lc = m.get("lifecycle_counts") or {}
    eq = m.get("evidence_quality") or {}
    scm_rows = []
    if cc:
        bin_acc = m.get("binary_accuracy_excluding_mixed")
        scm_rows.append(f'<div class="kv"><dt>S / C / M (N={m.get("categorical_n", 0)})</dt><dd>{cc.get("supported", 0)} / {cc.get("contradicted", 0)} / {cc.get("mixed", 0)}</dd></div>')
        if bin_acc:
            scm_rows.append(f'<div class="kv"><dt>Binary S/(S+C)</dt><dd>{esc(percent(bin_acc))} ({bin_acc["numerator"]}/{bin_acc["denominator"]})</dd></div>')
    if eq:
        scm_rows.append(f'<div class="kv"><dt>Evidence quality</dt><dd>{fmt(eq.get("mean"), 3)} (n={eq.get("assessed_n", 0)}/{eq.get("expected_n", 0)})</dd></div>')
    if lc:
        scm_rows.append(f'<div class="kv"><dt>{esc(t["lifecycle_dist"])}</dt><dd>pending={lc.get("pending",0)} · awaiting={lc.get("awaiting_evidence",0)} · disputed={lc.get("disputed",0)} · indet={m.get("indeterminate_resolved_n",0)}</dd></div>')
    if scm_rows:
        disclosures.append(f'<div class="card"><div class="card-header"><h3>{esc(t["scm_detail"])}</h3></div><div class="card-content"><dl class="key-values">{"".join(scm_rows)}</dl></div></div>')
    if disclosures:
        html_out += '<div class="disclosures">' + "".join(disclosures) + '</div>'
    by_domain = m.get("by_domain") or {}
    if len(by_domain) > 1:
        d_rows = "".join(
            f'<tr><td>{esc(dom)}</td><td>{esc(percent(sub.get("strict_support_rate")))}</td>'
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
                f'<td>{esc(percent(sr))}</td><td>{sr.get("numerator", 0)}/{sr.get("denominator", 0)}</td>'
                f'<td>{esc(mean_s)}</td></tr>'
            )
        if diff_rows:
            html_out += (
                f'<div class="card" style="margin-bottom:20px"><div class="table-wrap"><table>'
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
        if phor.get("supported_mean_lead_time_days") is not None:
            lead_parts.append(f'{t["horizon_supported_lead"]}: {fmt(phor.get("supported_mean_lead_time_days"), 1)}d')
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
                f'<td>{esc(percent(sr))}</td><td>{sr.get("numerator", 0)}/{sr.get("denominator", 0)}</td>'
                f'<td>{esc(avg_d)}</td></tr>'
            )
        if h_rows:
            html_out += (
                f'<div class="card" style="margin-bottom:20px"><div class="table-wrap"><table>'
                f'<caption>{esc(t["horizon_title"])} · {esc(" · ".join(lead_parts))}</caption>'
                f'<thead><tr><th>{esc(t["th_horizon"])}</th><th>{esc(t["th_claims"])}</th>'
                f'<th>{esc(t["strict_support"])}</th><th>S/N</th><th>{esc(t["th_avg_lead"])}</th></tr></thead>'
                f'<tbody>{"".join(h_rows)}</tbody></table></div></div>'
            )
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
    body = f'<div class="card"><div class="radar-layout"><div class="radar-wrap">{render_radar(data,theme,prepared["rubric"],lang=lang)}</div><div class="radar-note"><h3>{esc(t["panel_note_h"])}</h3><p>{esc(t["panel_note_p"])}</p><div class="mini-stat"><span>{esc(t["panel_completed"])}</span><strong>{len(completed)} <span style="font-size:12px;font-weight:400">/ {len(stats["planned_models"])} {esc(t["panel_models_unit"])}</span></strong></div><div class="mini-stat"><span>{esc(t["panel_max_sd"])}</span><strong style="font-size:14px">{esc(label_map.get(high_disagreement[0], t["panel_insufficient"]))}</strong><span>SD {fmt(high_disagreement[1].get("sd"))}</span></div><p style="margin-top:15px">{esc(t["panel_missing_note"].format(n=missing_axes))}</p></div></div><div class="legend">{legends}<span class="legend-item"><i class="legend-line mean-line"></i>{esc(t["mean_legend"])}</span></div><div class="table-wrap"><table><caption>{esc(t["table_caption"])}</caption><thead><tr><th scope="col">{esc(t["th_dim"])}</th>{heads}<th scope="col">{esc(t["th_mean"])}</th><th scope="col">{esc(t["th_var"])}</th><th scope="col">{esc(t["th_sd"])}</th><th scope="col">{esc(t["th_range"])}</th><th scope="col">{esc(t["th_judge"])}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="card-footer">{esc(t["panel_footer"])}</div>'
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
            entries.append(f'<div class="entry"><div class="entry-date">{esc(entry["date"])}</div><div class="entry-body"><div class="entry-top"><span class="stance">{esc(entry["stance"])}</span>{badge(status,tone)}</div><p class="entry-claim">{esc(entry["claim"])}</p><blockquote class="quote">“{esc(entry["quote"])}”</blockquote><p class="entry-context">{esc(entry.get("context", ""))}</p>{citation_links(data,entry.get("source_ids",[]))}{citation_links(data,entry.get("evidence_ids",[]))}{explanation}</div></div>')
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
    cases = []
    for case in data.get("cases") or []:
        st_key = case.get("status", "not_checked")
        status, tone = t["status"][st_key], STATUS_TONES[st_key]
        quote_html = f'<blockquote class="quote">“{esc(case["original_quote"])}”</blockquote>' if isinstance(case.get("original_quote"), str) and case["original_quote"].strip() else ""
        badges = [badge(status, tone)]
        if case.get("difficulty"):
            d_label = t["difficulty_tiers"].get(case["difficulty"], case["difficulty"])
            if case.get("difficulty_score") is not None:
                d_label = f"{d_label} ({case['difficulty_score']}/5)"
            badges.append(badge(d_label, "accent" if case["difficulty"] in {"hard", "non_consensus"} else "muted"))
        if case.get("lead_time_days") is not None:
            badges.append(badge(f'{case["lead_time_days"]:g}d', "muted"))
        meta_bits = []
        if case.get("speaker"):
            meta_bits.append(str(case["speaker"]))
        if case.get("endorsement"):
            meta_bits.append(str(case["endorsement"]))
        if case.get("notes"):
            meta_bits.append(str(case["notes"]))
        diff_rat_html = f'<p class="source-meta">{esc(case["difficulty_rationale"])}</p>' if isinstance(case.get("difficulty_rationale"), str) and case["difficulty_rationale"].strip() else ""
        cases.append(f'<article class="card case"><div class="case-top"><h3>{esc(case["title"])}</h3><div>{" ".join(badges)}</div></div><p class="case-claim">{esc(case["claim"])}</p>{quote_html}<p>{esc(case["assessment"])}</p>{diff_rat_html}{citation_links(data,case.get("evidence_ids") or [])}<p class="source-meta">{esc(" · ".join(meta_bits))}</p></article>')
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
        notes = [f"Composite blockers: {', '.join(comp['blockers'])}"] + notes
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
    if view == "longitudinal" and data.get("metrics") is None:
        overview += objective_metrics(data, lang=lang)
    body = f'<div class="shell"><header class="topbar"><div class="brand"><span class="mark">✓</span> CLAIM AUDIT <span style="font-weight:400;letter-spacing:0;color:var(--muted)">{esc(t["brand_sub"])}</span></div><div class="top-meta">{esc(r["generated_at"])}<br>{esc(t["static_note"])}</div></header><div class="layout"><aside class="sidebar"><div class="nav-title">{esc(t["nav_title"])}</div>{navigation}<div class="side-note">{t["side_note"]}</div></aside><main class="content">{overview}{order}{case_section}{coverage}{source_section}<footer class="footer"><span>{esc(t["footer_synth"] if data["synthetic"] else t["footer_real"])}</span><span class="hash">{esc(prepared["rubric_hash"][:12])} · {esc(str(data.get("data_hash") or t["not_provided"])[:12])}</span></footer></main></div></div>'
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
