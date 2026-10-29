#!/usr/bin/env python3
"""Summarize a routing ledger by model, task kind, tool or project. Reads exports only; never writes a store."""
import argparse
import csv
from collections import Counter, defaultdict
import io
import json
from pathlib import Path
import re
import sys

OUTCOMES = ("pass-after-retry", "pass", "partial", "fail", "pending")
UNKNOWN = {"", "unknown", "—", "-", "n/a", "na", "?", "none recorded"}
UNVERIFIED = re.compile(r"identity (unknown|unavailable)|served identity", re.I)
INFRA = re.compile(r"\b(tool|environment|infrastructure|transport|endpoint) failure\b", re.I)
GROUPS = {"model": "model", "task_kind": "task kind", "tool": "tool", "project": "project"}


class ReportError(ValueError):
    pass


def key_name(name):
    """Column/field names match case-insensitively and treat underscores as spaces (task_kind == Task kind)."""
    return " ".join(str(name).replace("_", " ").split()).lower()


def read_rows(path):
    path = Path(path).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"Cannot read ledger {path}: {exc}") from exc
    header = None
    try:
        if path.suffix.lower() == ".csv":
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            header = reader.fieldnames or []
        elif path.suffix.lower() == ".jsonl":
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            value = json.loads(text)
            if isinstance(value, dict) and "values" in value:
                value = value["values"]
            if isinstance(value, list) and value and all(isinstance(row, list) for row in value):
                header = value[0]
                rows = [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in value[1:]]
            else:
                rows = value
    except (ValueError, csv.Error) as exc:
        raise ReportError(f"{path}: cannot parse ledger: {exc}") from exc
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ReportError(f"{path}: expected rows with a header (CSV, JSONL objects, or a Sheets values export)")
    if header is None:
        header = set().union(*(row.keys() for row in rows)) if rows else ["model", "outcome"]
    if not {"model", "outcome"} <= {key_name(name) for name in header}:
        raise ReportError(f"{path}: ledger needs Model and Outcome columns; include the header row in the export")
    rows = [{key_name(k): ("" if v is None else str(v)) for k, v in row.items()} for row in rows]
    return rows


def load_aliases(path):
    if not path:
        return {}
    try:
        value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        return {field: [(re.compile(pattern, re.I), label) for pattern, label in pairs]
                for field, pairs in value.items()}
    except (OSError, ValueError, TypeError, re.error) as exc:
        raise ReportError(f"Cannot load aliases {path}: {exc}") from exc


def canonical(raw, rules):
    text = " ".join(raw.split())
    for pattern, label in rules:
        if pattern.search(text):
            return label
    return text.lower() or "(blank)"


def outcome(raw):
    text = re.sub(r"[\s_]+", "-", raw.strip().lower())
    for label in OUTCOMES:
        if text.startswith(label):
            # A worker pass still waiting on its gate is not an accepted result yet.
            if label != "pending" and "pending" in text:
                return "pending"
            return label
    return "unknown"


def rework(raw):
    text = raw.strip().lower()
    if text in UNKNOWN:
        return "unknown"
    if text in {"no", "0"} or text.startswith("none"):
        return "none"
    return "some"


def measured(raw):
    return raw.strip().lower() not in UNKNOWN | {"free", "subscription"}


def summarize(rows, by=("model",), aliases=None, project=None, since=None, min_evidence=3):
    aliases = aliases or {}
    groups = defaultdict(Counter)
    mapping = {"model": Counter(), "task_kind": Counter(), "outcome": Counter()}
    skipped = 0
    for row in rows:
        if project and row.get("project", "").strip().lower() != project.lower():
            skipped += 1
            continue
        if since and row.get("date", "")[:10] < since:
            skipped += 1
            continue
        model = canonical(row.get("model", ""), aliases.get("model", []))
        if UNVERIFIED.search(row.get("model", "")) or UNVERIFIED.search(row.get("tool", "")):
            model = "(unverified) " + model
        values = {"model": model, "task_kind": canonical(row.get("task kind", ""), aliases.get("task_kind", [])),
                  "tool": canonical(row.get("tool", ""), aliases.get("tool", [])),
                  "project": canonical(row.get("project", ""), [])}
        result = outcome(row.get("outcome", ""))
        if result == "fail" and INFRA.search(row.get("outcome", "") + " " + row.get("quality notes", "")):
            result = "infra"
        mapping["model"][(row.get("model", ""), model)] += 1
        mapping["task_kind"][(row.get("task kind", ""), values["task_kind"])] += 1
        mapping["outcome"][(row.get("outcome", ""), result)] += 1
        stats = groups[tuple(values[key] for key in by)]
        stats["n"] += 1
        stats[result] += 1
        stats["rework_" + rework(row.get("rework", ""))] += 1
        stats["duration_measured"] += measured(row.get("duration", ""))
        stats["tokens_measured"] += measured(row.get("tokens", ""))
    table = []
    for key, stats in groups.items():
        resolved = sum(stats[label] for label in ("pass-after-retry", "pass", "partial", "fail"))
        accepted = stats["pass"] + stats["pass-after-retry"]
        known_rework = stats["rework_none"] + stats["rework_some"]
        table.append(dict(group=dict(zip(by, key)), n=stats["n"],
            outcomes={label: stats[label] for label in OUTCOMES + ("infra", "unknown")},
            resolved=resolved, accepted=accepted,
            accept_rate=round(accepted / resolved, 3) if resolved else None,
            rework_known=known_rework,
            rework_rate=round(stats["rework_some"] / known_rework, 3) if known_rework else None,
            duration_coverage=round(stats["duration_measured"] / stats["n"], 3),
            tokens_coverage=round(stats["tokens_measured"] / stats["n"], 3),
            thin=resolved < min_evidence))
    table.sort(key=lambda item: (-item["n"], tuple(item["group"].values())))
    return dict(rows=sum(item["n"] for item in table), skipped=skipped, by=list(by), groups=table,
                mapping={field: [dict(raw=raw, normalized=norm, count=count) for (raw, norm), count in counts.most_common()]
                         for field, counts in mapping.items()},
                method="Outcome is inferred from the leading token; a pass that mentions pending counts as pending; "
                       "a fail whose outcome or notes say tool/environment/endpoint failure counts as infra. "
                       "accept_rate = (pass + pass-after-retry) / resolved; pending, infra and unknown are excluded. "
                       "rework_rate counts only rows whose Rework is known. thin = fewer than "
                       f"{min_evidence} resolved rows. Rates describe recorded tasks, not general model ability.")


def percent(value):
    return "—" if value is None else f"{value:.0%}"


def markdown(report, min_n=1, show_mapping=False):
    by = report["by"]
    lines = [f"Rows: {report['rows']} (filtered out: {report['skipped']})", "",
             "| " + " | ".join(GROUPS[key] for key in by) + " | n | pass | retry | partial | fail | pending | infra "
             "| unknown | accept | rework | duration | tokens |",
             "|" + "---|" * (len(by) + 12)]
    for item in report["groups"]:
        if item["n"] < min_n:
            continue
        o = item["outcomes"]
        label = [value + (" ⚠ thin" if index == len(by) - 1 and item["thin"] else "")
                 for index, value in enumerate(item["group"].values())]
        lines.append("| " + " | ".join(label) + f" | {item['n']} | {o['pass']} | {o['pass-after-retry']} | {o['partial']} "
                     f"| {o['fail']} | {o['pending']} | {o['infra']} | {o['unknown']} | {percent(item['accept_rate'])} "
                     f"| {percent(item['rework_rate'])} | {percent(item['duration_coverage'])} "
                     f"| {percent(item['tokens_coverage'])} |")
    lines += ["", "accept = accepted / resolved; rework = rows with rework / rows with known rework; "
              "duration and tokens = share of rows with a measured value.", report["method"]]
    if show_mapping:
        for field, entries in report["mapping"].items():
            lines += ["", f"### {field} mapping", "", "| raw | normalized | count |", "|---|---|---|"]
            lines += [f"| {e['raw'] or '(blank)'} | {e['normalized']} | {e['count']} |" for e in entries]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="+", help="CSV, JSONL, or JSON (Sheets values export with header row)")
    parser.add_argument("--by", default="model", help="comma list of: " + ", ".join(GROUPS))
    parser.add_argument("--aliases", help="JSON {field: [[regex, label], ...]} for model, task_kind, tool")
    parser.add_argument("--project")
    parser.add_argument("--since", help="YYYY-MM-DD; rows without a date are filtered out")
    parser.add_argument("--min-n", type=int, default=1, help="hide groups with fewer rows (markdown only)")
    parser.add_argument("--min-evidence", type=int, default=3, help="resolved rows below this are marked thin")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--mapping", action="store_true", help="also print raw-to-normalized mappings for audit")
    args = parser.parse_args()
    try:
        by = tuple(key.strip() for key in args.by.split(","))
        if not by or any(key not in GROUPS for key in by):
            raise ReportError("--by accepts: " + ", ".join(GROUPS))
        rows = [row for path in args.ledger for row in read_rows(path)]
        report = summarize(rows, by, load_aliases(args.aliases), args.project, args.since, args.min_evidence)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(markdown(report, args.min_n, args.mapping))
        return 0
    except ReportError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
