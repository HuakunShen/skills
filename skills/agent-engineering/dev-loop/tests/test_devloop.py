"""Behavior checks: layering, instruction sources, safe init and scaffold."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("devloop", ROOT / "scripts" / "devloop.py")
devloop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(devloop)


class DevLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "proj" / "sub"
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, **body}))
        return path

    def resolve(self, **kw):
        return devloop.resolve(self.project, env={}, home=self.home, **kw)

    def test_unconfigured_is_read_only_and_has_defaults(self):
        before = set(self.root.rglob("*"))
        result = self.resolve()
        self.assertFalse(result["configured"])
        self.assertEqual(result["layout"]["decisions"], "docs/decisions")
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_project_overrides_user_but_keeps_other_sources(self):
        self.write(self.home / ".config/dev-loop/config.json", {
            "inbox": {"kind": "notion", "uri": "n"}, "layout": {"plans": "specs"},
            "instruction_sources": [{"id": "rules", "kind": "notion", "uri": "n/rules"},
                                    {"id": "style", "kind": "text", "text": "short"}]})
        self.write(self.project.parent / ".dev-loop/config.json", {
            "inbox": {"kind": "github_projects", "uri": "g"},
            "instruction_sources": [{"id": "rules", "kind": "s3", "uri": "s3://b/k", "applies_to": ["code_review"]}]})
        result = self.resolve()
        self.assertEqual(result["inbox"]["kind"], "github_projects")
        self.assertEqual(result["layout"]["plans"], "specs")
        ids = {s["id"]: s for s in result["instruction_sources"]}
        self.assertEqual(ids["rules"]["kind"], "s3")
        self.assertTrue(ids["rules"]["fetch_required"])
        self.assertEqual(ids["style"]["text"], "short")
        self.assertEqual(result["sources_by_stage"]["code_review"], ["rules", "style"])
        self.assertEqual(result["sources_by_stage"]["intent"], ["style"])

    def test_local_file_source_is_inlined_relative_to_config(self):
        cfg = self.project.parent / ".dev-loop/config.json"
        (cfg.parent).mkdir(parents=True)
        (cfg.parent / "review.md").write_text("use sol")
        self.write(cfg, {"instruction_sources": [{"id": "r", "kind": "file", "uri": "review.md"}]})
        self.assertEqual(self.resolve()["instruction_sources"][0]["text"], "use sol")

    def test_missing_local_source_and_explicit_config_fail(self):
        cfg = self.write(self.project / ".dev-loop/config.json",
                         {"instruction_sources": [{"id": "r", "kind": "file", "uri": "nope.md"}]})
        with self.assertRaises(devloop.ConfigError):
            self.resolve()
        with self.assertRaises(devloop.ConfigError):
            self.resolve(explicit=str(self.root / "missing.json"))
        cfg.unlink()

    def test_validation_rejects_bad_input(self):
        for body in ({"layout": {"bogus": "x"}}, {"instruction_sources": [{"id": "a", "kind": "file", "uri": "x", "applies_to": ["nope"]}]},
                     {"instruction_sources": [{"id": "a", "kind": "file", "uri": "x"}, {"id": "a", "kind": "file", "uri": "y"}]},
                     {"instruction_sources": [{"id": "a", "kind": "file", "uri": "x", "mode": "zap"}]}):
            path = self.write(self.root / "bad.json", body)
            with self.assertRaises(devloop.ConfigError):
                devloop.load(path)

    def test_init_never_overwrites(self):
        path = self.root / "c.json"
        devloop.initialize(path)
        devloop.load(path)
        with self.assertRaises(devloop.ConfigError):
            devloop.initialize(path)

    def test_scaffold_is_idempotent_and_ignores_private_dirs(self):
        project = self.root / "fresh"
        project.mkdir()
        first = devloop.scaffold(project, devloop.DEFAULT_LAYOUT, ROOT / "templates")
        self.assertTrue((project / "docs/plans/WORK-REGISTER.md").is_file())
        self.assertTrue((project / "docs/plans/INTAKE.md").is_file())
        self.assertTrue((project / "docs/backlog/PATCHES.md").is_file())
        self.assertIn("references/", (project / ".gitignore").read_text())
        (project / "docs/plans/WORK-REGISTER.md").write_text("mine")
        second = devloop.scaffold(project, devloop.DEFAULT_LAYOUT, ROOT / "templates")
        self.assertEqual((project / "docs/plans/WORK-REGISTER.md").read_text(), "mine")
        self.assertFalse([a for a in second["actions"] if "write" in a or "mkdir" in a or "gitignore_add" in a])
        self.assertTrue(first["actions"])

    def test_stage_tools_layer_and_validate(self):
        self.write(self.home / ".config/dev-loop/config.json", {"stage_tools": {"design": {"name": "superpowers:brainstorming", "kind": "skill"}}})
        self.write(self.project / ".dev-loop/config.json", {"stage_tools": {"design": {"name": "openspec", "kind": "cli"}, "slice": {"name": "x"}}})
        tools = self.resolve()["stage_tools"]
        self.assertEqual(tools["design"]["name"], "openspec")
        self.assertIn("slice", tools)
        bad = self.write(self.root / "bad2.json", {"stage_tools": {"nonsense": {"name": "x"}}})
        with self.assertRaises(devloop.ConfigError):
            devloop.load(bad)

    def test_discover_categorizes_by_name_and_is_read_only(self):
        for name in ("openspec-propose", "brainstorming", "unrelated-thing", "code-review"):
            d = self.root / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
        before = set(self.root.rglob("*"))
        result = devloop.discover(self.project, roots=[self.root / "skills"], home=self.home, env={"PATH": ""})
        names = {s["name"]: s["categories"] for s in result["skills"]}
        self.assertIn("spec", names["openspec-propose"])
        self.assertIn("review", names["code-review"])
        self.assertNotIn("unrelated-thing", names)
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_scaffold_dry_run_writes_nothing(self):
        project = self.root / "dry"
        project.mkdir()
        devloop.scaffold(project, devloop.DEFAULT_LAYOUT, ROOT / "templates", dry_run=True)
        self.assertEqual(list(project.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
