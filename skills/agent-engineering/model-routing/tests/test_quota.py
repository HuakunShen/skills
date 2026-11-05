"""Unit tests for live quota fetching across harnesses in scripts/quota.py."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("quota", SKILL / "scripts" / "quota.py")
quota = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quota)


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_agy_json(self):
        agy_raw = {
            "status": "SUCCESS",
            "command": {
                "name": "usage",
                "data": {
                    "groups": [
                        {
                            "name": "Gemini Models",
                            "buckets": [
                                {
                                    "id": "gemini-weekly",
                                    "name": "Weekly Limit Remaining",
                                    "window": "weekly",
                                    "remaining_fraction": 0.9962302446365356,
                                    "reset_time": "2026-11-12T19:05:58Z"
                                },
                                {
                                    "id": "gemini-5h",
                                    "name": "Five Hour Limit Remaining",
                                    "window": "5h",
                                    "remaining_fraction": 0.9868059754371643,
                                    "reset_time": "2026-11-06T00:05:58Z"
                                }
                            ]
                        },
                        {
                            "name": "Claude and GPT models",
                            "buckets": [
                                {
                                    "id": "3p-5h",
                                    "name": "Five Hour Limit Remaining",
                                    "window": "5h",
                                    "remaining_fraction": 1.0,
                                    "reset_time": "2026-11-06T00:30:12Z"
                                }
                            ]
                        }
                    ]
                }
            }
        }
        res = quota.parse_agy_json(agy_raw)
        self.assertEqual(len(res), 3)

        gemini_weekly = res[0]
        self.assertEqual(gemini_weekly["provider"], "antigravity")
        self.assertEqual(gemini_weekly["model_group"], "Gemini Models")
        self.assertEqual(gemini_weekly["window_id"], "weekly")
        self.assertEqual(gemini_weekly["window_minutes"], 10080)
        self.assertEqual(gemini_weekly["remaining_percent"], 99.62)
        self.assertEqual(gemini_weekly["used_percent"], 0.38)
        self.assertEqual(gemini_weekly["resets_at"], "2026-11-12T19:05:58Z")

        gemini_5h = res[1]
        self.assertEqual(gemini_5h["window_id"], "5h")
        self.assertEqual(gemini_5h["window_minutes"], 300)
        self.assertEqual(gemini_5h["remaining_percent"], 98.68)
        self.assertEqual(gemini_5h["used_percent"], 1.32)

        claude_5h = res[2]
        self.assertEqual(claude_5h["model_group"], "Claude and GPT models")
        self.assertEqual(claude_5h["remaining_percent"], 100.0)
        self.assertEqual(claude_5h["used_percent"], 0.0)

    def test_parse_codex_response(self):
        codex_raw = {
            "id": 2,
            "result": {
                "rateLimitsByLimitId": {
                    "codex": {
                        "primary": {
                            "usedPercent": 25.5,
                            "windowDurationMins": 300,
                            "resetsAt": 1730851200
                        },
                        "secondary": {
                            "usedPercent": 50.0,
                            "windowDurationMins": 10080,
                            "resetsAt": "2024-11-13T00:00:00Z"
                        }
                    }
                }
            }
        }
        res = quota.parse_codex_response(codex_raw, account_id="work")
        self.assertEqual(len(res), 2)

        p = res[0]
        self.assertEqual(p["provider"], "codex")
        self.assertEqual(p["account_id"], "work")
        self.assertEqual(p["window_id"], "5h")
        self.assertEqual(p["window_minutes"], 300)
        self.assertEqual(p["used_percent"], 25.5)
        self.assertEqual(p["remaining_percent"], 74.5)
        self.assertEqual(p["resets_at"], "2024-11-06T00:00:00Z")

        s = res[1]
        self.assertEqual(s["window_id"], "weekly")
        self.assertEqual(s["used_percent"], 50.0)
        self.assertEqual(s["remaining_percent"], 50.0)
        self.assertEqual(s["resets_at"], "2024-11-13T00:00:00Z")

    def test_parse_claude_response(self):
        claude_raw = {
            "type": "control_response",
            "request_id": "usage",
            "response": {
                "rate_limits": {
                    "five_hour": {
                        "utilization": 20.0,
                        "resets_at": "2026-11-06T00:30:00Z"
                    },
                    "seven_day": {
                        "utilization": 70.0,
                        "resets_at": "2026-11-12T19:00:00Z"
                    }
                }
            }
        }
        res = quota.parse_claude_response(claude_raw)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["window_id"], "five_hour")
        self.assertEqual(res[0]["used_percent"], 20.0)
        self.assertEqual(res[0]["remaining_percent"], 80.0)
        self.assertEqual(res[1]["window_id"], "seven_day")
        self.assertEqual(res[1]["used_percent"], 70.0)
        self.assertEqual(res[1]["remaining_percent"], 30.0)

    def test_parse_claude_history_file(self):
        hist_file = self.base / "plan-usage-history.json"
        hist_data = [
            {
                "t": 1730851200000,
                "u": {"fh": 12.5, "sd": 45.0, "so": 5.0, "sn": 40.0}
            }
        ]
        hist_file.write_text(json.dumps(hist_data))

        res = quota.parse_claude_history_file(str(hist_file))
        self.assertEqual(len(res), 4)
        self.assertEqual(res[0]["window_id"], "five_hour")
        self.assertEqual(res[0]["used_percent"], 12.5)
        self.assertEqual(res[0]["remaining_percent"], 87.5)
        self.assertEqual(res[0]["source"], "local_file")

    def test_format_table(self):
        windows = [
            {
                "provider": "antigravity",
                "account_id": None,
                "model_group": "Gemini",
                "window_name": "5h",
                "used_percent": 1.0,
                "remaining_percent": 99.0,
                "resets_at": "2026-11-06T00:00:00Z",
                "source": "cli"
            }
        ]
        tbl = quota.format_table(windows)
        self.assertIn("antigravity", tbl)
        self.assertIn("99.0%", tbl)


if __name__ == "__main__":
    unittest.main()
