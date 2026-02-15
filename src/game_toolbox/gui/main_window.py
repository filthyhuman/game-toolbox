"""MainWindow — sidebar + stacked tool pages + status bar."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from game_toolbox.gui.pipeline_editor import PipelineEditor
from game_toolbox.gui.tool_page import ToolPage

if TYPE_CHECKING:
    from game_toolbox.core.events import EventBus
    from game_toolbox.core.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window.

    Layout::

        QSplitter
        +-- Sidebar (QListWidget)  -- grouped by tool.category
        +-- QStackedWidget         -- one ToolPage per tool
        QStatusBar
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialise the main window.

        Args:
            registry: Tool registry used to populate the sidebar.
            event_bus: Shared event bus for status-bar updates.
        """
        super().__init__()
        self.setWindowTitle("Game Toolbox")
        self.setMinimumSize(900, 600)

        self._registry = registry
        self._event_bus = event_bus
        self._item_to_index: dict[int, int] = {}  # sidebar-item id → stack index

        # ── Widgets ────────────────────────────────────────────
        self._sidebar = QListWidget()
        self._stack = QStackedWidget()

        splitter = QSplitter()
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(1, 3)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # ── Populate tools and wire signals ────────────────────
        self._populate_tools()
        self._sidebar.currentItemChanged.connect(self._on_sidebar_changed)

        if self._event_bus is not None:
            self._event_bus.subscribe("completed", self._on_tool_completed)

    # ── Private helpers ────────────────────────────────────────

    def _populate_tools(self) -> None:
        """Build sidebar entries and ToolPages from the registry."""
        if self._registry is None:
            return

        tools = self._registry.all_tools()
        if not tools:
            return

        # Group tools by category
        categories: dict[str, list[Any]] = {}
        for tool in tools.values():
            cat = tool.category or "General"
            categories.setdefault(cat, []).append(tool)

        # Sort categories alphabetically; tools within each category too
        for cat in sorted(categories):
            # Category header (non-selectable, bold)
            header = QListWidgetItem(cat)
            header_font = QFont()
            header_font.setBold(True)
            header.setFont(header_font)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._sidebar.addItem(header)

            for tool in sorted(categories[cat], key=lambda t: t.display_name):
                item = QListWidgetItem(f"  {tool.display_name}")
                self._sidebar.addItem(item)

                page = ToolPage(tool, event_bus=self._event_bus)
                stack_index = self._stack.addWidget(page)
                self._item_to_index[id(item)] = stack_index

        # Pipeline Editor placeholder
        pipeline_header = QListWidgetItem("Pipelines")
        pipeline_font = QFont()
        pipeline_font.setBold(True)
        pipeline_header.setFont(pipeline_font)
        pipeline_header.setFlags(Qt.ItemFlag.NoItemFlags)
        self._sidebar.addItem(pipeline_header)

        pipeline_item = QListWidgetItem("  Pipeline Editor")
        self._sidebar.addItem(pipeline_item)
        pipeline_index = self._stack.addWidget(PipelineEditor())
        self._item_to_index[id(pipeline_item)] = pipeline_index

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_sidebar_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        """Switch the stacked widget when a sidebar item is selected.

        Args:
            current: The newly selected sidebar item.
            _previous: The previously selected item (unused).
        """
        if current is None:
            return
        index = self._item_to_index.get(id(current))
        if index is not None:
            self._stack.setCurrentIndex(index)

    def _on_tool_completed(self, **kwargs: Any) -> None:
        """Show a status-bar message when a tool finishes.

        Args:
            **kwargs: Event data; expects ``tool`` key with the tool name.
        """
        tool_name = kwargs.get("tool", "Tool")
        self._status_bar.showMessage(f"{tool_name} completed.", 5000)
