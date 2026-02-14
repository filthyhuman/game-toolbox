"""PipelineEditor — visual node-graph canvas for chaining tools."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PipelineEditor(QWidget):
    """Visual pipeline editor — placeholder for future node-graph canvas.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the pipeline editor placeholder.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Pipeline Editor</h2>"))
        layout.addWidget(QLabel("Drag-and-drop node graph — coming soon."))
        layout.addStretch()
