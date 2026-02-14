"""Tests for ChromaKeyTool (BaseTool integration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import ChromaKeyResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.chroma_key.logic import COLOR_PRESETS
from game_toolbox.tools.chroma_key.tool import ChromaKeyTool

# Pillow's getpixel() returns a broad union; cast for mypy.
_Pixel = tuple[int, ...]


def _px(img: Image.Image, xy: tuple[int, int]) -> _Pixel:
    """Return the pixel value at *xy* as a typed tuple."""
    val = img.getpixel(xy)
    assert isinstance(val, tuple)
    return val


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> ChromaKeyTool:
    """Return a fresh ChromaKeyTool instance."""
    return ChromaKeyTool()


@pytest.fixture()
def green_bg_image(tmp_path: Path) -> Path:
    """Create a 100x100 image with green background and red centre."""
    img = Image.new("RGB", (100, 100), color=COLOR_PRESETS["green"])
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0))
    img_path = tmp_path / "green_bg.png"
    img.save(str(img_path))
    return img_path


# ── Metadata & Parameters ─────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: ChromaKeyTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "chroma_key"
        assert tool.category == "Image"
        assert tool.display_name == "Chroma Key"

    def test_define_parameters_returns_list(self, tool: ChromaKeyTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 6
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: ChromaKeyTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_pathlist(self, tool: ChromaKeyTool) -> None:
        """Chroma key accepts ``PathList`` from a pipeline."""
        assert PathList in tool.input_types()

    def test_output_types_contain_pathlist(self, tool: ChromaKeyTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()


# ── Validation ─────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``run()``."""

    def test_rejects_invalid_preset(self, tool: ChromaKeyTool) -> None:
        """Validation raises when preset is not in allowed choices."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.run(params={"preset": "red", "inputs": []})

    def test_rejects_invalid_colour_string(self, tool: ChromaKeyTool) -> None:
        """Validation raises for malformed colour string."""
        with pytest.raises(ValidationError, match="3 comma-separated"):
            tool.validate({"color": "0,177"})

    def test_rejects_out_of_range_colour(self, tool: ChromaKeyTool) -> None:
        """Validation raises when colour values are out of 0-255."""
        with pytest.raises(ValidationError, match="0-255"):
            tool.validate({"color": "300,0,0"})

    def test_accepts_valid_params(self, tool: ChromaKeyTool) -> None:
        """Validation passes for valid parameters."""
        tool.validate({"preset": "green", "tolerance": 30.0, "output_format": "png"})

    def test_accepts_custom_colour(self, tool: ChromaKeyTool) -> None:
        """Validation passes for a valid custom colour string."""
        tool.validate({"color": "128,128,0"})


# ── Execution ──────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_run_returns_chroma_key_result(self, tool: ChromaKeyTool, green_bg_image: Path, tmp_path: Path) -> None:
        """Happy path: ``run()`` returns a ``ChromaKeyResult``."""
        out_dir = tmp_path / "out"

        result = tool.run(
            params={
                "inputs": [green_bg_image],
                "output_dir": out_dir,
                "preset": "green",
                "color": None,
                "tolerance": 30.0,
                "softness": 10.0,
                "output_format": "png",
                "in_place": False,
            },
        )

        assert isinstance(result, ChromaKeyResult)
        assert result.count == 1
        # Verify the green background was removed.
        keyed_img = Image.open(result.images[0].path)
        assert _px(keyed_img, (0, 0))[3] == 0
        assert _px(keyed_img, (50, 50))[3] == 255

    def test_run_with_pipeline_input(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Tool accepts ``PathList`` as pipeline input data."""
        out_dir = tmp_path / "pipe_out"

        tool = ChromaKeyTool()
        result = tool.run(
            params={
                "inputs": [],
                "output_dir": out_dir,
                "preset": "green",
                "color": None,
                "tolerance": 30.0,
                "softness": 10.0,
                "output_format": "png",
                "in_place": False,
            },
            input_data=PathList(paths=(green_bg_image,)),
        )

        assert result.count == 1

    def test_run_with_custom_colour(self, tmp_path: Path) -> None:
        """Custom colour string overrides preset."""
        custom = (128, 64, 32)
        img = Image.new("RGB", (40, 40), color=custom)
        src = tmp_path / "custom.png"
        img.save(str(src))
        out_dir = tmp_path / "out"

        tool = ChromaKeyTool()
        result = tool.run(
            params={
                "inputs": [src],
                "output_dir": out_dir,
                "preset": "green",
                "color": "128,64,32",
                "tolerance": 30.0,
                "softness": 10.0,
                "output_format": "png",
                "in_place": False,
            },
        )

        assert result.count == 1
        keyed_img = Image.open(result.images[0].path)
        assert _px(keyed_img, (20, 20))[3] == 0

    def test_run_uses_event_bus(self, green_bg_image: Path, tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = ChromaKeyTool(event_bus=bus)
        tool.run(
            params={
                "inputs": [green_bg_image],
                "output_dir": tmp_path / "out",
                "preset": "green",
                "color": None,
                "tolerance": 30.0,
                "softness": 10.0,
                "output_format": "png",
                "in_place": False,
            },
        )

        assert len(events) == 1
        assert events[0]["tool"] == "chroma_key"

    def test_run_default_output_dir(self, green_bg_image: Path) -> None:
        """When output_dir is None and not in-place, uses 'keyed/' next to input."""
        tool = ChromaKeyTool()
        result = tool.run(
            params={
                "inputs": [green_bg_image],
                "output_dir": None,
                "preset": "green",
                "color": None,
                "tolerance": 30.0,
                "softness": 10.0,
                "output_format": "png",
                "in_place": False,
            },
        )

        assert result.count == 1
        assert result.images[0].path.parent.name == "keyed"
