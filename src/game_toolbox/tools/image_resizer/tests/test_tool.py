"""Tests for ImageResizerTool (BaseTool integration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import PathList, ResizeResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.image_resizer.tool import ImageResizerTool

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> ImageResizerTool:
    """Return a fresh ImageResizerTool instance."""
    return ImageResizerTool()


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """Create a 100x80 RGB test image."""
    img_path = tmp_path / "sample.png"
    img = Image.new("RGB", (100, 80), color=(255, 0, 0))
    img.save(str(img_path))
    return img_path


# ── Metadata & Parameters ─────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: ImageResizerTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "image_resizer"
        assert tool.category == "Image"
        assert tool.display_name == "Image Resizer"

    def test_define_parameters_returns_list(self, tool: ImageResizerTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 6
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: ImageResizerTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_pathlist(self, tool: ImageResizerTool) -> None:
        """Image resizer accepts ``PathList`` from a pipeline."""
        assert PathList in tool.input_types()

    def test_output_types_contain_pathlist(self, tool: ImageResizerTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()


# ── Validation ─────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``run()``."""

    def test_rejects_invalid_mode(self, tool: ImageResizerTool) -> None:
        """Validation raises when mode is not in allowed choices."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.run(params={"mode": "zoom", "inputs": []})

    def test_rejects_exact_without_dimensions(self, tool: ImageResizerTool) -> None:
        """Validation raises when exact mode lacks width/height."""
        with pytest.raises(ValidationError, match="requires both"):
            tool.validate({"mode": "exact", "width": None, "height": None})

    def test_rejects_percent_without_value(self, tool: ImageResizerTool) -> None:
        """Validation raises when percent mode lacks percent value."""
        with pytest.raises(ValidationError, match="requires 'percent'"):
            tool.validate({"mode": "percent", "percent": None})

    def test_accepts_valid_exact_params(self, tool: ImageResizerTool) -> None:
        """Validation passes for valid exact mode parameters."""
        tool.validate({"mode": "exact", "width": 100, "height": 100, "resample": "lanczos"})

    def test_accepts_valid_percent_params(self, tool: ImageResizerTool) -> None:
        """Validation passes for valid percent mode parameters."""
        tool.validate({"mode": "percent", "percent": 50.0, "resample": "lanczos"})


# ── Execution ──────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_run_returns_resize_result(self, tool: ImageResizerTool, sample_image: Path, tmp_path: Path) -> None:
        """Happy path: ``run()`` returns a ``ResizeResult``."""
        out_dir = tmp_path / "out"

        result = tool.run(
            params={
                "inputs": [sample_image],
                "output_dir": out_dir,
                "mode": "exact",
                "width": 32,
                "height": 32,
                "percent": None,
                "resample": "lanczos",
                "in_place": False,
            },
        )

        assert isinstance(result, ResizeResult)
        assert result.count == 1
        assert result.images[0].width == 32

    def test_run_with_pipeline_input(self, tmp_path: Path) -> None:
        """Tool accepts ``PathList`` as pipeline input data."""
        img_path = tmp_path / "pipe.png"
        Image.new("RGB", (60, 40)).save(str(img_path))
        out_dir = tmp_path / "pipe_out"

        tool = ImageResizerTool()
        result = tool.run(
            params={
                "inputs": [],
                "output_dir": out_dir,
                "mode": "percent",
                "width": None,
                "height": None,
                "percent": 200,
                "resample": "lanczos",
                "in_place": False,
            },
            input_data=PathList(paths=(img_path,)),
        )

        assert result.count == 1
        assert result.images[0].width == 120
        assert result.images[0].height == 80

    def test_run_uses_event_bus(self, sample_image: Path, tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = ImageResizerTool(event_bus=bus)
        tool.run(
            params={
                "inputs": [sample_image],
                "output_dir": tmp_path / "out",
                "mode": "exact",
                "width": 16,
                "height": 16,
                "percent": None,
                "resample": "nearest",
                "in_place": False,
            },
        )

        assert len(events) == 1
        assert events[0]["tool"] == "image_resizer"

    def test_run_default_output_dir(self, sample_image: Path) -> None:
        """When output_dir is None and not in-place, uses 'resized/' next to input."""
        tool = ImageResizerTool()
        result = tool.run(
            params={
                "inputs": [sample_image],
                "output_dir": None,
                "mode": "exact",
                "width": 10,
                "height": 10,
                "percent": None,
                "resample": "lanczos",
                "in_place": False,
            },
        )

        assert result.count == 1
        assert result.images[0].path.parent.name == "resized"
