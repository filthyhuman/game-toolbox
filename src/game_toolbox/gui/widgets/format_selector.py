"""FormatSelector — dropdown widget for choosing an output format."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget


class FormatSelector(QWidget):
    """A labelled combo box for selecting from a list of format choices.

    Args:
        formats: List of format strings (e.g. ``["png", "webp", "jpg"]``).
        default: The format pre-selected on creation.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        formats: list[str],
        default: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the format selector.

        Args:
            formats: Available format choices.
            default: Initially selected format.
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._combo = QComboBox()
        self._combo.addItems(formats)
        if default and default in formats:
            self._combo.setCurrentText(default)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Format:"))
        layout.addWidget(self._combo)

    @property
    def selected_format(self) -> str:
        """Return the currently selected format string."""
        return self._combo.currentText()
