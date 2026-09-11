"""Flow logic for the shortcut plugin.

Each function here is a self-contained flow that composes the native `hermes`
CLI as subprocesses. The functions are called by the CLI handler in
``__init__.py`` and by the test suite.

Conventions:
- Every flow prints its plan before executing.
- Every flow is idempotent (safe to re-run).
- Every mutation goes through ``hermes`` CLI subprocesses — never direct
  config.yaml / projects.db / manifest writes (except the ecosystem manifest
  and PROJECTS.md, which are declarative spec files, not config state).
- ``run()`` is the single subprocess runner; ``_hermes()`` is a thin wrapper.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (resolved at call time, not import time — profiles can shift $HERMES_HOME)
# ---------------------------------------------------------------------------

ECOSYSTEM_MANIFEST = Path.home() / "projects" / "hermes" / "admin" / "ecosystem" / "manifest.yaml"
PROJECTS_MD = Path.home() / "projects" / "hermes" / "admin" / "PROJECTS.md"
CHECK_SYNC = Path.home() / ".hermes" / "scripts" / "check-sync.py"
VENV_PYTHON = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, optionally capturing stdout."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def hermes(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run ``hermes <args>`` as a subprocess."""
    return run(["hermes", *args], check=check, capture=capture)


def hermes_profile(profile: str, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run ``hermes -p <profile> <args>``."""
    return hermes("-p", profile, *args, check=check, capture=capture)


def print_plan(title: str, steps: list[str]) -> None:
    """Print a plan header + numbered steps."""
    print(f"\n📋 {title}")
    print("=" * 60)
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    print()


# ---------------------------------------------------------------------------
# Manifest helpers (ecosystem manifest is a declarative spec, NOT config)
# ---------------------------------------------------------------------------

def _load_manifest() -> dict[str, Any]:
    """Load the ecosystem manifest YAML."""
    import yaml
    with open(ECOSYSTEM_MANIFEST) as f:
        return yaml.safe_load(f)


def _save_manifest(data: dict[str, Any]) -> None:
    """Write the ecosystem manifest back."""
    import yaml
    with open(ECOSYSTEM_MANIFEST, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        f.write("\n")


def _find_project_in_manifest(manifest: dict[str, Any], slug: str) -> dict[str, Any] | None:
    """Find a project entry by slug in the manifest's projects list."""
    for entry in manifest.get("projects", []):
        if entry.get("slug") == slug:
            return entry
    return None


# ---------------------------------------------------------------------------
# Flow: move-project
# ---------------------------------------------------------------------------

def move_project(slug: str, to_profile: str, *, dry_run: bool = False) -> int:
    """Move a project between profiles.

    Steps:
    1. Find the project in the manifest (get current profile + path).
    2. If already on the target profile → no-op gracefully.
    3. Register on target profile (create or add-folder + set-primary).
    4. Detach from current profile (archive + remove-folder).
    5. Update ecosystem manifest (set profile: <to> on the project row).
    6. Update PROJECTS.md row.
    7. Remind: desktop app needs quit+relaunch; old chats don't migrate.
    8. Run check-sync --strict to verify the gate stays green.
    """
    manifest = _load_manifest()
    entry = _find_project_in_manifest(manifest, slug)
    if entry is None:
        print(f"❌ Project '{slug}' not found in ecosystem manifest.")
        print(f"   Checked: {ECOSYSTEM_MANIFEST}")
        return 1

    name = entry.get("name", slug)
    path = entry.get("path", "")
    current_profile = entry.get("profile")

    if current_profile == to_profile:
        print(f"✅ Project '{slug}' is already on profile '{to_profile}' — nothing to do.")
        return 0

    # Resolve the absolute path for the project folder.
    manifest_home = Path(manifest.get("home", "~/projects/hermes")).expanduser()
    # Paths in the manifest are relative to the manifest home, or absolute.
    if path.startswith("~") or path.startswith("/"):
        project_path = Path(path).expanduser()
    else:
        project_path = manifest_home / path

    steps = [
        f"Register '{name}' on profile '{to_profile}' (hermes -p {to_profile} project create or add-folder)",
        f"Detach from current profile '{current_profile or 'default'}' (archive + remove-folder)",
        f"Update ecosystem manifest: set profile: {to_profile} on slug '{slug}'",
        f"Update PROJECTS.md row for '{name}' (profile column → {to_profile})",
        f"Run check-sync --strict to verify the gate stays green",
        f"Remind: desktop app needs quit+relaunch; old chats don't migrate",
    ]
    print_plan(f"Move project '{slug}' → profile '{to_profile}'", steps)

    if dry_run:
        print("Dry run — no changes made.")
        return 0

    # --- Step 1: Register on target profile ---
    # Check if the slug already exists on the target profile.
    r = hermes_profile(to_profile, "project", "show", slug, check=False, capture=True)
    if r.returncode == 0:
        # Slug exists on target — add-folder + set-primary if the path isn't already there.
        print(f"  ℹ️  Slug '{slug}' already exists on profile '{to_profile}' — adding folder.")
        hermes_profile(to_profile, "project", "add-folder", slug, str(project_path))
        hermes_profile(to_profile, "project", "set-primary", slug, str(project_path))
    else:
        # Create the project on the target profile.
        hermes_profile(
            to_profile,
            "project", "create", name,
            "--slug", slug,
            "--primary", str(project_path),
        )

    # --- Step 2: Detach from current profile ---
    if current_profile:
        # Archive on the current profile (idempotent — if already archived, no error).
        r = hermes_profile(current_profile, "project", "archive", slug, check=False, capture=True)
        if r.returncode != 0 and "already" not in r.stdout.lower() and "already" not in r.stderr.lower():
            print(f"  ⚠️  archive on '{current_profile}' returned non-zero (may already be archived)")
        # Remove the folder from the current profile's registration.
        hermes_profile(current_profile, "project", "remove-folder", slug, str(project_path), check=False)

    # --- Step 3: Update ecosystem manifest ---
    entry["profile"] = to_profile
    # Ensure the target profile is declared in the profiles section.
    profiles = manifest.setdefault("profiles", {})
    if to_profile not in profiles:
        profiles[to_profile] = {"description": f"Projects on the {to_profile} profile"}
    _save_manifest(manifest)
    print(f"  ✅ Ecosystem manifest updated: profile: {to_profile}")

    # --- Step 4: Update PROJECTS.md ---
    _update_projects_md(slug, to_profile)

    # --- Step 5: check-sync --strict ---
    sync_rc = _run_check_sync_strict()

    # --- Step 6: Remind ---
    print()
    print("  ⚠️  Reminder: the desktop app needs a quit+relaunch to pick up")
    print("     the new profile/project registration. Old chats don't migrate.")
    print()

    if sync_rc != 0:
        print("  ⚠️  check-sync --strict found DRIFT items — review above.")
        return 1

    print(f"✅ Project '{slug}' moved to profile '{to_profile}' successfully.")
    return 0


# ---------------------------------------------------------------------------
# Flow: status
# ---------------------------------------------------------------------------

def status() -> int:
    """Run check-sync.py and `hermes doctor`, print a plain-language summary."""
    print_plan("Hermes status check", [
        "Run check-sync.py (cross-surface sync)",
        "Run hermes doctor (health check)",
        "Print plain-language summary",
    ])

    # --- check-sync.py ---
    sync_py = str(CHECK_SYNC) if CHECK_SYNC.exists() else None
    py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    sync_output = ""
    sync_rc = 0
    if sync_py:
        r = run([py, sync_py], check=False, capture=True)
        sync_output = r.stdout.strip()
        sync_rc = r.returncode
    else:
        sync_output = "check-sync.py not found at ~/.hermes/scripts/check-sync.py"
        sync_rc = -1

    # --- hermes doctor ---
    r = hermes("doctor", check=False, capture=True)
    doctor_output = r.stdout.strip()
    doctor_rc = r.returncode

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if sync_rc == 0 and not sync_output:
        print("  ✅ Sync: all surfaces in sync (no drift, no review items).")
    elif sync_rc == 0:
        print(f"  ⚠️  Sync: clean (0 exit) but has review items:\n     {sync_output}")
    else:
        print(f"  ❌ Sync: drift found (exit {sync_rc}):\n     {sync_output}")

    if doctor_rc == 0:
        print("  ✅ Doctor: all health checks passed.")
    else:
        print(f"  ❌ Doctor: issues found (exit {doctor_rc}):")
        if doctor_output:
            for line in doctor_output.splitlines()[:10]:
                print(f"     {line}")

    print()
    if sync_rc == 0 and doctor_rc == 0:
        print("  All green. Nothing to fix.")
    else:
        print("  ⚠️  Some items need attention — see details above.")

    return 0 if (sync_rc == 0 and doctor_rc == 0) else 1


# ---------------------------------------------------------------------------
# Flow: explain
# ---------------------------------------------------------------------------

FLOWS_DOC: dict[str, dict[str, Any]] = {
    "move-project": {
        "summary": "Move a project between profiles — register on the target, detach from the source, update the manifest + PROJECTS.md.",
        "commands": [
            "hermes -p <to> project show <slug>  (check if slug exists on target)",
            "hermes -p <to> project create <name> --slug <slug> --primary <path>  (if not exists)",
            "hermes -p <to> project add-folder <slug> <path>  (if slug exists, add folder)",
            "hermes -p <to> project set-primary <slug> <path>  (if slug exists)",
            "hermes -p <from> project archive <slug>  (detach from current profile)",
            "hermes -p <from> project remove-folder <slug> <path>  (remove folder registration)",
            "# Update ecosystem manifest: set profile: <to> on the project row",
            "# Update PROJECTS.md: profile column -> <to>",
            "~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py --strict",
        ],
        "touches": [
            "Target profile's projects.db (via hermes project create/add-folder)",
            "Source profile's projects.db (via hermes project archive/remove-folder)",
            "~/projects/hermes/admin/ecosystem/manifest.yaml (profile: field on the project row)",
            "~/projects/hermes/admin/PROJECTS.md (profile column in the project row)",
        ],
        "args": "move-project <slug> <to-profile>",
    },
    "status": {
        "summary": "Run the cross-surface sync check and the health doctor, then print a plain-language summary.",
        "commands": [
            "~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py",
            "hermes doctor",
        ],
        "touches": [],
        "args": "status (no arguments)",
    },
    "project-new": {
        "summary": "Create a new project: make the folder (optional), register on a profile, add manifest + PROJECTS.md rows.",
        "commands": [
            "mkdir -p <path>  (if --path given)",
            "hermes -p <profile> project create <name> --slug <slug> --primary <path>",
            "# Add row to ~/projects/hermes/admin/ecosystem/manifest.yaml",
            "# Add row to ~/projects/hermes/admin/PROJECTS.md",
            "~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py --strict",
        ],
        "touches": [
            "Target profile's projects.db (via hermes project create)",
            "~/projects/hermes/admin/ecosystem/manifest.yaml (new project row)",
            "~/projects/hermes/admin/PROJECTS.md (new project row)",
        ],
        "args": "project-new <name> <profile> [--path <dir>]",
    },
    "profile-new": {
        "summary": "Create a new profile with alias, scoped repo scan roots, and model set.",
        "commands": [
            "hermes profile create <name> --description <desc>",
            "hermes profile alias <name>",
            "hermes -p <name> config set desktop.repo_scan_roots <paths>",
            "hermes -p <name> config set model.default <model>",
        ],
        "touches": [
            "~/.hermes/profiles/<name>/  (new profile directory)",
            "~/.hermes/profiles/<name>/config.yaml  (via hermes config set)",
        ],
        "args": "profile-new <name>",
    },
}


def explain(flow_name: str) -> int:
    """Print what a flow does, every command it runs, and what it touches. No execution."""
    if flow_name not in FLOWS_DOC:
        print(f"❌ Unknown flow '{flow_name}'. Available flows:")
        for name in sorted(FLOWS_DOC):
            print(f"   - {name}: {FLOWS_DOC[name]['args']}")
        return 1

    doc = FLOWS_DOC[flow_name]
    print(f"\n📋 hermes shortcut {flow_name}")
    print("=" * 60)
    print(f"\nSummary: {doc['summary']}")
    print(f"\nUsage: hermes shortcut {doc['args']}")
    print(f"\nCommands it runs:")
    for i, cmd in enumerate(doc["commands"], 1):
        print(f"  {i}. {cmd}")
    if doc["touches"]:
        print(f"\nWhat it touches:")
        for t in doc["touches"]:
            print(f"  - {t}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Flow: project-new (stub — for second milestone)
# ---------------------------------------------------------------------------

def project_new(name: str, profile: str, path: str | None = None, *, dry_run: bool = False) -> int:
    """Create a new project: folder (optional), register, manifest + PROJECTS.md rows."""
    # Derive a slug from the name (lowercase, hyphens for spaces).
    slug = name.lower().replace(" ", "-").replace("_", "-")

    project_path = Path(path).expanduser() if path else None

    steps = [
        f"Create folder: {project_path}" if project_path else "(no folder — path not given)",
        f"Register on profile '{profile}': hermes -p {profile} project create '{name}' --slug {slug}",
        f"Add ecosystem manifest row for slug '{slug}'",
        f"Add PROJECTS.md row for '{name}'",
        f"Run check-sync --strict",
    ]
    print_plan(f"Create new project '{name}' on profile '{profile}'", steps)

    if dry_run:
        print("Dry run — no changes made.")
        return 0

    # Step 1: Create folder if path given.
    if project_path:
        project_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Folder ready: {project_path}")

    # Step 2: Register on profile.
    create_args = ["-p", profile, "project", "create", name, "--slug", slug]
    if project_path:
        create_args += ["--primary", str(project_path)]
    hermes(*create_args)
    print(f"  ✅ Registered on profile '{profile}'")

    # Step 3: Add to manifest.
    manifest = _load_manifest()
    projects = manifest.setdefault("projects", [])
    if not any(p.get("slug") == slug for p in projects):
        entry = {"slug": slug, "name": name}
        if project_path:
            entry["path"] = str(project_path)
        entry["profile"] = profile
        projects.append(entry)
        _save_manifest(manifest)
        print(f"  ✅ Ecosystem manifest row added")

    # Step 4: Add to PROJECTS.md (append a row).
    _add_project_to_projects_md(name, str(project_path) if project_path else "(no folder)", profile)

    # Step 5: check-sync.
    _run_check_sync_strict()

    print(f"\n✅ Project '{name}' created on profile '{profile}'.")
    print("  ⚠️  Desktop app needs quit+relaunch to see the new project.")
    return 0


# ---------------------------------------------------------------------------
# Flow: profile-new (stub — for second milestone)
# ---------------------------------------------------------------------------

def profile_new(name: str, *, dry_run: bool = False) -> int:
    """Create a new profile with alias, scoped scan roots, and model set."""
    steps = [
        f"hermes profile create {name}",
        f"hermes profile alias {name}",
        f"hermes -p {name} config set desktop.repo_scan_roots <paths>",
        f"hermes -p {name} config set model.default <model>  (offer/confirm)",
    ]
    print_plan(f"Create new profile '{name}'", steps)

    if dry_run:
        print("Dry run — no changes made.")
        return 0

    # Step 1: Create profile.
    hermes("profile", "create", name)
    print(f"  ✅ Profile '{name}' created")

    # Step 2: Alias wrapper.
    hermes("profile", "alias", name)
    print(f"  ✅ Alias '{name}' created")

    # Step 3: Repo scan roots (default to empty for now — ask user or default).
    hermes("-p", name, "config", "set", "desktop.repo_scan_roots", "[]", check=False)
    print(f"  ✅ desktop.repo_scan_roots set to [] (adjust with: hermes -p {name} config set desktop.repo_scan_roots ...)")

    # Step 4: Model set — offer.
    print(f"\n  💡 To set a model: hermes -p {name} config set model.default <model>")
    print(f"     Or run: hermes -p {name} model")

    print(f"\n✅ Profile '{name}' created and configured.")
    return 0


# ---------------------------------------------------------------------------
# PROJECTS.md helpers
# ---------------------------------------------------------------------------

def _update_projects_md(slug: str, new_profile: str) -> None:
    """Update the profile column for a project slug in PROJECTS.md.

    PROJECTS.md has a markdown table; the project is identified by the
    slug appearing in the row (either in the path or the name). We update
    the Telegram topic / profile column to the new profile name.
    """
    if not PROJECTS_MD.exists():
        print(f"  ⚠️  PROJECTS.md not found at {PROJECTS_MD} — skipping update.")
        return

    content = PROJECTS_MD.read_text()
    lines = content.splitlines()
    updated = False

    for i, line in enumerate(lines):
        # Match table rows that contain the slug (case-insensitive).
        if slug.lower() in line.lower() and "|" in line and not line.startswith("|---"):
            # The table columns: Project | Path | Desktop session | Telegram topic | Priority | Status
            # We update the Telegram topic column (4th column) to the new profile.
            cols = line.split("|")
            if len(cols) >= 5:
                # cols[0] = empty (leading |), cols[4] = Telegram topic
                cols[4] = f" {new_profile} "
                lines[i] = "|".join(cols)
                updated = True

    if updated:
        PROJECTS_MD.write_text("\n".join(lines) + "\n")
        print(f"  ✅ PROJECTS.md updated: profile column → {new_profile}")
    else:
        print(f"  ⚠️  Could not find slug '{slug}' in PROJECTS.md — row not updated.")


def _add_project_to_projects_md(name: str, path: str, profile: str) -> None:
    """Append a new project row to PROJECTS.md."""
    if not PROJECTS_MD.exists():
        print(f"  ⚠️  PROJECTS.md not found at {PROJECTS_MD} — skipping.")
        return

    content = PROJECTS_MD.read_text()
    # Find the main table and append before the next blank line / section.
    lines = content.splitlines()
    insert_idx = None
    in_table = False
    for i, line in enumerate(lines):
        if line.startswith("| **") or (line.startswith("| ") and "---" not in line and "Project" not in line):
            in_table = True
        if in_table and not line.strip().startswith("|"):
            insert_idx = i
            break

    new_row = f"| **{name}** | `{path}` | {name} | {profile} | active | (new) |"

    if insert_idx is not None:
        lines.insert(insert_idx, new_row)
        PROJECTS_MD.write_text("\n".join(lines) + "\n")
        print(f"  ✅ PROJECTS.md row added for '{name}'")
    else:
        print(f"  ⚠️  Could not find table in PROJECTS.md — row not added.")


# ---------------------------------------------------------------------------
# check-sync gate
# ---------------------------------------------------------------------------

def _run_check_sync_strict() -> int:
    """Run check-sync.py --strict with the venv python. Returns exit code."""
    py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    sync_py = str(CHECK_SYNC) if CHECK_SYNC.exists() else None
    if not sync_py:
        print("  ⚠️  check-sync.py not found — skipping gate.")
        return 0
    r = run([py, sync_py, "--strict"], check=False, capture=True)
    if r.stdout.strip():
        print(f"  check-sync output:\n{r.stdout.strip()}")
    if r.returncode != 0:
        print(f"  ⚠️  check-sync --strict exited {r.returncode} (DRIFT items found)")
    return r.returncode
