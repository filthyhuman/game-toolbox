"""Tests for sprite extraction logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from game_toolbox.core.datatypes import SpriteExtractionResult
from game_toolbox.core.events import EventBus
from game_toolbox.core.exceptions import ToolError, ValidationError
from game_toolbox.tools.sprite_extractor.logic import (
    _format_index,
    extract_auto_detect,
    extract_from_metadata,
    extract_grid,
    validate_extraction_params,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def grid_sheet(tmp_path: Path) -> Path:
    """Create a 64x64 sprite sheet with a 2x2 grid of 32x32 coloured squares."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    colours = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    for i, colour in enumerate(colours):
        col, row = i % 2, i // 2
        tile = Image.new("RGBA", (32, 32), colour)
        img.paste(tile, (col * 32, row * 32))
    path = tmp_path / "grid_sheet.png"
    img.save(str(path))
    return path


@pytest.fixture()
def auto_detect_sheet(tmp_path: Path) -> Path:
    """Create a transparent sheet with three small sprites at known positions."""
    img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    # Sprite 1: top-left area
    for x in range(10, 30):
        for y in range(10, 30):
            img.putpixel((x, y), (255, 0, 0, 255))
    # Sprite 2: top-right area
    for x in range(100, 120):
        for y in range(10, 30):
            img.putpixel((x, y), (0, 255, 0, 255))
    # Sprite 3: bottom-left area
    for x in range(10, 30):
        for y in range(60, 80):
            img.putpixel((x, y), (0, 0, 255, 255))
    path = tmp_path / "auto_sheet.png"
    img.save(str(path))
    return path


@pytest.fixture()
def metadata_file(tmp_path: Path, grid_sheet: Path) -> Path:
    """Create a sprite_sheet-style JSON metadata file for the grid sheet."""
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


# ── TestFormatIndex ──────────────────────────────────────────────────────


class TestFormatIndex:
    """Tests for the ``_format_index`` helper."""

    def test_two_digit_padding(self) -> None:
        """Uses 2 digits when total < 100."""
        assert _format_index(0, 16) == "01"
        assert _format_index(15, 16) == "16"

    def test_three_digit_padding(self) -> None:
        """Uses 3 digits when total >= 100."""
        assert _format_index(0, 100) == "001"
        assert _format_index(99, 100) == "100"

    def test_one_based_numbering(self) -> None:
        """Index 0 maps to 1."""
        assert _format_index(0, 5) == "01"
        assert _format_index(4, 5) == "05"


# ── TestExtractGrid ─────────────────────────────────────────────────────


class TestExtractGrid:
    """Tests for ``extract_grid``."""

    def test_by_frame_size(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Extract by explicit frame dimensions."""
        out = tmp_path / "out_frame"
        result = extract_grid(grid_sheet, out, "sprite", frame_width=32, frame_height=32)

        assert isinstance(result, SpriteExtractionResult)
        assert result.count == 4
        assert len(result.images) == 4
        assert result.output_dir == out

    def test_by_cols_rows(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Extract by specifying column and row count."""
        out = tmp_path / "out_grid"
        result = extract_grid(grid_sheet, out, "sprite", columns=2, rows=2)

        assert result.count == 4

    def test_filenames_are_numbered(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Output filenames are zero-padded 1-based."""
        out = tmp_path / "out_names"
        result = extract_grid(grid_sheet, out, "tile", frame_width=32, frame_height=32)

        names = [img.path.name for img in result.images]
        assert names[0] == "tile_01.png"
        assert names[3] == "tile_04.png"

    def test_creates_output_dir(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Output directory is created if it does not exist."""
        out = tmp_path / "deep" / "nested" / "dir"
        result = extract_grid(grid_sheet, out, "s", frame_width=32, frame_height=32)
        assert result.output_dir.exists()

    def test_emits_progress_events(self, grid_sheet: Path, tmp_path: Path) -> None:
        """EventBus receives progress and completed events."""
        bus = EventBus()
        progress: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []
        bus.subscribe("progress", lambda **kw: progress.append(kw))
        bus.subscribe("completed", lambda **kw: completed.append(kw))

        extract_grid(grid_sheet, tmp_path / "ev", "s", frame_width=32, frame_height=32, event_bus=bus)

        assert len(progress) == 4
        assert progress[0]["tool"] == "sprite_extractor"
        assert len(completed) == 1

    def test_raises_on_invalid_image(self, tmp_path: Path) -> None:
        """ToolError is raised for an unreadable image file."""
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        with pytest.raises(ToolError, match="could not be opened"):
            extract_grid(bad, tmp_path / "out", "s", frame_width=32, frame_height=32)

    def test_webp_format(self, grid_sheet: Path, tmp_path: Path) -> None:
        """Can extract to WebP format."""
        out = tmp_path / "webp_out"
        result = extract_grid(grid_sheet, out, "sprite", frame_width=32, frame_height=32, output_format="webp")
        assert result.images[0].format == "webp"
        assert result.images[0].path.suffix == ".webp"


# ── TestExtractFromMetadata ──────────────────────────────────────────────


class TestExtractFromMetadata:
    """Tests for ``extract_from_metadata``."""

    def test_correct_regions(self, grid_sheet: Path, metadata_file: Path, tmp_path: Path) -> None:
        """Extracts correct regions from metadata coordinates."""
        out = tmp_path / "meta_out"
        result = extract_from_metadata(grid_sheet, metadata_file, out, "sprite")

        assert result.count == 4
        # The metadata uses "name" field, so filenames should use those.
        names = [img.path.stem for img in result.images]
        assert "red" in names
        assert "green" in names

    def test_invalid_json(self, grid_sheet: Path, tmp_path: Path) -> None:
        """ToolError is raised when the metadata file is not valid JSON."""
        bad_meta = tmp_path / "bad.json"
        bad_meta.write_text("not json", encoding="utf-8")
        with pytest.raises(ToolError, match="could not be read as JSON"):
            extract_from_metadata(grid_sheet, bad_meta, tmp_path / "out", "s")

    def test_missing_frames_key(self, grid_sheet: Path, tmp_path: Path) -> None:
        """ToolError is raised when metadata lacks the 'frames' key."""
        bad_meta = tmp_path / "no_frames.json"
        bad_meta.write_text(json.dumps({"columns": 2}), encoding="utf-8")
        with pytest.raises(ToolError, match="missing the 'frames' key"):
            extract_from_metadata(grid_sheet, bad_meta, tmp_path / "out", "s")


# ── TestExtractAutoDetect ────────────────────────────────────────────────


class TestExtractAutoDetect:
    """Tests for ``extract_auto_detect``."""

    def test_detects_sprites(self, auto_detect_sheet: Path, tmp_path: Path) -> None:
        """Detects the expected number of sprites."""
        out = tmp_path / "auto_out"
        result = extract_auto_detect(auto_detect_sheet, out, "sprite")

        assert result.count == 3

    def test_sorted_order(self, auto_detect_sheet: Path, tmp_path: Path) -> None:
        """Sprites are sorted top-to-bottom, left-to-right."""
        out = tmp_path / "sorted_out"
        result = extract_auto_detect(auto_detect_sheet, out, "sprite")

        # First sprite should be top-left (y~10), second top-right (y~10),
        # third bottom-left (y~60).
        assert result.count == 3
        # First two are in the top row, third in the bottom row.
        y_coords = [img.path for img in result.images]
        assert len(y_coords) == 3

    def test_fully_transparent_returns_zero(self, tmp_path: Path) -> None:
        """A fully transparent sheet produces zero sprites."""
        transparent = tmp_path / "empty.png"
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(str(transparent))

        result = extract_auto_detect(transparent, tmp_path / "out", "sprite")
        assert result.count == 0

    def test_filters_noise(self, tmp_path: Path) -> None:
        """Regions smaller than min_area are filtered out."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        # Tiny 2x2 region (area 4, less than default min_area=16)
        for x in range(10, 12):
            for y in range(10, 12):
                img.putpixel((x, y), (255, 0, 0, 255))
        # Larger 10x10 region (area 100, should be kept)
        for x in range(50, 60):
            for y in range(50, 60):
                img.putpixel((x, y), (0, 255, 0, 255))
        path = tmp_path / "noise.png"
        img.save(str(path))

        result = extract_auto_detect(path, tmp_path / "out", "sprite")
        assert result.count == 1


# ── TestValidateExtractionParams ─────────────────────────────────────────


class TestValidateExtractionParams:
    """Tests for ``validate_extraction_params``."""

    def test_grid_requires_one_pair(self) -> None:
        """Grid mode with no frame size and no cols/rows raises."""
        with pytest.raises(ValidationError, match="requires either"):
            validate_extraction_params(mode="grid", output_format="png")

    def test_grid_rejects_both_pairs(self) -> None:
        """Grid mode with both pairs raises."""
        with pytest.raises(ValidationError, match="not both"):
            validate_extraction_params(
                mode="grid",
                output_format="png",
                frame_width=32,
                frame_height=32,
                columns=2,
                rows=2,
            )

    def test_grid_rejects_partial_frame_size(self) -> None:
        """Grid mode with only frame_width (no frame_height) raises."""
        with pytest.raises(ValidationError, match="Both frame_width and frame_height"):
            validate_extraction_params(mode="grid", output_format="png", frame_width=32)

    def test_grid_rejects_partial_grid_dims(self) -> None:
        """Grid mode with only columns (no rows) raises."""
        with pytest.raises(ValidationError, match="Both columns and rows"):
            validate_extraction_params(mode="grid", output_format="png", columns=2)

    def test_metadata_requires_path(self) -> None:
        """Metadata mode without metadata_path raises."""
        with pytest.raises(ValidationError, match="requires a metadata_path"):
            validate_extraction_params(mode="metadata", output_format="png")

    def test_invalid_format(self) -> None:
        """Unsupported output format raises."""
        with pytest.raises(ValidationError, match="Output format"):
            validate_extraction_params(mode="grid", output_format="gif", frame_width=32, frame_height=32)

    def test_invalid_mode(self) -> None:
        """Unsupported mode raises."""
        with pytest.raises(ValidationError, match="Mode must be"):
            validate_extraction_params(mode="manual", output_format="png")

    def test_valid_grid_frame_size(self) -> None:
        """Valid grid-with-frame-size params pass."""
        validate_extraction_params(mode="grid", output_format="png", frame_width=32, frame_height=32)

    def test_valid_grid_cols_rows(self) -> None:
        """Valid grid-with-cols/rows params pass."""
        validate_extraction_params(mode="grid", output_format="webp", columns=4, rows=4)

    def test_valid_auto(self) -> None:
        """Valid auto mode params pass."""
        validate_extraction_params(mode="auto", output_format="png")

    def test_valid_metadata(self) -> None:
        """Valid metadata mode params pass."""
        validate_extraction_params(mode="metadata", output_format="png", metadata_path=Path("meta.json"))
