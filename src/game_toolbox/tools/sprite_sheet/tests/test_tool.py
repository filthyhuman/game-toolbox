"""Tests for SpriteSheetTool (BaseTool integration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import ImageData, PathList, SpriteSheetResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.sprite_sheet.tool import SpriteSheetTool

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> SpriteSheetTool:
    """Return a fresh SpriteSheetTool instance."""
    return SpriteSheetTool()


@pytest.fixture()
def four_images(tmp_path: Path) -> list[Path]:
    """Create four 32x32 RGBA test images."""
    paths: list[Path] = []
    for i in range(4):
        img_path = tmp_path / f"frame_{i:05d}.png"
        img = Image.new("RGBA", (32, 32), color=(i * 60, 100, 200, 255))
        img.save(str(img_path))
        paths.append(img_path)
    return paths


# ── Metadata & Parameters ─────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: SpriteSheetTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "sprite_sheet"
        assert tool.category == "Image"
        assert tool.display_name == "Sprite Sheet"

    def test_define_parameters_returns_list(self, tool: SpriteSheetTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 4
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: SpriteSheetTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_pathlist(self, tool: SpriteSheetTool) -> None:
        """Sprite sheet accepts ``PathList`` from a pipeline."""
        assert PathList in tool.input_types()

    def test_output_types_contain_imagedata(self, tool: SpriteSheetTool) -> None:
        """Output types include ``ImageData``."""
        assert ImageData in tool.output_types()


# ── Validation ─────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``run()``."""

    def test_rejects_invalid_metadata_format(self, tool: SpriteSheetTool) -> None:
        """Validation raises when metadata format is not in allowed choices."""
        with pytest.raises(ValidationError, match="must be one of"):
            tool.run(params={"metadata_format": "yaml", "inputs": []})

    def test_rejects_invalid_columns(self, tool: SpriteSheetTool) -> None:
        """Validation raises when columns is < 1."""
        with pytest.raises(ValidationError, match="Columns"):
            tool.validate({"columns": 0})

    def test_accepts_valid_params(self, tool: SpriteSheetTool) -> None:
        """Validation passes for valid parameters."""
        tool.validate({"columns": 4, "padding": 1, "metadata_format": "json"})

    def test_accepts_none_columns(self, tool: SpriteSheetTool) -> None:
        """Validation passes when columns is None (auto)."""
        tool.validate({"columns": None, "padding": 0, "metadata_format": "css"})


# ── Execution ──────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_run_returns_sprite_sheet_result(
        self, tool: SpriteSheetTool, four_images: list[Path], tmp_path: Path
    ) -> None:
        """Happy path: ``run()`` returns a ``SpriteSheetResult``."""
        out = tmp_path / "out" / "sheet.png"

        result = tool.run(
            params={
                "inputs": four_images,
                "output": out,
                "columns": 2,
                "padding": 1,
                "metadata_format": "json",
            },
        )

        assert isinstance(result, SpriteSheetResult)
        assert result.columns == 2
        assert result.rows == 2
        assert len(result.frames) == 4

    def test_run_with_pipeline_input(self, four_images: list[Path], tmp_path: Path) -> None:
        """Tool accepts ``PathList`` as pipeline input data."""
        out = tmp_path / "pipe_sheet.png"

        tool = SpriteSheetTool()
        result = tool.run(
            params={
                "inputs": [],
                "output": out,
                "columns": None,
                "padding": 0,
                "metadata_format": "json",
            },
            input_data=PathList(paths=tuple(four_images)),
        )

        assert result.columns == 2
        assert len(result.frames) == 4

    def test_run_uses_event_bus(self, four_images: list[Path], tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = SpriteSheetTool(event_bus=bus)
        tool.run(
            params={
                "inputs": four_images,
                "output": tmp_path / "sheet.png",
                "columns": 2,
                "padding": 1,
                "metadata_format": "json",
            },
        )

        assert len(events) == 4
        assert events[0]["tool"] == "sprite_sheet"

    def test_run_default_output(self, four_images: list[Path], tmp_path: Path) -> None:
        """When output is None, defaults to 'sprite-sheet/' next to first input."""
        tool = SpriteSheetTool()
        result = tool.run(
            params={
                "inputs": four_images,
                "output": None,
                "columns": 2,
                "padding": 0,
                "metadata_format": "json",
            },
        )

        assert result.sheet.path.parent.name == "sprite-sheet"
        assert result.sheet.path.parent.parent == tmp_path
        assert result.sheet.path.name == "sprite_sheet.png"

    def test_run_generates_metadata(self, four_images: list[Path], tmp_path: Path) -> None:
        """Metadata file is generated alongside the sprite sheet."""
        out = tmp_path / "sheet.png"
        tool = SpriteSheetTool()
        result = tool.run(
            params={
                "inputs": four_images,
                "output": out,
                "columns": 2,
                "padding": 1,
                "metadata_format": "json",
            },
        )

        assert result.metadata_path.exists()
        assert result.metadata_path.suffix == ".json"
