"""MainWindow — sidebar + stacked tool pages + status bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

if TYPE_CHECKING:
    from game_toolbox.core.registry import ToolRegistry


class MainWindow(QMainWindow):
    """Top-level application window.

    Layout::

        QSplitter
        ├── Sidebar (QListWidget)  — grouped by tool.category
        └── QStackedWidget         — one ToolPage per tool
        QStatusBar
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        """Initialise the main window.

        Args:
            registry: Tool registry used to populate the sidebar.
        """
        super().__init__()
        self.setWindowTitle("Game Toolbox")
        self.setMinimumSize(900, 600)

        self._registry = registry

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
