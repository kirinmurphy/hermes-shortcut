# shortcut

Guided multi-step configuration flows for Hermes, exposed as native CLI
subcommands: `hermes shortcut <flow>`.

Composes the **existing** native `hermes` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. When native Hermes absorbs a
flow, that subcommand gets deleted.

## Commands

Two kinds: **flows** mutate the ecosystem (macro over native `hermes`
commands — see [docs/flows.md](docs/flows.md) for exactly what each one
runs); **utilities** are read-only.

### Flows

| Flow | Usage | What it does | Macro |
|---|---|---|---|
| `move-project` | `hermes shortcut move-project <slug> <to-profile>` | Move a project between profiles | [see macro](docs/flows.md#move-project) |
| `new-project` | `hermes shortcut new-project <name> <profile> [--path <dir>]` | Create a new project | [see macro](docs/flows.md#new-project) |
| `new-profile` | `hermes shortcut new-profile <name>` | Create a new profile with alias + model | [see macro](docs/flows.md#new-profile) |

### Utilities

| Utility | Usage | What it does |
|---|---|---|
| `status` | `hermes shortcut status` | Run check-sync + doctor, print summary |
| `explain` | `hermes shortcut explain <name>` | Print what a command does (no execution) |

## How the code fits together

One job per file:

| Module | Job |
|---|---|
| `__init__.py` | Plugin entry point — registers the CLI command + skill. Nothing else. |
| `cli.py` | The argparse tree: maps argv to functions. No logic. |
| `flows.py` | The flows — each reads as its sequence of native `hermes` commands. |
| `info.py` | The utilities (`status`, `explain`) — read-only. |
| `records.py` | Ecosystem manifest + PROJECTS.md bookkeeping. |
| `runner.py` | Subprocess plumbing: how `hermes` gets called, plan printing, the check-sync gate. |

Reading a flow (`flows.py`) shows the actual hermes workflow; the plumbing
it calls is in `runner.py`, the file edits in `records.py`. Every hermes
mutation is echoed to the terminal as it runs (`→ hermes -p careering project …`),
so the macro is visible in the output.

## Install

```bash
ln -s ~/projects/hermes-tooling/hermes-shortcut ~/.hermes/plugins/shortcut
hermes plugins enable shortcut
```

Verify the symlink (not a copy — copies cause drift):

```bash
file ~/.hermes/plugins/shortcut
# symbolic link → .../hermes-shortcut/
```

## Tests

```bash
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests -v
```

Hermetic — the flow tests run against fixtures in `tests/fixtures/`, no real
Hermes ecosystem or even a Hermes install required (same suite runs in the
GitHub CI workflow). Live verification of a flow happens by running the real
command, e.g. `hermes shortcut explain move-project`.

## Contracts

See AGENTS.md for the full contract. Key rules:

- Compose native `hermes` CLI only — never write config/state directly.
- Print the plan before executing; every flow idempotent.
- check-sync gate must stay green after any manifest/PROJECTS.md change.
- No new dependencies. Stdlib + the hermes CLI only.
