"""shortcut — guided multi-step configuration flows for Hermes.

Composes the EXISTING native ``hermes`` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. When native Hermes absorbs a
flow, that subcommand gets deleted.

Surface: ``hermes shortcut <flow>`` — native CLI subcommands registered via
``ctx.register_cli_command``. No agent tools, no parallel config store.

Flows:
  move-project <slug> <to-profile>   Move a project between profiles
  status                              Run check-sync + doctor, summarize
  explain <flow>                      Print what a flow does (no execution)
  project-new <name> <profile> [--path]  Create a new project (milestone 2)
  profile-new <name>                  Create a new profile (milestone 2)

Contracts (see AGENTS.md):
  - Compose native ``hermes`` CLI only — never write config/state directly.
  - Print the plan before executing; every flow is idempotent.
  - check-sync gate must stay green after any manifest/PROJECTS.md change.
  - No new dependencies. Stdlib + the hermes CLI only.
  - Git: work on main, commit after each working flow. Never push without
    explicit approval.
"""
from __future__ import annotations

import argparse
import sys

from . import _config
from ._config import HUMAN_NAME, NAME, PLUGIN_DIR, VERSION
from . import flows


def _setup_shortcut_parser(parser: argparse.ArgumentParser) -> None:
    """Set up the ``hermes shortcut`` subparser with sub-subparsers.

    This is the function passed to ``ctx.register_cli_command`` as
    ``setup_fn``. It receives the argparse subparser for ``hermes shortcut``
    and MUST add the sub-subparsers (otherwise every subcommand parse-fails).
    """
    sub = parser.add_subparsers(dest="shortcut_subcommand", metavar="<flow>")

    # move-project
    mp = sub.add_parser(
        "move-project",
        help="Move a project between profiles",
        description="Move a project from one profile to another: register on target, detach from source, update manifest + PROJECTS.md.",
    )
    mp.add_argument("slug", help="Project slug (e.g. 'job-hunt')")
    mp.add_argument("to_profile", help="Target profile name (e.g. 'careering')")
    mp.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    mp.set_defaults(func=_cmd_move_project)

    # status
    st = sub.add_parser(
        "status",
        help="Run check-sync + doctor, print summary",
        description="Run the cross-surface sync check and the health doctor, then print a plain-language summary.",
    )
    st.set_defaults(func=_cmd_status)

    # explain
    ex = sub.add_parser(
        "explain",
        help="Explain a flow (no execution)",
        description="Print what a flow does, every command it will run, and what it touches. No execution.",
    )
    ex.add_argument("flow_name", help="Flow name (move-project, status, project-new, profile-new)")
    ex.set_defaults(func=_cmd_explain)

    # project-new
    pn = sub.add_parser(
        "project-new",
        help="Create a new project on a profile",
        description="Create a folder (optional), register on a profile, add manifest + PROJECTS.md rows.",
    )
    pn.add_argument("name", help="Human project name (e.g. 'Job hunt')")
    pn.add_argument("profile", help="Target profile name")
    pn.add_argument("--path", help="Folder path for the project (optional)", default=None)
    pn.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    pn.set_defaults(func=_cmd_project_new)

    # profile-new
    prn = sub.add_parser(
        "profile-new",
        help="Create a new profile with alias and model",
        description="Create a new profile, add alias, scope scan roots, and offer model set.",
    )
    prn.add_argument("name", help="Profile name (lowercase, alphanumeric)")
    prn.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    prn.set_defaults(func=_cmd_profile_new)


# ---------------------------------------------------------------------------
# Command handlers (called by argparse dispatch via set_defaults(func=...))
# ---------------------------------------------------------------------------

def _cmd_move_project(args: argparse.Namespace) -> int:
    return flows.move_project(args.slug, args.to_profile, dry_run=args.dry_run)


def _cmd_status(args: argparse.Namespace) -> int:
    return flows.status()


def _cmd_explain(args: argparse.Namespace) -> int:
    return flows.explain(args.flow_name)


def _cmd_project_new(args: argparse.Namespace) -> int:
    return flows.project_new(args.name, args.profile, path=args.path, dry_run=args.dry_run)


def _cmd_profile_new(args: argparse.Namespace) -> int:
    return flows.profile_new(args.name, dry_run=args.dry_run)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx):
    """Register the shortcut CLI command and bundled skill."""
    ctx.register_cli_command(
        name=NAME,
        help=f"{HUMAN_NAME}: guided multi-step configuration flows for Hermes",
        setup_fn=_setup_shortcut_parser,
        handler_fn=_dispatch,
        description=(
            "Composes the native hermes CLI into multi-step flows: "
            "move-project, status, explain, project-new, profile-new."
        ),
    )

    skill_dir = PLUGIN_DIR / "skills" / NAME
    if skill_dir.exists():
        try:
            ctx.register_skill(NAME, skill_dir)
        except Exception as e:
            print(f"[{NAME}] skill registration skipped: {e}")


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch a shortcut subcommand by its ``func`` default.

    argparse calls this via ``set_defaults(func=_dispatch)`` on the top-level
    shortcut parser; each sub-subparser overrides ``func`` with its own
    handler. If no subcommand was given, print help.
    """
    func = getattr(args, "func", None)
    if func is None:
        print("Usage: hermes shortcut <flow> [args]")
        print("Flows: move-project, status, explain, project-new, profile-new")
        print("Run 'hermes shortcut --help' for details.")
        return 0

    rc = func(args)
    if isinstance(rc, int):
        return rc
    return 0
