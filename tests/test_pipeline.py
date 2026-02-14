"""Integration tests for the Pipeline system."""

from __future__ import annotations

import pytest

from game_toolbox.core.exceptions import PipelineError
from game_toolbox.core.pipeline import Pipeline, PipelineStage


class TestPipelineConstruction:
    """Tests for building pipelines."""

    def test_add_stage_appends(self) -> None:
        """Stages are appended in order."""
        pipeline = Pipeline(name="test")
        pipeline.add_stage("tool_a", params={"x": 1})
        pipeline.add_stage("tool_b")

        assert len(pipeline.stages) == 2
        assert pipeline.stages[0].tool_name == "tool_a"
        assert pipeline.stages[1].tool_name == "tool_b"

    def test_stages_returns_copy(self) -> None:
        """The ``stages`` property returns a copy, not the internal list."""
        pipeline = Pipeline(name="test")
        pipeline.add_stage("tool_a")
        stages = pipeline.stages
        stages.clear()

        assert len(pipeline.stages) == 1

    def test_pipeline_stage_dataclass(self) -> None:
        """``PipelineStage`` stores tool name and params."""
        stage = PipelineStage(tool_name="resizer", params={"width": 256})
        assert stage.tool_name == "resizer"
        assert stage.params == {"width": 256}


class TestPipelineValidation:
    """Tests for pipeline validation."""

    def test_empty_pipeline_raises(self) -> None:
        """Validating an empty pipeline raises ``PipelineError``."""
        pipeline = Pipeline(name="empty")
        with pytest.raises(PipelineError, match="no stages"):
            pipeline.validate()

    def test_non_empty_pipeline_passes(self) -> None:
        """A pipeline with at least one stage passes validation."""
        pipeline = Pipeline(name="ok")
        pipeline.add_stage("some_tool")
        pipeline.validate()


class TestPipelineRun:
    """Tests for pipeline execution."""

    def test_run_empty_pipeline_raises(self) -> None:
        """Running an empty pipeline raises ``PipelineError``."""
        pipeline = Pipeline(name="empty")
        with pytest.raises(PipelineError, match="no stages"):
            pipeline.run()

    def test_run_unknown_tool_raises(self) -> None:
        """Running with an unregistered tool raises ``PipelineError``."""
        from game_toolbox.core.registry import ToolRegistry

        ToolRegistry.reset()
        registry = ToolRegistry()
        registry.discover()

        pipeline = Pipeline(name="bad")
        pipeline.add_stage("nonexistent_tool_xyz")

        with pytest.raises(PipelineError, match="not found"):
            pipeline.run()

        ToolRegistry.reset()
