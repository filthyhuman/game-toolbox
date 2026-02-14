"""ProgressPanel — widget for displaying tool execution progress."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressPanel(QWidget):
    """Displays a progress bar and status message during tool execution.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the progress panel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

        self._status_label = QLabel("Ready.")

        layout = QVBoxLayout(self)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._status_label)

    def set_progress(self, value: int) -> None:
        """Update the progress bar value.

        Args:
            value: Progress percentage (0-100).
        """
        self._progress_bar.setValue(min(100, max(0, value)))

    def set_status(self, message: str) -> None:
        """Update the status label text.

        Args:
            message: Status message to display.
        """
        self._status_label.setText(message)

    def reset(self) -> None:
        """Reset the panel to its initial state."""
        self._progress_bar.setValue(0)
        self._status_label.setText("Ready.")
