"""shortcut — guided multi-step configuration flows for Hermes.

Composes the EXISTING native ``hermes`` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. When native Hermes absorbs a
flow, that subcommand gets deleted.

Surface: ``hermes shortcut <command>`` — registered via register_cli_command.
No agent tools, no parallel config store.

Layout: the loader requires plugin.yaml + this file at the repo root, so the
root holds only setup/wiring and the execution code lives in ``core/``:
  _config.py     identity (NAME / HUMAN_NAME / VERSION / PLUGIN_DIR)
  core/cli.py    the argparse tree (argv → functions, no logic)
  core/flows.py  the flows — macros over native hermes commands
  core/info.py   the utilities (status, explain) — read-only
  core/records.py  manifest + PROJECTS.md bookkeeping (spec files)
  core/runner.py   subprocess plumbing (hermes calls, plans, the gate)

Contracts:
  - Compose native ``hermes`` CLI only — never write config/state directly.
  - Print the plan before executing; every flow is idempotent.
  - check-sync gate must stay green after any manifest/PROJECTS.md change.
  - No new dependencies. Stdlib + the hermes CLI only.
  - Git: work on main, commit after each working flow. Never push without
    explicit approval.
"""
from __future__ import annotations

from .core import cli
from ._config import HUMAN_NAME, NAME, PLUGIN_DIR


def register(ctx):
    """Register the shortcut CLI command and bundled skill."""
    ctx.register_cli_command(
        name=NAME,
        help=f"{HUMAN_NAME}: guided multi-step configuration flows for Hermes",
        setup_fn=cli.setup,
        handler_fn=_dispatch,
        description=(
            "Composes the native hermes CLI into multi-step flows: "
            "move-project, create-project, create-profile. Utilities: status, explain."
        ),
    )

    skill_dir = PLUGIN_DIR / "skills" / NAME
    if skill_dir.exists():
        try:
            ctx.register_skill(NAME, skill_dir)
        except Exception as e:
            print(f"[{NAME}] skill registration skipped: {e}")


def _dispatch(args):
    """Dispatch to the subcommand's func (set by cli.setup). Print help if
    no subcommand was given."""
    func = getattr(args, "func", None)
    if func is None:
        print("Usage: hermes shortcut <command> [args]")
        print("Flows: move-project, create-project, create-profile")
        print("Utilities: status, explain")
        print("Run 'hermes shortcut --help' for details.")
        return 0
    rc = func(args)
    return rc if isinstance(rc, int) else 0
