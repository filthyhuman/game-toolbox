"""Tests for AtlasUnpackerTool (BaseTool integration)."""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.base_tool import ToolParameter
from game_toolbox.core.datatypes import AtlasUnpackResult, PathList
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ValidationError
from game_toolbox.tools.atlas_unpacker.tool import AtlasUnpackerTool

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_atlas_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create a matching .plist + .png atlas pair."""
    # Create 64x64 atlas
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    colours = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    for i, colour in enumerate(colours):
        tile = Image.new("RGBA", (32, 32), colour)
        img.paste(tile, ((i % 2) * 32, (i // 2) * 32))
    png_path = tmp_path / "test.png"
    img.save(str(png_path))

    # Create plist
    plist_data: dict[str, Any] = {
        "frames": {
            "red.png": {
                "frame": "{{0,0},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "green.png": {
                "frame": "{{32,0},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "blue.png": {
                "frame": "{{0,32},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
            "yellow.png": {
                "frame": "{{32,32},{32,32}}",
                "rotated": False,
                "sourceSize": "{32,32}",
                "offset": "{0,0}",
            },
        },
        "metadata": {"textureFileName": "test.png"},
    }
    plist_path = tmp_path / "test.plist"
    with plist_path.open("wb") as fh:
        plistlib.dump(plist_data, fh)

    return plist_path, png_path


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> AtlasUnpackerTool:
    """Return a fresh AtlasUnpackerTool instance."""
    return AtlasUnpackerTool()


@pytest.fixture()
def atlas_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create a matching .plist + .png atlas pair."""
    return _make_atlas_pair(tmp_path)


# ── Metadata & Parameters ────────────────────────────────────────────────


class TestToolMetadata:
    """Tests for tool identity and parameter schema."""

    def test_tool_name_and_category(self, tool: AtlasUnpackerTool) -> None:
        """Tool exposes the expected name and category."""
        assert tool.name == "atlas_unpacker"
        assert tool.category == "Image"
        assert tool.display_name == "Atlas Unpacker"

    def test_define_parameters_returns_list(self, tool: AtlasUnpackerTool) -> None:
        """``define_parameters`` returns a non-empty list of ``ToolParameter``."""
        params = tool.define_parameters()
        assert len(params) >= 4
        assert all(isinstance(p, ToolParameter) for p in params)

    def test_parameter_names_are_unique(self, tool: AtlasUnpackerTool) -> None:
        """No two parameters share the same name."""
        names = [p.name for p in tool.define_parameters()]
        assert len(names) == len(set(names))

    def test_input_types_contain_pathlist(self, tool: AtlasUnpackerTool) -> None:
        """Atlas unpacker accepts ``PathList`` from a pipeline."""
        assert PathList in tool.input_types()

    def test_output_types_contain_pathlist(self, tool: AtlasUnpackerTool) -> None:
        """Output types include ``PathList``."""
        assert PathList in tool.output_types()


# ── Validation ────────────────────────────────────────────────────────────


class TestToolValidation:
    """Tests for the BaseTool validation triggered by ``validate()``."""

    def test_rejects_missing_input(self, tool: AtlasUnpackerTool) -> None:
        """Execution raises when no input is provided and no pipeline data."""
        with pytest.raises(ValidationError, match="No input"):
            tool.run(params={"input": None})

    def test_rejects_nonexistent_file(self, tool: AtlasUnpackerTool, tmp_path: Path) -> None:
        """Validation raises for a missing plist file."""
        with pytest.raises(ValidationError, match="does not exist"):
            tool.validate({"input": tmp_path / "missing.plist"})

    def test_rejects_wrong_extension(self, tool: AtlasUnpackerTool, tmp_path: Path) -> None:
        """Validation raises for a non-.plist file."""
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        with pytest.raises(ValidationError, match=r"Expected a \.plist"):
            tool.validate({"input": txt})

    def test_accepts_valid_plist(self, tool: AtlasUnpackerTool, atlas_pair: tuple[Path, Path]) -> None:
        """Validation passes for a valid plist file."""
        plist_path, _ = atlas_pair
        tool.validate({"input": plist_path})


# ── Execution ─────────────────────────────────────────────────────────────


class TestToolExecution:
    """Tests for the full ``run()`` lifecycle."""

    def test_extract_mode(self, tool: AtlasUnpackerTool, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Normal extraction produces the expected result."""
        plist_path, _ = atlas_pair
        out = tmp_path / "extract_out"

        result = tool.run(params={"input": plist_path, "output_dir": out})

        assert isinstance(result, AtlasUnpackResult)
        assert result.count == 4
        assert result.output_dir == out

    def test_dry_run_mode(self, tool: AtlasUnpackerTool, atlas_pair: tuple[Path, Path]) -> None:
        """Dry run returns count=0 without extracting files."""
        plist_path, _ = atlas_pair

        result = tool.run(params={"input": plist_path, "dry_run": True})

        assert isinstance(result, AtlasUnpackResult)
        assert result.count == 0
        assert len(result.images) == 0

    def test_default_output_dir(self, tool: AtlasUnpackerTool, atlas_pair: tuple[Path, Path]) -> None:
        """When output_dir is None, defaults to 'unpacked/' next to input."""
        plist_path, _ = atlas_pair

        result = tool.run(params={"input": plist_path, "output_dir": None})

        assert result.output_dir.name == "unpacked"
        assert result.output_dir.parent == plist_path.parent

    def test_pipeline_input(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Tool accepts ``PathList`` as pipeline input."""
        plist_path, _ = atlas_pair
        tool = AtlasUnpackerTool()
        out = tmp_path / "pipe_out"

        input_data = PathList(paths=(plist_path,))
        result = tool.run(params={"output_dir": out}, input_data=input_data)

        assert result.count == 4

    def test_event_bus_receives_events(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Progress events are emitted through the injected event bus."""
        plist_path, _ = atlas_pair
        bus = EventBus()
        events: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: events.append(kw))

        tool = AtlasUnpackerTool(event_bus=bus)
        tool.run(params={"input": plist_path, "output_dir": tmp_path / "ev_out"})

        assert len(events) == 4
        assert events[0]["tool"] == "atlas_unpacker"

    def test_skip_existing_via_tool(self, atlas_pair: tuple[Path, Path], tmp_path: Path) -> None:
        """Skip existing works through the tool interface."""
        plist_path, _ = atlas_pair
        out = tmp_path / "skip_out"
        out.mkdir()
        (out / "red.png").write_bytes(b"existing")

        tool = AtlasUnpackerTool()
        result = tool.run(params={"input": plist_path, "output_dir": out, "skip_existing": True})

        assert result.count == 3
