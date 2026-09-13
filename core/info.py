"""The utilities — things that report or explain, but don't flow.

Utilities differ from flows: no plan, no mutation. `status` reports;
`explain` documents; `inventory` lists. All are read-only.
"""
from __future__ import annotations

from typing import Any

from . import db
from . import runner
from .runner import hermes


# ---------------------------------------------------------------------------
# Utility: status
# ---------------------------------------------------------------------------

def status() -> int:
    """Run check-sync + doctor, print one plain-language summary."""
    # --- check-sync.py ---
    sync_rc, sync_output = 0, ""
    if runner.CHECK_SYNC.exists():
        r = runner.run([str(runner.VENV_PYTHON), str(runner.CHECK_SYNC)],
                       check=False, capture=True)
        sync_rc, sync_output = r.returncode, r.stdout.strip()
    else:
        sync_rc, sync_output = -1, "check-sync.py not found at ~/.hermes/scripts/"

    # --- hermes doctor ---
    r = hermes("doctor", check=False, capture=True)
    doctor_rc, doctor_output = r.returncode, r.stdout.strip()

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if sync_rc == 0 and not sync_output:
        print("  ✅ Sync: all surfaces in sync (no drift, no review items).")
    elif sync_rc == 0:
        print(f"  ⚠️  Sync: clean, with review items:\n     {sync_output}")
    else:
        print(f"  ❌ Sync: drift found (exit {sync_rc}):\n     {sync_output}")

    if doctor_rc == 0:
        print("  ✅ Doctor: all health checks passed.")
    else:
        print(f"  ❌ Doctor: issues found (exit {doctor_rc}):")
        for line in doctor_output.splitlines()[:10]:
            print(f"     {line}")

    print()
    if sync_rc == 0 and doctor_rc == 0:
        print("  All green. Nothing to fix.")
        return 0
    print("  ⚠️  Some items need attention — see details above.")
    return 1


# ---------------------------------------------------------------------------
# Utility: inventory
# ---------------------------------------------------------------------------

def inventory() -> int:
    """List every project registration on every profile. Read-only.

    projects.db is the single source of truth; this is the cross-profile
    window onto it (no pass/fail, nothing to reconcile)."""
    rows = db.all_projects()
    print("\n" + "=" * 60)
    print("INVENTORY — project registrations across all profiles")
    print("=" * 60)
    if not rows:
        print("\n  No active registrations found on any profile.")
        return 0

    current = None
    for r in sorted(rows, key=lambda x: (x["profile"] != "default", x["profile"], x["name"])):
        if r["profile"] != current:
            current = r["profile"]
            print(f"\n  [{current}]")
        star = "*" if r["primary_path"] else " "
        print(f"    {star} {r['name']:<28} {r['slug']:<28} {r['primary_path']}")
    print(f"\n  {len(rows)} registration(s) total. * = has primary folder.")
    print("  (Single source: each profile's projects.db — no separate spec.)")
    return 0


# ---------------------------------------------------------------------------
# Utility: explain
# ---------------------------------------------------------------------------

# One entry per flow/utility. `commands` is the exact hermes surface the
# flow composes — kept in sync with docs/flows.md (the rendered version).
FLOWS_DOC: dict[str, dict[str, Any]] = {
    "move-project": {
        "kind": "flow",
        "summary": "Move a project between profiles — register on the target, "
                   "detach from the source. Slug is resolved from the "
                   "per-profile registries; no spec files involved.",
        "args": "move-project <slug> <to-profile>",
        "commands": [
            "hermes -p <to> project show <slug>",
            "hermes -p <to> project create <name> --slug <slug> --primary <path>",
            "  (or, if the slug already exists on <to>:)",
            "hermes -p <to> project add-folder <slug> <path>",
            "hermes -p <to> project set-primary <slug> <path>",
            "hermes -p <from> project archive <slug>",
            "hermes -p <from> project remove-folder <slug> <path>",
        ],
        "touches": [
            "target profile's projects.db (via hermes project …)",
            "source profile's projects.db (via hermes project …)",
        ],
    },
    "attach-project": {
        "kind": "flow",
        "summary": "Attach a project (registered on some profile) to another "
                   "profile. A project may be attached to several profiles.",
        "args": "attach-project <slug> <profile>",
        "commands": [
            "hermes -p <profile> project show <slug>",
            "hermes -p <profile> project create <name> --slug <slug> --primary <path>",
            "  (or, if the slug already exists on <profile>:)",
            "hermes -p <profile> project add-folder <slug> <path>",
            "hermes -p <profile> project set-primary <slug> <path>",
        ],
        "touches": [
            "profile's projects.db (via hermes project …)",
        ],
    },
    "status": {
        "kind": "utility",
        "summary": "Run the cross-surface sync check and the health doctor, "
                   "then print a plain-language summary.",
        "args": "status",
        "commands": [
            "~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py",
            "hermes doctor",
        ],
        "touches": [],
    },
    "inventory": {
        "kind": "utility",
        "summary": "List every project registration on every profile — the "
                   "cross-profile window onto projects.db (the single "
                   "source). Read-only, no pass/fail.",
        "args": "inventory",
        "commands": [
            "(read every profile's ~/.hermes[/profiles/<name>]/projects.db)",
        ],
        "touches": [],
    },
}


def explain(flow_name: str) -> int:
    """Print what a flow does, every command it runs, and what it touches."""
    if flow_name not in FLOWS_DOC:
        print(f"❌ Unknown flow '{flow_name}'. Available:")
        for name, doc in sorted(FLOWS_DOC.items()):
            print(f"   - {name} ({doc['kind']}): hermes shortcut {doc['args']}")
        return 1

    doc = FLOWS_DOC[flow_name]
    print(f"\n📋 hermes shortcut {flow_name}  ({doc['kind']})")
    print("=" * 60)
    print(f"\nSummary: {doc['summary']}")
    print(f"Usage:   hermes shortcut {doc['args']}")
    print("\nCommands it runs:")
    for i, cmd in enumerate(doc["commands"], 1):
        print(f"  {i}. {cmd}")
    if doc["touches"]:
        print("\nWhat it touches:")
        for t in doc["touches"]:
            print(f"  - {t}")
    print()
    return 0
