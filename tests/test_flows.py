"""Tests for flow logic — explain, move-project no-op, and manifest helpers.

Pure unittest — no pytest dependency. All admin-file paths (ecosystem
manifest, PROJECTS.md) are redirected to hermetic fixtures so the suite
runs on any machine (including CI) with zero real-ecosystem dependencies.
Subprocess-touching paths (check-sync, hermes doctor) are only exercised
by tests that tolerate either exit code.
"""
from __future__ import annotations

import io
import sys
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

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


class _FixtureTestCase(unittest.TestCase):
    """Base: point the flows module's admin-file paths at the fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()
        # The fixture manifest's home is ~/projects/hermes; resolve fixture
        # project paths against a temp-free canonical base so assertions are
        # deterministic. We swap the module-level path constants — flows.py
        # reads them at call time.
        cls._orig_manifest = cls.flows.ECOSYSTEM_MANIFEST
        cls._orig_projects_md = cls.flows.PROJECTS_MD
        cls.flows.ECOSYSTEM_MANIFEST = FIXTURES / "manifest.yaml"
        cls.flows.PROJECTS_MD = FIXTURES / "PROJECTS.md"

    @classmethod
    def tearDownClass(cls):
        cls.flows.ECOSYSTEM_MANIFEST = cls._orig_manifest
        cls.flows.PROJECTS_MD = cls._orig_projects_md


class TestExplain(_FixtureTestCase):
    """explain() is pure output — no side effects, no subprocesses."""

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


class TestMoveProjectNoOp(_FixtureTestCase):
    """move-project should no-op when the project is already on the target profile."""

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


class TestManifestHelpers(_FixtureTestCase):
    """Test the manifest path resolution helpers against the fixture manifest."""

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
    """status() shells out to check-sync + hermes doctor. For hermetic tests,
    mock the subprocess layer and verify the summary logic on both outcomes.
    """

    @classmethod
    def setUpClass(cls):
        cls.flows = _load_flows()

    def _run_status(self, sync_rc, sync_out, doctor_rc, doctor_out):
        """Run status() with both subprocess calls faked; return (rc, output)."""
        def fake_run(cmd, *, check=True, capture=False):
            result = unittest.mock.Mock()
            result.returncode = sync_rc
            result.stdout = sync_out
            result.stderr = ""
            return result

        def fake_hermes(*args, check=True, capture=False):
            result = unittest.mock.Mock()
            result.returncode = doctor_rc
            result.stdout = doctor_out
            result.stderr = ""
            return result

        with unittest.mock.patch.object(self.flows, "run", side_effect=fake_run), \
             unittest.mock.patch.object(self.flows, "hermes", side_effect=fake_hermes), \
             unittest.mock.patch.object(self.flows, "CHECK_SYNC", FIXTURES / "manifest.yaml"), \
             unittest.mock.patch.object(self.flows, "VENV_PYTHON", FIXTURES / "manifest.yaml"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.flows.status()
        return rc, buf.getvalue()

    def test_status_all_green(self):
        rc, out = self._run_status(0, "", 0, "")
        self.assertEqual(rc, 0)
        self.assertIn("All green", out)
        self.assertIn("all surfaces in sync", out)

    def test_status_sync_drift(self):
        rc, out = self._run_status(1, "DRIFT items found", 0, "")
        self.assertEqual(rc, 1)
        self.assertIn("drift found", out)

    def test_status_doctor_failure(self):
        rc, out = self._run_status(0, "", 1, "some check failed")
        self.assertEqual(rc, 1)
        self.assertIn("Doctor: issues found", out)


if __name__ == "__main__":
    unittest.main()
