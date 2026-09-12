# shortcut

Guided multi-step configuration flows for Hermes, exposed as native CLI
subcommands: `hermes shortcut <command>`.

Composes the **existing** native `hermes` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. When native Hermes absorbs a
command, that subcommand gets deleted.

## Commands

Two kinds: **flows** mutate the ecosystem (macros over native `hermes`
commands — the `macro` column links to exactly what each one runs);
**utilities** are read-only.

### Flows

| Flow | Usage | What it does | macro |
|---|---|---|---|
| `move-project` | `hermes shortcut move-project <slug> <to-profile>` | Move a project between profiles | [macro](docs/flows.md#move-project) |
| `create-project` | `hermes shortcut create-project <name> <profile> [--path <dir>]` | Create a new project | [macro](docs/flows.md#create-project) |
| `create-profile` | `hermes shortcut create-profile <name>` | Create a new profile with alias + model | [macro](docs/flows.md#create-profile) |

### Utilities

| Utility | Usage | What it does |
|---|---|---|
| `status` | `hermes shortcut status` | Run check-sync + doctor, print summary |
| `explain` | `hermes shortcut explain <name>` | Print what a command does (no execution) |

## Install


```bash
hermes plugins install <owner>/shortcut
```

