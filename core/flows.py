"""The flows — each one is a macro over native `hermes` CLI commands.

A flow reads as its sequence of hermes commands. Subprocess mechanics live
in runner.py. projects.db is the only project registry — flows don't touch
any spec file, run no record-sync, and no gate. They print their plan first
and are idempotent (re-run = no-op).

A flow exists only where composing beats the single native command:
move-project (two registries) and attach-project (cross-profile slug
lookup). Everything else is native: `hermes project create/archive`,
`hermes profile create`, the desktop sidebar.
"""
from __future__ import annotations

from pathlib import Path

from . import db
from .runner import hermes_profile, print_plan


# ---------------------------------------------------------------------------
# Flow: move-project
# ---------------------------------------------------------------------------

def move_project(slug: str, to_profile: str, *, dry_run: bool = False) -> int:
    """Move a project between profiles.

    The hermes workflow:
      1. register the project on the target profile
      2. archive + remove-folder on the source profile
    """
    hits = db.find_slug(slug)
    if not hits:
        print(f"❌ Project '{slug}' not registered on any profile.")
        print("   (Checked every profile's projects.db.)")
        return 1
    if len(hits) > 1:
        print(f"❌ '{slug}' is registered on several profiles — pick one:")
        for h in hits:
            print(f"     • {h['slug']} on '{h['profile']}' ({h['primary_path']})")
        return 1

    entry = hits[0]
    current_profile = entry["profile"]
    project_path = entry["primary_path"]

    if current_profile == to_profile:
        print(f"✅ Project '{slug}' is already on profile '{to_profile}' — nothing to do.")
        return 0

    print_plan(f"Move project '{slug}' → profile '{to_profile}'", [
        f"Register '{entry['name']}' on profile '{to_profile}'",
        f"Detach from profile '{current_profile}'",
    ])
    if dry_run:
        print("Dry run — no changes made.")
        return 0

    # 1. Register on the target profile. If the slug already exists there,
    #    add-folder + set-primary instead of create (create would fail).
    r = hermes_profile(to_profile, "project", "show", slug, check=False, capture=True)
    if r.returncode == 0:
        print(f"  ℹ️  '{slug}' already registered on '{to_profile}' — adding folder.")
        hermes_profile(to_profile, "project", "add-folder", slug, project_path)
        hermes_profile(to_profile, "project", "set-primary", slug, project_path)
    else:
        hermes_profile(to_profile, "project", "create", entry["name"],
                       "--slug", slug, "--primary", project_path)

    # 2. Detach from the source profile (archive is idempotent).
    hermes_profile(current_profile, "project", "archive", slug, check=False, capture=True)
    hermes_profile(current_profile, "project", "remove-folder", slug,
                   project_path, check=False)

    print()
    print("  ⚠️  Desktop app needs a quit+relaunch to pick up the move.")
    print("     Old chats don't migrate.")
    print(f"✅ '{slug}' moved to profile '{to_profile}'.")
    return 0


# ---------------------------------------------------------------------------
# Flow: attach-project
# ---------------------------------------------------------------------------

def attach_project(slug: str, profile: str, *, dry_run: bool = False) -> int:
    """Attach a project (already registered on some profile) to another
    profile: register it in the target's desktop projects.db. A project may
    be attached to several profiles."""
    hits = db.find_slug(slug)
    if not hits:
        print(f"❌ Project '{slug}' not registered on any profile.")
        return 1
    entry = hits[0]
    name = entry["name"]
    project_path = entry["primary_path"]
    if not project_path:
        print(f"❌ '{slug}' has no primary folder — nothing to attach.")
        return 1

    print_plan(f"Attach project '{slug}' → profile '{profile}'", [
        f"hermes -p {profile} project create '{name}' --slug {slug} --primary {project_path}"
        "  (add-folder + set-primary if the slug already exists there)",
    ])
    if dry_run:
        print("Dry run — no changes made.")
        return 0

    if not Path(project_path).expanduser().exists():
        print(f"  ⚠️  Path does not exist on disk: {project_path}")

    # Register on the target profile. If the slug already exists there,
    # add-folder + set-primary instead of create (create would fail).
    r = hermes_profile(profile, "project", "show", slug, check=False, capture=True)
    if r.returncode == 0:
        print(f"  ℹ️  '{slug}' already registered on '{profile}' — adding folder.")
        hermes_profile(profile, "project", "add-folder", slug, project_path)
        hermes_profile(profile, "project", "set-primary", slug, project_path)
    else:
        hermes_profile(profile, "project", "create", name,
                       "--slug", slug, "--primary", project_path)

    print(f"✅ '{slug}' attached to profile '{profile}'.")
    return 0

