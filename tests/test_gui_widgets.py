"""Tests for GUI widgets — ParamForm, ProgressPanel, FilePicker, FormatSelector, MultiPathPicker."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.gui.widgets.file_picker import FilePicker
from game_toolbox.gui.widgets.format_selector import FormatSelector
from game_toolbox.gui.widgets.multi_path_picker import MultiPathPicker
from game_toolbox.gui.widgets.param_form import ParamForm
from game_toolbox.gui.widgets.progress_panel import ProgressPanel


class TestParamForm:
    """Tests for auto-generated parameter forms."""

    def test_creates_line_edit_for_str(self, qtbot: object) -> None:
        """String parameters produce a QLineEdit."""
        form = ParamForm([ToolParameter(name="name", label="Name", type=str, default="hello")])
        widget = form._widgets["name"]
        assert isinstance(widget, QLineEdit)
        assert widget.text() == "hello"

    def test_creates_spin_box_for_int(self, qtbot: object) -> None:
        """Integer parameters produce a QSpinBox."""
        form = ParamForm(
            [
                ToolParameter(name="count", label="Count", type=int, default=10, min_value=1, max_value=100),
            ]
        )
        widget = form._widgets["count"]
        assert isinstance(widget, QSpinBox)
        assert widget.value() == 10
        assert widget.minimum() == 1
        assert widget.maximum() == 100

    def test_creates_checkbox_for_bool(self, qtbot: object) -> None:
        """Boolean parameters produce a QCheckBox."""
        form = ParamForm([ToolParameter(name="flag", label="Flag", type=bool, default=True)])
        widget = form._widgets["flag"]
        assert isinstance(widget, QCheckBox)
        assert widget.isChecked() is True

    def test_creates_combo_for_choices(self, qtbot: object) -> None:
        """Parameters with choices produce a QComboBox."""
        form = ParamForm(
            [
                ToolParameter(name="fmt", label="Format", type=str, choices=["png", "webp", "jpg"], default="webp"),
            ]
        )
        widget = form._widgets["fmt"]
        assert isinstance(widget, QComboBox)
        assert widget.currentText() == "webp"

    def test_creates_file_picker_for_path(self, qtbot: object) -> None:
        """Path parameters produce a FilePicker with browse dialog."""
        form = ParamForm([ToolParameter(name="file", label="File", type=Path)])
        widget = form._widgets["file"]
        assert isinstance(widget, FilePicker)
        assert widget._directory is False

    def test_creates_directory_picker_for_path_dir(self, qtbot: object) -> None:
        """Path parameters with 'directory' in help produce a directory FilePicker."""
        form = ParamForm(
            [ToolParameter(name="output_dir", label="Output", type=Path, help="Output directory for files.")]
        )
        widget = form._widgets["output_dir"]
        assert isinstance(widget, FilePicker)
        assert widget._directory is True

    def test_creates_multi_path_picker_for_list(self, qtbot: object) -> None:
        """List parameters produce a MultiPathPicker."""
        form = ParamForm([ToolParameter(name="inputs", label="Inputs", type=list)])
        widget = form._widgets["inputs"]
        assert isinstance(widget, MultiPathPicker)

    def test_get_values_returns_file_picker_path(self, qtbot: object) -> None:
        """get_values returns Path from FilePicker widgets."""
        form = ParamForm([ToolParameter(name="file", label="File", type=Path)])
        widget = form._widgets["file"]
        assert isinstance(widget, FilePicker)
        widget._line_edit.setText("/tmp/test.txt")
        values = form.get_values()
        assert values["file"] == Path("/tmp/test.txt")

    def test_get_values_returns_list_from_multi_path(self, qtbot: object) -> None:
        """get_values returns list of Paths from MultiPathPicker widgets."""
        form = ParamForm([ToolParameter(name="inputs", label="Inputs", type=list)])
        widget = form._widgets["inputs"]
        assert isinstance(widget, MultiPathPicker)
        widget._list.addItem("/tmp/a.png")
        widget._list.addItem("/tmp/b.png")
        values = form.get_values()
        assert values["inputs"] == [Path("/tmp/a.png"), Path("/tmp/b.png")]

    def test_get_values_returns_all_params(self, qtbot: object) -> None:
        """get_values collects current values from all widgets."""
        params = [
            ToolParameter(name="text", label="Text", type=str, default="abc"),
            ToolParameter(name="num", label="Num", type=int, default=5),
            ToolParameter(name="on", label="On", type=bool, default=False),
            ToolParameter(name="choice", label="Choice", type=str, choices=["a", "b"], default="b"),
        ]
        form = ParamForm(params)
        values = form.get_values()
        assert values == {"text": "abc", "num": 5, "on": False, "choice": "b"}

    def test_spin_box_default_max_without_max_value(self, qtbot: object) -> None:
        """Spin box uses 999999 as max when no max_value is set."""
        form = ParamForm([ToolParameter(name="n", label="N", type=int, default=0)])
        widget = form._widgets["n"]
        assert isinstance(widget, QSpinBox)
        assert widget.maximum() == 999_999

    def test_line_edit_tooltip_from_help(self, qtbot: object) -> None:
        """Help text is set as tooltip on QLineEdit."""
        form = ParamForm([ToolParameter(name="x", label="X", type=str, help="some help")])
        widget = form._widgets["x"]
        assert isinstance(widget, QLineEdit)
        assert widget.toolTip() == "some help"


class TestProgressPanel:
    """Tests for the progress bar and status label."""

    def test_initial_state(self, qtbot: object) -> None:
        """Panel starts at 0% with 'Ready.' status."""
        panel = ProgressPanel()
        assert panel._progress_bar.value() == 0
        assert panel._status_label.text() == "Ready."

    def test_set_progress(self, qtbot: object) -> None:
        """set_progress updates the bar value."""
        panel = ProgressPanel()
        panel.set_progress(42)
        assert panel._progress_bar.value() == 42

    def test_set_progress_clamps_high(self, qtbot: object) -> None:
        """Values above 100 are clamped."""
        panel = ProgressPanel()
        panel.set_progress(150)
        assert panel._progress_bar.value() == 100

    def test_set_progress_clamps_low(self, qtbot: object) -> None:
        """Negative values are clamped to 0."""
        panel = ProgressPanel()
        panel.set_progress(-5)
        assert panel._progress_bar.value() == 0

    def test_set_status(self, qtbot: object) -> None:
        """set_status updates the label text."""
        panel = ProgressPanel()
        panel.set_status("Processing...")
        assert panel._status_label.text() == "Processing..."

    def test_reset(self, qtbot: object) -> None:
        """Reset restores initial state."""
        panel = ProgressPanel()
        panel.set_progress(75)
        panel.set_status("Halfway")
        panel.reset()
        assert panel._progress_bar.value() == 0
        assert panel._status_label.text() == "Ready."


class TestFilePicker:
    """Tests for the file picker widget."""

    def test_initial_path_is_none(self, qtbot: object) -> None:
        """Path is None when the line edit is empty."""
        picker = FilePicker()
        assert picker.path is None

    def test_returns_path_when_text_set(self, qtbot: object) -> None:
        """Path is returned when text is entered."""
        picker = FilePicker()
        picker._line_edit.setText("/tmp/test.txt")
        assert picker.path == Path("/tmp/test.txt")

    def test_directory_mode(self, qtbot: object) -> None:
        """Directory mode is stored correctly."""
        picker = FilePicker(directory=True)
        assert picker._directory is True

    def test_custom_placeholder(self, qtbot: object) -> None:
        """Custom placeholder text is applied."""
        picker = FilePicker(label="Pick a video...")
        assert picker._line_edit.placeholderText() == "Pick a video..."


class TestFormatSelector:
    """Tests for the format dropdown widget."""

    def test_initial_selection(self, qtbot: object) -> None:
        """Default format is pre-selected."""
        selector = FormatSelector(["png", "webp", "jpg"], default="webp")
        assert selector.selected_format == "webp"

    def test_first_item_without_default(self, qtbot: object) -> None:
        """First item is selected when no default is given."""
        selector = FormatSelector(["png", "webp", "jpg"])
        assert selector.selected_format == "png"

    def test_invalid_default_falls_back(self, qtbot: object) -> None:
        """Invalid default falls back to first item."""
        selector = FormatSelector(["png", "webp"], default="bmp")
        assert selector.selected_format == "png"


class TestMultiPathPicker:
    """Tests for the multi-path picker widget."""

    def test_initial_paths_empty(self, qtbot: object) -> None:
        """Paths list is empty on creation."""
        picker = MultiPathPicker()
        assert picker.paths == []

    def test_paths_returns_added_items(self, qtbot: object) -> None:
        """Paths property returns all added items."""
        picker = MultiPathPicker()
        picker._list.addItem("/tmp/a.png")
        picker._list.addItem("/tmp/b.png")
        assert picker.paths == [Path("/tmp/a.png"), Path("/tmp/b.png")]

    def test_clear_removes_all(self, qtbot: object) -> None:
        """Clear button removes all entries."""
        picker = MultiPathPicker()
        picker._list.addItem("/tmp/a.png")
        picker._list.addItem("/tmp/b.png")
        picker._on_clear()
        assert picker.paths == []

    def test_no_duplicate_paths(self, qtbot: object) -> None:
        """Duplicate paths are not added."""
        picker = MultiPathPicker()
        picker._list.addItem("/tmp/a.png")
        assert not picker._contains("/tmp/b.png")
        assert picker._contains("/tmp/a.png")
