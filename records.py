"""Record bookkeeping — the ecosystem manifest and PROJECTS.md.

These two files are the declarative spec of the ecosystem (NOT hermes
config state), so this plugin edits them directly. Every hermes config/
project mutation still goes through the CLI (runner.py).

Path overrides: HERMES_ECOSYSTEM_MANIFEST / HERMES_PROJECTS_MD (used by
tests and CI to run against fixtures).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ECOSYSTEM_MANIFEST = Path(os.environ.get(
    "HERMES_ECOSYSTEM_MANIFEST",
    str(Path.home() / "projects" / "hermes" / "admin" / "ecosystem" / "manifest.yaml"),
))
PROJECTS_MD = Path(os.environ.get(
    "HERMES_PROJECTS_MD",
    str(Path.home() / "projects" / "hermes" / "admin" / "PROJECTS.md"),
))


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def load_manifest() -> dict[str, Any]:
    """Load the ecosystem manifest."""
    import yaml
    with open(ECOSYSTEM_MANIFEST) as f:
        return yaml.safe_load(f)


def save_manifest(data: dict[str, Any]) -> None:
    """Write the ecosystem manifest back."""
    import yaml
    with open(ECOSYSTEM_MANIFEST, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        f.write("\n")


def find_project(slug: str) -> dict[str, Any] | None:
    """Find a project entry by slug in the manifest."""
    for entry in load_manifest().get("projects", []):
        if entry.get("slug") == slug:
            return entry
    return None


def resolve_path(entry: dict[str, Any]) -> Path:
    """Resolve a manifest project entry's path to an absolute Path.

    Manifest paths are relative to the manifest's `home:` (e.g.
    `projects/job-hunt/` under `~/projects/hermes`) or absolute/~-rooted.
    """
    manifest = load_manifest()
    home = Path(manifest.get("home", "~/projects/hermes")).expanduser()
    path = entry.get("path", "")
    if path.startswith("~") or path.startswith("/"):
        return Path(path).expanduser()
    return home / path


def set_profile(slug: str, to_profile: str) -> None:
    """Set profile: <to_profile> on a project row, declaring the profile in
    the profiles: section if it's not there yet."""
    manifest = load_manifest()
    for entry in manifest.get("projects", []):
        if entry.get("slug") == slug:
            entry["profile"] = to_profile
            break
    profiles = manifest.setdefault("profiles", {})
    if to_profile not in profiles:
        profiles[to_profile] = {"description": f"Projects on the {to_profile} profile"}
    save_manifest(manifest)
    print(f"  ✅ Manifest updated: {slug} → profile {to_profile}")


def add_project(slug: str, name: str, path: str | None, profile: str) -> None:
    """Add a project row to the manifest (no-op if the slug already exists)."""
    manifest = load_manifest()
    projects = manifest.setdefault("projects", [])
    if any(p.get("slug") == slug for p in projects):
        return
    entry: dict[str, Any] = {"slug": slug, "name": name}
    if path:
        entry["path"] = path
    entry["profile"] = profile
    projects.append(entry)
    save_manifest(manifest)
    print(f"  ✅ Manifest row added for '{slug}'")


# ---------------------------------------------------------------------------
# PROJECTS.md
# ---------------------------------------------------------------------------

def update_projects_md(slug: str, new_profile: str) -> None:
    """Update a project row's topic column (4th) to the profile name.

    PROJECTS.md table shape: Project | Path | Desktop session | Telegram
    topic | Priority | Status — the topic column carries the profile for
    profile-scoped projects.
    """
    if not PROJECTS_MD.exists():
        print(f"  ⚠️  PROJECTS.md not found at {PROJECTS_MD} — skipping.")
        return

    lines = PROJECTS_MD.read_text().splitlines()
    updated = False
    for i, line in enumerate(lines):
        if _row_matches(line, slug):
            cols = line.split("|")
            if len(cols) >= 5:
                cols[4] = f" {new_profile} "
                lines[i] = "|".join(cols)
                updated = True
    if updated:
        PROJECTS_MD.write_text("\n".join(lines) + "\n")
        print(f"  ✅ PROJECTS.md updated: {slug} → {new_profile}")
    else:
        print(f"  ⚠️  No PROJECTS.md row matched '{slug}' — not updated.")


def add_to_projects_md(name: str, path: str, profile: str) -> None:
    """Append a new row to PROJECTS.md's main table."""
    if not PROJECTS_MD.exists():
        print(f"  ⚠️  PROJECTS.md not found at {PROJECTS_MD} — skipping.")
        return

    lines = PROJECTS_MD.read_text().splitlines()
    insert_idx = None
    in_table = False
    for i, line in enumerate(lines):
        if line.startswith("| **") or (line.startswith("| ") and "---" not in line and "Project" not in line):
            in_table = True
        if in_table and not line.strip().startswith("|"):
            insert_idx = i
            break

    if insert_idx is None:
        print("  ⚠️  Could not find the project table in PROJECTS.md — row not added.")
        return

    new_row = f"| **{name}** | `{path}` | {name} | {profile} | active | (new) |"
    lines.insert(insert_idx, new_row)
    PROJECTS_MD.write_text("\n".join(lines) + "\n")
    print(f"  ✅ PROJECTS.md row added for '{name}'")


def _row_matches(line: str, slug: str) -> bool:
    """Does a PROJECTS.md table row reference this slug? (Case-insensitive
    substring match on path/name, skipping the header separator.)"""
    return ("|" in line
            and not line.startswith("|---")
            and slug.lower() in line.lower())
