"""ToolRegistry — singleton that auto-discovers and caches tool instances."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_toolbox.core.base_tool import BaseTool
    from game_toolbox.core.events import EventBus

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry that discovers all ``BaseTool`` subclasses.

    On first access the registry scans ``game_toolbox.tools.*`` sub-packages
    and instantiates every concrete ``BaseTool`` it finds.
    """

    _instance: ToolRegistry | None = None
    _tools: dict[str, BaseTool]

    def __new__(cls) -> ToolRegistry:
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def discover(self, event_bus: EventBus | None = None) -> None:
        """Scan ``game_toolbox.tools`` and register all ``BaseTool`` subclasses.

        Args:
            event_bus: Shared event bus injected into each tool.
        """
        from game_toolbox.core.base_tool import BaseTool

        tools_package = importlib.import_module("game_toolbox.tools")
        package_path = tools_package.__path__

        for _importer, module_name, is_pkg in pkgutil.iter_modules(package_path):
            if not is_pkg:
                continue
            try:
                tool_module = importlib.import_module(f"game_toolbox.tools.{module_name}.tool")
            except ImportError:
                logger.debug("Skipping %s — no tool.py found", module_name)
                continue

            for attr_name in dir(tool_module):
                attr = getattr(tool_module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                ):
                    tool_instance = attr(event_bus=event_bus)
                    self._tools[tool_instance.name] = tool_instance
                    logger.info("Registered tool: %s", tool_instance.name)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by its unique slug.

        Args:
            name: The tool's ``name`` attribute (e.g. ``"frame_extractor"``).

        Returns:
            The tool instance, or ``None`` if not found.
        """
        return self._tools.get(name)

    def all_tools(self) -> dict[str, BaseTool]:
        """Return all registered tools as a name → instance mapping."""
        return dict(self._tools)

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton — intended for testing only."""
        cls._instance = None
