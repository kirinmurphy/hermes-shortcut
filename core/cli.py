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

    ap = sub.add_parser("attach-project", help="Flow: attach a project to a profile")
    ap.add_argument("slug", help="Project slug (e.g. 'job-hunt')")
    ap.add_argument("profile", help="Profile to attach it to")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan without executing")
    ap.set_defaults(func=_attach_project)

    st = sub.add_parser("status", help="Utility: run check-sync + doctor, print summary")
    st.set_defaults(func=_status)

    inv = sub.add_parser("inventory",
                         help="Utility: list all project registrations across profiles")
    inv.set_defaults(func=_inventory)

    ex = sub.add_parser("explain", help="Utility: explain a flow or utility (no execution)")
    ex.add_argument("name", help="Name (move-project, attach-project, status, …)")
    ex.set_defaults(func=_explain)


# --- adapters: argparse namespace → flow/utility signature -------------------

def _move_project(args: argparse.Namespace) -> int:
    return flows.move_project(args.slug, args.to_profile, dry_run=args.dry_run)


def _attach_project(args: argparse.Namespace) -> int:
    return flows.attach_project(args.slug, args.profile, dry_run=args.dry_run)


def _status(args: argparse.Namespace) -> int:
    return info.status()


def _inventory(args: argparse.Namespace) -> int:
    return info.inventory()


def _explain(args: argparse.Namespace) -> int:
    return info.explain(args.name)
