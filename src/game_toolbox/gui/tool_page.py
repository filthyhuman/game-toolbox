"""ToolPage — base widget that wraps a tool's parameter form."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from game_toolbox.core.base_tool import BaseTool


class ToolPage(QWidget):
    """Adapter widget that presents a ``BaseTool`` in the GUI.

    Renders an auto-generated parameter form and an optional custom
    panel provided by the tool.

    Args:
        tool: The ``BaseTool`` instance to display.
        parent: Optional parent widget.
    """

    def __init__(self, tool: BaseTool, parent: QWidget | None = None) -> None:
        """Initialise the tool page.

        Args:
            tool: The tool whose parameters are rendered.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._tool = tool

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>{tool.display_name}</h2>"))
        layout.addWidget(QLabel(tool.description))
        layout.addStretch()
