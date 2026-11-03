"""Claude Code transcript parsing: iteration usage, de-duplication, main vs subagent, idle re-writes."""
from datetime import date, datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("claude_usage", Path(__file__).resolve().parents[1] / "scripts" / "claude_usage.py")
cu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cu)
DAY = date(2026, 10, 30)


def local(hour, minute):
    return datetime(2026, 10, 30, hour, minute).astimezone().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def entry(mid, when, read=0, write=0, out=10, top_level=False, content=None):
    part = {"input_tokens": 1, "cache_read_input_tokens": read, "cache_creation_input_tokens": write,
            "cache_creation": {"ephemeral_5m_input_tokens": write, "ephemeral_1h_input_tokens": 0}, "output_tokens": out}
    usage = part if top_level else {"input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0, "iterations": [part]}
    return {"type": "assistant", "timestamp": when, "message": {"id": mid, "model": "claude-sonnet-5-5", "usage": usage, "content": content or []}}


class ClaudeUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        project = self.base / "proj"
        (project / "s1" / "subagents").mkdir(parents=True)
        main = [entry("m1", local(10, 0), read=100, write=50), entry("m1", local(10, 0), read=100, write=50),
                entry("m2", local(11, 0), read=200, top_level=True)]
        sub = [entry("a1", local(10, 0), write=80000),
               entry("a2", local(10, 1), read=80000, content=[{"type": "tool_use", "name": "Bash", "input": {"command": "sleep 60"}}]),
               entry("a3", local(10, 20), write=90000, read=0)]
        (project / "s1.jsonl").write_text("\n".join(json.dumps(e) for e in main) + "\n{bad json\n")
        (project / "s1" / "subagents" / "agent-x.jsonl").write_text("\n".join(json.dumps(e) for e in sub))
        (project / "s1" / "subagents" / "agent-x.meta.json").write_text(json.dumps({"model": "sonnet", "agentType": "general-purpose"}))
        for path in project.rglob("*.jsonl"):
            os.utime(path, None)

    def tearDown(self):
        self.temp.cleanup()

    def test_iterations_dedupe_and_split(self):
        groups, calls, _, agents, rewrites, bash = cu.analyse(str(self.base), DAY)
        main = groups[("proj", "main", "sonnet-5-5")]
        self.assertEqual(calls[("proj", "main", "sonnet-5-5")], 2)  # m1 counted once
        self.assertEqual(main["read"], 300)                          # iterations + top-level layouts
        self.assertEqual(calls[("proj", "sub", "sonnet-5-5")], 3)
        self.assertEqual(agents[0]["first_context"], 80001)
        self.assertEqual(rewrites["events"], 1)                      # a3 after a 19-minute idle gap
        self.assertEqual(bash["poll"], 1)

    def test_other_day_is_ignored(self):
        groups, *_ = cu.analyse(str(self.base), date(2026, 10, 29))
        self.assertEqual(dict(groups), {})


if __name__ == "__main__":
    unittest.main()
