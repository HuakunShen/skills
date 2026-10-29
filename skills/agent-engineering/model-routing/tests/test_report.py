"""Behavioral checks for ledger normalization and the evidence rules in reports."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("routing_report", SKILL / "scripts" / "report.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def row(model="m", outcome="pass", rework="none", **extra):
    value = {"model": model, "outcome": outcome, "rework": rework, "task kind": "fix", "date": "2026-10-01"}
    value.update(extra)
    return value


def group(result, **key):
    return next(item for item in result["groups"] if item["group"] == key)


class ReportTests(unittest.TestCase):
    def test_pending_gate_is_not_accepted(self):
        stats = group(report.summarize([row(outcome="pass (pending sol review)"), row()]), model="m")
        self.assertEqual(stats["outcomes"]["pending"], 1)
        self.assertEqual((stats["accepted"], stats["resolved"]), (1, 1))

    def test_tool_failure_is_not_counted_against_model(self):
        rows = [row(outcome="fail", **{"quality notes": "tool failure: hung without stdin"}), row(outcome="fail")]
        stats = group(report.summarize(rows), model="m")
        self.assertEqual((stats["outcomes"]["infra"], stats["outcomes"]["fail"], stats["resolved"]), (1, 1, 1))

    def test_unknown_values_are_not_zero_or_pass(self):
        stats = group(report.summarize([row(outcome="looks fine", rework=""), row(rework="2 rounds")]), model="m")
        self.assertEqual(stats["outcomes"]["unknown"], 1)
        self.assertEqual((stats["rework_known"], stats["rework_rate"]), (1, 1.0))
        self.assertIsNone(group(report.summarize([row(outcome="")]), model="m")["accept_rate"])

    def test_aliases_merge_labels_and_mapping_is_auditable(self):
        aliases = {"model": [(report.re.compile("deepseek", report.re.I), "deepseek")]}
        result = report.summarize([row(model="DeepSeek V4.1 (free)"), row(model="opencode/deepseek")], aliases=aliases)
        self.assertEqual(group(result, model="deepseek")["n"], 2)
        self.assertEqual({e["raw"] for e in result["mapping"]["model"]}, {"DeepSeek V4.1 (free)", "opencode/deepseek"})

    def test_unverified_identity_is_kept_apart(self):
        aliases = {"model": [(report.re.compile("sol/high"), "sol/high")]}
        rows = [row(model="sol/high"), row(model="requested sol/high; served identity unknown")]
        result = report.summarize(rows, aliases=aliases)
        self.assertEqual(group(result, model="(unverified) sol/high")["n"], 1)
        self.assertEqual(group(result, model="sol/high")["n"], 1)

    def test_thin_groups_and_filters(self):
        result = report.summarize([row(), row(), row(date="2026-09-01")], since="2026-10-01")
        self.assertEqual(result["skipped"], 1)
        self.assertTrue(group(result, model="m")["thin"])
        result = report.summarize([row(project="a"), row(project="b")], project="A", min_evidence=1)
        self.assertEqual((result["rows"], result["skipped"]), (1, 1))
        self.assertFalse(group(result, model="m")["thin"])

    def test_reads_sheets_export_and_rejects_missing_header(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "export.json"
            path.write_text(json.dumps({"values": [["Model", "Outcome", "Rework"], ["m", "pass"]]}))
            self.assertEqual(report.read_rows(path)[0]["rework"], "")
            path.write_text(json.dumps({"values": [["m", "pass", "none"]]}))
            with self.assertRaises(report.ReportError):
                report.read_rows(path)

    def test_jsonl_snake_case_nulls_and_csv_give_same_report(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.jsonl"
            path.write_text("\n".join(json.dumps(v) for v in (
                {"model": "m", "task_kind": "fix", "outcome": "pass", "rework": None, "tokens": None},
                {"Model": "m", "Task kind": "fix", "Outcome": "fail", "Rework": "once", "Tokens": 5})) + "\n")
            rows = report.read_rows(path)
            self.assertEqual({r["task kind"] for r in rows}, {"fix"})
            stats = group(report.summarize(rows, ("model", "task_kind")), model="m", task_kind="fix")
            self.assertEqual((stats["n"], stats["rework_known"], stats["tokens_coverage"]), (2, 1, 0.5))
        for name in ("jsonl", "csv"):
            with self.subTest(name):
                data = report.read_rows(SKILL / "examples" / f"ledger.{name}")
                self.assertEqual(len(data), 15)
        aliases = report.load_aliases(SKILL / "examples" / "aliases.json")
        reports = [report.summarize(report.read_rows(SKILL / "examples" / f"ledger.{n}"), ("model", "task_kind"), aliases)["groups"]
                   for n in ("jsonl", "csv")]
        self.assertEqual(reports[0], reports[1])

    def test_example_ledger_matches_documented_rule(self):
        rows = report.read_rows(SKILL / "examples" / "ledger.jsonl")
        result = report.summarize(rows, ("model", "task_kind"), report.load_aliases(SKILL / "examples" / "aliases.json"))
        stats = group(result, model="deepseek-v4.1-flash-free", task_kind="scoped bug fix (non-security)")
        self.assertEqual((stats["resolved"], stats["accepted"]), (4, 3))
        self.assertEqual(group(result, model="deepseek-v4.1-flash-free", task_kind="run tests and triage failures")["outcomes"]["infra"], 1)


if __name__ == "__main__":
    unittest.main()
