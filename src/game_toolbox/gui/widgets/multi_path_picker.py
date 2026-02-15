"""MultiPathPicker — composite widget for selecting multiple files or directories."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MultiPathPicker(QWidget):
    """A list widget with browse buttons for picking multiple files and directories.

    Provides "Add Files..." and "Add Folder..." buttons that open native dialogs,
    and a "Clear" button to remove all entries.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the multi-path picker widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setMaximumHeight(100)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._add_files_btn = QPushButton("Add Files...")
        self._add_files_btn.clicked.connect(self._on_add_files)
        btn_row.addWidget(self._add_files_btn)

        self._add_folder_btn = QPushButton("Add Folder...")
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        btn_row.addWidget(self._add_folder_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self._clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    @property
    def paths(self) -> list[Path]:
        """Return all selected paths."""
        result: list[Path] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is not None:
                result.append(Path(item.text()))
        return result

    def _on_add_files(self) -> None:
        """Open a native file dialog for selecting multiple files."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select files")
        for f in files:
            if f and not self._contains(f):
                self._list.addItem(f)

    def _on_add_folder(self) -> None:
        """Open a native directory dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select directory")
        if folder and not self._contains(folder):
            self._list.addItem(folder)

    def _on_clear(self) -> None:
        """Remove all entries from the list."""
        self._list.clear()

    def _contains(self, path: str) -> bool:
        """Check if a path is already in the list.

        Args:
            path: The path string to check.

        Returns:
            True if the path is already listed.
        """
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is not None and item.text() == path:
                return True
        return False
