"""QApplication bootstrap and theme loading for Game Toolbox GUI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from game_toolbox.core.events import EventBus
from game_toolbox.core.registry import ToolRegistry
from game_toolbox.gui.main_window import MainWindow


def main() -> None:
    """Launch the Game Toolbox GUI application.

    Creates the QApplication, discovers tools via ``ToolRegistry``,
    builds the ``MainWindow``, and enters the Qt event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Game Toolbox")

    event_bus = EventBus()

    registry = ToolRegistry()
    registry.discover(event_bus=event_bus)

    window = MainWindow(registry=registry, event_bus=event_bus)
    window.show()

    sys.exit(app.exec())
