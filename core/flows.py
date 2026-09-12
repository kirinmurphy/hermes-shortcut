"""The flows — each one is a macro over native `hermes` CLI commands.

A flow reads as its sequence of hermes commands, with the bookkeeping
(manifest + PROJECTS.md updates, the check-sync gate) called out between
them. Subprocess mechanics live in runner.py; file bookkeeping in
records.py. Nothing in this file runs anything other than the native CLI
and those two helpers.

All flows print their plan first and are idempotent (re-run = no-op).
"""
from __future__ import annotations

from pathlib import Path

from . import runner
from . import records
from .runner import hermes, hermes_profile, print_plan


# ---------------------------------------------------------------------------
# Flow: move-project
# ---------------------------------------------------------------------------

def move_project(slug: str, to_profile: str, *, dry_run: bool = False) -> int:
    """Move a project between profiles.

    The hermes workflow:
      1. register the project on the target profile
      2. archive + remove-folder on the source profile
    The bookkeeping:
      3. manifest row: profile: <to>
      4. PROJECTS.md row: topic column → <to>
      5. check-sync gate stays green
    """
    entry = records.find_project(slug)
    if entry is None:
        print(f"❌ Project '{slug}' not found in the ecosystem manifest.")
        print(f"   Checked: {records.ECOSYSTEM_MANIFEST}")
        return 1

    name = entry.get("name", slug)
    current_profile = entry.get("profile")
    project_path = records.resolve_path(entry)

    if current_profile == to_profile:
        print(f"✅ Project '{slug}' is already on profile '{to_profile}' — nothing to do.")
        return 0

    print_plan(f"Move project '{slug}' → profile '{to_profile}'", [
        f"Register '{name}' on profile '{to_profile}'",
        f"Detach from profile '{current_profile or 'default'}'",
        "Update manifest + PROJECTS.md",
        "Run the check-sync gate",
    ])
    if dry_run:
        print("Dry run — no changes made.")
        return 0

    # 1. Register on the target profile. If the slug already exists there,
    #    add-folder + set-primary instead of create (create would fail).
    r = hermes_profile(to_profile, "project", "show", slug, check=False, capture=True)
    if r.returncode == 0:
        print(f"  ℹ️  '{slug}' already registered on '{to_profile}' — adding folder.")
        hermes_profile(to_profile, "project", "add-folder", slug, str(project_path))
        hermes_profile(to_profile, "project", "set-primary", slug, str(project_path))
    else:
        hermes_profile(to_profile, "project", "create", name,
                       "--slug", slug, "--primary", str(project_path))

    # 2. Detach from the source profile (archive is idempotent).
    if current_profile:
        hermes_profile(current_profile, "project", "archive", slug, check=False, capture=True)
        hermes_profile(current_profile, "project", "remove-folder", slug,
                       str(project_path), check=False)

    # 3+4. Bookkeeping: the records must match where the project now lives.
    records.set_profile(slug, to_profile)
    records.update_projects_md(slug, to_profile)

    # 5. Gate.
    sync_rc = runner.check_sync_strict()

    print()
    print("  ⚠️  Desktop app needs a quit+relaunch to pick up the move.")
    print("     Old chats don't migrate.")

    if sync_rc != 0:
        print("  ⚠️  check-sync --strict found DRIFT items — review above.")
        return 1
    print(f"✅ '{slug}' moved to profile '{to_profile}'.")
    return 0


# ---------------------------------------------------------------------------
# Flow: create-project
# ---------------------------------------------------------------------------

def create_project(name: str, profile: str, path: str | None = None, *, dry_run: bool = False) -> int:
    """Create a new project: folder (optional), register on a profile,
    add manifest + PROJECTS.md rows, run the gate."""
    slug = name.lower().replace(" ", "-").replace("_", "-")
    project_path = Path(path).expanduser() if path else None

    print_plan(f"Create project '{name}' on profile '{profile}'", [
        f"Create folder {project_path}" if project_path else "(no folder — no --path given)",
        f"Register '{name}' on profile '{profile}'",
        "Add manifest + PROJECTS.md rows",
        "Run the check-sync gate",
    ])
    if dry_run:
        print("Dry run — no changes made.")
        return 0

    if project_path:
        project_path.mkdir(parents=True, exist_ok=True)

    create_args = ["-p", profile, "project", "create", name, "--slug", slug]
    if project_path:
        create_args += ["--primary", str(project_path)]
    hermes(*create_args)

    records.add_project(slug, name, str(project_path) if project_path else None, profile)
    records.add_to_projects_md(name, str(project_path) if project_path else "(no folder)", profile)

    runner.check_sync_strict()

    print(f"\n✅ Project '{name}' created on profile '{profile}'.")
    print("  ⚠️  Desktop app needs a quit+relaunch to see it.")
    return 0


# ---------------------------------------------------------------------------
# Flow: create-profile
# ---------------------------------------------------------------------------

def create_profile(name: str, *, dry_run: bool = False) -> int:
    """Create a profile: create + alias, scope repo scan roots (default []),
    and print how to set its model. Model choice is interactive — offered,
    not guessed."""
    print_plan(f"Create profile '{name}'", [
        f"hermes profile create {name}",
        f"hermes profile alias {name}",
        "Set desktop.repo_scan_roots on the new profile (default: [])",
        "Offer model set",
    ])
    if dry_run:
        print("Dry run — no changes made.")
        return 0

    hermes("profile", "create", name)
    hermes("profile", "alias", name)
    hermes("-p", name, "config", "set", "desktop.repo_scan_roots", "[]", check=False)

    print(f"\n  💡 Set its model with: hermes -p {name} config set model.default <model>")
    print(f"     Or interactively: hermes -p {name} model")
    print(f"\n✅ Profile '{name}' created.")
    return 0
