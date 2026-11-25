#!/usr/bin/env python3
"""Render an escaped, standalone HTML audit dashboard and exact inline-SVG radar.

Python 3.10+ stdlib. No JavaScript, CDN, browser, network or model calls.
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

import model_panel as panel

ROOT = Path(__file__).resolve().parent.parent
DIMENSIONS = ("source_transparency", "fact_interpretation_separation", "prediction_operationality", "uncertainty_expression", "correction_transparency", "counterargument_engagement", "stance_change_explanation", "argument_clarity")
THEME = {
    "light": {"background": "#FAFAFA", "surface": "#FFFFFF", "foreground": "#18181B", "muted": "#71717A", "border": "#E4E4E7", "accent": "#2563EB", "subtle": "#F4F4F5"},
    "dark": {"background": "#101113", "surface": "#18191C", "foreground": "#F4F4F5", "muted": "#A1A1AA", "border": "#303137", "accent": "#7DA8FF", "subtle": "#222328"},
    "radius": 8, "font": "system",
}
FONT = {"system": 'ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif', "sans": 'Arial,"Noto Sans CJK SC","Microsoft YaHei",sans-serif'}
COLORS = ("#64748B", "#3B82F6", "#0F766E", "#8B5CF6", "#B45309")
STATUS = {"supported": ("支持", "ok"), "contradicted": ("证据反驳", "negative"), "mixed": ("部分支持", "muted"), "pending": ("待结算", "muted"), "indeterminate": ("无法判定", "muted"), "not_checked": ("未核验", "muted")}
RELATIONS = {"continuity": "持续主张", "genuine_change": "立场更新", "not_comparable": "不可直接比较", "contradiction": "存在冲突", "unclear": "解释不足"}


def load_json(path):
    def bad(value):
        raise ValueError("Non-finite JSON number: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=bad)


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
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be nonempty text")
    return value


def count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a nonnegative integer")
    return value


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
    # Reject non-finite values even when callers supplied Python dictionaries.
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
    sources = data.get("sources", [])
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
    for topic in data.get("topics", []):
        text(topic.get("id"), "topic.id"); text(topic.get("label"), "topic.label")
        for entry in topic.get("entries", []):
            for key in ("id", "date", "stance", "claim", "quote"):
                text(entry.get(key), "timeline." + key)
            references(entry.get("source_ids", [])); references(entry.get("evidence_ids", []))
            if entry.get("status", "not_checked") not in STATUS:
                raise ValueError("Unknown timeline verification status")
            if entry.get("transition") and entry["transition"].get("kind") not in RELATIONS:
                raise ValueError("Unknown longitudinal relation")
    for case in data.get("cases", []):
        references(case.get("evidence_ids", []))
        if case.get("status", "not_checked") not in STATUS:
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
    for key, value in data.get("costs", {}).items():
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
    index = {s["id"]: i + 1 for i, s in enumerate(data.get("sources", []))}
    return " ".join(f'<a class="citation" href="#source-{index[sid]}" aria-label="查看来源 {esc(sid)}">{esc(sid)}</a>' for sid in ids)


def badge(label, tone="muted"):
    return f'<span class="badge {tone}">{esc(label)}</span>'


def plot_series(values, color, width, css_class=""):
    coordinates = []
    for i, value in enumerate(values):
        if value is None:
            coordinates.append(None)
        else:
            angle = -math.pi / 2 + i * math.tau / len(values)
            coordinates.append((310 + 137 * value / 10 * math.cos(angle), 210 + 137 * value / 10 * math.sin(angle)))
    parts = []
    if all(p is not None for p in coordinates):
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in coordinates)
        parts.append(f'<polygon class="{css_class}" points="{points}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')
    else:
        # Draw only observed adjacent pairs. A missing axis is a gap, never a zero vertex.
        for i, point in enumerate(coordinates):
            following = coordinates[(i + 1) % len(values)]
            if point is not None and following is not None:
                parts.append(f'<path class="{css_class}" d="M {point[0]:.3f} {point[1]:.3f} L {following[0]:.3f} {following[1]:.3f}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    for point in coordinates:
        if point is not None:
            parts.append(f'<circle class="{css_class}" cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="{2.8 if width > 2 else 1.9}" fill="{color}"/>')
    return "".join(parts)


def wrap_svg_text(label, max_units):
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
    # Seven CJK characters fit at the larger mobile size; full labels remain in the table.
    lines = wrap_svg_text(label, 14)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:-1] + "…"
    parts = [f'<text class="label" text-anchor="{anchor}" dominant-baseline="middle" x="{x:.3f}" y="{y:.3f}"><title>{esc(label)}</title>']
    for i, line in enumerate(lines):
        parts.append(f'<tspan x="{x:.3f}" y="{y+(i-(len(lines)-1)/2)*20:.3f}">{esc(line)}</tspan>')
    return "".join(parts) + '</text>'


def render_radar(data, theme=None, rubric=None, standalone=False):
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
        items.append(("可用评分均值", fg, 2.8, "mean"))
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
        f'.label{{font-size:14px}}.mean{{stroke:{fg}}}circle.mean{{fill:{fg}}}.model{{opacity:.70}}'
        f'@media(prefers-color-scheme:dark){{text{{fill:{dark["muted"]}}}'
        f'.grid,.axis{{stroke:{dark["border"]}}}.mean{{stroke:{dark["foreground"]}}}'
        f'circle.mean{{fill:{dark["foreground"]}}}.radar-bg{{fill:{dark["surface"]}}}}}'
    )
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 {chart_height}" role="img" aria-labelledby="radar-chart-title radar-chart-desc"><title id="radar-chart-title">{n}维表达与可审计性雷达</title><desc id="radar-chart-desc">零到十分；细线为各模型，粗线为可用评分均值。缺失值保留断点。精确数据见报告表格。{"手工合成演示，未调用真实模型。" if data["synthetic"] else ""}</desc><style>{svg_style}</style><rect class="radar-bg" width="620" height="{chart_height}"/>']
    for level in (2, 4, 6, 8, 10):
        points = " ".join(f'{310+137*level/10*math.cos(-math.pi/2+i*math.tau/n):.3f},{210+137*level/10*math.sin(-math.pi/2+i*math.tau/n):.3f}' for i in range(n))
        parts.append(f'<polygon class="grid" points="{points}"/><text x="316" y="{210-137*level/10+4:.3f}" font-size="10">{level}</text>')
    for i, dimension in enumerate(dims):
        angle = -math.pi / 2 + i * math.tau / n
        x, y = 310 + 137 * math.cos(angle), 210 + 137 * math.sin(angle)
        lx, ly = 310 + 164 * math.cos(angle), 210 + 164 * math.sin(angle)
        anchor = "middle" if abs(math.cos(angle)) < 0.1 else "start" if math.cos(angle) > 0 else "end"
        parts.append(f'<line class="axis" x1="310" y1="210" x2="{x:.3f}" y2="{y:.3f}"/>' + svg_label(dimension["label"], lx, ly, anchor))
    if stats:
        for i, review in enumerate(data["panel"]["reviews"]):
            if review["status"] == "completed":
                parts.append(plot_series([review["scores"].get(k) for k in dimension_ids], COLORS[i % len(COLORS)], 1.35, "model"))
        parts.append(plot_series([stats["metrics"].get(k, {}).get("mean") for k in dimension_ids], fg, 2.8, "mean"))
    parts.extend(legend)
    if data["synthetic"]:
        parts.append(f'<text x="310" y="{footer_y}" text-anchor="middle" font-size="11">合成演示数据 · 未调用真实模型</text>')
    parts.append('</svg>')
    return "".join(parts)


CSS = r'''
*{box-sizing:border-box}h1,h2,h3,.stance,.reason-meta,.metadata,.synthetic,.topic-index,.judge-label,.badge,.top-meta{overflow-wrap:anywhere;min-width:0}.legend-item{max-width:100%;overflow-wrap:anywhere}html{scroll-behavior:auto;scroll-padding-top:24px}body{margin:0;background:var(--background);color:var(--foreground);font-family:var(--font);font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:4px}p{margin:0 0 10px;overflow-wrap:anywhere}ul{padding-left:19px;margin:8px 0}li{margin:5px 0;overflow-wrap:anywhere}.shell{max-width:1280px;margin:0 auto;padding:24px 32px 56px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 0 20px;border-bottom:1px solid var(--border);margin-bottom:30px;font-size:12px;color:var(--muted)}.brand{display:flex;gap:9px;align-items:center;font-weight:650;color:var(--foreground);letter-spacing:.055em}.mark{display:grid;place-items:center;width:25px;height:25px;border:1px solid var(--border);border-radius:6px;font-size:14px}.top-meta{font-size:11px;text-align:right}.layout{display:grid;grid-template-columns:156px minmax(0,1fr);gap:32px}.sidebar{position:sticky;top:24px;align-self:start;font-size:12px}.nav-title{font-size:10px;letter-spacing:.10em;color:var(--muted);margin:0 0 12px;font-weight:650}.sidebar a{display:block;color:var(--muted);padding:8px 10px;margin:2px 0;border-radius:6px}.sidebar a:first-of-type{color:var(--foreground);background:var(--subtle);font-weight:600}.sidebar .side-note{margin:27px 10px 0;color:var(--muted);font-size:11px;line-height:1.8}.content{min-width:0}.eyebrow{font-size:11px;font-weight:600;color:var(--muted);letter-spacing:.04em;margin-bottom:8px}h1{font-size:28px;line-height:1.35;letter-spacing:-.035em;margin:0 0 10px;font-weight:680}h2{font-size:17px;letter-spacing:-.02em;line-height:1.4;margin:0;font-weight:650}h3{font-size:14px;margin:0 0 5px;font-weight:650}.subtitle{font-size:13px;color:var(--muted);max-width:78ch}.metadata{display:flex;flex-wrap:wrap;gap:7px 14px;color:var(--muted);font-size:11px;margin:14px 0 23px}.badge{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border);border-radius:5px;padding:2px 7px;font-size:10px;font-weight:550;line-height:1.5;white-space:normal;color:var(--muted);background:var(--surface)}.badge.accent{color:var(--accent)}.badge.ok{color:var(--foreground)}.badge.negative{color:#BE414B}.synthetic{display:flex;gap:8px;align-items:baseline;padding:10px 13px;border:1px solid var(--border);background:var(--surface);border-radius:var(--radius);margin:18px 0;font-size:11px;color:var(--muted)}.synthetic strong{color:var(--foreground);font-weight:600}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:24px}.metric{min-width:0;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:16px 16px 14px}.metric-label{color:var(--muted);font-size:11px}.metric-value{font-size:29px;font-weight:650;letter-spacing:-.04em;line-height:1.2;margin:9px 0;font-variant-numeric:tabular-nums}.metric-note{font-size:10px;color:var(--muted);line-height:1.6}.section{margin-top:28px;scroll-margin-top:24px}.section-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:13px}.section-description{font-size:11px;color:var(--muted);margin-top:5px}.card{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:hidden}.card-header{padding:18px 20px 0}.card-content{padding:18px 20px}.card-footer{border-top:1px solid var(--border);padding:12px 20px;font-size:11px;color:var(--muted)}.summary{font-size:13px;line-height:1.9}.summary .summary-label{display:block;font-size:10px;font-weight:650;letter-spacing:.08em;color:var(--muted);margin-bottom:9px}.radar-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(210px,1fr);align-items:center}.radar-wrap{padding:12px 0 0;min-width:0}.radar-wrap svg{display:block;width:100%;height:auto}.radar-note{padding:20px 22px 20px 4px;font-size:12px;color:var(--muted)}.legend{display:flex;gap:9px 17px;flex-wrap:wrap;font-size:10px;margin:5px 20px 17px;color:var(--muted)}.legend-item{display:flex;align-items:center;gap:7px}.legend-line{width:18px;border-top:2px solid;flex:0 0 auto}.legend-line.mean-line{border-top:3px solid var(--foreground)}.mini-stat{border-top:1px solid var(--border);padding-top:12px;margin-top:14px}.mini-stat strong{display:block;font-size:20px;color:var(--foreground);font-weight:600;margin:3px 0;font-variant-numeric:tabular-nums}.table-wrap{overflow:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:11px;min-width:650px}caption{text-align:left;color:var(--muted);padding:12px 20px 8px;font-size:10px}th,td{border-bottom:1px solid var(--border);padding:11px 12px;text-align:right;vertical-align:top;font-variant-numeric:tabular-nums}th{font-weight:550;color:var(--muted);background:var(--subtle);font-size:10px}th:first-child,td:first-child{text-align:left;min-width:148px;padding-left:20px}th:last-child,td:last-child{padding-right:20px}tbody tr:last-child td{border-bottom:0}.mean-cell{font-weight:650;color:var(--foreground)}.dim-label{display:block;color:var(--foreground);font-weight:550}.n-note{color:var(--muted);font-size:9px;margin-top:2px}details{border-top:1px solid var(--border)}summary{cursor:pointer;padding:12px 20px;font-size:11px;font-weight:550;list-style-position:inside;overflow-wrap:anywhere}.reason-content{padding:0 20px 15px}.reason-row{padding:12px 0;border-top:1px solid var(--border);font-size:11px}.reason-row:first-child{border-top:0}.reason-meta{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:10px;margin-bottom:5px}.citation{display:inline-flex;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px;border:1px solid var(--border);border-radius:4px;padding:0 5px;line-height:1.7;margin:2px 3px 2px 0;background:var(--surface);white-space:nowrap}.judge{display:grid;grid-template-columns:110px minmax(0,1fr);gap:15px;padding:17px 20px;border-top:1px solid var(--border);background:var(--subtle)}.judge-label{font-size:11px;font-weight:600}.judge-note{font-size:10px;color:var(--muted);margin-top:3px}.judge p{font-size:12px;margin:0 0 6px}.topic{margin-bottom:16px}.topic-header{display:flex;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--border)}.topic-header p{font-size:11px;color:var(--muted);margin:5px 0 0;max-width:65ch}.topic-index{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.timeline{padding:6px 20px 12px}.entry{display:grid;grid-template-columns:90px minmax(0,1fr);gap:18px;padding:20px 0 0}.entry-date{font-size:11px;color:var(--muted);padding-top:2px;font-variant-numeric:tabular-nums}.entry-body{position:relative;border-left:1px solid var(--border);padding:0 0 20px 20px;min-width:0}.entry:last-child .entry-body{padding-bottom:4px}.entry-body:before{content:"";position:absolute;left:-4px;top:7px;width:7px;height:7px;border:1px solid var(--border);border-radius:50%;background:var(--surface)}.entry-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.stance{font-size:12px;font-weight:600}.entry-claim{font-size:11px;color:var(--muted);margin:5px 0 10px}.quote{margin:0;padding:10px 12px;border:1px solid var(--border);border-radius:6px;background:var(--background);font-size:12px;line-height:1.8;overflow-wrap:anywhere}.entry-context{font-size:10px;color:var(--muted);margin:8px 0 5px}.transition{padding:11px 0 0;font-size:11px;color:var(--muted);line-height:1.8}.transition .badge{margin:0 5px 4px 0}.topic-assessment{padding:12px 20px;border-top:1px solid var(--border);font-size:11px;color:var(--muted);background:var(--background)}.topic-assessment strong{color:var(--foreground);font-weight:550}.cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.case{padding:17px 18px}.case-top{display:flex;justify-content:space-between;gap:10px;margin-bottom:10px}.case p{font-size:12px}.case .case-claim{color:var(--muted);font-size:11px}.dual-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.key-values{margin:0}.kv{display:flex;justify-content:space-between;gap:18px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12px}.kv:first-child{padding-top:0}.kv:last-child{border-bottom:0}.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:550;text-align:right;font-variant-numeric:tabular-nums}.footnotes{font-size:11px;color:var(--muted);line-height:1.85}.sources{display:grid;grid-template-columns:1fr 1fr;gap:0 22px;padding:5px 20px}.source{padding:14px 0;border-bottom:1px solid var(--border);scroll-margin-top:24px;min-width:0}.source-title{font-size:11px;font-weight:550;margin:3px 0 5px;overflow-wrap:anywhere}.source-meta{font-size:10px;color:var(--muted);overflow-wrap:anywhere}.source-excerpt{font-size:10px;color:var(--muted);margin:7px 0 0;line-height:1.8}.footer{margin-top:30px;padding-top:15px;border-top:1px solid var(--border);color:var(--muted);font-size:10px;display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}.hash{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.empty{padding:22px 20px;color:var(--muted);font-size:12px}.empty strong{display:block;color:var(--foreground);font-weight:550;margin-bottom:5px}.numeric{font-variant-numeric:tabular-nums}@media(max-width:1050px){.layout{grid-template-columns:120px minmax(0,1fr);gap:24px}.shell{padding:20px 24px 45px}.radar-layout{grid-template-columns:1fr}.radar-note{padding:5px 20px 18px}.mini-stat{display:inline-block;border:0;padding:0;margin:0 25px 0 0}.radar-note>p{margin-bottom:12px}.radar-wrap{max-width:620px;margin:auto;width:100%}}@media(max-width:760px){.radar-wrap .label{font-size:18px}.shell{padding:18px 16px 36px}.layout{display:block}.sidebar{position:static;margin-bottom:24px;display:flex;gap:4px;overflow:auto}.sidebar a{flex:0 0 auto;padding:7px 9px;font-size:11px}.sidebar .nav-title,.sidebar .side-note{display:none}.topbar{margin-bottom:16px;padding-bottom:14px}.top-meta{font-size:9px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.metric{padding:14px}.metric-value{font-size:27px}h1{font-size:25px}.metadata{font-size:10px}.section{margin-top:24px}.card-content,.card-header{padding-left:16px;padding-right:16px}.radar-note{padding:5px 16px 18px}.cases,.dual-grid,.sources{grid-template-columns:1fr}.topic-header{padding:16px}.timeline{padding:0 16px 12px}.entry{grid-template-columns:63px minmax(0,1fr);gap:10px}.entry-date{font-size:10px}.entry-body{padding-left:14px}.entry-top{display:block}.entry-top .badge{margin-top:6px}.quote{font-size:11px;padding:9px 10px}.judge{grid-template-columns:1fr;gap:8px;padding:15px 16px}.judge-label,.judge-note{display:inline}.judge-note{margin-left:8px}.synthetic{display:block}.sources{padding:2px 16px}.legend{font-size:9px;gap:9px 13px}.source:last-child{border:0}}@media print{body{background:#fff;color:#18181b}.shell{max-width:none;padding:0}.layout{display:block}.sidebar{display:none}.card,.metric,.entry,.case{break-inside:avoid}.section{break-inside:auto}.table-wrap{overflow:visible}a{color:inherit}details:not([open]) .reason-content{display:block}.topbar{margin-top:0}.footer{font-size:9px}}
'''


def theme_css(theme):
    values = ";".join(f"--{k}:{v}" for k, v in theme["light"].items())
    dark = ";".join(f"--{k}:{v}" for k, v in theme["dark"].items())
    return f':root{{{values};--radius:{theme["radius"]}px;--font:{FONT[theme["font"]]};color-scheme:light dark}}@media(prefers-color-scheme:dark){{:root{{{dark}}}}}'


def objective_metrics(data):
    m = data.get("metrics")
    if m is None:
        return '<div class="card empty"><strong>未执行事实核验</strong>此视图分析观点随时间的变化；未核验的断言不计为错误，缺失指标不记作零。</div>'
    cards = []
    for label, key, note in (("严格支持率", "strict_support_rate", "已裁定的分类断言"), ("可检验性", "accountability", "有清晰判定规则的实证观点"), ("裁定覆盖", "adjudication_coverage", "已到期且完成核验的观点")):
        r = m.get(key)
        detail = f'{r["numerator"]} / {r["denominator"]} · {note}' if r else "未提供此指标"
        cards.append((label, percent(r), detail))
    b = m.get("brier")
    cards.append(("概率校准 · Brier", fmt(b.get("value"), 3) if b else "—", f'n = {b["n"]} · 越低越好，仅明确概率' if b else "未提供概率预测样本"))
    return '<div class="metrics">' + "".join(f'<div class="metric"><div class="metric-label">{esc(label)}</div><div class="metric-value">{esc(value)}</div><div class="metric-note">{esc(note)}</div></div>' for label, value, note in cards) + '</div>'


def render_panel(data, prepared, theme):
    stats = prepared["stats"]
    if stats is None:
        return '<div class="card empty"><strong>未进行多模型表达评价</strong>没有评分就不绘制雷达，不以缺失资料代替零分。</div>'
    p, dims = data["panel"], prepared["rubric"]["dimensions"]
    completed = [r for r in p["reviews"] if r["status"] == "completed"]
    rows = []
    for dim in dims:
        key = dim["id"]
        m = stats["metrics"].get(key, {"n": 0, "mean": None, "sample_variance": None, "sd": None, "min": None, "max": None})
        cells = "".join(f'<td>{fmt(next((r for r in p["reviews"] if r["model_id"] == model), {}).get("scores", {}).get(key),1)}</td>' for model in stats["planned_models"])
        judge_record = p.get("judge") or {}
        judge_score = (judge_record.get("scores") or {}) if judge_record.get("status") == "completed" else {}
        rows.append(f'<tr><td><span class="dim-label">{esc(dim["label"])}</span><span class="n-note">n = {m["n"]} / {len(stats["planned_models"])}</span></td>{cells}<td class="mean-cell">{fmt(m["mean"])}</td><td>{fmt(m["sample_variance"])}</td><td>{fmt(m["sd"])}</td><td>{fmt(m["min"],1)}–{fmt(m["max"],1)}</td><td>{fmt(judge_score.get(key),1)}</td></tr>')
    heads = "".join(f'<th scope="col">{esc(model_name(data,m))}</th>' for m in stats["planned_models"])
    legends = "".join(f'<span class="legend-item"><i class="legend-line" style="border-color:{COLORS[i % len(COLORS)]}"></i>{esc(model_name(data,r["model_id"]))}</span>' for i,r in enumerate(p["reviews"]) if r["status"] == "completed")
    high_disagreement = max(((key, value) for key, value in stats["metrics"].items() if value["sd"] is not None), key=lambda pair: pair[1]["sd"], default=(None, {}))
    label_map = {d["id"]: d["label"] for d in dims}
    missing_axes = sum(stats["metrics"].get(k, {}).get("n", 0) < len(stats["planned_models"]) for k in [d["id"] for d in dims])
    body = f'<div class="card"><div class="radar-layout"><div class="radar-wrap">{render_radar(data,theme,prepared["rubric"])}</div><div class="radar-note"><h3>同一份材料，不同判断</h3><p>评价表达方式与可审计性。事实支持率与 Brier 单独呈现，不混入这个雷达。</p><div class="mini-stat"><span>独立完成的评价</span><strong>{len(completed)} <span style="font-size:12px;font-weight:400">/ {len(stats["planned_models"])} 模型</span></strong></div><div class="mini-stat"><span>分歧最大的维度</span><strong style="font-size:14px">{esc(label_map.get(high_disagreement[0],"样本不足"))}</strong><span>样本 SD {fmt(high_disagreement[1].get("sd"))}</span></div><p style="margin-top:15px">{missing_axes} 个维度存在缺失评分。null 保留缺口；n &lt; 2 时不计算样本方差。</p></div></div><div class="legend">{legends}<span class="legend-item"><i class="legend-line mean-line"></i>可用评分均值</span></div><div class="table-wrap"><table><caption>精确数据 · 统一 0–10 量表；Judge 不参与均值与方差</caption><thead><tr><th scope="col">评价维度</th>{heads}<th scope="col">均值</th><th scope="col">样本方差</th><th scope="col">SD</th><th scope="col">最小–最大</th><th scope="col">Judge</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><div class="card-footer">方差采用 ddof = 1。这里描述模型之间的分歧，不是真实可信度的置信区间；共享训练数据也可能带来共同错误。</div>'
    for dim in dims:
        key = dim["id"]
        reasons = []
        judge_record = p.get("judge") or {}
        scored_judge = [judge_record] if judge_record.get("status") == "completed" and judge_record.get("scores") is not None else []
        for review in p["reviews"] + scored_judge:
            if review["status"] != "completed":
                continue
            explanation = review["rationales"][key]
            value = review["scores"].get(key)
            reason = explanation.get("rationale") if value is not None else explanation["missing_reason"]
            supporting = citation_links(data, explanation.get("supporting_evidence_ids", []))
            counter = citation_links(data, explanation.get("counter_evidence_ids", []))
            reasons.append(f'<div class="reason-row"><div class="reason-meta"><span>{esc(model_name(data,review["model_id"]))}{" · 单列复核" if review is judge_record else ""}</span><span>{fmt(value,1)} / 10</span></div><p>{esc(reason)}</p><span class="source-meta">支持材料 </span>{supporting or "—"} <span class="source-meta">反例材料 </span>{counter or "—"}</div>')
        body += f'<details><summary>{esc(dim["label"])} · 展开评分依据</summary><div class="reason-content">{"".join(reasons)}</div></details>'
    judge = p.get("judge")
    if judge and judge.get("status") == "completed":
        body += f'<div class="judge"><div><div class="judge-label">Judge 复核</div><div class="judge-note">单列，不计入统计</div></div><div><p>{esc(judge["summary"])}</p>{citation_links(data,judge.get("evidence_ids",[]))}</div></div>'
    else:
        body += '<div class="card-footer">Judge：未完成或未请求；未据此改变独立模型的原始评分。</div>'
    return body + '</div>'


def render_topics(data):
    parts = []
    for index, topic in enumerate(data.get("topics", []), 1):
        entries = []
        for entry in sorted(topic.get("entries", []), key=lambda x:x["date"]):
            status, tone = STATUS[entry.get("status", "not_checked")]
            transition = entry.get("transition")
            explanation = ''
            if transition:
                label = transition.get("label") or RELATIONS[transition["kind"]]
                explanation = f'<div class="transition">{badge(label,"accent" if transition["kind"]=="genuine_change" else "muted")}{esc(transition.get("explanation", ""))}</div>'
            entries.append(f'<div class="entry"><div class="entry-date">{esc(entry["date"])}</div><div class="entry-body"><div class="entry-top"><span class="stance">{esc(entry["stance"])}</span>{badge(status,tone)}</div><p class="entry-claim">{esc(entry["claim"])}</p><blockquote class="quote">“{esc(entry["quote"])}”</blockquote><p class="entry-context">{esc(entry.get("context", ""))}</p>{citation_links(data,entry.get("source_ids",[]))}{citation_links(data,entry.get("evidence_ids",[]))}{explanation}</div></div>')
        parts.append(f'<article class="card topic" id="topic-{index}"><header class="topic-header"><div><h3>{esc(topic["label"])}</h3><p>{esc(topic.get("summary",""))}</p></div><span class="topic-index">{index:02d} / {len(topic.get("entries",[]))} 个节点</span></header><div class="timeline">{"".join(entries)}</div><div class="topic-assessment"><strong>跨期解读：</strong>{esc(topic.get("assessment","尚未完成解释。"))}</div></article>')
    return "".join(parts) or '<div class="card empty">尚未提供跨期观点记录。</div>'


def render_report(data, view="full", theme=None, rubric=None):
    if view not in {"full", "longitudinal"}:
        raise ValueError("Unknown report view")
    prepared = validate_report(data, rubric)
    theme = validate_theme(theme)
    r = data["report"]
    synthetic = '<div class="synthetic"><strong>合成演示数据</strong><span>人物、原话、核验案例与模型分数均为手工构造；未调用真实模型，也不代表真实人物。</span></div>' if data["synthetic"] else ''
    nav = [("overview","报告总览"),("model-panel","表达评价"),("longitudinal","跨期观点"),("cases","核验案例"),("coverage","覆盖与成本"),("sources","材料与引用")]
    if view == "longitudinal":
        nav = [("overview","报告总览"),("longitudinal","观点时间线"),("model-panel","表达评价"),("coverage","范围与限制"),("sources","材料与引用")]
    navigation = ''.join(f'<a href="#{a}">{b}</a>' for a,b in nav)
    overview = f'<section id="overview"><div class="eyebrow">{ "LONGITUDINAL REVIEW" if view=="longitudinal" else "CLAIM & CREDIBILITY AUDIT"}</div><h1>{esc(r["title"] if view=="full" else r.get("longitudinal_title","观点如何随时间变化"))}</h1><p class="subtitle">{esc(r.get("subtitle", ""))}</p><div class="metadata"><span>{esc(r["subject"])}</span><span>{esc(r["period_start"])} — {esc(r["period_end"])}</span><span>截止 {esc(r["as_of"])}</span>{badge("综合分暂不发布") if data.get("metrics",{} ) and data["metrics"].get("composite",{}).get("value") is None else ""}</div>{synthetic}{objective_metrics(data) if view=="full" else ""}<div class="card"><div class="card-content summary"><span class="summary-label">阅读结论</span>{"".join(f"<p>{esc(line)}</p>" for line in r.get("summary",[]))}</div><div class="card-footer">{esc(r.get("scope_note","本报告只涵盖已列明的材料和日期范围。"))}</div></div></section>'
    topics = f'<section id="longitudinal" class="section"><div class="section-heading"><div><h2>按主题追踪观点</h2><p class="section-description">先核对目标、条件和时间，再判断是连续主张、真实更新还是尚待解释的冲突。</p></div>{badge(str(len(data.get("topics",[])))+" 个主题")}</div>{render_topics(data)}</section>'
    model = f'<section id="model-panel" class="section"><div class="section-heading"><div><h2>表达与可审计性</h2><p class="section-description">独立阅读同一材料，使用同一量表，保留各模型判断与分歧。</p></div>{badge(str(len(prepared["rubric"]["dimensions"]))+" 维 · 0–10")}</div>{render_panel(data,prepared,theme)}</section>'
    cases = []
    for case in data.get("cases", []):
        status, tone = STATUS[case.get("status", "not_checked")]
        cases.append(f'<article class="card case"><div class="case-top"><h3>{esc(case["title"])}</h3>{badge(status,tone)}</div><p class="case-claim">{esc(case["claim"])}</p><p>{esc(case["assessment"])}</p>{citation_links(data,case.get("evidence_ids",[]))}<p class="source-meta">{esc(case.get("notes",""))}</p></article>')
    case_section = '<section id="cases" class="section"><div class="section-heading"><div><h2>可复查的案例</h2><p class="section-description">原始断言、判定理由与证据一起展示。</p></div></div><div class="cases">'+''.join(cases)+'</div></section>' if cases and view=="full" else ''
    c, cost = data.get("coverage", {}), data.get("costs", {})
    coverage_rows = [("范围内来源",c.get("eligible_sources")),("已取得完整材料",c.get("acquired_sources")),("已完成提取",c.get("extracted_sources"))]
    cost_rows = [("规划估算",cost.get("estimated_usd")),("已核对费用",cost.get("observed_usd")),("预算上限",cost.get("budget_usd"))]
    coverage_body = ''.join(f'<div class="kv"><dt>{esc(label)}</dt><dd>{value if value is not None else "未提供"}</dd></div>' for label,value in coverage_rows)
    cost_body = ''.join(f'<div class="kv"><dt>{esc(label)}</dt><dd>{"USD "+fmt(value) if value is not None else "未知 / 未核对"}</dd></div>' for label,value in cost_rows)
    notes = c.get("notes",[]) + cost.get("notes",[]) + data.get("limitations",[])
    coverage = f'<section id="coverage" class="section"><div class="section-heading"><h2>覆盖、费用与限制</h2></div><div class="dual-grid"><div class="card"><div class="card-header"><h3>材料覆盖</h3></div><div class="card-content"><dl class="key-values">{coverage_body}</dl></div></div><div class="card"><div class="card-header"><h3>运行成本</h3></div><div class="card-content"><dl class="key-values">{cost_body}</dl></div></div></div><div class="footnotes"><ul>{"".join(f"<li>{esc(note)}</li>" for note in notes)}</ul></div></section>'
    sources = []
    for i, source in enumerate(data.get("sources",[]),1):
        url = safe_url(source.get("url"))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">打开原始材料 ↗</a>' if url else '本地或合成材料 · 无公开链接'
        sources.append(f'<article class="source" id="source-{i}"><span class="source-meta hash">{esc(source["id"])}</span><div class="source-title">{esc(source["title"])}</div><div class="source-meta">{esc(source.get("published_at","日期未提供"))} · {esc(source.get("locator",""))}</div><div class="source-meta">{link}</div><p class="source-excerpt">{esc(source.get("excerpt",""))}</p></article>')
    source_section = '<section id="sources" class="section"><div class="section-heading"><div><h2>材料与引用</h2><p class="section-description">图表、观点节点和评分依据均可回到这里；材料不足不会自动变成负面结论。</p></div></div><div class="card sources">'+''.join(sources)+'</div></section>'
    order = topics+model if view=="longitudinal" else model+topics
    if view=="longitudinal" and data.get("metrics") is None:
        overview += objective_metrics(data)
    body = f'<div class="shell"><header class="topbar"><div class="brand"><span class="mark">✓</span> CLAIM AUDIT <span style="font-weight:400;letter-spacing:0;color:var(--muted)">/ 研究报告</span></div><div class="top-meta">{esc(r["generated_at"])}<br>静态报告 · 可离线阅读</div></header><div class="layout"><aside class="sidebar"><div class="nav-title">REPORT CONTENTS</div>{navigation}<div class="side-note">事实核验与表达评价分开。<br>保留原话、分歧与未知。</div></aside><main class="content">{overview}{order}{case_section}{coverage}{source_section}<footer class="footer"><span>{"手工合成演示 · 无真实模型调用" if data["synthetic"] else "本页面只格式化已提供的审计结果，不独立证明事实真伪。"}</span><span class="hash">量表 {esc(prepared["rubric_hash"][:12])} · 数据 {esc(str(data.get("data_hash","未提供"))[:12])}</span></footer></main></div></div>'
    return f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>{esc(r["title"])}</title><style>{theme_css(theme)}{CSS}</style></head><body>{body}</body></html>'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--view", choices=["full", "longitudinal"], default="full")
    parser.add_argument("--theme-json")
    parser.add_argument("--rubric")
    parser.add_argument("--radar-out")
    args = parser.parse_args(argv)
    try:
        protected = {Path(p).resolve() for p in (args.input,args.theme_json,args.rubric) if p}
        protected.add((ROOT / "assets/evaluation-rubric.json").resolve())
        destinations = [Path(args.out).resolve()] + ([Path(args.radar_out).resolve()] if args.radar_out else [])
        if len(set(destinations)) != len(destinations) or any(p in protected for p in destinations):
            raise ValueError("Output cannot overwrite inputs or another output")
        data = load_json(args.input)
        theme = load_json(args.theme_json) if args.theme_json else None
        rubric = load_json(args.rubric) if args.rubric else None
        page = render_report(data,args.view,theme,rubric)
        radar = render_radar(data,theme,rubric,standalone=True) if args.radar_out else None
        panel.atomic_text(destinations[0],page)
        if radar is not None:
            panel.atomic_text(destinations[1],radar)
        print(json.dumps({"html":str(destinations[0]),"radar":str(destinations[1]) if radar else None,"view":args.view,"network_calls":0},ensure_ascii=False))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as error:
        print("ERROR: "+str(error),file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
