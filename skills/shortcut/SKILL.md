---
name: shortcut
description: "Guided multi-step configuration flows for Hermes — move projects between profiles, create projects/profiles, check status. Composed from the native CLI."
version: 0.2.0
author: Esteban (via Hermes)
license: MIT
---

# Shortcut — Hermes Configuration Flows

Use when the user wants a multi-step Hermes configuration change:
move a project between profiles, create a project or profile, check
overall status, or understand what a command does before running it.

Two kinds of commands:

- **Flows** mutate the ecosystem — macros over native `hermes` commands.
  Full command breakdown per flow: `docs/flows.md` in the plugin repo.
- **Utilities** are read-only.

## Flows

### `hermes shortcut move-project <slug> <to-profile>`
Moves a project between profiles:
1. Registers the project on the target profile (create, or add-folder + set-primary if the slug exists there).
2. Detaches from the current profile (archive + remove-folder).
3. Updates the ecosystem manifest (`profile:` field + profiles section).
4. Updates PROJECTS.md (topic column).
5. Runs check-sync --strict (the gate must stay green).
6. Reminds: desktop app needs quit+relaunch; old chats don't migrate.

Idempotent — already-on-target is a graceful no-op.

### `hermes shortcut new-project <name> <profile> [--path <dir>]`
Creates a folder (if --path), registers the project on the profile,
adds manifest + PROJECTS.md rows, runs the check-sync gate.

### `hermes shortcut new-profile <name>`
Creates the profile (`hermes profile create` + `alias`), scopes
`desktop.repo_scan_roots` (default []), and prints how to set its model.

## Utilities

### `hermes shortcut status`
Runs check-sync.py + `hermes doctor`, prints one plain-language summary.
Exit 0 only when both are clean.

### `hermes shortcut explain <name>`
Prints what a command does, every hermes command it runs, and what it
touches. No execution. Use before running an unfamiliar flow.

## Choosing

- Move a project between profiles → `move-project`
- New project → `new-project`
- New profile → `new-profile`
- Health check → `status`
- Review before running → `explain <name>`

## Rules

- Flows compose the native `hermes` CLI — macros, not parallel implementations.
- Every flow prints its plan first and is idempotent (safe to re-run).
- The check-sync gate must stay green after any manifest/PROJECTS.md change.
- No new dependencies — stdlib + the hermes CLI only.
