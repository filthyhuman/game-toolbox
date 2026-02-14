"""FilePicker — composite widget for selecting files or directories."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class FilePicker(QWidget):
    """A line-edit with a browse button for picking files.

    Args:
        label: Placeholder text shown in the line edit.
        directory: If ``True``, open a directory picker instead.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        label: str = "Select file...",
        *,
        directory: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the file picker widget.

        Args:
            label: Placeholder text.
            directory: Pick directories instead of files.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._directory = directory

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText(label)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._line_edit)
        layout.addWidget(self._browse_btn)

    @property
    def path(self) -> Path | None:
        """Return the currently selected path, or ``None`` if empty."""
        text = self._line_edit.text().strip()
        return Path(text) if text else None

    def _on_browse(self) -> None:
        """Open a native file dialog."""
        if self._directory:
            result = QFileDialog.getExistingDirectory(self, "Select directory")
        else:
            result, _ = QFileDialog.getOpenFileName(self, "Select file")
        if result:
            self._line_edit.setText(result)
