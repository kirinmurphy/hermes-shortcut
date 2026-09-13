"""Tests for the plugin after the single-source collapse.

projects.db is the only registry; the flows are pure CLI macros.
Admin-spec files (manifest.yaml, PROJECTS.md) no longer exist.

Pure unittest — no pytest dependency. All hermes subprocess calls are
mocked; the db lookups run against tiny temp SQLite files.
"""
from __future__ import annotations

import argparse
import io
import shutil
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from tests.helpers import FakePluginContext, load_plugin


def _load():
    mod = load_plugin(PLUGIN_DIR)
    core = mod.core
    return mod, core.flows, core.db, core.info, core.runner


def _make_projects_db(home: Path, rows: list[tuple[str, str, str]]) -> None:
    """rows: (slug, name, primary_path)."""
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "projects.db")
    conn.execute("CREATE TABLE IF NOT EXISTS projects ("
                 "id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, "
                 "name TEXT NOT NULL, primary_path TEXT, "
                 "archived INTEGER NOT NULL DEFAULT 0)")
    for i, (slug, name, path) in enumerate(rows):
        conn.execute("INSERT INTO projects (id, slug, name, primary_path, archived) "
                     "VALUES (?, ?, ?, ?, 0)", (f"p_{i}", slug, name, path or None))
    conn.commit()
    conn.close()
    # Named profiles need a config.yaml for db.py to count them.
    if home.name != ".hermes":
        (home / "config.yaml").write_text("")


class _PluginCase(unittest.TestCase):
    """Base: fake home tree + mocked subprocess layer."""

    @classmethod
    def setUpClass(cls):
        cls.mod, cls.flows, cls.db, cls.info, cls.runner = _load()

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="shortcut-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.tmpdir = Path(tmp)
        self.fake_home = self.tmpdir / ".hermes"
        self.profiles_root = self.fake_home / "profiles"
        # db.py derives homes from Path.home()/".hermes".
        p = unittest.mock.patch.object(Path, "home", lambda: self.tmpdir)
        p.start()
        self.addCleanup(p.stop)

    def _mock_subprocess(self, registered: dict[str, set[str]] | None = None):
        """Patch flows.hermes_profile. registered: profile → slugs that
        exist there (drives `project show` exit codes). Returns calls list."""
        registered = registered or {}
        calls: list[list[str]] = []

        def fake_hermes_profile(profile, *args, check=True, capture=False):
            calls.append(["-p", profile, *args])
            result = unittest.mock.Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            if args[:2] == ("project", "show"):
                slug = args[2] if len(args) > 2 else ""
                result.returncode = 0 if slug in registered.get(profile, ()) else 1
            return result

        p = unittest.mock.patch.object(self.flows, "hermes_profile",
                                       side_effect=fake_hermes_profile)
        p.start()
        self.addCleanup(p.stop)
        return calls

    def _run(self, fn, *args, registered=None, **kwargs):
        calls = self._mock_subprocess(registered)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = fn(*args, **kwargs)
        return rc, buf.getvalue(), calls


class TestDb(_PluginCase):
    """db.py — the cross-profile read layer."""

    def test_all_projects_across_profiles(self):
        _make_projects_db(self.fake_home, [("travel", "Travel", "/p/travel"),
                                           ("horizon", "Horizon", "/p/horizon")])
        _make_projects_db(self.profiles_root / "careering",
                          [("job-hunt", "Job hunt", "/p/job-hunt")])
        rows = self.db.all_projects()
        profiles = {r["profile"] for r in rows}
        self.assertEqual(profiles, {"default", "careering"})
        self.assertEqual(len(rows), 3)

    def test_archived_excluded(self):
        home = self.fake_home
        home.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(home / "projects.db")
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, slug TEXT, "
                     "name TEXT, primary_path TEXT, archived INTEGER DEFAULT 0)")
        conn.execute("INSERT INTO projects VALUES ('p0', 'gone', 'Gone', '', 1)")
        conn.execute("INSERT INTO projects VALUES ('p1', 'here', 'Here', '/p/here', 0)")
        conn.commit()
        conn.close()
        rows = self.db.all_projects()
        self.assertEqual([r["slug"] for r in rows], ["here"])

    def test_find_slug_multiple_profiles(self):
        _make_projects_db(self.fake_home, [("shared", "Shared", "/p/shared")])
        _make_projects_db(self.profiles_root / "x", [("shared", "Shared", "/p/shared")])
        (self.profiles_root / "x" / "config.yaml").write_text("")
        hits = self.db.find_slug("shared")
        self.assertEqual(len(hits), 2)

    def test_no_dbs_no_crash(self):
        self.assertEqual(self.db.all_projects(), [])


class TestMoveProject(_PluginCase):

    def _seed_default(self, slug="travel", path="/p/travel"):
        _make_projects_db(self.fake_home, [(slug, "Travel", path)])

    def test_move_registers_and_detaches(self):
        self._seed_default()
        rc, out, calls = self._run(self.flows.move_project, "travel", "careering")
        self.assertEqual(rc, 0)
        self.assertIn(["-p", "careering", "project", "create", "Travel",
                       "--slug", "travel", "--primary", "/p/travel"], calls)
        self.assertIn(["-p", "default", "project", "archive", "travel"], calls)
        self.assertIn(["-p", "default", "project", "remove-folder", "travel",
                       "/p/travel"], calls)
        # No record-sync / gate steps anymore.
        self.assertNotIn("check-sync", str(calls))

    def test_already_on_target_noop(self):
        self._seed_default()
        rc, out, _ = self._run(self.flows.move_project, "travel", "default")
        self.assertEqual(rc, 0)
        self.assertIn("already on profile", out)

    def test_unknown_slug_fails(self):
        rc, out, _ = self._run(self.flows.move_project, "ghost", "careering")
        self.assertEqual(rc, 1)
        self.assertIn("not registered", out)

    def test_multi_profile_slug_requires_disambiguation(self):
        self._seed_default()
        _make_projects_db(self.profiles_root / "x", [("travel", "Travel", "/p/travel")])
        (self.profiles_root / "x" / "config.yaml").write_text("")
        rc, out, _ = self._run(self.flows.move_project, "travel", "careering")
        self.assertEqual(rc, 1)
        self.assertIn("several profiles", out)

    def test_dry_run(self):
        self._seed_default()
        rc, out, calls = self._run(self.flows.move_project, "travel", "careering",
                                   dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("Dry run", out)
        self.assertEqual([c for c in calls if "project" in c], [])


class TestCreateProject(_PluginCase):
    """Projects and profiles are created with native commands / the desktop —
    no flows here (negative contracts live in TestRegistration)."""


class TestAttachProject(_PluginCase):

    def test_attach_from_other_profile(self):
        _make_projects_db(self.profiles_root / "careering",
                          [("job-hunt", "Job hunt", "/p/job-hunt")])
        rc, out, calls = self._run(self.flows.attach_project, "job-hunt", "vacation")
        self.assertEqual(rc, 0)
        self.assertIn(["-p", "vacation", "project", "create", "Job hunt",
                       "--slug", "job-hunt", "--primary", "/p/job-hunt"], calls)

    def test_attach_already_registered_uses_add_folder(self):
        _make_projects_db(self.fake_home, [("travel", "Travel", "/p/travel")])
        rc, out, calls = self._run(self.flows.attach_project, "travel", "vacation",
                                   registered={"vacation": {"travel"}})
        self.assertEqual(rc, 0)
        self.assertIn("already registered", out)
        self.assertIn(["-p", "vacation", "project", "add-folder", "travel",
                       "/p/travel"], calls)
        self.assertNotIn(["-p", "vacation", "project", "create", "Travel",
                          "--slug", "travel", "--primary", "/p/travel"], calls)

    def test_detach_is_native_not_a_flow(self):
        """Removing a project = native `hermes project archive` (negative contract)."""
        self.assertFalse(hasattr(self.flows, "detach_project"))


class TestInventory(_PluginCase):

    def test_lists_all_profiles(self):
        _make_projects_db(self.fake_home, [("travel", "Travel", "/p/travel")])
        _make_projects_db(self.profiles_root / "careering",
                          [("job-hunt", "Job hunt", "/p/job-hunt")])
        (self.profiles_root / "careering" / "config.yaml").write_text("")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.info.inventory()
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("Travel", out)
        self.assertIn("Job hunt", out)
        self.assertIn("[careering]", out)
        self.assertIn("no separate spec", out)


class TestExplain(_PluginCase):

    def _explain(self, name):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.info.explain(name)
        return rc, buf.getvalue()

    def test_all_documented(self):
        for name in ["move-project", "attach-project", "status", "inventory"]:
            rc, _ = self._explain(name)
            self.assertEqual(rc, 0, f"explain('{name}') failed")

    def test_native_operations_are_not_flows(self):
        """create-project / create-profile / detach-project are native
        operations — the names stay free (negative contract)."""
        for name in ("create-project", "create-profile", "detach-project"):
            rc, out = self._explain(name)
            self.assertEqual(rc, 1, name)
            self.assertIn("Unknown flow", out)

    def test_unknown(self):
        rc, out = self._explain("nope")
        self.assertEqual(rc, 1)
        self.assertIn("Unknown flow", out)


class TestRegistration(unittest.TestCase):
    """register(ctx) wires the CLI command + skill."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_plugin(PLUGIN_DIR)
        cls.ctx = FakePluginContext(PLUGIN_DIR)
        cls.mod.register(cls.ctx)

    def _make_parser(self):
        parser = argparse.ArgumentParser(prog="hermes shortcut")
        self.ctx.cli_commands["shortcut"]["setup_fn"](parser)
        return parser

    def test_cli_registered(self):
        self.assertIn("shortcut", self.ctx.cli_commands)
        self.assertEqual(len(self.ctx.skills), 1)

    def test_every_command_maps_to_func(self):
        parser = self._make_parser()
        argvs = {
            "move-project": ["s", "p"], "attach-project": ["s", "p"],
            "status": [], "inventory": [],
            "explain": ["status"],
        }
        for sub, argv in argvs.items():
            args = parser.parse_args([sub, *argv])
            self.assertTrue(callable(getattr(args, "func", None)), sub)

    def test_native_only_operations_are_not_subcommands(self):
        """create-project / create-profile / detach-project are native CLI /
        desktop operations — no shortcut subcommands (negative contract)."""
        parser = self._make_parser()
        for sub in ("create-project", "create-profile", "detach-project"):
            with self.assertRaises(SystemExit, msg=sub):
                parser.parse_args([sub, "n", "p"])


if __name__ == "__main__":
    unittest.main()
