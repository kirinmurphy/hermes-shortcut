# shortcut

Guided multi-step configuration flows for Hermes, exposed as native CLI
subcommands: `hermes shortcut <command>`.

Composes the **existing** native `hermes` CLI into multi-task flows. It is a
macro layer, NOT a parallel implementation. A flow that adds nothing over a
single native command doesn't exist here.

**Single source of truth:** each profile's `projects.db` (the Hermes
primitive the desktop app renders). This plugin has no spec files, no record
sync, and no gate — backups are file-level SQLite copies of the dbs.

## Commands

Two kinds: **flows** mutate state (macros over native `hermes` commands —
the `macro` column links to exactly what each one runs); **utilities** are
read-only.

### Flows

| Flow | Usage | What it does | macro |
|---|---|---|---|
| `move-project` | `hermes shortcut move-project <slug> <to-profile>` | Move a project between profiles | [macro](docs/flows.md#move-project) |
| `attach-project` | `hermes shortcut attach-project <slug> <profile>` | Attach a project to another profile | [macro](docs/flows.md#attach-project) |

### Utilities

| Utility | Usage | What it does |
|---|---|---|
| `status` | `hermes shortcut status` | Run check-sync + doctor, print summary |
| `inventory` | `hermes shortcut inventory` | List all project registrations across profiles |
| `explain` | `hermes shortcut explain <name>` | Print what a command does (no execution) |

### Plugin lifecycle

```bash
hermes plugins update shortcut    # pull latest
hermes plugins remove shortcut    # uninstall
```

Plugin installs are per home: `~/.hermes/plugins/` (default) or
`~/.hermes/profiles/<name>/plugins/`. Run update/remove in the same scope
the plugin is installed in (`-p <profile>` or the default, matching where
`hermes plugins list` shows it).

### Done natively (no flow)

Profiles: desktop profile builder or `hermes profile create`. Projects:
desktop sidebar or `hermes -p <profile> project create "<Name>" --primary <path>`.
Archive: `hermes -p <profile> project archive <slug>`. Scoping a profile's
Projects section: Settings → Workspace → Automatic Repository Discovery off,
then `attach-project` explicitly.

## Install

```bash
hermes plugins install <owner>/shortcut
```
