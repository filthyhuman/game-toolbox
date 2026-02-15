"""Tests for MainWindow, ToolPage, PipelineEditor, and app bootstrap."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from game_toolbox.core.base_tool import BaseTool, ToolParameter
from game_toolbox.core.datatypes import PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.registry import ToolRegistry
from game_toolbox.gui.main_window import MainWindow
from game_toolbox.gui.pipeline_editor import PipelineEditor
from game_toolbox.gui.tool_page import ToolPage, _ToolWorker

# ── Helpers ────────────────────────────────────────────────────────


class _DummyTool(BaseTool):
    """Minimal concrete BaseTool for testing."""

    name = "dummy"
    display_name = "Dummy Tool"
    description = "A test tool"
    category = "Testing"

    def define_parameters(self) -> list[ToolParameter]:
        """Return a simple parameter list."""
        return [
            ToolParameter(name="value", label="Value", type=int, default=42),
        ]

    def input_types(self) -> list[type]:
        """No inputs."""
        return []

    def output_types(self) -> list[type]:
        """Produce PathList."""
        return [PathList]

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> str:
        """Return a simple string result."""
        return f"result-{params.get('value', 0)}"


class _FailingTool(BaseTool):
    """Tool that always raises an exception."""

    name = "failing"
    display_name = "Failing Tool"
    description = "Always fails"
    category = "Testing"

    def define_parameters(self) -> list[ToolParameter]:
        """Return empty parameter list."""
        return []

    def input_types(self) -> list[type]:
        """No inputs."""
        return []

    def output_types(self) -> list[type]:
        """No outputs."""
        return []

    def _do_execute(self, params: dict[str, Any], input_data: Any) -> Any:
        """Raise an error."""
        msg = "intentional failure"
        raise RuntimeError(msg)


# ── PipelineEditor ─────────────────────────────────────────────────


class TestPipelineEditor:
    """Tests for the pipeline editor placeholder."""

    def test_creates_without_error(self, qtbot: object) -> None:
        """PipelineEditor instantiates successfully."""
        editor = PipelineEditor()
        assert editor is not None

    def test_contains_placeholder_text(self, qtbot: object) -> None:
        """PipelineEditor shows the coming-soon label."""
        editor = PipelineEditor()
        labels = [child.text() for child in editor.children() if hasattr(child, "text")]
        assert any("coming soon" in text.lower() for text in labels)


# ── ToolPage ───────────────────────────────────────────────────────


class TestToolPage:
    """Tests for the tool page widget."""

    def test_creates_with_tool(self, qtbot: object) -> None:
        """ToolPage initialises with correct tool reference."""
        tool = _DummyTool()
        page = ToolPage(tool)
        assert page._tool is tool
        assert page._run_btn.isEnabled()

    def test_creates_with_event_bus(self, qtbot: object) -> None:
        """ToolPage stores event bus reference."""
        bus = EventBus()
        tool = _DummyTool(event_bus=bus)
        page = ToolPage(tool, event_bus=bus)
        assert page._event_bus is bus

    def test_param_form_populated(self, qtbot: object) -> None:
        """ToolPage builds a ParamForm from the tool's parameters."""
        tool = _DummyTool()
        page = ToolPage(tool)
        values = page._param_form.get_values()
        assert "value" in values
        assert values["value"] == 42

    def test_on_progress_updates_panel(self, qtbot: object) -> None:
        """Progress slot updates bar and status."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._on_progress(50, 100, "halfway")
        assert page._progress._progress_bar.value() == 50
        assert page._progress._status_label.text() == "halfway"

    def test_on_progress_zero_total(self, qtbot: object) -> None:
        """Progress with zero total does not crash."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._on_progress(0, 0, "")
        assert page._progress._progress_bar.value() == 0

    def test_on_completed_event(self, qtbot: object) -> None:
        """Completed event updates status label."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._on_completed_event("Dummy Tool")
        assert "completed" in page._progress._status_label.text().lower()

    def test_on_error_event_appends_red(self, qtbot: object) -> None:
        """Error event appends colored text to log."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._on_error_event("bad thing")
        assert "ERROR: bad thing" in page._log.toPlainText()

    def test_on_finished_re_enables_button(self, qtbot: object) -> None:
        """Successful finish re-enables the Run button."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._run_btn.setEnabled(False)
        page._on_finished("ok")
        assert page._run_btn.isEnabled()
        assert page._progress._progress_bar.value() == 100
        assert "Done." in page._log.toPlainText()

    def test_on_failed_re_enables_button(self, qtbot: object) -> None:
        """Failed finish re-enables the Run button and shows error."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._run_btn.setEnabled(False)
        page._on_failed("oops")
        assert page._run_btn.isEnabled()
        assert "Error: oops" in page._log.toPlainText()
        assert "Failed" in page._progress._status_label.text()

    def test_append_log(self, qtbot: object) -> None:
        """_append_log adds text to the log area."""
        tool = _DummyTool()
        page = ToolPage(tool)
        page._append_log("line one")
        page._append_log("line two")
        text = page._log.toPlainText()
        assert "line one" in text
        assert "line two" in text

    def test_subscribe_unsubscribe_events(self, qtbot: object) -> None:
        """Subscribe/unsubscribe do not crash with or without event bus."""
        tool = _DummyTool()

        # Without event bus
        page_no_bus = ToolPage(tool, event_bus=None)
        page_no_bus._subscribe_events()
        page_no_bus._unsubscribe_events()

        # With event bus
        bus = EventBus()
        page_bus = ToolPage(tool, event_bus=bus)
        page_bus._subscribe_events()
        assert len(bus._handlers["progress"]) == 1
        page_bus._unsubscribe_events()
        assert len(bus._handlers["progress"]) == 0

    def test_eventbus_bridge_progress(self, qtbot: object) -> None:
        """EventBus progress handler emits bridge signal with correct args."""
        bus = EventBus()
        tool = _DummyTool(event_bus=bus)
        page = ToolPage(tool, event_bus=bus)

        received: list[tuple[int, int, str]] = []
        page._bridge.progress.connect(lambda c, t, m: received.append((c, t, m)))

        page._eb_progress(current=5, total=10, message="half")
        assert received == [(5, 10, "half")]

    def test_eventbus_bridge_completed(self, qtbot: object) -> None:
        """EventBus completed handler emits bridge signal."""
        tool = _DummyTool()
        page = ToolPage(tool)

        received: list[str] = []
        page._bridge.completed.connect(lambda name: received.append(name))

        page._eb_completed(tool="TestTool")
        assert received == ["TestTool"]

    def test_eventbus_bridge_log(self, qtbot: object) -> None:
        """EventBus log handler emits bridge signal."""
        tool = _DummyTool()
        page = ToolPage(tool)

        received: list[str] = []
        page._bridge.log.connect(lambda msg: received.append(msg))

        page._eb_log(message="hello log")
        assert received == ["hello log"]

    def test_eventbus_bridge_error(self, qtbot: object) -> None:
        """EventBus error handler emits bridge signal."""
        tool = _DummyTool()
        page = ToolPage(tool)

        received: list[str] = []
        page._bridge.error.connect(lambda msg: received.append(msg))

        page._eb_error(message="bad")
        assert received == ["bad"]


class TestToolWorker:
    """Tests for the background worker thread."""

    def test_successful_run(self, qtbot: object) -> None:
        """Worker emits finished_ok on success."""
        tool = _DummyTool()
        worker = _ToolWorker(tool, {"value": 7})

        results: list[object] = []
        worker.finished_ok.connect(lambda r: results.append(r))
        worker.start()
        worker.wait()
        QApplication.processEvents()

        assert results == ["result-7"]

    def test_failed_run(self, qtbot: object) -> None:
        """Worker emits failed on exception."""
        tool = _FailingTool()
        worker = _ToolWorker(tool, {})

        errors: list[str] = []
        worker.failed.connect(lambda e: errors.append(e))
        worker.start()
        worker.wait()
        QApplication.processEvents()

        assert len(errors) == 1
        assert "intentional failure" in errors[0]


# ── MainWindow ─────────────────────────────────────────────────────


class TestMainWindow:
    """Tests for the main application window."""

    def test_creates_without_registry(self, qtbot: object) -> None:
        """MainWindow works with no registry."""
        window = MainWindow()
        assert window._sidebar.count() == 0
        assert window._stack.count() == 0

    def test_populates_sidebar_from_registry(self, qtbot: object) -> None:
        """MainWindow populates sidebar with tool entries and headers."""
        registry = ToolRegistry()
        ToolRegistry._instance = registry
        registry._tools = {"dummy": _DummyTool()}

        try:
            window = MainWindow(registry=registry)
            # Should have: "Testing" header + "  Dummy Tool" + "Pipelines" header + "  Pipeline Editor"
            assert window._sidebar.count() == 4
            # Stack should have: DummyTool page + PipelineEditor
            assert window._stack.count() == 2
        finally:
            ToolRegistry.reset()

    def test_sidebar_selection_switches_stack(self, qtbot: object) -> None:
        """Clicking a tool in the sidebar switches the stacked widget."""
        registry = ToolRegistry()
        ToolRegistry._instance = registry
        registry._tools = {"dummy": _DummyTool()}

        try:
            window = MainWindow(registry=registry)
            # Item at index 1 is "  Dummy Tool" (index 0 is the header)
            tool_item = window._sidebar.item(1)
            window._sidebar.setCurrentItem(tool_item)
            assert window._stack.currentIndex() == 0
        finally:
            ToolRegistry.reset()

    def test_header_items_not_selectable(self, qtbot: object) -> None:
        """Category headers have no item flags."""
        registry = ToolRegistry()
        ToolRegistry._instance = registry
        registry._tools = {"dummy": _DummyTool()}

        try:
            window = MainWindow(registry=registry)
            header_item = window._sidebar.item(0)
            assert header_item.flags() == Qt.ItemFlag.NoItemFlags
        finally:
            ToolRegistry.reset()

    def test_sidebar_changed_with_none(self, qtbot: object) -> None:
        """_on_sidebar_changed handles None gracefully."""
        window = MainWindow()
        # Should not raise
        window._on_sidebar_changed(None, None)

    def test_status_bar_on_completed(self, qtbot: object) -> None:
        """EventBus completed event shows status-bar message."""
        bus = EventBus()
        window = MainWindow(event_bus=bus)
        bus.emit("completed", tool="Test Tool")
        assert "Test Tool completed" in window._status_bar.currentMessage()

    def test_pipeline_editor_in_sidebar(self, qtbot: object) -> None:
        """Pipeline Editor appears in sidebar even without tools."""
        registry = ToolRegistry()
        ToolRegistry._instance = registry
        registry._tools = {"dummy": _DummyTool()}

        try:
            window = MainWindow(registry=registry)
            items = [window._sidebar.item(i).text() for i in range(window._sidebar.count())]
            assert any("Pipeline Editor" in item for item in items)
        finally:
            ToolRegistry.reset()


# ── app.main ───────────────────────────────────────────────────────


class TestAppMain:
    """Tests for the app bootstrap function."""

    def test_main_creates_and_shows_window(self, qtbot: object) -> None:
        """main() creates a MainWindow and calls show()."""
        from game_toolbox.gui import app

        shown: list[bool] = []

        with (
            patch.object(app, "QApplication", return_value=QApplication.instance()),
            patch.object(app, "ToolRegistry") as mock_registry_cls,
            patch.object(app, "MainWindow") as mock_window_cls,
            patch.object(app, "sys") as mock_sys,
        ):
            mock_registry_cls.return_value = mock_registry_cls
            mock_window_cls.return_value = mock_window_cls
            mock_window_cls.show = lambda: shown.append(True)
            mock_sys.argv = []
            # Prevent sys.exit from actually exiting
            mock_sys.exit = lambda code: None
            mock_app = QApplication.instance()
            assert mock_app is not None
            # Monkey-patch exec to return immediately
            original_exec = mock_app.exec
            mock_app.exec = lambda: 0  # type: ignore[assignment]

            try:
                app.main()
            finally:
                mock_app.exec = original_exec  # type: ignore[assignment]

            mock_registry_cls.discover.assert_called_once()
            assert shown == [True]
