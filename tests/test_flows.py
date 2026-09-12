"""Tests for flow logic — explain, move-project no-op, and record helpers.

Pure unittest — no pytest dependency. All admin-file paths (ecosystem
manifest, PROJECTS.md) are redirected to hermetic fixtures so the suite
runs on any machine (including CI) with zero real-ecosystem dependencies.
Subprocess-touching paths (check-sync, hermes doctor) are mocked.
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


def _load():
    """Load the plugin; return (plugin_module, flows, records, info)."""
    mod = load_plugin(PLUGIN_DIR)
    core = mod.core  # execution code lives in core/ (see __init__.py docstring)
    return mod, core.flows, core.records, core.info


class _FixtureTestCase(unittest.TestCase):
    """Base: point the records module's admin-file paths at the fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.plugin, cls.flows, cls.records, cls.info = _load()
        cls._orig_manifest = cls.records.ECOSYSTEM_MANIFEST
        cls._orig_projects_md = cls.records.PROJECTS_MD
        cls.records.ECOSYSTEM_MANIFEST = FIXTURES / "manifest.yaml"
        cls.records.PROJECTS_MD = FIXTURES / "PROJECTS.md"

    @classmethod
    def tearDownClass(cls):
        cls.records.ECOSYSTEM_MANIFEST = cls._orig_manifest
        cls.records.PROJECTS_MD = cls._orig_projects_md


class TestExplain(_FixtureTestCase):
    """explain() is pure output — no side effects, no subprocesses."""

    def _explain(self, name):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.info.explain(name)
        return rc, buf.getvalue()

    def test_explain_known_flow(self):
        rc, out = self._explain("move-project")
        self.assertEqual(rc, 0)
        self.assertIn("move-project", out)
        self.assertIn("Summary:", out)
        self.assertIn("Commands it runs:", out)
        self.assertIn("What it touches:", out)

    def test_explain_labels_kind(self):
        """Flows and utilities are labeled with their kind."""
        _, out_flow = self._explain("move-project")
        self.assertIn("(flow)", out_flow)
        _, out_util = self._explain("status")
        self.assertIn("(utility)", out_util)

    def test_explain_status(self):
        rc, out = self._explain("status")
        self.assertEqual(rc, 0)
        self.assertIn("check-sync", out)
        self.assertIn("hermes doctor", out)

    def test_explain_unknown_flow(self):
        rc, out = self._explain("nonexistent")
        self.assertEqual(rc, 1)
        self.assertIn("Unknown flow", out)
        self.assertIn("Available:", out)

    def test_explain_all(self):
        """Every documented flow/utility should be explainable."""
        for name in ["move-project", "create-project", "create-profile", "status"]:
            rc, _ = self._explain(name)
            self.assertEqual(rc, 0, f"explain('{name}') returned {rc}")


class TestMoveProjectNoOp(_FixtureTestCase):
    """move-project should no-op when the project is already on the target profile."""

    def test_already_on_target_profile(self):
        """job-hunt is on 'careering' in the fixture — moving it there is a no-op."""
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
    """Test the record helpers against the fixture manifest."""

    def test_find_project_in_manifest(self):
        entry = self.records.find_project("job-hunt")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["slug"], "job-hunt")
        self.assertEqual(entry["profile"], "careering")

    def test_find_project_not_in_manifest(self):
        self.assertIsNone(self.records.find_project("nonexistent"))

    def test_manifest_has_profiles_section(self):
        manifest = self.records.load_manifest()
        self.assertIn("profiles", manifest)
        self.assertIn("careering", manifest["profiles"])

    def test_resolve_path_relative_to_home(self):
        entry = self.records.find_project("job-hunt")
        path = self.records.resolve_path(entry)
        self.assertTrue(str(path).endswith("projects/job-hunt"))


class TestStatusFlow(unittest.TestCase):
    """status() shells out to check-sync + hermes doctor. Mock the subprocess
    layer and verify the summary logic on each outcome.
    """

    @classmethod
    def setUpClass(cls):
        cls.plugin, cls.flows, cls.records, cls.info = _load()

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

        with unittest.mock.patch.object(self.info, "hermes", side_effect=fake_hermes), \
             unittest.mock.patch.object(self.info.runner, "run", side_effect=fake_run), \
             unittest.mock.patch.object(self.info.runner, "CHECK_SYNC", FIXTURES / "manifest.yaml"), \
             unittest.mock.patch.object(self.info.runner, "VENV_PYTHON", FIXTURES / "manifest.yaml"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.info.status()
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
