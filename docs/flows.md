# Flows & Utilities

`hermes shortcut` has two kinds of commands:

- **Flows** — macros that mutate state. Each one composes several native
  `hermes` CLI commands, prints its plan first, and is idempotent (safe to
  re-run).
- **Utilities** — read-only. They report or explain; they never mutate.

The macro principle: shortcut never replaces a hermes command — it composes
them, and only where composing beats the single command. Single source of
truth: each profile's `projects.db`. The plugin runs no record sync and no
gate; desktop-app creations are first-class records.

---

## move-project

**Usage:** `hermes shortcut move-project <slug> <to-profile>`

Move a project between profiles. The slug is resolved by reading every
profile's `projects.db` (read-only). The exact macro:

```bash
# 0. Find where the slug lives (across profiles). Several hits → pick one.

# 1. If the slug already exists on the target profile:
hermes -p <to> project add-folder <slug> <path>
hermes -p <to> project set-primary <slug> <path>
#    otherwise, register fresh:
hermes -p <to> project create <name> --slug <slug> --primary <path>

# 2. Detach from the source profile:
hermes -p <from> project archive <slug>
hermes -p <from> project remove-folder <slug> <path>
```

**Touches:** target + source profile `projects.db` (via `hermes project …`).

**Reminders printed at the end:** the desktop app needs a quit+relaunch;
old chats don't migrate.

---

## attach-project

**Usage:** `hermes shortcut attach-project <slug> <profile>`

Attach a project (registered on some profile) to another profile. A
project may be attached to several profiles. The exact macro:

```bash
# 0. Find the project's name + path (across profiles' projects.db).

# 1. If the slug already exists on the target profile:
hermes -p <profile> project add-folder <slug> <path>
hermes -p <profile> project set-primary <slug> <path>
#    otherwise, register fresh:
hermes -p <profile> project create <name> --slug <slug> --primary <path>
```

**Touches:** the target profile's `projects.db` (via `hermes project …`).

---

## Done natively (no flow exists)

**New profile** — desktop profile builder (Profile switcher → add), or:

```bash
hermes profile create <name>
```

**New project** — desktop sidebar "New project", or:

```bash
mkdir -p <path>   # only if you want the folder created
hermes -p <profile> project create "<Name>" --primary <path>
```

The command derives `<slug>` from the name (`--slug` is an override).

**Remove a project from a profile** — right-click → archive in the sidebar, or:

```bash
hermes -p <profile> project archive <slug>    # restore undoes it
```

**Scope a profile's Projects section** — Settings → Workspace →
"Automatic Repository Discovery" OFF. Per profile: ON with empty roots
scans all of `$HOME`, which is why every repo shows up on a new profile.
With it off, attach explicitly:

```bash
hermes shortcut attach-project <slug> <profile>
```

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

## inventory *(utility)*

**Usage:** `hermes shortcut inventory`

Read-only listing of every project registration on every profile:

```bash
# Walks every home with a config.yaml:
#   ~/.hermes/projects.db           (default profile)
#   ~/.hermes/profiles/<name>/projects.db   (each named profile)
# Prints active (non-archived) registrations grouped by profile.
```

The cross-profile window onto projects.db. No pass/fail — there is no
second source to reconcile against.

---

## explain *(utility)*

**Usage:** `hermes shortcut explain <name>`

Prints what a flow/utility does, every command it runs, and what it
touches. No execution — this page is the rendered version of the same
information.
