"""BaseTool ABC — the contract every tool in the toolbox implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError


@dataclass
class ToolParameter:
    """Declarative parameter definition — drives auto-generated GUI forms and CLI args."""

    name: str
    label: str
    type: type
    default: Any = None
    choices: list[Any] | None = None
    min_value: float | None = None
    max_value: float | None = None
    help: str = ""


class BaseTool(ABC):
    """Template Method base for every tool in the toolbox.

    Subclasses must override the abstract methods to provide tool-specific
    metadata, parameter definitions, I/O types, and execution logic.
    """

    # ── metadata (override in subclass) ────────────────────────
    name: str
    display_name: str
    description: str
    version: str = "0.1.0"
    category: str = "General"
    icon: str = ""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialise the tool with an optional event bus.

        Args:
            event_bus: Event bus for emitting progress and status events.
                       A default bus is created if none is provided.
        """
        self.event_bus = event_bus or EventBus()

    # ── parameter schema ───────────────────────────────────────
    @abstractmethod
    def define_parameters(self) -> list[ToolParameter]:
        """Return the list of parameters this tool accepts."""
        ...

    # ── I/O port declarations (for pipeline chaining) ─────────
    @abstractmethod
    def input_types(self) -> list[type]:
        """Return data types this tool can receive (empty list = entry point)."""
        ...

    @abstractmethod
    def output_types(self) -> list[type]:
        """Return data types this tool produces (empty list = terminal)."""
        ...

    # ── lifecycle (Template Method skeleton) ───────────────────
    def run(self, params: dict[str, Any], input_data: Any = None) -> Any:
        """Execute the tool — public entry point, do NOT override.

        Args:
            params: Dictionary of parameter values keyed by parameter name.
            input_data: Optional input data from a preceding pipeline stage.

        Returns:
            The result produced by the tool's core logic.
        """
        self.validate(params)
        self._pre_execute(params)
        result = self._do_execute(params, input_data)
        self._post_execute(result)
        return result

    def validate(self, params: dict[str, Any]) -> None:
        """Validate params against ``define_parameters()``.

        Override to add custom validation rules.  The base implementation
        checks that required parameters are present and that values with
        ``choices`` are within the allowed set.

        Args:
            params: Parameter dict to validate.

        Raises:
            ValidationError: If any parameter is invalid.
        """
        for param in self.define_parameters():
            value = params.get(param.name)
            if value is None and param.default is None:
                continue
            if value is not None and param.choices is not None and value not in param.choices:
                msg = f"Parameter '{param.name}' must be one of {param.choices}, got '{value}'"
                raise ValidationError(msg)

    def _pre_execute(self, params: dict[str, Any]) -> None:  # noqa: B027
        """Hook called before execution (optional override).

        Args:
            params: The validated parameter dict.
        """

    @abstractmethod
    def _do_execute(self, params: dict[str, Any], input_data: Any) -> Any:
        """Core logic — MUST override.  Pure computation, no GUI code.

        Args:
            params: Validated parameter dictionary.
            input_data: Optional input from a pipeline stage.

        Returns:
            The tool's result.
        """
        ...

    def _post_execute(self, result: Any) -> None:  # noqa: B027
        """Hook called after execution (optional override).

        Args:
            result: The value returned by ``_do_execute``.
        """
