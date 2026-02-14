"""Integration tests for the ToolRegistry."""

from __future__ import annotations

from game_toolbox.core.events import EventBus
from game_toolbox.core.registry import ToolRegistry


class TestToolRegistryDiscovery:
    """Tests for auto-discovery of tools."""

    def setup_method(self) -> None:
        """Reset the singleton before each test."""
        ToolRegistry.reset()

    def teardown_method(self) -> None:
        """Reset the singleton after each test."""
        ToolRegistry.reset()

    def test_discovers_frame_extractor(self) -> None:
        """The registry finds the frame_extractor tool after discovery."""
        registry = ToolRegistry()
        registry.discover()

        tool = registry.get("frame_extractor")
        assert tool is not None
        assert tool.name == "frame_extractor"

    def test_all_tools_returns_discovered_tools(self) -> None:
        """``all_tools()`` contains all discovered tools."""
        registry = ToolRegistry()
        registry.discover()

        tools = registry.all_tools()
        assert "frame_extractor" in tools

    def test_get_returns_none_for_unknown_tool(self) -> None:
        """Looking up a non-existent tool returns ``None``."""
        registry = ToolRegistry()
        registry.discover()

        assert registry.get("nonexistent_tool") is None

    def test_singleton_returns_same_instance(self) -> None:
        """Multiple instantiations return the same singleton."""
        a = ToolRegistry()
        b = ToolRegistry()
        assert a is b

    def test_discover_injects_event_bus(self) -> None:
        """Tools receive the injected event bus."""
        bus = EventBus()
        registry = ToolRegistry()
        registry.discover(event_bus=bus)

        tool = registry.get("frame_extractor")
        assert tool is not None
        assert tool.event_bus is bus

    def test_reset_clears_singleton(self) -> None:
        """After reset, a new instance is created."""
        a = ToolRegistry()
        ToolRegistry.reset()
        b = ToolRegistry()
        assert a is not b
