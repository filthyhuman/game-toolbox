"""ConfigManager — per-tool and global settings backed by TOML files."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "game-toolbox"


class ConfigManager:
    """Strategy-based configuration manager.

    Provides hierarchical configuration: global defaults can be
    overridden by per-tool settings.  Settings are loaded from TOML
    files on disk.

    Args:
        config_dir: Root directory for configuration files.
                    Defaults to ``~/.config/game-toolbox/``.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialise the config manager.

        Args:
            config_dir: Custom configuration directory.  Uses the
                        platform default if ``None``.
        """
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._global: dict[str, Any] = {}
        self._per_tool: dict[str, dict[str, Any]] = {}

    @property
    def config_dir(self) -> Path:
        """Return the configuration directory path."""
        return self._config_dir

    def load(self) -> None:
        """Load global and per-tool config from ``config_dir``.

        Missing files are silently skipped.
        """
        global_file = self._config_dir / "config.toml"
        if global_file.is_file():
            self._global = self._read_toml(global_file)
            logger.info("Loaded global config from %s", global_file)

        tools_dir = self._config_dir / "tools"
        if tools_dir.is_dir():
            for toml_file in tools_dir.glob("*.toml"):
                tool_name = toml_file.stem
                self._per_tool[tool_name] = self._read_toml(toml_file)
                logger.info("Loaded config for tool '%s'", tool_name)

    def get(self, key: str, *, tool: str | None = None, default: Any = None) -> Any:
        """Retrieve a config value with optional tool-level override.

        Args:
            key: The configuration key.
            tool: If given, check the tool-specific config first.
            default: Fallback value when the key is not found.

        Returns:
            The configuration value, or *default*.
        """
        if tool and tool in self._per_tool:
            value = self._per_tool[tool].get(key)
            if value is not None:
                return value
        return self._global.get(key, default)

    def set_global(self, key: str, value: Any) -> None:
        """Set a global configuration value (in-memory only).

        Args:
            key: The configuration key.
            value: The value to store.
        """
        self._global[key] = value

    @staticmethod
    def _read_toml(path: Path) -> dict[str, Any]:
        """Read and parse a TOML file.

        Args:
            path: Path to the TOML file.

        Returns:
            Parsed dictionary.
        """
        with path.open("rb") as fh:
            return tomllib.load(fh)
