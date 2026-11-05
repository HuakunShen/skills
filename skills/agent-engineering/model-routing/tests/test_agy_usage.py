"""Unit tests for Antigravity (agy) transcript parsing in scripts/usage.py."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("usage", SKILL / "scripts" / "usage.py")
usage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usage)


class AgyUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agy_transcript_parsing(self):
        transcript_file = self.base / "transcript.jsonl"
        steps = [
            {
                "step_index": 0,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "content": "<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Gemini 3.8 Flash (Medium). No need to comment on this change\n</USER_SETTINGS_CHANGE>",
                "created_at": "2026-11-05T12:00:00Z"
            },
            {
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "input_tokens": 1000,
                "cache_read_tokens": 500,
                "output_tokens": 150,
                "created_at": "2026-11-05T12:00:05Z"
            },
            {
                "step_index": 2,
                "source": "MODEL",
                "type": "GENERIC",
                "content": "output text",
                "created_at": "2026-11-05T12:00:10Z"
            },
            {
                "step_index": 3,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "input_tokens": 2000,
                "cache_read_tokens": 800,
                "output_tokens": 250,
                "created_at": "2026-11-05T12:00:15Z"
            }
        ]
        transcript_file.write_text("\n".join(json.dumps(s) for s in steps) + "\n")

        res = usage.agy(str(transcript_file))
        self.assertEqual(res["source"], "agy_transcript")
        self.assertEqual(res["session_id"], "transcript")
        self.assertEqual(res["models"], ["Gemini 3.8 Flash (Medium)"])
        self.assertEqual(res["measured_steps"], 2)
        self.assertEqual(res["counters"]["input_tokens"], 3000)
        self.assertEqual(res["counters"]["cache_read_tokens"], 1300)
        self.assertEqual(res["counters"]["output_tokens"], 400)
        self.assertEqual(res["counters"]["total_tokens"], 4700)
        self.assertEqual(res["last_receipt_at"], "2026-11-05T12:00:15Z")

    def test_agy_diff_works(self):
        before_file = self.base / "before.json"
        after_file = self.base / "after.json"

        snap1 = {
            "source": "agy_transcript",
            "session_id": "sess-1",
            "models": ["gemini-pro"],
            "token_semantics": "exclusive buckets: input_tokens, cache_read_tokens, output_tokens",
            "counters": {
                "input_tokens": 100,
                "cache_read_tokens": 200,
                "output_tokens": 50,
                "total_tokens": 350
            },
            "scope": "session_snapshot",
            "captured_at": "2026-11-05T10:00:00Z"
        }
        snap2 = {
            "source": "agy_transcript",
            "session_id": "sess-1",
            "models": ["gemini-pro"],
            "token_semantics": "exclusive buckets: input_tokens, cache_read_tokens, output_tokens",
            "counters": {
                "input_tokens": 150,
                "cache_read_tokens": 250,
                "output_tokens": 80,
                "total_tokens": 480
            },
            "scope": "session_snapshot",
            "captured_at": "2026-11-05T10:05:00Z"
        }
        before_file.write_text(json.dumps(snap1))
        after_file.write_text(json.dumps(snap2))

        diff = usage.difference(str(before_file), str(after_file))
        self.assertEqual(diff["scope"], "task_delta")
        self.assertEqual(diff["counters"]["input_tokens"], 50)
        self.assertEqual(diff["counters"]["cache_read_tokens"], 50)
        self.assertEqual(diff["counters"]["output_tokens"], 30)
        self.assertEqual(diff["counters"]["total_tokens"], 130)


if __name__ == "__main__":
    unittest.main()
