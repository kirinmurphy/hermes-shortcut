"""Subprocess plumbing — how the plugin calls the native `hermes` CLI.

Everything here is mechanical. WHAT gets run and WHY lives in flows.py
(the flows) and info.py (the utilities). This module just knows how to:

  - run a subprocess quietly (run)
  - run a hermes command, echoing it so the user sees the macro expand
    (hermes / hermes_profile)
  - print a flow's plan before executing (print_plan)
  - run the check-sync gate (check_sync_strict)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECK_SYNC = Path.home() / ".hermes" / "scripts" / "check-sync.py"
VENV_PYTHON = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, optionally capturing output."""
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def hermes(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run ``hermes <args>``.

    Echoes the command unless captured — every mutation this plugin makes
    is visible as the exact native command it maps to.
    """
    if not capture:
        print(f"  → hermes {' '.join(args)}")
    return run(["hermes", *args], check=check, capture=capture)


def hermes_profile(profile: str, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run ``hermes -p <profile> <args>``."""
    return hermes("-p", profile, *args, check=check, capture=capture)


def print_plan(title: str, steps: list[str]) -> None:
    """Print a flow's plan before executing it."""
    print(f"\n📋 {title}")
    print("=" * 60)
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    print()


def check_sync_strict() -> int:
    """Run check-sync.py --strict with the venv python. Returns its exit code.

    The contract: any manifest/PROJECTS.md change must leave this green.
    """
    py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    sync = str(CHECK_SYNC) if CHECK_SYNC.exists() else None
    if not sync:
        print("  ⚠️  check-sync.py not found — skipping gate.")
        return 0
    r = run([py, sync, "--strict"], check=False, capture=True)
    if r.stdout.strip():
        print(f"  check-sync output:\n{r.stdout.strip()}")
    if r.returncode != 0:
        print(f"  ⚠️  check-sync --strict exited {r.returncode} (DRIFT items found)")
    return r.returncode
