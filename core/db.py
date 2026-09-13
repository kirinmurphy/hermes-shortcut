"""Read-only access to the per-profile project registries (projects.db).

After the single-source collapse (Sep 2026), projects.db IS the source of
truth — one SQLite file per profile. This module is how the flows answer
questions across profiles (e.g. "where does this slug live?") without any
secondary spec files. Read-only: every mutation goes through the CLI.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _profile_homes() -> list[tuple[str, Path]]:
    """(profile_name, home_dir) for default + every named profile."""
    home = Path.home() / ".hermes"
    homes: list[tuple[str, Path]] = [("default", home)]
    profiles = home / "profiles"
    if profiles.is_dir():
        for d in sorted(profiles.iterdir()):
            if (d / "config.yaml").exists():
                homes.append((d.name, d))
    return homes


def all_projects() -> list[dict]:
    """Every active (non-archived) registration on every profile.

    Returns dicts: {profile, slug, name, primary_path}.
    Profiles with no/unreadable projects.db contribute nothing.
    """
    rows: list[dict] = []
    for pname, home in _profile_homes():
        db = home / "projects.db"
        if not db.exists():
            continue
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            found = conn.execute(
                "SELECT slug, name, primary_path FROM projects "
                "WHERE archived=0 ORDER BY name").fetchall()
            conn.close()
        except sqlite3.Error:
            continue
        for slug, name, path in found:
            rows.append({"profile": pname, "slug": slug, "name": name,
                         "primary_path": path or ""})
    return rows


def find_slug(slug: str) -> list[dict]:
    """All active registrations of a slug, across profiles."""
    return [r for r in all_projects() if r["slug"] == slug]
