"""cli.py — argparse tree for `hermes shortcut`.

Pure argument parsing: maps argv → flow/utility functions. The adapter
functions at the bottom unpack the argparse namespace into the flow's
keyword arguments — that's their whole job.
"""
from __future__ import annotations

import argparse

from . import flows, info


def setup(parser: argparse.ArgumentParser) -> None:
    """Attach sub-subparsers for every flow and utility."""
    sub = parser.add_subparsers(dest="shortcut_subcommand", metavar="<command>")

    mp = sub.add_parser("move-project", help="Flow: move a project between profiles")
    mp.add_argument("slug", help="Project slug (e.g. 'job-hunt')")
    mp.add_argument("to_profile", help="Target profile name (e.g. 'careering')")
    mp.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    mp.set_defaults(func=_move_project)

    pn = sub.add_parser("new-project", help="Flow: create a new project on a profile")
    pn.add_argument("name", help="Human project name (e.g. 'Job hunt')")
    pn.add_argument("profile", help="Target profile name")
    pn.add_argument("--path", default=None, help="Folder path for the project (optional)")
    pn.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    pn.set_defaults(func=_new_project)

    prn = sub.add_parser("new-profile", help="Flow: create a new profile with alias + model")
    prn.add_argument("name", help="Profile name (lowercase, alphanumeric)")
    prn.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    prn.set_defaults(func=_new_profile)

    st = sub.add_parser("status", help="Utility: run check-sync + doctor, print summary")
    st.set_defaults(func=_status)

    ex = sub.add_parser("explain", help="Utility: explain a flow or utility (no execution)")
    ex.add_argument("name", help="Name (move-project, new-project, new-profile, status)")
    ex.set_defaults(func=_explain)


# --- adapters: argparse namespace → flow/utility signature -------------------

def _move_project(args: argparse.Namespace) -> int:
    return flows.move_project(args.slug, args.to_profile, dry_run=args.dry_run)


def _new_project(args: argparse.Namespace) -> int:
    return flows.new_project(args.name, args.profile, path=args.path, dry_run=args.dry_run)


def _new_profile(args: argparse.Namespace) -> int:
    return flows.new_profile(args.name, dry_run=args.dry_run)


def _status(args: argparse.Namespace) -> int:
    return info.status()


def _explain(args: argparse.Namespace) -> int:
    return info.explain(args.name)
