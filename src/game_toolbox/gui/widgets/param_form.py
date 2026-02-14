"""ParamForm — auto-generates a form from a tool's parameter schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from game_toolbox.core.base_tool import ToolParameter


class ParamForm(QWidget):
    """Dynamically generated form based on ``ToolParameter`` definitions.

    Each parameter type maps to an appropriate Qt widget:

    - ``str`` → ``QLineEdit``
    - ``int`` → ``QSpinBox``
    - ``bool`` → ``QCheckBox``
    - ``Path`` → ``QLineEdit`` (with placeholder)
    - choices → ``QComboBox``

    Args:
        parameters: The tool's parameter schema.
        parent: Optional parent widget.
    """

    def __init__(self, parameters: list[ToolParameter], parent: QWidget | None = None) -> None:
        """Initialise the auto-generated parameter form.

        Args:
            parameters: List of ``ToolParameter`` definitions.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._widgets: dict[str, QWidget] = {}
        form = QFormLayout(self)

        for param in parameters:
            widget = self._create_widget(param)
            self._widgets[param.name] = widget
            form.addRow(param.label, widget)

    def get_values(self) -> dict[str, Any]:
        """Collect current form values as a parameter dictionary.

        Returns:
            Dictionary mapping parameter names to their current values.
        """
        values: dict[str, Any] = {}
        for name, widget in self._widgets.items():
            if isinstance(widget, QSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                values[name] = widget.text()
        return values

    @staticmethod
    def _create_widget(param: ToolParameter) -> QWidget:
        """Create the appropriate Qt widget for a parameter.

        Args:
            param: The parameter definition.

        Returns:
            A configured Qt widget.
        """
        if param.choices:
            combo = QComboBox()
            combo.addItems([str(c) for c in param.choices])
            if param.default is not None:
                combo.setCurrentText(str(param.default))
            return combo

        if param.type is bool:
            checkbox = QCheckBox()
            if param.default is not None:
                checkbox.setChecked(bool(param.default))
            return checkbox

        if param.type is int:
            spin = QSpinBox()
            if param.min_value is not None:
                spin.setMinimum(int(param.min_value))
            if param.max_value is not None:
                spin.setMaximum(int(param.max_value))
            else:
                spin.setMaximum(999_999)
            if param.default is not None:
                spin.setValue(int(param.default))
            return spin

        line = QLineEdit()
        if param.default is not None:
            line.setText(str(param.default))
        if param.type is Path:
            line.setPlaceholderText("Enter path...")
        if param.help:
            line.setToolTip(param.help)
        return line
