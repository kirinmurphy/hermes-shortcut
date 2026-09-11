"""Tests for flow logic — explain, move-project no-op, and manifest helpers.

Pure unittest — no pytest dependency. These tests do NOT run real hermes
subprocesses (except status which runs real check-sync + doctor); they test
the pure-Python logic paths and the real ecosystem manifest.
"""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

# Put the plugin dir on sys.path so we can import _config directly.
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from tests.helpers import load_plugin


def _load_flows():
    """Load the flows module via the plugin namespace."""
    load_plugin(PLUGIN_DIR)
    # The __init__.py already imports flows as `from . import flows`,
    # so it's available as an attribute of the package module.
    mod = sys.modules["hermes_plugins.shortcut"]
    return mod.flows


class TestExplain(unittest.TestCase):
    """explain() is pure output — no side effects, no subprocesses."""

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()

    def _explain(self, name):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.flows.explain(name)
        return rc, buf.getvalue()

    def test_explain_known_flow(self):
        rc, out = self._explain("move-project")
        self.assertEqual(rc, 0)
        self.assertIn("move-project", out)
        self.assertIn("Summary:", out)
        self.assertIn("Commands it runs:", out)
        self.assertIn("What it touches:", out)

    def test_explain_status(self):
        rc, out = self._explain("status")
        self.assertEqual(rc, 0)
        self.assertIn("check-sync", out)
        self.assertIn("hermes doctor", out)

    def test_explain_unknown_flow(self):
        rc, out = self._explain("nonexistent")
        self.assertEqual(rc, 1)
        self.assertIn("Unknown flow", out)
        self.assertIn("Available flows:", out)

    def test_explain_all_flows(self):
        """Every documented flow should be explainable."""
        for name in ["move-project", "status", "project-new", "profile-new"]:
            rc, _ = self._explain(name)
            self.assertEqual(rc, 0, f"explain('{name}') returned {rc}")


class TestMoveProjectNoOp(unittest.TestCase):
    """move-project should no-op when the project is already on the target profile."""

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()

    def test_already_on_target_profile(self):
        """job-hunt is on 'careering' in the manifest — moving it to 'careering' should no-op."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.flows.move_project("job-hunt", "careering", dry_run=False)
        self.assertEqual(rc, 0)
        self.assertIn("already on profile", buf.getvalue())

    def test_dry_run_does_not_execute(self):
        """dry_run should print the plan but not execute."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.flows.move_project("job-hunt", "default", dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("Dry run", buf.getvalue())

    def test_unknown_slug(self):
        """An unknown slug should return 1 with an error message."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.flows.move_project("nonexistent-slug", "careering", dry_run=False)
        self.assertEqual(rc, 1)
        self.assertIn("not found", buf.getvalue())


class TestManifestHelpers(unittest.TestCase):
    """Test the manifest path resolution helpers against the real manifest."""

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()

    def test_find_project_in_manifest(self):
        manifest = self.flows._load_manifest()
        entry = self.flows._find_project_in_manifest(manifest, "job-hunt")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["slug"], "job-hunt")
        self.assertEqual(entry["profile"], "careering")

    def test_find_project_not_in_manifest(self):
        manifest = self.flows._load_manifest()
        entry = self.flows._find_project_in_manifest(manifest, "nonexistent")
        self.assertIsNone(entry)

    def test_manifest_has_profiles_section(self):
        manifest = self.flows._load_manifest()
        self.assertIn("profiles", manifest)
        self.assertIn("careering", manifest["profiles"])


class TestStatusFlow(unittest.TestCase):
    """status() runs real subprocesses — test it returns 0 or 1."""

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()

    def test_status_returns_int(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.flows.status()
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
