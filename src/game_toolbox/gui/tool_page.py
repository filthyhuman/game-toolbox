"""ToolPage — widget that wraps a tool's parameter form, run button, and progress."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from game_toolbox.gui.widgets.param_form import ParamForm
from game_toolbox.gui.widgets.progress_panel import ProgressPanel

if TYPE_CHECKING:
    from game_toolbox.core.base_tool import BaseTool
    from game_toolbox.core.events import EventBus

logger = logging.getLogger(__name__)


class _BridgeSignals(QObject):
    """Thread-safe bridge from EventBus callbacks to Qt signals."""

    progress = Signal(int, int, str)  # current, total, message
    completed = Signal(str)  # tool name
    error = Signal(str)  # error message
    log = Signal(str)  # log line


class _ToolWorker(QThread):
    """Background worker that runs a tool's ``run()`` method.

    Signals:
        finished_ok: Emitted with the result on success.
        failed: Emitted with the error message on failure.
    """

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, tool: BaseTool, params: dict[str, Any], parent: QObject | None = None) -> None:
        """Initialise the worker.

        Args:
            tool: The tool to execute.
            params: Parameter dictionary for the tool.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tool = tool
        self._params = params

    def run(self) -> None:
        """Execute the tool and emit the appropriate signal."""
        try:
            result = self._tool.run(self._params)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ToolPage(QWidget):
    """Adapter widget that presents a ``BaseTool`` in the GUI.

    Renders an auto-generated parameter form, a run button, a progress panel,
    and a read-only log area.  Tool execution happens in a ``QThread``.

    Args:
        tool: The ``BaseTool`` instance to display.
        event_bus: Shared event bus for progress / status events.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        tool: BaseTool,
        event_bus: EventBus | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the tool page.

        Args:
            tool: The tool whose parameters are rendered.
            event_bus: Shared event bus for receiving progress events.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._tool = tool
        self._event_bus = event_bus
        self._worker: _ToolWorker | None = None

        # ── Bridge signals (thread-safe EventBus → Qt) ────────
        self._bridge = _BridgeSignals(self)
        self._bridge.progress.connect(self._on_progress)
        self._bridge.completed.connect(self._on_completed_event)
        self._bridge.log.connect(self._append_log)
        self._bridge.error.connect(self._on_error_event)

        # ── Layout ─────────────────────────────────────────────
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<h2>{tool.display_name}</h2>"))
        layout.addWidget(QLabel(tool.description))

        self._param_form = ParamForm(tool.define_parameters())
        layout.addWidget(self._param_form)

        # Run button row
        button_row = QHBoxLayout()
        self._run_btn = QPushButton("Run")
        self._run_btn.setFixedWidth(120)
        self._run_btn.clicked.connect(self._on_run)
        button_row.addWidget(self._run_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        # Progress panel
        self._progress = ProgressPanel()
        layout.addWidget(self._progress)

        # Log area
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        log_font = QFont("Menlo, Consolas, monospace")
        log_font.setStyleHint(QFont.StyleHint.Monospace)
        self._log.setFont(log_font)
        self._log.setMaximumHeight(200)
        layout.addWidget(self._log)

        layout.addStretch()

    # ── EventBus handlers (called from worker thread) ──────────

    def _eb_progress(self, **kwargs: Any) -> None:
        """EventBus progress handler — emits Qt signal."""
        current = int(kwargs.get("current", 0))
        total = int(kwargs.get("total", 100))
        message = str(kwargs.get("message", ""))
        self._bridge.progress.emit(current, total, message)

    def _eb_completed(self, **kwargs: Any) -> None:
        """EventBus completed handler — emits Qt signal."""
        tool_name = str(kwargs.get("tool", self._tool.display_name))
        self._bridge.completed.emit(tool_name)

    def _eb_log(self, **kwargs: Any) -> None:
        """EventBus log handler — emits Qt signal."""
        message = str(kwargs.get("message", ""))
        self._bridge.log.emit(message)

    def _eb_error(self, **kwargs: Any) -> None:
        """EventBus error handler — emits Qt signal."""
        message = str(kwargs.get("message", ""))
        self._bridge.error.emit(message)

    def _subscribe_events(self) -> None:
        """Subscribe EventBus handlers before running a tool."""
        if self._event_bus is None:
            return
        self._event_bus.subscribe("progress", self._eb_progress)
        self._event_bus.subscribe("completed", self._eb_completed)
        self._event_bus.subscribe("log", self._eb_log)
        self._event_bus.subscribe("error", self._eb_error)

    def _unsubscribe_events(self) -> None:
        """Unsubscribe EventBus handlers after a tool finishes."""
        if self._event_bus is None:
            return
        self._event_bus.unsubscribe("progress", self._eb_progress)
        self._event_bus.unsubscribe("completed", self._eb_completed)
        self._event_bus.unsubscribe("log", self._eb_log)
        self._event_bus.unsubscribe("error", self._eb_error)

    # ── Qt slots (main thread) ─────────────────────────────────

    @Slot()
    def _on_run(self) -> None:
        """Handle Run button click — start tool execution in a worker thread."""
        params = self._param_form.get_values()
        self._run_btn.setEnabled(False)
        self._progress.reset()
        self._log.clear()

        self._subscribe_events()

        self._worker = _ToolWorker(self._tool, params, parent=self)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, message: str) -> None:
        """Update progress panel from a progress event."""
        if total > 0:
            pct = int(current / total * 100)
            self._progress.set_progress(pct)
        if message:
            self._progress.set_status(message)
            self._append_log(message)

    @Slot(str)
    def _on_completed_event(self, tool_name: str) -> None:
        """Handle a completed event from EventBus."""
        self._progress.set_status(f"{tool_name} completed.")

    @Slot(str)
    def _on_error_event(self, message: str) -> None:
        """Handle an error event from EventBus."""
        self._append_log_colored(f"ERROR: {message}", QColor("red"))

    @Slot(str)
    def _append_log(self, text: str) -> None:
        """Append a line to the log area."""
        self._log.append(text)

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        """Handle successful tool completion."""
        self._unsubscribe_events()
        self._run_btn.setEnabled(True)
        self._progress.set_progress(100)
        self._progress.set_status("Completed.")
        self._append_log(f"Done. Result: {result}")

    @Slot(str)
    def _on_failed(self, error_msg: str) -> None:
        """Handle tool execution failure."""
        self._unsubscribe_events()
        self._run_btn.setEnabled(True)
        self._progress.set_status("Failed.")
        self._append_log_colored(f"Error: {error_msg}", QColor("red"))

    # ── Helpers ─────────────────────────────────────────────────

    def _append_log_colored(self, text: str, color: QColor) -> None:
        """Append a colored line to the log area.

        Args:
            text: The text to append.
            color: The text color.
        """
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor = self._log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        self._log.setTextCursor(cursor)
