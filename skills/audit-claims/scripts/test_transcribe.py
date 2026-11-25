#!/usr/bin/env python3
"""Offline regression checks for the paid-request boundaries; no API calls."""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import transcribe_openai as stt


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audio = self.root / "a.mp3"
        self.audio.write_bytes(b"fixture-a-not-for-upload")
        self.manifest = self.root / "audio.jsonl"
        self.manifest.write_text(json.dumps({"id": "a", "path": "a.mp3", "duration_seconds": 60, "language": ["zh", "en"]}) + "\n")
        self.quote = self.root / "estimate.json"
        self.state = self.root / "state"
        self.calls = 0

    def estimate(self, *extras):
        args = stt.parser().parse_args(["estimate", "--manifest", str(self.manifest), "--model", "gpt-transcribe", "--usd-per-minute", "0.01", "--price-source", "https://example.invalid/test-only", "--price-checked-at", dt.datetime.now(dt.timezone.utc).date().isoformat(), "--budget-usd", "1", "--output", str(self.quote), *extras])
        with contextlib.redirect_stdout(io.StringIO()):
            return stt.make_estimate(args)

    def args(self, waiver=False):
        return stt.parser().parse_args(["run", "--cost-waiver" if waiver else "--approve-estimate", str(self.quote), "--approval-note", "Fixture approval; never authorize live uploads", "--state-dir", str(self.state)])

    def transport(self, item, key, timeout):
        self.calls += 1
        return {"text": "原文", "usage": {"type": "duration", "seconds": 60}}, "request-fixture"

    def run_quiet(self, transport=None, waiver=False):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return stt.execute(self.args(waiver), transport or self.transport)

    def test_estimate_is_offline_and_hash_bound(self):
        with mock.patch.object(stt, "call_openai", side_effect=AssertionError("network forbidden")):
            e = self.estimate()
        self.assertEqual(e["estimate_id"], stt.digest(e["plan"]))
        self.assertAlmostEqual(e["plan"]["estimated_usd"], 0.01)
        self.assertIn(("languages[]", "zh"), e["plan"]["items"][0]["request_fields"])

    def test_success_resume_does_not_rebill(self):
        self.estimate()
        self.run_quiet()
        self.run_quiet()
        self.assertEqual(self.calls, 1)
        result = stt.read_json(self.state / "cost-summary.json")
        self.assertIsNone(result["actual_usd"])
        self.assertEqual(result["completed"], 1)

    def test_changed_audio_rejected_before_request(self):
        self.estimate()
        self.audio.write_bytes(b"changed")
        with self.assertRaises(stt.StopRun):
            self.run_quiet()
        self.assertEqual(self.calls, 0)

    def test_tampered_estimate_rejected(self):
        e = self.estimate()
        e["plan"]["budget_usd"] = 1000
        stt.atomic_json(self.quote, e)
        with self.assertRaisesRegex(stt.StopRun, "hash"):
            self.run_quiet()
        self.assertEqual(self.calls, 0)

    def test_expired_estimate_rejected(self):
        e = self.estimate()
        e["plan"]["valid_until"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat()
        e["estimate_id"] = stt.digest(e["plan"])
        stt.atomic_json(self.quote, e)
        with self.assertRaisesRegex(stt.StopRun, "expired"):
            self.run_quiet()

    def test_expired_quote_allows_cache_only_resume(self):
        e = self.estimate()
        self.run_quiet()
        e["plan"]["valid_until"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat()
        e["estimate_id"] = stt.digest(e["plan"])
        stt.atomic_json(self.quote, e)
        summary = self.run_quiet()
        self.assertEqual(summary["remaining"], 0)
        self.assertEqual(self.calls, 1)

    def test_ambiguous_timeout_prevents_repeat(self):
        self.estimate()
        def timeout(*args):
            self.calls += 1
            raise TimeoutError()
        with self.assertRaises(TimeoutError):
            self.run_quiet(timeout)
        with self.assertRaisesRegex(stt.StopRun, "incomplete/uncertain"):
            self.run_quiet()
        self.assertEqual(self.calls, 1)

    def test_response_saved_before_crash_is_recovered(self):
        e = self.estimate()
        item = e["plan"]["items"][0]
        key = item["request_key"]
        stt.atomic_json(self.state / "items" / (key + ".json"), {"status": "submitting", "request_key": key})
        stt.atomic_json(self.state / "responses" / (key + ".json"), {"request_key": key, "response": {"text": "cached"}})
        self.run_quiet()
        self.assertEqual(self.calls, 0)
        self.assertEqual(stt.read_json(self.state / "items" / (key + ".json"))["status"], "succeeded")

    def test_budget_applies_even_with_waiver(self):
        self.estimate("--budget-usd", "0.001")
        with self.assertRaisesRegex(stt.StopRun, "budget"):
            self.run_quiet(waiver=True)
        self.assertEqual(self.calls, 0)

    def test_deviation_stops_before_next_item(self):
        other = self.root / "b.mp3"
        other.write_bytes(b"different")
        with self.manifest.open("a") as f:
            f.write(json.dumps({"id": "b", "path": "b.mp3", "duration_seconds": 60}) + "\n")
        self.estimate("--budget-usd", "100")
        def unexpectedly_long(*args):
            self.calls += 1
            return {"text": "fixture", "usage": {"type": "duration", "seconds": 12000}}, "fixture"
        with self.assertRaisesRegex(stt.StopRun, "deviates"):
            self.run_quiet(unexpectedly_long)
        self.assertEqual(self.calls, 1)
        self.assertEqual(stt.read_json(self.state / "cost-summary.json")["completed"], 1)

    def test_unknown_duration_fails_estimate(self):
        self.manifest.write_text(json.dumps({"id": "a", "path": "a.mp3"}) + "\n")
        with self.assertRaises(stt.StopRun):
            self.estimate()

    def test_duplicate_audio_deduplicated(self):
        with self.manifest.open("a") as f:
            f.write(json.dumps({"id": "a-copy", "path": "a.mp3", "duration_seconds": 60, "language": ["zh", "en"]}) + "\n")
        e = self.estimate()
        self.assertEqual(len(e["plan"]["items"]), 1)
        self.assertEqual(e["plan"]["items"][0]["aliases"], ["a-copy"])

    def test_timestamps_require_compatible_model(self):
        with self.assertRaises(stt.StopRun):
            self.estimate("--timestamps", "word")

    def test_oversize_file_fails_before_network(self):
        with self.audio.open("wb") as f:
            f.truncate(stt.MAX_FILE_BYTES + 1)
        with self.assertRaises(stt.StopRun):
            self.estimate()


if __name__ == "__main__":
    unittest.main()
