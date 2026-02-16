"""Tests for AnimationCropperTool (BaseTool integration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import CropResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.animation_cropper.tool import AnimationCropperTool

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> AnimationCropperTool:
    """Return a fresh AnimationCropperTool instance."""
    return AnimationCropperTool()


@pytest.fixture()
def sample_frame(tmp_path: Path) -> Path:
    """Create a 100x100 RGBA image with content in a 40x40 central region."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0, 255))
    path = tmp_path / "frame.png"
    img.save(str(path))
    return path


@pytest.fixture()
def frame_dir(tmp_path: Path) -> Path:
    """Create a directory with multiple RGBA test frames."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for i in range(3):
        img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        for x in range(10 + i * 5, 40 + i * 5):
            for y in range(10, 50):
                img.putpixel((x, y), (0, 255, 0, 255))
        img.save(str(frames_dir / f"frame_{i:03d}.png"))
    return frames_dir


# ── Metadata & Parameters ─────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: AnimationCropperTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "animation_cropper"
        assert tool.category == "Image"
        assert tool.display_name == "Animation Cropper"

    def test_define_parameters_returns_list(self, tool: AnimationCropperTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 4
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: AnimationCropperTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_pathlist(self, tool: AnimationCropperTool) -> None:
        """Animation cropper accepts ``PathList`` from a pipeline."""
        assert PathList in tool.input_types()

    def test_output_types_contain_pathlist(self, tool: AnimationCropperTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()

    def test_width_has_min_value(self, tool: AnimationCropperTool) -> None:
        """Width parameter has min_value of 1."""
        params_by_name = {p.name: p for p in tool.define_parameters()}
        assert params_by_name["width"].min_value == 1

    def test_output_format_choices(self, tool: AnimationCropperTool) -> None:
        """Output format parameter has png and webp as choices."""
        params_by_name = {p.name: p for p in tool.define_parameters()}
        assert params_by_name["output_format"].choices == ["png", "webp"]


# ── Validation ─────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``run()``."""

    def test_rejects_width_without_height(self, tool: AnimationCropperTool) -> None:
        """Validation raises when width is given but height is not."""
        with pytest.raises(ValidationError, match="both"):
            tool.validate({"width": 100, "height": None})

    def test_rejects_height_without_width(self, tool: AnimationCropperTool) -> None:
        """Validation raises when height is given but width is not."""
        with pytest.raises(ValidationError, match="both"):
            tool.validate({"width": None, "height": 100})

    def test_accepts_both_none(self, tool: AnimationCropperTool) -> None:
        """Validation passes when both width and height are omitted."""
        tool.validate({"width": None, "height": None})

    def test_accepts_both_provided(self, tool: AnimationCropperTool) -> None:
        """Validation passes when both width and height are provided."""
        tool.validate({"width": 64, "height": 64, "output_format": "png"})

    def test_rejects_invalid_format(self, tool: AnimationCropperTool) -> None:
        """Validation raises when output_format is not in choices."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.validate({"width": 64, "height": 64, "output_format": "gif"})


# ── Execution ──────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_analyze_only(self, tool: AnimationCropperTool, sample_frame: Path) -> None:
        """When no dimensions given, returns analyse-only CropResult."""
        result = tool.run(
            params={
                "inputs": [sample_frame],
                "output_dir": None,
                "width": None,
                "height": None,
                "output_format": "png",
            },
        )

        assert isinstance(result, CropResult)
        assert result.count == 0
        assert result.suggested_width > 0

    def test_full_crop(self, tool: AnimationCropperTool, sample_frame: Path, tmp_path: Path) -> None:
        """Full crop run returns a CropResult with images."""
        out_dir = tmp_path / "out"
        result = tool.run(
            params={
                "inputs": [sample_frame],
                "output_dir": out_dir,
                "width": 64,
                "height": 64,
                "output_format": "png",
            },
        )

        assert isinstance(result, CropResult)
        assert result.count == 1
        assert result.images[0].width == 64
        assert result.images[0].height == 64

    def test_pipeline_input(self, tmp_path: Path) -> None:
        """Tool accepts ``PathList`` as pipeline input data."""
        img = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
        frame_path = tmp_path / "pipe_frame.png"
        img.save(str(frame_path))
        out_dir = tmp_path / "pipe_out"

        tool = AnimationCropperTool()
        result = tool.run(
            params={
                "inputs": [],
                "output_dir": out_dir,
                "width": 32,
                "height": 32,
                "output_format": "png",
            },
            input_data=PathList(paths=(frame_path,)),
        )

        assert result.count == 1
        assert result.images[0].width == 32

    def test_event_bus_receives_events(self, sample_frame: Path, tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = AnimationCropperTool(event_bus=bus)
        tool.run(
            params={
                "inputs": [sample_frame],
                "output_dir": tmp_path / "out",
                "width": 32,
                "height": 32,
                "output_format": "png",
            },
        )

        assert len(events) >= 1
        assert events[0]["tool"] == "animation_cropper"

    def test_default_output_dir(self, sample_frame: Path) -> None:
        """When output_dir is None, uses 'cropped/' next to first input."""
        tool = AnimationCropperTool()
        result = tool.run(
            params={
                "inputs": [sample_frame],
                "output_dir": None,
                "width": 32,
                "height": 32,
                "output_format": "png",
            },
        )

        assert result.count == 1
        assert result.images[0].path.parent.name == "cropped"

    def test_crop_with_directory_input(self, tool: AnimationCropperTool, frame_dir: Path, tmp_path: Path) -> None:
        """Tool handles directory inputs correctly."""
        out_dir = tmp_path / "dir_out"
        result = tool.run(
            params={
                "inputs": [frame_dir],
                "output_dir": out_dir,
                "width": 64,
                "height": 64,
                "output_format": "png",
            },
        )

        assert result.count == 3
