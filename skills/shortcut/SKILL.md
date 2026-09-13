---
name: shortcut
description: "Guided multi-step configuration flows for Hermes — move projects between profiles, attach projects across profiles, list inventory, check status. Composed from the native CLI."
version: 0.4.0
author: Esteban (via Hermes)
license: MIT
---

# Shortcut — Hermes Configuration Flows

Use when the user wants a multi-step Hermes configuration change:
move a project between profiles, attach a project to another profile,
list what's registered where, check overall status, or understand what a
command does before running it.

**Single source of truth:** each profile's `projects.db`. No spec files,
no record sync, no gate. The desktop app is a first-class editor — its
creations ARE records.

Every flow takes `--dry-run`: prints the plan, executes nothing.

## Flows

### `hermes shortcut move-project <slug> <to-profile>`
Moves a project between profiles:
1. Registers the project on the target profile (create, or add-folder + set-primary if the slug exists there).
2. Detaches from the current profile (archive + remove-folder).
3. Reminds: desktop app needs quit+relaunch; old chats don't migrate.

Idempotent — already-on-target is a graceful no-op. A slug registered on
several profiles must be disambiguated first.

### `hermes shortcut attach-project <slug> <profile>`
Attaches a project (registered on some profile) to another profile —
resolves the slug's name + path across all profiles' projects.db, then
registers it on the target. Repeatable: a project can be attached to
several profiles.

## Utilities

### `hermes shortcut status`
Runs check-sync.py + `hermes doctor`, prints one plain-language summary.
Exit 0 only when both are clean.

### `hermes shortcut inventory`
Read-only listing of every project registration on every profile — the
cross-profile window onto projects.db. No pass/fail, nothing to reconcile.

### `hermes shortcut explain <name>`
Prints what a command does, every hermes command it runs, and what it
touches. No execution. Use before running an unfamiliar flow.

## Done natively (no flow exists)

- **New profile** — desktop profile builder (Profile switcher → add), or
  `hermes profile create <name>`.
- **New project** — desktop sidebar "New project", or
  `mkdir -p <path> && hermes -p <profile> project create "<Name>" --primary <path>`.
- **Remove a project from a profile** — `hermes -p <profile> project archive <slug>`
  (restore undoes it), or right-click → archive in the sidebar.
- **Scope a profile's Projects section** — Settings → Workspace →
  "Automatic Repository Discovery" OFF (per profile; ON with empty roots
  scans all of $HOME — the reason every repo appears on a new profile).
  Then attach explicitly: `hermes shortcut attach-project <slug> <profile>`.

## Choosing

- Move a project between profiles → `move-project`
- Same project on another profile (cross-profile lookup) → `attach-project`
- What's registered where? → `inventory`
- Health check → `status`
- Review before running → `explain <name>`

## Rules

- Flows compose the native `hermes` CLI — macros, not parallel implementations.
  A flow that adds nothing over a single native command doesn't belong here.
- Every flow prints its plan first, is idempotent (safe to re-run), and
  supports `--dry-run`.
- projects.db is the only registry; the plugin never writes spec files.
- No new dependencies — stdlib + the hermes CLI only.
