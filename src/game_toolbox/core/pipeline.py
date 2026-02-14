"""Pipeline & PipelineStage — chains tools via input/output ports."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from game_toolbox.core.exceptions import PipelineError

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """A single stage in a pipeline, binding a tool name to its parameters.

    Attributes:
        tool_name: Registry slug of the tool to execute.
        params: Parameter dictionary passed to ``tool.run()``.
    """

    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Composite of ``PipelineStage`` objects executed in sequence.

    Data flows through the chain: the output of stage *N* becomes the
    ``input_data`` of stage *N+1*.  Port compatibility is validated at
    build time via ``validate()``.

    Args:
        name: Human-readable pipeline name.
    """

    def __init__(self, name: str) -> None:
        """Initialise an empty pipeline.

        Args:
            name: A descriptive name for this pipeline.
        """
        self.name = name
        self._stages: list[PipelineStage] = []

    @property
    def stages(self) -> list[PipelineStage]:
        """Return the ordered list of pipeline stages."""
        return list(self._stages)

    def add_stage(self, tool_name: str, params: dict[str, Any] | None = None) -> None:
        """Append a stage to the pipeline.

        Args:
            tool_name: Registry slug of the tool (e.g. ``"frame_extractor"``).
            params: Parameters forwarded to the tool's ``run()`` method.
        """
        self._stages.append(PipelineStage(tool_name=tool_name, params=params or {}))

    def validate(self) -> None:
        """Check that the pipeline has at least one stage.

        Raises:
            PipelineError: If the pipeline is empty.
        """
        if not self._stages:
            msg = f"Pipeline '{self.name}' has no stages"
            raise PipelineError(msg)

    def run(self, input_data: Any = None) -> Any:
        """Execute all stages in order, threading data through the chain.

        Args:
            input_data: Initial data fed into the first stage.

        Returns:
            The result produced by the last stage.

        Raises:
            PipelineError: If the pipeline is empty or a tool is not found.
        """
        from game_toolbox.core.registry import ToolRegistry

        self.validate()
        registry = ToolRegistry()
        result = input_data

        for stage in self._stages:
            tool = registry.get(stage.tool_name)
            if tool is None:
                msg = f"Tool '{stage.tool_name}' not found in registry"
                raise PipelineError(msg)
            logger.info("Pipeline '%s': running stage '%s'", self.name, stage.tool_name)
            result = tool.run(params=stage.params, input_data=result)

        return result
