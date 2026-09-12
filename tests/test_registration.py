"""Tests for plugin registration — verifies register(ctx) wires up the CLI
command and bundled skill exactly as the real loader expects.

Pure unittest — no pytest dependency.
"""
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

# Put the plugin dir on sys.path so we can import _config directly.
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from tests.helpers import FakePluginContext, load_plugin


def _load():
    mod = load_plugin(PLUGIN_DIR)
    ctx = FakePluginContext(PLUGIN_DIR)
    mod.register(ctx)
    return mod, ctx


class TestRegistration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod, cls.ctx = _load()

    def test_cli_command_registered(self):
        self.assertIn("shortcut", self.ctx.cli_commands)
        entry = self.ctx.cli_commands["shortcut"]
        self.assertIsNotNone(entry["setup_fn"])
        self.assertIsNotNone(entry["handler_fn"])
        self.assertIn("Shortcut", entry["help"])

    def test_skill_registered(self):
        self.assertEqual(len(self.ctx.skills), 1)
        name, skill_dir = self.ctx.skills[0]
        self.assertEqual(name, "shortcut")
        self.assertTrue(skill_dir.exists(), f"skill_dir should exist: {skill_dir}")

    def test_plugin_yaml_name_matches_config(self):
        import yaml
        with open(PLUGIN_DIR / "plugin.yaml") as f:
            ydata = yaml.safe_load(f)
        from _config import NAME
        self.assertEqual(ydata["name"], NAME)

    def test_provides_cli_commands_in_plugin_yaml(self):
        import yaml
        with open(PLUGIN_DIR / "plugin.yaml") as f:
            ydata = yaml.safe_load(f)
        self.assertIn("shortcut", ydata.get("provides_cli_commands", []))

    def test_no_tools_registered(self):
        """shortcut is a CLI-only plugin — it should NOT register any agent tools."""
        self.assertFalse(hasattr(self.mod, "TOOLS"),
                        "shortcut should not have a TOOLS list — it's CLI-only")


class TestParserSetup(unittest.TestCase):
    """Verify the argparse tree maps every command to the right function."""

    @classmethod
    def setUpClass(cls):
        cls.mod, cls.ctx = _load()

    def _make_parser(self):
        parser = argparse.ArgumentParser(prog="hermes shortcut")
        self.ctx.cli_commands["shortcut"]["setup_fn"](parser)
        return parser

    def test_move_project_args(self):
        args = self._make_parser().parse_args(["move-project", "job-hunt", "careering"])
        self.assertEqual(args.slug, "job-hunt")
        self.assertEqual(args.to_profile, "careering")
        self.assertFalse(args.dry_run)

    def test_move_project_dry_run(self):
        args = self._make_parser().parse_args(["move-project", "job-hunt", "careering", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_create_project_args(self):
        args = self._make_parser().parse_args(["create-project", "My Project", "default", "--path", "/tmp/test"])
        self.assertEqual(args.name, "My Project")
        self.assertEqual(args.profile, "default")
        self.assertEqual(args.path, "/tmp/test")

    def test_create_profile_args(self):
        args = self._make_parser().parse_args(["create-profile", "myprofile"])
        self.assertTrue(hasattr(args, "func"))

    def test_explain_args(self):
        args = self._make_parser().parse_args(["explain", "move-project"])
        self.assertEqual(args.name, "move-project")

    def test_status_no_args(self):
        args = self._make_parser().parse_args(["status"])
        self.assertTrue(hasattr(args, "func"))

    def test_every_command_has_a_func(self):
        """Each subcommand must map to a callable — or dispatch fails."""
        parser = self._make_parser()
        for sub in ["move-project", "create-project", "create-profile", "status", "explain"]:
            argv = {"move-project": ["x", "y"], "create-project": ["n", "p"],
                    "create-profile": ["n"], "status": [], "explain": ["status"]}[sub]
            args = parser.parse_args([sub, *argv])
            self.assertTrue(callable(getattr(args, "func", None)),
                            f"{sub} did not map to a callable func")


if __name__ == "__main__":
    unittest.main()
