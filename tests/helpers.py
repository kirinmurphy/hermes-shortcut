"""Test helpers: a fake PluginContext that captures registrations.

Mirrors the real loader pattern — the plugin is loaded as a namespace
package (hermes_plugins.<slug>) so relative imports work the same way
they do in production.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
import importlib.util
import sys


class FakePluginContext:
    """Captures register_cli_command / register_skill calls."""

    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.cli_commands: dict[str, dict] = {}
        self.skills: list[tuple[str, Path]] = []

    def register_cli_command(self, name, help="", setup_fn=None,
                             handler_fn=None, description=""):
        self.cli_commands[name] = {
            "name": name,
            "help": help,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "description": description,
        }

    def register_skill(self, name, skill_dir):
        self.skills.append((name, skill_dir))

    def register_tool(self, *a, **kw):
        pass  # shortcut has no tools


def load_plugin(plugin_dir: Path) -> ModuleType:
    """Load the plugin module the way PluginManager does it.

    Builds a hermes_plugins namespace package, then spec_from_file_location
    with submodule_search_locations=[plugin_dir] so relative imports work.

    The module name is derived from plugin.yaml's `name:` field (not the
    directory name — the directory may have a hyphen, which is not a valid
    Python identifier).
    """
    import yaml

    # Read the plugin name from plugin.yaml (valid Python identifier).
    with open(plugin_dir / "plugin.yaml") as f:
        ydata = yaml.safe_load(f)
    slug = ydata["name"]  # e.g. "shortcut" (no hyphens)

    # Create the hermes_plugins namespace package if it doesn't exist.
    if "hermes_plugins" not in sys.modules:
        pkg = ModuleType("hermes_plugins")
        pkg.__path__ = []  # namespace package
        sys.modules["hermes_plugins"] = pkg

    mod_name = f"hermes_plugins.{slug}"

    # If already loaded, return it (idempotent).
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(plugin_dir / "__init__.py"),
        submodule_search_locations=[str(plugin_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = mod_name
    mod.__path__ = [str(plugin_dir)]
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
