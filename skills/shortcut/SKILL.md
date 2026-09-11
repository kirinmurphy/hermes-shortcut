---
name: shortcut
description: "Guided multi-step configuration flows for Hermes — move projects between profiles, check status, create projects/profiles. Composed from the native CLI."
version: 0.1.0
author: Esteban (via Hermes)
license: MIT
---

# Shortcut — Hermes Configuration Flows

Use when the user wants to run a multi-step Hermes configuration flow:
move a project between profiles, check overall status, create a new
project or profile, or understand what a flow does before running it.

## Commands

### `hermes shortcut move-project <slug> <to-profile>`
Moves a project from one profile to another:
1. Registers the project on the target profile (create or add-folder + set-primary).
2. Detaches from the current profile (archive + remove-folder).
3. Updates the ecosystem manifest (`profile:` field on the project row).
4. Updates PROJECTS.md (profile column).
5. Runs check-sync --strict to verify the gate stays green.
6. Reminds: desktop app needs quit+relaunch; old chats don't migrate.

Idempotent — if the project is already on the target profile, no-ops gracefully.

### `hermes shortcut status`
Runs `check-sync.py` (cross-surface sync) and `hermes doctor` (health check),
then prints a plain-language summary. Exit 0 if all green, 1 if issues found.

### `hermes shortcut explain <flow>`
Prints what a flow does, every command it will run, and what it touches.
Does NOT execute anything. Use this to review a flow before running it.

### `hermes shortcut project-new <name> <profile> [--path <dir>]`
Creates a new project: makes the folder (if --path given), registers on
the profile, adds manifest + PROJECTS.md rows, runs check-sync --strict.

### `hermes shortcut profile-new <name>`
Creates a new profile: `hermes profile create`, `hermes profile alias`,
scopes `desktop.repo_scan_roots`, and offers model set.

## When to use which flow

- **Moving a project between profiles** → `move-project` (the full flow:
  register + detach + manifest + PROJECTS.md + check-sync gate).
- **Quick health check** → `status` (check-sync + doctor + summary).
- **Reviewing a flow before running it** → `explain <flow>`.
- **Creating a new project** → `project-new`.
- **Creating a new profile** → `profile-new`.

## Rules

- These flows compose the native `hermes` CLI — they are macros, not
  parallel implementations.
- Every flow prints its plan before executing.
- Every flow is idempotent (safe to re-run).
- The check-sync gate must stay green after any manifest/PROJECTS.md change.
- No new dependencies — stdlib + the hermes CLI only.
