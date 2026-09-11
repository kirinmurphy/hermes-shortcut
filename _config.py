"""Single source of truth for the plugin's identity.

A future rename of this project should be ONE edit here (plus the
out-of-repo couplings listed in the runbook below).

Rename runbook (in-repo):
1. NAME / HUMAN_NAME below.
2. skills/<NAME>/ directory (git mv) — the bundled skill dir is keyed by name.

Out-of-repo couplings (the plugin loader enforces these):
3. Install dir: ~/.hermes/plugins/<NAME> — re-point the symlink.
4. plugins.enabled in ~/.hermes/config.yaml — via `hermes plugins enable`
   (never hand-edit).
5. Ecosystem manifest project row (slug may diverge from the plugin name).
"""
from pathlib import Path

# Machine name — used as the plugin registry key (plugin.yaml `name:` MUST
# match), the bundled skill name, and the CLI command name.
NAME = "shortcut"

# Human-facing product name (help text, docs).
HUMAN_NAME = "Shortcut"

# Plugin version (mirrors plugin.yaml `version:`).
VERSION = "0.1.0"

# Repo root (for path resolution inside the plugin).
PLUGIN_DIR = Path(__file__).resolve().parent
