# shortcut

Guided multi-step configuration flows for Hermes, exposed as native CLI
subcommands: `hermes shortcut <flow>`.

Composes the **existing** native `hermes` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. When native Hermes absorbs a
flow, that subcommand gets deleted.

## Flows

| Flow | Usage | What it does |
|---|---|---|
| `move-project` | `hermes shortcut move-project <slug> <to-profile>` | Move a project between profiles |
| `status` | `hermes shortcut status` | Run check-sync + doctor, print summary |
| `explain` | `hermes shortcut explain <flow>` | Print what a flow does (no execution) |
| `project-new` | `hermes shortcut project-new <name> <profile> [--path <dir>]` | Create a new project |
| `profile-new` | `hermes shortcut profile-new <name>` | Create a new profile with alias + model |

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
