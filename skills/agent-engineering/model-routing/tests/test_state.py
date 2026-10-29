"""Behavioral checks for storage identity, policy visibility, and safe bootstrap."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("routing_state", Path(__file__).resolve().parents[1] / "scripts" / "state.py")
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "project" / "nested"
        self.project.mkdir(parents=True)
        self.skill = self.root / "skill"

    def tearDown(self):
        self.temp.cleanup()

    def config(self, path, label, policy=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "storage": {"backend": "local",
            "ledger": {"uri": label + "/ledger.jsonl"}, "rules": {"uri": label + "/rules.jsonl"}},
            "policy": policy or {}}))
        return path

    def resolve(self, explicit=None, env=None):
        return state.resolve(self.project, explicit=explicit, env=env or {}, home=self.home, skill_dir=self.skill)

    def test_unconfigured_lookup_is_read_only(self):
        before = set(self.root.rglob("*"))
        self.assertFalse(self.resolve()["configured"])
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_project_storage_does_not_hide_user_ban(self):
        self.config(self.home / ".config/model-routing/config.json", "global", {"denied_models": ["expensive"]})
        project = self.config(self.project.parent / ".model-routing/config.json", "project")
        result = self.resolve()
        self.assertEqual(result["config"], str(project.resolve()))
        self.assertEqual(result["storage"]["ledger"]["uri"], "project/ledger.jsonl")
        self.assertEqual(result["policy_layers"][0]["policy"]["denied_models"], ["expensive"])

    def test_explicit_missing_never_falls_back(self):
        self.config(self.skill / ".local/config.json", "fallback")
        with self.assertRaises(state.StateError):
            self.resolve(explicit=self.root / "missing.json")

    def test_explicit_overrides_environment_and_project(self):
        self.config(self.project / ".model-routing/config.json", "project")
        explicit = self.config(self.root / "selected.json", "selected")
        result = self.resolve(explicit=explicit, env={"MODEL_ROUTING_CONFIG": str(self.root / "missing.json")})
        self.assertEqual(result["storage"]["ledger"]["uri"], "selected/ledger.jsonl")

    def test_ignored_skill_state_is_a_fallback(self):
        path = self.config(self.skill / ".local/config.json", "skill")
        self.assertEqual(self.resolve()["config"], str(path.resolve()))

    def test_relative_policy_file_is_loaded_and_missing_is_error(self):
        path = self.config(self.skill / ".local/config.json", "skill")
        value = json.loads(path.read_text())
        value["policy_files"] = ["rules.md"]
        path.write_text(json.dumps(value))
        with self.assertRaises(state.StateError):
            self.resolve()
        (path.parent / "rules.md").write_text("Do not try banned models.")
        self.assertEqual(self.resolve()["policy_layers"][0]["policy_files"][0]["text"], "Do not try banned models.")

    def test_malformed_lower_policy_is_not_silently_ignored(self):
        self.config(self.project / ".model-routing/config.json", "project")
        path = self.home / ".config/model-routing/config.json"
        path.parent.mkdir(parents=True)
        path.write_text("invalid")
        with self.assertRaises(state.StateError):
            self.resolve()

    def test_init_preserves_existing_identity(self):
        path = self.root / "state.json"
        state.initialize(path, "custom", "one", "two")
        with self.assertRaises(state.StateError):
            state.initialize(path, "custom", "wrong", "wrong")
        self.assertEqual(state.load(path)["storage"]["ledger"]["uri"], "one")

    def test_invalid_init_does_not_create_file_or_parent(self):
        path = self.root / "new-folder" / "state.json"
        for args in (("", "one", "two"), ("local", " ", "two"), ("local", "one", "")):
            with self.assertRaises(state.StateError):
                state.initialize(path, *args)
        self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
