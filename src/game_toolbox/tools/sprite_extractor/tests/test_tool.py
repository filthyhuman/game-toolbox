"""Tests for SpriteExtractorTool (BaseTool integration)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import ImageData, PathList, SpriteExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.sprite_extractor.tool import SpriteExtractorTool

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> SpriteExtractorTool:
    """Return a fresh SpriteExtractorTool instance."""
    return SpriteExtractorTool()


@pytest.fixture()
def grid_sheet(tmp_path: Path) -> Path:
    """Create a 64x64 sprite sheet with a 2x2 grid of 32x32 cells."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    colours = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    for i, colour in enumerate(colours):
        tile = Image.new("RGBA", (32, 32), colour)
        img.paste(tile, ((i % 2) * 32, (i // 2) * 32))
    path = tmp_path / "sheet.png"
    img.save(str(path))
    return path


@pytest.fixture()
def auto_sheet(tmp_path: Path) -> Path:
    """Create a sheet with two distinct sprites for auto-detect mode."""
    img = Image.new("RGBA", (100, 50), (0, 0, 0, 0))
    for x in range(5, 25):
        for y in range(5, 25):
            img.putpixel((x, y), (255, 0, 0, 255))
    for x in range(60, 80):
        for y in range(5, 25):
            img.putpixel((x, y), (0, 255, 0, 255))
    path = tmp_path / "auto_sheet.png"
    img.save(str(path))
    return path


@pytest.fixture()
def metadata_file(tmp_path: Path, grid_sheet: Path) -> Path:
    """Create a JSON metadata file for the grid sheet."""
    meta = {
        "sprite_sheet": grid_sheet.name,
        "columns": 2,
        "rows": 2,
        "padding": 0,
        "frames": [
            {"name": "red", "x": 0, "y": 0, "width": 32, "height": 32},
            {"name": "green", "x": 32, "y": 0, "width": 32, "height": 32},
            {"name": "blue", "x": 0, "y": 32, "width": 32, "height": 32},
            {"name": "yellow", "x": 32, "y": 32, "width": 32, "height": 32},
        ],
    }
    path = tmp_path / "meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


# ── Metadata & Parameters ────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: SpriteExtractorTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "sprite_extractor"
        assert tool.category == "Image"
        assert tool.display_name == "Sprite Extractor"

    def test_define_parameters_returns_list(self, tool: SpriteExtractorTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 8
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: SpriteExtractorTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_imagedata(self, tool: SpriteExtractorTool) -> None:
        """Sprite extractor accepts ``ImageData`` from a pipeline."""
        assert ImageData in tool.input_types()

    def test_output_types_contain_pathlist(self, tool: SpriteExtractorTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()


# ── Validation ────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``validate()``."""

    def test_rejects_invalid_mode(self, tool: SpriteExtractorTool) -> None:
        """Validation raises for an unknown mode."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.validate({"mode": "manual", "output_format": "png"})

    def test_rejects_invalid_format(self, tool: SpriteExtractorTool) -> None:
        """Validation raises for an unsupported format."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.run(params={"output_format": "gif", "mode": "auto", "input": "x.png"})

    def test_accepts_valid_grid_params(self, tool: SpriteExtractorTool) -> None:
        """Validation passes for valid grid parameters."""
        tool.validate(
            {
                "mode": "grid",
                "output_format": "png",
                "frame_width": 32,
                "frame_height": 32,
            }
        )


# ── Execution ─────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_grid_mode(self, tool: SpriteExtractorTool, grid_sheet: Path, tmp_path: Path) -> None:
        """Grid mode extracts the expected number of sprites."""
        out = tmp_path / "grid_out"
        result = tool.run(
            params={
                "input": grid_sheet,
                "output_dir": out,
                "mode": "grid",
                "frame_width": 32,
                "frame_height": 32,
                "output_format": "png",
            }
        )
        assert isinstance(result, SpriteExtractionResult)
        assert result.count == 4

    def test_auto_mode(self, tool: SpriteExtractorTool, auto_sheet: Path, tmp_path: Path) -> None:
        """Auto mode detects sprites."""
        out = tmp_path / "auto_out"
        result = tool.run(
            params={
                "input": auto_sheet,
                "output_dir": out,
                "mode": "auto",
                "output_format": "png",
            }
        )
        assert isinstance(result, SpriteExtractionResult)
        assert result.count == 2

    def test_metadata_mode(
        self,
        tool: SpriteExtractorTool,
        grid_sheet: Path,
        metadata_file: Path,
        tmp_path: Path,
    ) -> None:
        """Metadata mode extracts sprites using JSON coordinates."""
        out = tmp_path / "meta_out"
        result = tool.run(
            params={
                "input": grid_sheet,
                "output_dir": out,
                "mode": "metadata",
                "metadata_path": metadata_file,
                "output_format": "png",
            }
        )
        assert isinstance(result, SpriteExtractionResult)
        assert result.count == 4

    def test_pipeline_input(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Tool accepts ``ImageData`` as pipeline input."""
        tool = SpriteExtractorTool()
        out = tmp_path / "pipe_out"
        input_data = ImageData(path=grid_sheet, width=64, height=64, format="png")
        result = tool.run(
            params={
                "output_dir": out,
                "mode": "grid",
                "frame_width": 32,
                "frame_height": 32,
                "output_format": "png",
            },
            input_data=input_data,
        )
        assert result.count == 4

    def test_default_output_dir(self, tool: SpriteExtractorTool, grid_sheet: Path) -> None:
        """When output_dir is None, defaults to 'sprites/' next to input."""
        result = tool.run(
            params={
                "input": grid_sheet,
                "output_dir": None,
                "mode": "grid",
                "frame_width": 32,
                "frame_height": 32,
                "output_format": "png",
            }
        )
        assert result.output_dir.name == "sprites"
        assert result.output_dir.parent == grid_sheet.parent

    def test_default_base_name(self, tool: SpriteExtractorTool, grid_sheet: Path, tmp_path: Path) -> None:
        """When base_name is None, defaults to input filename stem."""
        out = tmp_path / "name_out"
        result = tool.run(
            params={
                "input": grid_sheet,
                "output_dir": out,
                "base_name": None,
                "mode": "grid",
                "frame_width": 32,
                "frame_height": 32,
                "output_format": "png",
            }
        )
        assert result.images[0].path.name.startswith("sheet_")

    def test_event_bus_receives_events(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = SpriteExtractorTool(event_bus=bus)
        tool.run(
            params={
                "input": grid_sheet,
                "output_dir": tmp_path / "ev_out",
                "mode": "grid",
                "frame_width": 32,
                "frame_height": 32,
                "output_format": "png",
            }
        )

        assert len(events) == 4
        assert events[0]["tool"] == "sprite_extractor"
