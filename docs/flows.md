# Flows & Utilities

`hermes shortcut` has two kinds of commands:

- **Flows** — macros that mutate the ecosystem. Each one composes several
  native `hermes` CLI commands plus the record bookkeeping, prints its plan
  first, and is idempotent (safe to re-run).
- **Utilities** — read-only. They report or explain; they never mutate.

The macro principle: shortcut never replaces a hermes command — it composes
them. Every mutation below is a native command you could run by hand; the
flow adds ordering, the record sync, and the check-sync gate.

---

## move-project

**Usage:** `hermes shortcut move-project <slug> <to-profile>`

Move a project between profiles. The exact macro:

```bash
# 0. Look up the project's current profile + path (ecosystem manifest)

# 1. If the slug already exists on the target profile:
hermes -p <to> project add-folder <slug> <path>
hermes -p <to> project set-primary <slug> <path>
#    otherwise, register fresh:
hermes -p <to> project create <name> --slug <slug> --primary <path>

# 2. Detach from the source profile:
hermes -p <from> project archive <slug>
hermes -p <from> project remove-folder <slug> <path>

# 3. Record sync (direct edits — these are declarative spec files):
#    - ecosystem manifest: set profile: <to> on the project row,
#      declare <to> in profiles: if missing
#    - PROJECTS.md: topic column of the project row → <to>

# 4. Gate — must stay green:
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py --strict
```

**Touches:** target + source profile project registries (via `hermes
project …`), `~/projects/hermes/admin/ecosystem/manifest.yaml`,
`~/projects/hermes/admin/PROJECTS.md`.

**Reminders printed at the end:** the desktop app needs a quit+relaunch;
old chats don't migrate.

---

## create-project

**Usage:** `hermes shortcut create-project <name> <profile> [--path <dir>]`

Create a new project and register it everywhere. The exact macro:

```bash
# 0. Create the folder (only if --path given):
mkdir -p <path>

# 1. Register on the profile:
hermes -p <profile> project create <name> --slug <slug> --primary <path>

# 2. Record sync (direct edits):
#    - ecosystem manifest: new project row (slug, name, path, profile)
#    - PROJECTS.md: new row in the main table

# 3. Gate — must stay green:
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py --strict
```

**Touches:** the project folder (if `--path`), the profile's project
registry, the ecosystem manifest, PROJECTS.md.

---

## create-profile

**Usage:** `hermes shortcut create-profile <name>`

Create a profile with an alias and scoped scan roots. The exact macro:

```bash
hermes profile create <name>
hermes profile alias <name>
hermes -p <name> config set desktop.repo_scan_roots []

# Model choice is offered, not guessed:
#   hermes -p <name> config set model.default <model>   (or: hermes -p <name> model)
```

**Touches:** `~/.hermes/profiles/<name>/` (via `hermes profile create` and
`hermes config set` only).

---

## status *(utility)*

**Usage:** `hermes shortcut status`

Read-only health report. Runs:

```bash
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/check-sync.py
hermes doctor
```

Prints one plain-language summary; exits 0 only when both are clean.

---

## explain *(utility)*

**Usage:** `hermes shortcut explain <name>`

Prints what a flow/utility does, every command it runs, and what it
touches. No execution — this page is the rendered version of the same
information.
