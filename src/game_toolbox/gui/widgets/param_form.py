"""ParamForm — auto-generates a form from a tool's parameter schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.gui.widgets.file_picker import FilePicker
from game_toolbox.gui.widgets.multi_path_picker import MultiPathPicker

_NOT_SET = "Not set"


class ParamForm(QWidget):
    """Dynamically generated form based on ``ToolParameter`` definitions.

    Each parameter type maps to an appropriate Qt widget:

    - ``str`` → ``QLineEdit``
    - ``int`` → ``QSpinBox`` (with "Not set" for nullable)
    - ``float`` → ``QDoubleSpinBox`` (with "Not set" for nullable)
    - ``bool`` → ``QCheckBox``
    - ``Path`` → ``FilePicker`` (with browse dialog)
    - ``list`` → ``MultiPathPicker`` (multi-file/folder selection)
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
        self._params: dict[str, ToolParameter] = {}
        form = QFormLayout(self)

        for param in parameters:
            widget = self._create_widget(param)
            self._widgets[param.name] = widget
            self._params[param.name] = param
            form.addRow(param.label, widget)

    def get_values(self) -> dict[str, Any]:
        """Collect current form values as a parameter dictionary.

        Returns:
            Dictionary mapping parameter names to their current values.
        """
        values: dict[str, Any] = {}
        for name, widget in self._widgets.items():
            param = self._params[name]
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                if widget.specialValueText() and widget.value() == widget.minimum():
                    values[name] = None
                else:
                    values[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[name] = widget.currentText()
            elif isinstance(widget, MultiPathPicker):
                values[name] = widget.paths
            elif isinstance(widget, FilePicker):
                values[name] = widget.path
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                if text == "" and param.default is None:
                    values[name] = None
                else:
                    values[name] = text
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
            nullable = param.default is None
            real_min = int(param.min_value) if param.min_value is not None else 0
            if nullable:
                spin.setMinimum(real_min - 1)
                spin.setSpecialValueText(_NOT_SET)
            else:
                spin.setMinimum(real_min)
            if param.max_value is not None:
                spin.setMaximum(int(param.max_value))
            else:
                spin.setMaximum(999_999)
            if nullable:
                spin.setValue(spin.minimum())
            elif param.default is not None:
                spin.setValue(int(param.default))
            return spin

        if param.type is float:
            dspin = QDoubleSpinBox()
            dspin.setDecimals(1)
            nullable = param.default is None
            float_min = float(param.min_value) if param.min_value is not None else 0.0
            if nullable:
                dspin.setMinimum(float_min - 1.0)
                dspin.setSpecialValueText(_NOT_SET)
            else:
                dspin.setMinimum(float_min)
            if param.max_value is not None:
                dspin.setMaximum(float(param.max_value))
            else:
                dspin.setMaximum(999_999.0)
            if nullable:
                dspin.setValue(dspin.minimum())
            elif param.default is not None:
                dspin.setValue(float(param.default))
            return dspin

        if param.type is list:
            multi_picker = MultiPathPicker()
            return multi_picker

        if param.type is Path:
            is_directory = "directory" in param.help.lower() or param.name.endswith("_dir")
            label = param.help if param.help else ("Select directory..." if is_directory else "Select file...")
            file_picker = FilePicker(label=label, directory=is_directory)
            return file_picker

        line = QLineEdit()
        if param.default is not None:
            line.setText(str(param.default))
        if param.help:
            line.setToolTip(param.help)
        return line
